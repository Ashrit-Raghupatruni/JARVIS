"""
Prash AI Engine — Training Pipeline.

Handles all training operations for the Prash transformer model:
- JSONL data loading and tokenization
- PyTorch DataLoader creation with padding and batching
- AdamW optimizer with cosine annealing LR schedule
- Gradient clipping, checkpointing, and training history logging
- Extraction of training pairs from JARVIS SQLite conversation database

All training is done from scratch using only PyTorch — no external AI
libraries, no HuggingFace, no pre-trained weights.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset

from loguru import logger


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Instruction–Response Dataset
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class InstructionResponseDataset(Dataset):
    """
    PyTorch Dataset that wraps pre-tokenized instruction–response sequences.

    Each sample is a padded tensor of token IDs in the form:
        <BOS> instruction_tokens <SEP> response_tokens <EOS> <PAD>...

    Args:
        sequences: List of 1-D LongTensors, already padded to max_seq_len.
    """

    def __init__(self, sequences: List[torch.Tensor]) -> None:
        super().__init__()
        self.sequences = sequences

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns (input_ids, target_ids) where target_ids are input_ids
        shifted left by one position (standard causal-LM training).
        """
        seq = self.sequences[idx]
        input_ids = seq[:-1]  # everything except last token
        target_ids = seq[1:]  # everything except first token
        return input_ids, target_ids


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Trainer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PrashTrainer:
    """
    End-to-end training pipeline for the Prash transformer.

    Supports:
        • Loading JSONL instruction/response pairs
        • Tokenizing with the custom PrashTokenizer
        • AdamW + cosine-annealing schedule
        • Gradient clipping, periodic checkpointing
        • Training on JARVIS conversation history (SQLite)

    Args:
        model:     Instantiated PrashTransformer.
        tokenizer: Instantiated PrashTokenizer with encode/decode + special tokens.
        config:    PrashConfig dataclass with vocab_size, max_seq_len, etc.
        device:    Torch device string ('cpu' or 'cuda').
        data_dir:  Optional directory for saving checkpoints and logs.
    """

    def __init__(
        self,
        model: nn.Module,
        tokenizer: Any,
        config: Any,
        device: str = "cpu",
        data_dir: Optional[str] = None,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.device = torch.device(device)
        self.model.to(self.device)

        # Resolve data directory for checkpoints / logs
        if data_dir is not None:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "prash"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Will be initialised in train()
        self.optimizer: Optional[AdamW] = None
        self.scheduler: Optional[CosineAnnealingLR] = None

        # Running training history
        self.history: List[Dict[str, Any]] = []

        logger.info(
            "PrashTrainer initialised — device={}, data_dir={}, vocab_size={}, max_seq_len={}",
            self.device,
            self.data_dir,
            getattr(config, "vocab_size", "?"),
            getattr(config, "max_seq_len", "?"),
        )

    # ── Data helpers ─────────────────────────────────────────────────────

    def _load_jsonl(self, path: str) -> List[Dict[str, str]]:
        """
        Load instruction/response pairs from a JSONL file.

        Each line must be a JSON object with at least ``instruction`` and
        ``response`` keys.  Blank lines and malformed rows are skipped
        with a warning.

        Args:
            path: Filesystem path to the .jsonl file.

        Returns:
            List of dicts ``[{"instruction": ..., "response": ...}, ...]``.

        Raises:
            FileNotFoundError: If *path* does not exist.
        """
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Training data not found: {filepath}")

        pairs: List[Dict[str, str]] = []
        skipped = 0

        with open(filepath, "r", encoding="utf-8") as fh:
            for line_no, raw_line in enumerate(fh, start=1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    record = json.loads(raw_line)
                    instruction = record.get("instruction", "").strip()
                    response = record.get("response", "").strip()
                    if not instruction or not response:
                        skipped += 1
                        continue
                    pairs.append({"instruction": instruction, "response": response})
                except json.JSONDecodeError:
                    logger.warning("Malformed JSON on line {} of {}", line_no, filepath.name)
                    skipped += 1

        if skipped:
            logger.warning("Skipped {} malformed/empty rows from {}", skipped, filepath.name)

        logger.info("Loaded {} instruction/response pairs from {}", len(pairs), filepath.name)
        return pairs

    def _tokenize_pairs(
        self,
        pairs: List[Dict[str, str]],
        max_seq_len: Optional[int] = None,
    ) -> List[torch.Tensor]:
        """
        Tokenize instruction/response pairs into padded token-ID tensors.

        Format per sequence:
            ``<BOS> instruction_tokens <SEP> response_tokens <EOS> <PAD>...``

        Sequences longer than *max_seq_len* are truncated; shorter ones are
        right-padded with the ``<PAD>`` token.

        Args:
            pairs:       Output of :meth:`_load_jsonl`.
            max_seq_len: Maximum sequence length (default: ``config.max_seq_len``).

        Returns:
            List of 1-D ``torch.LongTensor`` of length *max_seq_len*.
        """
        if max_seq_len is None:
            max_seq_len = getattr(self.config, "max_seq_len", 512)

        # Resolve special-token IDs from the tokenizer
        bos_id: int = getattr(self.tokenizer, "bos_id", 1)
        eos_id: int = getattr(self.tokenizer, "eos_id", 2)
        sep_id: int = getattr(self.tokenizer, "sep_id", 3)
        pad_id: int = getattr(self.tokenizer, "pad_id", 0)

        sequences: List[torch.Tensor] = []
        too_short = 0

        for pair in pairs:
            inst_ids: List[int] = self.tokenizer.encode(pair["instruction"])
            resp_ids: List[int] = self.tokenizer.encode(pair["response"])

            # Build full sequence: <BOS> inst <SEP> resp <EOS>
            token_ids = [bos_id] + inst_ids + [sep_id] + resp_ids + [eos_id]

            # Skip degenerate sequences (instruction + response too short)
            if len(token_ids) < 4:
                too_short += 1
                continue

            # Truncate to max_seq_len
            if len(token_ids) > max_seq_len:
                token_ids = token_ids[:max_seq_len]
                # Ensure the sequence still ends with <EOS>
                token_ids[-1] = eos_id

            # Right-pad to max_seq_len
            padding_len = max_seq_len - len(token_ids)
            token_ids = token_ids + [pad_id] * padding_len

            sequences.append(torch.tensor(token_ids, dtype=torch.long))

        if too_short:
            logger.warning("Dropped {} sequences shorter than 4 tokens", too_short)

        logger.info(
            "Tokenized {} sequences (max_seq_len={}, pad_id={})",
            len(sequences),
            max_seq_len,
            pad_id,
        )
        return sequences

    # ── Checkpointing ────────────────────────────────────────────────────

    def save_checkpoint(self, path: str, epoch: int, loss: float) -> None:
        """
        Save a training checkpoint containing model weights, optimizer state,
        epoch counter, and current loss.

        Args:
            path:  Destination file path (e.g. ``checkpoints/epoch_4.pt``).
            epoch: Current epoch number.
            loss:  Most recent average training loss.
        """
        checkpoint_path = Path(path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "epoch": epoch,
            "loss": loss,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict() if self.optimizer else None,
            "config": {
                k: v
                for k, v in vars(self.config).items()
                if isinstance(v, (int, float, str, bool))
            },
            "timestamp": time.time(),
        }
        torch.save(payload, checkpoint_path)
        logger.info(
            "Checkpoint saved → {} (epoch={}, loss={:.4f})",
            checkpoint_path.name,
            epoch,
            loss,
        )

    def load_checkpoint(self, path: str) -> Dict[str, Any]:
        """
        Load a previously saved training checkpoint.

        Restores model weights and (optionally) optimizer state.  Returns
        metadata so the caller can resume from the correct epoch.

        Args:
            path: Path to the ``.pt`` checkpoint file.

        Returns:
            Dict with keys ``epoch``, ``loss``, ``config``, ``timestamp``.

        Raises:
            FileNotFoundError: If *path* does not exist.
        """
        checkpoint_path = Path(path)
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

        checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=False)

        # Restore model weights
        self.model.load_state_dict(checkpoint["model_state_dict"])
        logger.info("Model weights restored from {}", checkpoint_path.name)

        # Restore optimizer state if available and optimizer is initialised
        if self.optimizer and checkpoint.get("optimizer_state_dict"):
            try:
                self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                logger.info("Optimizer state restored")
            except Exception as exc:
                logger.warning("Could not restore optimizer state: {}", exc)

        metadata = {
            "epoch": checkpoint.get("epoch", 0),
            "loss": checkpoint.get("loss", float("inf")),
            "config": checkpoint.get("config", {}),
            "timestamp": checkpoint.get("timestamp", 0.0),
        }
        logger.info(
            "Checkpoint loaded — epoch={}, loss={:.4f}",
            metadata["epoch"],
            metadata["loss"],
        )
        return metadata

    # ── Training history persistence ─────────────────────────────────────

    def _save_training_log(self) -> None:
        """Persist ``self.history`` to ``training_log.json`` in *data_dir*."""
        log_path = self.data_dir / "training_log.json"
        try:
            with open(log_path, "w", encoding="utf-8") as fh:
                json.dump(self.history, fh, indent=2)
            logger.debug("Training log saved → {}", log_path)
        except Exception as exc:
            logger.error("Failed to save training log: {}", exc)

    # ── Main training loop ───────────────────────────────────────────────

    def train(
        self,
        data_path: str,
        epochs: int = 10,
        batch_size: int = 8,
        lr: float = 3e-4,
        save_every: int = 2,
    ) -> Dict[str, Any]:
        """
        Run the full training loop on JSONL instruction/response data.

        Pipeline:
            1. Load JSONL → list of instruction/response dicts
            2. Tokenize into padded ``<BOS> inst <SEP> resp <EOS>`` tensors
            3. Wrap in a ``DataLoader``
            4. Train with AdamW + cosine-annealing LR + gradient clipping
            5. Checkpoint every *save_every* epochs
            6. Write ``training_log.json`` at the end

        Args:
            data_path:  Path to the JSONL training file.
            epochs:     Number of full passes over the dataset.
            batch_size: Mini-batch size.
            lr:         Peak learning rate for AdamW.
            save_every: Save a checkpoint every N epochs.

        Returns:
            Summary dict with final loss, total steps, and epochs completed.
        """
        logger.info("═══ Training started ═══")
        logger.info(
            "epochs={}, batch_size={}, lr={}, save_every={}",
            epochs,
            batch_size,
            lr,
            save_every,
        )

        # 1. Load data
        pairs = self._load_jsonl(data_path)
        if not pairs:
            logger.error("No valid training pairs found in {}. Aborting.", data_path)
            return {"error": "empty_dataset", "epochs_completed": 0}

        # 2. Tokenize
        sequences = self._tokenize_pairs(pairs)
        if not sequences:
            logger.error("All sequences were dropped during tokenization. Aborting.")
            return {"error": "no_valid_sequences", "epochs_completed": 0}

        # 3. DataLoader
        dataset = InstructionResponseDataset(sequences)
        dataloader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=True,
            drop_last=False,
            pin_memory=(self.device.type == "cuda"),
        )
        logger.info(
            "DataLoader ready — {} samples, {} batches/epoch",
            len(dataset),
            len(dataloader),
        )

        # 4. Optimizer + scheduler
        self.optimizer = AdamW(self.model.parameters(), lr=lr, weight_decay=0.01)
        total_steps = len(dataloader) * epochs
        self.scheduler = CosineAnnealingLR(
            self.optimizer,
            T_max=max(total_steps, 1),
            eta_min=lr * 0.1,
        )

        # Loss function — ignore PAD tokens
        pad_id: int = getattr(self.tokenizer, "pad_id", 0)
        criterion = nn.CrossEntropyLoss(ignore_index=pad_id)

        # 5. Training loop
        self.model.train()
        global_step = 0
        best_loss = float("inf")
        start_time = time.time()

        for epoch in range(1, epochs + 1):
            epoch_loss = 0.0
            epoch_steps = 0

            for batch_idx, (input_ids, target_ids) in enumerate(dataloader, start=1):
                input_ids = input_ids.to(self.device)
                target_ids = target_ids.to(self.device)

                # Forward pass
                logits, _ = self.model(input_ids)  # (B, T, vocab_size)

                # Reshape for cross-entropy: (B*T, vocab) vs (B*T,)
                loss = criterion(
                    logits.reshape(-1, logits.size(-1)),
                    target_ids.reshape(-1),
                )

                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()

                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

                self.optimizer.step()
                self.scheduler.step()

                epoch_loss += loss.item()
                epoch_steps += 1
                global_step += 1

                # Log every 10 steps
                if global_step % 10 == 0:
                    current_lr = self.scheduler.get_last_lr()[0]
                    logger.info(
                        "step={:>5d} | epoch={}/{} | loss={:.4f} | lr={:.2e}",
                        global_step,
                        epoch,
                        epochs,
                        loss.item(),
                        current_lr,
                    )

            # Epoch summary
            avg_epoch_loss = epoch_loss / max(epoch_steps, 1)
            elapsed = time.time() - start_time
            logger.info(
                "Epoch {}/{} complete — avg_loss={:.4f} | elapsed={:.1f}s",
                epoch,
                epochs,
                avg_epoch_loss,
                elapsed,
            )

            # Record history
            self.history.append(
                {
                    "epoch": epoch,
                    "avg_loss": round(avg_epoch_loss, 6),
                    "lr": round(self.scheduler.get_last_lr()[0], 8),
                    "elapsed_s": round(elapsed, 2),
                }
            )

            # Track best loss
            if avg_epoch_loss < best_loss:
                best_loss = avg_epoch_loss

            # Checkpoint
            if epoch % save_every == 0 or epoch == epochs:
                ckpt_name = f"checkpoint_epoch_{epoch}.pt"
                self.save_checkpoint(
                    str(self.data_dir / ckpt_name),
                    epoch=epoch,
                    loss=avg_epoch_loss,
                )
                # Also save as "latest" for easy loading
                self.save_checkpoint(
                    str(self.data_dir / "checkpoint_latest.pt"),
                    epoch=epoch,
                    loss=avg_epoch_loss,
                )

        # 6. Persist training history
        self._save_training_log()

        total_time = time.time() - start_time
        summary = {
            "epochs_completed": epochs,
            "final_loss": round(best_loss, 6),
            "total_steps": global_step,
            "total_time_s": round(total_time, 2),
            "samples": len(dataset),
        }
        logger.info("═══ Training complete ═══ {}", summary)
        return summary

    # ── Train from JARVIS conversations ──────────────────────────────────

    def train_on_conversations(
        self,
        db_path: str,
        epochs: int = 5,
        batch_size: int = 8,
        lr: float = 3e-4,
    ) -> Dict[str, Any]:
        """
        Extract instruction/response pairs from the JARVIS SQLite database
        and run training on them.

        The ``messages`` table is expected to have at least:
            ``conversation_id``, ``role`` ('user' | 'assistant'), ``content``

        Adjacent user→assistant message pairs within the same conversation
        become one training sample.

        Args:
            db_path: Path to the SQLite database (e.g. ``data/jarvis.db``).
            epochs:  Number of training epochs.
            batch_size: Mini-batch size.
            lr:      Peak learning rate.

        Returns:
            Training summary dict (same as :meth:`train`).
        """
        db_file = Path(db_path)
        if not db_file.exists():
            logger.error("Database not found: {}", db_path)
            return {"error": "db_not_found", "epochs_completed": 0}

        logger.info("Extracting training pairs from JARVIS database: {}", db_path)

        try:
            conn = sqlite3.connect(str(db_file))
            cursor = conn.cursor()

            # Fetch all messages ordered by conversation, then by rowid
            cursor.execute(
                """
                SELECT conversation_id, role, content
                FROM messages
                ORDER BY conversation_id, rowid
                """
            )
            rows = cursor.fetchall()
            conn.close()
        except Exception as exc:
            logger.error("Failed to read database: {}", exc)
            return {"error": f"db_read_error: {exc}", "epochs_completed": 0}

        if not rows:
            logger.warning("No messages found in database")
            return {"error": "no_messages", "epochs_completed": 0}

        # Group by conversation_id
        conversations: Dict[str, List[Tuple[str, str]]] = {}
        for conv_id, role, content in rows:
            conversations.setdefault(conv_id, []).append((role, content))

        # Create instruction/response pairs from adjacent user→assistant turns
        pairs: List[Dict[str, str]] = []
        for conv_id, messages in conversations.items():
            for i in range(len(messages) - 1):
                role_user, content_user = messages[i]
                role_asst, content_asst = messages[i + 1]

                if role_user == "user" and role_asst == "assistant":
                    user_text = content_user.strip()
                    asst_text = content_asst.strip()
                    if user_text and asst_text:
                        pairs.append(
                            {"instruction": user_text, "response": asst_text}
                        )

        if not pairs:
            logger.warning("No valid user→assistant pairs extracted from database")
            return {"error": "no_valid_pairs", "epochs_completed": 0}

        logger.info(
            "Extracted {} training pairs from {} conversations",
            len(pairs),
            len(conversations),
        )

        # Write to a temporary JSONL file and delegate to train()
        tmp_dir = self.data_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        tmp_path = tmp_dir / "conversation_training_data.jsonl"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                for pair in pairs:
                    fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
            logger.info("Wrote temporary training file: {}", tmp_path)
        except Exception as exc:
            logger.error("Failed to write temporary JSONL: {}", exc)
            return {"error": f"write_error: {exc}", "epochs_completed": 0}

        # Delegate to the main training loop
        result = self.train(
            data_path=str(tmp_path),
            epochs=epochs,
            batch_size=batch_size,
            lr=lr,
        )

        # Clean up temp file
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

        return result
