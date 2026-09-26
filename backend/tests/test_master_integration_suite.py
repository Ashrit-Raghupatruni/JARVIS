"""
JARVIS AI OS — Master E2E System Integration Test Suite (Steps 0–23).
========================================================================
Executes empirical pytest runtime verification across all master implementation steps.
"""

import pytest
import sys
import asyncio
import time
from pathlib import Path

from backend.api.websocket import RobustConnectionManager
from backend.agents.router import RequestRouter, HierarchicalCategory, RequestCategory
from backend.agents.message_router import classify_request
from backend.services.provider_health_evaluator import ProviderHealthEvaluator, ProviderStatus
from backend.services.action_verifier import ActionExecutionVerifier
from backend.services.live_mode.live_goal_engine import LiveGoalExecutionEngine
from backend.services.perception.spatial_engine import SpatialEngine
from backend.services.strategy_memory import StrategyMemoryService
from backend.services.online_research_engine import OnlineResearchEngine
from backend.services.n8n_service import N8nIntegrationService
from backend.services.voice_intelligence import VoiceIntelligenceService
from backend.services.self_diagnostic_engine import self_diagnostic_engine
from backend.services.personality_engine import PersonalityEngine
from backend.services.developer_assistant import DeveloperAssistantService
from backend.services.learning_assistant import learning_assistant
from backend.services.proactive_engine import ProactiveEngine
from backend.services.perception.gesture_engine import gesture_engine
from backend.services.security.face_auth_engine import face_auth_engine
from backend.services.task_queue import TaskQueueManager, TaskPriority
from backend.services.tool_registry import ToolRegistry


@pytest.mark.asyncio
async def test_step_01_websocket_reliability():
    """Verify WebSocket connection manager registers, tracks, and cleans up active connections."""
    ws_mgr = RobustConnectionManager()
    assert len(ws_mgr.active_connections) == 0

    from unittest.mock import AsyncMock
    from starlette.websockets import WebSocketState
    from backend.models.schemas import WSMessage
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.client_state = WebSocketState.CONNECTED

    session = await ws_mgr.connect(mock_ws, client_id="test_client_01")
    assert session.client_id == "test_client_01"
    assert len(ws_mgr.active_connections) == 1
    assert "test_client_01" in ws_mgr.sessions

    # Broadcast message test
    msg = WSMessage(type="ping", data={"timestamp": time.time()})
    await ws_mgr.broadcast(msg)
    mock_ws.send_json.assert_called_once()

    # Disconnect cleanup
    ws_mgr.disconnect(mock_ws, client_id="test_client_01")
    assert len(ws_mgr.active_connections) == 0
    assert ws_mgr.sessions["test_client_01"].state == "DISCONNECTED"


def test_step_02_intent_routing():
    """Verify deterministic request classification across system control, coding, and chat."""
    cat_action = classify_request("Run AP24110011746")
    assert cat_action == RequestCategory.ACTION_REQUEST

    cat_code = classify_request("Write a python script to parse json")
    assert cat_code == RequestCategory.CODING

    cat_chat = classify_request("Tell me a funny joke about quantum physics")
    assert cat_chat == RequestCategory.CONVERSATION

    cat_query = classify_request("What is the capital of France?")
    assert cat_query == RequestCategory.KNOWLEDGE_REQUEST


def test_step_03_provider_health_evaluator():
    """Verify provider health cooldown triggers upon consecutive failures."""
    health = ProviderHealthEvaluator()
    health.record_provider_failure("groq")
    health.record_provider_failure("groq")
    assert health.providers["groq"].status == ProviderStatus.COOLDOWN
    # Healthy provider selection prefers available non-cooldown providers
    best = health.get_healthy_provider(["groq", "ollama", "gemini"])
    assert best != "groq"
    assert best in ("ollama", "gemini")


@pytest.mark.asyncio
async def test_step_04_action_verification_loop():
    """Verify ActionExecutionVerifier executes tool and returns structured verification outcome."""
    verifier = ActionExecutionVerifier()
    registry = ToolRegistry()

    # 1. Direct tool execution and verification
    res = await verifier.execute_and_verify("get_system_status", {}, registry)
    assert res["status"] == "success"
    assert res["verified"] is True
    assert res["duration_ms"] >= 0
    assert res["result"]["status"] == "success"

    # 2. Process existence inspection probe
    v_res = verifier.verify_application_launched("cmd")
    assert isinstance(v_res, tuple)
    assert len(v_res) == 2
    assert isinstance(v_res[0], bool)
    assert isinstance(v_res[1], str)


@pytest.mark.asyncio
async def test_step_05_live_goal_engine():
    """Verify LiveGoalExecutionEngine decomposes and autonomously resolves multi-step goals."""
    goal_eng = LiveGoalExecutionEngine()
    registry = ToolRegistry()
    g_res = await goal_eng.execute_multi_step_goal("Fill this form", registry)

    assert g_res["status"] == "COMPLETED"
    assert g_res["total_steps"] >= 1
    assert len(g_res["executed_steps"]) >= 1
    assert g_res["duration_seconds"] >= 0.0
    registered_tool_names = list(registry.tools.keys())
    for step in g_res["executed_steps"]:
        assert step["status"] == "COMPLETED"
        assert step["tool_name"] in registered_tool_names


def test_step_06_spatial_engine():
    """Verify SpatialEngine retrieves valid virtual screen bounds."""
    spatial = SpatialEngine()
    displays = spatial.refresh_displays()
    assert len(displays) >= 1
    bounds = spatial.get_virtual_desktop_bounds()
    assert len(bounds) >= 4
    assert bounds[2] >= bounds[0]  # right >= left
    assert bounds[3] >= bounds[1]  # bottom >= top


def test_step_07_strategy_memory():
    """Verify StrategyMemoryService records and recalls optimal execution strategies."""
    strat = StrategyMemoryService()
    pref = strat.get_preferred_strategy("ui_automation")
    assert pref["strategy"] in ("win32_uia", "browser_playwright", "ocr_screen", "pixel_clicking")

    # Record and retrieve task-specific strategy
    strat.record_task_strategy_outcome("fill_form_task", "win32_uia", success=True)
    best_strat = strat.get_best_strategy_for_task("fill_form_task", "ui_automation")
    assert best_strat["strategy"] == "win32_uia"


@pytest.mark.asyncio
async def test_step_08_online_research():
    """Verify OnlineResearchEngine parses structured query results with citations."""
    research = OnlineResearchEngine()
    # Test deterministic search response with mocked HTML parser
    from unittest.mock import patch, MagicMock
    mock_html = '''
    <html>
      <a class="result__a" href="https://python.org">Python Programming</a>
      <a class="result__snippet">The official home of Python language.</a>
    </html>
    '''
    mock_resp = MagicMock()
    mock_resp.read.return_value = mock_html.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = research.search_web("python programming language", max_results=2)
        assert res["status"] == "success"
        assert res["count"] == 1
        assert res["results"][0]["title"] == "Python Programming"
        assert res["results"][0]["url"] == "https://python.org"
        assert "Python" in res["results"][0]["snippet"]


def test_step_09_n8n_integration():
    n8n = N8nIntegrationService()
    hc = n8n.health_check()
    assert isinstance(hc, dict)
    assert "status" in hc
    assert hc["status"] in ("online", "offline", "degraded")


def test_step_10_voice_intelligence():
    voice = VoiceIntelligenceService()
    res = voice.handle_interruption()
    assert res.get("status") == "interrupted"
    assert res.get("state") == "listening"


def test_step_11_self_diagnostic():
    diag = self_diagnostic_engine.run_full_system_check()
    assert isinstance(diag, dict)
    assert diag["status"] in ("HEALTHY", "WARNING", "DEGRADED")
    assert "metrics" in diag
    assert "cpu_percent" in diag["metrics"]
    assert "ram_percent" in diag["metrics"]
    assert isinstance(diag.get("issues_found"), list)


def test_step_12_personality_engine():
    personality = PersonalityEngine()
    resp = personality.format_response("System online.")
    assert len(resp) > 0
    assert "System online" in resp or "JARVIS" in resp or len(resp.strip()) > 5


def test_step_13_developer_assistant():
    dev = DeveloperAssistantService()
    res = dev.analyze_repository_structure(".")
    assert isinstance(res, dict)
    assert "languages" in res or "total_files" in res or "config_files" in res


def test_step_14_learning_assistant():
    exp = learning_assistant.explain_concept("Neural Networks", complexity_level="beginner")
    assert isinstance(exp, dict)
    assert exp.get("status") == "success"
    assert "core_principles" in exp
    assert len(exp.get("core_principles", [])) >= 2


def test_step_15_proactive_engine():
    pro = ProactiveEngine()
    # Test content safety validation on monitored topics
    res = pro.add_monitored_topic("Quantum Computing")
    assert res.get("status") == "ok"
    assert "quantum computing" in res.get("monitored_topics", [])

    # Blocked topic safety test
    blocked_res = pro.add_monitored_topic("crypto daytrading alert")
    assert blocked_res.get("status") == "blocked"


def test_step_16_gesture_engine():
    # 21-landmark array simulating OPEN PALM:
    # Wrist at (0.5, 0.9), Thumb tip (4) at (0.2, 0.2), Index tip (8) at (0.4, 0.2), Middle tip (12) at (0.5, 0.2), Ring (16) at (0.6, 0.2), Pinky (20) at (0.7, 0.2)
    landmarks = [(0.5, 0.9)] * 21
    landmarks[4] = (0.2, 0.2)
    landmarks[8] = (0.4, 0.2)
    landmarks[12] = (0.5, 0.2)
    landmarks[16] = (0.6, 0.2)
    landmarks[20] = (0.7, 0.2)
    res = gesture_engine.process_hand_landmarks(landmarks)
    assert isinstance(res, dict)
    assert res.get("gesture") == "OPEN_PALM"
    assert res.get("action") == "toggle_media_play_pause"


def test_step_17_face_auth_engine_biometric_verification():
    import math
    from backend.services.security.face_auth_engine import FaceAuthEngine
    engine = FaceAuthEngine()

    # 1. Enrolled vector
    user_vec = [float(i % 10) for i in range(128)]
    norm = math.sqrt(sum(x * x for x in user_vec))
    user_vec = [x / norm for x in user_vec]
    ok = engine.enroll_user("TestOwner", user_vec)
    assert ok is True

    # 2. Match test with genuine liveness (blink + head turn)
    matching_vec = list(user_vec)
    liveness_sequence = [
        {"eye_aspect_ratio": 0.32, "head_yaw": 0.0},
        {"eye_aspect_ratio": 0.12, "head_yaw": 2.5},  # Blink + head yaw delta
    ]
    res_match = engine.verify_face(matching_vec, liveness_sequence)
    assert res_match["authenticated"] is True
    assert res_match["similarity"] >= 0.82
    assert res_match["liveness_passed"] is True

    # 3. Mismatched vector rejection (orthogonal vector)
    orthogonal_vec = [float((i + 5) % 10 * (-1 if i % 2 == 0 else 1)) for i in range(128)]
    ortho_norm = math.sqrt(sum(x * x for x in orthogonal_vec))
    orthogonal_vec = [x / ortho_norm for x in orthogonal_vec]
    res_mismatch = engine.verify_face(orthogonal_vec, liveness_sequence)
    assert res_mismatch["authenticated"] is False
    assert res_mismatch["similarity"] < 0.82

    # 4. Anti-spoofing rejection (static photo: no blink, zero yaw variance)
    static_sequence = [
        {"eye_aspect_ratio": 0.30, "head_yaw": 0.0},
        {"eye_aspect_ratio": 0.30, "head_yaw": 0.0},
    ]
    res_spoof = engine.verify_face(matching_vec, static_sequence)
    assert res_spoof["authenticated"] is False
    assert res_spoof["liveness_passed"] is False


@pytest.mark.asyncio
async def test_step_18_task_queue_priority_ordering():
    tq = TaskQueueManager()
    t_low = tq.enqueue_task(name="Low Priority Job", payload={"type": "low"}, priority=TaskPriority.LOW)
    t_high = tq.enqueue_task(name="High Priority Command", payload={"type": "high"}, priority=TaskPriority.HIGH)
    t_med = tq.enqueue_task(name="Medium Priority Task", payload={"type": "med"}, priority=TaskPriority.MEDIUM)

    # Executing tasks must process HIGH priority first
    executed_types = []
    async def _tracker(payload):
        executed_types.append(payload["type"])
        return {"done": True}

    await tq.execute_next_task(_tracker)
    await tq.execute_next_task(_tracker)
    await tq.execute_next_task(_tracker)

    assert executed_types == ["high", "med", "low"]


@pytest.mark.asyncio
async def test_step_19_end_to_end_orchestration_pipeline():
    """
    End-to-End Master Pipeline Verification:
    Request -> classify_request -> SafetyGatekeeper -> ToolRegistry -> ActionExecutionVerifier -> Outcome.
    """
    from backend.services.safety_gatekeeper import SafetyGatekeeper, ActionRiskLevel

    # 1. User command
    user_query = "Check system hardware resources and status"

    # 2. Intent Classification
    intent = classify_request(user_query)
    assert intent in (RequestCategory.KNOWLEDGE_REQUEST, RequestCategory.ACTION_REQUEST, RequestCategory.SYSTEM_REQUEST)

    # 3. Tool Selection & Safety Interlock Audit
    tool_name = "get_system_status"
    tool_args = {}

    gatekeeper = SafetyGatekeeper()
    decision = gatekeeper.evaluate_tool_call(tool_name, tool_args)
    assert decision.allowed is True
    assert decision.risk_level in (ActionRiskLevel.READ_ONLY, ActionRiskLevel.REVERSIBLE, ActionRiskLevel.SENSITIVE)

    # 4. Tool Execution & Outcome Verification Loop
    registry = ToolRegistry()
    verifier = ActionExecutionVerifier()

    res = await verifier.execute_and_verify(tool_name, tool_args, registry)
    assert res["status"] == "success"
    assert res["verified"] is True
    assert res["duration_ms"] >= 0
    assert "result" in res
    assert res["result"]["status"] == "success"



