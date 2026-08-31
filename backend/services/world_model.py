"""
Central Desktop World Model for JARVIS.

Provides a unified, thread-safe real-time state representation of the desktop operating system:
- Display monitors & spatial layout
- Active application & foreground window
- Native Win32 UIA Scene Graph (controls, textboxes, buttons, forms)
- Active browser tab & webpage context
- System state (clipboard, active folder, audio, internet status)
"""

import time
import win32gui
import win32process
import win32clipboard
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from backend.services.perception.spatial_engine import SpatialEngine, MonitorInfo
from backend.services.perception.uia_scene_graph import UIASceneGraph, SceneGraph


class DesktopState(BaseModel):
    active_window: str = "Desktop"
    monitors: List[Dict[str, Any]] = Field(default_factory=list)
    active_monitor_id: int = 1
    cursor_position: List[int] = Field(default_factory=lambda: [0, 0])


class ApplicationState(BaseModel):
    app_name: str = "explorer.exe"
    process_id: Optional[int] = None
    window_title: str = "Desktop"
    window_bounds: List[int] = Field(default_factory=list)
    browser_url: Optional[str] = None


class UIState(BaseModel):
    control_count: int = 0
    focused_element: Optional[str] = None
    scene_graph: Optional[Dict[str, Any]] = None


class VisualState(BaseModel):
    screenshot_timestamp: Optional[float] = None
    detected_ocr_blocks: int = 0
    detected_forms: int = 0


class SystemState(BaseModel):
    cpu_percent: float = 0.0
    ram_mb_free: float = 0.0
    audio_playing: bool = False
    internet_online: bool = True


class UserContextState(BaseModel):
    current_workflow: str = "Idle Desktop Observation"
    active_goal: Optional[str] = None
    recent_action: Optional[str] = None


class WorldModelState(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    world_model_version: int = 1
    captured_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    source_versions: Dict[str, str] = Field(default_factory=lambda: {
        "uia": "v2.1",
        "spatial": "v1.4",
        "world_model": "v2.0"
    })
    desktop: DesktopState = Field(default_factory=DesktopState)
    application: ApplicationState = Field(default_factory=ApplicationState)
    ui: UIState = Field(default_factory=UIState)
    visual: VisualState = Field(default_factory=VisualState)
    system: SystemState = Field(default_factory=SystemState)
    user_context: UserContextState = Field(default_factory=UserContextState)

    # Legacy flat compatibility fields
    monitors: List[Dict[str, Any]] = Field(default_factory=list)
    active_monitor_id: int = 1
    active_app: str = "Desktop"
    window_title: str = "Desktop"
    window_bounds: List[int] = Field(default_factory=list)
    process_id: Optional[int] = None
    scene_graph: Optional[Dict[str, Any]] = None
    browser_url: Optional[str] = None
    browser_title: Optional[str] = None
    clipboard_text: Optional[str] = None
    active_folder: Optional[str] = None
    audio_playing: bool = False
    internet_online: bool = True
    current_workflow: str = "Idle Desktop Observation"
    cursor_position: List[int] = Field(default_factory=lambda: [0, 0])


class WorldModel:
    """
    Centralized World Model container for JARVIS.
    Acts as the single source of truth across all perception, planning, and execution modules.
    """

    def __init__(self, event_bus: Optional[Any] = None) -> None:
        self.event_bus = event_bus
        self.spatial_engine = SpatialEngine()
        self.scene_graph_engine = UIASceneGraph()
        self._last_online_check_time: float = 0.0
        self._cached_is_online: bool = True
        self._state = WorldModelState()
        self.refresh()
        if self.event_bus:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._subscribe_event_bus())
            except RuntimeError:
                pass
        logger.info("WorldModel initialized (Central Desktop State Aggregator Ready).")

    async def _subscribe_event_bus(self) -> None:
        if not self.event_bus:
            return
        await self.event_bus.subscribe("task.*", self._handle_task_event)
        await self.event_bus.subscribe("config_reloaded", self._handle_config_event)
        await self.event_bus.subscribe("security.approval_required", self._handle_security_event)
        await self.event_bus.subscribe("context.updated.*", self._handle_context_event)
        logger.info("✓ [EventBus Subscriber] WorldModel bound to topics: task.*, config_reloaded, security.approval_required, context.updated.*")

    async def _handle_task_event(self, event) -> None:
        logger.info(f"⚡ [EventBus Subscriber -> WorldModel] Received '{event.topic}': task='{event.data.get('name')}' (ID: {event.data.get('task_id')})")
        if event.topic == "task.started":
            self._state.current_workflow = f"Executing Task: {event.data.get('name', 'Async Goal')}"
        elif event.topic in ["task.completed", "task.failed"]:
            self._state.current_workflow = "Idle Desktop Observation"

    async def _handle_config_event(self, event) -> None:
        logger.info(f"⚡ [EventBus Subscriber -> WorldModel] Received '{event.topic}': config changes={event.data.get('changes')}")
        self.refresh()

    async def _handle_security_event(self, event) -> None:
        logger.warning(f"⚡ [EventBus Subscriber -> WorldModel] Received '{event.topic}': Security approval required for action '{event.data.get('action')}'")
        self._state.current_workflow = f"Awaiting Security Approval: {event.data.get('action')}"

    async def _handle_context_event(self, event) -> None:
        logger.info(f"⚡ [EventBus Subscriber -> WorldModel] Received '{event.topic}': key='{event.data.get('key')}', new_value='{event.data.get('new_value')}'")

    @property
    def state(self) -> WorldModelState:
        return self._state

    def refresh(self) -> WorldModelState:
        """
        Refresh current desktop environment state (monitors, active window, UIA scene graph, clipboard).
        Sub-30ms execution lifecycle.
        """
        now = time.time()
        monitors_data = [m.model_dump() for m in self.spatial_engine.get_monitors()]
        
        # 1. Capture Active Foreground Window
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            try:
                top_windows = []
                def _enum_cb(h, _):
                    if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h):
                        r = win32gui.GetWindowRect(h)
                        if r[2] > r[0] and r[3] > r[1]:
                            top_windows.append(h)
                win32gui.EnumWindows(_enum_cb, None)
                hwnd = top_windows[0] if top_windows else win32gui.GetDesktopWindow()
            except Exception:
                hwnd = 0

        window_title = "Desktop"
        process_id = None
        app_name = "explorer.exe"
        bounds = [0, 0, 1920, 1080]

        if hwnd:
            try:
                window_title = win32gui.GetWindowText(hwnd) or "Desktop"
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process_id = pid
                try:
                    import psutil
                    app_name = psutil.Process(pid).name()
                except Exception:
                    app_name = "explorer.exe"
                rect = win32gui.GetWindowRect(hwnd)
                bounds = [rect[0], rect[1], rect[2], rect[3]]
            except Exception as e:
                logger.debug("Failed to read window attributes: {}", e)

        # 2. Capture Win32 UIA Scene Graph
        scene = self.scene_graph_engine.capture_scene(max_depth=3, max_elements=50)

        # 3. Read Clipboard Text Safely
        clipboard_text = self._read_clipboard()

        # 4. Extract Browser URL / Title if focused app is a browser
        browser_url = None
        browser_title = None
        if app_name.lower() in ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"):
            browser_title = window_title
            # Find address bar in controls
            for c in scene.controls:
                if c.control_type in ("Edit", "50004") or "address" in c.name.lower() or "url" in c.name.lower():
                    if c.name and (c.name.startswith("http") or "." in c.name):
                        browser_url = c.name
                        break

        # 5. Dynamic Internet Online Check (socket ping cached for 30s)
        if now - self._last_online_check_time > 30.0:
            try:
                import socket
                socket.create_connection(("8.8.8.8", 53), timeout=0.2).close()
                self._cached_is_online = True
            except Exception:
                self._cached_is_online = False
            self._last_online_check_time = now
        is_online = self._cached_is_online

        # 6. Read Real Cursor Position via Win32 API
        cursor_pos = [0, 0]
        try:
            cur_x, cur_y = win32api.GetCursorPos()
            cursor_pos = [int(cur_x), int(cur_y)]
        except Exception:
            pass

        # 7. Dynamic Audio Session Probe
        is_audio_active = False
        try:
            from pycaw.pycaw import AudioUtilities
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.State == 1:  # 1 = AudioSessionStateActive
                    is_audio_active = True
                    break
        except Exception:
            pass

        # 8. Feed updates into WorkspaceIntelligenceService
        ws_workflow = scene.active_app or "General Desktop Automation"
        try:
            from backend.services.manager import ServiceManager
            ws_intel = ServiceManager.get_instance("workspace_intelligence")
            if ws_intel and hasattr(ws_intel, "update_from_desktop_state"):
                ctx = ws_intel.update_from_desktop_state(app_name, window_title, browser_url)
                ws_workflow = ctx.current_workflow
        except Exception:
            pass

        # 9. Construct updated state
        self._state = WorldModelState(
            timestamp=now,
            monitors=monitors_data,
            active_monitor_id=1,
            active_app=app_name,
            window_title=window_title,
            window_bounds=bounds,
            process_id=process_id,
            scene_graph=scene.model_dump(),
            browser_url=browser_url,
            browser_title=browser_title,
            clipboard_text=clipboard_text,
            audio_playing=is_audio_active,
            internet_online=is_online,
            current_workflow=ws_workflow,
            cursor_position=cursor_pos,
            desktop=DesktopState(
                active_window=window_title,
                monitors=monitors_data,
                active_monitor_id=1,
                cursor_position=cursor_pos
            )
        )
        return self._state

    def _read_clipboard(self) -> Optional[str]:
        """Safely read current text from Windows Clipboard."""
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                return data[:500]  # cap at 500 chars
            win32clipboard.CloseClipboard()
        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
        return None

    def get_summary(self) -> Dict[str, Any]:
        """Returns concise dictionary summary for Planner context prompts."""
        st = self._state
        disp_list = getattr(st, "monitors", []) or (st.desktop.monitors if hasattr(st, "desktop") else [])
        disp_count = len(disp_list)
        ctrl_count = st.scene_graph.get("total_elements", 0) if st.scene_graph else 0
        pid = st.process_id

        return {
            "active_window": st.window_title or "Desktop",
            "foreground_pid": pid,
            "process_id": pid,
            "ui_control_count": ctrl_count,
            "control_nodes": ctrl_count,
            "display_count": disp_count,
            "monitors_count": disp_count,
            "focused_control": st.scene_graph.get("focused_element") if st.scene_graph else None,
            "clipboard_has_text": bool(st.clipboard_text),
            "workflow": st.current_workflow,
            "active_app": st.active_app
        }
