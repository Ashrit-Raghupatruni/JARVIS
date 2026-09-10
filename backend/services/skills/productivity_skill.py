"""
Productivity Skill for FastMCP & Skill Registry integration.
Exposes tools: daily briefing, task manager, reminder queue, meeting summarizer,
email drafter, calendar manager, local markdown note-taking, and marketing/sales copywriting.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.productivity_service import ProductivityService


class ProductivitySkill(BaseSkill):
    """Skill exposing Productivity Suite, Note-Taking, and Copywriting tools."""

    name = "ProductivitySkill"
    description = "Executive briefing, tasks, reminders, meeting summarizer, email drafter, note-taking, and marketing copy drafting."

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
            },
            {
                "name": "take_note",
                "description": "Save a structured markdown note into local data/notes/ storage with tags and metadata.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Title of note."},
                        "content": {"type": "string", "description": "Markdown body content."},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of tags."
                        }
                    },
                    "required": ["title", "content"]
                }
            },
            {
                "name": "list_notes",
                "description": "List all markdown notes stored in data/notes/ with modification dates and previews.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "search_notes",
                "description": "Search local markdown notes for keywords and terms.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query terms."}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "draft_copy",
                "description": "Generate high-converting marketing, sales, ad, social, or customer support copy.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string", "description": "Primary goal or topic of the copy."},
                        "target_audience": {"type": "string", "description": "Target demographic or persona."},
                        "channel": {"type": "string", "enum": ["email", "landing_page", "social", "ad", "support"]},
                        "tone": {"type": "string", "description": "Tone preset (e.g. persuasive, professional, urgent)."},
                        "product_context": {"type": "string", "description": "Optional product/service name or description."}
                    },
                    "required": ["goal", "target_audience"]
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
        elif tool_name == "take_note":
            return self.productivity_service.take_note(
                parameters.get("title", ""),
                parameters.get("content", ""),
                parameters.get("tags")
            )
        elif tool_name == "list_notes":
            return self.productivity_service.list_notes()
        elif tool_name == "search_notes":
            return self.productivity_service.search_notes(parameters.get("query", ""))
        elif tool_name == "draft_copy":
            return self.productivity_service.draft_copy(
                parameters.get("goal", ""),
                parameters.get("target_audience", ""),
                channel=parameters.get("channel", "email"),
                tone=parameters.get("tone", "persuasive"),
                product_context=parameters.get("product_context")
            )
        else:
            raise ValueError(f"Unknown productivity tool: {tool_name}")
