"""
Prash AI Engine — Conversation Memory Manager.

Manages a sliding-window conversation context for the Prash transformer.
Handles:
- Turn-by-turn storage of user/assistant messages
- Formatting into a structured prompt string for the model
- Token-budget trimming to stay within the model's max_seq_len
- Automatic eviction of oldest turns when the window overflows

Designed to be lightweight and stateless beyond the current conversation
window — long-term memory is handled by JARVIS's ChromaDB-backed memory
service separately.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger


class PrashMemory:
    """
    Sliding-window conversation context manager for Prash.

    Stores the most recent *max_turns* of conversation and formats them
    into a prompt string that the transformer can process.  Can also
    trim context to fit a hard token budget using the tokenizer.

    Args:
        max_turns:  Maximum number of turns (user + assistant messages) to
                    retain.  Oldest turns are evicted first.
        max_tokens: Soft token budget hint (used by :meth:`trim_to_token_budget`).
    """

    def __init__(self, max_turns: int = 10, max_tokens: int = 384) -> None:
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.turns: List[Dict[str, str]] = []

        logger.debug(
            "PrashMemory initialised — max_turns={}, max_tokens={}",
            max_turns,
            max_tokens,
        )

    # ── Turn management ──────────────────────────────────────────────────

    def add_turn(self, role: str, content: str) -> None:
        """
        Append a conversation turn.

        If the window already contains *max_turns* messages, the oldest
        turn is evicted before the new one is added.

        Args:
            role:    Speaker role — ``'user'`` or ``'assistant'``.
            content: The message text.
        """
        if role not in ("user", "assistant", "system"):
            logger.warning("Unexpected role '{}' — accepting anyway", role)

        content = content.strip()
        if not content:
            logger.debug("Ignoring empty turn for role='{}'", role)
            return

        # Evict oldest turn if at capacity
        if len(self.turns) >= self.max_turns:
            evicted = self.turns.pop(0)
            logger.debug(
                "Evicted oldest turn (role={}, len={})",
                evicted["role"],
                len(evicted["content"]),
            )

        self.turns.append({"role": role, "content": content})
        logger.debug(
            "Added turn — role={}, len={}, total_turns={}",
            role,
            len(content),
            len(self.turns),
        )

    def get_context(self) -> List[Dict[str, str]]:
        """
        Return the current conversation history.

        Returns:
            A shallow copy of the turns list.  Each element is a dict
            with ``role`` and ``content`` keys.
        """
        return list(self.turns)

    def clear(self) -> None:
        """Remove all stored turns."""
        count = len(self.turns)
        self.turns.clear()
        logger.debug("Memory cleared ({} turns removed)", count)

    # ── Prompt formatting ────────────────────────────────────────────────

    def to_prompt(self, system_prompt: str = "") -> str:
        """
        Format the conversation context into a prompt string ready for
        the Prash transformer to generate the next assistant response.

        Output format::

            [SYSTEM] {system_prompt}
            [USER] {turn_1_content}
            [ASSISTANT] {turn_2_content}
            [USER] {turn_3_content}
            [ASSISTANT]

        The prompt always ends with ``[ASSISTANT]`` (no trailing content)
        so the model can begin generating immediately.

        If there are no turns and no system prompt, returns a bare
        ``[ASSISTANT]`` tag.

        Args:
            system_prompt: Optional system-level instructions to prepend.

        Returns:
            Formatted prompt string.
        """
        parts: List[str] = []

        # System prompt (always include if provided)
        if system_prompt.strip():
            parts.append(f"[SYSTEM] {system_prompt.strip()}")

        # Conversation turns
        for turn in self.turns:
            tag = turn["role"].upper()
            parts.append(f"[{tag}] {turn['content']}")

        # If the last turn is from the user (or there are no turns),
        # append an empty ASSISTANT tag for the model to continue from
        if not self.turns or self.turns[-1]["role"] == "user":
            parts.append("[ASSISTANT]")

        prompt = "\n".join(parts)
        return prompt

    # ── Token-budget trimming ────────────────────────────────────────────

    def trim_to_token_budget(
        self,
        tokenizer: Any,
        max_tokens: Optional[int] = None,
    ) -> None:
        """
        Remove the oldest turns until the formatted prompt fits within
        *max_tokens* when encoded by *tokenizer*.

        This is a destructive operation — evicted turns are lost.

        Args:
            tokenizer:  Object with an ``encode(text) -> List[int]`` method.
            max_tokens: Hard token ceiling.  Defaults to ``self.max_tokens``.
        """
        if max_tokens is None:
            max_tokens = self.max_tokens

        iterations = 0
        max_iterations = len(self.turns) + 1  # safety cap

        while len(self.turns) > 1 and iterations < max_iterations:
            prompt = self.to_prompt()
            token_count = len(tokenizer.encode(prompt))

            if token_count <= max_tokens:
                break

            # Evict the oldest turn
            evicted = self.turns.pop(0)
            iterations += 1
            logger.debug(
                "Trimmed turn (role={}, tokens_now≈{}, budget={})",
                evicted["role"],
                token_count,
                max_tokens,
            )

        if iterations > 0:
            logger.info(
                "Trimmed {} turns to fit token budget (≤{})",
                iterations,
                max_tokens,
            )

    # ── Dunder helpers ───────────────────────────────────────────────────

    def __len__(self) -> int:
        """Number of turns currently stored."""
        return len(self.turns)

    def __repr__(self) -> str:
        return (
            f"PrashMemory(turns={len(self.turns)}, "
            f"max_turns={self.max_turns}, max_tokens={self.max_tokens})"
        )
