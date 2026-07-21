"""
Plugin SDK & Manifest definitions for JARVIS Plugin Ecosystem.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    """Manifest data model for JARVIS plugins (manifest.json)."""

    name: str = Field(..., description="Unique plugin name")
    version: str = Field("1.0.0", description="Semantic version string")
    author: str = Field("Unknown", description="Plugin author name or handle")
    description: str = Field("", description="Short plugin description")
    entry_point: str = Field("main.py", description="Main Python entry point file")
    permissions: List[str] = Field(default_factory=list, description="Required permissions (e.g. file_read, terminal_exec, network)")


class BasePlugin:
    """Base class that all JARVIS third-party plugins inherit from."""

    def __init__(self, manifest: PluginManifest, plugin_dir: Optional[str] = None):
        self.manifest = manifest
        self.plugin_dir = plugin_dir
        self.is_enabled = True

    def initialize(self) -> None:
        """Called when plugin is loaded into JARVIS process."""
        pass

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return list of tool definitions provided by this plugin."""
        return []

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute a tool provided by this plugin."""
        raise NotImplementedError("Plugin tool execution not implemented.")
