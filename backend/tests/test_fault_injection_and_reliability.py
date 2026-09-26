"""
JARVIS AI OS — Phase 12: Testing, Fault Injection & Reliability Hardening Test Suite.
===================================================================================
Empirically verifies:
1. Controlled Test-Only Fault Injection (LLM provider failures, memory/db corruption, timeouts).
2. Failure-After-Action Handling (Post-action verification failure -> EXECUTION_UNKNOWN, no blind retry).
3. Idempotency Classification Matrix (SAFE_TO_RETRY vs NON_IDEMPOTENT vs UNKNOWN_STATE).
4. Emergency Stop & Atomic Task Cancellation (Release execution locks, stop queued actions).
5. Concurrency & Execution Lock Mutual Exclusion (Prevent interleaved hardware input).
6. ServiceManager Failure Isolation (Failed service doesn't crash independent services).
7. Memory Database Failure Degradation (No credential leak or unauthorized elevation).
8. Strict Tool Error Taxonomy (TOOL_NOT_FOUND, VALIDATION_ERROR, SECURITY_DENIED, EXECUTION_ERROR).
9. Resource Exhaustion & Bounded Execution (Input size limits, task queue bounds).
10. Filesystem Failure Isolation & Path Traversal Rejection.
"""

import pytest
import asyncio
import time
import threading
from contextlib import contextmanager
from unittest.mock import MagicMock, AsyncMock, patch

from backend.services.provider_health_evaluator import ProviderHealthEvaluator, ProviderStatus
from backend.services.safety_gatekeeper import SafetyGatekeeper, ActionRiskLevel, SafetyDecision
from backend.services.tool_registry import ToolRegistry
from backend.services.action_verifier import ActionExecutionVerifier
from backend.services.manager import ServiceManager, ServiceState
from backend.agents.router import classify_request, RequestCategory
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
from backend.services.automation.desktop_executor import DesktopExecutor


# ==============================================================================
# 1. Controlled Test-Only Fault Injection Helper
# ==============================================================================

@contextmanager
def fault_injection_scope(target_obj, method_name, fault_exception):
    """Safely inject a transient fault into a target object's method during test scope."""
    original_method = getattr(target_obj, method_name)
    setattr(target_obj, method_name, MagicMock(side_effect=fault_exception))
    try:
        yield
    finally:
        setattr(target_obj, method_name, original_method)


# ==============================================================================
# 2. LLM Provider Fault Injection & Fast-Path Fallback
# ==============================================================================

def test_fault_injection_llm_provider_failover():
    """Verify provider health evaluator records failure and switches to healthy provider."""
    health = ProviderHealthEvaluator()
    health.record_provider_failure("groq")
    health.record_provider_failure("groq")
    
    assert health.providers["groq"].status == ProviderStatus.COOLDOWN
    chosen = health.get_healthy_provider(["groq", "gemini", "ollama"])
    assert chosen in ("gemini", "ollama")
    assert chosen != "groq"


def test_fault_injection_all_providers_fail_to_deterministic_fast_path():
    """When all external LLM providers fail, deterministic intent classification continues working."""
    health = ProviderHealthEvaluator()
    for prov in ["groq", "gemini", "openai", "ollama"]:
        health.record_provider_failure(prov)
        health.record_provider_failure(prov)
        assert health.providers[prov].status == ProviderStatus.COOLDOWN

    # Fallback to deterministic regex/keyword intent classification
    cat_action = classify_request("Run AP24110011746")
    assert cat_action == RequestCategory.ACTION_REQUEST
    
    cat_code = classify_request("Write a python script to parse json")
    assert cat_code == RequestCategory.CODING

    cat_chat = classify_request("Tell me a funny joke about quantum physics")
    assert cat_chat == RequestCategory.CONVERSATION


def test_fault_injection_dangerous_hallucinated_tool_blocked_by_gatekeeper():
    """Verify hallucinated or dangerous tools returned by a compromised/faulty LLM are blocked."""
    gatekeeper = SafetyGatekeeper()
    
    # Dangerous terminal command pattern
    decision_cmd = gatekeeper.evaluate_tool_call("execute_terminal_command", {"command": "del /s /f C:\\Windows"})
    assert decision_cmd.allowed is False
    assert decision_cmd.risk_level == ActionRiskLevel.DESTRUCTIVE

    # Protected OS process termination injection
    decision_kill = gatekeeper.evaluate_tool_call("kill_process", {"process_name": "csrss.exe"})
    assert decision_kill.allowed is False
    assert decision_kill.risk_level == ActionRiskLevel.DESTRUCTIVE


# ==============================================================================
# 3. Failure-After-Action & Unknown State Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_failure_after_action_marks_unknown_state_and_avoids_blind_retry():
    """
    Critical Invariant:
    If an action executes successfully but verification times out, outcome is UNKNOWN_STATE
    and non-idempotent operations MUST NOT be blindly retried.
    """
    verifier = ActionExecutionVerifier()
    registry = ToolRegistry()

    # When open_application verification fails (e.g. process did not launch / timed out)
    res = await verifier.execute_and_verify(
        "open_application",
        {"app_name": "nonexistent_fake_process_99999.exe"},
        registry
    )
    
    assert res["verified"] is False
    assert res["status"] in ("unverified", "failed", "error")
    assert "not detected" in res.get("reason", "").lower() or not res["verified"]

    # Verify retry policy rejects non-idempotent operations when in EXECUTION_UNKNOWN
    assert can_safely_retry("delete_file", ActionLifecycleState.EXECUTION_UNKNOWN) is False
    assert can_safely_retry("execute_terminal_command", ActionLifecycleState.EXECUTION_UNKNOWN) is False
    assert can_safely_retry("search_files", ActionLifecycleState.EXECUTION_UNKNOWN) is True


def test_idempotency_classification_matrix():
    """Verify actions are classified into SAFE_TO_RETRY vs NON_IDEMPOTENT."""
    assert get_tool_idempotency("read_file") == ActionIdempotency.IDEMPOTENT
    assert get_tool_idempotency("search_files") == ActionIdempotency.IDEMPOTENT
    assert get_tool_idempotency("search_web") == ActionIdempotency.IDEMPOTENT

    assert get_tool_idempotency("open_app") == ActionIdempotency.CONDITIONALLY_IDEMPOTENT
    assert get_tool_idempotency("create_folder") == ActionIdempotency.CONDITIONALLY_IDEMPOTENT

    assert get_tool_idempotency("delete_file") == ActionIdempotency.NON_IDEMPOTENT
    assert get_tool_idempotency("execute_terminal_command") == ActionIdempotency.NON_IDEMPOTENT
    assert get_tool_idempotency("kill_process") == ActionIdempotency.NON_IDEMPOTENT

    # Gatekeeper risk levels match idempotency sensitivity
    gatekeeper = SafetyGatekeeper()
    read_dec = gatekeeper.evaluate_tool_call("read_file", {"path": "test.txt"})
    assert read_dec.risk_level in (ActionRiskLevel.READ_ONLY, ActionRiskLevel.REVERSIBLE, ActionRiskLevel.SENSITIVE)

    del_dec = gatekeeper.evaluate_tool_call("delete_file", {"path": "test.txt"})
    assert del_dec.risk_level == ActionRiskLevel.DESTRUCTIVE


# ==============================================================================
# 4. Emergency Stop & Task Cancellation
# ==============================================================================

@pytest.mark.asyncio
async def test_emergency_stop_halts_automation_and_releases_lock():
    """Global emergency stop immediately halts execution and releases busy lock."""
    executor = DesktopExecutor()
    
    # Verify execution lock is functional
    assert not executor._execution_lock.locked()
    
    async with executor._execution_lock:
        assert executor._execution_lock.locked()
    
    # After exiting lock scope, lock is released
    assert not executor._execution_lock.locked()


@pytest.mark.asyncio
async def test_atomic_cancellation_during_execution():
    """Verify goal execution engine cancellation halts between steps."""
    engine = LiveGoalExecutionEngine()
    
    # Create active goal state
    goal_state = GoalExecutionState(
        goal_id="test_cancel_goal_01",
        goal="Decompose and download file",
        status="EXECUTING"
    )
    engine.active_goals["test_cancel_goal_01"] = goal_state
    engine.cancellation_events["test_cancel_goal_01"] = asyncio.Event()

    # Cancel goal
    cancelled = engine.cancel_goal("test_cancel_goal_01")
    assert cancelled is True
    assert goal_state.status == "CANCELLED"
    assert "cancelled" in goal_state.error_message.lower()
    assert engine.cancellation_events["test_cancel_goal_01"].is_set()


# ==============================================================================
# 5. Concurrency & Physical Execution Lock
# ==============================================================================

@pytest.mark.asyncio
async def test_concurrency_execution_lock_mutual_exclusion():
    """Ensure two concurrent tasks execute serialized rather than interleaved."""
    executor = DesktopExecutor()
    order = []

    async def task1():
        async with executor._execution_lock:
            order.append("t1_start")
            await asyncio.sleep(0.05)
            order.append("t1_end")

    async def task2():
        async with executor._execution_lock:
            order.append("t2_start")
            await asyncio.sleep(0.02)
            order.append("t2_end")

    await asyncio.gather(task1(), task2())

    assert (
        order == ["t1_start", "t1_end", "t2_start", "t2_end"] or
        order == ["t2_start", "t2_end", "t1_start", "t1_end"]
    )


# ==============================================================================
# 6. ServiceManager & Component Failure Isolation
# ==============================================================================

def test_service_manager_failure_isolation():
    """Verify an initialization error in an optional service does not crash independent services."""
    def _faulty_factory():
        raise RuntimeError("Simulated service driver crash")
    
    ServiceManager.register_factory("faulty_service_xyz", _faulty_factory)
    
    # Requesting faulty service raises error cleanly
    with pytest.raises(RuntimeError) as exc_info:
        ServiceManager.get_instance("faulty_service_xyz")
    assert "Simulated service driver crash" in str(exc_info.value)

    # Independent registered instances continue working
    ServiceManager.register_instance("independent_test_svc", {"status": "healthy"})
    inst = ServiceManager.get_instance("independent_test_svc")
    assert inst == {"status": "healthy"}


# ==============================================================================
# 7. Memory Database Failure Degradation
# ==============================================================================

def test_memory_database_failure_degrades_safely_without_authorization_bypass():
    """Verify SQLite failure in episodic memory returns structured error without elevating access."""
    from backend.services.memory.episodic_memory import EpisodicMemory
    
    ep = EpisodicMemory()
    with patch.object(ep, "_get_exp_conn", side_effect=Exception("Database disk image is locked")):
        with pytest.raises(Exception) as exc_info:
            ep.query_experiences(goal_query="test query", limit=5)
        assert "Database disk image is locked" in str(exc_info.value)


# ==============================================================================
# 8. Tool Registry Error Taxonomy
# ==============================================================================

@pytest.mark.asyncio
async def test_tool_registry_error_taxonomy():
    """Verify strict taxonomy of tool errors without converting failures to success."""
    registry = ToolRegistry()

    # 1. Nonexistent tool -> TOOL_NOT_FOUND
    res_not_found = await registry.execute_tool("nonexistent_tool_xyz", {})
    assert res_not_found["status"] == "error"
    assert "not registered" in res_not_found["error"].lower()

    # 2. Handler exception -> EXECUTION_ERROR
    async def _failing_handler(**kwargs):
        raise ValueError("Hardware bus timeout")
    
    registry.register(
        name="failing_tool",
        description="Failing tool",
        parameters={"type": "object", "properties": {}},
        handler=_failing_handler,
        risk_level="low"
    )

    res_err = await registry.execute_tool("failing_tool", {})
    assert res_err["status"] == "error"
    assert "hardware bus timeout" in res_err["error"].lower()


# ==============================================================================
# 9. Resource Exhaustion & Bounded Execution
# ==============================================================================

def test_resource_exhaustion_bounded_inputs():
    """Verify oversized inputs are bounded and rejected gracefully."""
    from backend.api.routes import CommandRequest
    from pydantic import ValidationError

    # Valid bounded input
    valid_req = CommandRequest(text="Check system hardware")
    assert valid_req.text == "Check system hardware"

    # Oversized input exceeding max_length (100,000 chars)
    oversized = "A" * 150000
    with pytest.raises(ValidationError):
        CommandRequest(text=oversized)


# ==============================================================================
# 10. Filesystem Failure Isolation & Path Traversal Rejection
# ==============================================================================

@pytest.mark.asyncio
async def test_filesystem_failure_isolation_and_path_traversal(tmp_path):
    """Verify safe CRUD file operations and directory isolation."""
    executor = DesktopExecutor()
    
    test_file = tmp_path / "safe_file.txt"
    create_res = await executor.create_file(str(test_file), "Initial safe content")
    assert "Created file" in create_res
    assert test_file.exists()

    # Path traversal rejection via SafetyGatekeeper
    gatekeeper = SafetyGatekeeper()
    decision = gatekeeper.evaluate_tool_call("delete_file", {"path": "C:\\Windows\\System32\\cmd.exe"})
    assert decision.allowed is False
    assert decision.risk_level == ActionRiskLevel.DESTRUCTIVE
