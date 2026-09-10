"""
Developer Skill for FastMCP & Skill Registry integration.
Exposes tools: repository analysis, bug localization, test stubs, PR creation,
dependency audit, AST docstring generation, and safe Text-to-SQL querying.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.developer_assistant import DeveloperAssistantService


class DeveloperSkill(BaseSkill):
    """Skill exposing Developer Assistant, code documentation, and database querying tools."""

    name = "DeveloperSkill"
    description = "Codebase architecture analysis, bug localization, pytest stubs, PR generator, docstrings, and Text-to-SQL."

    def __init__(self, dev_service: Optional[DeveloperAssistantService] = None):
        self.dev_service = dev_service or DeveloperAssistantService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "analyze_repository_structure",
                "description": "Analyze repository files, languages, framework manifests, lines of code, and architecture summary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Path to codebase root directory."}
                    },
                    "required": ["repo_path"]
                }
            },
            {
                "name": "localize_bug_from_trace",
                "description": "Parse error stack traces or compiler logs to pinpoint matching source files, line numbers, and error types.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "stack_trace": {"type": "string", "description": "Stack trace log or exception error text."}
                    },
                    "required": ["stack_trace"]
                }
            },
            {
                "name": "generate_unit_test_stub",
                "description": "Analyze Python file AST to extract functions/classes and generate pytest test stubs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to target Python file."}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "generate_pr_description",
                "description": "Inspect git status and uncommitted/recent changes to format a Pull Request title and markdown summary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Path to git repository directory."}
                    },
                    "required": ["repo_path"]
                }
            },
            {
                "name": "audit_dependencies",
                "description": "Audit manifest dependencies (requirements.txt / package.json) for installed packages.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Path to target project directory."}
                    },
                    "required": ["repo_path"]
                }
            },
            {
                "name": "generate_docstrings",
                "description": "Parse Python file AST and generate structured Google/Sphinx style docstrings for functions and classes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to target Python file."},
                        "style": {"type": "string", "enum": ["google", "sphinx", "numpy"]}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "generate_sql_query",
                "description": "Translate natural language request into a validated, read-only SQL query with optional schema context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_query": {"type": "string", "description": "Natural language query (e.g. 'count active users in database')."},
                        "db_path": {"type": "string", "description": "Optional local SQLite DB path for schema inspection."}
                    },
                    "required": ["user_query"]
                }
            },
            {
                "name": "execute_safe_sql_query",
                "description": "Execute a read-only SQL query against a local SQLite database file with AST safety enforcement.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {"type": "string", "description": "SELECT SQL query to execute."},
                        "db_path": {"type": "string", "description": "Path to SQLite database file."}
                    },
                    "required": ["sql_query", "db_path"]
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "analyze_repository_structure":
            return self.dev_service.analyze_repository_structure(parameters.get("repo_path", "."))
        elif tool_name == "localize_bug_from_trace":
            return self.dev_service.localize_bug_from_trace(parameters.get("stack_trace", ""))
        elif tool_name == "generate_unit_test_stub":
            return self.dev_service.generate_unit_test_stub(parameters.get("file_path", ""))
        elif tool_name == "generate_pr_description":
            return self.dev_service.generate_pr_description(parameters.get("repo_path", "."))
        elif tool_name == "audit_dependencies":
            return self.dev_service.audit_dependencies(parameters.get("repo_path", "."))
        elif tool_name == "generate_docstrings":
            return self.dev_service.generate_docstrings(
                parameters.get("file_path", ""),
                style=parameters.get("style", "google")
            )
        elif tool_name == "generate_sql_query":
            return self.dev_service.generate_sql_query(
                parameters.get("user_query", ""),
                db_path=parameters.get("db_path")
            )
        elif tool_name == "execute_safe_sql_query":
            return self.dev_service.execute_safe_sql_query(
                parameters.get("sql_query", ""),
                parameters.get("db_path", "")
            )
        else:
            raise ValueError(f"Unknown developer tool: {tool_name}")
