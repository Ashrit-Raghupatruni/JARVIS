"""
JARVIS AI OS — Domain Agents Package.
Exports the 4 core domain agents: GeneralAgent, ResearchAgent, DeveloperAgent, and AutomationAgent.
"""

from backend.agents.domain.base_domain_agent import BaseDomainAgent
from backend.agents.domain.general_agent import GeneralAgent
from backend.agents.domain.research_agent import ResearchAgent
from backend.agents.domain.developer_agent import DeveloperAgent
from backend.agents.domain.automation_agent import AutomationAgent

DOMAIN_AGENTS = {
    "GeneralAgent": GeneralAgent,
    "ResearchAgent": ResearchAgent,
    "DeveloperAgent": DeveloperAgent,
    "AutomationAgent": AutomationAgent,
    # Aliases for backward compatibility with earlier role strings
    "CodeAgent": DeveloperAgent,
    "SecurityAgent": DeveloperAgent,
    "ConversationAgent": GeneralAgent,
    "PlanningAgent": GeneralAgent,
    "VisionAgent": AutomationAgent,
    "DesktopControlAgent": AutomationAgent,
    "BrowserAgent": AutomationAgent,
}

__all__ = [
    "BaseDomainAgent",
    "GeneralAgent",
    "ResearchAgent",
    "DeveloperAgent",
    "AutomationAgent",
    "DOMAIN_AGENTS",
]
