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
from backend.services.data_privacy import (
    DataClassification,
    DataFlowDestination,
    get_privacy_enforcer,
    mask_secrets,
    sanitize_payload,
)


class ActionRiskLevel(str, Enum):
    READ_ONLY = "read_only"          # Safe perception / queries (Auto-approved)
    REVERSIBLE = "reversible"        # Window resize, clicks, control input (Auto-approved)
    SENSITIVE = "sensitive"          # App launch, form fill, safe non-critical writes (Logged & Checked)
    DESTRUCTIVE = "destructive"      # File delete, overwrite critical paths, process kill, shell exec (User Confirmation Required)


class SecurityDecisionType(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    DEVICE_AUTHENTICATION_REQUIRED = "DEVICE_AUTHENTICATION_REQUIRED"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"


class SafetyDecision(BaseModel):
    allowed: bool
    risk_level: ActionRiskLevel
    requires_user_approval: bool = False
    decision: SecurityDecisionType = SecurityDecisionType.ALLOW
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

    # Protected critical system processes that must NEVER be terminated
    PROTECTED_PROCESS_NAMES = {
        "csrss.exe", "lsass.exe", "smss.exe", "wininit.exe", "services.exe",
        "svchost.exe", "winlogon.exe", "system", "idle", "system idle process",
        "dwm.exe"
    }

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
            "rename_file": ActionRiskLevel.SENSITIVE,
            "execute_terminal_command": ActionRiskLevel.SENSITIVE,
            "close_application": ActionRiskLevel.SENSITIVE,
            "close_app": ActionRiskLevel.SENSITIVE,
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
        Fails closed on any unexpected exception or validation failure.
        """
        try:
            risk_level = self.risk_mapping.get(tool_name, ActionRiskLevel.SENSITIVE)
            sanitized_args = dict(arguments) if isinstance(arguments, dict) else {}

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
                            decision=SecurityDecisionType.DENY,
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
                            decision=SecurityDecisionType.REQUIRE_APPROVAL,
                            reason=f"User Confirmation Required: Terminal command matches dangerous pattern ('{cmd}')",
                            validated_args=sanitized_args,
                        )

                # Check for targeting protected system paths inside terminal commands
                cmd_norm = os.path.normpath(cmd).lower()
                for pat in self.PROTECTED_PATH_PATTERNS:
                    if re.search(pat, cmd, re.IGNORECASE) or re.search(pat, cmd_norm, re.IGNORECASE):
                        logger.warning("SafetyGatekeeper: Terminal command references protected OS path: '{}'", cmd)
                        return SafetyDecision(
                            allowed=False,
                            risk_level=ActionRiskLevel.DESTRUCTIVE,
                            requires_user_approval=True,
                            decision=SecurityDecisionType.REQUIRE_APPROVAL,
                            reason=f"User Confirmation Required: Terminal command targets protected path ('{cmd}')",
                            validated_args=sanitized_args,
                        )

            # ── 2. Deep Inspection: File Writes / Overwrites / Deletes ───────
            elif tool_name in ("write_file", "edit_file", "create_file", "save_file", "delete_file", "delete_folder", "move_file", "copy_file", "rename_file"):
                raw_path = str(
                    sanitized_args.get("file_path")
                    or sanitized_args.get("path")
                    or sanitized_args.get("destination_path")
                    or sanitized_args.get("new_path")
                    or sanitized_args.get("old_path")
                    or ""
                ).strip()
                
                # Canonicalize path before evaluating security patterns
                target_norm = os.path.normpath(raw_path).lower()
                try:
                    target_resolved = str(Path(raw_path).resolve()).lower()
                except Exception:
                    target_resolved = target_norm

                for check_str in (target_norm, target_resolved, raw_path.lower()):
                    for pattern in self.PROTECTED_PATH_PATTERNS:
                        if re.search(pattern, check_str, re.IGNORECASE):
                            logger.warning("SafetyGatekeeper: Intercepted write/delete attempt to protected path: '{}' (matched '{}')", raw_path, pattern)
                            return SafetyDecision(
                                allowed=False,
                                risk_level=ActionRiskLevel.DESTRUCTIVE,
                                requires_user_approval=True,
                                decision=SecurityDecisionType.REQUIRE_APPROVAL,
                                reason=f"User Confirmation Required: Target path '{raw_path}' contains protected system files",
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
                        decision=SecurityDecisionType.DENY,
                        reason=f"Security Policy Rejected: Command injection or dangerous path detected in app_name '{app_name}'",
                        validated_args={},
                    )

            # ── 4. Deep Inspection: Process Termination ───────────────────
            elif tool_name in ("kill_process", "terminate_process", "close_application", "close_app"):
                proc_name = str(sanitized_args.get("process_name") or sanitized_args.get("app_name") or "").strip().lower()
                target_pid = sanitized_args.get("pid")

                # Check self-PID protection
                if target_pid is not None:
                    try:
                        if int(target_pid) == os.getpid():
                            logger.warning("SafetyGatekeeper: Intercepted attempt to kill JARVIS self PID: {}", target_pid)
                            return SafetyDecision(
                                allowed=False,
                                risk_level=ActionRiskLevel.DESTRUCTIVE,
                                requires_user_approval=False,
                                decision=SecurityDecisionType.DENY,
                                reason=f"Security Policy Denied: Process PID {target_pid} is JARVIS runtime process (self-kill blocked)",
                                validated_args={},
                            )
                    except (ValueError, TypeError):
                        pass

                # Check protected critical Windows processes
                if proc_name:
                    clean_pname = proc_name if proc_name.endswith(".exe") else f"{proc_name}.exe"
                    if clean_pname in self.PROTECTED_PROCESS_NAMES or proc_name in self.PROTECTED_PROCESS_NAMES:
                        logger.warning("SafetyGatekeeper: Intercepted attempt to terminate protected system process: '{}'", proc_name)
                        return SafetyDecision(
                            allowed=False,
                            risk_level=ActionRiskLevel.DESTRUCTIVE,
                            requires_user_approval=False,
                            decision=SecurityDecisionType.DENY,
                            reason=f"Security Policy Denied: Process '{proc_name}' is a critical system process and cannot be terminated",
                            validated_args={},
                        )

            # ── 5. Deep Inspection: Outbound Data & Exfiltration Interception ──
            elif tool_name in ("upload_file", "browser_upload", "send_email", "send_message", "post_webhook", "transmit_telemetry", "export_data"):
                privacy_enforcer = get_privacy_enforcer()
                classification = privacy_enforcer.classify_data(sanitized_args, source_hint=tool_name)
                
                # Check for unmasked secrets in outbound payload
                if classification == DataClassification.SECRET:
                    logger.warning("SafetyGatekeeper: Intercepted attempt to exfiltrate unmasked credentials via '{}'", tool_name)
                    return SafetyDecision(
                        allowed=False,
                        risk_level=ActionRiskLevel.DESTRUCTIVE,
                        requires_user_approval=True,
                        decision=SecurityDecisionType.DENY,
                        reason=f"Security Policy Denied: Outbound tool '{tool_name}' contains unmasked SECRET credentials",
                        validated_args={},
                    )

                # Check if LOCAL_ONLY is active
                if privacy_enforcer.local_only_mode:
                    logger.warning("SafetyGatekeeper: Outbound tool '{}' blocked under LOCAL_ONLY isolation mode", tool_name)
                    return SafetyDecision(
                        allowed=False,
                        risk_level=ActionRiskLevel.DESTRUCTIVE,
                        requires_user_approval=False,
                        decision=SecurityDecisionType.DENY,
                        reason=f"Security Policy Denied: Outbound tool '{tool_name}' forbidden under LOCAL_ONLY isolation",
                        validated_args={},
                    )

                # Sensitive uploads/emails require user approval
                if classification in (DataClassification.SENSITIVE, DataClassification.PERSONAL):
                    return SafetyDecision(
                        allowed=False,
                        risk_level=ActionRiskLevel.SENSITIVE,
                        requires_user_approval=True,
                        decision=SecurityDecisionType.REQUIRE_APPROVAL,
                        reason=f"User Confirmation Required: Outbound transmission of {classification.value} data via '{tool_name}'",
                        validated_args=sanitized_args,
                    )

            # ── 6. Destructive Tools (delete_file, terminate_process, etc.) 
            if risk_level == ActionRiskLevel.DESTRUCTIVE:
                return SafetyDecision(
                    allowed=False,
                    risk_level=risk_level,
                    requires_user_approval=True,
                    decision=SecurityDecisionType.REQUIRE_APPROVAL,
                    reason=f"User Confirmation Required: '{tool_name}' is categorized as DESTRUCTIVE",
                    validated_args=sanitized_args,
                )

            logger.info("SafetyGatekeeper: Approved tool '{}' (Risk: {})", tool_name, risk_level.value)
            return SafetyDecision(
                allowed=True,
                risk_level=risk_level,
                requires_user_approval=False,
                decision=SecurityDecisionType.ALLOW,
                reason="Action policy check passed",
                validated_args=sanitized_args,
            )
        except Exception as exc:
            logger.error("SafetyGatekeeper internal error during evaluation of tool '{}': {}", tool_name, exc)
            return SafetyDecision(
                allowed=False,
                risk_level=ActionRiskLevel.DESTRUCTIVE,
                requires_user_approval=True,
                decision=SecurityDecisionType.DENY,
                reason=f"Security Policy Exception (Fail-Closed): {exc}",
                validated_args={},
            )

    def evaluate_data_egress(
        self,
        data: Any,
        destination: Union[DataFlowDestination, str],
        source_hint: Optional[str] = None,
        has_user_approval: bool = False,
    ) -> Tuple[bool, str, DataClassification]:
        """
        Evaluates out-of-model information flow and egress compliance.
        Returns (allowed: bool, reason: str, classification: DataClassification).
        """
        try:
            privacy_enforcer = get_privacy_enforcer()
            classification = privacy_enforcer.classify_data(data, source_hint=source_hint)
            dest_enum = DataFlowDestination(str(destination)) if isinstance(destination, str) else destination

            # Check for secrets
            is_masked = False
            if classification == DataClassification.SECRET:
                # If masked, allow to proceed with sanitized data
                is_masked = False

            allowed, reason = privacy_enforcer.evaluate_egress(
                classification=classification,
                destination=dest_enum,
                is_masked=is_masked,
                has_user_approval=has_user_approval,
            )
            return allowed, reason, classification
        except Exception as exc:
            logger.error("SafetyGatekeeper.evaluate_data_egress exception (Fail-Closed): {}", exc)
            return False, f"Fail-Closed Privacy Exception: {exc}", DataClassification.SECRET

