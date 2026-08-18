"""
JARVIS AI OS - Hierarchical Intent & Task-Based Model Router.
=============================================================
Implements a decision hierarchy routing user requests into:
- CONVERSATION / CHAT
- KNOWLEDGE
- ACTION
- LIVE_PERCEPTION
- RESEARCH
- WORKFLOW
- SYSTEM
- MULTI_STEP_TASK
- CLARIFICATION

Assigns optimal models based on task complexity, latency requirements,
offline state, and tool schemas. Guarantees tool execution for executable requests.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.utils.logger import logger
from backend.models.envelope import RequestEnvelope, RequestModality


class HierarchicalCategory(str, Enum):
    CHAT = "CHAT"
    CONVERSATION = "CONVERSATION"
    KNOWLEDGE = "KNOWLEDGE"
    ACTION = "ACTION"
    LIVE_PERCEPTION = "LIVE_PERCEPTION"
    AUTOMATION = "AUTOMATION"
    WORKFLOW = "WORKFLOW"
    RESEARCH = "RESEARCH"
    SYSTEM = "SYSTEM"
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
        self.fast_greetings = {"hi", "hello", "hey", "jarvis", "ping", "test", "who are you", "greetings"}

    def classify_and_route(
        self, envelope: RequestEnvelope, force_offline: bool = False
    ) -> tuple[HierarchicalCategory, TargetModelAssignment]:
        """
        Classifies incoming RequestEnvelope through an expanded decision hierarchy:
        1. Is conversational greeting? -> CHAT / CONVERSATION
        2. Requires multi-step workflow? -> MULTI_STEP_TASK
        3. Requires active Live Perception? -> LIVE_PERCEPTION
        4. Relates to n8n / visual canvas workflow? -> WORKFLOW
        5. Explicit web search or URL analysis? -> RESEARCH
        6. System controls (shutdown, battery, volume)? -> SYSTEM
        7. OS / Win32 / Application / Script / Job ID execution? -> ACTION
        8. Default knowledge / RAG query? -> KNOWLEDGE
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
        live_triggers = ["look at my screen", "what is on my screen", "what window", "see this", "spotlight", "read screen", "describe screen"]
        if msg_type == "live_frame" or any(trig in lower_text for trig in live_triggers):
            category = HierarchicalCategory.LIVE_PERCEPTION
            assignment = self._select_model(category, force_offline, complexity="medium")
            assignment.requires_perception = True
            logger.info("HierarchicalRouter: Classified Tier 3 LIVE_PERCEPTION")
            return category, assignment

        # ── Tier 4: Workflow / n8n Engine Triggers ────────────────────────────────
        workflow_triggers = ["n8n", "workflow", "canvas", "visual builder", "trigger workflow", "run workflow"]
        if any(trig in lower_text for trig in workflow_triggers):
            category = HierarchicalCategory.WORKFLOW
            assignment = self._select_model(category, force_offline, complexity="medium")
            logger.info("HierarchicalRouter: Classified Tier 4 WORKFLOW")
            return category, assignment

        # ── Tier 5: Web Research Triggers ─────────────────────────────────────────
        research_triggers = ["search online", "search web", "google", "find online", "research ", "latest news", "http://", "https://"]
        if any(trig in lower_text for trig in research_triggers):
            category = HierarchicalCategory.RESEARCH
            assignment = self._select_model(category, force_offline, complexity="medium")
            logger.info("HierarchicalRouter: Classified Tier 5 RESEARCH")
            return category, assignment

        # ── Tier 6: System Control Triggers ───────────────────────────────────────
        system_triggers = ["shutdown", "restart", "lock screen", "set volume", "mute", "unmute", "battery", "system status", "system diagnostic"]
        if any(trig in lower_text for trig in system_triggers):
            category = HierarchicalCategory.SYSTEM
            assignment = self._select_model(category, force_offline, complexity="low")
            logger.info("HierarchicalRouter: Classified Tier 6 SYSTEM")
            return category, assignment

        # ── Tier 7: OS / Application / Script / Job ID Action Execution ───────────
        action_verbs = [
            "run", "open", "launch", "execute", "start", "play", "click", "type",
            "resize", "close", "kill", "find file", "delete", "clean", "clear",
            "minimize", "maximize", "fill form", "scroll", "tap"
        ]
        # Match action verbs at start of prompt or job ID patterns e.g. "Run AP24110011746"
        is_action_verb = any(re.match(rf"^\b{verb}\b", lower_text) for verb in action_verbs)
        has_job_pattern = bool(re.search(r"\b[A-Z]{2,}\d{5,}\b", text))  # Matches e.g. AP24110011746
        has_ext_pattern = bool(re.search(r"\.(exe|py|bat|sh|ps1|pdf|docx|txt|json)\b", lower_text))

        if is_action_verb or has_job_pattern or has_ext_pattern or "button" in lower_text or "app" in lower_text:
            category = HierarchicalCategory.ACTION
            assignment = self._select_model(category, force_offline, complexity="medium")
            logger.info("HierarchicalRouter: Classified Tier 7 ACTION (Job/Verb Match)")
            return category, assignment

        # Default Tier 8: KNOWLEDGE / Conversational Query
        category = HierarchicalCategory.KNOWLEDGE
        assignment = self._select_model(category, force_offline, complexity="medium")
        logger.info("HierarchicalRouter: Classified Tier 8 KNOWLEDGE")
        return category, assignment

    def _select_model(
        self, category: HierarchicalCategory, force_offline: bool, complexity: str
    ) -> TargetModelAssignment:
        if force_offline:
            return TargetModelAssignment(
                provider="prash",
                model_name="prash-local-3b",
                reasoning_complexity=complexity,
                use_tools=category in (
                    HierarchicalCategory.ACTION,
                    HierarchicalCategory.AUTOMATION,
                    HierarchicalCategory.WORKFLOW,
                    HierarchicalCategory.SYSTEM,
                    HierarchicalCategory.RESEARCH,
                    HierarchicalCategory.MULTI_STEP_TASK
                ),
            )

        if category in (HierarchicalCategory.CHAT, HierarchicalCategory.CONVERSATION):
            return TargetModelAssignment(
                provider="groq",
                model_name="llama-3.3-70b-versatile",
                reasoning_complexity="low",
                use_tools=False,
            )
        elif category == HierarchicalCategory.KNOWLEDGE:
            return TargetModelAssignment(
                provider="groq",
                model_name="llama-3.3-70b-versatile",
                reasoning_complexity="medium",
                use_tools=False,
            )
        else:
            return TargetModelAssignment(
                provider="groq",
                model_name="llama-3.3-70b-versatile",
                reasoning_complexity="medium",
                use_tools=True,
            )
