"""
JARVIS AI Desktop Assistant - Desktop Automation Service.

Provides comprehensive desktop automation capabilities including
application management, keyboard/mouse control, file operations,
terminal command execution, and system information queries.
Uses pyautogui for input simulation and subprocess for app management.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyautogui

from backend.services.safety import SafetyService, classify_action, sanitize_command, ActionCategory
from backend.utils.logger import logger

# ── Safety: prevent pyautogui from taking over the entire screen ─────────
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1  # Small pause between actions

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

# Process names for closing applications
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
}


def _resolve_user_path(path: str) -> str:
    """Replace ``{user}`` placeholder with the current username."""
    return path.replace("{user}", os.getenv("USERNAME", os.getenv("USER", "user")))


class AutomationService:
    """
    Desktop automation service for Windows.

    Provides high-level methods for application management, input
    simulation, file operations, and system queries. All destructive
    operations go through the safety service.
    """

    def __init__(self, safety_service: Optional[SafetyService] = None) -> None:
        """
        Initialise the automation service.

        Args:
            safety_service: Optional safety service for checking
                            dangerous operations. If not provided,
                            a default instance is created.
        """
        self.safety = safety_service or SafetyService()
        logger.info("AutomationService initialised")

    # ── Application Management ───────────────────────────────────────────

    async def open_application(self, app_name: str) -> str:
        """
        Open an application by its common name.

        Looks up the application in the known paths dictionary,
        falling back to ``start`` command for unknown apps.

        Args:
            app_name: Common application name (case-insensitive).

        Returns:
            Status message describing the result.
        """
        app_key = app_name.lower().strip()
        logger.info("Opening application: {}", app_name)

        try:
            if app_key in APP_PATHS:
                path = _resolve_user_path(APP_PATHS[app_key])

                # Handle ms-settings: style URIs
                if path.startswith("ms-settings:") or path.startswith("http"):
                    os.startfile(path)
                    return f"Opened {app_name} successfully."

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
                    subprocess.Popen(
                        [path],
                        shell=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                return f"Opened {app_name} successfully."

            else:
                # Try via start command (works for many Windows apps)
                subprocess.Popen(
                    ["cmd", "/c", "start", "", app_name],
                    shell=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return f"Attempted to open '{app_name}' via system search."

        except FileNotFoundError:
            # Fallback: try via start command
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
                return f"Failed to open '{app_name}': {e2}"

        except Exception as e:
            logger.error("Error opening '{}': {}", app_name, e)
            return f"Error opening '{app_name}': {e}"

    async def close_application(self, app_name: str) -> str:
        """
        Close a running application by its common name.

        Uses ``taskkill`` on Windows to terminate the process.

        Args:
            app_name: Common application name (case-insensitive).

        Returns:
            Status message.
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
                # Try case-insensitive search via WMIC
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

    # ── Keyboard & Mouse ─────────────────────────────────────────────────

    async def type_text(self, text: str) -> str:
        """
        Type text at the current cursor position.

        Args:
            text: The text to type.

        Returns:
            Confirmation message.
        """
        try:
            pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyautogui.write(text)
            logger.info("Typed text: '{}'", text[:50])
            return f"Typed: '{text[:50]}{'...' if len(text) > 50 else ''}'"
        except Exception as e:
            logger.error("Error typing text: {}", e)
            return f"Error typing text: {e}"

    async def press_hotkey(self, keys: str) -> str:
        """
        Press a keyboard hotkey combination.

        Args:
            keys: Key combination separated by ``+`` (e.g. ``ctrl+shift+s``).

        Returns:
            Confirmation message.
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
        Move the mouse cursor to screen coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            Confirmation message.
        """
        try:
            pyautogui.moveTo(x, y, duration=0.3)
            logger.info("Moved mouse to ({}, {})", x, y)
            return f"Moved mouse to ({x}, {y})"
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
        Click the mouse at the current or specified position.

        Args:
            button: Mouse button — ``left``, ``right``, or ``middle``.
            x: Optional X coordinate to click at.
            y: Optional Y coordinate to click at.

        Returns:
            Confirmation message.
        """
        try:
            kwargs: Dict[str, Any] = {"button": button}
            if x is not None and y is not None:
                kwargs["x"] = x
                kwargs["y"] = y
            pyautogui.click(**kwargs)
            pos = f"({x}, {y})" if x is not None else "current position"
            logger.info("Clicked {} at {}", button, pos)
            return f"Clicked {button} button at {pos}"
        except Exception as e:
            logger.error("Error clicking mouse: {}", e)
            return f"Error clicking mouse: {e}"

    async def scroll(self, direction: str = "down", amount: int = 3) -> str:
        """
        Scroll the mouse wheel.

        Args:
            direction: ``up`` or ``down``.
            amount: Number of scroll increments.

        Returns:
            Confirmation message.
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
        Create a new file with optional content.

        Args:
            path: Full path for the new file.
            content: Initial file content (default: empty).

        Returns:
            Status message.
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
        Create a new directory (including parents).

        Args:
            path: Full path for the new directory.

        Returns:
            Status message.
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

        Args:
            old_path: Current path.
            new_path: New path.

        Returns:
            Status message.
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
        Delete a file or folder after safety check.

        Args:
            path: Path to delete.

        Returns:
            Status message.
        """
        # Safety check
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

    # ── Terminal Commands ────────────────────────────────────────────────

    async def run_terminal_command(self, command: str) -> str:
        """
        Execute a shell command with safety checks.

        Args:
            command: The command to execute.

        Returns:
            Command output or error message.
        """
        # Safety check
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

            # Truncate very long output
            if len(response) > 2000:
                response = response[:2000] + "\n... (output truncated)"

            logger.info("Command result (exit {}): {}", result.returncode, response[:100])
            return response

        except asyncio.TimeoutError:
            logger.error("Terminal command timed out: {}", command)
            return "Command timed out after 30 seconds."
        except Exception as e:
            logger.error("Terminal command error: {}", e)
            return f"Error executing command: {e}"

    # ── Window Management ────────────────────────────────────────────────

    async def minimize_all_windows(self) -> str:
        """
        Minimize all windows (show desktop).

        Returns:
            Confirmation message.
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
        Get information about the currently active window.

        Returns:
            Dictionary with ``title``, ``position``, and ``size``.
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

    # ── System Information ───────────────────────────────────────────────

    async def get_system_info(self) -> Dict[str, Any]:
        """
        Collect current system information.

        Returns:
            Dictionary with CPU, memory, disk, OS, and battery details.
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

            # Battery info (laptops)
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

            logger.info("System info collected — CPU={}%, RAM={}%", cpu_percent, memory.percent)
            return info

        except Exception as e:
            logger.error("Error collecting system info: {}", e)
            return {"error": str(e)}
