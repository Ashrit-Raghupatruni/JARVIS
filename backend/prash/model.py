"""
Prash Transformer — A decoder-only GPT-style transformer built from scratch.

Every component is implemented as a standalone ``nn.Module`` using only
PyTorch primitives.  The architecture mirrors modern efficient LLMs
(LLaMA / Mistral family):

* **RMSNorm** instead of LayerNorm
* **Rotary Positional Embeddings (RoPE)** instead of absolute / learned pos-emb
* **SwiGLU feed-forward** instead of vanilla MLP
* **Pre-norm** residual layout
* **Weight-tied** embedding ↔ output head

Designed for the JARVIS desktop assistant — small enough to train and run
on a single consumer GPU while still capturing the key ideas behind
state-of-the-art language models.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from loguru import logger


# ======================================================================== #
#  Configuration
# ======================================================================== #


@dataclass
class PrashConfig:
    """Hyperparameters for the Prash transformer.

    Defaults are deliberately small so the model can train on a laptop
    CPU / single GPU in minutes.  Scale up for production.

    Attributes
    ----------
    vocab_size : int
        Size of the token vocabulary (must match the tokenizer).
    d_model : int
        Dimensionality of token embeddings and hidden states.
    n_heads : int
        Number of attention heads.  ``d_model`` must be divisible by
        ``n_heads``.
    n_layers : int
        Number of stacked transformer decoder blocks.
    d_ff : int
        Hidden dimension of the SwiGLU feed-forward network.  For
        SwiGLU the effective expansion is ``(2/3) * d_ff`` per the
        LLaMA convention, so set this ~2.7× ``d_model`` for a
        comparable parameter budget to a vanilla 4× MLP.
    max_seq_len : int
        Maximum sequence length supported by the model.  RoPE
        frequencies are precomputed up to this length.
    dropout : float
        Dropout probability applied after attention and FFN.
    rope_theta : float
        Base frequency for RoPE (default 10 000 matches the original
        RoFormer paper).
    """

    vocab_size: int = 8192
    d_model: int = 256
    n_heads: int = 4
    n_layers: int = 4
    d_ff: int = 512
    max_seq_len: int = 512
    dropout: float = 0.1
    rope_theta: float = 10000.0
    norm_eps: float = 1e-5

    # -- Serialization --------------------------------------------------- #

    def save(self, path: str) -> None:
        """Persist configuration to a JSON file.

        Parameters
        ----------
        path:
            Destination file path.
        """
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        logger.info("PrashConfig saved to {}", path)

    @classmethod
    def load(cls, path: str) -> "PrashConfig":
        """Load configuration from a JSON file.

        Parameters
        ----------
        path:
            Path to the JSON file written by :meth:`save`.
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        config = cls(**data)
        logger.info("PrashConfig loaded from {}", path)
        return config

    # -- Helpers --------------------------------------------------------- #

    @property
    def num_parameters(self) -> int:
        """Estimate the total trainable parameter count.

        This is a *rough* analytical estimate (ignoring bias terms and
        RMSNorm weights which are negligible).  For the exact count,
        call ``sum(p.numel() for p in model.parameters())``.
        """
        d, h, L, V = self.d_model, self.n_heads, self.n_layers, self.vocab_size  # noqa: N806
        d_ff = self.d_ff

        # Token embedding (weight-tied with output, so counted once).
        emb = V * d

        # Per-layer: attention (Q, K, V, O projections) + SwiGLU (gate, up, down).
        attn_per_layer = 4 * d * d                    # Wq, Wk, Wv, Wo
        ffn_per_layer = 3 * d * d_ff                   # gate, up, down
        layer_total = L * (attn_per_layer + ffn_per_layer)

        return emb + layer_total


# ======================================================================== #
#  RMSNorm
# ======================================================================== #


class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalisation.

    Simpler and faster than standard LayerNorm — no mean-centering, no
    bias.  Used in LLaMA, Mistral, and most modern LLMs.

    .. math::

        \\text{RMSNorm}(x) = \\frac{x}{\\text{RMS}(x) + \\epsilon} \\odot \\gamma

    Parameters
    ----------
    dim : int
        Feature dimension (last axis of the input tensor).
    eps : float
        Small constant for numerical stability.
    """

    def __init__(self, dim: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply RMSNorm to *x*.

        Parameters
        ----------
        x : Tensor
            Shape ``(batch, seq_len, dim)``.

        Returns
        -------
        Tensor
            Normalised tensor of the same shape.
        """
        rms = torch.sqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)
        return x / rms * self.weight


# ======================================================================== #
#  Rotary Positional Embedding (RoPE)
# ======================================================================== #


class RotaryPositionalEmbedding(nn.Module):
    """Rotary Position Encoding (RoPE).

    Encodes absolute position information directly into query and key
    vectors via rotation matrices in 2-D sub-spaces.  Unlike learned
    positional embeddings, RoPE provides extrapolation-friendly relative
    position awareness with zero extra parameters.

    Parameters
    ----------
    dim : int
        Per-head dimension (``d_model // n_heads``).  Must be even.
    max_seq_len : int
        Maximum sequence length for which to precompute frequencies.
    theta : float
        Base frequency (10 000 by default).
    """

    def __init__(self, dim: int, max_seq_len: int = 512, theta: float = 10000.0) -> None:
        super().__init__()
        assert dim % 2 == 0, "RoPE requires an even per-head dimension"
        self.dim = dim
        self.max_seq_len = max_seq_len
        self.theta = theta

        # Precompute the complex-valued frequency tensor once.
        freqs = self._precompute_freqs(dim, max_seq_len, theta)
        # Register as a buffer so it moves with the model (.to(device))
        # but is *not* a learnable parameter.
        self.register_buffer("freqs_complex", freqs, persistent=False)

    # ------------------------------------------------------------------ #

    @staticmethod
    def _precompute_freqs(dim: int, max_seq_len: int, theta: float) -> torch.Tensor:
        """Build the complex-valued frequency tensor.

        Returns
        -------
        Tensor
            Shape ``(max_seq_len, dim // 2)`` with dtype ``torch.complex64``.
        """
        # Frequencies for each pair of dimensions.
        freq_exponents = torch.arange(0, dim, 2, dtype=torch.float32) / dim
        inv_freq = 1.0 / (theta ** freq_exponents)  # (dim // 2,)

        # Position indices.
        positions = torch.arange(max_seq_len, dtype=torch.float32)  # (max_seq_len,)

        # Outer product → angles matrix.
        angles = torch.outer(positions, inv_freq)  # (max_seq_len, dim // 2)

        # Convert to unit complex numbers for efficient rotation.
        return torch.polar(torch.ones_like(angles), angles)  # e^{i * angle}

    # ------------------------------------------------------------------ #

    def forward(self, x: torch.Tensor, seq_len: int) -> torch.Tensor:
        """Apply rotary embedding to *x*.

        Parameters
        ----------
        x : Tensor
            Shape ``(batch, n_heads, seq_len, head_dim)``.
        seq_len : int
            Actual sequence length (may be < ``max_seq_len``).

        Returns
        -------
        Tensor
            Rotated tensor of the same shape.
        """
        # Reshape x into pairs: (..., head_dim) → (..., head_dim // 2, 2)
        x_paired = x.float().reshape(*x.shape[:-1], -1, 2)

        # View as complex numbers.
        x_complex = torch.view_as_complex(x_paired)  # (..., head_dim // 2)

        # Slice precomputed frequencies to the current seq_len and
        # broadcast across batch & heads.
        freqs = self.freqs_complex[:seq_len]  # (seq_len, head_dim // 2)
        freqs = freqs.unsqueeze(0).unsqueeze(0)  # (1, 1, seq_len, head_dim // 2)

        # Element-wise complex multiplication = rotation.
        x_rotated = x_complex * freqs

        # Back to real pairs and flatten.
        x_out = torch.view_as_real(x_rotated)  # (..., head_dim // 2, 2)
        x_out = x_out.reshape(*x.shape)

        return x_out.type_as(x)


# ======================================================================== #
#  Multi-Head Self-Attention (causal, with RoPE)
# ======================================================================== #


class MultiHeadSelfAttention(nn.Module):
    """Causal multi-head self-attention with Rotary Position Encoding.

    Parameters
    ----------
    config : PrashConfig
        Model hyper-parameters.
    """

    def __init__(self, config: PrashConfig) -> None:
        super().__init__()
        assert config.d_model % config.n_heads == 0, (
            f"d_model ({config.d_model}) must be divisible by n_heads ({config.n_heads})"
        )

        self.n_heads = config.n_heads
        self.head_dim = config.d_model // config.n_heads
        self.d_model = config.d_model

        # Linear projections (no bias — following LLaMA convention).
        self.q_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.k_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.v_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.o_proj = nn.Linear(config.d_model, config.d_model, bias=False)

        # RoPE — applied to Q and K only.
        self.rope = RotaryPositionalEmbedding(
            dim=self.head_dim,
            max_seq_len=config.max_seq_len,
            theta=config.rope_theta,
        )

        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)

    # ------------------------------------------------------------------ #

    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Compute causal self-attention.

        Parameters
        ----------
        x : Tensor
            Shape ``(batch, seq_len, d_model)``.
        mask : Tensor, optional
            Additive causal mask of shape ``(1, 1, seq_len, seq_len)``
            filled with 0 (attend) and ``-inf`` (mask).

        Returns
        -------
        Tensor
            Shape ``(batch, seq_len, d_model)``.
        """
        B, S, _ = x.shape  # noqa: N806

        # Project → (B, S, d_model) then reshape → (B, n_heads, S, head_dim)
        q = self.q_proj(x).view(B, S, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, S, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, S, self.n_heads, self.head_dim).transpose(1, 2)

        # Apply RoPE to queries and keys.
        q = self.rope(q, seq_len=S)
        k = self.rope(k, seq_len=S)

        # Scaled dot-product attention.
        scale = math.sqrt(self.head_dim)
        attn_weights = torch.matmul(q, k.transpose(-2, -1)) / scale  # (B, H, S, S)

        if mask is not None:
            attn_weights = attn_weights + mask

        attn_weights = F.softmax(attn_weights, dim=-1)
        attn_weights = self.attn_dropout(attn_weights)

        # Weighted sum of values.
        attn_output = torch.matmul(attn_weights, v)  # (B, H, S, D_head)

        # Merge heads → (B, S, d_model)
        attn_output = attn_output.transpose(1, 2).contiguous().view(B, S, self.d_model)

        return self.resid_dropout(self.o_proj(attn_output))


# ======================================================================== #
#  SwiGLU Feed-Forward Network
# ======================================================================== #


class SwiGLUFFN(nn.Module):
    """SwiGLU gated feed-forward network.

    Introduced by Shazeer (2020) and adopted by LLaMA / Mistral.

    .. math::

        \\text{SwiGLU}(x) = W_{\\text{down}}
            \\bigl(\\text{SiLU}(W_{\\text{gate}} x) \\odot W_{\\text{up}} x\\bigr)

    Parameters
    ----------
    config : PrashConfig
        Model hyper-parameters.  ``d_ff`` controls the hidden width.
    """

    def __init__(self, config: PrashConfig) -> None:
        super().__init__()
        self.gate_proj = nn.Linear(config.d_model, config.d_ff, bias=False)
        self.up_proj = nn.Linear(config.d_model, config.d_ff, bias=False)
        self.down_proj = nn.Linear(config.d_ff, config.d_model, bias=False)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Apply SwiGLU FFN.

        Parameters
        ----------
        x : Tensor
            Shape ``(batch, seq_len, d_model)``.

        Returns
        -------
        Tensor
            Same shape as input.
        """
        gate = F.silu(self.gate_proj(x))
        up = self.up_proj(x)
        return self.dropout(self.down_proj(gate * up))


# ======================================================================== #
#  Transformer Decoder Block
# ======================================================================== #


class TransformerBlock(nn.Module):
    """A single pre-norm transformer decoder block.

    Layout::

        x  ──► RMSNorm ──► Self-Attention ──► + ──► RMSNorm ──► SwiGLU FFN ──► + ──► out
           └──────────────────────────────────┘  └──────────────────────────────┘
                     residual connection                 residual connection

    Parameters
    ----------
    config : PrashConfig
        Model hyper-parameters.
    """

    def __init__(self, config: PrashConfig) -> None:
        super().__init__()
        self.norm1 = RMSNorm(config.d_model)
        self.attn = MultiHeadSelfAttention(config)
        self.norm2 = RMSNorm(config.d_model)
        self.ffn = SwiGLUFFN(config)

    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Forward pass through one decoder block.

        Parameters
        ----------
        x : Tensor
            Shape ``(batch, seq_len, d_model)``.
        mask : Tensor, optional
            Causal attention mask.

        Returns
        -------
        Tensor
            Same shape as input.
        """
        # Pre-norm attention with residual.
        x = x + self.attn(self.norm1(x), mask=mask)

        # Pre-norm FFN with residual.
        x = x + self.ffn(self.norm2(x))

        return x


# ======================================================================== #
#  Full Model — PrashTransformer
# ======================================================================== #


class PrashTransformer(nn.Module):
    """Decoder-only transformer language model.

    This is the complete Prash model.  It stacks token embeddings, a
    sequence of :class:`TransformerBlock` layers, a final
    :class:`RMSNorm`, and an output linear head whose weights are tied
    to the embedding matrix.

    Parameters
    ----------
    config : PrashConfig
        Model hyper-parameters.

    Example
    -------
    >>> cfg = PrashConfig(vocab_size=8192, d_model=256, n_layers=4)
    >>> model = PrashTransformer(cfg)
    >>> input_ids = torch.randint(0, 8192, (2, 128))
    >>> logits, loss = model(input_ids)            # inference
    >>> logits, loss = model(input_ids, input_ids)  # training (with loss)
    """

    def __init__(self, config: PrashConfig) -> None:
        super().__init__()
        self.config = config

        # Token embedding.
        self.tok_emb = nn.Embedding(config.vocab_size, config.d_model)

        # Embedding dropout.
        self.emb_dropout = nn.Dropout(config.dropout)

        # Transformer decoder stack.
        self.layers = nn.ModuleList(
            [TransformerBlock(config) for _ in range(config.n_layers)]
        )

        # Final normalisation before the output head.
        self.final_norm = RMSNorm(config.d_model)

        # Output projection (weight-tied with embedding).
        self.output_head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        self.output_head.weight = self.tok_emb.weight  # weight tying

        # Precompute the causal mask (upper-triangular → −inf).
        causal_mask = torch.full(
            (config.max_seq_len, config.max_seq_len), float("-inf")
        )
        causal_mask = torch.triu(causal_mask, diagonal=1)
        self.register_buffer("causal_mask", causal_mask, persistent=False)

        # Initialise weights.
        self.apply(self._init_weights)

        # Log parameter count.
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        logger.info(
            "PrashTransformer initialised — {:,} total parameters ({:,} trainable)",
            total_params,
            trainable_params,
        )

    # ------------------------------------------------------------------ #
    #  Weight initialisation
    # ------------------------------------------------------------------ #

    @staticmethod
    def _init_weights(module: nn.Module) -> None:
        """Apply sensible initialisations.

        * Linear layers → truncated normal (σ = 0.02)
        * Embeddings   → normal (σ = 0.02)
        * RMSNorm      → ones (already the default)
        """
        if isinstance(module, nn.Linear):
            nn.init.trunc_normal_(module.weight, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.trunc_normal_(module.weight, std=0.02)

    # ------------------------------------------------------------------ #
    #  Forward
    # ------------------------------------------------------------------ #

    def forward(
        self,
        input_ids: torch.Tensor,
        targets: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """Run a forward pass through the full model.

        Parameters
        ----------
        input_ids : Tensor
            Integer token IDs of shape ``(batch, seq_len)``.
        targets : Tensor, optional
            Ground-truth token IDs for computing the language-modelling
            loss.  Same shape as *input_ids*.  When provided, the loss
            is computed using cross-entropy between the predicted logits
            (shifted by one position) and the target IDs.

        Returns
        -------
        logits : Tensor
            Raw (un-normalised) scores of shape
            ``(batch, seq_len, vocab_size)``.
        loss : Tensor or None
            Scalar cross-entropy loss if *targets* is provided, else
            ``None``.
        """
        B, S = input_ids.shape  # noqa: N806

        if S > self.config.max_seq_len:
            raise ValueError(
                f"Sequence length {S} exceeds model max_seq_len "
                f"({self.config.max_seq_len})"
            )

        # --- Embed tokens ------------------------------------------------
        x = self.tok_emb(input_ids)          # (B, S, d_model)
        x = self.emb_dropout(x)

        # --- Causal mask (slice to current seq length) -------------------
        mask = self.causal_mask[:S, :S].unsqueeze(0).unsqueeze(0)  # (1, 1, S, S)

        # --- Transformer layers ------------------------------------------
        for layer in self.layers:
            x = layer(x, mask=mask)

        # --- Final norm + output head ------------------------------------
        x = self.final_norm(x)
        logits = self.output_head(x)         # (B, S, vocab_size)

        # --- Optional loss ------------------------------------------------
        loss: Optional[torch.Tensor] = None
        if targets is not None:
            # Shift: predict next token from each position.
            shift_logits = logits[:, :-1, :].contiguous()
            shift_targets = targets[:, 1:].contiguous()
            loss = F.cross_entropy(
                shift_logits.view(-1, self.config.vocab_size),
                shift_targets.view(-1),
                ignore_index=0,  # ignore <PAD> in loss
            )

        return logits, loss
