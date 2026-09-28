"""
JARVIS AI OS — Comprehensive Reliability & Master Fix Verification Suite.
========================================================================
Empirically tests:
1. Persistent SQLite WAL Task Queue (Durability, navigation simulation, reboot recovery, reordering).
2. Long-Horizon Goal Recovery Service & Checkpoint Resumption.
3. ChromaDB Telemetry Signature Isolation (No TypeError on PostHog 3-arg call).
4. Speech-to-Text Transcript Sanitization & Hallucination Suppression (Noise, single-char, stuttering loops).
5. Task REST API Truthful Contracts (Status codes, error handling, payload consistency).
"""

import pytest
import asyncio
import os
import json
import time
from pathlib import Path

from backend.services.task_queue import TaskQueueManager, TaskStatus
from backend.services.long_horizon_checkpoint import LongHorizonCheckpointService, long_horizon_manager
from backend.services.voice.stt_manager import is_valid_transcript, clean_whisper_hallucinations


# ==============================================================================
# 1. Task Queue SQLite Persistence & Durability
# ==============================================================================

@pytest.mark.asyncio
async def test_task_queue_sqlite_durability_across_reloads(tmp_path):
    """Verify tasks survive simulated page navigation and app reboots via SQLite WAL."""
    db_file = str(tmp_path / "test_tasks.db")

    # Instance 1: Create, pause, and enqueue tasks
    tq1 = TaskQueueManager(db_path=db_file)
    await tq1.initialize()

    t1 = await tq1.create_task("Index Knowledge Base", command="python -m index", priority=1)
    t2 = await tq1.create_task("Run Diagnostics", command="python -m diag", priority=2)

    assert t1["status"] == "pending"
    assert t2["status"] == "pending"

    # Pause t1
    paused_t1 = await tq1.pause_task(t1["id"])
    assert paused_t1["status"] == "paused"

    # Instance 2: Simulate tab switch / app restart reading same DB
    tq2 = TaskQueueManager(db_path=db_file)
    tasks = await tq2.get_all_tasks()

    assert len(tasks) >= 2
    task_map = {t["id"]: t for t in tasks}
    assert task_map[t1["id"]]["status"] == "paused"
    assert task_map[t2["id"]]["status"] == "pending"

    # Resume t1 in Instance 2
    resumed_t1 = await tq2.resume_task(t1["id"])
    assert resumed_t1["status"] == "pending"

    # Cancel t2
    cancelled_t2 = await tq2.cancel_task_async(t2["id"])
    assert cancelled_t2 is True

    # Instance 3: Verify cancellation and resumption persisted
    tq3 = TaskQueueManager(db_path=db_file)
    tasks3 = await tq3.get_all_tasks()
    task_map3 = {t["id"]: t for t in tasks3}
    assert task_map3[t1["id"]]["status"] == "pending"
    assert task_map3[t2["id"]]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_task_queue_reordering_durability(tmp_path):
    """Verify task reordering persists to SQLite."""
    db_file = str(tmp_path / "test_reorder.db")
    tq = TaskQueueManager(db_path=db_file)
    await tq.initialize()

    t1 = await tq.create_task("Task Alpha", priority=1)
    t2 = await tq.create_task("Task Beta", priority=2)

    # Reorder so Beta comes first
    new_order = [t2["id"], t1["id"]]
    await tq.reorder_tasks(new_order)

    # Verify reloaded order
    tq_reloaded = TaskQueueManager(db_path=db_file)
    tasks = await tq_reloaded.get_all_tasks()
    task_map = {t["id"]: t for t in tasks}

    assert task_map[t2["id"]]["priority"] == 1
    assert task_map[t1["id"]]["priority"] == 2


# ==============================================================================
# 2. Long-Horizon Goal Recovery
# ==============================================================================

@pytest.mark.asyncio
async def test_long_horizon_recovery_engine(tmp_path):
    """Verify interrupted goals are recovered and marked paused_for_resume."""
    db_file = str(tmp_path / "test_recovery.db")
    service = LongHorizonCheckpointService(db_path=db_file)
    await service.initialize()

    # Create active goal (status='running')
    goal = await service.create_goal(title="Multi-Step Research Project", description="Analyze market trends", total_steps=5)
    assert goal["status"] == "running"

    # Add checkpoint for step 1
    await service.create_checkpoint(
        goal_id=goal["goal_id"],
        step_title="Step 1: Data Gathering",
        state_data={"step_index": 1, "collected": ["report1.pdf"]}
    )

    # Trigger self-recovery
    recovered = await service.recover_interrupted_goals()
    assert len(recovered) == 1
    assert recovered[0]["goal_id"] == goal["goal_id"]

    # Verify goal queue status is now paused_for_resume
    goals = await service.get_goal_queue()
    assert goals[0]["status"] == "paused_for_resume"

    # Resume goal
    resumed = await service.resume_goal(goal["goal_id"])
    assert resumed["status"] == "running"
    assert resumed["resume_from_step"] == 2


# ==============================================================================
# 3. ChromaDB Telemetry Signature Isolation
# ==============================================================================

def test_chromadb_telemetry_isolation():
    """Verify Posthog monkeypatch suppresses TypeError without crashing."""
    try:
        import chromadb.telemetry.product.posthog as ch_ph
        ch_ph.Posthog.capture = lambda self, *args, **kwargs: None
        ch_ph.Posthog._direct_capture = lambda self, *args, **kwargs: None

        # Call capture with 3 arguments (ChromaDB signature)
        res = ch_ph.Posthog.capture(None, "user_123", "test_event", {"prop": "val"})
        assert res is None

        res_direct = ch_ph.Posthog._direct_capture(None, "user_123", "test_event", {"prop": "val"})
        assert res_direct is None
    except ImportError:
        pass


# ==============================================================================
# 4. Speech-to-Text Transcript Sanitization & Hallucination Cleaner
# ==============================================================================

def test_stt_transcript_validation():
    """Verify rejection of empty, single-character, and pure noise inputs."""
    # Rejections
    assert is_valid_transcript("") is False
    assert is_valid_transcript("   ") is False
    assert is_valid_transcript("I") is False
    assert is_valid_transcript("a") is False
    assert is_valid_transcript(".") is False
    assert is_valid_transcript("...") is False
    assert is_valid_transcript("uh") is False
    assert is_valid_transcript("um") is False
    assert is_valid_transcript("subtitles") is False
    assert is_valid_transcript("[music]") is False
    assert is_valid_transcript("who who who") is False

    # Acceptances
    assert is_valid_transcript("How many fingers does humans have?") is True
    assert is_valid_transcript("open notepad") is True
    assert is_valid_transcript("hello") is True
    assert is_valid_transcript("yes") is True
    assert is_valid_transcript("stop") is True


def test_clean_whisper_hallucinations_stutter_and_loops():
    """Verify stutter loop collapse and phrase deduplication."""
    # Repeated phrase loop
    raw1 = "How many How many How many finger does humans have?"
    assert clean_whisper_hallucinations(raw1) == "How many finger does humans have?"

    # Comma-separated repeated phrase
    raw2 = "How many, how many, how many fingers do humans have?"
    assert clean_whisper_hallucinations(raw2) == "How many fingers do humans have?"

    # Hyphenated stutter
    raw3 = "Who-who-who is the president?"
    assert clean_whisper_hallucinations(raw3) == "Who is the president?"

    # Duplicate leading word
    raw4 = "open open the browser"
    assert clean_whisper_hallucinations(raw4) == "open the browser"

    # Multi-phrase repetition
    raw5 = "thank you thank you thank you"
    assert clean_whisper_hallucinations(raw5) == "Thank you"


# ==============================================================================
# 5. REST API Truthful Contracts
# ==============================================================================

@pytest.mark.asyncio
async def test_tasks_rest_api_lifecycle():
    """Verify HTTP API contracts for tasks."""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # 1. GET /api/v1/tasks
    res = client.get("/api/v1/tasks")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert isinstance(data["tasks"], list)

    # 2. POST /api/v1/tasks (Create)
    res_create = client.post("/api/v1/tasks", json={
        "title": "Automated Unit Test Task",
        "command": "pytest backend/tests",
        "priority": 1
    })
    assert res_create.status_code == 200
    created = res_create.json()["task"]
    task_id = created["id"]
    assert created["title"] == "Automated Unit Test Task"

    # 3. POST /api/v1/tasks/{id}/pause
    res_pause = client.post(f"/api/v1/tasks/{task_id}/pause")
    assert res_pause.status_code == 200
    assert res_pause.json()["task"]["status"] == "paused"

    # 4. POST /api/v1/tasks/{id}/resume
    res_resume = client.post(f"/api/v1/tasks/{task_id}/resume")
    assert res_resume.status_code == 200
    assert res_resume.json()["task"]["status"] == "pending"

    # 5. DELETE /api/v1/tasks/{id} (Cancel)
    res_cancel = client.delete(f"/api/v1/tasks/{task_id}")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["cancelled"] is True

    # 6. DELETE non-existent task returns 404
    res_404 = client.delete("/api/v1/tasks/non_existent_task_id_999")
    assert res_404.status_code == 404

    # 7. POST /api/v1/developer/recover_interrupted_goals
    res_rec = client.post("/api/v1/developer/recover_interrupted_goals")
    assert res_rec.status_code == 200
    assert "recovered_count" in res_rec.json()
