"""
Research Skill for FastMCP & Skill Registry integration.
Exposes Phase 10 tools: research report generation, PDF analysis, fact claim verification, persistent browser profiles.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.research_agent import ResearchAgentService


class ResearchSkill(BaseSkill):
    """Skill exposing Phase 10 Browser & Research Agent tools."""

    name = "ResearchSkill"
    description = "Research report synthesis with citations, PDF text parsing, fact claim verification, persistent browser profile manager."

    def __init__(self, research_service: Optional[ResearchAgentService] = None):
        self.research_service = research_service or ResearchAgentService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "generate_research_report",
                "description": "Synthesize research topic findings into a structured markdown report with citations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Research subject query."}
                    },
                    "required": ["topic"]
                }
            },
            {
                "name": "analyze_pdf_document",
                "description": "Extract text, headings, and structure from a local PDF document.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pdf_path": {"type": "string", "description": "Path to local PDF file."}
                    },
                    "required": ["pdf_path"]
                }
            },
            {
                "name": "verify_fact_claim",
                "description": "Evaluate a claim or fact statement against reference sources.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string", "description": "Claim text to verify."}
                    },
                    "required": ["claim"]
                }
            },
            {
                "name": "manage_browser_profile",
                "description": "Inspect Playwright persistent browser context profile directory and saved session states.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "multi_tab_browser_action",
                "description": "Simulate multi-tab browser context controls (create, list, switch, close tab).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["create_tab", "list_tabs", "switch_tab", "close_tab"]},
                        "url": {"type": "string", "description": "Optional URL for new tab."},
                        "tab_id": {"type": "integer", "description": "Optional target tab ID."}
                    },
                    "required": ["action"]
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "generate_research_report":
            return self.research_service.generate_research_report(parameters.get("topic", ""))
        elif tool_name == "analyze_pdf_document":
            return self.research_service.analyze_pdf_document(parameters.get("pdf_path", ""))
        elif tool_name == "verify_fact_claim":
            return self.research_service.verify_fact_claim(parameters.get("claim", ""))
        elif tool_name == "manage_browser_profile":
            return self.research_service.manage_browser_profile()
        elif tool_name == "multi_tab_browser_action":
            return self.research_service.multi_tab_browser_action(
                parameters.get("action", "list_tabs"),
                parameters.get("url"),
                parameters.get("tab_id")
            )
        else:
            raise ValueError(f"Unknown research tool: {tool_name}")
