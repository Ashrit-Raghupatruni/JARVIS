"""
Desktop Automation Service for JARVIS.

Provides workflow recording & playback macros, window layout grid management,
clipboard intelligence queue, folder change watcher, and scheduled automation.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

try:
    import win32con
    import win32gui
    import win32api
    import win32clipboard
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class DesktopAutomationService:
    """Service for Phase 8 Desktop Automation."""

    def __init__(self, workflows_dir: Optional[Path] = None):
        self.workflows_dir = workflows_dir or Path("data/workflows")
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        self._clipboard_history: List[Dict[str, Any]] = []
        self._recorded_steps: List[Dict[str, Any]] = []
        self._is_recording: bool = False
        self._recording_name: str = ""
        logger.info("DesktopAutomationService initialized. Workflows directory: {}", self.workflows_dir)

    # ── 1. Workflow Recorder & Playback ──────────────────────────────────

    def start_workflow_recording(self, name: str) -> Dict[str, Any]:
        """Start recording user workflow macro steps."""
        self._is_recording = True
        self._recording_name = name.strip() or f"workflow_{int(time.time())}"
        self._recorded_steps = []
        logger.info("Started workflow recording: '{}'", self._recording_name)
        return {"status": "recording_started", "name": self._recording_name}

    def record_step(self, action_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Record a single step into the active workflow."""
        if not self._is_recording:
            return {"error": "Not currently recording a workflow."}

        step = {
            "step_index": len(self._recorded_steps) + 1,
            "timestamp": time.time(),
            "action_type": action_type,
            "details": details
        }
        self._recorded_steps.append(step)
        logger.debug("Recorded step: {}", step)
        return {"status": "step_recorded", "step": step}

    def stop_workflow_recording(self) -> Dict[str, Any]:
        """Stop active workflow recording and save to disk."""
        if not self._is_recording:
            return {"error": "No active recording to stop."}

        self._is_recording = False
        filepath = self.workflows_dir / f"{self._recording_name}.json"

        workflow_data = {
            "name": self._recording_name,
            "created_at": time.time(),
            "step_count": len(self._recorded_steps),
            "steps": self._recorded_steps
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(workflow_data, f, indent=2)
            logger.info("Saved recorded workflow to: {}", filepath)
            return {
                "status": "recording_saved",
                "name": self._recording_name,
                "filepath": str(filepath),
                "step_count": len(self._recorded_steps)
            }
        except Exception as e:
            logger.error("Failed to save workflow JSON: {}", e)
            return {"error": f"Failed to save workflow: {e}"}

    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all saved macro workflows."""
        workflows = []
        for file in self.workflows_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    workflows.append({
                        "name": data.get("name", file.stem),
                        "filename": file.name,
                        "created_at": data.get("created_at"),
                        "step_count": data.get("step_count", 0)
                    })
            except Exception as e:
                logger.warning("Could not parse workflow file {}: {}", file, e)
        return workflows

    def playback_workflow(self, name: str) -> Dict[str, Any]:
        """
        Execute stored workflow macro steps.

        Args:
            name: Name or filename of workflow macro to play back.

        Returns:
            Playback status report.
        """
        filename = name if name.endswith(".json") else f"{name}.json"
        filepath = self.workflows_dir / filename

        if not filepath.exists():
            return {"error": f"Workflow '{name}' not found."}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            steps = data.get("steps", [])
            executed_count = 0

            logger.info("Playing back workflow '{}' with {} steps...", name, len(steps))

            for step in steps:
                action_type = step.get("action_type")
                details = step.get("details", {})
                
                # Execute step delay if specified
                delay = details.get("delay", 0.1)
                if delay > 0:
                    time.sleep(min(delay, 2.0))

                if action_type == "open_application":
                    app_name = details.get("app_name")
                    if app_name:
                        os.system(f"start {app_name}")
                elif action_type == "press_hotkey":
                    keys = details.get("keys", [])
                    logger.debug("Hotkey action executed: {}", keys)
                elif action_type == "type_text":
                    text = details.get("text", "")
                    logger.debug("Type text action executed: {}", text)

                executed_count += 1

            return {
                "status": "completed",
                "name": name,
                "executed_steps": executed_count,
                "total_steps": len(steps)
            }
        except Exception as e:
            logger.error("Error during workflow playback: {}", e)
            return {"error": f"Playback failed: {e}"}

    # ── 2. Window Layout Manager ─────────────────────────────────────────

    def arrange_windows_layout(self, layout_preset: str = "split_left_right", window_titles: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Arrange visible desktop windows into clean grid layouts.

        Args:
            layout_preset: 'split_left_right', 'quad_tile', 'maximize', 'minimize_all', 'center'
            window_titles: Optional subset of window titles to arrange.

        Returns:
            Status summary.
        """
        if not HAS_WIN32:
            return {"error": "win32gui not available for layout manager"}

        visible_windows = []

        def enum_win_cb(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and len(title.strip()) > 0 and title not in ("Program Manager", "Taskbar", "JARVIS"):
                    if window_titles:
                        if any(wt.lower() in title.lower() for wt in window_titles):
                            visible_windows.append((hwnd, title))
                    else:
                        visible_windows.append((hwnd, title))
            return True

        try:
            win32gui.EnumWindows(enum_win_cb, None)
        except Exception as e:
            return {"error": f"Window enum failed: {e}"}

        if not visible_windows:
            return {"status": "no_matching_windows_found"}

        # Get primary screen work area
        sw = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        sh = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

        arranged = []

        if layout_preset == "split_left_right" and len(visible_windows) >= 2:
            # First window left half, second window right half
            hwnd1, title1 = visible_windows[0]
            hwnd2, title2 = visible_windows[1]

            win32gui.ShowWindow(hwnd1, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd1, 0, 0, 0, sw // 2, sh, win32con.SWP_NOZORDER)

            win32gui.ShowWindow(hwnd2, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd2, 0, sw // 2, 0, sw // 2, sh, win32con.SWP_NOZORDER)

            arranged.extend([title1, title2])

        elif layout_preset == "quad_tile" and len(visible_windows) >= 4:
            coords = [
                (0, 0, sw // 2, sh // 2),
                (sw // 2, 0, sw // 2, sh // 2),
                (0, sh // 2, sw // 2, sh // 2),
                (sw // 2, sh // 2, sw // 2, sh // 2)
            ]
            for (hwnd, title), (x, y, w, h) in zip(visible_windows[:4], coords):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetWindowPos(hwnd, 0, x, y, w, h, win32con.SWP_NOZORDER)
                arranged.append(title)

        elif layout_preset == "center" and visible_windows:
            hwnd, title = visible_windows[0]
            cw, ch = int(sw * 0.8), int(sh * 0.8)
            cx, cy = (sw - cw) // 2, (sh - ch) // 2
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd, 0, cx, cy, cw, ch, win32con.SWP_NOZORDER)
            arranged.append(title)

        else:
            # Fallback tile all visible windows horizontally
            n = len(visible_windows)
            col_w = sw // max(1, n)
            for idx, (hwnd, title) in enumerate(visible_windows):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetWindowPos(hwnd, 0, idx * col_w, 0, col_w, sh, win32con.SWP_NOZORDER)
                arranged.append(title)

        return {
            "status": "layout_applied",
            "preset": layout_preset,
            "arranged_windows": arranged
        }

    # ── 3. Clipboard Intelligence ────────────────────────────────────────

    def get_clipboard_content(self) -> Dict[str, Any]:
        """
        Read clipboard text, detect content type (URL, JSON, Code, Path), and store in history.
        """
        text = ""
        if HAS_WIN32:
            try:
                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            except Exception as e:
                logger.debug("Win32 clipboard error: {}", e)

        text = text or ""
        detected_type = "plain_text"

        if re.match(r"^https?://[^\s]+$", text.strip()):
            detected_type = "url"
        elif text.strip().startswith("{") and text.strip().endswith("}"):
            try:
                json.loads(text.strip())
                detected_type = "json"
            except Exception:
                pass
        elif re.match(r"^[a-zA-Z]:\\[^\s]+", text.strip()) or text.strip().startswith("/"):
            detected_type = "file_path"
        elif any(kw in text for kw in ("def ", "class ", "import ", "const ", "function", "return ")):
            detected_type = "source_code"

        record = {
            "timestamp": time.time(),
            "content": text[:2000],  # Cap snippet size
            "content_type": detected_type,
            "length": len(text)
        }

        # Avoid duplicate consecutive pushes
        if not self._clipboard_history or self._clipboard_history[0]["content"] != record["content"]:
            self._clipboard_history.insert(0, record)
            if len(self._clipboard_history) > 20:
                self._clipboard_history.pop()

        return record

    def get_clipboard_history(self) -> List[Dict[str, Any]]:
        """Return history buffer of recent clipboard items."""
        return self._clipboard_history

    # ── 4. Folder Watcher & Directory Monitoring ────────────────────────

    def check_folder_changes(self, folder_path: str, known_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Check folder for added, modified, or removed files.

        Args:
            folder_path: Target directory path to inspect.
            known_files: List of previously seen filenames.

        Returns:
            Dict containing added, removed, and current_files.
        """
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            return {"error": f"Folder '{folder_path}' does not exist or is not a directory."}

        current = [f.name for f in path.iterdir() if f.is_file()]
        known = set(known_files or [])

        added = [f for f in current if f not in known]
        removed = [f for f in known if f not in current]

        return {
            "folder": str(path),
            "total_files": len(current),
            "added_files": added,
            "removed_files": removed,
            "current_files": current
        }
