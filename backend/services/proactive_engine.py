"""
Proactive Collaboration Engine for JARVIS Live Mode 2.0.

Continuously monitors the Desktop World Model and generates proactive human-like guidance:
- Terminal build & compilation error detection
- Form field omission alerts
- Next logical step synthesis
- Workflow optimization suggestions
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from loguru import logger

from backend.services.world_model import WorldModel, WorldModelState


class ProactiveGuidance(BaseModel):
    guidance_type: str = "suggestion"  # error_alert, form_warning, suggestion, workflow_step
    title: str
    message: str
    action_suggestion: Optional[str] = None
    confidence: float = 0.95


class ProactiveEngine:
    """
    Real-Time Proactive Collaboration Engine for Live Mode 2.0.
    """

    def __init__(self) -> None:
        self._action_history: List[str] = []
        logger.info("ProactiveEngine initialized (Human-Like Collaborative Guidance Active).")

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
