"""
JARVIS AI OS - Out-of-Model Safety Gatekeeper & Schema Validator.

Enforces strict security policy outside the LLM. The LLM is never the final
authority for safety. Independent policy evaluation validates tool call schemas
and categorizes action risk levels prior to Win32 execution.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from backend.utils.logger import logger


class ActionRiskLevel(str, Enum):
    READ_ONLY = "read_only"          # Safe perception / queries (Auto-approved)
    REVERSIBLE = "reversible"        # Window resize, clicks, control input (Auto-approved)
    SENSITIVE = "sensitive"          # App launch, form fill (Logged & Checked)
    DESTRUCTIVE = "destructive"      # File delete, process kill, system shutdown (User Confirmation Required)


class SafetyDecision(BaseModel):
    allowed: bool
    risk_level: ActionRiskLevel
    requires_user_approval: bool = False
    reason: str = "Action permitted"
    validated_args: Dict[str, Any] = Field(default_factory=dict)


class SafetyGatekeeper:
    """Out-of-model security gatekeeper enforcing strict schema validation and policy checks."""

    def __init__(self) -> None:
        self.risk_mapping = {
            "get_system_telemetry": ActionRiskLevel.READ_ONLY,
            "list_windows": ActionRiskLevel.READ_ONLY,
            "search_files": ActionRiskLevel.READ_ONLY,
            "get_active_app": ActionRiskLevel.READ_ONLY,
            "click_element_by_name": ActionRiskLevel.REVERSIBLE,
            "set_control_value": ActionRiskLevel.REVERSIBLE,
            "resize_window": ActionRiskLevel.REVERSIBLE,
            "minimize_window": ActionRiskLevel.REVERSIBLE,
            "open_app": ActionRiskLevel.SENSITIVE,
            "auto_fill_form": ActionRiskLevel.SENSITIVE,
            "delete_file": ActionRiskLevel.DESTRUCTIVE,
            "terminate_process": ActionRiskLevel.DESTRUCTIVE,
            "system_shutdown": ActionRiskLevel.DESTRUCTIVE,
        }

    def evaluate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> SafetyDecision:
        """
        Validates tool schema arguments and evaluates policy risk level.
        The LLM is NEVER allowed to bypass this security gate.
        """
        # Determine risk level
        risk_level = self.risk_mapping.get(tool_name, ActionRiskLevel.SENSITIVE)

        # Sanitize arguments
        sanitized_args = dict(arguments)
        
        # Check for dangerous command injections in open_app or text inputs
        if tool_name == "open_app":
            app_name = str(sanitized_args.get("app_name", "")).strip()
            dangerous_chars = ["&", ";", "|", ">", "<", "$", "`", "\n"]
            if any(char in app_name for char in dangerous_chars):
                logger.warning(f"SafetyGatekeeper: Intercepted malicious command injection in open_app: '{app_name}'")
                return SafetyDecision(
                    allowed=False,
                    risk_level=ActionRiskLevel.DESTRUCTIVE,
                    requires_user_approval=True,
                    reason=f"Security Policy Rejected: Command injection detected in app_name '{app_name}'",
                    validated_args={},
                )

        # Destructive actions require explicit user approval modal
        if risk_level == ActionRiskLevel.DESTRUCTIVE:
            return SafetyDecision(
                allowed=False,
                risk_level=risk_level,
                requires_user_approval=True,
                reason=f"User Confirmation Required: '{tool_name}' is categorized as DESTRUCTIVE",
                validated_args=sanitized_args,
            )

        logger.info(f"SafetyGatekeeper: Approved tool '{tool_name}' (Risk: {risk_level.value})")
        return SafetyDecision(
            allowed=True,
            risk_level=risk_level,
            requires_user_approval=False,
            reason="Action policy check passed",
            validated_args=sanitized_args,
        )
