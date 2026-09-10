"""
JARVIS AI OS — Teacher-Student Distillation Orchestrator.
===========================================================
Trains Prash (Student model) using high-quality dataset examples synthesized by Qwen3:8B (Teacher model)
or collected from verified execution logs.

Full End-to-End Distillation Lifecycle:
  1. Dataset Preparation & Category Balancing
  2. Pre-Training Baseline Evaluation (PrashBenchmarkSuite)
  3. BPE Tokenized Instruction-Response Fine-Tuning (PrashTrainer)
  4. Post-Training Evaluation (PrashBenchmarkSuite)
  5. Safe Checkpoint Preservation (best_prash_checkpoint.pt protection)
  6. Live PrashEngine Reloading
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import torch
from loguru import logger

from backend.config import PROJECT_ROOT
from backend.prash.tokenizer import PrashTokenizer
from backend.prash.model import PrashConfig, PrashTransformer
from backend.prash.training import PrashTrainer
from backend.prash.benchmark import PrashBenchmarkSuite, BenchmarkMetrics
from backend.services.prash_teacher_distillation import PrashTeacherDatasetPipeline, TeacherDatasetSample


class PrashDistillationEngine:
    """Orchestrates Teacher-Student Distillation between Qwen3:8B and Prash."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = data_dir or (PROJECT_ROOT / "data" / "prash")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pipeline = PrashTeacherDatasetPipeline(data_dir=self.data_dir)
        self.benchmark_suite = PrashBenchmarkSuite(data_dir=self.data_dir)

    def prepare_distillation_data(self) -> Path:
        """
        Loads balanced teacher dataset and converts samples into Prash instruction-response pairs.
        Returns path to the formatted training JSONL file.
        """
        samples = self.pipeline.get_balanced_dataset(max_per_category=500)

        # Fallback seeding if dataset is sparse
        if len(samples) < 10:
            logger.info("Dataset contains < 10 samples. Seeding baseline training pairs...")
            seed_pairs = [
                ("hello jarvis", "Hello sir, how can I assist you today?"),
                ("open notepad", "Opening notepad application now, sir."),
                ("take a screenshot", "Taking a screenshot of your screen now, sir."),
                ("lock computer", "Locking your computer workstation now, sir."),
                ("get system status", "Querying current CPU and memory status, sir."),
            ]
            train_pairs = [{"instruction": inst, "response": resp} for inst, resp in seed_pairs]
        else:
            train_pairs = []
            for s in samples:
                # Format intent / tool response pattern
                if s.tool_name and s.tool_name != "unknown":
                    resp_str = json.dumps({"action": "tool_call", "name": s.tool_name, "parameters": s.parameters})
                else:
                    resp_str = s.expected_result or "Action acknowledged, sir."
                train_pairs.append({"instruction": s.user_request, "response": resp_str})

        # Multiply dataset for epoch training iterations
        expanded_pairs = train_pairs * 10
        train_file = self.data_dir / "distillation_train_data.jsonl"

        try:
            with open(train_file, "w", encoding="utf-8") as f:
                for pair in expanded_pairs:
                    f.write(json.dumps(pair) + "\n")
            logger.info(f"✓ Formatted {len(expanded_pairs)} distillation pairs into {train_file}")
        except Exception as e:
            logger.error(f"Failed to write distillation train file: {e}")

        return train_file

    async def run_distillation_cycle(
        self,
        engine: Any,
        epochs: int = 5,
        learning_rate: float = 5e-4,
        teacher_model: str = "qwen3:8b",
    ) -> Dict[str, Any]:
        """
        Executes a full Teacher-Student Distillation cycle:
          1. Synthesize teacher dataset using qwen3:8b if needed
          2. Baseline evaluation of PrashEngine
          3. PrashTrainer fine-tuning
          4. Post-training evaluation
          5. Safe Checkpoint Preservation check
          6. Engine re-initialization
        """
        logger.info(f"🚀 Starting Prash Teacher-Student Distillation Cycle (Teacher: {teacher_model})")
        start_time = time.time()

        # Step 1: Synthesize teacher dataset if empty
        existing_dataset = self.pipeline.load_dataset()
        if len(existing_dataset) < 10:
            logger.info("Generating synthetic teacher samples from Qwen3:8B...")
            await self.pipeline.generate_synthetic_teacher_samples(teacher_model=teacher_model, samples_per_category=3)

        train_file = self.prepare_distillation_data()

        # Step 2: Pre-training Baseline Evaluation
        logger.info("Phase 1: Running Pre-Training Baseline Evaluation...")
        before_metrics = await self.benchmark_suite.evaluate_engine(engine)

        # Step 3: Train Prash Model
        logger.info("Phase 2: Fine-Tuning Prash Model Weights...")
        temp_ckpt = self.data_dir / "checkpoint_temp_distill.pt"

        try:
            # Ensure model & tokenizer are loaded
            if not getattr(engine, "model", None) or not getattr(engine, "tokenizer", None):
                await engine.init()

            model = getattr(engine, "model", None)
            tokenizer = getattr(engine, "tokenizer", None)
            config = getattr(engine, "config", None)

            if not model or not tokenizer or not config:
                raise RuntimeError("Prash model/tokenizer initialization failed prior to distillation.")

            trainer = PrashTrainer(model, tokenizer, config, device=engine.device, data_dir=str(self.data_dir))
            trainer.train(str(train_file), epochs=epochs, batch_size=16, lr=learning_rate, save_every=2)

            # Save temp checkpoint for evaluation
            torch.save({"model_state_dict": model.state_dict(), "epoch": epochs}, temp_ckpt)

        except Exception as err:
            logger.error(f"Distillation training failed: {err}")
            return {
                "status": "error",
                "message": f"Training failed: {err}",
                "before_metrics": before_metrics.to_dict(),
            }

        # Step 4: Post-Training Evaluation
        logger.info("Phase 3: Running Post-Training Evaluation...")
        after_metrics = await self.benchmark_suite.evaluate_engine(engine)

        # Step 5: Safe Checkpoint Preservation Decision
        logger.info("Phase 4: Evaluating Checkpoint Preservation Safety Rules...")
        checkpoint_updated = self.benchmark_suite.preserve_checkpoint_if_improved(
            new_checkpoint_path=temp_ckpt,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
        )

        # Step 6: Reload Prash Engine
        if checkpoint_updated:
            logger.info("Reloading PrashEngine with updated best weights...")
            await engine.init()

        cycle_duration = round(time.time() - start_time, 2)

        return {
            "status": "success",
            "checkpoint_updated": checkpoint_updated,
            "duration_seconds": cycle_duration,
            "before_metrics": before_metrics.to_dict(),
            "after_metrics": after_metrics.to_dict(),
            "teacher_model": teacher_model,
        }
