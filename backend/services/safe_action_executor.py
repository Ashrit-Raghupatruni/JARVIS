"""
JARVIS AI OS — Guarded Action Executor.
========================================
Ensures no candidate model output (from Qwen3:8B, Prash, or Planner) is permitted to execute
without passing through the 3 mandatory verification layers:
  1. ToolRegistry schema validation & argument type checking
  2. SafetyGatekeeper security evaluation & risk level categorization
  3. ActionExecutionVerifier post-condition state verification
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel
from loguru import logger

from backend.services.tool_registry import ToolRegistry
from backend.services.safety_gatekeeper import SafetyGatekeeper, ActionRiskLevel, SafetyDecision
from backend.services.action_verifier import ActionExecutionVerifier
from backend.services.prash_tool_validator import PrashToolValidator, PrashValidationResult


class ExecutionGuardResult(BaseModel):
    allowed: bool
    status: str
    tool_name: str
    parameters: Dict[str, Any]
    risk_level: str
    requires_user_approval: bool
    schema_valid: bool
    verified: bool
    verification_reason: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class SafeActionExecutor:
    """
    Unified guarded execution pipeline.
    Enforces out-of-model security, schema compliance, and post-condition execution verification.
    """

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        safety_gatekeeper: Optional[SafetyGatekeeper] = None,
        action_verifier: Optional[ActionExecutionVerifier] = None,
    ) -> None:
        self.tool_registry = tool_registry or ToolRegistry()
        self.safety_gatekeeper = safety_gatekeeper or SafetyGatekeeper()
        self.action_verifier = action_verifier or ActionExecutionVerifier()
        self.prash_validator = PrashToolValidator(tool_registry=self.tool_registry)

    async def execute_guarded(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        source: str = "qwen3:8b",
        user_confirmed: bool = False,
    ) -> ExecutionGuardResult:
        """
        Executes a candidate tool call through the 3 mandatory safety gates:
          Gate 1: ToolRegistry / PrashToolValidator Schema & Argument Type Check
          Gate 2: SafetyGatekeeper Risk Level & Path / Pattern Inspection
          Gate 3: ActionExecutionVerifier State Delta Verification
        """
        start_time = time.time()
        logger.info(f"🛡️ SafeActionExecutor: Evaluating candidate tool '{tool_name}' from source '{source}'")

        # ── Gate 1: ToolRegistry & PrashToolValidator Schema Check ──────────────
        raw_json_call = json_format_tool_call(tool_name, parameters)
        val_res: PrashValidationResult = self.prash_validator.validate_raw_response(raw_json_call, user_query="")

        if not val_res.is_valid:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"❌ Gate 1 REJECTED: Schema validation failed for tool '{tool_name}': {val_res.rejection_reason}")
            return ExecutionGuardResult(
                allowed=False,
                status="schema_error",
                tool_name=tool_name,
                parameters=parameters,
                risk_level=ActionRiskLevel.SENSITIVE.value,
                requires_user_approval=False,
                schema_valid=False,
                verified=False,
                error=f"Schema validation failed: {val_res.rejection_reason or 'Unknown tool or invalid arguments'}",
                duration_ms=duration_ms,
            )

        sanitized_params = val_res.parameters if (val_res.is_valid and val_res.parameters) else parameters

        # ── Gate 2: SafetyGatekeeper Evaluation ───────────────────────────────
        safety_dec: SafetyDecision = self.safety_gatekeeper.evaluate_tool_call(tool_name, sanitized_params)
        logger.info(f"Gate 2 Safety Evaluation for '{tool_name}': allowed={safety_dec.allowed}, risk={safety_dec.risk_level}, req_approval={safety_dec.requires_user_approval}")

        if not safety_dec.allowed:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"⛔ Gate 2 REJECTED by SafetyGatekeeper: {safety_dec.reason}")
            return ExecutionGuardResult(
                allowed=False,
                status="blocked_by_safety_gatekeeper",
                tool_name=tool_name,
                parameters=sanitized_params,
                risk_level=safety_dec.risk_level.value,
                requires_user_approval=safety_dec.requires_user_approval,
                schema_valid=True,
                verified=False,
                error=f"Security Policy Block: {safety_dec.reason}",
                duration_ms=duration_ms,
            )

        if safety_dec.requires_user_approval and not user_confirmed:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.info(f"⚠️ Gate 2 HELD FOR APPROVAL: Destructive/Sensitive tool '{tool_name}' requires explicit user confirmation.")
            return ExecutionGuardResult(
                allowed=False,
                status="user_approval_required",
                tool_name=tool_name,
                parameters=sanitized_params,
                risk_level=safety_dec.risk_level.value,
                requires_user_approval=True,
                schema_valid=True,
                verified=False,
                error=f"Action '{tool_name}' requires explicit user confirmation prior to execution.",
                duration_ms=duration_ms,
            )

        # ── Gate 3: Execute & ActionExecutionVerifier Verification ───────────
        try:
            exec_ver_res = await self.action_verifier.execute_and_verify(
                tool_name=tool_name,
                arguments=sanitized_params,
                tool_registry=self.tool_registry,
            )

            duration_ms = round((time.time() - start_time) * 1000, 2)
            is_verified = exec_ver_res.get("verified", False)
            exec_status = exec_ver_res.get("status", "unknown")

            logger.info(f"✓ Gate 3 PASSED for '{tool_name}': verified={is_verified}, status={exec_status}, duration={duration_ms}ms")

            return ExecutionGuardResult(
                allowed=True,
                status="success" if is_verified else "executed_unverified",
                tool_name=tool_name,
                parameters=sanitized_params,
                risk_level=safety_dec.risk_level.value,
                requires_user_approval=False,
                schema_valid=True,
                verified=is_verified,
                verification_reason=exec_ver_res.get("reason"),
                execution_result=exec_ver_res,
                duration_ms=duration_ms,
            )
        except Exception as err:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(f"❌ Gate 3 EXECUTION ERROR for '{tool_name}': {err}")
            return ExecutionGuardResult(
                allowed=False,
                status="execution_failed",
                tool_name=tool_name,
                parameters=sanitized_params,
                risk_level=safety_dec.risk_level.value,
                requires_user_approval=False,
                schema_valid=True,
                verified=False,
                error=str(err),
                duration_ms=duration_ms,
            )


def json_format_tool_call(tool_name: str, parameters: Dict[str, Any]) -> str:
    """Helper to format tool call as JSON string for validator inspection."""
    return json.dumps({"action": "tool_call", "name": tool_name, "parameters": parameters})
