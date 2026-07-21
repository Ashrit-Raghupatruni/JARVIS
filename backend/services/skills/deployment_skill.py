"""
Deployment & Test Skill for FastMCP & Skill Registry integration.
Exposes Phase 17 tools: run_system_benchmarks, trigger_backup, restore_backup, check_update_status.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.test_runner import TestRunnerService


class DeploymentSkill(BaseSkill):
    """Skill exposing Phase 17 System Benchmarks & Local Backup tools."""

    name = "DeploymentSkill"
    description = "Local performance benchmarks runner, data backup manager, backup restore engine, system update checker."

    def __init__(self, test_runner_service: Optional[TestRunnerService] = None):
        self.test_runner = test_runner_service or TestRunnerService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "run_system_benchmarks",
                "description": "Run local performance benchmarks for CPU, latency, and memory speed.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "trigger_backup",
                "description": "Create a local ZIP backup of all user data and JSON states.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "backup_label": {"type": "string", "description": "Optional label prefix for the backup."}
                    }
                }
            },
            {
                "name": "restore_backup",
                "description": "Restore local user data from a specified backup ZIP file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "backup_filename": {"type": "string", "description": "Name of backup zip file to restore."}
                    },
                    "required": ["backup_filename"]
                }
            },
            {
                "name": "check_update_status",
                "description": "Check current system version and update availability.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "run_system_benchmarks":
            return self.test_runner.run_system_benchmarks()
        elif tool_name == "trigger_backup":
            return self.test_runner.trigger_backup(parameters.get("backup_label", "auto_backup"))
        elif tool_name == "restore_backup":
            return self.test_runner.restore_backup(parameters.get("backup_filename", ""))
        elif tool_name == "check_update_status":
            return self.test_runner.check_update_status()
        else:
            raise ValueError(f"Unknown deployment tool: {tool_name}")
