"""
Prash BPE Tokenizer — Byte-Pair Encoding tokenizer built from scratch.

Implements the full BPE algorithm with no external tokenizer dependencies.
Supports training on raw text, encoding/decoding, and serialization of
vocabulary and merge rules to JSON.

Special tokens:
    0: <PAD>   — padding token for batching
    1: <BOS>   — begin-of-sequence marker
    2: <EOS>   — end-of-sequence marker
    3: <UNK>   — unknown / out-of-vocabulary fallback
    4: <SEP>   — separator between conversation turns
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPECIAL_TOKENS: Dict[str, int] = {
    "<PAD>": 0,
    "<BOS>": 1,
    "<EOS>": 2,
    "<UNK>": 3,
    "<SEP>": 4,
}

NUM_SPECIAL_TOKENS: int = len(SPECIAL_TOKENS)

# Pre-tokenisation regex — splits on whitespace boundaries, punctuation
# groups, and digit runs while keeping the delimiters attached.  Loosely
# inspired by GPT-2 style pre-tokenisation.
_PRETOK_PATTERN: re.Pattern = re.compile(
    r"""'s|'t|'re|'ve|'m|'ll|'d"""          # common contractions
    r"""| ?\w+"""                             # optional leading space + word
    r"""| ?\d+"""                             # optional leading space + digits
    r"""| ?[^\s\w]+"""                        # optional leading space + punct
    r"""|\s+(?!\S)"""                         # trailing whitespace
    r"""|\s+""",                              # other whitespace
    re.IGNORECASE,
)


class PrashTokenizer:
    """A byte-pair encoding tokenizer trained and run entirely in Python.

    Workflow
    --------
    1. **Train** on a raw-text corpus to learn BPE merge rules::

           tok = PrashTokenizer()
           tok.train(corpus_text, vocab_size=8192)

    2. **Encode** text to a list of integer token IDs::

           ids = tok.encode("Hello, JARVIS!")

    3. **Decode** token IDs back to a string::

           text = tok.decode(ids)

    4. **Save / Load** the learned vocabulary and merge table::

           tok.save("tokenizer.json")
           tok2 = PrashTokenizer.load("tokenizer.json")
    """

    # ------------------------------------------------------------------ #
    #  Construction
    # ------------------------------------------------------------------ #

    def __init__(self) -> None:
        # id  →  token-string   (includes special tokens + learned pieces)
        self._id_to_token: Dict[int, str] = {}
        # token-string  →  id
        self._token_to_id: Dict[str, int] = {}

        # Ordered list of merge rules as (token_a, token_b) tuples.
        # The *index* in this list is the priority (lower = earlier merge).
        self._merges: List[Tuple[str, str]] = []

        # Populate special tokens immediately.
        for token, tid in SPECIAL_TOKENS.items():
            self._id_to_token[tid] = token
            self._token_to_id[token] = tid

        self._trained: bool = False

    # ------------------------------------------------------------------ #
    #  Properties
    # ------------------------------------------------------------------ #

    @property
    def vocab_size(self) -> int:
        """Return the current vocabulary size (special + base + merged)."""
        return len(self._id_to_token)

    @property
    def is_trained(self) -> bool:
        """Whether :meth:`train` has been called (or a vocab was loaded)."""
        return self._trained

    # ------------------------------------------------------------------ #
    #  Training
    # ------------------------------------------------------------------ #

    def train(self, corpus: str, vocab_size: int = 8192) -> None:
        """Train BPE merge rules from a raw-text *corpus*.

        Parameters
        ----------
        corpus:
            The full training text.  Longer corpora yield better
            sub-word statistics.
        vocab_size:
            Target vocabulary size **including** special tokens and the
            base character vocabulary.  Must be larger than the base
            vocabulary that results from the unique characters in the
            corpus plus the special tokens.

        Algorithm
        ---------
        1. Pre-tokenise the corpus into coarse word-level chunks.
        2. Split every chunk into individual characters — these form the
           base vocabulary.
        3. Repeatedly find the most-frequent adjacent pair of tokens,
           merge them into a single new token, and record the merge rule.
        4. Stop when *vocab_size* is reached.
        """
        logger.info("Tokenizer training started — target vocab_size={}", vocab_size)

        # --- Step 1: pre-tokenise -----------------------------------------
        words: List[str] = re.findall(_PRETOK_PATTERN, corpus)
        if not words:
            logger.warning("Corpus produced no tokens after pre-tokenisation")
            self._trained = True
            return

        # Each "word" is stored as a tuple of characters, with an
        # associated frequency count.
        word_freqs: Counter[Tuple[str, ...]] = Counter()
        for word in words:
            char_tuple = tuple(word)
            word_freqs[char_tuple] += 1

        # --- Step 2: build base (character-level) vocabulary --------------
        chars: set[str] = set()
        for char_tuple in word_freqs:
            chars.update(char_tuple)

        # Assign IDs starting after special tokens.
        next_id: int = NUM_SPECIAL_TOKENS
        for ch in sorted(chars):
            if ch not in self._token_to_id:
                self._id_to_token[next_id] = ch
                self._token_to_id[ch] = next_id
                next_id += 1

        base_vocab_size: int = next_id
        logger.info(
            "Base vocabulary built — {} characters (+ {} special = {} total)",
            base_vocab_size - NUM_SPECIAL_TOKENS,
            NUM_SPECIAL_TOKENS,
            base_vocab_size,
        )

        if vocab_size <= base_vocab_size:
            logger.warning(
                "Requested vocab_size ({}) <= base vocab ({}); no merges will be learned",
                vocab_size,
                base_vocab_size,
            )
            self._trained = True
            return

        num_merges: int = vocab_size - base_vocab_size

        # --- Step 3 & 4: iteratively merge most-frequent pairs ------------
        for merge_idx in range(num_merges):
            # Count every adjacent pair across all words.
            pair_counts: Counter[Tuple[str, str]] = Counter()
            for char_tuple, freq in word_freqs.items():
                for i in range(len(char_tuple) - 1):
                    pair = (char_tuple[i], char_tuple[i + 1])
                    pair_counts[pair] += freq

            if not pair_counts:
                logger.info("No more pairs to merge — stopping early at merge {}", merge_idx)
                break

            best_pair: Tuple[str, str] = pair_counts.most_common(1)[0][0]
            merged_token: str = best_pair[0] + best_pair[1]

            # Record the merge rule.
            self._merges.append(best_pair)

            # Add merged token to vocab.
            self._id_to_token[next_id] = merged_token
            self._token_to_id[merged_token] = next_id
            next_id += 1

            # Apply the merge to every word in the frequency table.
            new_word_freqs: Counter[Tuple[str, ...]] = Counter()
            for char_tuple, freq in word_freqs.items():
                new_tuple = self._apply_single_merge(char_tuple, best_pair, merged_token)
                new_word_freqs[new_tuple] += freq
            word_freqs = new_word_freqs

            if (merge_idx + 1) % 500 == 0:
                logger.debug(
                    "Merge {}/{}: '{}' + '{}' → '{}' (freq {})",
                    merge_idx + 1,
                    num_merges,
                    best_pair[0],
                    best_pair[1],
                    merged_token,
                    pair_counts[best_pair],
                )

        self._trained = True
        logger.info(
            "Tokenizer training complete — {} merges learned, final vocab_size={}",
            len(self._merges),
            self.vocab_size,
        )

    # ------------------------------------------------------------------ #
    #  Encoding
    # ------------------------------------------------------------------ #

    def encode(self, text: str) -> List[int]:
        """Encode *text* into a list of integer token IDs.

        Parameters
        ----------
        text:
            Arbitrary string to tokenise.

        Returns
        -------
        List[int]
            Sequence of token IDs.  Unknown single characters fall back
            to ``<UNK>`` (ID 3).
        """
        if not self._trained:
            raise RuntimeError("Tokenizer has not been trained yet — call train() or load() first")

        ids: List[int] = []

        # Pre-tokenise identically to training.
        chunks: List[str] = re.findall(_PRETOK_PATTERN, text)

        for chunk in chunks:
            # Start with individual characters.
            tokens: List[str] = list(chunk)

            # Apply every merge rule in learned order.
            for pair_a, pair_b in self._merges:
                tokens = self._apply_merge_to_list(tokens, pair_a, pair_b)

            # Map tokens → IDs.
            for tok in tokens:
                tid = self._token_to_id.get(tok)
                if tid is not None:
                    ids.append(tid)
                else:
                    ids.append(SPECIAL_TOKENS["<UNK>"])

        return ids

    # ------------------------------------------------------------------ #
    #  Decoding
    # ------------------------------------------------------------------ #

    def decode(self, token_ids: List[int]) -> str:
        """Decode a sequence of token IDs back into a string.

        Parameters
        ----------
        token_ids:
            List of integer IDs previously produced by :meth:`encode`.

        Returns
        -------
        str
            The reconstructed text.  Special tokens (``<PAD>``,
            ``<BOS>``, ``<EOS>``, ``<SEP>``) are silently stripped.
            ``<UNK>`` is replaced with the Unicode replacement character
            ``\ufffd``.
        """
        pieces: List[str] = []
        for tid in token_ids:
            token = self._id_to_token.get(tid)
            if token is None:
                pieces.append("\ufffd")
            elif token == "<UNK>":
                pieces.append("\ufffd")
            elif token in ("<PAD>", "<BOS>", "<EOS>", "<SEP>"):
                continue  # strip control tokens
            else:
                pieces.append(token)
        return "".join(pieces)

    # ------------------------------------------------------------------ #
    #  Serialization
    # ------------------------------------------------------------------ #

    def save(self, path: str) -> None:
        """Persist the vocabulary and merge rules to a JSON file.

        Parameters
        ----------
        path:
            Destination file path (will be created / overwritten).

        File format (JSON)::

            {
                "version": "prash-bpe-v1",
                "vocab": {"<PAD>": 0, ...},
                "merges": [["a", "b"], ...]
            }
        """
        data = {
            "version": "prash-bpe-v1",
            "vocab": self._token_to_id,
            "merges": [list(pair) for pair in self._merges],
        }
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Tokenizer saved to {} (vocab_size={})", path, self.vocab_size)

    @classmethod
    def load(cls, path: str) -> "PrashTokenizer":
        """Load a previously saved tokenizer from a JSON file.

        Parameters
        ----------
        path:
            Path to the JSON file written by :meth:`save`.

        Returns
        -------
        PrashTokenizer
            A fully-initialised tokenizer ready for :meth:`encode` /
            :meth:`decode`.
        """
        filepath = Path(path)
        data = json.loads(filepath.read_text(encoding="utf-8"))

        tok = cls()
        tok._token_to_id = data["vocab"]
        tok._id_to_token = {int(v): k for k, v in data["vocab"].items()}
        tok._merges = [tuple(pair) for pair in data["merges"]]  # type: ignore[misc]
        tok._trained = True

        logger.info("Tokenizer loaded from {} (vocab_size={})", path, tok.vocab_size)
        return tok

    # ------------------------------------------------------------------ #
    #  Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_single_merge(
        char_tuple: Tuple[str, ...],
        pair: Tuple[str, str],
        merged: str,
    ) -> Tuple[str, ...]:
        """Merge all occurrences of *pair* inside *char_tuple*.

        Parameters
        ----------
        char_tuple:
            The current token sequence for a word.
        pair:
            The (left, right) pair being merged.
        merged:
            The new token string (left + right).

        Returns
        -------
        Tuple[str, ...]
            Updated token sequence with every adjacent occurrence of
            *pair* replaced by *merged*.
        """
        result: List[str] = []
        i = 0
        while i < len(char_tuple):
            if (
                i < len(char_tuple) - 1
                and char_tuple[i] == pair[0]
                and char_tuple[i + 1] == pair[1]
            ):
                result.append(merged)
                i += 2
            else:
                result.append(char_tuple[i])
                i += 1
        return tuple(result)

    @staticmethod
    def _apply_merge_to_list(
        tokens: List[str],
        pair_a: str,
        pair_b: str,
    ) -> List[str]:
        """Apply a single merge rule to a list of token strings.

        Parameters
        ----------
        tokens:
            Current list of token strings for one pre-tokenised chunk.
        pair_a:
            Left element of the pair.
        pair_b:
            Right element of the pair.

        Returns
        -------
        List[str]
            New token list with all adjacent (pair_a, pair_b)
            occurrences merged.
        """
        merged_token = pair_a + pair_b
        result: List[str] = []
        i = 0
        while i < len(tokens):
            if (
                i < len(tokens) - 1
                and tokens[i] == pair_a
                and tokens[i + 1] == pair_b
            ):
                result.append(merged_token)
                i += 2
            else:
                result.append(tokens[i])
                i += 1
        return result
