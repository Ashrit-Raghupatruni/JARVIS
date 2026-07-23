"""
JARVIS AI OS Perception Engine Package.

Extracts structured Win32 UIA Scene Graphs, active window controls,
multi-monitor spatial layouts, and resolves visual anchors ("this", "that").
"""

from backend.services.perception.uia_scene_graph import UIASceneGraph, SceneElement
from backend.services.perception.spatial_engine import SpatialEngine, MonitorInfo

__all__ = ["UIASceneGraph", "SceneElement", "SpatialEngine", "MonitorInfo"]
