"""
JARVIS AI OS - Out-of-Model Safety Gatekeeper & Schema Validator.

Enforces strict security policy outside the LLM. The LLM is never the final
authority for safety. Independent policy evaluation validates tool call schemas
and categorizes action risk levels prior to Win32 execution.
"""

from __future__ import annotations

import re
import os
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel, Field
from backend.utils.logger import logger
from backend.services.safety import DANGEROUS_COMMAND_PATTERNS, BLOCKED_COMMAND_PATTERNS


class ActionRiskLevel(str, Enum):
    READ_ONLY = "read_only"          # Safe perception / queries (Auto-approved)
    REVERSIBLE = "reversible"        # Window resize, clicks, control input (Auto-approved)
    SENSITIVE = "sensitive"          # App launch, form fill, safe non-critical writes (Logged & Checked)
    DESTRUCTIVE = "destructive"      # File delete, overwrite critical paths, process kill, shell exec (User Confirmation Required)


class SafetyDecision(BaseModel):
    allowed: bool
    risk_level: ActionRiskLevel
    requires_user_approval: bool = False
    reason: str = "Action permitted"
    validated_args: Dict[str, Any] = Field(default_factory=dict)


class SafetyGatekeeper:
    """Out-of-model security gatekeeper enforcing strict schema validation and policy checks."""

    # Sensitive paths that cannot be written or overwritten without explicit user approval
    PROTECTED_PATH_PATTERNS = [
        r"^[a-zA-Z]:[\\/]windows",
        r"^[a-zA-Z]:[\\/]program files",
        r"system32",
        r"syswow64",
        r"\.env$",
        r"id_rsa",
        r"id_ed25519",
        r"shadow$",
        r"passwd$",
        r"boot\.ini",
        r"ntuser\.dat",
        r"backend[\\/]config\.py",
        r"backend[\\/]services[\\/]safety.*\.py",
    ]

    def __init__(self) -> None:
        self.risk_mapping = {
            "get_system_telemetry": ActionRiskLevel.READ_ONLY,
            "list_windows": ActionRiskLevel.READ_ONLY,
            "search_files": ActionRiskLevel.READ_ONLY,
            "read_file": ActionRiskLevel.READ_ONLY,
            "get_file_info": ActionRiskLevel.READ_ONLY,
            "list_running_processes": ActionRiskLevel.READ_ONLY,
            "get_process_info": ActionRiskLevel.READ_ONLY,
            "check_hung_processes": ActionRiskLevel.READ_ONLY,
            "get_monitors": ActionRiskLevel.READ_ONLY,
            "get_clipboard": ActionRiskLevel.READ_ONLY,
            "get_active_app": ActionRiskLevel.READ_ONLY,
            "get_page_content": ActionRiskLevel.READ_ONLY,
            "search_web": ActionRiskLevel.READ_ONLY,
            "click_element_by_name": ActionRiskLevel.REVERSIBLE,
            "set_control_value": ActionRiskLevel.REVERSIBLE,
            "resize_window": ActionRiskLevel.REVERSIBLE,
            "minimize_window": ActionRiskLevel.REVERSIBLE,
            "set_clipboard": ActionRiskLevel.REVERSIBLE,
            "adjust_volume": ActionRiskLevel.REVERSIBLE,
            "open_app": ActionRiskLevel.SENSITIVE,
            "auto_fill_form": ActionRiskLevel.SENSITIVE,
            "create_file": ActionRiskLevel.SENSITIVE,
            "write_file": ActionRiskLevel.SENSITIVE,
            "create_folder": ActionRiskLevel.SENSITIVE,
            "move_file": ActionRiskLevel.SENSITIVE,
            "copy_file": ActionRiskLevel.SENSITIVE,
            "execute_terminal_command": ActionRiskLevel.SENSITIVE,
            "delete_file": ActionRiskLevel.DESTRUCTIVE,
            "delete_folder": ActionRiskLevel.DESTRUCTIVE,
            "kill_process": ActionRiskLevel.DESTRUCTIVE,
            "terminate_process": ActionRiskLevel.DESTRUCTIVE,
            "system_shutdown": ActionRiskLevel.DESTRUCTIVE,
        }

    def evaluate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> SafetyDecision:
        """
        Validates tool schema arguments and evaluates policy risk level per actual effect.
        The LLM is NEVER allowed to bypass this security gate.
        """
        risk_level = self.risk_mapping.get(tool_name, ActionRiskLevel.SENSITIVE)
        sanitized_args = dict(arguments)

        # ── 1. Deep Inspection: Terminal Commands ─────────────────────
        if tool_name in ("execute_terminal_command", "run_terminal_command", "shell_exec"):
            cmd = str(sanitized_args.get("command", "")).strip()
            
            # Check for unconditionally blocked commands (root wipe, fork bomb, etc.)
            for pat in BLOCKED_COMMAND_PATTERNS:
                if re.search(pat, cmd, re.IGNORECASE):
                    logger.warning("SafetyGatekeeper: Blocked critical command pattern: '{}'", cmd)
                    return SafetyDecision(
                        allowed=False,
                        risk_level=ActionRiskLevel.DESTRUCTIVE,
                        requires_user_approval=True,
                        reason=f"Security Policy Blocked: Dangerous system command pattern matched ('{pat}')",
                        validated_args=sanitized_args,
                    )

            # Check for dangerous command patterns (rm, del /f, format, reg, shutdown, taskkill)
            for pat in DANGEROUS_COMMAND_PATTERNS:
                if re.search(pat, cmd, re.IGNORECASE):
                    logger.warning("SafetyGatekeeper: Dangerous terminal command requires approval: '{}'", cmd)
                    return SafetyDecision(
                        allowed=False,
                        risk_level=ActionRiskLevel.DESTRUCTIVE,
                        requires_user_approval=True,
                        reason=f"User Confirmation Required: Terminal command matches dangerous pattern ('{cmd}')",
                        validated_args=sanitized_args,
                    )

        # ── 2. Deep Inspection: File Writes / Overwrites / Deletes ───────
        elif tool_name in ("write_file", "edit_file", "create_file", "save_file", "delete_file", "delete_folder", "move_file", "copy_file"):
            target_path = str(sanitized_args.get("file_path") or sanitized_args.get("path") or sanitized_args.get("destination_path") or "").strip()
            
            # Check for path traversal or operating on protected OS/system files
            target_norm = os.path.normpath(target_path).lower()
            for pattern in self.PROTECTED_PATH_PATTERNS:
                if re.search(pattern, target_norm, re.IGNORECASE):
                    logger.warning("SafetyGatekeeper: Intercepted write/delete attempt to protected path: '{}'", target_path)
                    return SafetyDecision(
                        allowed=False,
                        risk_level=ActionRiskLevel.DESTRUCTIVE,
                        requires_user_approval=True,
                        reason=f"User Confirmation Required: Target path '{target_path}' contains protected system files",
                        validated_args=sanitized_args,
                    )

        # ── 3. Deep Inspection: Application Launches ──────────────────
        elif tool_name in ("open_app", "open_application"):
            app_name = str(sanitized_args.get("app_name", "")).strip()
            dangerous_chars = ["&", ";", "|", ">", "<", "$", "`", "\n", "rm ", "del ", "format ", "system32", "syswow64"]
            if any(char in app_name.lower() for char in dangerous_chars):
                logger.warning("SafetyGatekeeper: Intercepted malicious command injection in open_application: '{}'", app_name)
                return SafetyDecision(
                    allowed=False,
                    risk_level=ActionRiskLevel.DESTRUCTIVE,
                    requires_user_approval=True,
                    reason=f"Security Policy Rejected: Command injection or dangerous path detected in app_name '{app_name}'",
                    validated_args={},
                )

        # ── 4. Destructive Tools (delete_file, terminate_process, etc.) 
        if risk_level == ActionRiskLevel.DESTRUCTIVE:
            return SafetyDecision(
                allowed=False,
                risk_level=risk_level,
                requires_user_approval=True,
                reason=f"User Confirmation Required: '{tool_name}' is categorized as DESTRUCTIVE",
                validated_args=sanitized_args,
            )

        logger.info("SafetyGatekeeper: Approved tool '{}' (Risk: {})", tool_name, risk_level.value)
        return SafetyDecision(
            allowed=True,
            risk_level=risk_level,
            requires_user_approval=False,
            reason="Action policy check passed",
            validated_args=sanitized_args,
        )
