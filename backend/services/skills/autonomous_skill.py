"""
Autonomous Skill for FastMCP & Skill Registry integration.
Exposes Phase 18 tools: get_learned_habits, predict_next_tasks, manage_long_term_goals, optimize_agent_prompt.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.autonomous_engine import AutonomousEngineService


class AutonomousSkill(BaseSkill):
    """Skill exposing Phase 18 Autonomous Intelligence tools."""

    name = "AutonomousSkill"
    description = "Workflow habit learning, predictive task execution engine, long-term goal planner, self-improving prompt optimizer."

    def __init__(self, autonomous_service: Optional[AutonomousEngineService] = None):
        self.auto_engine = autonomous_service or AutonomousEngineService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_learned_habits",
                "description": "Get learned user habit patterns and workflow automation suggestions.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "predict_next_tasks",
                "description": "Predict upcoming user tasks based on time-of-day and habits.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "manage_long_term_goals",
                "description": "Add or list long-term goals managed by the Personal AI Project Manager.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["add", "list"]},
                        "title": {"type": "string", "description": "Goal title."}
                    }
                }
            },
            {
                "name": "optimize_agent_prompt",
                "description": "Self-improve and optimize agent system prompts based on feedback.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "base_prompt": {"type": "string", "description": "Base system prompt to optimize."}
                    },
                    "required": ["base_prompt"]
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "get_learned_habits":
            return self.auto_engine.get_learned_habits()
        elif tool_name == "predict_next_tasks":
            return self.auto_engine.predict_next_tasks()
        elif tool_name == "manage_long_term_goals":
            return self.auto_engine.manage_long_term_goals(
                parameters.get("action", "list"),
                parameters.get("title")
            )
        elif tool_name == "optimize_agent_prompt":
            return self.auto_engine.optimize_agent_prompt(parameters.get("base_prompt", ""))
        else:
            raise ValueError(f"Unknown autonomous tool: {tool_name}")
