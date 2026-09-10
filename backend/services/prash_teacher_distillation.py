"""
JARVIS AI OS — Teacher-Student Distillation Pipeline & Dataset Generator.
==========================================================================
Manages structured dataset generation using Qwen3:8B as the teacher model.
Supports live execution feedback capture, deduplication, category balancing,
schema validation, and unsafe output filtering.

Dataset Item Schema:
  user_request → context → expected_intent → tool/plan → params → expected_result
"""

from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field
from loguru import logger

from backend.config import PROJECT_ROOT, get_settings


class TeacherDatasetSample(BaseModel):
    user_request: str
    context: Dict[str, Any] = Field(default_factory=dict)
    expected_intent: str
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    expected_result: str
    category: str  # "intent", "tool_selection", "parameters", "plan", "error_recovery", "safe_refusal"
    verified: bool = True
    is_safe: bool = True
    source: str = "qwen3:8b_teacher"
    timestamp: float = Field(default_factory=time.time)

    def compute_hash(self) -> str:
        """Computes a normalized SHA256 fingerprint for deduplication."""
        norm_str = f"{self.user_request.lower().strip()}:{self.tool_name}:{json.dumps(self.parameters, sort_keys=True)}"
        return hashlib.sha256(norm_str.encode("utf-8")).hexdigest()


class PrashTeacherDatasetPipeline:
    """
    Dataset management pipeline for Prash teacher-student distillation.
    Handles data collection, Qwen teacher synthesis, live feedback, deduplication,
    category balancing, and train/test dataset export.
    """

    CATEGORIES = ["intent", "tool_selection", "parameters", "plan", "error_recovery", "safe_refusal"]

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        settings = get_settings()
        self.data_dir = data_dir or (PROJECT_ROOT / "data" / "prash")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_file = self.data_dir / "teacher_dataset.jsonl"

    def save_sample(self, sample: TeacherDatasetSample) -> bool:
        """Appends a single verified sample to the JSONL dataset if valid and non-duplicate."""
        if not sample.verified or not sample.is_safe:
            logger.warning(f"Skipping unverified or unsafe sample for request: '{sample.user_request}'")
            return False

        existing_samples = self.load_dataset()
        existing_hashes = {s.compute_hash() for s in existing_samples}

        if sample.compute_hash() in existing_hashes:
            logger.debug(f"Deduplicated duplicate sample for request: '{sample.user_request}'")
            return False

        try:
            with open(self.dataset_file, "a", encoding="utf-8") as f:
                f.write(sample.model_dump_json() + "\n")
            logger.info(f"✓ Saved teacher sample [{sample.category}] '{sample.user_request}' -> tool '{sample.tool_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to write teacher dataset sample: {e}")
            return False

    def load_dataset(self) -> List[TeacherDatasetSample]:
        """Loads all samples from the dataset JSONL file."""
        if not self.dataset_file.exists():
            return []

        samples = []
        try:
            with open(self.dataset_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line.strip())
                            samples.append(TeacherDatasetSample(**data))
                        except Exception:
                            continue
        except Exception as e:
            logger.error(f"Failed to load dataset from {self.dataset_file}: {e}")
        return samples

    def record_live_execution(
        self,
        user_request: str,
        context: Dict[str, Any],
        intent: str,
        tool_name: str,
        parameters: Dict[str, Any],
        execution_result: str,
        is_safe: bool,
        is_verified: bool,
        category: str = "tool_selection",
        source: str = "qwen3:8b_live_execution",
    ) -> bool:
        """
        Feedback Loop: Records a live successful execution trace from Qwen/Planner as a training example.
        Filters out unsafe or unverified outputs.
        """
        if not is_safe or not is_verified:
            logger.info(f"Feedback Loop Filtered: Execution for '{user_request}' was unsafe or unverified. Not saved to dataset.")
            return False

        sample = TeacherDatasetSample(
            user_request=user_request,
            context=context,
            expected_intent=intent,
            tool_name=tool_name,
            parameters=parameters,
            expected_result=execution_result,
            category=category if category in self.CATEGORIES else "tool_selection",
            verified=is_verified,
            is_safe=is_safe,
            source=source,
        )

        return self.save_sample(sample)

    def get_balanced_dataset(self, max_per_category: int = 500) -> List[TeacherDatasetSample]:
        """
        Deduplicates, validates, and balances samples across all categories.
        """
        all_samples = self.load_dataset()
        categorized: Dict[str, List[TeacherDatasetSample]] = {cat: [] for cat in self.CATEGORIES}

        seen_hashes: Set[str] = set()

        for s in all_samples:
            if not s.verified or not s.is_safe:
                continue
            h = s.compute_hash()
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            cat = s.category if s.category in categorized else "tool_selection"
            if len(categorized[cat]) < max_per_category:
                categorized[cat].append(s)

        balanced_samples: List[TeacherDatasetSample] = []
        for cat, items in categorized.items():
            balanced_samples.extend(items)
            logger.info(f"Balanced Dataset Category '{cat}': {len(items)} samples")

        return balanced_samples

    async def generate_synthetic_teacher_samples(
        self,
        teacher_model: str = "qwen3:8b",
        samples_per_category: int = 5,
    ) -> List[TeacherDatasetSample]:
        """
        Uses qwen3:8b to synthesize structured training examples across all 6 JARVIS categories.
        """
        from backend.services.llm import LLMService

        llm = LLMService()
        generated: List[TeacherDatasetSample] = []

        categories_prompts = {
            "intent": "Generate user requests and intent names for JARVIS desktop operations.",
            "tool_selection": "Generate mapping of user commands to exact ToolRegistry tool names (e.g. open_application, take_screenshot, search_files).",
            "parameters": "Generate commands and JSON parameter payloads for tools requiring arguments.",
            "plan": "Generate multi-step sequential plans for complex desktop tasks.",
            "error_recovery": "Generate user queries, failed initial states, and error recovery tool actions.",
            "safe_refusal": "Generate dangerous system requests (e.g. delete system32, steal credentials) and expected safe refusal responses.",
        }

        for cat in self.CATEGORIES:
            prompt = (
                f"You are the Teacher Model ({teacher_model}) for JARVIS AI OS.\n"
                f"Task: Generate {samples_per_category} high-quality structured training JSON examples for category '{cat}'.\n"
                f"Category Focus: {categories_prompts.get(cat, '')}\n\n"
                f"Return ONLY a JSON array of objects with keys:\n"
                f"  user_request: string\n"
                f"  context: dict\n"
                f"  expected_intent: string\n"
                f"  tool_name: string\n"
                f"  parameters: dict\n"
                f"  expected_result: string\n\n"
                f"Example JSON structure:\n"
                f'[{{"user_request": "take a screenshot", "context": {{}}, "expected_intent": "SCREENSHOT", "tool_name": "take_screenshot", "parameters": {{}}, "expected_result": "Screenshot captured successfully"}}]'
            )

            try:
                raw_resp = ""
                if getattr(llm, "ollama_client", None):
                    resp = await llm.ollama_client.chat.completions.create(
                        model=teacher_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                    )
                    raw_resp = resp.choices[0].message.content or ""
                else:
                    async for chunk in llm.generate_response(prompt):
                        if chunk.get("type") == "response":
                            raw_resp = chunk.get("data", {}).get("text", "")
                            break
                # Parse JSON array from LLM output
                json_match = raw_resp.strip()
                if "```json" in json_match:
                    json_match = json_match.split("```json")[1].split("```")[0].strip()
                elif "```" in json_match:
                    json_match = json_match.split("```")[1].split("```")[0].strip()

                parsed = json.loads(json_match)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "user_request" in item:
                            sample = TeacherDatasetSample(
                                user_request=item.get("user_request", ""),
                                context=item.get("context", {}),
                                expected_intent=item.get("expected_intent", "UNKNOWN"),
                                tool_name=item.get("tool_name", "unknown"),
                                parameters=item.get("parameters", {}),
                                expected_result=item.get("expected_result", ""),
                                category=cat,
                                verified=True,
                                is_safe=True,
                                source=f"teacher_{teacher_model}",
                            )
                            if self.save_sample(sample):
                                generated.append(sample)
            except Exception as err:
                logger.warning(f"Teacher synthesis for category '{cat}' notice: {err}")

        return generated
