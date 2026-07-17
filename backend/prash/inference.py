"""
Prash AI Engine — Inference Pipeline.

Autoregressive text generation for the Prash transformer model with:
- Temperature-scaled sampling
- Top-k filtering (zero out logits below the k-th largest)
- Top-p (nucleus) filtering
- Entropy-based confidence scoring
- Synchronous and async streaming generation

All inference runs under ``torch.no_grad()`` with the model in eval mode.
No external AI APIs — pure PyTorch generation from scratch.
"""

from __future__ import annotations

import asyncio
import math
from typing import AsyncGenerator, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from loguru import logger


class PrashInference:
    """
    Autoregressive inference engine for the Prash transformer.

    Generates text token-by-token using temperature scaling, top-k, and
    top-p (nucleus) sampling.  Provides an entropy-based confidence metric
    so the JARVIS orchestrator can decide whether to fall back to a larger
    external model.

    Args:
        model:     Instantiated PrashTransformer in eval-ready state.
        tokenizer: PrashTokenizer with encode/decode and special-token IDs.
        config:    PrashConfig with max_seq_len, vocab_size, etc.
        device:    Torch device string ('cpu' or 'cuda').
    """

    def __init__(
        self,
        model: nn.Module,
        tokenizer: object,
        config: object,
        device: str = "cpu",
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.device = torch.device(device)

        # Move model to device and lock into eval mode
        self.model.to(self.device)
        self.model.eval()

        # Cache special token IDs
        self.bos_id: int = getattr(tokenizer, "bos_id", 1)
        self.eos_id: int = getattr(tokenizer, "eos_id", 2)
        self.pad_id: int = getattr(tokenizer, "pad_id", 0)

        self.max_seq_len: int = getattr(config, "max_seq_len", 512)
        self.vocab_size: int = getattr(config, "vocab_size", 4096)

        logger.info(
            "PrashInference ready — device={}, vocab={}, max_seq_len={}",
            self.device,
            self.vocab_size,
            self.max_seq_len,
        )

    # ── Sampling helpers ─────────────────────────────────────────────────

    @staticmethod
    def _apply_temperature(logits: torch.Tensor, temperature: float) -> torch.Tensor:
        """
        Scale logits by temperature.

        Args:
            logits:      Raw logits tensor of shape ``(vocab_size,)``.
            temperature: Sampling temperature (>0).  Lower = more deterministic.

        Returns:
            Temperature-scaled logits.
        """
        if temperature <= 0:
            temperature = 1e-8  # avoid division by zero
        return logits / temperature

    @staticmethod
    def _apply_top_k(logits: torch.Tensor, top_k: int) -> torch.Tensor:
        """
        Zero out all logits below the top-k largest values.

        After this operation only the *top_k* most probable tokens retain
        their original logit values; everything else is set to ``-inf``.

        Args:
            logits: 1-D logits tensor of shape ``(vocab_size,)``.
            top_k:  Number of top tokens to keep.

        Returns:
            Filtered logits tensor.
        """
        if top_k <= 0 or top_k >= logits.size(-1):
            return logits

        # kthvalue is ascending, so we want the (V - k)-th smallest = k-th largest
        threshold = torch.topk(logits, top_k).values[-1]
        logits = logits.clone()
        logits[logits < threshold] = float("-inf")
        return logits

    @staticmethod
    def _apply_top_p(logits: torch.Tensor, top_p: float) -> torch.Tensor:
        """
        Apply nucleus (top-p) filtering.

        Sorts tokens by descending probability, computes the cumulative
        distribution, and zeros out all tokens whose cumulative probability
        exceeds *top_p*.

        Args:
            logits: 1-D logits tensor of shape ``(vocab_size,)``.
            top_p:  Cumulative probability threshold (0.0–1.0).

        Returns:
            Filtered logits tensor.
        """
        if top_p >= 1.0:
            return logits

        sorted_logits, sorted_indices = torch.sort(logits, descending=True)
        cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

        # Identify tokens to remove: cumulative prob exceeds top_p
        # Shift right so the first token above the threshold is kept
        sorted_mask = cumulative_probs - F.softmax(sorted_logits, dim=-1) >= top_p
        sorted_logits[sorted_mask] = float("-inf")

        # Scatter back to original ordering
        logits = logits.clone()
        logits.scatter_(0, sorted_indices, sorted_logits)
        return logits

    @staticmethod
    def _compute_entropy(logits: torch.Tensor) -> float:
        """
        Compute the Shannon entropy (in nats) of the softmax distribution.

        Higher entropy → model is less certain about the next token.

        Args:
            logits: 1-D logits tensor of shape ``(vocab_size,)``.

        Returns:
            Entropy as a Python float.
        """
        probs = F.softmax(logits, dim=-1)
        # Clamp to avoid log(0)
        log_probs = torch.log(probs.clamp(min=1e-12))
        entropy = -(probs * log_probs).sum().item()
        return entropy

    # ── Core generation ──────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_k: int = 50,
        top_p: float = 0.9,
    ) -> Tuple[str, float]:
        """
        Generate a complete response for the given prompt.

        Performs autoregressive sampling:
            1. Encode prompt → token IDs
            2. Loop: forward pass → last-position logits → temperature →
               top-k → top-p → sample → append
            3. Stop on ``<EOS>`` or *max_new_tokens* reached

        Args:
            prompt:         Input text to continue from.
            max_new_tokens: Maximum number of tokens to generate.
            temperature:    Sampling temperature.
            top_k:          Top-k filter width.
            top_p:          Nucleus sampling threshold.

        Returns:
            Tuple of ``(generated_text, avg_entropy)`` where *avg_entropy*
            is the mean Shannon entropy across all generated token steps.
        """
        # Encode prompt if it is a string
        if isinstance(prompt, str):
            prompt_ids = self.tokenizer.encode(prompt)
        else:
            prompt_ids = prompt

        if not prompt_ids:
            logger.warning("Empty prompt after tokenization")
            return ("", float("inf"))

        input_ids = torch.tensor([prompt_ids], dtype=torch.long, device=self.device)

        generated_tokens: List[int] = []
        entropies: List[float] = []

        with torch.no_grad():
            for _ in range(max_new_tokens):
                # Truncate to max_seq_len if the context has grown too long
                if input_ids.size(1) > self.max_seq_len:
                    input_ids = input_ids[:, -self.max_seq_len :]

                # Forward pass
                logits, _ = self.model(input_ids)  # (1, T, vocab_size)

                # Get logits for the last position
                next_logits = logits[0, -1, :]  # (vocab_size,)

                # Record raw entropy before any filtering
                entropies.append(self._compute_entropy(next_logits))

                # Apply temperature scaling
                next_logits = self._apply_temperature(next_logits, temperature)

                # Apply top-k filtering
                next_logits = self._apply_top_k(next_logits, top_k)

                # Apply top-p (nucleus) filtering
                next_logits = self._apply_top_p(next_logits, top_p)

                # Sample from the filtered distribution
                probs = F.softmax(next_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)  # (1,)

                token_id = next_token.item()

                # Stop on EOS
                if token_id == self.eos_id:
                    break

                generated_tokens.append(token_id)

                # Append to context for next iteration
                input_ids = torch.cat(
                    [input_ids, next_token.unsqueeze(0)], dim=1
                )

        # Decode generated tokens
        generated_text = self.tokenizer.decode(generated_tokens)

        # Average entropy across all generated steps
        avg_entropy = (
            sum(entropies) / len(entropies) if entropies else float("inf")
        )

        logger.debug(
            "Generated {} tokens, avg_entropy={:.3f}",
            len(generated_tokens),
            avg_entropy,
        )
        return (generated_text, avg_entropy)

    # ── Streaming generation ─────────────────────────────────────────────

    async def generate_stream(
        self,
        prompt: str,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_k: int = 50,
        top_p: float = 0.9,
    ) -> AsyncGenerator[Tuple[str, float], None]:
        """
        Streaming version of :meth:`generate`.

        Yields ``(token_text, 0.0)`` for each generated token as soon as
        it is produced.  After the final token (or ``<EOS>``), yields
        ``("", avg_entropy)`` as a sentinel indicating generation is complete.

        This is an ``async`` generator — use ``async for`` to consume.

        Args:
            prompt:         Input text to continue from.
            max_new_tokens: Maximum number of tokens to generate.
            temperature:    Sampling temperature.
            top_k:          Top-k filter width.
            top_p:          Nucleus sampling threshold.

        Yields:
            Tuples of ``(token_text, entropy)`` — intermediate yields have
            entropy ``0.0``; the final sentinel has the average entropy.
        """
        # Encode prompt
        # Encode prompt if it is a string
        if isinstance(prompt, str):
            prompt_ids = self.tokenizer.encode(prompt)
        else:
            prompt_ids = prompt

        if not prompt_ids:
            logger.warning("Empty prompt after tokenization (stream)")
            yield ("", float("inf"))
            return

        input_ids = torch.tensor([prompt_ids], dtype=torch.long, device=self.device)

        entropies: List[float] = []

        with torch.no_grad():
            for _ in range(max_new_tokens):
                # Truncate context to max_seq_len
                if input_ids.size(1) > self.max_seq_len:
                    input_ids = input_ids[:, -self.max_seq_len :]

                # Forward pass
                logits, _ = self.model(input_ids)  # (1, T, vocab_size)
                next_logits = logits[0, -1, :]  # (vocab_size,)

                # Record entropy
                entropies.append(self._compute_entropy(next_logits))

                # Temperature → top-k → top-p → sample
                next_logits = self._apply_temperature(next_logits, temperature)
                next_logits = self._apply_top_k(next_logits, top_k)
                next_logits = self._apply_top_p(next_logits, top_p)

                probs = F.softmax(next_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)

                token_id = next_token.item()

                # Stop on EOS
                if token_id == self.eos_id:
                    break

                # Decode this single token
                token_text = self.tokenizer.decode([token_id])

                # Yield the token immediately
                yield (token_text, 0.0)

                # Append to context
                input_ids = torch.cat(
                    [input_ids, next_token.unsqueeze(0)], dim=1
                )

                # Yield control back to the event loop
                await asyncio.sleep(0)

        # Final sentinel with average entropy
        avg_entropy = (
            sum(entropies) / len(entropies) if entropies else float("inf")
        )
        logger.debug(
            "Stream complete — {} tokens, avg_entropy={:.3f}",
            len(entropies),
            avg_entropy,
        )
        yield ("", avg_entropy)

    # ── Confidence check ─────────────────────────────────────────────────

    @staticmethod
    def is_confident(entropy: float, threshold: float = 3.0) -> bool:
        """
        Determine whether the model's response is confident enough to use
        without falling back to an external LLM.

        Lower entropy → the model is more certain about its predictions.

        Args:
            entropy:   Average entropy from :meth:`generate` or stream sentinel.
            threshold: Maximum acceptable entropy.  Default ``3.0`` is
                       calibrated for the Prash vocab size (~4 k tokens).

        Returns:
            ``True`` if the model is confident (entropy < threshold).
        """
        return entropy < threshold
