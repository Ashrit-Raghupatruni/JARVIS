"""
JARVIS AI OS - Multi-Monitor Spatial Coordinate & Layout Engine.

Detects connected displays, resolutions, DPI scaling, primary status,
and resolves spatial references ("this box", "that button", "Monitor 2").
"""

from __future__ import annotations

import ctypes
import math
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from loguru import logger

try:
    import win32api
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class MonitorInfo(BaseModel):
    index: int
    name: str
    bounds: List[int] = Field(description="[left, top, right, bottom]")
    width: int
    height: int
    is_primary: bool = False
    is_vertical: bool = False


class SpatialEngine:
    """
    Multi-Monitor Display Topology and Spatial Coordinate Anchor Engine.
    """

    def __init__(self) -> None:
        self._monitors: List[MonitorInfo] = []
        self.refresh_displays()

    def refresh_displays(self) -> List[MonitorInfo]:
        """Enumerate all active displays connected to the Windows OS."""
        monitors = []
        try:
            if HAS_WIN32:
                mon_handles = win32api.EnumDisplayMonitors()
                primary_mon = win32api.GetSystemMetrics(win32con.SM_CXSCREEN), win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                
                for idx, (h_mon, h_dc, rect) in enumerate(mon_handles, start=1):
                    info = win32api.GetMonitorInfo(h_mon)
                    r = info["Monitor"]
                    width = r[2] - r[0]
                    height = r[3] - r[1]
                    is_primary = info.get("Flags", 0) == win32con.MONITORINFOF_PRIMARY
                    is_vertical = height > width

                    m_info = MonitorInfo(
                        index=idx,
                        name=f"Monitor {idx}" + (" (Primary)" if is_primary else ""),
                        bounds=[r[0], r[1], r[2], r[3]],
                        width=width,
                        height=height,
                        is_primary=is_primary,
                        is_vertical=is_vertical
                    )
                    monitors.append(m_info)
            else:
                # Fallback display config
                monitors.append(MonitorInfo(
                    index=1,
                    name="Monitor 1 (Primary)",
                    bounds=[0, 0, 1920, 1080],
                    width=1920,
                    height=1080,
                    is_primary=True
                ))
        except Exception as e:
            logger.warning(f"Display enumeration notice: {e}")
            if not monitors:
                monitors.append(MonitorInfo(index=1, name="Monitor 1", bounds=[0, 0, 1920, 1080], width=1920, height=1080, is_primary=True))

        self._monitors = monitors
        logger.debug(f"Discovered {len(monitors)} monitor(s).")
        return self._monitors

    def get_monitors(self) -> List[MonitorInfo]:
        if not self._monitors:
            self.refresh_displays()
        return self._monitors

    def get_cursor_position(self) -> Tuple[int, int]:
        """Get current Windows mouse cursor screen coordinates."""
        try:
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            return (pt.x, pt.y)
        except Exception:
            return (0, 0)

    def resolve_spatial_anchor(self, spatial_ref: str, scene_elements: List[Any]) -> Optional[Any]:
        """
        Resolve natural language anchors ("this box", "the button near mouse", "the first textbox").
        """
        if not scene_elements:
            return None

        ref_lower = spatial_ref.lower().strip()
        cursor_x, cursor_y = self.get_cursor_position()

        # 1. "this", "this box", "this field", "here" -> closest element to cursor
        if any(w in ref_lower for w in ["this", "here", "cursor", "pointer"]):
            best_elem = None
            min_dist = float("inf")
            for elem in scene_elements:
                bounds = getattr(elem, "bounds", None) or (elem.get("bounds") if isinstance(elem, dict) else None)
                if bounds and len(bounds) == 4:
                    cx = (bounds[0] + bounds[2]) / 2
                    cy = (bounds[1] + bounds[3]) / 2
                    dist = math.hypot(cx - cursor_x, cy - cursor_y)
                    if dist < min_dist:
                        min_dist = dist
                        best_elem = elem
            if best_elem:
                return best_elem

        # 2. Ordinal references ("first button", "second textbox")
        is_second = "second" in ref_lower or "2nd" in ref_lower
        is_third = "third" in ref_lower or "3rd" in ref_lower
        idx = 1 if is_second else (2 if is_third else 0)

        matching = []
        for elem in scene_elements:
            c_type = (getattr(elem, "control_type", "") or "").lower()
            name = (getattr(elem, "name", "") or "").lower()
            
            if "button" in ref_lower and ("button" in c_type or "button" in name):
                matching.append(elem)
            elif any(w in ref_lower for w in ["textbox", "field", "box", "input"]) and ("edit" in c_type or "combobox" in c_type):
                matching.append(elem)

        if matching and idx < len(matching):
            return matching[idx]

        return scene_elements[0] if scene_elements else None
