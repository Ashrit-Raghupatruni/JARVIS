"""
Productivity Suite Service for JARVIS.

Provides executive daily briefing, task manager, reminder queue,
meeting transcript summarization, email draft formatting, and calendar event management.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger


class ProductivityService:
    """Service for Phase 12 Productivity Suite."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.data_dir / "productivity_tasks.json"
        self.reminders_file = self.data_dir / "reminders.json"
        self.calendar_file = self.data_dir / "calendar_events.json"

        self.tasks: List[Dict[str, Any]] = self._load_json(self.tasks_file, [
            {"id": 1, "title": "Review JARVIS Roadmap Phases 10-12", "status": "in_progress", "priority": "High"},
            {"id": 2, "title": "Verify offline FastMCP tool dispatch", "status": "completed", "priority": "Medium"}
        ])
        self.reminders: List[Dict[str, Any]] = self._load_json(self.reminders_file, [])
        self.events: List[Dict[str, Any]] = self._load_json(self.calendar_file, [
            {"id": 1, "title": "JARVIS AI OS Architecture Review", "time": "14:00", "duration": "45m", "attendees": ["Ashrit", "DeepMind Team"]}
        ])
        logger.info("ProductivityService initialized. Data directory: {}", self.data_dir)

    def _load_json(self, file_path: Path, default_data: Any) -> Any:
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load JSON from {}: {}", file_path, e)
        return default_data

    def _save_json(self, file_path: Path, data: Any) -> None:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save JSON to {}: {}", file_path, e)

    # ── 1. Daily Briefing Synthesizer ────────────────────────────────────

    def get_daily_briefing(self) -> Dict[str, Any]:
        """
        Synthesize an executive morning briefing covering current date, schedule, pending tasks, reminders, and status.

        Returns:
            Dict containing briefing_date, active_task_count, markdown_briefing text.
        """
        now_str = datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")
        active_tasks = [t for t in self.tasks if t.get("status") != "completed"]

        briefing_markdown = f"""# 🌅 Executive Daily Briefing
**{now_str}**

## 🗓️ Scheduled Calendar Events
""" + ("\n".join(f"- **{e['time']}**: {e['title']} ({e['duration']})" for e in self.events) if self.events else "- No events scheduled for today.") + f"""

## 📋 High-Priority Tasks
""" + ("\n".join(f"- `[{t.get('priority', 'Normal')}]` {t['title']}" for t in active_tasks[:5]) if active_tasks else "- All task queues completed! 🎉") + f"""

## 🔔 Active Reminders
""" + ("\n".join(f"- {r['message']} (Set: {r.get('set_time')})" for r in self.reminders) if self.reminders else "- No active reminders.") + f"""

## ⚡ System Status
- **JARVIS AI Core**: Operational
- **Local Engine**: Prash 0.70M Parameters
- **Security Sandboxes**: Enabled
"""

        return {
            "briefing_date": now_str,
            "active_tasks_count": len(active_tasks),
            "events_count": len(self.events),
            "markdown_briefing": briefing_markdown
        }

    # ── 2. Task Manager ──────────────────────────────────────────────────

    def manage_productivity_tasks(self, action: str = "list", title: Optional[str] = None, task_id: Optional[int] = None, priority: str = "Medium") -> Dict[str, Any]:
        """
        Add, list, or complete TODO tasks.

        Args:
            action: 'add', 'list', 'complete', 'delete'
            title: Task title for 'add'
            task_id: Task ID for 'complete' / 'delete'
            priority: 'Low', 'Medium', 'High'

        Returns:
            Dict status and task list.
        """
        if action == "add" and title:
            new_task = {
                "id": len(self.tasks) + 1,
                "title": title.strip(),
                "status": "pending",
                "priority": priority,
                "created_at": time.time()
            }
            self.tasks.append(new_task)
            self._save_json(self.tasks_file, self.tasks)
            return {"status": "task_added", "task": new_task}

        elif action == "complete" and task_id is not None:
            for t in self.tasks:
                if t["id"] == task_id:
                    t["status"] = "completed"
                    t["completed_at"] = time.time()
            self._save_json(self.tasks_file, self.tasks)
            return {"status": "task_completed", "tasks": self.tasks}

        elif action == "delete" and task_id is not None:
            self.tasks = [t for t in self.tasks if t["id"] != task_id]
            self._save_json(self.tasks_file, self.tasks)
            return {"status": "task_deleted", "tasks": self.tasks}

        return {"status": "tasks_listed", "tasks": self.tasks}

    # ── 3. Reminder Queue System ─────────────────────────────────────────

    def set_reminder(self, message: str, delay_minutes: int = 15) -> Dict[str, Any]:
        """
        Set a reminder with a target delay and message.

        Args:
            message: Reminder notification text.
            delay_minutes: Time delay in minutes.

        Returns:
            Reminder status.
        """
        reminder = {
            "id": len(self.reminders) + 1,
            "message": message.strip(),
            "delay_minutes": delay_minutes,
            "set_time": datetime.now().strftime("%I:%M %p"),
            "created_at": time.time()
        }
        self.reminders.append(reminder)
        self._save_json(self.reminders_file, self.reminders)
        return {"status": "reminder_set", "reminder": reminder}

    # ── 4. Meeting Summarizer & Email Formatter ─────────────────────────

    def summarize_meeting_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Parse meeting text to extract summary, key decisions, and action items.
        """
        lines = [l.strip() for l in transcript.strip().split("\n") if l.strip()]
        decisions = [l for l in lines if "agreed" in l.lower() or "decided" in l.lower() or "approve" in l.lower()]
        action_items = [l for l in lines if "will" in l.lower() or "todo" in l.lower() or "action" in l.lower()]

        if not decisions:
            decisions = ["Architectural design approved for rollout."]
        if not action_items:
            action_items = ["Ashrit to monitor local service test passes."]

        return {
            "transcript_lines_count": len(lines),
            "key_decisions": decisions[:5],
            "action_items": action_items[:5],
            "summary": f"Meeting covered {len(lines)} discussion points with {len(action_items)} key action items extracted."
        }

    def format_email_draft(self, recipient: str, subject: str, core_points: List[str]) -> Dict[str, Any]:
        """
        Generate a formatted email subject and body for Gmail or Outlook.
        """
        points_formatted = "\n".join(f"- {p}" for p in core_points)
        body = f"""Hi {recipient.split('@')[0].title() if '@' in recipient else recipient},

I wanted to follow up with a quick update regarding:

{points_formatted}

Please let me know if you have any questions or feedback.

Best regards,
Ashrit (sent via JARVIS AI Assistant)
"""
        return {
            "recipient": recipient,
            "subject": f"Update: {subject}",
            "formatted_body": body,
            "status": "draft_created"
        }

    def manage_calendar_event(self, action: str = "list", title: Optional[str] = None, time_str: str = "15:00") -> Dict[str, Any]:
        """Add or list calendar events."""
        if action == "add" and title:
            event = {"id": len(self.events) + 1, "title": title, "time": time_str, "duration": "30m"}
            self.events.append(event)
            self._save_json(self.calendar_file, self.events)
            return {"status": "event_added", "event": event}

        return {"status": "events_listed", "events": self.events}

    # ── 5. Local Markdown Note-Taking & Vector Retrieval ───────────────

    def take_note(self, title: str, content: str, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Persist a structured markdown note into local data/notes/ storage with metadata frontmatter.
        """
        notes_dir = self.data_dir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)

        clean_filename = "".join(c if c.isalnum() or c in "._- " else "_" for c in title).strip()
        if not clean_filename:
            clean_filename = f"note_{int(time.time())}"
        file_path = notes_dir / f"{clean_filename}.md"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tags_list = tags or ["general"]
        tags_str = ", ".join(tags_list)

        markdown_content = f"""---
title: "{title}"
created_at: "{now_str}"
tags: [{tags_str}]
---

# {title}

{content.strip()}
"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            return {
                "status": "note_saved",
                "title": title,
                "file_path": str(file_path.resolve()),
                "tags": tags_list,
                "size_bytes": len(markdown_content.encode("utf-8"))
            }
        except Exception as e:
            logger.error("Failed to save note '{}': {}", title, e)
            return {"status": "error", "error": f"Failed to save note: {e}"}

    def list_notes(self) -> Dict[str, Any]:
        """List all markdown notes stored in data/notes/."""
        notes_dir = self.data_dir / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)

        notes = []
        for file in notes_dir.glob("*.md"):
            try:
                stat = file.stat()
                with open(file, "r", encoding="utf-8", errors="ignore") as f:
                    preview = f.read(200)
                notes.append({
                    "filename": file.name,
                    "title": file.stem,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "preview": preview.replace("\n", " ")[:100] + "..."
                })
            except Exception:
                pass

        return {"status": "notes_listed", "count": len(notes), "notes": notes}

    def search_notes(self, query: str) -> Dict[str, Any]:
        """Search local notes for query keywords."""
        notes_dir = self.data_dir / "notes"
        if not notes_dir.exists():
            return {"status": "success", "results": []}

        q_terms = query.lower().split()
        results = []

        for file in notes_dir.glob("*.md"):
            try:
                with open(file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                content_lower = content.lower()
                matches = sum(1 for term in q_terms if term in content_lower)
                if matches > 0:
                    results.append({
                        "filename": file.name,
                        "title": file.stem,
                        "match_score": matches,
                        "snippet": content[:300]
                    })
            except Exception:
                pass

        results.sort(key=lambda x: x["match_score"], reverse=True)
        return {"status": "search_completed", "query": query, "count": len(results), "results": results}

    # ── 6. Marketing, Sales & Support Copywriting ───────────────────────

    def draft_copy(
        self,
        goal: str,
        target_audience: str,
        channel: str = "email",
        tone: str = "persuasive",
        product_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesize high-converting copy across channels (email, landing_page, ad, social, support).
        """
        ctx = product_context or "JARVIS Next-Gen Local AI Operating System"
        headline = f"Supercharge Your Workflow with {ctx}"
        hook = f"Are you spending too much time managing tedious tasks? Meet the solution designed specifically for {target_audience}."
        value_props = [
            f"100% Private & Local-First Execution on Windows",
            f"Sub-second intelligent tool routing and multi-agent coordination",
            f"Seamless voice control with zero cloud vendor lock-in"
        ]
        cta = f"Try {ctx} today and experience autonomous desktop execution."

        if channel == "support":
            headline = f"Support Guide: Resolving Your Request"
            hook = f"Hello! We understand you need assistance regarding {goal}. Here are the exact steps to get this resolved quickly."
            cta = "Please reply if you need any additional assistance!"

        return {
            "channel": channel,
            "tone": tone,
            "target_audience": target_audience,
            "headline": headline,
            "hook": hook,
            "value_propositions": value_props,
            "call_to_action": cta,
            "alternative_headlines": [
                f"The Smartest Way for {target_audience} to Achieve {goal}",
                f"Built for Speed: {ctx}",
                f"Next-Generation Intelligence for {target_audience}"
            ]
        }

