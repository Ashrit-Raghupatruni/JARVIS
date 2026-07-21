"""
Automation Skill for FastMCP & Skill Registry integration.
Exposes Phase 8 Desktop Automation tools: macro recording, workflow playback, window layouts, and clipboard tools.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.desktop_automation import DesktopAutomationService


class AutomationSkill(BaseSkill):
    """Skill exposing Phase 8 Desktop Automation tools."""

    name = "AutomationSkill"
    description = "Workflow recorder & macro playback, window grid layout manager, clipboard intelligence, and directory watcher."

    def __init__(self, automation_service: Optional[DesktopAutomationService] = None):
        self.automation_service = automation_service or DesktopAutomationService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "start_workflow_recording",
                "description": "Start recording user workflow macro steps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name for recorded workflow."}
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "stop_workflow_recording",
                "description": "Stop current workflow recording and save macro to JSON.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "playback_workflow",
                "description": "Play back a stored workflow macro.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name or filename of workflow macro to run."}
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "list_workflows",
                "description": "List all saved workflow macros.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "arrange_windows_layout",
                "description": "Tile, split, or snap visible desktop windows into grid layouts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "layout_preset": {
                            "type": "string",
                            "enum": ["split_left_right", "quad_tile", "center", "tile_horizontal"],
                            "description": "Target grid layout configuration."
                        },
                        "window_titles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of window titles to arrange."
                        }
                    }
                }
            },
            {
                "name": "get_clipboard_intelligence",
                "description": "Read clipboard content, auto-detect data type (URL, JSON, Code, Path), and view clipboard history.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "check_folder_changes",
                "description": "Check a target directory for added, modified, or removed files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "folder_path": {"type": "string", "description": "Directory path to inspect."}
                    },
                    "required": ["folder_path"]
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "start_workflow_recording":
            return self.automation_service.start_workflow_recording(parameters.get("name", ""))
        elif tool_name == "stop_workflow_recording":
            return self.automation_service.stop_workflow_recording()
        elif tool_name == "playback_workflow":
            return self.automation_service.playback_workflow(parameters.get("name", ""))
        elif tool_name == "list_workflows":
            return self.automation_service.list_workflows()
        elif tool_name == "arrange_windows_layout":
            return self.automation_service.arrange_windows_layout(
                parameters.get("layout_preset", "split_left_right"),
                parameters.get("window_titles")
            )
        elif tool_name == "get_clipboard_intelligence":
            return self.automation_service.get_clipboard_content()
        elif tool_name == "check_folder_changes":
            return self.automation_service.check_folder_changes(parameters.get("folder_path", ""))
        else:
            raise ValueError(f"Unknown automation tool: {tool_name}")
