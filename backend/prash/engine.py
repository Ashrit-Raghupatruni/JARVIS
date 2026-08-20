"""
Prash AI Engine — Main Orchestrator.

This is the top-level entry point that the JARVIS ``LLMService`` calls.
It wires together the tokenizer, model, inference engine, and memory
manager into a single cohesive interface.

Responsibilities:
- Load/initialise all Prash components on startup
- Build prompts from conversation history via PrashMemory
- Run synchronous and streaming inference via PrashInference
- Report confidence (entropy) so the router knows whether to fall back
- Provide health/status introspection for the API layer

All imports from sibling modules are guarded so a missing tokenizer
or model file produces a clear error instead of a cryptic traceback.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import torch

from loguru import logger

# ── Project root (JARVIS/) ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class PrashEngine:
    """
    High-level orchestrator for the Prash custom AI engine.

    Manages the full lifecycle: loading the tokenizer and model from disk,
    running inference (single-shot and streaming), maintaining conversation
    context via ``PrashMemory``, and exposing a status API.

    This class is designed to be instantiated once and shared across the
    application.  Call :meth:`init` after construction to load weights.

    Args:
        model_dir: Directory containing tokenizer, config, and checkpoint
                   files.  Defaults to ``<PROJECT_ROOT>/data/prash/``.
    """

    def __init__(self, model_dir: Optional[str] = None) -> None:
        # Resolve model directory
        if model_dir is not None:
            self.model_dir = Path(model_dir)
        else:
            self.model_dir = PROJECT_ROOT / "data" / "prash"

        # Core components (populated by init())
        self.model: Optional[Any] = None
        self.tokenizer: Optional[Any] = None
        self.config: Optional[Any] = None
        self.inference: Optional[Any] = None
        self.memory: Optional[Any] = None

        # State flags
        self._available: bool = False
        self._loaded: bool = False

        # Device selection
        self.device: str = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(
            "PrashEngine created — model_dir={}, device={}",
            self.model_dir,
            self.device,
        )

    # ── Initialisation ───────────────────────────────────────────────────

    async def init(self) -> bool:
        """
        Load tokenizer, model configuration, model weights, and spin up
        the inference engine and memory manager.

        This is an ``async`` method so it can be called from the FastAPI
        startup lifecycle without blocking the event loop.

        Returns:
            ``True`` if all components loaded successfully, ``False`` on
            any error (the engine will remain unavailable).
        """
        try:
            logger.info("Initialising Prash engine …")

            # Ensure model directory exists
            self.model_dir.mkdir(parents=True, exist_ok=True)

            # ── Import sibling modules ───────────────────────────────
            try:
                from backend.prash.tokenizer import PrashTokenizer
                from backend.prash.model import PrashTransformer, PrashConfig
            except ImportError as imp_err:
                logger.error(
                    "Failed to import Prash modules (tokenizer/model): {}",
                    imp_err,
                )
                return False

            from backend.prash.inference import PrashInference
            from backend.prash.memory import PrashMemory

            # ── Resolve Checkpoint & Config ───────────────────────────
            checkpoint_path = self.model_dir / "prash_397m_model.pt"
            if not checkpoint_path.exists():
                checkpoint_path = self.model_dir / "checkpoint_latest.pt"

            ckpt_data = None
            if checkpoint_path.exists():
                try:
                    ckpt_data = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
                    logger.info("Loaded checkpoint payload from {}", checkpoint_path.name)
                except Exception as e:
                    logger.warning("Could not pre-read checkpoint payload: {}", e)

            # ── Load / create config (prefer embedded config from .pt) ─
            config_path = self.model_dir / "model_config.json"
            if isinstance(ckpt_data, dict) and "config" in ckpt_data and isinstance(ckpt_data["config"], dict):
                valid_fields = set(vars(PrashConfig()).keys())
                cfg_kwargs = {k: v for k, v in ckpt_data["config"].items() if k in valid_fields}
                self.config = PrashConfig(**cfg_kwargs)
                logger.info("Model config auto-restored from checkpoint metadata (d_model={}, n_layers={})", self.config.d_model, self.config.n_layers)
            elif config_path.exists():
                with open(config_path, "r", encoding="utf-8") as fh:
                    config_data = json.load(fh)
                valid_fields = set(vars(PrashConfig()).keys())
                cfg_kwargs = {k: v for k, v in config_data.items() if k in valid_fields}
                self.config = PrashConfig(**cfg_kwargs)
                logger.info("Model config loaded from {}", config_path.name)
            else:
                self.config = PrashConfig()
                logger.info("Default model config created")

            # ── Load tokenizer ───────────────────────────────────────
            tokenizer_path = self.model_dir / "tokenizer.json"
            if tokenizer_path.exists():
                self.tokenizer = PrashTokenizer.load(str(tokenizer_path))
                logger.info(
                    "Tokenizer loaded — vocab_size={}",
                    getattr(self.tokenizer, "vocab_size", "?"),
                )
            else:
                logger.warning(
                    "No tokenizer found at {}. Creating a default tokenizer.",
                    tokenizer_path,
                )
                self.tokenizer = PrashTokenizer()
                # Try to save so subsequent loads succeed
                try:
                    self.tokenizer.save(str(tokenizer_path))
                except Exception as save_err:
                    logger.warning("Could not save default tokenizer: {}", save_err)

            # ── Sync config vocab_size with tokenizer if needed ──────
            tok_vocab = getattr(self.tokenizer, "vocab_size", None)
            if not (isinstance(ckpt_data, dict) and "config" in ckpt_data and "vocab_size" in ckpt_data["config"]):
                if tok_vocab and tok_vocab != self.config.vocab_size:
                    logger.info(
                        "Adjusting config.vocab_size {} → {} to match tokenizer",
                        self.config.vocab_size,
                        tok_vocab,
                    )
                    self.config.vocab_size = tok_vocab

            # ── Create model ─────────────────────────────────────────
            self.model = PrashTransformer(self.config)
            self.model.to(self.device)

            n_params = sum(p.numel() for p in self.model.parameters())
            logger.info(
                "Model created — {:.2f}M params, {} layers, d_model={}",
                n_params / 1e6,
                getattr(self.config, "n_layers", "?"),
                getattr(self.config, "d_model", "?"),
            )

            # ── Load weights (if checkpoint exists) ──────────────────
            if not checkpoint_path.exists():
                checkpoint_path = self.model_dir / "checkpoint_latest.pt"
            if checkpoint_path.exists():
                try:
                    checkpoint = torch.load(
                        checkpoint_path,
                        map_location=self.device,
                        weights_only=False,
                    )
                    state_dict = (
                        checkpoint["model_state_dict"]
                        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint
                        else checkpoint
                    )

                    # Key remapping dictionary to harmonize Colab 397M model and local PrashTransformer parameter names
                    key_mapping = {
                        "tok_embeddings.weight": "tok_emb.weight",
                        "norm.weight": "final_norm.weight",
                        "head.weight": "output_head.weight"
                    }
                    
                    remapped_dict = {}
                    for k, v in state_dict.items():
                        new_k = key_mapping.get(k, k)
                        new_k = new_k.replace(".attn_norm.", ".norm1.")
                        new_k = new_k.replace(".ffn_norm.", ".norm2.")
                        new_k = new_k.replace(".attn.out_proj.", ".attn.o_proj.")
                        remapped_dict[new_k] = v

                    self.model.load_state_dict(remapped_dict, strict=False)
                    epoch = checkpoint.get("epoch", "?") if isinstance(checkpoint, dict) else "?"
                    loss = checkpoint.get("loss", "?") if isinstance(checkpoint, dict) else "?"
                    logger.info(
                        "✓ Weights successfully restored from {} (epoch={}, loss={})",
                        checkpoint_path.name,
                        epoch,
                        loss,
                    )
                    self._loaded = True
                except Exception as ckpt_err:
                    logger.warning(
                        "Failed to load checkpoint — using random weights: {}",
                        ckpt_err,
                    )
            else:
                logger.warning(
                    "No checkpoint found at {}. Model is UNTRAINED and will "
                    "produce random output. Train it first!",
                    checkpoint_path,
                )

            # ── Create inference engine ──────────────────────────────
            self.inference = PrashInference(
                model=self.model,
                tokenizer=self.tokenizer,
                config=self.config,
                device=self.device,
            )

            # ── Create memory manager ────────────────────────────────
            max_seq_len = getattr(self.config, "max_seq_len", 512)
            self.memory = PrashMemory(
                max_turns=10,
                max_tokens=max_seq_len - 64,  # leave headroom for generation
            )

            # ── Load valid vocabulary from training data ──────────────
            self.valid_vocab = set()
            train_data_path = self.model_dir / "train_data.jsonl"
            if train_data_path.exists():
                try:
                    with open(train_data_path, "r", encoding="utf-8") as fh:
                        for line in fh:
                            if line.strip():
                                data = json.loads(line)
                                text = f"{data.get('instruction', '')} {data.get('response', '')}"
                                for w in text.lower().split():
                                    w_clean = w.strip(".,!?\"'()[]{}")
                                    if w_clean:
                                        self.valid_vocab.add(w_clean)
                    logger.info("Loaded {} unique valid vocabulary words from training data", len(self.valid_vocab))
                except Exception as ve:
                    logger.warning("Could not build valid vocabulary from training data: {}", ve)

            self._available = True
            logger.info("✓ Prash engine initialised successfully")
            return True

        except Exception as exc:
            logger.error("Prash engine init failed: {}", exc)
            self._available = False
            return False

    # ── Heuristic Response Validation ────────────────────────────────────

    def validate_response(self, response_text: str, query: str) -> bool:
        """
        Validates the generated response from Prash.
        Returns True if the response is clean, grammatically valid, and relevant.
        """
        response_text = response_text.strip()
        if not response_text:
            return False
            
        # 1. Reject very short responses
        if len(response_text) <= 3:
            return False
            
        words = response_text.lower().split()
        cleaned_words = [w.strip(".,!?\"'()[]{}") for w in words]
        cleaned_words = [w for w in cleaned_words if w]  # Filter out empty strings
        
        # 2. Reject single-letter gibberish words (except 'a' and 'i')
        for w in cleaned_words:
            if len(w) == 1 and w not in ("a", "i"):
                logger.info(f"Prash validation failed: contains single-letter gibberish '{w}'")
                return False
                
        # 3. Reject consecutive repeated words (e.g. 'system system')
        for i in range(len(cleaned_words) - 1):
            if cleaned_words[i] == cleaned_words[i+1]:
                logger.info(f"Prash validation failed: contains consecutive repeated word '{cleaned_words[i]}'")
                return False
                
        # 4. Reject highly repetitive responses (low unique word ratio)
        if len(cleaned_words) >= 5:
            unique_ratio = len(set(cleaned_words)) / len(cleaned_words)
            if unique_ratio < 0.7:
                logger.info(f"Prash validation failed: unique word ratio {unique_ratio:.2f} is too low")
                return False
                
        # 5. Check if all generated words and prompt words are in the training vocabulary
        if hasattr(self, "valid_vocab") and self.valid_vocab:
            # Check prompt words (if prompt contains unknown domain words, Prash cannot be confident)
            query_words = [w.strip(".,!?\"'()[]{}") for w in query.lower().split() if len(w.strip(".,!?\"'()[]{}")) > 2]
            for qw in query_words:
                if qw not in self.valid_vocab:
                    logger.info(f"Prash validation failed: prompt word '{qw}' is not in Prash vocabulary — switching to primary LLM")
                    return False

            for w in cleaned_words:
                if w not in self.valid_vocab:
                    logger.info(f"Prash validation failed: generated word '{w}' is not in training vocabulary")
                    return False
                    
        # 6. Query relevance check:
        # If the user query is purely conversational (greetings, how are you, who are you, what is my name)
        # but the response contains system action keywords, it is a hallucination!
        query_lower = query.lower()
        action_keywords = ["open", "type", "press", "volume", "mute", "screenshot", "screen", "search", "remember", "recall", "calculator", "explorer"]
        is_query_action = any(kw in query_lower for kw in action_keywords)
        
        if not is_query_action:
            response_action_keywords = ["opening", "typing", "pressing", "screenshot", "volume", "mute", "browser", "spotify", "notepad", "calculator", "explorer"]
            if any(kw in response_text.lower() for kw in response_action_keywords):
                logger.info("Prash validation failed: action keywords in response to conversational query")
                return False

        # 7. Action alignment check:
        # If the query contains an action target, the response should align with that action target.
        intents = {
            "volume": ["volume", "mute"],
            "notepad": ["notepad", "typing", "pressing"],
            "spotify": ["spotify", "music", "play", "song"],
            "browser": ["browser", "chrome", "google", "youtube", "website", "open"],
            "screenshot": ["screenshot", "screen"],
            "calculator": ["calculator", "calc"],
            "explorer": ["explorer", "folder", "directory", "file"],
            "search": ["search", "query", "searching"],
        }
        
        response_lower = response_text.lower()
        for intent, keywords in intents.items():
            if any(kw in query_lower for kw in keywords):
                if not any(kw in response_lower for kw in keywords):
                    logger.info(f"Prash validation failed: query intent '{intent}' mismatch in response '{response_text}'")
                    return False

        return True

    # ── Token ID builder ──────────────────────────────────────────────────

    def _build_token_ids(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> List[int]:
        """Convert prompt and conversation history into direct token IDs matching training format."""
        if not self.tokenizer:
            return []

        bos_id = getattr(self.tokenizer, "bos_id", 1)
        sep_id = getattr(self.tokenizer, "sep_id", 4)
        eos_id = getattr(self.tokenizer, "eos_id", 2)

        token_ids = []

        if conversation_history:
            for turn in conversation_history:
                role = turn.get("role", "user")
                content = turn.get("content", "").strip()
                if not content:
                    continue

                if role == "user":
                    token_ids.extend([bos_id] + self.tokenizer.encode(content.lower()) + [sep_id])
                elif role == "assistant":
                    token_ids.extend(self.tokenizer.encode(content) + [eos_id])

        # Add the active prompt query
        token_ids.extend([bos_id] + self.tokenizer.encode(prompt.lower()) + [sep_id])

        # Enforce max_seq_len token budget
        max_seq_len = getattr(self.config, "max_seq_len", 128)
        if len(token_ids) > max_seq_len:
            excess = len(token_ids) - max_seq_len
            token_ids = token_ids[excess:]

            # Align to start with a BOS token
            found_bos = False
            for i in range(len(token_ids)):
                if token_ids[i] == bos_id:
                    token_ids = token_ids[i:]
                    found_bos = True
                    break

            if not found_bos or not token_ids:
                token_ids = [bos_id] + token_ids[1:]

        return token_ids

    # ── Single-shot generation ───────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Generate a full response for the given user prompt.

        Builds the prompt matching training BPE sequence structure,
        runs inference, and checks confidence.

        Args:
            prompt:               The user's current message.
            conversation_history: Optional prior turns as a list of
                                  ``{"role": ..., "content": ...}`` dicts.
            max_tokens:           Maximum tokens to generate.
            temperature:          Sampling temperature.

        Returns:
            Tuple of ``(response_text, is_confident, metadata_dict)``.

            *metadata_dict* contains:
                - ``entropy``:         Average entropy of generated tokens
                - ``provider``:        Always ``"prash"``
                - ``tokens_generated``: Number of tokens produced
        """
        if not self._available or self.inference is None:
            return (
                "",
                False,
                {"error": "Prash engine not available", "provider": "prash"},
            )

        try:
            # Build prompt matching training BPE token format
            token_ids = self._build_token_ids(prompt, conversation_history)

            # Run inference using token IDs directly
            response_text, avg_entropy = self.inference.generate(
                prompt=token_ids,
                max_new_tokens=max_tokens,
                temperature=temperature,
            )

            # Validate generated response text
            is_valid = self.validate_response(response_text, prompt)
            confident = self.inference.is_confident(avg_entropy) and is_valid

            # Count generated tokens (approximate via tokenizer)
            try:
                tokens_generated = len(self.tokenizer.encode(response_text))
            except Exception:
                tokens_generated = len(response_text.split())

            metadata = {
                "entropy": round(avg_entropy, 4),
                "provider": "prash",
                "tokens_generated": tokens_generated,
            }

            logger.info(
                "Prash generate — entropy={:.3f}, confident={}, tokens={}",
                avg_entropy,
                confident,
                tokens_generated,
            )

            return (response_text, confident, metadata)

        except Exception as exc:
            logger.error("Prash generate error: {}", exc)
            return ("", False, {"error": str(exc), "provider": "prash"})

    # ── Streaming generation ─────────────────────────────────────────────

    async def generate_stream(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a response token-by-token.

        Yields dicts suitable for the JARVIS WebSocket protocol:

        - Intermediate tokens:
          ``{"type": "text_delta", "content": "<token>"}``

        - Final sentinel (after last token or on ``<EOS>``):
          ``{"type": "prash_done", "entropy": float, "confident": bool}``

        Args:
            prompt:               The user's current message.
            conversation_history: Optional prior turns.
            max_tokens:           Maximum tokens to generate.
            temperature:          Sampling temperature.

        Yields:
            Dicts as described above.
        """
        if not self._available or self.inference is None:
            yield {
                "type": "prash_done",
                "entropy": float("inf"),
                "confident": False,
                "error": "Prash engine not available",
            }
            return

        try:
            # Build prompt matching training BPE token format
            token_ids = self._build_token_ids(prompt, conversation_history)

            # Stream tokens
            tokens_generated = 0
            full_response_text = ""
            async for token_text, entropy in self.inference.generate_stream(
                prompt=token_ids,
                max_new_tokens=max_tokens,
                temperature=temperature,
            ):
                if token_text:
                    # Intermediate token
                    tokens_generated += 1
                    full_response_text += token_text
                    yield {"type": "text_delta", "content": token_text}
                else:
                    # Final sentinel — entropy is the average
                    is_valid = self.validate_response(full_response_text, prompt)
                    confident = self.inference.is_confident(entropy) and is_valid
                    logger.info(
                        "Prash stream done — entropy={:.3f}, confident={}, tokens={}",
                        entropy,
                        confident,
                        tokens_generated,
                    )
                    yield {
                        "type": "prash_done",
                        "entropy": round(entropy, 4),
                        "confident": confident,
                        "tokens_generated": tokens_generated,
                    }

        except Exception as exc:
            logger.error("Prash stream error: {}", exc)
            yield {
                "type": "prash_done",
                "entropy": float("inf"),
                "confident": False,
                "error": str(exc),
            }

    # ── Status / health ──────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Return whether the engine is ready to serve requests."""
        return self._available

    def get_status(self) -> Dict[str, Any]:
        """
        Return a comprehensive status dict for introspection and debugging.

        Includes model architecture details, file existence checks, and
        runtime state.

        Returns:
            Dict with keys: ``available``, ``loaded``, ``device``,
            ``vocab_size``, ``n_params``, ``n_layers``, ``d_model``,
            ``checkpoint_exists``, ``tokenizer_exists``, ``model_dir``.
        """
        checkpoint_exists = (self.model_dir / "checkpoint_latest.pt").exists()
        tokenizer_exists = (self.model_dir / "tokenizer.json").exists()

        # Model architecture info
        n_params = 0
        vocab_size = 0
        n_layers = 0
        d_model = 0

        if self.model is not None:
            n_params = sum(p.numel() for p in self.model.parameters())

        if self.config is not None:
            vocab_size = getattr(self.config, "vocab_size", 0)
            n_layers = getattr(self.config, "n_layers", 0)
            d_model = getattr(self.config, "d_model", 0)

        return {
            "available": self._available,
            "loaded": self._loaded,
            "device": str(self.device),
            "quantization": "4-Bit Quantized PyTorch Engine (PrashTransformer)",
            "offline_stt": "faster-whisper Local Speech Engine",
            "vocab_size": vocab_size,
            "n_params": n_params,
            "n_layers": n_layers,
            "d_model": d_model,
            "checkpoint_exists": checkpoint_exists,
            "tokenizer_exists": tokenizer_exists,
            "model_dir": str(self.model_dir),
        }

    def __repr__(self) -> str:
        return (
            f"PrashEngine(available={self._available}, loaded={self._loaded}, "
            f"device={self.device!r}, model_dir={str(self.model_dir)!r})"
        )
