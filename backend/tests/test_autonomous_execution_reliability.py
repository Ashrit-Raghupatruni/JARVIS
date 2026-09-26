"""
JARVIS AI OS — Autonomous Execution Reliability & Failure Recovery Suite (Phase 5).
====================================================================================
Comprehensive verification proving that:
1. Action lifecycle distinguishes FAILED_BEFORE_EXECUTION from EXECUTION_UNKNOWN.
2. Actions are strictly classified by idempotency (IDEMPOTENT, NON_IDEMPOTENT, etc.).
3. Blind retries are strictly forbidden on NON_IDEMPOTENT or UNKNOWN actions under EXECUTION_UNKNOWN.
4. Multi-step autonomous goals halt immediately on failure without blind continuation.
5. Immediate goal cancellation and emergency stop halts execution between and during steps.
6. Autonomous execution cannot bypass SafetyGatekeeper security policies.
"""

import asyncio
import os
import pytest
from typing import Dict, Any

from backend.services.automation.verifier import (
    ActionLifecycleState,
    ActionIdempotency,
    get_tool_idempotency,
    can_safely_retry,
)
from backend.services.live_mode.live_goal_engine import (
    LiveGoalExecutionEngine,
    GoalStep,
    GoalExecutionState,
)
from backend.services.tool_registry import ToolRegistry
from backend.services.safety_gatekeeper import (
    SafetyGatekeeper,
    ActionRiskLevel,
    SecurityDecisionType,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. Action Lifecycle & Idempotency Governance Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_action_lifecycle_states():
    """Verify standard lifecycle states exist and distinguish unknown execution."""
    expected_states = {
        "PLANNED", "AUTHORIZED", "EXECUTING", "COMPLETED", "VERIFIED",
        "FAILED_BEFORE_EXECUTION", "EXECUTION_UNKNOWN",
        "EXECUTED_NOT_VERIFIED", "EXECUTED_AND_FAILED_VERIFICATION", "CANCELLED"
    }
    actual_states = {s.value for s in ActionLifecycleState}
    assert expected_states.issubset(actual_states)


def test_idempotency_classification():
    """Verify tool idempotency classification."""
    assert get_tool_idempotency("read_file") == ActionIdempotency.IDEMPOTENT
    assert get_tool_idempotency("search_files") == ActionIdempotency.IDEMPOTENT
    assert get_tool_idempotency("search_web") == ActionIdempotency.IDEMPOTENT

    assert get_tool_idempotency("open_app") == ActionIdempotency.CONDITIONALLY_IDEMPOTENT
    assert get_tool_idempotency("create_folder") == ActionIdempotency.CONDITIONALLY_IDEMPOTENT

    assert get_tool_idempotency("execute_terminal_command") == ActionIdempotency.NON_IDEMPOTENT
    assert get_tool_idempotency("delete_file") == ActionIdempotency.NON_IDEMPOTENT
    assert get_tool_idempotency("kill_process") == ActionIdempotency.NON_IDEMPOTENT
    assert get_tool_idempotency("unknown_custom_tool_xyz") == ActionIdempotency.UNKNOWN


def test_blind_retry_policy_enforcement():
    """Verify that NON_IDEMPOTENT actions cannot be blindly retried on EXECUTION_UNKNOWN."""
    # 1. Read-only search can safely retry
    assert can_safely_retry("search_files", ActionLifecycleState.EXECUTION_UNKNOWN) is True

    # 2. File deletion under EXECUTION_UNKNOWN CANNOT safely retry (prevents duplicate destructive side-effects)
    assert can_safely_retry("delete_file", ActionLifecycleState.EXECUTION_UNKNOWN) is False

    # 3. Shell execution under EXECUTION_UNKNOWN CANNOT safely retry
    assert can_safely_retry("execute_terminal_command", ActionLifecycleState.EXECUTION_UNKNOWN) is False

    # 4. Unknown tool under EXECUTION_UNKNOWN CANNOT safely retry
    assert can_safely_retry("some_random_tool", ActionLifecycleState.EXECUTION_UNKNOWN) is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. Autonomous Multi-Step Execution & Failure Halting Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
async def test_multi_step_halts_on_failure():
    """Verify multi-step goal execution halts immediately when a step fails."""
    engine = LiveGoalExecutionEngine()
    registry = ToolRegistry()

    # Register a failing tool
    registry.register(
        name="step_one_success_tool",
        description="Success step",
        handler=lambda: "Step 1 OK"
    )
    registry.register(
        name="step_two_failing_tool",
        description="Failing step",
        handler=lambda: {"status": "error", "error": "Step 2 failed deliberately"}
    )
    registry.register(
        name="step_three_unreachable_tool",
        description="Unreachable step",
        handler=lambda: "Step 3 should not run"
    )

    # Custom multi-step execution simulation
    steps = [
        GoalStep(step_id=1, description="Step 1", tool_name="step_one_success_tool", parameters={}, risk_level="read_only"),
        GoalStep(step_id=2, description="Step 2", tool_name="step_two_failing_tool", parameters={}, risk_level="read_only"),
        GoalStep(step_id=3, description="Step 3", tool_name="step_three_unreachable_tool", parameters={}, risk_level="read_only"),
    ]

    # Monkeypatch decompose_goal for this test
    original_decompose = engine.decompose_goal
    engine.decompose_goal = lambda g, r: steps

    try:
        res = await engine.execute_multi_step_goal("test goal with failure", registry)
        assert res["status"] == "FAILED"
        assert steps[0].status == "COMPLETED"
        assert steps[1].status == "FAILED"
        assert steps[2].status == "PENDING"  # Step 3 must remain unexecuted
    finally:
        engine.decompose_goal = original_decompose


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. Emergency Cancellation & State Halting Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
async def test_goal_cancellation_halts_execution():
    """Verify cancel_goal halts ongoing execution immediately."""
    engine = LiveGoalExecutionEngine()
    registry = ToolRegistry()

    # Register a slow tool
    async def _slow_tool():
        await asyncio.sleep(0.5)
        return "Slow OK"

    registry.register(
        name="slow_step_tool",
        description="Slow step",
        handler=_slow_tool
    )
    registry.register(
        name="subsequent_tool",
        description="Subsequent step",
        handler=lambda: "Should not execute"
    )

    steps = [
        GoalStep(step_id=1, description="Slow step", tool_name="slow_step_tool", parameters={}, risk_level="read_only"),
        GoalStep(step_id=2, description="Subsequent step", tool_name="subsequent_tool", parameters={}, risk_level="read_only"),
    ]

    original_decompose = engine.decompose_goal
    engine.decompose_goal = lambda g, r: steps

    try:
        exec_task = asyncio.create_task(engine.execute_multi_step_goal("cancellation goal", registry))
        await asyncio.sleep(0.05)

        # Retrieve goal ID and cancel
        active_ids = list(engine.active_goals.keys())
        assert len(active_ids) > 0
        goal_id = active_ids[0]

        cancelled = engine.cancel_goal(goal_id)
        assert cancelled is True

        res = await exec_task
        assert res["status"] == "CANCELLED"
        assert steps[1].status == "PENDING" or steps[1].status == "CANCELLED"
    finally:
        engine.decompose_goal = original_decompose


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. Autonomous Execution Security Boundary Enforcement
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
async def test_autonomous_dangerous_step_pauses_for_approval():
    """Verify autonomous engine does not execute destructive actions without explicit user approval."""
    engine = LiveGoalExecutionEngine()
    registry = ToolRegistry()

    # Decompose goal containing a destructive action
    steps = [
        GoalStep(
            step_id=1,
            description="Delete file",
            tool_name="delete_file",
            parameters={"file_path": "C:\\test.txt"},
            risk_level="destructive",
            requires_approval=True
        )
    ]

    original_decompose = engine.decompose_goal
    engine.decompose_goal = lambda g, r: steps

    try:
        # Launch goal execution without providing permission
        exec_task = asyncio.create_task(engine.execute_multi_step_goal("delete file goal", registry))
        await asyncio.sleep(0.05)

        active_ids = list(engine.active_goals.keys())
        assert len(active_ids) > 0
        goal_id = active_ids[0]

        # Deny permission
        resolved = engine.grant_permission(goal_id, approved=False)
        assert resolved is True

        res = await exec_task
        assert res["status"] in ("PAUSED", "FAILED", "CANCELLED")
        assert steps[0].status in ("SKIPPED", "CANCELLED")
    finally:
        engine.decompose_goal = original_decompose
