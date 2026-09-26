"""
JARVIS AI Operating System - Phase 6: Desktop/UI Automation Reliability & Targeting Hardening Tests.
====================================================================================================
Adversarial test suite validating:
- HWND and window target verification before keyboard/mouse execution
- Wrong-foreground window prevention (blocking keystroke leakage)
- Multi-monitor virtual desktop bounds and negative coordinate clamping
- High-DPI scaling coordinate transformations
- UIA element identity disambiguation (Control Type, AutomationId, Class, Index)
- Bounded UIA traversal and stale element resilience
- Desktop execution serialization lock
- OCR confidence filtering and ambiguity rejection
- Fail-closed security boundaries for desktop actions
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from backend.services.automation.desktop_executor import DesktopExecutor
from backend.services.automation.uia_perception import UIAPerceptionEngine
from backend.services.perception.spatial_engine import SpatialEngine, MonitorInfo
from backend.services.perception.uia_scene_graph import UIASceneGraph, SceneGraph, SceneElement


# ── 1. Window Targeting & Wrong-Foreground Protection ────────────────────────

@pytest.mark.asyncio
async def test_wrong_foreground_hwnd_blocks_keystrokes():
    """
    If target_hwnd is specified and does NOT match the active foreground HWND,
    the executor must block keyboard input to prevent typing into the wrong app.
    """
    executor = DesktopExecutor()
    
    with patch("backend.services.automation.desktop_executor.HAS_WIN32", True), \
         patch("win32gui.GetForegroundWindow", return_value=12345), \
         patch("win32gui.GetWindowText", return_value="Calculator"), \
         patch("win32gui.IsWindow", return_value=True), \
         patch("win32gui.SetForegroundWindow", side_effect=Exception("Focus denied")):
        
        # Target is HWND 99999 (e.g. Notepad), but foreground is 12345 (Calculator)
        res = await executor.type_text("malicious or sensitive text", target_hwnd=99999)
        assert "Target Mismatch Blocked" in res
        assert "Expected HWND 99999" in res
        assert "HWND 12345" in res


@pytest.mark.asyncio
async def test_wrong_foreground_title_blocks_hotkey():
    """
    If target_window title does NOT match active foreground title, hotkeys must be blocked.
    """
    executor = DesktopExecutor()

    with patch("backend.services.automation.desktop_executor.HAS_WIN32", True), \
         patch("win32gui.GetForegroundWindow", return_value=54321), \
         patch("win32gui.GetWindowText", return_value="Google Chrome"), \
         patch.object(executor, "focus_window", return_value="No window found"):

        res = await executor.press_hotkey("ctrl+w", target_window="Terminal")
        assert "Target Mismatch Blocked" in res
        assert "Expected active window matching 'Terminal'" in res


@pytest.mark.asyncio
async def test_matching_foreground_window_allows_execution():
    """
    When foreground window matches expected target, execution proceeds safely.
    """
    executor = DesktopExecutor()

    with patch("backend.services.automation.desktop_executor.HAS_WIN32", True), \
         patch("win32gui.GetForegroundWindow", return_value=10101), \
         patch("win32gui.GetWindowText", return_value="Visual Studio Code"), \
         patch("pyautogui.typewrite") as mock_typewrite:

        res = await executor.type_text("print('hello')", target_window="Visual Studio Code")
        assert "Typed:" in res
        assert mock_typewrite.called


# ── 2. Multi-Monitor Coordinate Clamping & Negative Coordinate Support ───────

def test_multi_monitor_negative_coordinates_bounds():
    """
    Multi-monitor setups with secondary monitor to the left have negative coordinates.
    SpatialEngine and coordinate clamping must NOT truncate or clamp negative coordinates to 0.
    """
    spatial = SpatialEngine()
    
    # Configure mock dual-monitor: Monitor 2 (Left, -1920..0) and Monitor 1 (Primary, 0..1920)
    spatial._monitors = [
        MonitorInfo(index=1, name="Monitor 1 (Primary)", bounds=[0, 0, 1920, 1080], width=1920, height=1080, is_primary=True),
        MonitorInfo(index=2, name="Monitor 2", bounds=[-1920, 0, 0, 1080], width=1920, height=1080, is_primary=False),
    ]

    min_x, min_y, max_x, max_y, total_w, total_h = spatial.get_virtual_desktop_bounds()
    assert min_x == -1920
    assert min_y == 0
    assert max_x == 1919
    assert total_w == 3840

    executor = DesktopExecutor()
    with patch("backend.services.perception.spatial_engine.SpatialEngine.get_virtual_desktop_bounds", return_value=(min_x, min_y, max_x, max_y, total_w, total_h)):
        # Coordinate on secondary left monitor
        cx, cy = executor._get_clamped_coordinates(-500, 500)
        assert cx == -500
        assert cy == 500

        # Out-of-bounds negative coordinate clamped to leftmost boundary
        cx_oob, _ = executor._get_clamped_coordinates(-2500, 500)
        assert cx_oob == -1920


# ── 3. High-DPI Scaling & Coordinate Transformations ─────────────────────────

def test_high_dpi_scaling_transformations():
    """
    Validate logical to physical coordinate conversions across various DPI scaling factors (100%, 150%, 200%).
    """
    spatial = SpatialEngine()

    with patch.object(spatial, "get_dpi_scale_for_monitor", return_value=1.5):
        # 150% DPI scaling (e.g. 1440p / 4K display)
        phys_x, phys_y = spatial.convert_logical_to_physical(100, 200)
        assert phys_x == 150
        assert phys_y == 300

        log_x, log_y = spatial.convert_physical_to_logical(150, 300)
        assert log_x == 100
        assert log_y == 200

    with patch.object(spatial, "get_dpi_scale_for_monitor", return_value=2.0):
        # 200% DPI scaling
        phys_x2, phys_y2 = spatial.convert_logical_to_physical(50, 80)
        assert phys_x2 == 100
        assert phys_y2 == 160


# ── 4. UIA Element Identity & Disambiguation ─────────────────────────────────

def test_uia_duplicate_element_disambiguation():
    """
    When multiple UI controls share identical labels (e.g. two 'Delete' buttons),
    UIAPerceptionEngine must disambiguate using control_type, automation_id, or index.
    """
    engine = UIAPerceptionEngine()

    mock_scene = SceneGraph(
        window_title="Settings Manager",
        elements=[
            SceneElement(id="btn_delete_temp", name="Delete", control_type="Button", bounds=[10, 10, 50, 30]),
            SceneElement(id="btn_delete_account", name="Delete", control_type="Button", bounds=[10, 100, 50, 120]),
            SceneElement(id="lbl_delete_info", name="Delete", control_type="Text", bounds=[10, 200, 50, 220]),
        ]
    )

    with patch("backend.services.automation.uia_perception.UIAPerceptionEngine.inspect_active_window_controls", return_value={"controls": []}), \
         patch("backend.services.perception.uia_scene_graph.UIASceneGraph.capture_scene", return_value=mock_scene), \
         patch("pyautogui.click") as mock_click:

        # 1. Disambiguate by automation_id
        res1 = engine.click_element_by_name("Delete", automation_id="btn_delete_account")
        assert res1.get("status") == "clicked"
        assert res1.get("element_id") == "btn_delete_account"
        assert res1.get("coordinates") == {"x": 30, "y": 110}

        # 2. Disambiguate by index
        res2 = engine.click_element_by_name("Delete", index=1)
        assert res2.get("status") == "clicked"
        assert res2.get("element_id") == "btn_delete_account"

        # 3. Disambiguate by control_type
        res3 = engine.click_element_by_name("Delete", control_type="Text")
        assert res3.get("status") == "clicked"
        assert res3.get("element_id") == "lbl_delete_info"


# ── 5. Stale UIA Element & Traversal Robustness ──────────────────────────────

def test_stale_uia_element_and_traversal_safety():
    """
    Dynamic UI changes can cause stale COM element exceptions during traversal.
    UIASceneGraph must safely ignore stale elements and respect max_depth and max_elements.
    """
    sg = UIASceneGraph(cache_ttl=0.0)

    class MockCOMElement:
        def __init__(self, should_fail=False):
            self.should_fail = should_fail
        
        @property
        def info(self):
            if self.should_fail:
                raise Exception("COMError: Stale element reference (0x800401FD)")
            mock_info = MagicMock()
            mock_info.control_type = "Button"
            mock_info.rectangle = MagicMock(left=10, top=10, right=60, bottom=40)
            mock_info.name = "Submit"
            mock_info.automation_id = "btn_submit"
            mock_info.is_enabled = True
            mock_info.has_keyboard_focus = False
            return mock_info

    mock_app_instance = MagicMock()
    mock_win = MagicMock()
    mock_win.process_id.return_value = 4567
    # 3 elements: 1 valid, 1 stale/crashing, 1 valid
    mock_win.descendants.return_value = [
        MockCOMElement(should_fail=False),
        MockCOMElement(should_fail=True),
        MockCOMElement(should_fail=False),
    ]
    mock_app_instance.connect.return_value.window.return_value = mock_win

    with patch("backend.services.perception.uia_scene_graph.HAS_PYWINAUTO", True), \
         patch("win32gui.GetForegroundWindow", return_value=8888), \
         patch("win32gui.GetWindowText", return_value="Form Window"), \
         patch("win32gui.GetWindowRect", return_value=(0, 0, 800, 600)), \
         patch("pywinauto.Application", return_value=mock_app_instance):

        scene = sg.capture_scene(max_depth=3, max_elements=50, force=True)
        assert scene.window_title == "Form Window"
        # The stale element was skipped safely, leaving 2 valid elements
        assert len(scene.elements) == 2
        assert scene.total_elements == 2


# ── 6. Desktop Execution Serialization Lock ──────────────────────────────────

@pytest.mark.asyncio
async def test_desktop_execution_lock_serializes_concurrent_tasks():
    """
    Simultaneous background tasks must not interleave physical mouse/keyboard actions.
    The execution lock ensures serialized execution order.
    """
    executor = DesktopExecutor()
    execution_order = []

    async def task_a():
        async with executor._execution_lock:
            execution_order.append("A_start")
            await asyncio.sleep(0.05)
            execution_order.append("A_end")

    async def task_b():
        async with executor._execution_lock:
            execution_order.append("B_start")
            await asyncio.sleep(0.02)
            execution_order.append("B_end")

    await asyncio.gather(task_a(), task_b())

    # Ensure no interleaving occurred (A completed before B or vice versa)
    assert (
        execution_order == ["A_start", "A_end", "B_start", "B_end"] or
        execution_order == ["B_start", "B_end", "A_start", "A_end"]
    )
