"""
JARVIS AI OS — Base Domain Agent Interface.
Defines standard lifecycle, tool execution scope, and event bus communication for domain agents.
"""

from __future__ import annotations

import uuid
import time
import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger


class BaseDomainAgent:
    """Abstract Base Class for all JARVIS Domain Agents."""

    def __init__(
        self,
        name: str,
        role_description: str,
        allowed_tools: Optional[List[str]] = None,
        event_bus=None,
        llm_service=None
    ) -> None:
        self.name = name
        self.role_description = role_description
        self.allowed_tools = allowed_tools or []
        self.event_bus = event_bus
        self.llm_service = llm_service
        self.agent_id = f"ag_{name.lower()}_{uuid.uuid4().hex[:6]}"
        self.status = "idle"  # idle | processing | error | offline
        self.processed_count = 0
        self.last_active = time.time()

    def _get_llm(self) -> Any:
        if self.llm_service is not None:
            return self.llm_service
        try:
            from backend.services.manager import ServiceManager
            self.llm_service = ServiceManager.get_instance("llm_service")
        except Exception:
            pass
        return self.llm_service

    async def execute_task(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a domain task. To be implemented by specialized domain agents."""
        raise NotImplementedError(f"Agent '{self.name}' must implement execute_task()")

    async def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool within the domain agent's scope via ToolRegistry."""
        from backend.services.tool_registry import ToolRegistry
        registry = ToolRegistry()
        return await registry.execute_tool(tool_name, params)

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role_description,
            "status": self.status,
            "processed_count": self.processed_count,
            "last_active": self.last_active,
            "allowed_tools_count": len(self.allowed_tools)
        }
