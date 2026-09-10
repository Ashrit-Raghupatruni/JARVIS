"""
Plan validation, safety gatekeeper checks, and action outcome verifier.
"""
from typing import Any, Dict, Optional, Tuple
from loguru import logger
from backend.services.safety_gatekeeper import SafetyGatekeeper, ActionRiskLevel
from backend.services.action_verifier import ActionExecutionVerifier


class PlanValidator:
    def __init__(self, gatekeeper: Optional[SafetyGatekeeper] = None, verifier: Optional[ActionExecutionVerifier] = None):
        self.gatekeeper = gatekeeper or SafetyGatekeeper()
        self.verifier = verifier or ActionExecutionVerifier()

    def evaluate_safety(self, tool_name: str, arguments: dict) -> Any:
        return self.gatekeeper.evaluate_tool_call(tool_name=tool_name, arguments=arguments)

    def verify_action(self, tool_name: str, arguments: dict, execution_result: dict) -> Tuple[bool, str]:
        if tool_name == "open_application":
            app_target = arguments.get("app_name", "")
            return self.verifier.verify_application_launched(app_target)
        if isinstance(execution_result, dict) and execution_result.get("status") == "error":
            return False, execution_result.get("error", "Execution returned error status")
        return True, "Verified execution"
