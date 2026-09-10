"""
JARVIS AI OS — General Domain Agent.
Handles conversation, MCU personality tone, memory recall, note-taking, copywriting, and general system controls.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.agents.domain.base_domain_agent import BaseDomainAgent


class GeneralAgent(BaseDomainAgent):
    """Domain Agent for conversational reasoning, memory recall, note-taking, and system controls."""

    def __init__(self, event_bus=None, llm_service=None) -> None:
        super().__init__(
            name="GeneralAgent",
            role_description="General reasoning, natural language conversation, memory recall, notes, and system controls.",
            allowed_tools=[
                "take_note", "list_notes", "search_notes", "draft_copy",
                "summarize_content", "transform_style", "generate_audio_effect",
                "system_status", "volume_control", "manage_window"
            ],
            event_bus=event_bus,
            llm_service=llm_service
        )

    async def execute_task(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.status = "processing"
        self.last_active = time.time()
        start_time = time.time()

        try:
            llm = self._get_llm()
            system_prompt = (
                "You are JARVIS, a sophisticated and witty AI assistant with Tony Stark's Marvel J.A.R.V.I.S. personality. "
                "Be polite, precise, highly competent, and concise (1-3 sentences by default)."
            )

            if llm and hasattr(llm, "generate_response"):
                response_text = await llm.generate_response(prompt=task_description, system_prompt=system_prompt)
            elif llm and hasattr(llm, "simple_completion"):
                response_text = await llm.simple_completion(prompt=f"{system_prompt}\n\nUser: {task_description}\nJARVIS:")
            else:
                response_text = f"JARVIS GeneralAgent online. Understood: '{task_description}'."

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
            logger.error("GeneralAgent task error: {}", e)
            return {
                "status": "error",
                "agent": self.name,
                "error": str(e),
                "duration_seconds": round(time.time() - start_time, 3)
            }
