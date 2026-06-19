"""
Proactive Agent Mode and Scheduled Task Triggers for JARVIS.
Handles scheduling reminders, battery status polling, idle detection, and log-based pattern suggestion.
"""

import sqlite3
import time
import ctypes
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import psutil

from backend.services.skills.base import BaseSkill, skill_tool
from backend.utils.logger import logger
from backend.config import get_settings
from backend.models.schemas import WSMessage, ResponseMessage


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def get_idle_duration() -> float:
    """Returns the time in seconds since the last keyboard or mouse input on Windows."""
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(lii)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return max(0.0, millis / 1000.0)
    except Exception as e:
        logger.debug("Failed to get idle duration: {}", e)
    return 0.0


class ProactiveSkill(BaseSkill):
    """Enables JARVIS to monitor metrics and execute pre-planned actions in the background."""

    def __init__(self, app_state=None) -> None:
        self.app_state = app_state
        self._settings = get_settings()
        self._db_path = self._settings.data_path / "proactive.db"
        
        # State tracking
        self.last_battery_alert_percent = 100
        self.idle_lock_triggered = False
        self._init_proactive_db()

    def _init_proactive_db(self) -> None:
        """Initialize database for schedules."""
        try:
            self._settings.data_path.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    trigger_time TEXT NOT NULL,
                    recurrence TEXT,
                    completed INTEGER DEFAULT 0
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to initialize proactive db: {}", e)

    # ── Scheduling Tools ───────────────────────────────────────────────────

    @skill_tool(
        name="schedule_reminder",
        description="Schedules a proactive notification/alert to occur at a specific date and time (YYYY-MM-DD HH:MM) or interval.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "The reminder content / title"},
                "trigger_time": {"type": "string", "description": "Time to trigger (YYYY-MM-DD HH:MM)"},
                "recurrence": {"type": "string", "enum": ["none", "daily", "weekly"], "description": "Optional recurring frequency."}
            },
            "required": ["title", "trigger_time"]
        }
    )
    def schedule_reminder(self, title: str, trigger_time: str, recurrence: str = "none") -> str:
        try:
            # Validate input format
            datetime.strptime(trigger_time, "%Y-%m-%d %H:%M")
        except ValueError:
            return "Invalid trigger time format. Please use YYYY-MM-DD HH:MM (e.g. '2026-06-25 15:00')."

        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO schedules (title, trigger_time, recurrence) VALUES (?, ?, ?)",
                (title, trigger_time, recurrence)
            )
            conn.commit()
            conn.close()
            return f"✓ Reminder scheduled: '{title}' for {trigger_time} (Recurrence: {recurrence})."
        except Exception as e:
            return f"Failed to schedule reminder: {e}"

    @skill_tool(
        name="list_reminders",
        description="Lists all scheduled active reminders.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def list_reminders(self) -> str:
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, trigger_time, recurrence, completed FROM schedules WHERE completed = 0")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return "No upcoming reminders found."

            lines = ["⏳ Upcoming Reminders:"]
            for row in rows:
                r_id, title, trigger_time, recurrence, _ = row
                recur_str = f" ({recurrence})" if recurrence and recurrence != "none" else ""
                lines.append(f"[{r_id}] {trigger_time} : **{title}**{recur_str}")
            return "\n".join(lines)
        except Exception as e:
            return f"Failed to list reminders: {e}"

    @skill_tool(
        name="cancel_reminder",
        description="Cancels/deletes a scheduled reminder by its numerical ID.",
        parameters={
            "type": "object",
            "properties": {
                "reminder_id": {"type": "integer", "description": "ID of the reminder to cancel"}
            },
            "required": ["reminder_id"]
        }
    )
    def cancel_reminder(self, reminder_id: int) -> str:
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedules WHERE id = ?", (reminder_id,))
            conn.commit()
            conn.close()
            return f"✓ Cancelled reminder [{reminder_id}]."
        except Exception as e:
            return f"Failed to cancel reminder: {e}"

    # ── Background Worker Checks ───────────────────────────────────────────

    async def check_triggers(self) -> None:
        """Runs periodic checks on battery, idle state, and active schedule reminders."""
        if not self.app_state:
            return

        # 1. Check Schedules
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, trigger_time, recurrence FROM schedules WHERE completed = 0 AND trigger_time <= ?", (now_str,))
            active_alerts = cursor.fetchall()
            
            for alert in active_alerts:
                a_id, title, trigger_time, recurrence = alert
                msg_text = f"Reminder, sir: {title}"
                logger.info("Firing scheduled reminder [{}]: {}", a_id, title)
                
                # Speak alert
                await self._proactive_speak(msg_text)

                if recurrence == "daily":
                    new_time = (datetime.strptime(trigger_time, "%Y-%m-%d %H:%M") + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
                    cursor.execute("UPDATE schedules SET trigger_time = ? WHERE id = ?", (new_time, a_id))
                elif recurrence == "weekly":
                    new_time = (datetime.strptime(trigger_time, "%Y-%m-%d %H:%M") + timedelta(weeks=1)).strftime("%Y-%m-%d %H:%M")
                    cursor.execute("UPDATE schedules SET trigger_time = ? WHERE id = ?", (new_time, a_id))
                else:
                    cursor.execute("UPDATE schedules SET completed = 1 WHERE id = ?", (a_id,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("Schedules proactive check error: {}", e)

        # 2. Check Battery
        try:
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged:
                pct = battery.percent
                # Trigger alert if drops below 20%, but only once per threshold interval
                if pct <= 20 and self.last_battery_alert_percent > 20:
                    self.last_battery_alert_percent = pct
                    await self._proactive_speak(f"Sir, your computer battery is at {pct} percent and discharging. I recommend connecting a power source.")
                elif pct > 20:
                    self.last_battery_alert_percent = pct
            elif battery and battery.power_plugged:
                self.last_battery_alert_percent = 100
        except Exception as e:
            logger.debug("Battery check failed: {}", e)

        # 3. Check System Inactivity / Idle
        try:
            idle_s = get_idle_duration()
            # If idle for more than 30 minutes (1800s), prompt locking
            if idle_s >= 1800 and not self.idle_lock_triggered:
                self.idle_lock_triggered = True
                logger.warning("System has been idle for {:.1f}s. Triggering LockWorkStation.", idle_s)
                # Auto-lock screen
                import ctypes
                ctypes.windll.user32.LockWorkStation()
            elif idle_s < 60:
                self.idle_lock_triggered = False
        except Exception as e:
            logger.debug("Idle checking error: {}", e)

    async def _proactive_speak(self, text: str) -> None:
        """Tells the voice agent to synthesize and broadcast text."""
        voice_agent = getattr(self.app_state, "voice_agent", None)
        manager = getattr(self.app_state, "connection_manager", None)
        
        if voice_agent and manager:
            # Broadcast the text response first
            await manager.broadcast(WSMessage(
                type="response",
                data=ResponseMessage(text=text, conversation_id=None).model_dump()
            ))
            # Synthesize voice and broadcast audio frames
            async for chunk in voice_agent._speak(text):
                await manager.broadcast(chunk)
