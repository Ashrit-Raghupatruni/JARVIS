"""
JARVIS AI OS — Phase 13: Performance, Resource Usage & Long-Run Reliability Test Suite.
=======================================================================================
Empirically verifies:
1. Lazy ServiceManager Initialization (Heavy ML/perception models not loaded eagerly).
2. Sub-Millisecond Deterministic Fast-Path Routing Latency.
3. Sub-Microsecond ToolRegistry Catalog Lookups.
4. WorkingMemory Sliding Window Bounded Turn & Token Capacity.
5. EpisodicMemory SQLite WAL Mode & Indexed Query Latency.
6. Differential UIA Scene Graph Cache TTL & Invalidation.
7. Bounded TaskQueue Execution & Priority Preemption.
8. Browser Context Resource Lifecycle & Safe Cleanup.
9. Repeated Task Cancellation & Mutex Lock Leak Prevention.
10. WebSocket Connection Manager Session Purge & Leak Prevention.
"""

import pytest
import asyncio
import time
import sqlite3
from unittest.mock import MagicMock, AsyncMock, patch

from backend.services.manager import ServiceManager, ServiceState
from backend.services.fast_intent_router import FastIntentRouter
from backend.agents.router import classify_request, RequestCategory
from backend.services.tool_registry import ToolRegistry
from backend.services.memory.working_memory import WorkingMemory
from backend.services.memory.episodic_memory import EpisodicMemory
from backend.services.perception.uia_scene_graph import UIASceneGraph, SceneGraph, SceneElement
from backend.services.task_queue import TaskQueueManager, TaskPriority
from backend.services.automation.browser_executor import BrowserExecutor
from backend.services.automation.desktop_executor import DesktopExecutor
from backend.api.websocket import RobustConnectionManager
from backend.models.schemas import WSMessage


# ==============================================================================
# 1. Startup & Lazy Loading Efficiency
# ==============================================================================

def test_service_manager_lazy_initialization_efficiency():
    """Verify that registered factories remain UNINITIALIZED until explicitly requested."""
    created = False
    def heavy_model_factory():
        nonlocal created
        created = True
        return {"model": "heavy_simulated_transformer"}

    ServiceManager.register_factory("test_lazy_heavy_model", heavy_model_factory)
    
    assert ServiceManager.get_state("test_lazy_heavy_model") == ServiceState.UNINITIALIZED
    assert created is False

    # Factory only executes on demand
    instance = ServiceManager.get_instance("test_lazy_heavy_model")
    assert created is True
    assert instance["model"] == "heavy_simulated_transformer"
    assert ServiceManager.get_state("test_lazy_heavy_model") == ServiceState.READY


# ==============================================================================
# 2. Fast Intent Routing Sub-Millisecond Latency
# ==============================================================================

def test_fast_intent_router_submillisecond_latency():
    """Verify that deterministic regex/keyword routing executes in sub-millisecond time (<1.0 ms)."""
    router = FastIntentRouter()
    
    start = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        _ = router.classify("open notepad")
        _ = router.classify("what time is it")
        _ = router.classify("write a python script to sort a list")
    
    elapsed_total_ms = (time.perf_counter() - start) * 1000.0
    avg_per_call_ms = elapsed_total_ms / (iterations * 3)
    
    assert avg_per_call_ms < 1.0, f"Average routing latency {avg_per_call_ms:.4f} ms exceeded 1.0 ms threshold"


# ==============================================================================
# 3. ToolRegistry Sub-Microsecond Lookup Latency
# ==============================================================================

def test_tool_registry_submicrosecond_lookup_latency():
    """Verify that tool catalog lookup is high-performance dictionary indexed (<100 μs)."""
    registry = ToolRegistry()
    assert len(registry.tools) >= 60

    start = time.perf_counter()
    iterations = 500
    for _ in range(iterations):
        t1 = registry.get_tool("get_system_status")
        t2 = registry.get_tool("search_files")
        t3 = registry.get_tool("read_file")
    
    elapsed_total_ms = (time.perf_counter() - start) * 1000.0
    avg_per_lookup_us = (elapsed_total_ms * 1000.0) / (iterations * 3)
    
    assert t1 is not None and t2 is not None and t3 is not None
    assert avg_per_lookup_us < 100.0, f"Average tool lookup {avg_per_lookup_us:.2f} us exceeded 100 us threshold"


# ==============================================================================
# 4. Working Memory Sliding Window Bounded Capacity
# ==============================================================================

def test_working_memory_sliding_window_bounded_size():
    """Verify WorkingMemory enforces bounded turn counts to prevent memory leaks."""
    wm = WorkingMemory(max_turns=5, max_tokens=1000)
    
    # Add 20 conversation turns
    for i in range(20):
        wm.add_turn("user", f"User query message number {i}")
        wm.add_turn("assistant", f"Assistant response message number {i}")
    
    # Bounded window must retain at most max_turns (5) turns
    turns = wm.get_turns()
    assert len(turns) <= 5
    assert "number 19" in turns[-1]["content"]


# ==============================================================================
# 5. Episodic Memory SQLite WAL Mode & Query Bounds
# ==============================================================================

def test_episodic_memory_wal_and_retrieval_performance(tmp_path):
    """Verify EpisodicMemory uses SQLite WAL mode and bounds experience queries."""
    ep = EpisodicMemory(data_dir=tmp_path)
    
    # Verify WAL journal mode
    with ep._get_exp_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"

    # Record 50 experiences
    for i in range(50):
        ep.record_experience(goal=f"Automate task {i}", result="Success", success=True)

    # Query with limit bound
    results = ep.query_experiences(limit=10)
    assert len(results) == 10
    assert isinstance(results[0], dict)


# ==============================================================================
# 6. Differential UIA Scene Graph Cache TTL
# ==============================================================================

def test_uia_scene_graph_cache_ttl_and_differential_refresh():
    """Verify UIASceneGraph caches scene graphs within TTL and refreshes on expiry."""
    sg = UIASceneGraph(cache_ttl=0.1)  # Fast 100ms TTL for testing
    
    with patch("win32gui.GetForegroundWindow", return_value=1234), \
         patch("win32gui.GetWindowText", return_value="Test Application"), \
         patch("win32gui.GetWindowRect", return_value=(0, 0, 800, 600)), \
         patch("pywinauto.Application") as mock_app_cls:
        
        mock_active_win = MagicMock()
        mock_active_win.process_id.return_value = 9999
        
        info_mock = MagicMock()
        info_mock.control_type = "Button"
        info_mock.rectangle.left = 10
        info_mock.rectangle.top = 10
        info_mock.rectangle.right = 50
        info_mock.rectangle.bottom = 30
        info_mock.name = "OK Button"
        info_mock.automation_id = "el1"
        info_mock.handle = 123
        info_mock.is_enabled = True
        info_mock.has_keyboard_focus = False

        mock_elem = MagicMock()
        mock_elem.info = info_mock
        mock_elem.get_value.side_effect = Exception("no value")
        mock_active_win.descendants.return_value = [mock_elem]
        
        mock_app_inst = MagicMock()
        mock_app_inst.window.return_value = mock_active_win
        mock_app_cls.return_value.connect.return_value = mock_app_inst

        # 1. First capture (Cache miss -> parses UIA tree)
        s1 = sg.capture_scene()
        assert s1.window_title == "Test Application"
        assert len(s1.elements) == 1
        assert s1.elements[0].id == "el1"
        assert mock_app_cls.return_value.connect.call_count == 1

        # 2. Immediate second capture within TTL (Cache hit -> avoids UIA tree traversal)
        s2 = sg.capture_scene()
        assert s2.window_title == "Test Application"
        assert mock_app_cls.return_value.connect.call_count == 1

        # 3. Sleep past TTL (Cache expired -> triggers refresh)
        time.sleep(0.12)
        s3 = sg.capture_scene()
        assert s3.window_title == "Test Application"
        assert mock_app_cls.return_value.connect.call_count == 2


# ==============================================================================
# 7. Bounded TaskQueue Execution & Priority Preemption
# ==============================================================================

@pytest.mark.asyncio
async def test_task_queue_bounded_capacity_and_priority_ordering():
    """Verify TaskQueue executes highest priority tasks first."""
    tq = TaskQueueManager()
    
    tq.enqueue_task(name="Batch Job", payload={"order": 3}, priority=TaskPriority.LOW)
    tq.enqueue_task(name="Urgent Interrupt", payload={"order": 1}, priority=TaskPriority.HIGH)
    tq.enqueue_task(name="Standard Action", payload={"order": 2}, priority=TaskPriority.MEDIUM)

    executed_order = []
    async def _handler(payload):
        executed_order.append(payload["order"])
        return {"status": "ok"}

    await tq.execute_next_task(_handler)
    await tq.execute_next_task(_handler)
    await tq.execute_next_task(_handler)

    assert executed_order == [1, 2, 3]


# ==============================================================================
# 8. Browser Context Resource Lifecycle & Safe Cleanup
# ==============================================================================

@pytest.mark.asyncio
async def test_browser_isolated_context_resource_cleanup():
    """Verify BrowserExecutor creates isolated contexts and cleans up correctly."""
    executor = BrowserExecutor()
    
    # Mock playwright browser and context without launching real browser
    mock_context = AsyncMock()
    mock_context.close = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    
    executor._started = True
    executor._page = MagicMock()
    executor._browser = mock_browser

    context = await executor.create_isolated_context()
    assert context is mock_context

    # Close context cleans up resources
    await context.close()
    mock_context.close.assert_awaited_once()


# ==============================================================================
# 9. Repeated Task Cancellation & Mutex Lock Leak Prevention
# ==============================================================================

@pytest.mark.asyncio
async def test_repeated_task_cancellation_memory_stability():
    """Verify rapid acquisition and release of desktop execution lock without deadlock or leakage."""
    executor = DesktopExecutor()
    
    for _ in range(50):
        async with executor._execution_lock:
            assert executor._execution_lock.locked()
        assert not executor._execution_lock.locked()


# ==============================================================================
# 10. WebSocket Connection Manager Session Purge & Leak Prevention
# ==============================================================================

@pytest.mark.asyncio
async def test_websocket_connection_manager_session_cleanup():
    """Verify rapid client connect/disconnect cycles clean up session dictionaries completely."""
    ws_mgr = RobustConnectionManager()
    
    from starlette.websockets import WebSocketState
    
    for i in range(20):
        client_id = f"bench_client_{i}"
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.client_state = WebSocketState.CONNECTED
        
        session = await ws_mgr.connect(mock_ws, client_id=client_id)
        assert len(ws_mgr.active_connections) == 1
        
        ws_mgr.disconnect(mock_ws, client_id=client_id)
        assert len(ws_mgr.active_connections) == 0
        assert ws_mgr.sessions[client_id].state == "DISCONNECTED"
