"""
Prash AI Engine — KV-Cache & Multi-Turn Conversational Memory.

Implements Key-Value caching for the Prash Transformer:
- O(1) per-token attention computation during autoregressive decoding
- Multi-turn conversation context retention across dialogue turns
- Bounded token memory eviction and pruning
"""

from typing import Dict, Any, List, Optional, Tuple
import torch
from loguru import logger


class PrashKVCache:
    """
    Key-Value attention cache for multi-layer Prash decoder.
    Stores past key and value tensors per layer: (batch_size, n_heads, cached_len, head_dim).
    """

    def __init__(self, n_layers: int, max_seq_len: int = 512, device: str = "cpu") -> None:
        self.n_layers = n_layers
        self.max_seq_len = max_seq_len
        self.device = torch.device(device)
        self.k_cache: List[Optional[torch.Tensor]] = [None] * n_layers
        self.v_cache: List[Optional[torch.Tensor]] = [None] * n_layers
        self.cached_tokens: List[int] = []

    def reset(self) -> None:
        """Clear all cached keys, values, and token IDs."""
        self.k_cache = [None] * self.n_layers
        self.v_cache = [None] * self.n_layers
        self.cached_tokens.clear()

    @property
    def current_seq_len(self) -> int:
        if self.k_cache[0] is None:
            return 0
        return self.k_cache[0].shape[2]

    def update(
        self,
        layer_idx: int,
        key: torch.Tensor,
        value: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Appends new key and value states to the cache for the specified layer.

        Args:
            layer_idx: Layer index (0 .. n_layers-1)
            key: New key tensor (batch, n_heads, seq_len, head_dim)
            value: New value tensor (batch, n_heads, seq_len, head_dim)

        Returns:
            Tuple of full (all_keys, all_values) up to the current position.
        """
        if self.k_cache[layer_idx] is None:
            self.k_cache[layer_idx] = key
            self.v_cache[layer_idx] = value
        else:
            self.k_cache[layer_idx] = torch.cat([self.k_cache[layer_idx], key], dim=2)
            self.v_cache[layer_idx] = torch.cat([self.v_cache[layer_idx], value], dim=2)

        # Evict oldest tokens if cache exceeds max_seq_len
        if self.k_cache[layer_idx].shape[2] > self.max_seq_len:
            self.k_cache[layer_idx] = self.k_cache[layer_idx][:, :, -self.max_seq_len:, :]
            self.v_cache[layer_idx] = self.v_cache[layer_idx][:, :, -self.max_seq_len:, :]

        return self.k_cache[layer_idx], self.v_cache[layer_idx]


class PrashMultiTurnMemory:
    """
    Manages multi-turn conversation dialogue history and active KV caches for Prash sessions.
    Retains conversational turns in memory so follow-up requests maintain context.
    """

    def __init__(self, n_layers: int = 6, max_seq_len: int = 256, device: str = "cpu") -> None:
        self.n_layers = n_layers
        self.max_seq_len = max_seq_len
        self.device = device
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def get_or_create_session(self, session_id: str = "default") -> Dict[str, Any]:
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "session_id": session_id,
                "turns": [],
                "kv_cache": PrashKVCache(n_layers=self.n_layers, max_seq_len=self.max_seq_len, device=self.device),
                "total_tokens": 0,
            }
        return self._sessions[session_id]

    def add_turn(self, session_id: str, role: str, content: str, token_ids: Optional[List[int]] = None) -> None:
        session = self.get_or_create_session(session_id)
        turn = {
            "role": role,
            "content": content,
            "token_ids": token_ids or [],
        }
        session["turns"].append(turn)
        if token_ids:
            session["total_tokens"] += len(token_ids)
            session["kv_cache"].cached_tokens.extend(token_ids)

        # Bounded prune check: keep last 10 turns
        if len(session["turns"]) > 10:
            evicted = session["turns"].pop(0)
            logger.debug("PrashMultiTurnMemory: Evicted oldest turn for session '{}'", session_id)

    def get_history(self, session_id: str = "default") -> List[Dict[str, str]]:
        session = self.get_or_create_session(session_id)
        return [{"role": t["role"], "content": t["content"]} for t in session["turns"]]

    def clear_session(self, session_id: str = "default") -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["kv_cache"].reset()
            self._sessions[session_id]["turns"].clear()
            self._sessions[session_id]["total_tokens"] = 0
            logger.info("PrashMultiTurnMemory: Cleared session '{}'", session_id)
