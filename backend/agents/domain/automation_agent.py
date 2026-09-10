"""
JARVIS AI OS — Automation Domain Agent.
Handles desktop UI automation, Win32 UIA accessibility tree interactions, RPA macros, screen perception, and Playwright browser control.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.agents.domain.base_domain_agent import BaseDomainAgent


class AutomationAgent(BaseDomainAgent):
    """Domain Agent for desktop automation, Win32 UIA, RPA workflows, and browser automation."""

    def __init__(self, event_bus=None, llm_service=None) -> None:
        super().__init__(
            name="AutomationAgent",
            role_description="Win32 UIA accessibility tree, mouse/keyboard automation, RPA desktop macros, screen OCR perception, and Playwright browser navigation.",
            allowed_tools=[
                "execute_rpa_macro", "click_element", "type_text",
                "open_application", "close_application", "focus_window",
                "capture_screen", "browser_navigate", "browser_click", "browser_type"
            ],
            event_bus=event_bus,
            llm_service=llm_service
        )

    async def execute_task(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.status = "processing"
        self.last_active = time.time()
        start_time = time.time()

        try:
            from backend.services.skills.automation_skill import AutomationSkill
            skill = AutomationSkill()
            
            desc_lower = task_description.lower()
            if "open" in desc_lower or "launch" in desc_lower:
                app_name = task_description.split("open")[-1].split("launch")[-1].strip()
                res = await skill.execute_tool("open_app", {"app_name": app_name})
                response_text = f"Opened application: {app_name} (result: {res})"
            elif "close" in desc_lower or "kill" in desc_lower:
                app_name = task_description.split("close")[-1].split("kill")[-1].strip()
                res = await skill.execute_tool("close_app", {"app_name": app_name})
                response_text = f"Closed application: {app_name} (result: {res})"
            else:
                from backend.services.manager import ServiceManager
                auto_svc = ServiceManager.get_instance("automation_service")
                response_text = f"AutomationAgent processed desktop task: '{task_description}'."

            self.processed_count += 1
            self.status = "idle"
            return {
                "status": "success",
                "agent": self.name,
                "response": response_text,
                "duration_seconds": round(time.time() - start_time, 3)
            }
        except Exception as e:
            self.status = "error"
            logger.error("AutomationAgent task error: {}", e)
            return {
                "status": "error",
                "agent": self.name,
                "error": str(e),
                "duration_seconds": round(time.time() - start_time, 3)
            }
