"""
Vision Skill for FastMCP & Skill Registry integration.
Provides tools for accessibility tree inspection, UI element grounding, multi-monitor mapping,
visual verification, local object recognition, and grounded image captioning.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.vision_service import VisionService


class VisionSkill(BaseSkill):
    """Skill exposing Vision-Based Computer Use, Object Detection, and Scene Captioning tools."""

    name = "VisionSkill"
    description = "Vision intelligence, accessibility tree parsing, UI grounding, object recognition, and grounded image captioning."

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
            },
            {
                "name": "detect_objects_in_image",
                "description": "Detect visual elements, UI containers, faces, and bounding boxes in an image or current desktop screen.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string", "description": "Optional file path to local image."},
                        "confidence_threshold": {"type": "number", "description": "Detection confidence threshold (0.0 to 1.0)."}
                    }
                }
            },
            {
                "name": "generate_image_caption",
                "description": "Generate grounded visual description and structure caption for an image or desktop screen.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string", "description": "Optional file path to local image."},
                        "style": {"type": "string", "enum": ["descriptive", "concise", "technical"]}
                    }
                }
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
        elif tool_name == "detect_objects_in_image":
            return self.vision_service.detect_objects_in_image(
                image_path=parameters.get("image_path"),
                confidence_threshold=parameters.get("confidence_threshold", 0.4)
            )
        elif tool_name == "generate_image_caption":
            return self.vision_service.generate_image_caption(
                image_path=parameters.get("image_path"),
                style=parameters.get("style", "descriptive")
            )
        else:
            raise ValueError(f"Unknown vision tool: {tool_name}")
