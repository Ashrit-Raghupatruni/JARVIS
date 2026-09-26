import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import os
from pathlib import Path

from backend.services.image_generator import ImageGeneratorService
from backend.services.fast_intent_router import FastIntentRouter
from backend.services.tool_registry import ToolRegistry
from backend.agents.desktop_agent import HermesDesktopAgent, HERMES_DESKTOP_SYSTEM_PROMPT
from backend.agents.hermes_agent import HermesGeneralAgent, HERMES_AGENT_SYSTEM_PROMPT
from backend.agents.hermes_orchestrator import HermesOrchestrator
from backend.services.hermes_bridge import HermesBridgeService, HermesJob
from backend.services.live_mode.failover_controller import (
    LiveModeFailoverSupervisor,
    AgentAuthorityState,
    ActionExecutionStatus
)
from backend.services.live_mode.live_goal_engine import GoalStep, LiveGoalExecutionEngine


@pytest.fixture
def image_service(tmp_path):
    output_dir = tmp_path / "media_output" / "images"
    return ImageGeneratorService(output_dir=output_dir)


@pytest.fixture
def tool_registry():
    return ToolRegistry()


@pytest.mark.asyncio
async def test_image_generator_fallback_generation(image_service):
    # Test local high-res PIL fallback when network is unavailable/mocked
    with patch("aiohttp.ClientSession.get", side_effect=Exception("Network offline")):
        result = await image_service.generate_image(
            prompt="A futuristic neon city skyline at dusk",
            style="cyberpunk",
            resolution="1024x1024"
        )
        assert result["status"] == "success"
        assert result["provider_used"] == "Local High-Res Visual Generator"
        assert "A futuristic neon city skyline at dusk" in result["prompt"]
        assert result["url"].startswith("/media/images/")
        assert os.path.exists(result["file_path"])
        assert result["markdown"].startswith("![A futuristic neon city skyline at dusk](/media/images/")


@pytest.mark.asyncio
async def test_image_generator_pollinations_success(image_service):
    # Mock aiohttp download returning valid fake image bytes (> 1000 bytes)
    fake_png_bytes = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 1200)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=fake_png_bytes)

    class MockGetContext:
        async def __aenter__(self):
            return mock_resp
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("aiohttp.ClientSession.get", return_value=MockGetContext()):
        result = await image_service.generate_image(
            prompt="A sleek futuristic autonomous vehicle",
            style="photorealistic"
        )
        assert result["status"] == "success"
        assert result["provider_used"] == "Pollinations AI (Flux Model)"
        assert os.path.exists(result["file_path"])
        assert result["url"].endswith(".png")


def test_fast_intent_router_image_generation():
    router = FastIntentRouter()
    
    prompts = [
        "generate an image of a red sports car",
        "create image of an astronaut on Mars",
        "draw a picture of a cyberpunk samurai",
        "paint an image of a serene mountain lake",
        "generate picture of AI neural core"
    ]
    
    for prompt in prompts:
        route = router.classify(prompt)
        assert route is not None, f"Failed to classify: {prompt}"
        assert route.is_atomic is True
        assert route.tool_name == "generate_image", f"Expected generate_image, got {route.tool_name} for '{prompt}'"
        assert "prompt" in route.tool_params


@pytest.mark.asyncio
async def test_tool_registry_generate_image_and_hermes_tools(tool_registry):
    # Verify tools in registry
    assert "generate_image" in tool_registry._tools
    assert "hermes_agent_task" in tool_registry._tools
    assert "hermes_orchestrator_task" in tool_registry._tools
    assert "hermes_bridge_task" in tool_registry._tools
    assert "hermes_async_task" in tool_registry._tools
    assert "live_mode_execute_task" in tool_registry._tools
    assert "live_mode_emergency_stop" in tool_registry._tools


@pytest.mark.asyncio
async def test_hermes_desktop_agent_action_parsing():
    agent = HermesDesktopAgent()
    assert "open_app" in HERMES_DESKTOP_SYSTEM_PROMPT
    assert "open_file" in HERMES_DESKTOP_SYSTEM_PROMPT
    assert "focus_window" in HERMES_DESKTOP_SYSTEM_PROMPT
    assert "type_text" in HERMES_DESKTOP_SYSTEM_PROMPT

    raw_response = '''
    ```json
    {
      "action": "open_app",
      "app_name": "notepad",
      "reasoning": "Open text editor"
    }
    ```
    '''
    action = agent._parse_action_json(raw_response)
    assert action is not None
    assert action["action"] == "open_app"
    assert action["app_name"] == "notepad"


@pytest.mark.asyncio
async def test_hermes_desktop_agent_execution_mock():
    agent = HermesDesktopAgent()
    mock_llm_response = '''
    {
      "action": "finish",
      "summary": "Desktop automation task completed successfully."
    }
    '''
    
    with patch.object(agent, "_query_hermes_model", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_llm_response
        result = await agent.execute_task("Open calculator and compute something")
        assert result["status"] == "success"
        assert result["completed"] is True
        assert "completed successfully" in result["summary"]


@pytest.mark.asyncio
async def test_hermes_general_agent_tool_calling(tool_registry):
    agent = HermesGeneralAgent(tool_registry=tool_registry)
    
    step1_response = '```json\n{"thought": "Check status", "tool": "get_system_status", "parameters": {}}\n```'
    step2_response = '```json\n{"action": "finish", "summary": "All systems operating at peak performance."}\n```'
    
    with patch.object(agent, "_query_hermes_model", new_callable=AsyncMock) as mock_query:
        mock_query.side_effect = [step1_response, step2_response]
        result = await agent.execute_task("Check system health")
        assert result["status"] == "success"
        assert len(result["steps"]) == 2
        assert "operating at peak performance" in result["summary"]


@pytest.mark.asyncio
async def test_hermes_orchestrator_routing_and_collaborative():
    desktop_agent = HermesDesktopAgent()
    general_agent = HermesGeneralAgent()
    orchestrator = HermesOrchestrator(desktop_agent=desktop_agent, general_agent=general_agent)
    
    assert orchestrator.classify_intent("click the submit button on screen") == "desktop"
    assert orchestrator.classify_intent("analyze this python codebase and summarize") == "general"
    
    with patch.object(desktop_agent, "execute_task", new_callable=AsyncMock) as mock_desk, \
         patch.object(general_agent, "execute_task", new_callable=AsyncMock) as mock_gen:
        
        mock_desk.return_value = {"status": "success", "completed": True, "summary": "Clicked button", "steps": [{"step": 1}]}
        mock_gen.return_value = {"status": "success", "completed": True, "summary": "Explained concept", "steps": [{"step": 1}]}
        
        res_desk = await orchestrator.run_task("open notepad and click edit", mode="auto")
        assert res_desk["orchestration_mode"] == "hermes-desktop"
        
        res_collab = await orchestrator.run_task("Prepare meeting agenda and open notepad", mode="collaborative")
        assert res_collab["orchestration_mode"] == "collaborative"
        assert res_collab["status"] == "success"


@pytest.mark.asyncio
async def test_failover_supervisor_primary_success(tool_registry):
    primary_engine = LiveGoalExecutionEngine()
    fallback_agent = HermesDesktopAgent()
    supervisor = LiveModeFailoverSupervisor(primary_engine=primary_engine, fallback_agent=fallback_agent)
    
    # Mock primary steps executing successfully
    with patch.object(tool_registry, "execute_tool", new_callable=AsyncMock) as mock_exec, \
         patch.object(tool_registry, "get_tool", return_value=True):
        mock_exec.return_value = {"status": "success", "output": "ok"}
        
        result = await supervisor.execute_with_failover(
            goal="open chrome and open notepad",
            tool_registry=tool_registry
        )
        assert result["status"] == "success"
        assert result["failover_occurred"] is False
        assert result["primary_agent"] == "JARVIS Desktop"
        assert len(result["completed_steps"]) > 0


@pytest.mark.asyncio
async def test_failover_supervisor_automatic_failover(tool_registry):
    primary_engine = LiveGoalExecutionEngine()
    fallback_agent = HermesDesktopAgent()
    supervisor = LiveModeFailoverSupervisor(primary_engine=primary_engine, fallback_agent=fallback_agent)
    
    # Simulate step 1 success, step 2 failure in primary
    step_call_count = 0
    async def mock_tool_execution(tool_name, params):
        nonlocal step_call_count
        step_call_count += 1
        if step_call_count == 1:
            return {"status": "success", "message": "App launched"}
        else:
            return {"status": "error", "message": "Element not found / window hung"}

    hermes_recovery_response = {
        "status": "success",
        "completed": True,
        "summary": "Hermes recovered and completed remaining steps.",
        "steps": [{"step": 2, "action": "focus_and_click", "result": "recovered"}]
    }

    with patch.object(tool_registry, "execute_tool", side_effect=mock_tool_execution), \
         patch.object(tool_registry, "get_tool", return_value=True), \
         patch.object(fallback_agent, "execute_task", new_callable=AsyncMock) as mock_hermes_task, \
         patch.object(fallback_agent, "get_active_screen_context", new_callable=AsyncMock) as mock_ctx:
        
        mock_ctx.return_value = {"foreground_window": "Chrome"}
        mock_hermes_task.return_value = hermes_recovery_response
        
        result = await supervisor.execute_with_failover(
            goal="open chrome and click repository",
            tool_registry=tool_registry
        )
        
        # Verify automatic failover took place
        assert result["status"] == "success"
        assert result["failover_occurred"] is True
        assert result["failed_step"] is not None
        assert "Hermes Desktop took over" in result["summary"]
        assert len(supervisor.handoff_history) == 1
        assert supervisor.handoff_history[0].from_agent == "JARVIS Desktop"
        assert supervisor.handoff_history[0].to_agent == "Hermes Desktop"


@pytest.mark.asyncio
async def test_failover_supervisor_emergency_stop():
    supervisor = LiveModeFailoverSupervisor()
    stop_result = supervisor.emergency_stop()
    
    assert stop_result["status"] == "stopped"
    assert supervisor.current_authority == AgentAuthorityState.CANCELLED
    assert "Manual Override" in supervisor.active_agent_name


@pytest.mark.asyncio
async def test_failover_supervisor_dual_failure(tool_registry):
    primary_engine = LiveGoalExecutionEngine()
    fallback_agent = HermesDesktopAgent()
    supervisor = LiveModeFailoverSupervisor(primary_engine=primary_engine, fallback_agent=fallback_agent)
    
    # Primary fails
    async def mock_primary_fail(tool_name, params):
        return {"status": "error", "message": "Primary hardware fault"}

    # Hermes also fails
    hermes_fail_response = {
        "status": "failed",
        "completed": False,
        "summary": "Hermes was unable to recover the action."
    }

    with patch.object(tool_registry, "execute_tool", side_effect=mock_primary_fail), \
         patch.object(tool_registry, "get_tool", return_value=True), \
         patch.object(fallback_agent, "execute_task", new_callable=AsyncMock) as mock_hermes_task:
        
        mock_hermes_task.return_value = hermes_fail_response
        
        result = await supervisor.execute_with_failover(
            goal="open obscure_app and perform action",
            tool_registry=tool_registry
        )
        
        assert result["status"] == "failed"
        assert result["failover_occurred"] is True
        assert result["requires_user_intervention"] is True
        assert "Dual Agent Failure" in result["summary"]
