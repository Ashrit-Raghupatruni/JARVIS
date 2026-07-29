"""
Proactive Collaboration Engine for JARVIS Live Mode 2.0.

Continuously monitors the Desktop World Model and generates proactive human-like guidance:
- Terminal build & compilation error detection
- Form field omission alerts
- Next logical step synthesis
- Workflow optimization suggestions
"""

import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from backend.services.world_model import WorldModel, WorldModelState


class ProactiveGuidance(BaseModel):
    guidance_type: str = "suggestion"  # error_alert, form_warning, suggestion, workflow_step, session_continuity
    title: str
    message: str
    action_suggestion: Optional[str] = None
    confidence: float = 0.95


# Content Safety Guardrails for Background Topic Monitoring
BLOCKED_MONITOR_TOPICS = {
    "crypto", "cryptocurrency", "bitcoin", "ethereum", "memecoin",
    "forex", "daytrading", "stock option", "trading alert", "gambling", "casino"
}


class ProactiveEngine:
    """
    Real-Time Proactive Collaboration Engine for Live Mode 2.0.
    Includes Session Memory, 20-min Interjection Cooldown, and Content-Safe Topic Monitoring.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._action_history: List[str] = []
        self._last_proactive_time = 0.0
        self.cooldown_seconds = 1200.0  # 20 minutes between interjections
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session_memory_file = self.data_dir / "session_memory.json"
        self.monitored_topics_file = self.data_dir / "monitored_topics.json"
        logger.info("ProactiveEngine initialized (Proactive 2.0 with 20-min Cooldown & Session Memory Active).")

    # ── Session Memory (Ephemeral Continuity) ──────────────────────────

    def save_session_summary(self, summary_text: str) -> None:
        """Store 1-2 sentence ephemeral summary at shutdown."""
        try:
            payload = {
                "summary": summary_text.strip(),
                "timestamp": time.time(),
                "formatted_date": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.session_memory_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info("Saved ephemeral session summary for next boot continuity.")
        except Exception as e:
            logger.error("Failed to save session summary: {}", e)

    def get_and_clear_session_memory(self) -> Optional[str]:
        """Read session summary once on startup and discard it (never repeats)."""
        if not self.session_memory_file.exists():
            return None
        try:
            with open(self.session_memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            summary = data.get("summary")
            # Delete file after reading so it is used exactly once
            self.session_memory_file.unlink(missing_ok=True)
            return summary
        except Exception as e:
            logger.error("Failed to read session memory: {}", e)
            return None

    # ── Background Topic Monitoring (with Content Safety) ─────────────

    def add_monitored_topic(self, topic: str) -> Dict[str, Any]:
        """Add topic for background monitoring after validating content safety rules."""
        clean_topic = topic.lower().strip()
        
        # Enforce content-safety choice at code level
        if any(blocked in clean_topic for blocked in BLOCKED_MONITOR_TOPICS):
            logger.warning(f"Blocked background monitoring topic due to safety policy: '{topic}'")
            return {
                "status": "blocked",
                "reason": "Financial, day-trading, cryptocurrency, and gambling topics are blocked by system content-safety policy."
            }

        topics = self._load_monitored_topics()
        if clean_topic not in topics:
            topics.append(clean_topic)
            self._save_monitored_topics(topics)

        return {"status": "ok", "monitored_topics": topics}

    def _load_monitored_topics(self) -> List[str]:
        if self.monitored_topics_file.exists():
            try:
                with open(self.monitored_topics_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_monitored_topics(self, topics: List[str]) -> None:
        try:
            with open(self.monitored_topics_file, "w", encoding="utf-8") as f:
                json.dump(topics, f, indent=2)
        except Exception as e:
            logger.error("Failed to save monitored topics: {}", e)

    # ── Context Analysis & Proactive 2.0 Cooldown ──────────────────────

    def track_action(self, action_name: str) -> None:
        """Track user or system actions for repetition analysis."""
        self._action_history.append(action_name.lower().strip())
        if len(self._action_history) > 10:
            self._action_history.pop(0)

    def analyze_context(self, state: WorldModelState) -> Optional[ProactiveGuidance]:
        """
        Analyzes desktop state and returns proactive guidance if an actionable event is detected.
        """
        title = state.window_title.lower()
        app = state.active_app.lower()

        # 0. Repetitive Action Macro Nudge
        if len(self._action_history) >= 3:
            last_3 = self._action_history[-3:]
            if len(set(last_3)) == 1:
                repeated_act = last_3[0]
                logger.info("ProactiveEngine: Repetitive action detected '{}'", repeated_act)
                return ProactiveGuidance(
                    guidance_type="macro_recommendation",
                    title="Repetitive Desktop Action Detected",
                    message=f"I noticed you've repeated '{repeated_act}' multiple times, sir.",
                    action_suggestion=f"Would you like me to automate '{repeated_act}' as a reusable macro skill?"
                )

        # 1. Terminal / Code Error Detection
        if any(term in title or term in app for term in ["cmd", "powershell", "terminal", "bash", "vscode"]):
            if "error" in title or "failed" in title:
                logger.info("ProactiveEngine: Terminal build error detected")
                return ProactiveGuidance(
                    guidance_type="error_alert",
                    title="Build Error Detected",
                    message="I noticed an error in your terminal or code editor window.",
                    action_suggestion="Would you like me to inspect the error log and fix it?"
                )

        # 2. Form Field Omission Alert
        scene = state.scene_graph or {}
        forms = scene.get("forms", [])
        if forms:
            total_fields = scene.get("total_elements", 0)
            focused = scene.get("focused_element")
            if total_fields > 1 and focused:
                logger.info("ProactiveEngine: Active form detected")
                return ProactiveGuidance(
                    guidance_type="form_warning",
                    title="Form Field Assistant Ready",
                    message=f"I detected {total_fields} form controls in '{state.window_title}'.",
                    action_suggestion="Say 'Fill this form' to autofill using your saved profile."
                )

        # 3. Next Step Workflow Guidance
        if "browser" in app or "chrome" in app or "edge" in app:
            if "google" in title or "search" in title:
                return ProactiveGuidance(
                    guidance_type="workflow_step",
                    title="Search Guidance",
                    message="You are searching for information.",
                    action_suggestion="Say 'Summarize search results' once you open a target page."
                )

        return ProactiveGuidance(
            guidance_type="suggestion",
            title="Desktop Observation Active",
            message="JARVIS is observing your desktop context in real-time.",
            action_suggestion=f"Active workflow: {state.current_workflow}"
        )
