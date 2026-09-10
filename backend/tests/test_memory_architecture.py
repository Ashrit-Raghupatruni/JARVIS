"""
JARVIS AI OS — Unified Memory Architecture Test Suite.

Validates the consolidated MemoryManager, WorkingMemory, LongTermMemory,
EpisodicMemory, and SemanticMemory subsystems.
"""

import pytest
import asyncio
from pathlib import Path
from backend.services.memory import (
    MemoryManager,
    MemoryService,
    WorkingMemory,
    LongTermMemory,
    EpisodicMemory,
    SemanticMemory,
    MemoryType
)


@pytest.mark.asyncio
async def test_memory_manager_initialization():
    """Verify MemoryManager initializes sub-memories and exposes standard interfaces."""
    manager = MemoryManager()
    await manager.init()

    assert manager.working is not None
    assert manager.long_term is not None
    assert manager.episodic is not None
    assert manager.semantic is not None

    # MemoryService alias check
    assert MemoryService is MemoryManager


@pytest.mark.asyncio
async def test_working_memory_turn_bounding():
    """Verify WorkingMemory adheres to max_turns sliding-window bounds and detects language."""
    wm = WorkingMemory(max_turns=3)

    wm.add_turn("user", "Hello JARVIS")
    wm.add_turn("assistant", "Greetings, sir.")
    wm.add_turn("user", "What is the weather today?")
    assert len(wm.get_turns()) == 3

    # Add 4th turn - should evict the oldest turn ("Hello JARVIS")
    wm.add_turn("assistant", "It is 22 degrees Celsius and clear.")
    turns = wm.get_turns()
    assert len(turns) == 3
    assert turns[0]["content"] == "Greetings, sir."
    assert turns[2]["content"] == "It is 22 degrees Celsius and clear."

    # Test Silent Language Detection
    wm.add_turn("user", "Bonjour, comment ca va?")
    assert wm.language.preferred_language == "fr"
    assert "French" in wm.language.get_system_prompt_instruction()


@pytest.mark.asyncio
async def test_long_term_memory_facts_and_preferences():
    """Verify LongTermMemory fact storage, retrieval, preference key-values, and knowledge graph."""
    manager = MemoryManager()
    await manager.init()

    # Preference KV
    await manager.long_term.set_user_preference("test_pref_editor", "VS Code")
    val = await manager.long_term.get_user_preference("test_pref_editor")
    assert val == "VS Code"

    # Knowledge Graph
    manager.long_term.add_relationship("Ashrit", "uses", "VS Code")
    manager.long_term.add_relationship("Ashrit", "created", "JARVIS")
    related = manager.long_term.get_related_entities("Ashrit")
    assert "VS Code" in related
    assert "JARVIS" in related

    # Fact storage
    mem_id = await manager.remember("User preferred browser is Brave Browser", metadata={"importance": "high"})
    assert mem_id.startswith("mem_")

    # Forget fact
    forget_res = await manager.forget(mem_id)
    assert forget_res.get("status") == "success"


@pytest.mark.asyncio
async def test_episodic_memory_experiences_and_strategies():
    """Verify EpisodicMemory task trace logging, success rate tracking, and strategy confidence."""
    manager = MemoryManager()
    await manager.init()

    # Experience recording
    exp = manager.store_episode(
        goal="open_notepad_and_write_note",
        result="Success: note saved",
        success=True,
        execution_time_seconds=0.45
    )
    assert exp["id"].startswith("exp_")
    assert exp["success"] is True

    # Experience querying
    past_exps = manager.episodic.query_experiences(goal_query="open_notepad", limit=5)
    assert len(past_exps) >= 1
    assert past_exps[0]["goal"] == "open_notepad_and_write_note"

    # Success rate
    rate = manager.episodic.get_success_rate("open_notepad")
    assert rate["total_attempts"] >= 1
    assert rate["success_rate"] == 1.0

    # Strategy ranking
    ranked = manager.episodic.get_ranked_strategies("ui_automation")
    assert len(ranked) >= 2
    assert ranked[0]["strategy"] == "win32_uia"

    # Task strategy outcome
    manager.episodic.record_task_strategy_outcome("navigate_settings", "win32_uia", success=True)
    best = manager.episodic.get_best_strategy_for_task("navigate_settings", "ui_automation")
    assert best["strategy"] == "win32_uia"


@pytest.mark.asyncio
async def test_semantic_memory_and_context_injection():
    """Verify SemanticMemory file parsing and consolidated context generation."""
    manager = MemoryManager()
    await manager.init()

    # Test context injection
    ctx = await manager.get_context("open note in editor")
    assert isinstance(ctx, str)
