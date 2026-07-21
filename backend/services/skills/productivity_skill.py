"""
Productivity Skill for FastMCP & Skill Registry integration.
Exposes Phase 12 tools: daily briefing, task manager, reminder queue, meeting summarizer, email drafter, calendar manager.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.productivity_service import ProductivityService


class ProductivitySkill(BaseSkill):
    """Skill exposing Phase 12 Productivity Suite tools."""

    name = "ProductivitySkill"
    description = "Executive daily briefing synthesizer, TODO task manager, reminder queue, meeting transcript summarizer, email drafter, calendar event manager."

    def __init__(self, productivity_service: Optional[ProductivityService] = None):
        self.productivity_service = productivity_service or ProductivityService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_daily_briefing",
                "description": "Synthesize an executive morning briefing covering date, schedule, pending tasks, reminders, and status.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "manage_productivity_tasks",
                "description": "Add, list, complete, or delete TODO tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["add", "list", "complete", "delete"]},
                        "title": {"type": "string", "description": "Task title for 'add'."},
                        "task_id": {"type": "integer", "description": "Task ID for 'complete' / 'delete'."},
                        "priority": {"type": "string", "enum": ["Low", "Medium", "High"]}
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "set_reminder",
                "description": "Set a reminder notification with target delay minutes and message.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Reminder text."},
                        "delay_minutes": {"type": "integer", "description": "Delay in minutes."}
                    },
                    "required": ["message"]
                }
            },
            {
                "name": "summarize_meeting_transcript",
                "description": "Parse meeting transcript text to extract summary, key decisions, and action items.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "transcript": {"type": "string", "description": "Meeting transcript text."}
                    },
                    "required": ["transcript"]
                }
            },
            {
                "name": "format_email_draft",
                "description": "Generate a formatted email subject and body for Gmail or Outlook.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string", "description": "Recipient name or email address."},
                        "subject": {"type": "string", "description": "Subject topic."},
                        "core_points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key bullet points to include."
                        }
                    },
                    "required": ["recipient", "subject", "core_points"]
                }
            },
            {
                "name": "manage_calendar_event",
                "description": "Add or list calendar events.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["add", "list"]},
                        "title": {"type": "string", "description": "Event title."},
                        "time_str": {"type": "string", "description": "Event time (e.g. '15:00')."}
                    }
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "get_daily_briefing":
            return self.productivity_service.get_daily_briefing()
        elif tool_name == "manage_productivity_tasks":
            return self.productivity_service.manage_productivity_tasks(
                parameters.get("action", "list"),
                parameters.get("title"),
                parameters.get("task_id"),
                parameters.get("priority", "Medium")
            )
        elif tool_name == "set_reminder":
            return self.productivity_service.set_reminder(
                parameters.get("message", ""),
                parameters.get("delay_minutes", 15)
            )
        elif tool_name == "summarize_meeting_transcript":
            return self.productivity_service.summarize_meeting_transcript(parameters.get("transcript", ""))
        elif tool_name == "format_email_draft":
            return self.productivity_service.format_email_draft(
                parameters.get("recipient", ""),
                parameters.get("subject", ""),
                parameters.get("core_points", [])
            )
        elif tool_name == "manage_calendar_event":
            return self.productivity_service.manage_calendar_event(
                parameters.get("action", "list"),
                parameters.get("title"),
                parameters.get("time_str", "15:00")
            )
        else:
            raise ValueError(f"Unknown productivity tool: {tool_name}")
