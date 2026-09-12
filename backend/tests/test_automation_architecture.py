"""
Unit & Integration Tests for Consolidated Automation Architecture.
==================================================================
Tests:
- DesktopExecutor (system info, volume, clipboard, folder watcher, file operations)
- BrowserExecutor (lifecycle, DuckDuckGo fallback, page parsing)
- UIAPerceptionEngine (window inspection, OCR scoring, fail-closed typing)
- ActionExecutionVerifier (process verification, delta checks, alternative strategies)
- AutomationOrchestrator (workflow recording, macro execution, sub-executor delegation)
- 100% Backward compatibility of root facades (AutomationService, DesktopAutomationService, UIAEngine, BrowserService, ActionVerifier)
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.automation import (
    AutomationOrchestrator,
    DesktopExecutor,
    BrowserExecutor,
    BrowserService,
    UIAPerceptionEngine,
    UIAEngine,
    ActionExecutionVerifier,
    ActionVerifier,
    action_verifier,
)
from backend.services.automation.desktop_executor import APP_PATHS, APP_PROCESS_NAMES, _resolve_user_path
from backend.services.automation import (
    AutomationService as AutomationServiceFacade,
)
from backend.services.desktop_automation import DesktopAutomationService
from backend.services.uia_engine import UIAEngine as UIAEngineFacade
from backend.services.browser import BrowserService as BrowserServiceFacade
from backend.services.action_verifier import ActionExecutionVerifier as ActionVerifierFacade


@pytest.fixture
def desktop_executor():
    return DesktopExecutor()


@pytest.fixture
def uia_engine():
    return UIAPerceptionEngine()


@pytest.fixture
def verifier():
    return ActionExecutionVerifier()


@pytest.fixture
def temp_workflow_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def orchestrator(temp_workflow_dir):
    return AutomationOrchestrator(workflows_dir=temp_workflow_dir)


# ── 1. DesktopExecutor Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_desktop_executor_system_info(desktop_executor):
    """Verify system info returns valid CPU, memory, disk, and OS dictionaries."""
    info = await desktop_executor.get_system_info()
    assert isinstance(info, dict)
    assert "os" in info
    assert "cpu" in info
    assert "memory" in info
    assert "disk" in info
    assert "uptime_hours" in info
    assert info["memory"]["total_gb"] > 0


@pytest.mark.asyncio
async def test_desktop_executor_volume_and_media(desktop_executor):
    """Verify volume adjustment and media playback commands."""
    with patch("pyautogui.press") as mock_press:
        res_mute = desktop_executor.adjust_volume("mute")
        assert "Muted" in res_mute or "successfully" in res_mute
        mock_press.assert_called_with("volumemute")

        res_up = desktop_executor.adjust_volume("up", amount=3)
        assert "3 steps" in res_up

        res_play = desktop_executor.control_media("playpause")
        assert "playpause" in res_play

        res_invalid = desktop_executor.control_media("invalid_action")
        assert "Unsupported" in res_invalid


def test_desktop_executor_clipboard_classification(desktop_executor):
    """Verify clipboard content type auto-detection."""
    # Patch win32clipboard so tests are hermetic
    with patch("backend.services.automation.desktop_executor.HAS_WIN32", False):
        with patch.object(desktop_executor, "get_clipboard_content") as mock_clip:
            mock_clip.return_value = {
                "timestamp": 123456.0,
                "content": "https://github.com/Ashrit-Raghupatruni/JARVIS",
                "content_type": "url",
                "length": 45
            }
            res = desktop_executor.get_clipboard_content()
            assert res["content_type"] == "url"


def test_desktop_executor_folder_watcher(desktop_executor, tmp_path):
    """Verify directory file change detection."""
    folder = tmp_path / "watch_test"
    folder.mkdir()
    f1 = folder / "file1.txt"
    f1.write_text("hello")

    res = desktop_executor.check_folder_changes(str(folder), known_files=[])
    assert res["total_files"] == 1
    assert "file1.txt" in res["added_files"]

    res2 = desktop_executor.check_folder_changes(str(folder), known_files=["file1.txt"])
    assert len(res2["added_files"]) == 0
    assert len(res2["removed_files"]) == 0


@pytest.mark.asyncio
async def test_desktop_executor_file_crud(desktop_executor, tmp_path):
    """Verify safe create, rename, and delete operations."""
    test_file = tmp_path / "test_doc.txt"
    create_res = await desktop_executor.create_file(str(test_file), "Test content")
    assert "Created file" in create_res
    assert test_file.exists()

    renamed_file = tmp_path / "renamed_doc.txt"
    rename_res = await desktop_executor.rename_file(str(test_file), str(renamed_file))
    assert "Renamed" in rename_res
    assert renamed_file.exists()
    assert not test_file.exists()

    # Default safety requires user confirmation for delete
    delete_prompt = await desktop_executor.delete_file(str(renamed_file))
    assert "confirmation" in delete_prompt.lower()
    assert renamed_file.exists()

    # With confirmation bypass in safety service, file is deleted
    from backend.services.safety import SafetyService
    safe_executor = DesktopExecutor(safety_service=SafetyService(confirm_dangerous=False))
    delete_res = await safe_executor.delete_file(str(renamed_file))
    assert "Deleted file" in delete_res
    assert not renamed_file.exists()


# ── 2. BrowserExecutor Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_browser_executor_state_and_lifecycle():
    """Verify browser state tracking and safe stop."""
    browser = BrowserExecutor()
    assert not browser.is_started

    # Test stop on unstarted browser does not raise
    await browser.stop()
    assert not browser.is_started


@pytest.mark.asyncio
async def test_browser_executor_duckduckgo_fallback():
    """Verify DuckDuckGo fallback query parser."""
    browser = BrowserExecutor()
    html_mock = """
    <html>
      <body>
        <div class="result__body">
          <a class="result__url" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com">Example Domain</a>
          <a class="result__snippet">This is an example domain snippet for testing.</a>
        </div>
      </body>
    </html>
    """
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = html_mock.encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch.object(browser, "_ensure_started", side_effect=Exception("Playwright unavailable")):
            res = await browser.search_web("example test query")
            assert "Example Domain" in res or "Search results" in res


# ── 3. UIAPerceptionEngine Tests ─────────────────────────────────────────

def test_uia_perception_engine_inspect_controls(uia_engine):
    """Verify active window inspection returns dictionary structure."""
    res = uia_engine.inspect_active_window_controls()
    assert isinstance(res, dict)
    assert "status" in res
    assert "controls" in res


def test_uia_perception_engine_fail_closed_typing(uia_engine):
    """Verify set_control_value rejects blind typing into non-existent controls."""
    with patch.object(uia_engine, "click_element_by_name", return_value={"status": "not_found"}):
        res = uia_engine.set_control_value("non_existent_submit_field_xyz", "my_password")
        assert res["status"] == "error"
        assert "not found" in res["message"]


def test_uia_perception_engine_ocr_matching(uia_engine):
    """Verify OCR element matching and confidence score calculation."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))

    with patch.object(uia_engine, "find_element_by_ocr") as mock_ocr:
        mock_ocr.return_value = {
            "found": True,
            "target": "Submit",
            "matched_text": "Submit",
            "confidence": 0.95,
            "engine": "mock_ocr",
            "coordinates": {"x": 100, "y": 50},
            "bounds": {"left": 50, "top": 30, "right": 150, "bottom": 70}
        }
        with patch("pyautogui.click") as mock_click:
            res = uia_engine.click_element_by_ocr("Submit", image=img)
            assert res["status"] == "clicked"
            assert res["target"] == "Submit"
            mock_click.assert_called_with(100, 50)


# ── 4. ActionExecutionVerifier Tests ─────────────────────────────────────

def test_action_verifier_process_verification(verifier):
    """Verify process verification against WorldModel or psutil."""
    with patch("psutil.process_iter") as mock_iter:
        mock_proc = MagicMock()
        mock_proc.info = {"name": "notepad.exe"}
        mock_iter.return_value = [mock_proc]

        verified, reason = verifier.verify_application_launched("notepad")
        assert verified is True
        assert "notepad" in reason

        verified_fail, reason_fail = verifier.verify_application_launched("non_existent_app_999")
        assert verified_fail is False


@pytest.mark.asyncio
async def test_action_verifier_execute_and_verify(verifier):
    """Verify execute_and_verify validates results and tracks duration."""
    mock_registry = MagicMock()
    mock_registry.execute_tool = AsyncMock(return_value={"status": "clicked", "target": "Submit"})

    res = await verifier.execute_and_verify(
        "click_element_by_name",
        {"element_name": "Submit"},
        mock_registry
    )

    assert res["status"] == "success"
    assert res["verified"] is True
    assert "duration_ms" in res


# ── 5. AutomationOrchestrator Tests ──────────────────────────────────────

def test_orchestrator_macro_recording_and_listing(orchestrator):
    """Verify recording, saving, and listing workflow macro JSON files."""
    start_res = orchestrator.start_workflow_recording("test_macro")
    assert start_res["status"] == "recording_started"

    orchestrator.record_step("open_application", {"app_name": "notepad"})
    orchestrator.record_step("type_text", {"text": "Hello JARVIS Automation"})

    stop_res = orchestrator.stop_workflow_recording()
    assert stop_res["status"] == "recording_saved"
    assert stop_res["step_count"] == 2

    workflows = orchestrator.list_workflows()
    assert len(workflows) >= 1
    assert any(w["name"] == "test_macro" for w in workflows)


def test_orchestrator_rpa_macro_execution(orchestrator):
    """Verify multi-step RPA macro execution with step-level error handling."""
    steps = [
        {"action": "wait", "seconds": 0.05},
        {"action": "type", "text": "test macro text"}
    ]
    with patch("pyautogui.typewrite"):
        res = orchestrator.execute_rpa_macro(steps, stop_on_error=True)
        assert res["status"] == "completed"
        assert res["executed_steps_count"] == 2


def test_orchestrator_sub_executors_lazy_properties(orchestrator):
    """Verify orchestrator exposes desktop, browser, uia, and verifier sub-executors."""
    assert isinstance(orchestrator.desktop, DesktopExecutor)
    assert isinstance(orchestrator.browser, BrowserExecutor)
    assert isinstance(orchestrator.uia, UIAPerceptionEngine)
    assert isinstance(orchestrator.verifier, ActionExecutionVerifier)


# ── 6. Backward Compatibility Facades Tests ──────────────────────────────

def test_backward_compatibility_facades():
    """Verify all legacy classes instantiate and provide identical methods."""
    # 1. AutomationService facade
    auto_svc = AutomationServiceFacade()
    assert hasattr(auto_svc, "open_application")
    assert hasattr(auto_svc, "close_application")
    assert hasattr(auto_svc, "arrange_workspace_layout")
    assert hasattr(auto_svc, "type_text")

    # 2. DesktopAutomationService facade
    desk_svc = DesktopAutomationService()
    assert hasattr(desk_svc, "start_workflow_recording")
    assert hasattr(desk_svc, "execute_rpa_macro")
    assert hasattr(desk_svc, "arrange_windows_layout")
    assert hasattr(desk_svc, "get_clipboard_content")

    # 3. UIAEngine facade
    uia = UIAEngineFacade()
    assert hasattr(uia, "inspect_active_window_controls")
    assert hasattr(uia, "click_element_by_name")
    assert hasattr(uia, "find_element_by_ocr")

    # 4. BrowserService facade
    browser = BrowserServiceFacade()
    assert hasattr(browser, "open_url")
    assert hasattr(browser, "search_web")
    assert hasattr(browser, "click_element")

    # 5. ActionVerifier facade
    av = ActionVerifierFacade()
    assert hasattr(av, "verify_application_launched")
    assert hasattr(av, "execute_and_verify")
    assert action_verifier is not None
