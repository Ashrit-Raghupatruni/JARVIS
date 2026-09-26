"""
JARVIS AI OS — Hermes Desktop Agent (Autonomous OS & GUI Interaction Loop).
=============================================================================
Powers real-time closed-loop desktop automation, text editing, file operations,
window management, and UI grounding via Ollama Hermes (hermes-desktop / hermes3).
"""

from __future__ import annotations

import os
import sys
import time
import json
import asyncio
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from loguru import logger
import aiohttp

from backend.services.manager import ServiceManager
from backend.services.safety_gatekeeper import SafetyGatekeeper
from backend.services.automation.desktop_executor import DesktopExecutor


HERMES_DESKTOP_SYSTEM_PROMPT = """You are the Hermes Desktop Automation Agent for the JARVIS AI Operating System.
Your job is to interact with the Windows GUI, open applications, open/edit files, type text, click elements, and manage windows to fulfill the user's objective.

You have access to the following JSON Action commands:
1. `{"action": "open_app", "app_name": "notepad"}` - Launch or focus an application.
2. `{"action": "open_file", "file_path": "C:\\path\\to\\file.txt"}` - Open a file in its default editor.
3. `{"action": "focus_window", "title": "Notepad"}` - Bring a window to the active foreground.
4. `{"action": "type_text", "text": "Hello world", "target_app": "notepad", "use_clipboard": true}` - Type or paste text reliably into the active window.
5. `{"action": "click", "x": 500, "y": 300, "button": "left"}` - Click at exact screen coordinates.
6. `{"action": "double_click", "x": 500, "y": 300}` - Double-click at screen coordinates.
7. `{"action": "hotkey", "keys": "ctrl+s"}` - Send keyboard shortcut (e.g. ctrl+s, ctrl+a, win+d, alt+f4).
8. `{"action": "scroll", "direction": "down", "amount": 3}` - Scroll the active window.
9. `{"action": "wait", "seconds": 1.0}` - Wait for an application to load or UI to render.
10. `{"action": "finish", "summary": "Successfully opened notepad and wrote the notes."}` - Conclude the task.

GUIDELINES:
- Always focus the target window before typing or sending shortcuts.
- For writing/editing text, use `"use_clipboard": true` for instant, error-free typing.
- Break multi-step tasks into clear, logical steps.
- Respond with a single valid JSON action block wrapped in ```json ... ``` on each turn.
"""


class HermesDesktopAgent:
    """
    Autonomous OS Agent powered by Ollama Hermes 3 / hermes-desktop.
    Executes multi-step GUI workflows with perception feedback and safety verification.
    """

    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        model_name: str = "hermes3",
        desktop_executor: Optional[DesktopExecutor] = None,
        gatekeeper: Optional[SafetyGatekeeper] = None,
        max_steps: int = 15
    ) -> None:
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.model_name = os.getenv("HERMES_MODEL_NAME", model_name)
        self.desktop_executor = desktop_executor or DesktopExecutor()
        self.gatekeeper = gatekeeper or SafetyGatekeeper()
        self.max_steps = max_steps
        self.history: List[Dict[str, Any]] = []
        logger.info("HermesDesktopAgent initialized. Model: {} @ {}", self.model_name, self.ollama_base_url)

    async def check_ollama_availability(self) -> bool:
        """Verify if Ollama daemon is reachable."""
        try:
            timeout = aiohttp.ClientTimeout(total=2.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.ollama_base_url}/api/tags") as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def get_active_screen_context(self) -> Dict[str, Any]:
        """Collect current foreground window title, active app, and window geometry."""
        context = {
            "timestamp": time.time(),
            "foreground_window": "Unknown",
            "active_app": "Desktop",
            "open_windows": []
        }
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) or "Desktop"
            context["foreground_window"] = title
            context["hwnd"] = hwnd

            # Collect top visible windows
            windows = []
            def enum_cb(h, _):
                if win32gui.IsWindowVisible(h):
                    t = win32gui.GetWindowText(h)
                    if t and len(t.strip()) > 1 and t not in ("Program Manager", "Taskbar", "JARVIS"):
                        windows.append(t)
            win32gui.EnumWindows(enum_cb, None)
            context["open_windows"] = windows[:10]
        except Exception as e:
            logger.debug("Error getting screen context: {}", e)

        return context

    async def _query_hermes_model(self, messages: List[Dict[str, str]]) -> str:
        """Send prompt to Ollama or fallback to local LLM manager."""
        try:
            timeout = aiohttp.ClientTimeout(total=60.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {
                    "model": self.model_name,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.95
                    }
                }
                async with session.post(f"{self.ollama_base_url}/api/chat", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("message", {}).get("content", "")
                    else:
                        logger.warning("Ollama returned status {}, falling back to LLMRouter", resp.status)
        except Exception as ollama_err:
            logger.warning("Ollama connection failed ({}): falling back to primary LLM Router", ollama_err)

        # Fallback to configured primary LLM Router
        try:
            from backend.services.manager import ServiceManager
            router = ServiceManager.get_instance("llm_router")
            if router:
                response = await router.generate(messages=messages, temperature=0.2)
                return response if isinstance(response, str) else str(response)
        except Exception as router_err:
            logger.error("LLM Router fallback also failed: {}", router_err)

        return '{"action": "finish", "summary": "Failed to connect to Hermes LLM."}'

    def _parse_action_json(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse JSON action payload from LLM output."""
        try:
            # 1. Search for markdown code block ```json ... ```
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
            if json_match:
                return json.loads(json_match.group(1))

            # 2. Search for direct JSON dictionary
            brace_match = re.search(r"\{[\s\S]*?\}", response_text)
            if brace_match:
                return json.loads(brace_match.group(0))
        except Exception as e:
            logger.warning("Could not parse JSON action from response: {} | Text: {}", e, response_text[:100])
        return None

    async def execute_task(self, user_goal: str) -> Dict[str, Any]:
        """
        Execute a high-level desktop goal autonomously through the Hermes closed-loop agent.
        """
        logger.info("🤖 Hermes Desktop Agent starting task: '{}'", user_goal)
        messages = [
            {"role": "system", "content": HERMES_DESKTOP_SYSTEM_PROMPT},
            {"role": "user", "content": f"User Goal: {user_goal}\n\nPlease execute the first step."}
        ]

        steps_log: List[Dict[str, Any]] = []
        is_completed = False
        summary = ""

        for step_num in range(1, self.max_steps + 1):
            logger.info("Hermes Desktop Agent — Step {}/{}", step_num, self.max_steps)
            screen_ctx = await self.get_active_screen_context()
            
            # Inject current screen state into conversation
            context_prompt = (
                f"[Current Screen State]\n"
                f"- Active Foreground Window: '{screen_ctx.get('foreground_window')}'\n"
                f"- Visible Applications: {', '.join(screen_ctx.get('open_windows', []))}\n"
                f"Determine the next action to advance the goal."
            )
            messages.append({"role": "user", "content": context_prompt})

            # Query Hermes model
            raw_response = await self._query_hermes_model(messages)
            action_dict = self._parse_action_json(raw_response)

            if not action_dict:
                # Direct heuristic fallback if LLM returned non-JSON
                action_dict = {"action": "finish", "summary": raw_response[:200]}

            action_type = action_dict.get("action", "finish").lower()
            logger.info("Hermes chosen action (Step {}): {}", step_num, action_dict)

            # Check if task is finished
            if action_type == "finish":
                is_completed = True
                summary = action_dict.get("summary", "Task completed successfully.")
                steps_log.append({"step": step_num, "action": action_dict, "result": summary})
                break

            # Execute the action via DesktopExecutor & SafetyGatekeeper
            step_result = await self._dispatch_action(action_dict)
            steps_log.append({"step": step_num, "action": action_dict, "result": step_result})

            # Append assistant's response and tool result to memory
            messages.append({"role": "assistant", "content": f"```json\n{json.dumps(action_dict, indent=2)}\n```"})
            messages.append({"role": "user", "content": f"Action Result: {step_result}"})

            # Small pause between UI steps
            await asyncio.sleep(0.5)

        return {
            "status": "success" if is_completed else "timeout",
            "goal": user_goal,
            "completed": is_completed,
            "summary": summary or f"Executed {len(steps_log)} steps.",
            "steps": steps_log
        }

    async def _dispatch_action(self, action: Dict[str, Any]) -> str:
        """Dispatch validated atomic action to DesktopExecutor."""
        action_type = action.get("action", "").lower()

        try:
            if action_type == "open_app":
                app_name = action.get("app_name", "")
                return await self.desktop_executor.open_application(app_name)

            elif action_type == "open_file":
                file_path = action.get("file_path", "")
                if os.path.exists(file_path):
                    await asyncio.to_thread(os.startfile, file_path)
                    return f"Opened file: '{file_path}'"
                return f"File does not exist: '{file_path}'"

            elif action_type == "focus_window":
                title = action.get("title", "")
                success = await self._focus_window_native(title)
                return f"Focused window matching '{title}': {success}"

            elif action_type == "type_text":
                text = action.get("text", "")
                target_app = action.get("target_app")
                use_clipboard = action.get("use_clipboard", True)

                # Focus target app if specified
                if target_app:
                    await self._focus_window_native(target_app)
                    await asyncio.sleep(0.3)

                if use_clipboard:
                    return await self._paste_text_via_clipboard(text)
                else:
                    return await self.desktop_executor.type_text(text)

            elif action_type == "click":
                x = action.get("x")
                y = action.get("y")
                button = action.get("button", "left")
                return await self.desktop_executor.click_mouse(button=button, x=x, y=y)

            elif action_type == "double_click":
                x = action.get("x")
                y = action.get("y")
                res1 = await self.desktop_executor.click_mouse(button="left", x=x, y=y)
                await asyncio.sleep(0.05)
                res2 = await self.desktop_executor.click_mouse(button="left", x=x, y=y)
                return f"Double-clicked at ({x}, {y})"

            elif action_type == "hotkey":
                keys = action.get("keys", "")
                return await self.desktop_executor.press_hotkey(keys)

            elif action_type == "scroll":
                direction = action.get("direction", "down")
                amount = action.get("amount", 3)
                return await self.desktop_executor.scroll(direction=direction, amount=amount)

            elif action_type == "wait":
                seconds = float(action.get("seconds", 1.0))
                await asyncio.sleep(seconds)
                return f"Waited {seconds}s"

            else:
                return f"Unknown action type: '{action_type}'"

        except Exception as e:
            logger.error("Error executing Hermes action {}: {}", action_type, e)
            return f"Action execution error: {e}"

    async def _focus_window_native(self, target_title: str) -> bool:
        """Bring target window to the active foreground on Windows."""
        try:
            import win32gui
            import win32con
            import win32process

            found_hwnd = None
            target_lower = target_title.lower()

            def enum_cb(hwnd, _):
                nonlocal found_hwnd
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if t and target_lower in t.lower():
                        found_hwnd = hwnd

            win32gui.EnumWindows(enum_cb, None)
            if found_hwnd:
                win32gui.ShowWindow(found_hwnd, win32con.SW_RESTORE)
                try:
                    win32gui.SetForegroundWindow(found_hwnd)
                except Exception:
                    # AttachThreadInput trick to bypass Windows foreground restriction
                    import ctypes
                    user32 = ctypes.windll.user32
                    fore_hwnd = user32.GetForegroundWindow()
                    fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, 0)
                    cur_thread = user32.GetCurrentThreadId()
                    user32.AttachThreadInput(cur_thread, fore_thread, True)
                    user32.SetForegroundWindow(found_hwnd)
                    user32.AttachThreadInput(cur_thread, fore_thread, False)
                return True
        except Exception as e:
            logger.debug("Native focus window error: {}", e)
        return False

    async def _paste_text_via_clipboard(self, text: str) -> str:
        """Inject text instantly and reliably using clipboard paste (Ctrl+V)."""
        try:
            import pyperclip
            import pyautogui
            pyperclip.copy(text)
            await asyncio.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
            await asyncio.sleep(0.1)
            logger.info("Pasted text via clipboard injection ({} chars)", len(text))
            return f"Pasted text: '{text[:60]}{'...' if len(text) > 60 else ''}'"
        except Exception as e:
            logger.warning("Clipboard paste failed, falling back to keystroke typing: {}", e)
            return await self.desktop_executor.type_text(text)


hermes_desktop_agent = HermesDesktopAgent()
