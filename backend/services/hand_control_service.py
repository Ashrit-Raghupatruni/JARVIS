"""
JARVIS AI OS - Hand Gesture Pointer & Desktop Control Service.

Simulates system-level mouse movements, clicks, double clicks, drag-and-drops,
scrolls, and key/hotkey presses. Optimised for low-latency real-time control.
Uses native win32api on Windows for instantaneous cursor movements, with pyautogui fallbacks.
"""

import time
import threading
from typing import Optional, Dict, Any, Tuple, List
from loguru import logger
import pyautogui

try:
    import win32api
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from backend.services.perception.gesture_engine import gesture_engine

# Disable PyAutoGUI fail-safe to prevent corner-screen aborts during gesture control
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0


class HandControlService:
    """Service to handle real-time hand gesture mouse and desktop interactions via standalone backend CV worker."""

    def __init__(self, confidence_threshold: float = 0.7, debounce_ms: float = 150.0) -> None:
        self.is_dragging = False
        self.confidence_threshold = confidence_threshold
        self.debounce_ms = debounce_ms
        self._last_action_time = 0.0
        self._tracking_active = False
        self._worker_thread: Optional[threading.Thread] = None
        logger.info("HandControlService initialized. Native win32api: {}, OpenCV: {}", HAS_WIN32, HAS_CV2)

    def move_cursor(self, x: int, y: int) -> None:
        """Move cursor to absolute coordinates across virtual desktop using sub-millisecond win32api."""
        try:
            if HAS_WIN32:
                try:
                    min_x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
                    min_y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
                    max_x = min_x + win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN) - 1
                    max_y = min_y + win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN) - 1
                    x = max(min_x, min(max_x, x))
                    y = max(min_y, min(max_y, y))
                    win32api.SetCursorPos((x, y))
                    return
                except Exception:
                    pass

            screen_w, screen_h = pyautogui.size()
            x = max(0, min(screen_w - 1, x))
            y = max(0, min(screen_h - 1, y))
            pyautogui.moveTo(x, y)
        except Exception as e:
            logger.debug("Move cursor warning: {}", e)

    def move_cursor_normalized(self, norm_x: float, norm_y: float, target_monitor: Optional[int | str] = None) -> Tuple[int, int]:
        """
        Move cursor using normalized [0.0, 1.0] coordinates mapped across multi-monitor virtual desktop or target display.
        """
        from backend.services.perception.spatial_engine import SpatialEngine
        from backend.services.manager import ServiceManager
        spatial = ServiceManager.get_instance("spatial_engine")
        if not spatial:
            spatial = SpatialEngine()

        target_x, target_y = spatial.map_normalized_to_screen(norm_x, norm_y, target_monitor=target_monitor)
        self.move_cursor(target_x, target_y)
        return target_x, target_y

    def click_mouse(self, button: str = "left", action: str = "click") -> None:
        """Execute clicking actions with debouncing guard."""
        now = time.time() * 1000
        if action == "click" and (now - self._last_action_time) < self.debounce_ms:
            logger.debug("Click ignored due to debounce lock ({}ms)", self.debounce_ms)
            return

        self._last_action_time = now
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
        """Scroll wheel up or down."""
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
        """Execute key press mapping for custom gesture shortcuts."""
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
            elif action in ("toggle_media_play_pause", "toggle_mute_audio", "next_track", "previous_track"):
                if action == "toggle_media_play_pause":
                    pyautogui.press("playpause")
                elif action == "toggle_mute_audio":
                    pyautogui.press("volumemute")
                elif action == "next_track":
                    pyautogui.press("nexttrack")
                elif action == "previous_track":
                    pyautogui.press("prevtrack")
            else:
                logger.warning("Unknown keyboard action: {}", action)
        except Exception as e:
            logger.error("Failed to execute keyboard action: {}", e)

    def handle_gesture_event(self, gesture_result: Dict[str, Any], cursor_pos: Optional[Tuple[int, int]] = None) -> bool:
        """Decoupled gesture event router with confidence filtering and action execution."""
        gesture = gesture_result.get("gesture", "NONE")
        confidence = gesture_result.get("confidence", 0.0)

        if confidence < self.confidence_threshold or gesture == "NONE":
            return False

        if cursor_pos:
            self.move_cursor(cursor_pos[0], cursor_pos[1])

        action = gesture_result.get("action")
        if gesture == "PINCH":
            self.click_mouse(button="left", action="click")
            return True
        elif action:
            self.execute_keyboard_action(action)
            return True

        return False

    def start_background_tracking(self, camera_index: int = 0) -> bool:
        """Start the standalone backend OpenCV camera worker thread."""
        if self._tracking_active:
            logger.info("Hand tracking worker already running.")
            return True

        if not HAS_CV2:
            logger.warning("OpenCV (cv2) not available. Cannot start camera worker.")
            return False

        self._tracking_active = True
        self._worker_thread = threading.Thread(
            target=self._camera_worker_loop,
            args=(camera_index,),
            daemon=True,
            name="JARVIS-HandTracker-CV"
        )
        self._worker_thread.start()
        logger.info("✓ Standalone Hand Tracking Camera Worker started on Camera Index {}", camera_index)
        return True

    def stop_background_tracking(self) -> None:
        """Stop the background camera tracking thread cleanly."""
        self._tracking_active = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        logger.info("Hand Tracking Camera Worker stopped.")

    def _camera_worker_loop(self, camera_index: int) -> None:
        """Standalone OpenCV capture loop."""
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
        if not cap.isOpened():
            logger.warning("Could not open camera index {} for hand tracking.", camera_index)
            self._tracking_active = False
            return

        try:
            while self._tracking_active:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue

                # Process frame (frame processing / landmark detection)
                time.sleep(0.033)  # ~30 FPS loop rate
        except Exception as e:
            logger.error("Hand tracking camera worker exception: {}", e)
        finally:
            cap.release()
            self._tracking_active = False

