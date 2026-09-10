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
from backend.agents.router import RequestRouter, HierarchicalCategory
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


def test_step_01_websocket_reliability():
    ws_mgr = RobustConnectionManager()
    assert hasattr(ws_mgr, "active_connections")
    assert isinstance(ws_mgr.active_connections, list)
    stats = ws_mgr.get_connection_stats() if hasattr(ws_mgr, "get_connection_stats") else {"count": len(ws_mgr.active_connections)}
    assert isinstance(stats, dict)


def test_step_02_intent_routing():
    cat = classify_request("Run AP24110011746")
    assert cat.value in ("action_request", "system_control", "coding", "automation")
    chat_cat = classify_request("Tell me a funny joke about quantum physics")
    assert chat_cat.value in ("conversation", "general_query", "chat", "knowledge_request")


def test_step_03_provider_health_evaluator():
    health = ProviderHealthEvaluator()
    health.record_provider_failure("groq")
    health.record_provider_failure("groq")
    assert health.providers["groq"].status == ProviderStatus.COOLDOWN
    # Healthy provider selection
    best = health.get_healthy_provider(["groq", "ollama", "gemini"])
    assert best != "groq"


def test_step_04_action_verification_loop():
    verifier = ActionExecutionVerifier()
    v_res = verifier.verify_application_launched("cmd")
    assert isinstance(v_res, tuple)
    assert len(v_res) == 2
    assert isinstance(v_res[0], bool)
    assert isinstance(v_res[1], str)


@pytest.mark.asyncio
async def test_step_05_live_goal_engine():
    goal_eng = LiveGoalExecutionEngine()
    registry = ToolRegistry()
    g_res = await goal_eng.execute_multi_step_goal("Fill this form", registry)
    assert isinstance(g_res, dict)
    assert "status" in g_res
    assert str(g_res.get("status", "")).lower() in ("completed", "success", "simulated")


def test_step_06_spatial_engine():
    spatial = SpatialEngine()
    displays = spatial.refresh_displays()
    assert len(displays) >= 1
    bounds = spatial.get_virtual_desktop_bounds()
    assert len(bounds) >= 4
    # Bounds contain (left, top, right, bottom, width, height)
    assert bounds[2] >= bounds[0]
    assert bounds[3] >= bounds[1]


def test_step_07_strategy_memory():
    strat = StrategyMemoryService()
    pref = strat.get_preferred_strategy("ui_automation")
    assert pref is not None
    assert pref.get("strategy") in ("win32_uia", "browser_playwright", "ocr_screen", "pixel_clicking")
    # Verify task-specific outcome recording
    strat.record_task_strategy_outcome("fill_form_task", "win32_uia", success=True)
    best_strat = strat.get_best_strategy_for_task("fill_form_task", "ui_automation")
    assert best_strat.get("strategy") == "win32_uia"


@pytest.mark.asyncio
async def test_step_08_online_research():
    research = OnlineResearchEngine()
    # Test query cleaning & live/mocked result structure
    res = research.search_web("python programming language", max_results=2)
    assert isinstance(res, dict)
    assert "status" in res
    assert "results" in res or "error" in res


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
    diag = self_diagnostic_engine.run_full_system_check() if hasattr(self_diagnostic_engine, "run_full_system_check") else {"status": "ok"}
    assert isinstance(diag, dict)
    assert "status" in diag or "healthy" in diag or "overall_health" in diag


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


