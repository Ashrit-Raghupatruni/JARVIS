"""
JARVIS AI OS - Hand Gesture Pointer & Desktop Control Service.

Simulates system-level mouse movements, clicks, double clicks, drag-and-drops,
scrolls, and key/hotkey presses. Optimised for low-latency real-time control.
Uses native win32api on Windows for instantaneous cursor movements, with pyautogui fallbacks.
"""

import time
from typing import Optional
from loguru import logger
import pyautogui

try:
    import win32api
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Disable PyAutoGUI fail-safe to prevent corner-screen aborts during gesture control
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0


class HandControlService:
    """Service to handle real-time hand gesture mouse and desktop interactions."""

    def __init__(self) -> None:
        self.is_dragging = False
        logger.info("HandControlService initialized. Native win32api: {}", HAS_WIN32)

    def move_cursor(self, x: int, y: int) -> None:
        """
        Move cursor to absolute coordinates on screen.
        Uses win32api directly on Windows for maximum speed (sub-millisecond),
        otherwise falls back to pyautogui.
        """
        try:
            screen_w, screen_h = pyautogui.size()
            x = max(0, min(screen_w - 1, x))
            y = max(0, min(screen_h - 1, y))

            if HAS_WIN32:
                try:
                    win32api.SetCursorPos((x, y))
                    return
                except Exception:
                    pass
            pyautogui.moveTo(x, y)
        except Exception as e:
            logger.debug("Move cursor warning: {}", e)

    def click_mouse(self, button: str = "left", action: str = "click") -> None:
        """
        Execute clicking actions.
        button: "left" or "right"
        action: "click", "double_click", "press" (for drag), "release" (for drop)
        """
        try:
            executed = False
            if HAS_WIN32:
                try:
                    x, y = win32api.GetCursorPos()
                    if button == "left":
                        down_flag = win32con.MOUSEEVENTF_LEFTDOWN
                        up_flag = win32con.MOUSEEVENTF_LEFTUP
                    else:
                        down_flag = win32con.MOUSEEVENTF_RIGHTDOWN
                        up_flag = win32con.MOUSEEVENTF_RIGHTUP

                    if action == "click":
                        win32api.mouse_event(down_flag, x, y, 0, 0)
                        win32api.mouse_event(up_flag, x, y, 0, 0)
                    elif action == "double_click":
                        win32api.mouse_event(down_flag, x, y, 0, 0)
                        win32api.mouse_event(up_flag, x, y, 0, 0)
                        time.sleep(0.08)
                        win32api.mouse_event(down_flag, x, y, 0, 0)
                        win32api.mouse_event(up_flag, x, y, 0, 0)
                    elif action == "press":
                        if not self.is_dragging:
                            win32api.mouse_event(down_flag, x, y, 0, 0)
                            self.is_dragging = True
                    elif action == "release":
                        if self.is_dragging:
                            win32api.mouse_event(up_flag, x, y, 0, 0)
                            self.is_dragging = False
                    executed = True
                except Exception:
                    executed = False

            if not executed:
                if action == "click":
                    pyautogui.click(button=button)
                elif action == "double_click":
                    pyautogui.doubleClick(button=button)
                elif action == "press":
                    if not self.is_dragging:
                        pyautogui.mouseDown(button=button)
                        self.is_dragging = True
                elif action == "release":
                    if self.is_dragging:
                        pyautogui.mouseUp(button=button)
                        self.is_dragging = False

            logger.debug("Simulated mouse {} on {}", action, button)
        except Exception as e:
            logger.debug("Click mouse warning: {}", e)

    def scroll(self, direction: str = "down", amount: int = 120) -> None:
        """
        Scroll wheel up or down.
        """
        try:
            executed = False
            if HAS_WIN32:
                try:
                    wheel_delta = 120 * amount if direction == "up" else -120 * amount
                    x, y = win32api.GetCursorPos()
                    win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, x, y, wheel_delta, 0)
                    executed = True
                except Exception:
                    executed = False

            if not executed:
                clicks = amount if direction == "up" else -amount
                pyautogui.scroll(clicks)
        except Exception as e:
            logger.debug("Scroll warning: {}", e)

    def execute_keyboard_action(self, action: str) -> None:
        """
        Execute key press mapping for custom gesture shortcuts.
        """
        try:
            logger.info("Executing keyboard gesture action: {}", action)
            if action == "back":
                pyautogui.hotkey("alt", "left")
            elif action == "forward":
                pyautogui.hotkey("alt", "right")
            elif action == "home":
                pyautogui.press("browserhome")
            elif action == "escape":
                pyautogui.press("escape")
            elif action == "window_switching":
                pyautogui.hotkey("win", "tab")
            elif action == "zoom_in":
                pyautogui.hotkey("ctrl", "=")
            elif action == "zoom_out":
                pyautogui.hotkey("ctrl", "-")
            elif action == "volume_up":
                pyautogui.press("volumeup")
            elif action == "volume_down":
                pyautogui.press("volumedown")
            elif action == "volume_mute":
                pyautogui.press("volumemute")
            else:
                logger.warning("Unknown keyboard action: {}", action)
        except Exception as e:
            logger.error("Failed to execute keyboard action: {}", e)
