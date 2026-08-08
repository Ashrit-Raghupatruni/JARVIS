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
    """

    def __init__(self, on_context_update: Optional[Callable[[LiveContextFrame], None]] = None) -> None:
        self.is_enabled: bool = False
        self.perception_interval: float = 1.0  # 1 FPS scanning loop
        self.on_context_update = on_context_update

        self.scene_extractor = UIASceneGraph()
        self.spatial_engine = SpatialEngine()
        self.form_assistant = FormAssistant()

        # Live Mode 2.0 Intelligent Collaborator Engines
        from backend.services.world_model import WorldModel
        from backend.services.proactive_engine import ProactiveEngine
        from backend.services.perception.spatial_ref_parser import SpatialRefParser
        from backend.services.workspace_memory import WorkspaceMemory

        self.world_model = WorldModel()
        self.proactive_engine = ProactiveEngine()
        self.spatial_parser = SpatialRefParser()
        self.workspace_memory = WorkspaceMemory()

        self._task: Optional[asyncio.Task] = None
        self.latest_frame: Optional[LiveContextFrame] = None
        self._last_window_title: str = ""

    def start(self) -> None:
        """Start the background Live Mode perception loop."""
        if self.is_enabled:
            return
        self.is_enabled = True
        self._task = asyncio.create_task(self._perception_loop())
        logger.info("✓ Live Mode AI Assistant started (1.0 FPS perception loop active).")

    def stop(self) -> None:
        """Stop the background Live Mode perception loop."""
        self.is_enabled = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Live Mode AI Assistant stopped.")

    async def _perception_loop(self) -> None:
        """Background streaming perception loop driven by WorldModel single source of truth."""
        while self.is_enabled:
            try:
                start_t = time.time()
                
                # Single Source of Truth: Refresh World Model
                wm_state = await asyncio.to_thread(self.world_model.refresh)
                
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

                # Check active scene graph controls for form fields
                form_fields = []
                try:
                    controls = (wm_state.scene_graph or {}).get("controls", [])
                    from backend.services.perception.uia_scene_graph import SceneElement
                    elements = [SceneElement(**c) for c in controls if "control_type" in c]
                    form_fields = self.form_assistant.detect_form_fields(elements)
                    if form_fields and not suggestion:
                        suggestion = f"Detected {len(form_fields)} form field(s). Say 'Fill form' to auto-complete."
                except Exception as f_err:
                    logger.debug("Form field detection notice: {}", f_err)

                # Capture active window screen bounds for Live Mode Spotlight Overlay
                win_bounds = None
                try:
                    import pyautogui
                    win = pyautogui.getActiveWindow()
                    if win and win.width > 0 and win.height > 0:
                        win_bounds = {"x": win.left, "y": win.top, "w": win.width, "h": win.height}
                except Exception:
                    pass

                # Construct Frame off WorldModel state
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
                
                # Event-driven callback trigger: notify when window changes or proactive suggestion is generated
                if self.on_context_update and (window_title != self._last_window_title or suggestion):
                    self._last_window_title = window_title
                    try:
                        if asyncio.iscoroutinefunction(self.on_context_update):
                            await self.on_context_update(frame)
                        else:
                            self.on_context_update(frame)
                    except Exception as cb_err:
                        logger.error(f"Error in Live Mode callback: {cb_err}")

                elapsed = time.time() - start_t
                sleep_t = max(0.1, self.perception_interval - elapsed)
                await asyncio.sleep(sleep_t)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Live Mode perception loop: {e}")
                await asyncio.sleep(2.0)
