import asyncio
import os
import tempfile
from backend.services.agent_ecosystem import AgentEcosystemService
from backend.services.long_horizon_checkpoint import LongHorizonCheckpointService
from backend.services.kv_cache_pruner import KVCachePruner


async def test_agent_ecosystem_spawning_and_ipc():
    """Test real sub-agent spawning for CodeAgent, ResearchAgent, SecurityAgent, and IPC bus."""
    ecosystem = AgentEcosystemService()

    # Spawn specialized CodeAgent
    code_agent = ecosystem.spawn_subagent("CodeAgent", "Refactor backend API endpoints")
    assert code_agent["role"] == "CodeAgent"
    assert code_agent["status"] in ["idle", "running", "completed"]

    # Spawn SecurityAgent
    sec_agent = ecosystem.spawn_subagent("SecurityAgent", "Verify sandbox policy")
    assert sec_agent["role"] == "SecurityAgent"

    agents = ecosystem.get_all_agents()
    assert len(agents) == 2

    # Send IPC Message
    ipc_msg = await ecosystem.send_ipc_message(
        sender="CodeAgent",
        recipient="SecurityAgent",
        content="Requesting permission to write file",
        message_type="request"
    )
    assert ipc_msg["sender"] == "CodeAgent"
    assert ipc_msg["recipient"] == "SecurityAgent"

    # Allow background execution step
    await asyncio.sleep(0.8)

    history = ecosystem.get_ipc_history()
    assert len(history) >= 2


async def test_long_horizon_checkpoint_service():
    """Test persistent goal queue and multi-day checkpoints in SQLite WAL."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        service = LongHorizonCheckpointService(db_path=db_path)
        await service.initialize()

        # Create Goal
        goal = await service.create_goal("Build Autonomous AI Agent", description="Multi-day build", total_steps=5)
        assert goal["title"] == "Build Autonomous AI Agent"
        assert goal["status"] == "running"

        # Create Checkpoint
        chk = await service.create_checkpoint(
            goal_id=goal["goal_id"],
            step_title="Architecture Approved",
            state_data={"step_index": 1, "status": "running"}
        )
        assert chk["goal_id"] == goal["goal_id"]

        # Fetch Checkpoints
        checkpoints = await service.get_checkpoints_for_goal(goal["goal_id"])
        assert len(checkpoints) >= 2

        # Update Goal Status
        updated = await service.set_goal_status(goal["goal_id"], "paused")
        assert updated is True

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_kv_cache_pruner():
    """Test KV-cache pruning and token compression metrics."""
    pruner = KVCachePruner(max_context_tokens=50)

    very_long_content = "Detailed execution log payload " * 100  # ~3100 chars -> ~775 tokens
    messages = [
        {"role": "system", "content": "You are JARVIS."},
        {"role": "user", "content": very_long_content},
        {"role": "assistant", "content": very_long_content},
        {"role": "user", "content": very_long_content},
        {"role": "assistant", "content": very_long_content},
        {"role": "user", "content": "Final question"}
    ]

    res = pruner.evaluate_and_prune(messages, target_token_budget=100)
    assert res["pruned"] is True
    assert res["final_tokens"] < res["original_tokens"]

    metrics = pruner.get_metrics()
    assert metrics["total_prune_events"] == 1
    assert metrics["pruned_tokens_saved"] > 0


async def test_security_sandbox():
    """Test SecuritySandbox execution rules, key scrubbing, and timeout protection."""
    from backend.services.security.sandbox import SecuritySandbox
    sandbox = SecuritySandbox(timeout_limit=2.0)
    
    # Test rejection of destructive patterns
    res = await sandbox.execute_shell("rmdir /s /q C:\\Windows")
    assert "Error:" in res.stderr
    assert res.exit_code == -1
    
    # Test environment variable sanitization
    os.environ["GEMINI_API_KEY"] = "sk-test-secret-gemini-key"
    env = sandbox._get_sanitized_env()
    assert "GEMINI_API_KEY" not in env
    
    # Test execution of simple script in sandbox
    res_py = await sandbox.execute_python("print('Hello Sandbox')")
    assert "Hello Sandbox" in res_py.stdout
    assert res_py.exit_code == 0


def test_security_rbac_classify():
    """Test SecurityOrchestrator command level classification and secrets masking."""
    from backend.services.security.rbac import SecurityOrchestrator
    from backend.utils.event_bus import EventBus
    
    bus = EventBus()
    orch = SecurityOrchestrator(event_bus=bus)
    
    # Check command levels
    assert orch.classify_command("git status") == "SAFE"
    assert orch.classify_command("npm install pandas") == "CONFIRM"
    assert orch.classify_command("rmdir /s /q test") == "DANGEROUS"
    
    # Check secrets masking
    raw_text = "My key is sk-test-secret-gemini-key-xyz"
    masked = orch.mask_secrets(raw_text, ["sk-test-secret-gemini-key-xyz"])
    assert "[REDACTED]" in masked
    assert "sk-test-secret-gemini-key-xyz" not in masked

