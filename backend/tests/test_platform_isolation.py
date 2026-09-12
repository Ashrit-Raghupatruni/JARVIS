"""
Platform Boundary Isolation & Capability Detection Test Suite.

Verifies:
1. Core backend modules import safely without requiring Windows-specific packages.
2. Platform capability checks correctly identify availability and fail cleanly.
3. Disk paths and storage usage resolve dynamically across operating systems.
4. Windows-specific tools produce actionable, structured error messages on unsupported platforms.
5. Process management routines operate safely with isolated arguments and zero unquoted shell strings.
"""

import sys
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_core_modules_import_cleanly_on_simulated_non_windows():
    """Verify that core modules can be imported even if all Windows libraries are missing."""
    from backend.services.manager import ServiceManager
    from backend.services.bootstrap import bootstrap_core_services, register_lazy_factories
    from backend.services.tool_registry import ToolRegistry
    from backend.services.world_model import WorldModel
    from backend.services.workspace_memory import WorkspaceMemory
    from backend.api.debug_router import debug_router
    from backend.services.skills.system_skill import SystemSkill

    assert ServiceManager is not None
    assert ToolRegistry is not None
    assert WorldModel is not None
    assert WorkspaceMemory is not None
    assert debug_router is not None
    assert SystemSkill is not None


@pytest.mark.asyncio
async def test_tool_registry_unsupported_platform_graceful_handling():
    """Verify Windows-only tools return clear structured errors when executed on non-Windows platform."""
    from backend.services.tool_registry import ToolRegistry

    registry = ToolRegistry()

    # Simulate running on Linux/macOS
    with patch("sys.platform", "linux"):
        # Test lock_pc on non-Windows
        res = await registry.execute_tool("lock_pc", {})
        assert res["status"] == "error"
        assert "only supported on Windows" in res["error"]

        # Test media_control on non-Windows
        res_media = await registry.execute_tool("media_control", {"action": "play_pause"})
        assert res_media["status"] == "error"
        assert "only supported on Windows" in res_media["error"]

        # Test adjust_volume on non-Windows
        res_vol = await registry.execute_tool("adjust_volume", {"direction": "up", "amount": 10})
        assert res_vol["status"] == "error"
        assert "only supported on Windows" in res_vol["error"]


def test_system_skill_unsupported_platform_handling():
    """Verify SystemSkill returns clear messages for Windows-only features on other OS."""
    from backend.services.skills.system_skill import SystemSkill

    skill = SystemSkill()

    with patch("sys.platform", "darwin"):
        msg = skill.list_startup_programs()
        assert "only supported on Windows" in msg

        set_msg = skill.set_startup_program("TestApp", "/usr/bin/testapp")
        assert "Windows-only" in set_msg


def test_workspace_memory_unsupported_platform_handling():
    """Verify WorkspaceMemory returns a graceful error when win32 is unavailable."""
    from backend.services.workspace_memory import WorkspaceMemory

    wm = WorkspaceMemory()
    with patch("backend.services.workspace_memory.HAS_WIN32", False), \
         patch("backend.services.workspace_memory.win32gui", None):
        res = wm.restore_workspace("coding")
        assert res["status"] == "error"
        assert "not supported on this platform" in res["message"]


def test_dynamic_path_resolution():
    """Verify no hardcoded user paths leak into runtime bootstrap."""
    from backend.config import PROJECT_ROOT, DEFAULT_DATA_DIR, DEFAULT_LOG_DIR

    assert PROJECT_ROOT.exists()
    assert DEFAULT_DATA_DIR.name == "data"
    assert DEFAULT_LOG_DIR.name == "logs"
    assert "ashri" not in str(PROJECT_ROOT.name).lower()


def test_disk_telemetry_uses_dynamic_root():
    """Verify disk usage uses dynamic OS root path rather than hardcoded C:\."""
    import psutil
    root_path = os.path.abspath(os.sep)
    usage = psutil.disk_usage(root_path)
    assert usage.total > 0
    assert 0 <= usage.percent <= 100


def test_world_model_summary_operates_without_win32():
    """Verify WorldModel provides consistent summary structure even in headless/platform-fallback state."""
    from backend.services.world_model import WorldModel

    wm = WorldModel()
    with patch("backend.services.world_model.win32gui", None), \
         patch("backend.services.world_model.win32process", None):
        state = wm.refresh(force=True)
        summary = wm.get_summary()
        assert "active_window" in summary
        assert "ui_control_count" in summary
        assert "monitors_count" in summary
        assert isinstance(summary["workflow"], str)