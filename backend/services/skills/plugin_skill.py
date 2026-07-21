"""
Plugin Skill for FastMCP & Skill Registry integration.
Exposes Phase 13 tools: install_plugin, uninstall_plugin, list_plugins, enable_plugin, disable_plugin, inspect_plugin_permissions.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.plugin_manager import PluginManager


class PluginSkill(BaseSkill):
    """Skill exposing Phase 13 Plugin Marketplace tools."""

    name = "PluginSkill"
    description = "Plugin Marketplace SDK, plugin installer, uninstaller, permission inspector, and plugin enabler."

    def __init__(self, plugin_manager: Optional[PluginManager] = None):
        self.plugin_manager = plugin_manager or PluginManager()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "install_plugin",
                "description": "Install a new plugin into the JARVIS plugin ecosystem.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plugin_name": {"type": "string", "description": "Unique plugin name."},
                        "source_path": {"type": "string", "description": "Optional source folder or zip path."}
                    },
                    "required": ["plugin_name"]
                }
            },
            {
                "name": "uninstall_plugin",
                "description": "Uninstall a plugin by name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plugin_name": {"type": "string", "description": "Plugin name to uninstall."}
                    },
                    "required": ["plugin_name"]
                }
            },
            {
                "name": "list_installed_plugins",
                "description": "List all installed plugins and their status.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "enable_plugin",
                "description": "Enable an installed plugin.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plugin_name": {"type": "string", "description": "Plugin name."}
                    },
                    "required": ["plugin_name"]
                }
            },
            {
                "name": "disable_plugin",
                "description": "Disable an installed plugin.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plugin_name": {"type": "string", "description": "Plugin name."}
                    },
                    "required": ["plugin_name"]
                }
            },
            {
                "name": "inspect_plugin_permissions",
                "description": "Inspect security permissions requested by a plugin.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plugin_name": {"type": "string", "description": "Plugin name."}
                    },
                    "required": ["plugin_name"]
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "install_plugin":
            return self.plugin_manager.install_plugin(
                parameters.get("plugin_name", ""),
                parameters.get("source_path")
            )
        elif tool_name == "uninstall_plugin":
            return self.plugin_manager.uninstall_plugin(parameters.get("plugin_name", ""))
        elif tool_name == "list_installed_plugins":
            return self.plugin_manager.scan_installed_plugins()
        elif tool_name == "enable_plugin":
            return self.plugin_manager.enable_plugin(parameters.get("plugin_name", ""))
        elif tool_name == "disable_plugin":
            return self.plugin_manager.disable_plugin(parameters.get("plugin_name", ""))
        elif tool_name == "inspect_plugin_permissions":
            return self.plugin_manager.inspect_plugin_permissions(parameters.get("plugin_name", ""))
        else:
            raise ValueError(f"Unknown plugin tool: {tool_name}")
