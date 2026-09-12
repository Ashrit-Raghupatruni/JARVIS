"""
JARVIS AI Operating System - Desktop Automation Executor.
=========================================================
Consolidated low-level Win32 and PyAutoGUI execution module:
- Application launching, search, and termination
- Mouse and keyboard interactions with safety clamping
- Multi-window layout presets and Win32 coordinate tiling
- File and directory CRUD operations with safety policy checks
- System information, volume, and media playback control
- Clipboard content detection and folder monitoring
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyautogui
from loguru import logger

from backend.services.safety import SafetyService, ActionCategory

# ── Safety: prevent pyautogui from taking over the entire screen ─────────
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1  # Small pause between actions

# Win32 platform support
try:
    import win32api
    import win32clipboard
    import win32con
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Application Path Mappings (Windows)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

APP_PATHS: Dict[str, str] = {
    # Microsoft Office
    "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "powerpoint": r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    "outlook": r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
    "onenote": r"C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE",
    # Browsers
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    # Development
    "vscode": r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "code": r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "git bash": r"C:\Program Files\Git\git-bash.exe",
    # System Utilities
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "snipping tool": "SnippingTool.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
    "settings": "ms-settings:",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    # Media
    "spotify": r"C:\Users\{user}\AppData\Roaming\Spotify\Spotify.exe",
    "vlc": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    "media player": "wmplayer.exe",
    # Communication
    "discord": r"C:\Users\{user}\AppData\Local\Discord\Update.exe --processStart Discord.exe",
    "teams": r"C:\Users\{user}\AppData\Local\Microsoft\Teams\Update.exe --processStart Teams.exe",
    "slack": r"C:\Users\{user}\AppData\Local\slack\slack.exe",
    "zoom": r"C:\Users\{user}\AppData\Roaming\Zoom\bin\Zoom.exe",
    # Other
    "steam": r"C:\Program Files (x86)\Steam\steam.exe",
    "obs": r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    "obs studio": r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
}

APP_PROCESS_NAMES: Dict[str, str] = {
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "brave": "brave.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE",
    "notepad": "notepad.exe",
    "calculator": "Calculator.exe",
    "calc": "Calculator.exe",
    "paint": "mspaint.exe",
    "vscode": "Code.exe",
    "code": "Code.exe",
    "spotify": "Spotify.exe",
    "vlc": "vlc.exe",
    "discord": "Discord.exe",
    "teams": "Teams.exe",
    "slack": "slack.exe",
    "zoom": "Zoom.exe",
    "steam": "steam.exe",
    "obs": "obs64.exe",
    "obs studio": "obs64.exe",
    "task manager": "Taskmgr.exe",
    "terminal": "WindowsTerminal.exe",
    "windows terminal": "WindowsTerminal.exe",
    "docker": "Docker Desktop.exe",
    "docker desktop": "Docker Desktop.exe",
}


def _resolve_user_path(path: str) -> str:
    """Replace ``{user}`` placeholder with the current username."""
    return path.replace("{user}", os.getenv("USERNAME", os.getenv("USER", "user")))


def _resolve_app_path(app_name: str) -> Optional[str]:
    """
    Search for an application executable or shortcut on Windows.
    Returns the absolute path (to .exe or .lnk), or None if not found.
    """
    app_key = app_name.lower().strip()

    # 1. Check hardcoded APP_PATHS
    if app_key in APP_PATHS:
        resolved = _resolve_user_path(APP_PATHS[app_key])
        if resolved.startswith("ms-settings:") or " --" in resolved or " /" in resolved:
            return resolved
        if os.path.exists(resolved):
            return resolved

    # 2. Check Windows Registry App Paths
    try:
        import winreg
        names = [app_name, f"{app_name}.exe"]
        for name in names:
            for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                key_path = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{name}"
                try:
                    with winreg.OpenKey(root, key_path) as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val and os.path.exists(val):
                            return val
                except FileNotFoundError:
                    continue
    except Exception as e:
        logger.debug(f"Registry lookup failed for '{app_name}': {e}")

    # 3. Check Start Menu shortcuts
    try:
        user_profile = os.environ.get("USERPROFILE", "")
        start_menu_paths = [
            os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Microsoft\\Windows\\Start Menu\\Programs"),
            os.path.join(user_profile, "AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs")
        ]

        for base_path in start_menu_paths:
            if not os.path.exists(base_path):
                continue
            for p in Path(base_path).rglob("*.lnk"):
                if app_key in p.stem.lower():
                    return str(p)
    except Exception as e:
        logger.debug(f"Start Menu lookup failed for '{app_name}': {e}")

    return None


class DesktopExecutor:
    """
    Core executor for local desktop automation actions on Windows.
    """

    def __init__(self, safety_service: Optional[SafetyService] = None) -> None:
        self.safety = safety_service or SafetyService()
        self._clipboard_history: List[Dict[str, Any]] = []
        logger.info("DesktopExecutor initialized")

    # ── Application Management ───────────────────────────────────────────

    async def open_application(self, app_name: str) -> str:
        """
        Open an application by its common name, script path, or URI.
        """
        logger.info("Opening application: {}", app_name)

        # Handle python script execution in interactive terminal
        if app_name.lower().endswith(".py") or (os.path.exists(app_name) and app_name.lower().endswith(".py")):
            script_path = os.path.abspath(app_name) if os.path.exists(app_name) else app_name
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", "python", script_path], shell=False)
            return f"Launched Python script '{os.path.basename(app_name)}' in interactive command prompt."

        try:
            path = _resolve_app_path(app_name)
            if path:
                # Handle ms-settings: style URIs
                if path.startswith("ms-settings:") or path.startswith("http"):
                    await asyncio.to_thread(os.startfile, path)
                    return f"Opened {app_name} successfully."

                # Chromium accessibility tree support
                if any(b in app_name.lower() for b in ["chrome", "msedge", "edge", "brave"]):
                    try:
                        subprocess.Popen(
                            [path, "--force-renderer-accessibility"],
                            shell=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        await asyncio.sleep(0.5)
                        return f"Opened {app_name} with UIA accessibility tree enabled."
                    except Exception as b_err:
                        logger.debug("Failed launching browser with accessibility flag: {}", b_err)

                # Handle paths with arguments
                if " --" in path or " /" in path:
                    parts = path.split(" ", 1)
                    subprocess.Popen(
                        [parts[0]] + parts[1].split(),
                        shell=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    await asyncio.to_thread(os.startfile, path)
                    await asyncio.sleep(0.5)
                return f"Opened {app_name} successfully."

            else:
                # Intercept via Self-Healing Engine to search system paths
                try:
                    from backend.services.self_healing import SelfHealingEngine
                    healer = SelfHealingEngine()
                    recovery = healer.diagnose_and_recover("open_application", f"App '{app_name}' not found", app_name)
                    if (recovery.get("recovered") or recovery.get("success")) and recovery.get("recovered_path"):
                        await asyncio.to_thread(os.startfile, recovery["recovered_path"])
                        return f"Opened '{app_name}' via Self-Healing Engine ({recovery['recovered_path']})."
                except Exception as h_err:
                    logger.debug("Self-Healing lookup notice: {}", h_err)

                # If spotify/music and not found locally, open web player
                if any(m in app_name.lower() for m in ["spotify", "music"]):
                    import webbrowser
                    webbrowser.open("https://open.spotify.com")
                    return f"Spotify desktop app was not found locally, so I opened Spotify Web in Chrome, sir!"

                # Try via start command
                subprocess.Popen(
                    ["cmd", "/c", "start", "", app_name],
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return f"Attempted to open '{app_name}' via system search."

        except FileNotFoundError:
            try:
                from backend.services.self_healing import SelfHealingEngine
                healer = SelfHealingEngine()
                recovery = healer.diagnose_and_recover("open_application", f"File not found for '{app_name}'", app_name)
                if (recovery.get("recovered") or recovery.get("success")) and recovery.get("recovered_path"):
                    await asyncio.to_thread(os.startfile, recovery["recovered_path"])
                    return f"Opened '{app_name}' via Self-Healing Engine ({recovery['recovered_path']})."
            except Exception:
                pass

            try:
                subprocess.Popen(
                    ["cmd", "/c", "start", "", app_name],
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return f"Opened '{app_name}' via system search (primary path not found)."
            except Exception as e2:
                logger.error("Failed to open '{}': {}", app_name, e2)
                return f"Could not open '{app_name}': {e2}"

        except Exception as e:
            logger.error("Error opening '{}': {}", app_name, e)
            return f"Error opening '{app_name}': {e}"

    async def close_application(self, app_name: str) -> str:
        """
        Close a running application by process name or lookup.
        """
        app_key = app_name.lower().strip()
        logger.info("Closing application: {}", app_name)

        try:
            process_name = APP_PROCESS_NAMES.get(app_key, f"{app_name}.exe")
            result = subprocess.run(
                ["taskkill", "/IM", process_name, "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return f"Closed {app_name} successfully."
            else:
                result2 = subprocess.run(
                    ["taskkill", "/IM", process_name.lower(), "/F"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result2.returncode == 0:
                    return f"Closed {app_name} successfully."
                return f"Could not close {app_name} — it may not be running. Details: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return f"Timed out trying to close {app_name}."
        except Exception as e:
            logger.error("Error closing '{}': {}", app_name, e)
            return f"Error closing '{app_name}': {e}"

    # ── Workspace & Window Layout Management ──────────────────────────────

    async def arrange_workspace_layout(self, preset_name: str) -> str:
        """
        Arrange desktop window positions according to predefined presets ('coding', 'research', 'presentation').
        """
        preset = preset_name.lower().strip()
        logger.info(f"Arranging workspace layout for preset: '{preset}'")

        try:
            if not HAS_WIN32:
                return "Win32 GUI extensions unavailable on this platform."

            from backend.services.perception.spatial_engine import SpatialEngine
            se = SpatialEngine()
            monitors = se.get_monitors()

            m1_bounds = monitors[0].bounds if monitors else [0, 0, 1920, 1080]
            m1_w = m1_bounds[2] - m1_bounds[0]
            m1_h = m1_bounds[3] - m1_bounds[1]

            m2_bounds = monitors[1].bounds if len(monitors) > 1 else m1_bounds

            def move_win(hwnd, left, top, width, height):
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetWindowPos(
                        hwnd, win32con.HWND_TOP,
                        int(left), int(top), int(width), int(height),
                        win32con.SWP_SHOWWINDOW
                    )
                except Exception as err:
                    logger.debug(f"SetWindowPos warning for {hwnd}: {err}")

            hwnds = []

            def enum_proc(hwnd, _):
                if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                    hwnds.append((hwnd, win32gui.GetWindowText(hwnd).lower()))

            win32gui.EnumWindows(enum_proc, None)

            if preset == "coding":
                for h, title in hwnds:
                    if "code" in title or "visual studio" in title:
                        move_win(h, m1_bounds[0], m1_bounds[1], m1_w * 0.55, m1_h)
                    elif "chrome" in title or "edge" in title or "firefox" in title:
                        move_win(h, m1_bounds[0] + m1_w * 0.55, m1_bounds[1], m1_w * 0.45, m1_h)

            elif preset == "research":
                for h, title in hwnds:
                    if "chrome" in title or "edge" in title:
                        move_win(h, m1_bounds[0], m1_bounds[1], m1_w, m1_h)
                    elif any(w in title for w in ["pdf", "acrobat", "reader"]):
                        m2_w = m2_bounds[2] - m2_bounds[0]
                        m2_h = m2_bounds[3] - m2_bounds[1]
                        move_win(h, m2_bounds[0], m2_bounds[1], m2_w, m2_h)

            return f"Workspace layout restored for preset: '{preset}'."
        except Exception as e:
            logger.error(f"Error arranging workspace: {e}")
            return f"Error arranging workspace: {e}"

    def arrange_windows_layout(
        self,
        layout_preset: str = "split_left_right",
        window_titles: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Arrange visible desktop windows into grid layouts ('split_left_right', 'quad_tile', 'center', etc.).
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

        sw = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        sh = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

        arranged = []

        if layout_preset == "split_left_right" and len(visible_windows) >= 2:
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

    # ── Keyboard & Mouse Control ─────────────────────────────────────────

    async def type_text(self, text: str) -> str:
        """
        Type text at current cursor position with win32api fallback.
        """
        try:
            pyautogui.FAILSAFE = False
            pyautogui.typewrite(text, interval=0.01) if text.isascii() else pyautogui.write(text)
            logger.info("Typed text: '{}'", text[:50])
            return f"Typed: '{text[:50]}{'...' if len(text) > 50 else ''}'"
        except Exception as e:
            try:
                import ctypes
                for ch in text:
                    vk = ctypes.windll.user32.VkKeyScanW(ord(ch))
                    if vk != -1:
                        ctypes.windll.user32.keybd_event(vk & 0xFF, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(vk & 0xFF, 0, 2, 0)
                logger.info("Typed text via win32 fallback: '{}'", text[:50])
                return f"Typed: '{text[:50]}'"
            except Exception as e2:
                logger.error("Error typing text: {}", e)
                return f"Error typing text: {e}"

    async def press_hotkey(self, keys: str) -> str:
        """
        Press a keyboard hotkey combination (e.g. 'ctrl+c', 'win+d').
        """
        try:
            key_list = [k.strip().lower() for k in keys.split("+")]
            pyautogui.hotkey(*key_list)
            logger.info("Pressed hotkey: {}", keys)
            return f"Pressed hotkey: {keys}"
        except Exception as e:
            logger.error("Error pressing hotkey '{}': {}", keys, e)
            return f"Error pressing hotkey '{keys}': {e}"

    async def move_mouse(self, x: int, y: int) -> str:
        """
        Move the mouse cursor with safe screen clamping.
        """
        try:
            safe_x = max(2, int(x))
            safe_y = max(2, int(y))
            pyautogui.moveTo(safe_x, safe_y, duration=0.3)
            logger.info("Moved mouse to ({}, {})", safe_x, safe_y)
            return f"Moved mouse to ({safe_x}, {safe_y})"
        except Exception as e:
            logger.error("Error moving mouse: {}", e)
            return f"Error moving mouse: {e}"

    async def click_mouse(
        self,
        button: str = "left",
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> str:
        """
        Click mouse button at current or specified coordinate.
        """
        try:
            kwargs: Dict[str, Any] = {"button": button}
            if x is not None and y is not None:
                safe_x = max(2, int(x))
                safe_y = max(2, int(y))
                kwargs["x"] = safe_x
                kwargs["y"] = safe_y
                pos = f"({safe_x}, {safe_y})"
            else:
                pos = "current position"
            pyautogui.click(**kwargs)
            logger.info("Clicked {} at {}", button, pos)
            return f"Clicked {button} button at {pos}"
        except Exception as e:
            logger.error("Error clicking mouse: {}", e)
            return f"Error clicking mouse: {e}"

    async def scroll(self, direction: str = "down", amount: int = 3) -> str:
        """
        Scroll the mouse wheel up or down.
        """
        try:
            clicks = amount if direction.lower() == "up" else -amount
            pyautogui.scroll(clicks)
            logger.info("Scrolled {} by {}", direction, amount)
            return f"Scrolled {direction} by {amount}"
        except Exception as e:
            logger.error("Error scrolling: {}", e)
            return f"Error scrolling: {e}"

    # ── File Operations ──────────────────────────────────────────────────

    async def create_file(self, path: str, content: str = "") -> str:
        """
        Create a new file with content.
        """
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            logger.info("Created file: {}", path)
            return f"Created file: {path}"
        except Exception as e:
            logger.error("Error creating file '{}': {}", path, e)
            return f"Error creating file '{path}': {e}"

    async def create_folder(self, path: str) -> str:
        """
        Create a new folder path.
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            logger.info("Created folder: {}", path)
            return f"Created folder: {path}"
        except Exception as e:
            logger.error("Error creating folder '{}': {}", path, e)
            return f"Error creating folder '{path}': {e}"

    async def rename_file(self, old_path: str, new_path: str) -> str:
        """
        Rename or move a file or folder.
        """
        try:
            src = Path(old_path)
            dst = Path(new_path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            logger.info("Renamed '{}' → '{}'", old_path, new_path)
            return f"Renamed '{old_path}' to '{new_path}'"
        except Exception as e:
            logger.error("Error renaming '{}' → '{}': {}", old_path, new_path, e)
            return f"Error renaming: {e}"

    async def delete_file(self, path: str) -> str:
        """
        Delete a file or folder after safety classification check.
        """
        category, msg = self.safety.check_action(f"delete file: {path}")
        if category == ActionCategory.BLOCKED:
            logger.warning("Delete blocked: {}", path)
            return f"Blocked: {msg}"
        if category == ActionCategory.NEEDS_CONFIRMATION:
            logger.info("Delete needs confirmation: {}", path)
            return f"I need your confirmation to delete '{path}'. This action is potentially dangerous."

        try:
            target = Path(path)
            if target.is_file():
                target.unlink()
                logger.info("Deleted file: {}", path)
                return f"Deleted file: {path}"
            elif target.is_dir():
                shutil.rmtree(target)
                logger.info("Deleted folder: {}", path)
                return f"Deleted folder: {path}"
            else:
                return f"Path not found: {path}"
        except Exception as e:
            logger.error("Error deleting '{}': {}", path, e)
            return f"Error deleting '{path}': {e}"

    # ── Terminal Command Execution ───────────────────────────────────────

    async def run_terminal_command(self, command: str) -> str:
        """
        Execute a shell command with safety checks and timeout.
        """
        is_safe, reason = self.safety.check_terminal_command(command)
        if not is_safe:
            logger.warning("Terminal command blocked: {} — {}", command, reason)
            return f"Command blocked: {reason}"

        logger.info("Executing terminal command: {}", command)

        try:
            result = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=30)

            output = stdout.decode("utf-8", errors="replace").strip()
            errors = stderr.decode("utf-8", errors="replace").strip()

            if result.returncode == 0:
                response = output if output else "Command executed successfully (no output)."
            else:
                response = f"Command failed (exit code {result.returncode})."
                if output:
                    response += f"\nOutput: {output}"
                if errors:
                    response += f"\nErrors: {errors}"

            if len(response) > 2000:
                response = response[:2000] + "\n... (output truncated)"

            return response

        except asyncio.TimeoutError:
            logger.error("Terminal command timed out: {}", command)
            return "Command timed out after 30 seconds."
        except Exception as e:
            logger.error("Terminal command error: {}", e)
            return f"Error executing command: {e}"

    # ── Window Management & System Information ────────────────────────────

    async def minimize_all_windows(self) -> str:
        """
        Minimize all windows to show desktop.
        """
        try:
            pyautogui.hotkey("win", "d")
            logger.info("Minimised all windows")
            return "Minimised all windows (showing desktop)."
        except Exception as e:
            logger.error("Error minimising windows: {}", e)
            return f"Error minimising windows: {e}"

    async def get_active_window(self) -> Dict[str, Any]:
        """
        Get information about current active window.
        """
        try:
            window = pyautogui.getActiveWindow()
            if window:
                return {
                    "title": window.title,
                    "position": {"x": window.left, "y": window.top},
                    "size": {"width": window.width, "height": window.height},
                }
            return {"title": "Unknown", "position": {"x": 0, "y": 0}, "size": {"width": 0, "height": 0}}
        except Exception as e:
            logger.error("Error getting active window: {}", e)
            return {"title": "Error", "error": str(e)}

    async def get_system_info(self) -> Dict[str, Any]:
        """
        Collect current CPU, memory, disk, OS, and battery metrics.
        """
        import psutil

        try:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time

            info: Dict[str, Any] = {
                "os": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                },
                "cpu": {
                    "usage_percent": cpu_percent,
                    "cores_physical": psutil.cpu_count(logical=False),
                    "cores_logical": psutil.cpu_count(logical=True),
                    "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "usage_percent": memory.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "usage_percent": round(disk.percent, 1),
                },
                "uptime_hours": round(uptime / 3600, 2),
                "username": os.getenv("USERNAME", os.getenv("USER", "unknown")),
            }

            try:
                battery = psutil.sensors_battery()
                if battery:
                    info["battery"] = {
                        "percent": battery.percent,
                        "plugged_in": battery.power_plugged,
                        "time_left_minutes": round(battery.secsleft / 60, 1) if battery.secsleft > 0 else None,
                    }
            except Exception:
                pass

            return info

        except Exception as e:
            logger.error("Error collecting system info: {}", e)
            return {"error": str(e)}

    def adjust_volume(self, direction: str, amount: Optional[int] = None) -> str:
        """
        Adjust system speaker volume on Windows.
        """
        try:
            dir_clean = direction.lower().strip()
            if dir_clean == "mute":
                pyautogui.press("volumemute")
                return "Muted/unmuted system volume successfully."

            if dir_clean in ("max", "full", "100"):
                for _ in range(50):
                    pyautogui.press("volumeup")
                return "System volume set to maximum (100%) successfully."

            if dir_clean == "set" or (amount is not None and amount > 20):
                target_pct = min(max(amount if amount is not None else 50, 0), 100)
                for _ in range(50):
                    pyautogui.press("volumedown")
                up_presses = target_pct // 2
                for _ in range(up_presses):
                    pyautogui.press("volumeup")
                return f"Set system volume to exactly {target_pct}% successfully."

            steps = amount if amount is not None else 5
            key = "volumeup" if dir_clean == "up" else "volumedown"

            for _ in range(steps):
                pyautogui.press(key)
                time.sleep(0.01)

            return f"Adjusted system volume {direction} by {steps} steps successfully."
        except Exception as e:
            logger.error("Failed to adjust volume: {}", e)
            return f"Failed to adjust volume: {e}"

    def control_media(self, action: str) -> str:
        """
        Control media playback ('playpause', 'next', 'previous').
        """
        try:
            key_map = {
                "playpause": "playpause",
                "next": "nexttrack",
                "previous": "prevtrack",
            }
            key = key_map.get(action.lower().strip())
            if not key:
                return f"Unsupported media action: {action}"

            pyautogui.press(key)
            return f"Executed media control '{action}' successfully."
        except Exception as e:
            logger.error("Failed to execute media action '{}': {}", action, e)
            return f"Failed to execute media action '{action}': {e}"

    def focus_window(self, title: str) -> str:
        """
        Bring an open window matching the title to the foreground.
        """
        title_lower = title.lower().strip()
        if title_lower in ["current", "active", "current window", "active window", "this window", "this"]:
            return "The window is already focused."

        try:
            if HAS_WIN32:
                matching_hwnds = []
                def enum_windows_callback(hwnd, extra):
                    if win32gui.IsWindowVisible(hwnd):
                        txt = win32gui.GetWindowText(hwnd)
                        if txt and title_lower in txt.lower():
                            matching_hwnds.append((hwnd, txt))
                
                win32gui.EnumWindows(enum_windows_callback, None)
                
                if matching_hwnds:
                    hwnd, window_text = matching_hwnds[0]
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                    except Exception:
                        try:
                            win32gui.BringWindowToTop(hwnd)
                        except Exception:
                            pass
                    return f"Focused window '{window_text}' successfully."
        except Exception as e:
            logger.debug("Win32 focus window fallback failed: {}", e)

        try:
            windows = pyautogui.getWindowsWithTitle(title)
            if not windows:
                windows = [w for w in pyautogui.getAllWindows() if title_lower in w.title.lower()]

            if windows:
                win = windows[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                return f"Focused window '{win.title}' successfully."
            
            return f"No window found matching title: '{title}'"
        except Exception as e:
            logger.error("Error focusing window: {}", e)
            return f"Error focusing window: {e}"

    def minimize_window(self, title: str) -> str:
        """
        Minimize an open window matching the title.
        """
        title_lower = title.lower().strip()
        
        try:
            if HAS_WIN32:
                if title_lower in ["current", "active", "current window", "active window", "this window", "this"]:
                    hwnd = win32gui.GetForegroundWindow()
                    if hwnd:
                        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                        txt = win32gui.GetWindowText(hwnd) or "active window"
                        return f"Minimized active window '{txt}' successfully."
                    return "Could not determine active window."

                matching_hwnds = []
                def enum_windows_callback(hwnd, extra):
                    if win32gui.IsWindowVisible(hwnd):
                        txt = win32gui.GetWindowText(hwnd)
                        if txt and title_lower in txt.lower():
                            matching_hwnds.append((hwnd, txt))
                
                win32gui.EnumWindows(enum_windows_callback, None)
                
                if matching_hwnds:
                    hwnd, window_text = matching_hwnds[0]
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                    return f"Minimized window '{window_text}' successfully."
        except Exception as e:
            logger.debug("Win32 minimize window fallback failed: {}", e)

        try:
            windows = pyautogui.getWindowsWithTitle(title)
            if not windows:
                windows = [w for w in pyautogui.getAllWindows() if title_lower in w.title.lower()]

            if windows:
                win = windows[0]
                win.minimize()
                return f"Minimized window '{win.title}' successfully."
            
            return f"No window found matching title: '{title}'"
        except Exception as e:
            logger.error("Error minimizing window: {}", e)
            return f"Error minimizing window: {e}"

    def resize_window(
        self,
        title: str,
        position: str = "left",
        width: Optional[int] = None,
        height: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None
    ) -> str:
        """
        Resize and reposition window matching title using Win32 SetWindowPos.
        """
        title_lower = title.lower().strip()

        try:
            if not HAS_WIN32:
                return "Win32 GUI extensions unavailable for resize."

            from backend.services.perception.spatial_engine import SpatialEngine
            spatial = SpatialEngine()
            monitors = spatial.get_monitors()
            if monitors:
                m = monitors[0]
                screen_w = getattr(m, "width", 1920)
                screen_h = getattr(m, "height", 1080)
                screen_x = getattr(m, "x", 0)
                screen_y = getattr(m, "y", 0)
            else:
                sw, sh = pyautogui.size()
                screen_w, screen_h, screen_x, screen_y = sw, sh, 0, 0

            matching_hwnds = []
            def enum_windows_callback(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    txt = win32gui.GetWindowText(hwnd)
                    if txt and title_lower in txt.lower():
                        matching_hwnds.append((hwnd, txt))

            win32gui.EnumWindows(enum_windows_callback, None)

            if not matching_hwnds:
                if title_lower in ["current", "active", "active window", "this window", "this"]:
                    hwnd = win32gui.GetForegroundWindow()
                    txt = win32gui.GetWindowText(hwnd) or "active window"
                    matching_hwnds.append((hwnd, txt))

            if not matching_hwnds:
                return f"No visible window found matching title: '{title}'"

            target_hwnd, win_text = matching_hwnds[0]

            pos_lower = position.lower().strip()
            if pos_lower in ["left", "left_half", "left side"]:
                target_x = screen_x
                target_y = screen_y
                target_w = screen_w // 2
                target_h = screen_h
            elif pos_lower in ["right", "right_half", "right side"]:
                target_x = screen_x + (screen_w // 2)
                target_y = screen_y
                target_w = screen_w // 2
                target_h = screen_h
            elif pos_lower == "maximize":
                win32gui.ShowWindow(target_hwnd, win32con.SW_MAXIMIZE)
                return f"Maximized window '{win_text}' successfully."
            elif pos_lower == "center":
                target_w = width or int(screen_w * 0.7)
                target_h = height or int(screen_h * 0.8)
                target_x = screen_x + (screen_w - target_w) // 2
                target_y = screen_y + (screen_h - target_h) // 2
            else:
                target_w = width or (screen_w // 2)
                target_h = height or screen_h
                target_x = x if x is not None else screen_x
                target_y = y if y is not None else screen_y

            try:
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_hwnd)
            except Exception as e:
                logger.debug("SetForegroundWindow notice: {}", e)

            win32gui.SetWindowPos(
                target_hwnd,
                win32con.HWND_TOP,
                target_x,
                target_y,
                target_w,
                target_h,
                win32con.SWP_SHOWWINDOW
            )
            return f"Resized and moved window '{win_text}' to position '{position}' ({target_w}x{target_h})."
        except Exception as e:
            logger.error("Error resizing window: {}", e)
            return f"Error resizing window: {e}"

    # ── Clipboard Intelligence & Folder Watching ──────────────────────────

    def get_clipboard_content(self) -> Dict[str, Any]:
        """
        Read clipboard text, classify content type, and maintain history buffer.
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
            "content": text[:2000],
            "content_type": detected_type,
            "length": len(text)
        }

        if not self._clipboard_history or self._clipboard_history[0]["content"] != record["content"]:
            self._clipboard_history.insert(0, record)
            if len(self._clipboard_history) > 20:
                self._clipboard_history.pop()

        return record

    def get_clipboard_history(self) -> List[Dict[str, Any]]:
        """Return history buffer of recent clipboard items."""
        return self._clipboard_history

    def check_folder_changes(self, folder_path: str, known_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Inspect directory for added, modified, or removed files.
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


# Backward-compatible alias
AutomationService = DesktopExecutor

__all__ = [
    "DesktopExecutor",
    "AutomationService",
    "APP_PATHS",
    "APP_PROCESS_NAMES",
    "_resolve_user_path",
    "_resolve_app_path",
]

