"""
Skill Registry to discover, load, and dispatch modular JARVIS skills.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.utils.logger import logger


class SkillRegistry:
    """Registry that holds all active skills and dispatches tool executions."""

    def __init__(self, **kwargs) -> None:
        self.context = kwargs
        self.skills: Dict[str, BaseSkill] = {}
        self.load_skills()

    def load_skills(self) -> None:
        """Instantiates and registers all available skills."""
        logger.info("Initializing skill registry...")

        # Dynamic/Manual skill imports to avoid circular dependencies
        try:
            # File Skill
            from backend.services.skills.file_skill import FileSkill
            file_skill = FileSkill(
                automation_service=self.context.get("automation_service"),
                memory_service=self.context.get("memory_service")
            )
            self.register_skill(file_skill)
        except Exception as e:
            logger.error("Failed to load FileSkill: {}", e)

        try:
            # Communication Skill
            from backend.services.skills.communication_skill import CommunicationSkill
            comm_skill = CommunicationSkill(
                browser_service=self.context.get("browser_service"),
                memory_service=self.context.get("memory_service")
            )
            self.register_skill(comm_skill)
        except Exception as e:
            logger.error("Failed to load CommunicationSkill: {}", e)

        try:
            # System Intelligence Skill
            from backend.services.skills.system_skill import SystemSkill
            sys_skill = SystemSkill(
                automation_service=self.context.get("automation_service")
            )
            self.register_skill(sys_skill)
        except Exception as e:
            logger.error("Failed to load SystemSkill: {}", e)

        try:
            # App Control Skill
            from backend.services.skills.app_control_skill import AppControlSkill
            app_control = AppControlSkill(
                automation_service=self.context.get("automation_service")
            )
            self.register_skill(app_control)
        except Exception as e:
            logger.error("Failed to load AppControlSkill: {}", e)

        try:
            # Context Skill
            from backend.services.skills.context_skill import ContextSkill
            context_skill = ContextSkill(
                automation_service=self.context.get("automation_service"),
                memory_service=self.context.get("memory_service")
            )
            self.register_skill(context_skill)
        except Exception as e:
            logger.error("Failed to load ContextSkill: {}", e)

        try:
            # Agent Skill (Phase P7)
            from backend.services.skills.agent_skill import AgentSkill
            agent_skill = AgentSkill(
                planner_agent=self.context.get("planner_agent")
            )
            self.register_skill(agent_skill)
        except Exception as e:
            logger.error("Failed to load AgentSkill: {}", e)

        logger.info("✓ Skill registry initialization complete. Registered skills: {}", list(self.skills.keys()))

    def register_skill(self, skill: BaseSkill) -> None:
        """Register a skill instance in the registry."""
        self.skills[skill.name] = skill
        logger.debug("Registered skill: {}", skill.name)

    def get_all_tool_definitions(self) -> List[Dict[str, Any]]:
        """Collects all tool definitions from all registered skills."""
        all_tools = []
        for skill in self.skills.values():
            all_tools.extend(skill.get_tool_definitions())
        return all_tools

    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Finds the skill owning the tool and executes it."""
        for skill in self.skills.values():
            definitions = skill.get_tool_definitions()
            for d in definitions:
                if d["function"]["name"] == tool_name:
                    logger.info("Dispatching execution of '{}' to skill '{}'", tool_name, skill.name)
                    return await skill.execute(tool_name, args)
        raise ValueError(f"No registered skill handles the tool '{tool_name}'")
