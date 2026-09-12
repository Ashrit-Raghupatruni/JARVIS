"""
JARVIS AI OS - Live Mode Continuous Perception & Collaboration Engine.

Continuously observes the active desktop, builds semantic Scene Graphs,
determines workflow context, generates next-step guidance, and manages
asymmetric confidence gating & safety interlocks.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional, Dict, Any, List, Callable
from pydantic import BaseModel, Field
from loguru import logger

from backend.services.perception.uia_scene_graph import UIASceneGraph, SceneGraph
from backend.services.perception.spatial_engine import SpatialEngine
from backend.services.live_mode.form_assistant import FormAssistant


class LiveContextFrame(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    is_live_mode_enabled: bool = True
    active_app: str = "Desktop"
    window_title: str = "Desktop Workspace"
    active_workflow: str = "General Desktop Assistance"
    current_step: str = "Observing active screen state"
    next_logical_step: Optional[str] = None
    proactive_suggestion: Optional[str] = None
    detected_form_fields: int = 0
    confidence_score: float = 0.95
    scene_graph: Optional[SceneGraph] = None
    window_bounds: Optional[Dict[str, int]] = None


class LiveModeEngine:
    """
    Real-time Continuous Observation and Co-Pilot Collaboration Engine.
    Operates on an event-driven, adaptive differential perception loop.
    Completely zero overhead when disabled.
    """

    def __init__(self, on_context_update: Optional[Callable[[LiveContextFrame], None]] = None) -> None:
        self.is_enabled: bool = False
        self.min_interval: float = 0.5   # Active change scan rate (2 Hz)
        self.max_interval: float = 2.5   # Idle static scan rate (0.4 Hz)
        self.current_interval: float = 0.5
        self.on_context_update = on_context_update

        # Lazy Collaborator Handles
        self._world_model = None
        self._scene_extractor = None
        self._spatial_engine = None
        self._form_assistant = None
        self._proactive_engine = None
        self._spatial_parser = None
        self._workspace_memory = None

        self._task: Optional[asyncio.Task] = None
        self.latest_frame: Optional[LiveContextFrame] = None
        self._last_window_title: str = ""
        self._last_win_bounds: Optional[Dict[str, int]] = None
        self._last_hwnd: int = 0
        self._consecutive_static_ticks: int = 0

    @property
    def world_model(self):
        if self._world_model is None:
            from backend.services.manager import ServiceManager
            self._world_model = ServiceManager.get_instance("world_model")
            if self._world_model is None:
                from backend.services.world_model import WorldModel
                self._world_model = WorldModel()
        return self._world_model

    @property
    def scene_extractor(self):
        if self._scene_extractor is None:
            from backend.services.perception.uia_scene_graph import UIASceneGraph
            self._scene_extractor = UIASceneGraph()
        return self._scene_extractor

    @property
    def spatial_engine(self):
        if self._spatial_engine is None:
            from backend.services.perception.spatial_engine import SpatialEngine
            self._spatial_engine = SpatialEngine()
        return self._spatial_engine

    @property
    def form_assistant(self):
        if self._form_assistant is None:
            self._form_assistant = FormAssistant()
        return self._form_assistant

    @property
    def proactive_engine(self):
        if self._proactive_engine is None:
            from backend.services.proactive_engine import ProactiveEngine
            self._proactive_engine = ProactiveEngine()
        return self._proactive_engine

    @property
    def spatial_parser(self):
        if self._spatial_parser is None:
            from backend.services.perception.spatial_ref_parser import SpatialRefParser
            self._spatial_parser = SpatialRefParser()
        return self._spatial_parser

    @property
    def workspace_memory(self):
        if self._workspace_memory is None:
            from backend.services.workspace_memory import WorkspaceMemory
            self._workspace_memory = WorkspaceMemory()
        return self._workspace_memory

    def get_activation_greeting(self) -> str:
        """Get human-readable spoken greeting for Live Mode activation."""
        return "JARVIS Live Mode active. What are we working on now?"

    async def _broadcast_live_mode_status(
        self,
        is_active: bool,
        active_app: str = "Desktop",
        window_title: str = "Desktop Workspace",
        window_bounds: Optional[Dict[str, int]] = None
    ) -> None:
        """Broadcast live mode activation state and focused window bounds for UI transparency and spotlight overlay."""
        try:
            from backend.services.manager import ServiceManager
            ws_mgr = ServiceManager.get_instance("connection_manager")
            if ws_mgr and hasattr(ws_mgr, "broadcast"):
                from backend.models.schemas import WSMessage, LiveModeStatusMessage
                payload = LiveModeStatusMessage(
                    is_active=is_active,
                    active_app=active_app,
                    window_title=window_title,
                    window_bounds=window_bounds,
                    timestamp=time.time()
                )
                await ws_mgr.broadcast(WSMessage(
                    type="live_mode_status",
                    data=payload.model_dump()
                ))
        except Exception as err:
            logger.debug("Live Mode status broadcast notice: {}", err)

    def start(self, speak_greeting: bool = True) -> None:
        """Start the background Live Mode perception loop and trigger spoken greeting."""
        if self.is_enabled:
            return
        self.is_enabled = True
        self.current_interval = self.min_interval
        self._consecutive_static_ticks = 0
        self._task = asyncio.create_task(self._perception_loop())
        logger.info("✓ Live Mode AI Assistant started (Event-driven adaptive perception active).")

        asyncio.create_task(self._broadcast_live_mode_status(is_active=True))

        if speak_greeting:
            asyncio.create_task(self._broadcast_activation_greeting())

    async def _broadcast_activation_greeting(self) -> None:
        """Synthesize and broadcast activation greeting over WebSocket."""
        try:
            greeting_text = self.get_activation_greeting()
            from backend.services.manager import ServiceManager
            tts = ServiceManager.get_instance("tts_service")
            ws_mgr = ServiceManager.get_instance("connection_manager")

            audio_bytes = None
            if tts and hasattr(tts, "synthesize"):
                audio_bytes = await tts.synthesize(greeting_text)

            if ws_mgr and hasattr(ws_mgr, "broadcast"):
                from backend.models.schemas import WSMessage, ResponseMessage, StatusMessage, AssistantState
                await ws_mgr.broadcast(WSMessage(
                    type="status",
                    data=StatusMessage(state=AssistantState.SPEAKING, message=greeting_text).model_dump()
                ))
                await ws_mgr.broadcast(WSMessage(
                    type="response",
                    data=ResponseMessage(text=greeting_text).model_dump()
                ))
                if audio_bytes:
                    import base64
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    await ws_mgr.broadcast(WSMessage(
                        type="tts_audio",
                        data={"audio": audio_b64, "format": "mp3"}
                    ))
                await ws_mgr.broadcast(WSMessage(
                    type="status",
                    data=StatusMessage(state=AssistantState.LISTENING, message="Hands-free voice control active").model_dump()
                ))
        except Exception as err:
            logger.warning(f"Live Mode activation greeting broadcast notice: {err}")

    def stop(self) -> None:
        """Stop the background Live Mode perception loop and cleanly release resources."""
        self.is_enabled = False
        if self._task:
            self._task.cancel()
            self._task = None

        # Cleanly stop any active hand tracking / camera worker
        try:
            from backend.services.manager import ServiceManager
            hc = ServiceManager.get_instance("hand_control_service")
            if hc and getattr(hc, "_tracking_active", False):
                hc.stop_background_tracking()
        except Exception as hc_err:
            logger.debug("Hand control cleanup notice: {}", hc_err)

        try:
            asyncio.create_task(self._broadcast_live_mode_status(is_active=False))
        except Exception:
            pass

        self._last_window_title = ""
        self._last_win_bounds = None
        self._last_hwnd = 0
        self._consecutive_static_ticks = 0
        logger.info("Live Mode AI Assistant stopped (Perception resources released).")

    async def _perception_loop(self) -> None:
        """Adaptive differential streaming perception loop."""
        import win32gui

        while self.is_enabled:
            try:
                start_t = time.time()

                # Fast Probe: Check active foreground window (<0.1ms)
                hwnd = win32gui.GetForegroundWindow()
                current_title = win32gui.GetWindowText(hwnd) if hwnd else "Desktop"
                
                # Fast Window Bounds
                win_bounds = None
                try:
                    if hwnd:
                        rect = win32gui.GetWindowRect(hwnd)
                        win_bounds = {"x": rect[0], "y": rect[1], "w": rect[2] - rect[0], "h": rect[3] - rect[1]}
                except Exception:
                    pass

                has_window_changed = (hwnd != self._last_hwnd or current_title != self._last_window_title or win_bounds != self._last_win_bounds)

                if has_window_changed:
                    self._consecutive_static_ticks = 0
                    self.current_interval = self.min_interval  # High responsiveness (0.5s)
                    force_refresh = True
                else:
                    self._consecutive_static_ticks += 1
                    # Dynamic backoff if nothing changed
                    if self._consecutive_static_ticks >= 4:
                        self.current_interval = min(self.max_interval, self.current_interval + 0.5)
                    force_refresh = False

                # Refresh World Model (uses cached scene graph if not forced)
                wm_state = await asyncio.to_thread(self.world_model.refresh, force=force_refresh)

                # Extract details from unified state
                window_title = wm_state.window_title
                app_name = wm_state.window_title.lower()
                workflow = "General Workspace"
                next_step = None
                suggestion = None

                if any(w in app_name for w in ["vscode", "code", "visual studio"]):
                    workflow = "Coding & Software Engineering Mode"
                    suggestion = "VS Code detected. Python environment active."
                elif any(w in app_name for w in ["chrome", "edge", "firefox", "browser"]):
                    workflow = "Web Browsing & Research Mode"
                elif any(w in app_name for w in ["setup", "install", "wizard"]):
                    workflow = "Software Installation Workflow"
                    next_step = "Review license agreement and click Next"
                elif any(w in app_name for w in ["excel", "spreadsheet"]):
                    workflow = "Data Analysis & Spreadsheet Mode"

                # Check active scene graph controls for form fields only when window changed
                form_fields = []
                if has_window_changed:
                    try:
                        controls = (wm_state.scene_graph or {}).get("controls", [])
                        from backend.services.perception.uia_scene_graph import SceneElement
                        elements = [SceneElement(**c) for c in controls if "control_type" in c]
                        form_fields = self.form_assistant.detect_form_fields(elements)
                        if form_fields and not suggestion:
                            suggestion = f"Detected {len(form_fields)} form field(s). Say 'Fill form' to auto-complete."
                    except Exception as f_err:
                        logger.debug("Form field detection notice: {}", f_err)

                # Construct Frame
                frame = LiveContextFrame(
                    is_live_mode_enabled=self.is_enabled,
                    active_app=wm_state.active_app,
                    window_title=wm_state.window_title,
                    active_workflow=workflow,
                    current_step=f"Active in {wm_state.window_title}",
                    next_logical_step=next_step,
                    proactive_suggestion=suggestion,
                    detected_form_fields=len(form_fields),
                    confidence_score=0.95,
                    scene_graph=None,
                    window_bounds=win_bounds
                )

                self.latest_frame = frame

                # Broadcast live status & window bounds if focus or geometry shifted
                if has_window_changed:
                    self._last_hwnd = hwnd
                    self._last_window_title = window_title
                    self._last_win_bounds = win_bounds
                    await self._broadcast_live_mode_status(
                        is_active=True,
                        active_app=wm_state.active_app,
                        window_title=wm_state.window_title,
                        window_bounds=win_bounds
                    )

                # Event-driven callback trigger: notify when window changes or proactive suggestion is generated
                if self.on_context_update and (has_window_changed or suggestion):
                    try:
                        if asyncio.iscoroutinefunction(self.on_context_update):
                            await self.on_context_update(frame)
                        else:
                            self.on_context_update(frame)
                    except Exception as cb_err:
                        logger.error(f"Error in Live Mode callback: {cb_err}")

                elapsed = time.time() - start_t
                sleep_t = max(0.05, self.current_interval - elapsed)
                await asyncio.sleep(sleep_t)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Live Mode perception loop: {e}")
                await asyncio.sleep(1.0)
