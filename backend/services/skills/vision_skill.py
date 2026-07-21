"""
Vision Skill for FastMCP & Skill Registry integration.
Provides tools for accessibility tree inspection, UI element grounding, multi-monitor mapping, and visual verification.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.vision_service import VisionService


class VisionSkill(BaseSkill):
    """Skill exposing Phase 7 Vision-Based Computer Use tools."""

    name = "VisionSkill"
    description = "Vision intelligence, accessibility tree parsing, UI grounding, and visual verification."

    def __init__(self, vision_service: Optional[VisionService] = None):
        self.vision_service = vision_service or VisionService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "inspect_accessibility_tree",
                "description": "Inspect native UI control elements and accessibility tree for target window.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hwnd": {"type": "integer", "description": "Optional window handle (HWND)."}
                    }
                }
            },
            {
                "name": "get_window_hierarchy",
                "description": "Enumerate visible top-level windows and child window hierarchies.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "locate_visual_element",
                "description": "Ground a target UI element label to screen coordinates [x, y].",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Element description (e.g. 'submit button', 'close icon')."}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_multi_monitor_layout",
                "description": "Get connected display monitors, primary display, and work area bounds.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "inspect_accessibility_tree":
            return self.vision_service.get_accessibility_tree(parameters.get("hwnd"))
        elif tool_name == "get_window_hierarchy":
            return self.vision_service.get_window_hierarchy()
        elif tool_name == "locate_visual_element":
            return self.vision_service.ground_element_coordinates(parameters.get("query", ""))
        elif tool_name == "get_multi_monitor_layout":
            return self.vision_service.get_multi_monitor_layout()
        else:
            raise ValueError(f"Unknown vision tool: {tool_name}")
