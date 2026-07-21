"""
Contextual Awareness & Ambient Intelligence Skill for JARVIS.
Tracks active window titles, process names, focus sessions, and builds semantic context summaries.
"""

import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import psutil

# Safe Win32 imports
win32_available = False
if sys.platform == "win32":
    try:
        import win32gui
        import win32process
        win32_available = True
    except ImportError:
        pass

from backend.services.skills.base import BaseSkill, skill_tool
from backend.utils.logger import logger


class ContextSkill(BaseSkill):
    """Enables JARVIS to keep track of active application usage, user focus, and inferred work items."""

    def __init__(self, automation_service=None, memory_service=None) -> None:
        self.automation = automation_service
        self.memory = memory_service
        
        # In-memory context state
        self.active_context: Dict[str, Any] = {
            "window_title": "Unknown",
            "process_name": "Unknown",
            "process_id": 0,
            "start_time": datetime.now().isoformat(),
            "inferred_project": "General Workspace"
        }
        
        self.focus_session_active = False
        self.focus_session_end: Optional[datetime] = None

    def update_active_window(self) -> bool:
        """Polls the OS foreground window and updates active context details.
        
        Returns:
            True if the active window changed, False if unchanged or unavailable.
        """
        if not win32_available:
            return False

        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False

            title = win32gui.GetWindowText(hwnd)
            if not title:
                return False

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == 0:
                return False

            # Skip if nothing changed
            if title == self.active_context["window_title"] and pid == self.active_context["process_id"]:
                return False

            try:
                proc = psutil.Process(pid)
                p_name = proc.name()
            except Exception:
                p_name = "unknown"

            # Infer project category
            inferred = self._infer_project(title, p_name)

            self.active_context = {
                "window_title": title,
                "process_name": p_name,
                "process_id": pid,
                "start_time": datetime.now().isoformat(),
                "inferred_project": inferred
            }
            # Log only on actual change (INFO, not DEBUG spam)
            logger.info("Context → {} [{}] :: {}", title[:45], p_name, inferred)
            return True
        except Exception as e:
            logger.debug("Failed updating active window context: {}", e)
            return False


    def _infer_project(self, title: str, proc_name: str) -> str:
        """Heuristic-based intent synthesis matching titles/processes to project domains."""
        title_l = title.lower()
        proc_l = proc_name.lower()

        if any(x in title_l for x in ("vscode", "visual studio", "pycharm", "eclipse", "sublime")) or any(x in proc_l for x in ("code.exe", "pycharm.exe", "cmd.exe", "terminal.exe")):
            return "Software Development"
        elif any(x in title_l for x in ("excel", "sheet", "csv", "calc")):
            return "Data Analysis & Spreadsheets"
        elif any(x in title_l for x in ("word", "document", "docx", "writer", "pdf", "resume")):
            return "Document Editing"
        elif any(x in title_l for x in ("slides", "powerpoint", "keynote")):
            return "Presentation Writing"
        elif any(x in title_l for x in ("outlook", "gmail", "inbox", "mail")):
            return "Email Coordination"
        elif any(x in title_l for x in ("teams", "slack", "discord", "whatsapp")):
            return "Team Communications"
        elif any(x in title_l for x in ("spotify", "youtube", "netflix")):
            return "Entertainment / Media"
            
        return "General Workspace"

    # ── Skill Tools ───────────────────────────────────────────────────────

    @skill_tool(
        name="get_active_context",
        description="Returns details about the currently focused foreground window, process name, and inferred active project context.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def get_active_context(self) -> str:
        # Check active session duration
        start = datetime.fromisoformat(self.active_context["start_time"])
        duration_sec = (datetime.now() - start).total_seconds()
        
        # Format minutes/seconds
        if duration_sec >= 60:
            dur_str = f"{int(duration_sec // 60)}m {int(duration_sec % 60)}s"
        else:
            dur_str = f"{int(duration_sec)}s"

        focus_status = "ACTIVE" if self.get_focus_status_bool() else "INACTIVE"

        return (
            f"🖥️ **Active Workspace Context**:\n"
            f"- Foreground Window: **{self.active_context['window_title']}**\n"
            f"- Application Process: `{self.active_context['process_name']}`\n"
            f"- Duration Focused: {dur_str}\n"
            f"- Inferred Activity: **{self.active_context['inferred_project']}**\n"
            f"- Do-Not-Disturb Focus Session: **{focus_status}**"
        )

    @skill_tool(
        name="set_focus_session",
        description="Enables or disables a Do-Not-Disturb focus session to filter alerts and track deep work time.",
        parameters={
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "description": "True to start focus, False to stop"},
                "duration_minutes": {"type": "integer", "description": "Duration of the focus session in minutes. Default is 25 (Pomodoro)."}
            },
            "required": ["enabled"]
        }
    )
    def set_focus_session(self, enabled: bool, duration_minutes: int = 25) -> str:
        if enabled:
            self.focus_session_active = True
            self.focus_session_end = datetime.now() + timedelta(minutes=duration_minutes)
            logger.info("Focus session started for {} minutes.", duration_minutes)
            return f"✓ Focus session started. Do-Not-Disturb enabled for {duration_minutes} minutes."
        else:
            self.focus_session_active = False
            self.focus_session_end = None
            logger.info("Focus session completed/cancelled.")
            return "✓ Focus session ended. Do-Not-Disturb disabled."

    @skill_tool(
        name="get_focus_status",
        description="Checks if a focus session is currently active and gets the remaining time.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def get_focus_status(self) -> str:
        if self.get_focus_status_bool():
            rem = self.focus_session_end - datetime.now()
            mins = int(rem.total_seconds() // 60)
            secs = int(rem.total_seconds() % 60)
            return f"🎯 Focus session is ACTIVE. Remaining time: {mins}m {secs}s."
        return "🎯 Focus session is currently INACTIVE."

    def get_focus_status_bool(self) -> bool:
        """Helper to check if focus is currently active, handling expired deadlines."""
        if self.focus_session_active:
            if self.focus_session_end and datetime.now() > self.focus_session_end:
                self.focus_session_active = False
                self.focus_session_end = None
                return False
            return True
        return False
