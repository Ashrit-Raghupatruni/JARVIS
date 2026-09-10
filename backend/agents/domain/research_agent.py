"""
JARVIS AI OS — Research Domain Agent.
Handles online web search, URL analysis, chemical science calculations, PubChem queries, RAG document search, and content extraction.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.agents.domain.base_domain_agent import BaseDomainAgent


class ResearchAgent(BaseDomainAgent):
    """Domain Agent for web search, document RAG, chemoinformatics, biology, and semantic extraction."""

    def __init__(self, event_bus=None, llm_service=None) -> None:
        super().__init__(
            name="ResearchAgent",
            role_description="Web search orchestration, URL scraping, PubChem science, RAG document querying, and semantic analysis.",
            allowed_tools=[
                "search_web", "fetch_url_content", "analyze_sentiment",
                "extract_keywords_and_entities", "summarize_content",
                "parse_chemical_formula", "balance_chemical_equation",
                "query_pubchem_compound", "explain_biological_process",
                "rag_search", "rag_add_document"
            ],
            event_bus=event_bus,
            llm_service=llm_service
        )

    async def execute_task(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.status = "processing"
        self.last_active = time.time()
        start_time = time.time()

        try:
            from backend.services.manager import ServiceManager
            research_svc = ServiceManager.get_instance("research_service")
            
            # If search or research service is available
            if research_svc and hasattr(research_svc, "search_and_summarize"):
                res = await research_svc.search_and_summarize(task_description)
                response_text = str(res)
            else:
                # Fallback to direct tool execution or LLM synthesis
                from backend.services.skills.research_skill import ResearchSkill
                skill = ResearchSkill()
                res = await skill.execute_tool("search_web", {"query": task_description})
                response_text = str(res)

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
            logger.error("ResearchAgent task error: {}", e)
            return {
                "status": "error",
                "agent": self.name,
                "error": str(e),
                "duration_seconds": round(time.time() - start_time, 3)
            }
