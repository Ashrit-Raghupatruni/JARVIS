"""
JARVIS AI OS — Developer Domain Agent.
Handles AST code analysis, docstring generation, Text-to-SQL generation, safe SQL execution, git operations, and SecuritySandbox execution.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.agents.domain.base_domain_agent import BaseDomainAgent


class DeveloperAgent(BaseDomainAgent):
    """Domain Agent for software engineering, code intelligence, SQL safety, and sandbox execution."""

    def __init__(self, event_bus=None, llm_service=None) -> None:
        super().__init__(
            name="DeveloperAgent",
            role_description="AST code docstrings, project structure scanning, text-to-SQL query generation, safe SQL, and sandbox execution.",
            allowed_tools=[
                "generate_docstrings", "generate_sql_query", "execute_safe_sql_query",
                "execute_code", "scan_project_structure", "git_status", "run_terminal"
            ],
            event_bus=event_bus,
            llm_service=llm_service
        )

    async def execute_task(self, task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.status = "processing"
        self.last_active = time.time()
        start_time = time.time()

        try:
            from backend.services.skills.developer_skill import DeveloperSkill
            skill = DeveloperSkill()
            
            # Identify sub-task type
            desc_lower = task_description.lower()
            if "sql" in desc_lower or "query" in desc_lower or "database" in desc_lower:
                res = await skill.execute_tool("generate_sql_query", {"user_query": task_description})
                response_text = f"Generated SQL Query:\n```sql\n{res.get('generated_sql', '')}\n```\nExplanation: {res.get('explanation', '')}"
            elif "docstring" in desc_lower or "document" in desc_lower:
                response_text = f"DeveloperAgent ready to document AST targets for: {task_description}"
            else:
                from backend.services.manager import ServiceManager
                dev_svc = ServiceManager.get_instance("developer_assistant_service")
                if dev_svc and hasattr(dev_svc, "analyze_codebase"):
                    res = dev_svc.analyze_codebase()
                    response_text = str(res)
                else:
                    response_text = f"DeveloperAgent analyzed task: '{task_description}'."

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
            logger.error("DeveloperAgent task error: {}", e)
            return {
                "status": "error",
                "agent": self.name,
                "error": str(e),
                "duration_seconds": round(time.time() - start_time, 3)
            }
