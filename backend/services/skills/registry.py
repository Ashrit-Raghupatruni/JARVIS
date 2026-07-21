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

        try:
            # News & Monitor & Research Skill (Ported from Friday/OpenJarvis)
            from backend.services.skills.news_skill import NewsSkill
            news_skill = NewsSkill(
                browser_service=self.context.get("browser_service"),
                automation_service=self.context.get("automation_service"),
                memory_service=self.context.get("memory_service")
            )
            self.register_skill(news_skill)
        except Exception as e:
            logger.error("Failed to load NewsSkill: {}", e)

        try:
            # Phase 7 Vision Skill
            from backend.services.skills.vision_skill import VisionSkill
            vision_skill = VisionSkill(
                vision_service=self.context.get("vision_service")
            )
            self.register_skill(vision_skill)
        except Exception as e:
            logger.error("Failed to load VisionSkill: {}", e)

        try:
            # Phase 8 Desktop Automation Skill
            from backend.services.skills.automation_skill import AutomationSkill
            auto_skill = AutomationSkill(
                automation_service=self.context.get("desktop_automation_service")
            )
            self.register_skill(auto_skill)
        except Exception as e:
            logger.error("Failed to load AutomationSkill: {}", e)

        try:
            # Phase 9 Developer Assistant Skill
            from backend.services.skills.developer_skill import DeveloperSkill
            dev_skill = DeveloperSkill(
                dev_service=self.context.get("developer_assistant_service")
            )
            self.register_skill(dev_skill)
        except Exception as e:
            logger.error("Failed to load DeveloperSkill: {}", e)

        try:
            # Phase 10 Research Skill
            from backend.services.skills.research_skill import ResearchSkill
            research_skill = ResearchSkill(
                research_service=self.context.get("research_service")
            )
            self.register_skill(research_skill)
        except Exception as e:
            logger.error("Failed to load ResearchSkill: {}", e)

        try:
            # Phase 11 Voice Intelligence Skill
            from backend.services.skills.voice_skill import VoiceSkill
            voice_intelligence_skill = VoiceSkill(
                voice_intelligence_service=self.context.get("voice_intelligence_service")
            )
            self.register_skill(voice_intelligence_skill)
        except Exception as e:
            logger.error("Failed to load VoiceSkill: {}", e)

        try:
            # Phase 12 Productivity Skill
            from backend.services.skills.productivity_skill import ProductivitySkill
            productivity_skill = ProductivitySkill(
                productivity_service=self.context.get("productivity_service")
            )
            self.register_skill(productivity_skill)
        except Exception as e:
            logger.error("Failed to load ProductivitySkill: {}", e)

        try:
            # Phase 13 Plugin Skill
            from backend.services.skills.plugin_skill import PluginSkill
            plugin_skill = PluginSkill(
                plugin_manager=self.context.get("plugin_manager")
            )
            self.register_skill(plugin_skill)
        except Exception as e:
            logger.error("Failed to load PluginSkill: {}", e)

        try:
            # Phase 14 UI Skill
            from backend.services.skills.ui_skill import UISkill
            ui_skill = UISkill()
            self.register_skill(ui_skill)
        except Exception as e:
            logger.error("Failed to load UISkill: {}", e)

        try:
            # Phase 15 Observability Skill
            from backend.services.skills.observability_skill import ObservabilitySkill
            obs_skill = ObservabilitySkill()
            self.register_skill(obs_skill)
        except Exception as e:
            logger.error("Failed to load ObservabilitySkill: {}", e)

        try:
            # Phase 16 Cross Platform Skill
            from backend.services.skills.cross_platform_skill import CrossPlatformSkill
            xp_skill = CrossPlatformSkill()
            self.register_skill(xp_skill)
        except Exception as e:
            logger.error("Failed to load CrossPlatformSkill: {}", e)

        try:
            # Phase 17 Deployment Skill
            from backend.services.skills.deployment_skill import DeploymentSkill
            dep_skill = DeploymentSkill()
            self.register_skill(dep_skill)
        except Exception as e:
            logger.error("Failed to load DeploymentSkill: {}", e)

        try:
            # Phase 18 Autonomous Skill
            from backend.services.skills.autonomous_skill import AutonomousSkill
            auto_skill = AutonomousSkill()
            self.register_skill(auto_skill)
        except Exception as e:
            logger.error("Failed to load AutonomousSkill: {}", e)

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
