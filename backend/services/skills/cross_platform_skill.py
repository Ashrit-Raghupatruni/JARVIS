"""
Cross-Platform Skill for FastMCP & Skill Registry integration.
Exposes Phase 16 tools: get_platform_compatibility, pair_companion_device, sync_cross_device_state, list_paired_devices.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.cross_platform import CrossPlatformService


class CrossPlatformSkill(BaseSkill):
    """Skill exposing Phase 16 Cross-Platform Compatibility & Device Sync tools."""

    name = "CrossPlatformSkill"
    description = "OS compatibility detector, Android/iOS mobile companion app pairing, cross-device state sync broker."

    def __init__(self, cross_platform_service: Optional[CrossPlatformService] = None):
        self.xp_service = cross_platform_service or CrossPlatformService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_platform_compatibility",
                "description": "Get operating system details and feature compatibility matrix.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "pair_companion_device",
                "description": "Pair an Android or iOS companion app device.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_name": {"type": "string", "description": "Device name or model."},
                        "device_platform": {"type": "string", "enum": ["Android", "iOS", "Linux", "macOS"]}
                    },
                    "required": ["device_name"]
                }
            },
            {
                "name": "sync_cross_device_state",
                "description": "Synchronize clipboard or memory state to a companion device.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string", "description": "Paired device ID."},
                        "payload_type": {"type": "string", "description": "clipboard, memory, tasks"}
                    },
                    "required": ["device_id"]
                }
            },
            {
                "name": "list_paired_devices",
                "description": "List all paired devices.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "get_platform_compatibility":
            return self.xp_service.get_platform_compatibility()
        elif tool_name == "pair_companion_device":
            return self.xp_service.pair_companion_device(
                parameters.get("device_name", ""),
                parameters.get("device_platform", "Android")
            )
        elif tool_name == "sync_cross_device_state":
            return self.xp_service.sync_cross_device_state(
                parameters.get("device_id", ""),
                parameters.get("payload_type", "clipboard")
            )
        elif tool_name == "list_paired_devices":
            return self.xp_service.list_paired_devices()
        else:
            raise ValueError(f"Unknown cross-platform tool: {tool_name}")
