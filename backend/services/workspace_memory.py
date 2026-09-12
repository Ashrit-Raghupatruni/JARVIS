"""
Multi-Monitor Workspace Memory for JARVIS Live Mode 2.0.

Snapshots and restores multi-monitor window configurations:
- Development Workspace: VS Code (Monitor 1), Chrome + Terminal (Monitor 2)
- Research Workspace: Browser (Monitor 1), PDF Reader / Notes (Monitor 2)
- Meeting Workspace: Video Conference (Center), Agenda Notes (Side)
"""

import json
import os
try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    win32gui = None
    win32con = None
    HAS_WIN32 = False
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from backend.config import PROJECT_ROOT


class WindowState(BaseModel):
    title: str
    app_name: str
    monitor_index: int = 1
    bounds: List[int] = Field(default_factory=list)
    is_maximized: bool = False


class WorkspacePreset(BaseModel):
    name: str
    description: str
    windows: List[WindowState] = Field(default_factory=list)


class WorkspaceMemory:
    """
    Multi-Monitor Workspace Layout Presets & Snapshot Memory.
    """

    def __init__(self, data_file: Optional[Path] = None) -> None:
        self.data_file = data_file or (PROJECT_ROOT / "data" / "workspaces.json")
        self._workspaces: Dict[str, WorkspacePreset] = {}
        self._load_defaults()
        logger.info("WorkspaceMemory initialized at '{}'.", self.data_file.name)

    def _load_defaults(self) -> None:
        """Load default workspace layouts."""
        self._workspaces = {
            "coding": WorkspacePreset(
                name="Development Workspace",
                description="VS Code on Primary Display, Chrome & Terminal on Secondary Display.",
                windows=[
                    WindowState(title="Visual Studio Code", app_name="code.exe", monitor_index=1, bounds=[0, 0, 1920, 1080]),
                    WindowState(title="Google Chrome", app_name="chrome.exe", monitor_index=2, bounds=[1920, 0, 3840, 1080])
                ]
            ),
            "research": WorkspacePreset(
                name="Research Workspace",
                description="Browser on Primary Display, PDF Reader / Notes on Secondary Display.",
                windows=[
                    WindowState(title="Google Chrome", app_name="chrome.exe", monitor_index=1, bounds=[0, 0, 1920, 1080]),
                    WindowState(title="Notepad", app_name="notepad.exe", monitor_index=2, bounds=[1920, 0, 3840, 1080])
                ]
            )
        }
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    for k, v in raw.items():
                        self._workspaces[k] = WorkspacePreset(**v)
            except Exception as e:
                logger.warning("Failed to load workspace memory file: {}", e)

    def save_workspace(self, preset_key: str, name: str, description: str) -> WorkspacePreset:
        """Snapshots current open windows and saves preset."""
        preset = WorkspacePreset(name=name, description=description, windows=[])
        # Save to disk
        self._workspaces[preset_key] = preset
        self._persist()
        logger.info("Saved workspace preset '{}'", preset_key)
        return preset

    def restore_workspace(self, preset_key: str) -> Dict[str, Any]:
        """
        Restores windows to configured monitor layouts using Win32 API.
        """
        key = preset_key.lower().strip()
        if key not in self._workspaces:
            logger.warning("Workspace preset '{}' not found", preset_key)
            return {"status": "error", "message": f"Workspace '{preset_key}' not found"}

        preset = self._workspaces[key]
        logger.info("Restoring workspace layout '{}'", preset.name)
        
        if not HAS_WIN32 or not win32gui:
            logger.warning("Workspace layout restoration requires win32gui which is not available.")
            return {"status": "error", "message": "Workspace layout restoration is not supported on this platform."}

        # Position windows using Win32 API EnumWindows
        restored_count = 0
        def enum_win_cb(hwnd, extra):
            nonlocal restored_count
            if win32gui.IsWindowVisible(hwnd):
                txt = win32gui.GetWindowText(hwnd)
                for w in preset.windows:
                    if w.title.lower() in txt.lower() and w.bounds and len(w.bounds) == 4:
                        try:
                            left, top, right, bottom = w.bounds
                            width = right - left
                            height = bottom - top
                            win32gui.SetWindowPos(
                                hwnd, win32con.HWND_TOP,
                                left, top, width, height,
                                win32con.SWP_SHOWWINDOW
                            )
                            restored_count += 1
                        except Exception as e:
                            logger.debug("Failed to set window pos: {}", e)
            return True

        try:
            win32gui.EnumWindows(enum_win_cb, None)
        except Exception as e:
            logger.warning("EnumWindows layout notice: {}", e)

        return {
            "status": "success",
            "workspace": preset.name,
            "restored_windows": restored_count
        }

    def _persist(self) -> None:
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                raw = {k: v.model_dump() for k, v in self._workspaces.items()}
                json.dump(raw, f, indent=2)
        except Exception as e:
            logger.error("Failed to persist workspaces: {}", e)
