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
        self.rotation_index = 0  # 3-way focus area rotation (0: Active Project, 1: Monitored Topic, 2: Time-of-Day Agenda)
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session_memory_file = self.data_dir / "session_memory.json"
        self.monitored_topics_file = self.data_dir / "monitored_topics.json"
        self.seen_headlines_file = self.data_dir / "seen_headlines.json"
        logger.info("ProactiveEngine initialized (Proactive 2.0 with 20-min Cooldown & 3-Way Rotation Active).")

    # ── Session Memory (Ephemeral Continuity) ──────────────────────────

    def save_session_summary(self, summary_text: str) -> None:
        """Store 1-2 sentence ephemeral summary at shutdown."""
        try:
            payload = {
                "summary": summary_text.strip(),
                "timestamp": time.time(),
                "formatted_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "consumed": False
            }
            with open(self.session_memory_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            logger.info("Saved ephemeral session summary for next boot continuity.")
        except Exception as e:
            logger.error("Failed to save session summary: {}", e)

    def get_last_session_summary(self) -> Optional[str]:
        """Read session summary if present and not yet consumed."""
        if not self.session_memory_file.exists():
            return None
        try:
            with open(self.session_memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("consumed", False):
                return None
            return data.get("summary")
        except Exception as e:
            logger.error("Failed to read last session summary: {}", e)
            return None

    def consume_session_summary(self) -> None:
        """Mark session summary consumed and delete file so it is never reused."""
        if self.session_memory_file.exists():
            try:
                self.session_memory_file.unlink(missing_ok=True)
                logger.info("Consumed ephemeral session summary file.")
            except Exception as e:
                logger.error("Failed to consume session summary file: {}", e)

    def get_and_clear_session_memory(self) -> Optional[str]:
        """Read session summary once on startup and discard it (never repeats)."""
        summary = self.get_last_session_summary()
        if summary:
            self.consume_session_summary()
        return summary

    # ── Background Topic Monitoring (with Content Safety & Dedup) ─────

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

    def remove_monitored_topic(self, topic: str) -> Dict[str, Any]:
        """Remove a topic from background monitoring and update persistent storage."""
        clean_topic = topic.lower().strip()
        topics = self._load_monitored_topics()
        if clean_topic in topics:
            topics.remove(clean_topic)
            self._save_monitored_topics(topics)
            logger.info(f"Removed monitored topic: '{clean_topic}'")
        return {"status": "ok", "monitored_topics": topics}

    def get_monitored_topics(self) -> List[str]:
        """Return currently monitored topics list from persistent storage."""
        return self._load_monitored_topics()

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

    def is_headline_new(self, headline: str) -> bool:
        """Check if headline has already been processed to prevent duplicate notifications."""
        clean = headline.lower().strip()
        seen = []
        if self.seen_headlines_file.exists():
            try:
                with open(self.seen_headlines_file, "r", encoding="utf-8") as f:
                    seen = json.load(f)
            except Exception:
                seen = []

        if clean in seen:
            return False

        seen.append(clean)
        if len(seen) > 200:
            seen = seen[-200:]  # Cap rolling buffer

        try:
            with open(self.seen_headlines_file, "w", encoding="utf-8") as f:
                json.dump(seen, f, indent=2)
        except Exception:
            pass

        return True

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
        # 0A. Resource Anomaly Alert Check
        try:
            import psutil
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            if cpu > 90.0 or ram > 90.0:
                logger.warning(f"ProactiveEngine: Anomaly detected! CPU={cpu}%, RAM={ram}%")
                return ProactiveGuidance(
                    guidance_type="error_alert",
                    title="High Resource Utilization Detected",
                    message=f"System resource warning, sir. CPU usage is at {cpu}% and RAM memory load is at {ram}%.",
                    action_suggestion="Should I clean temporary directories or list heavy background processes?"
                )
        except Exception:
            pass

        title = state.window_title.lower()
        app = state.active_app.lower()

        # 0a. Hung Application Proactive Alert via Win32 API
        try:
            import ctypes, win32gui
            hwnd_fore = win32gui.GetForegroundWindow()
            if hwnd_fore and ctypes.windll.user32.IsHungAppWindow(hwnd_fore):
                hung_title = win32gui.GetWindowText(hwnd_fore) or "Active Window"
                logger.info("ProactiveEngine: Detected hung foreground window '{}'", hung_title)
                return ProactiveGuidance(
                    guidance_type="hung_app_alert",
                    title="Unresponsive Application Detected",
                    message=f"I detected that '{hung_title}' has stopped responding.",
                    action_suggestion="Say 'Recover hung application' to terminate the unresponsive process."
                )
        except Exception:
            pass

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

    def generate_proactive_checkin(
        self,
        active_project: str = "JARVIS AI OS",
        recent_turns: Optional[List[str]] = None,
        force: bool = False
    ) -> Optional[ProactiveGuidance]:
        """
        Generate proactive 2.0 check-in card using 4 context inputs:
        1. Time of day
        2. Active project from memory
        3. Monitored topics
        4. Recent conversation turns
        And 3-way rotation between focus areas (0: Active Project, 1: Monitored Topics, 2: Time-of-Day Agenda).
        Enforces 20-minute (1200s) cooldown unless force=True.
        """
        now = time.time()
        if not force and (now - self._last_proactive_time) < self.cooldown_seconds:
            logger.debug(f"Proactive 2.0 check-in skipped (cooldown active: {int(self.cooldown_seconds - (now - self._last_proactive_time))}s remaining)")
            return None

        self._last_proactive_time = now

        # Context Input 1: Time of Day
        hour = time.localtime().tm_hour
        if 5 <= hour < 12:
            tod = "Morning Briefing"
        elif 12 <= hour < 18:
            tod = "Afternoon Progress Review"
        else:
            tod = "Evening Workflow Summary"

        # Context Input 2: Active Project
        project_name = active_project or "JARVIS OS"

        # Context Input 3: Monitored Topics
        topics = self._load_monitored_topics()
        top_topic = topics[0] if topics else "Quantum Computing Advances"

        # Context Input 4: Conversation History
        turn_count = len(recent_turns) if recent_turns else 0

        # 3-Way Focus Area Rotation
        rot = self.rotation_index % 3
        self.rotation_index += 1

        if rot == 0:
            # Rotation 0: Active Project Check-in
            guidance = ProactiveGuidance(
                guidance_type="active_project",
                title=f"Proactive Check-In: {project_name}",
                message=f"[{tod}] You have been working on '{project_name}' across the last {turn_count} conversation turns.",
                action_suggestion="Shall I review recent code changes or run system integration tests?"
            )
        elif rot == 1:
            # Rotation 1: Monitored Topic Digest
            guidance = ProactiveGuidance(
                guidance_type="topic_digest",
                title=f"Background Topic Alert: {top_topic.title()}",
                message=f"[{tod}] Updated news digest available for monitored topic '{top_topic}'.",
                action_suggestion="Say 'Show topic news' to view visual card previews."
            )
        else:
            # Rotation 2: Time-of-Day Agenda
            guidance = ProactiveGuidance(
                guidance_type="agenda_recap",
                title=f"{tod} Agenda",
                message=f"[{tod}] Hardware resources nominal. {len(topics)} topic(s) monitored.",
                action_suggestion="Say 'Show daily briefing' for full task summary."
            )

        logger.info(f"Generated Proactive 2.0 Guidance (Rotation {rot}): '{guidance.title}'")
        return guidance
