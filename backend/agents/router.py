"""
JARVIS AI OS - Hierarchical Intent & Task-Based Model Router.

Implements a 4-tier decision hierarchy routing user requests into CHAT, KNOWLEDGE,
ACTION, LIVE_PERCEPTION, AUTOMATION, MULTI_STEP_TASK, or CLARIFICATION categories,
and assigning optimal models based on task complexity, latency requirements,
offline state, and tool schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.utils.logger import logger
from backend.models.envelope import RequestEnvelope, RequestModality


class HierarchicalCategory(str, Enum):
    CHAT = "CHAT"
    KNOWLEDGE = "KNOWLEDGE"
    ACTION = "ACTION"
    LIVE_PERCEPTION = "LIVE_PERCEPTION"
    AUTOMATION = "AUTOMATION"
    MULTI_STEP_TASK = "MULTI_STEP_TASK"
    CLARIFICATION = "CLARIFICATION"


class TargetModelAssignment(BaseModel):
    provider: str  # "groq", "ollama", "openrouter", "gemini", "prash"
    model_name: str
    reasoning_complexity: str  # "low", "medium", "high"
    use_tools: bool = True
    requires_perception: bool = False


class RequestRouter:
    """Hierarchical Decision Engine for intent classification and model routing."""

    def __init__(self) -> None:
        self.fast_greetings = {"hi", "hello", "hey", "jarvis", "ping", "test", "who are you"}

    def classify_and_route(
        self, envelope: RequestEnvelope, force_offline: bool = False
    ) -> tuple[HierarchicalCategory, TargetModelAssignment]:
        """
        Classifies incoming RequestEnvelope through a 4-tier decision hierarchy:
        1. Is conversational greeting? -> CHAT
        2. Requires multi-step workflow? -> MULTI_STEP_TASK
        3. Requires active Live Perception? -> LIVE_PERCEPTION
        4. Requires Win32 automation tools? -> ACTION / AUTOMATION
        5. Default knowledge / RAG query? -> KNOWLEDGE
        """
        payload = envelope.payload
        msg_type = payload.get("type", "text_command")
        data = payload.get("data", {})
        text = str(data.get("text", "")).strip()
        lower_text = text.lower()

        # ── Tier 1: Conversational Greetings (Fast-Path CHAT) ─────────────────────
        if lower_text in self.fast_greetings or (len(lower_text.split()) <= 2 and "hello" in lower_text):
            category = HierarchicalCategory.CHAT
            assignment = self._select_model(category, force_offline, complexity="low")
            logger.info("HierarchicalRouter: Classified Tier 1 CHAT (Fast Greeting)")
            return category, assignment

        # ── Tier 2: Multi-Step Task Conjunctions ──────────────────────────────────
        multi_step_triggers = ["and then", "first", "after that", "next,", "then open", "and open"]
        if any(trig in lower_text for trig in multi_step_triggers) or lower_text.count(" and ") >= 2:
            category = HierarchicalCategory.MULTI_STEP_TASK
            assignment = self._select_model(category, force_offline, complexity="high")
            logger.info("HierarchicalRouter: Classified Tier 2 MULTI_STEP_TASK")
            return category, assignment

        # ── Tier 3: Active Live Mode Spatial Perception ───────────────────────────
        live_triggers = ["look at my screen", "what is on my screen", "what window", "see this", "spotlight"]
        if msg_type == "live_frame" or any(trig in lower_text for trig in live_triggers):
            category = HierarchicalCategory.LIVE_PERCEPTION
            assignment = self._select_model(category, force_offline, complexity="medium")
            assignment.requires_perception = True
            logger.info("HierarchicalRouter: Classified Tier 3 LIVE_PERCEPTION")
            return category, assignment

        # ── Tier 4: Win32 Automation Actions ─────────────────────────────────────
        action_verbs = ["open", "launch", "click", "type", "resize", "close", "minimize", "maximize", "fill form", "scroll"]
        if any(lower_text.startswith(verb) for verb in action_verbs) or "button" in lower_text or "app" in lower_text:
            category = HierarchicalCategory.ACTION
            assignment = self._select_model(category, force_offline, complexity="medium")
            logger.info("HierarchicalRouter: Classified Tier 4 ACTION")
            return category, assignment

        # Default: KNOWLEDGE / RAG Search
        category = HierarchicalCategory.KNOWLEDGE
        assignment = self._select_model(category, force_offline, complexity="medium")
        logger.info("HierarchicalRouter: Classified Tier 5 KNOWLEDGE")
        return category, assignment

    def _select_model(
        self, category: HierarchicalCategory, force_offline: bool, complexity: str
    ) -> TargetModelAssignment:
        if force_offline:
            return TargetModelAssignment(
                provider="prash",
                model_name="prash-local-3b",
                reasoning_complexity=complexity,
                use_tools=category in (HierarchicalCategory.ACTION, HierarchicalCategory.AUTOMATION),
            )

        if category == HierarchicalCategory.CHAT:
            return TargetModelAssignment(
                provider="groq",
                model_name="llama-3.3-70b-versatile",
                reasoning_complexity="low",
                use_tools=False,
            )
        elif category in (HierarchicalCategory.ACTION, HierarchicalCategory.AUTOMATION):
            return TargetModelAssignment(
                provider="groq",
                model_name="llama-3.3-70b-versatile",
                reasoning_complexity="medium",
                use_tools=True,
            )
        elif category == HierarchicalCategory.MULTI_STEP_TASK:
            return TargetModelAssignment(
                provider="openrouter",
                model_name="meta-llama/llama-3.3-70b-instruct:free",
                reasoning_complexity="high",
                use_tools=True,
            )
        else:
            return TargetModelAssignment(
                provider="groq",
                model_name="llama-3.3-70b-versatile",
                reasoning_complexity="medium",
                use_tools=True,
            )
