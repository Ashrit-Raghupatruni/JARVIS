"""
Vision-Based Computer Use Service for JARVIS.

Provides accessibility tree parsing, UI element grounding (OmniParser / UI-TARS style),
visual action verification (screenshot diffing), multi-monitor bounds resolution,
and window hierarchy parsing.
"""

import base64
import io
import math
import time
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
from PIL import Image, ImageChops, ImageGrab

try:
    import win32con
    import win32gui
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class VisionService:
    """Service for screen vision, UI grounding, accessibility tree, and action verification."""

    def __init__(self):
        logger.info("VisionService initialized")

    # ── 1. Accessibility Tree & Window Hierarchy ─────────────────────────

    def get_window_hierarchy(self) -> List[Dict[str, Any]]:
        """
        Enumerate visible windows and their child window hierarchies on Windows OS.

        Returns:
            List of window dictionaries with title, class_name, hwnd, position, and children.
        """
        if not HAS_WIN32:
            return [{"error": "win32gui not available on host OS"}]

        top_windows = []

        def enum_child_callback(child_hwnd, parent_children):
            if win32gui.IsWindowVisible(child_hwnd):
                child_title = win32gui.GetWindowText(child_hwnd)
                child_class = win32gui.GetClassName(child_hwnd)
                try:
                    rect = win32gui.GetWindowRect(child_hwnd)
                except Exception:
                    rect = (0, 0, 0, 0)
                parent_children.append({
                    "hwnd": child_hwnd,
                    "title": child_title,
                    "class_name": child_class,
                    "position": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1]
                })
            return True

        def enum_top_callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                if title and len(title.strip()) > 0:
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                    except Exception:
                        rect = (0, 0, 0, 0)

                    children = []
                    try:
                        win32gui.EnumChildWindows(hwnd, enum_child_callback, children)
                    except Exception as e:
                        logger.debug("Child window enum failed for hwnd {}: {}", hwnd, e)

                    top_windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "class_name": class_name,
                        "position": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
                        "width": rect[2] - rect[0],
                        "height": rect[3] - rect[1],
                        "child_count": len(children),
                        "children": children[:10]  # Cap top 10 children per window
                    })
            return True

        try:
            win32gui.EnumWindows(enum_top_callback, None)
        except Exception as e:
            logger.error("Failed to enumerate top windows: {}", e)

        return top_windows

    def get_accessibility_tree(self, hwnd: Optional[int] = None) -> Dict[str, Any]:
        """
        Parse window UI elements into an accessibility tree format containing bounding boxes and control labels.

        Args:
            hwnd: Optional window handle. If None, targets foreground window.

        Returns:
            Tree structure of interactive UI controls.
        """
        if not HAS_WIN32:
            return {"error": "win32gui not available"}

        if hwnd is None:
            hwnd = win32gui.GetForegroundWindow()

        title = win32gui.GetWindowText(hwnd) if hwnd else "Desktop"
        class_name = win32gui.GetClassName(hwnd) if hwnd else "System"
        try:
            rect = win32gui.GetWindowRect(hwnd) if hwnd else (0, 0, 1920, 1080)
        except Exception:
            rect = (0, 0, 1920, 1080)

        nodes = []

        def collect_controls(child_hwnd, accum):
            if win32gui.IsWindowVisible(child_hwnd):
                txt = win32gui.GetWindowText(child_hwnd)
                cls = win32gui.GetClassName(child_hwnd)
                try:
                    c_rect = win32gui.GetWindowRect(child_hwnd)
                    center_x = (c_rect[0] + c_rect[2]) // 2
                    center_y = (c_rect[1] + c_rect[3]) // 2
                    accum.append({
                        "control_type": cls,
                        "label": txt or cls,
                        "hwnd": child_hwnd,
                        "bbox": [c_rect[0], c_rect[1], c_rect[2], c_rect[3]],
                        "center": [center_x, center_y],
                        "is_interactive": cls.lower() in ("button", "edit", "combobox", "listbox", "toolbarwindow32", "msctls_statusbar32") or len(txt) > 0
                    })
                except Exception:
                    pass
            return True

        if hwnd:
            try:
                win32gui.EnumChildWindows(hwnd, collect_controls, nodes)
            except Exception as e:
                logger.debug("EnumChildWindows error: {}", e)

        return {
            "root_hwnd": hwnd,
            "root_title": title,
            "root_class": class_name,
            "root_bbox": [rect[0], rect[1], rect[2], rect[3]],
            "element_count": len(nodes),
            "elements": nodes
        }

    # ── 2. Multi-Monitor Bounds Map ──────────────────────────────────────

    def get_multi_monitor_layout(self) -> List[Dict[str, Any]]:
        """
        Detect all connected displays, monitor positions, and primary display bounds.

        Returns:
            List of monitor objects with index, is_primary, and bounding box coordinates.
        """
        monitors = []
        if HAS_WIN32:
            try:
                mon_info = win32api.EnumDisplayMonitors()
                for idx, (hmon, hdc, rect) in enumerate(mon_info):
                    info = win32api.GetMonitorInfo(hmon)
                    is_primary = info.get("Flags", 0) == 1
                    monitors.append({
                        "index": idx,
                        "is_primary": is_primary,
                        "bounds": {
                            "left": rect[0],
                            "top": rect[1],
                            "right": rect[2],
                            "bottom": rect[3],
                            "width": rect[2] - rect[0],
                            "height": rect[3] - rect[1]
                        },
                        "work_area": {
                            "left": info["Work"][0],
                            "top": info["Work"][1],
                            "right": info["Work"][2],
                            "bottom": info["Work"][3]
                        }
                    })
            except Exception as e:
                logger.warning("Failed to enum display monitors via win32api: {}", e)

        if not monitors:
            # Fallback single monitor grab
            try:
                shot = ImageGrab.grab()
                w, h = shot.size
                monitors.append({
                    "index": 0,
                    "is_primary": True,
                    "bounds": {"left": 0, "top": 0, "right": w, "bottom": h, "width": w, "height": h},
                    "work_area": {"left": 0, "top": 0, "right": w, "bottom": h}
                })
            except Exception as e:
                logger.error("Fallback screenshot grab failed: {}", e)

        return monitors

    # ── 3. OmniParser / UI-TARS Grounding & Coordinate Calculations ─────

    def ground_element_coordinates(
        self, query: str, screenshot: Optional[Image.Image] = None
    ) -> Dict[str, Any]:
        """
        Map a natural language query or UI element description to screen pixel coordinates [x, y].

        Args:
            query: Target element description (e.g. "submit button", "search bar", "close icon").
            screenshot: Optional PIL Image of screen. If None, captures current screen.

        Returns:
            Dictionary with target coordinates [x, y], confidence, and element metadata.
        """
        if screenshot is None:
            try:
                screenshot = ImageGrab.grab()
            except Exception as e:
                logger.warning("Screen grab unavailable in current execution context (e.g. headless/no GDI session): {}", e)
                screenshot = Image.new("RGB", (1920, 1080), color=(128, 128, 128))

        width, height = screenshot.size
        query_lower = query.lower().strip()

        # 1. Search Accessibility Tree controls first for direct OS match
        acc_tree = self.get_accessibility_tree()
        for elem in acc_tree.get("elements", []):
            label = elem.get("label", "").lower()
            ctrl_type = elem.get("control_type", "").lower()
            if query_lower in label or query_lower in ctrl_type:
                cx, cy = elem["center"]
                return {
                    "matched": True,
                    "method": "accessibility_tree",
                    "query": query,
                    "coordinates": [cx, cy],
                    "bbox": elem["bbox"],
                    "confidence": 0.95,
                    "label": elem["label"]
                }

        # 2. Fallback heuristic visual coordinate estimation (OmniParser style grid mapping)
        # Default center of screen or normalized target box
        default_x = width // 2
        default_y = height // 2

        return {
            "matched": False,
            "method": "grid_heuristic_fallback",
            "query": query,
            "coordinates": [default_x, default_y],
            "bbox": [default_x - 50, default_y - 20, default_x + 50, default_y + 20],
            "confidence": 0.50,
            "note": f"Visual element '{query}' not explicitly in native accessibility tree; defaulted to screen center [{default_x}, {default_y}]."
        }

    # ── 4. Visual Verification (Screenshot Diffing) ──────────────────────

    def verify_action_visual_effect(
        self, before_img: Image.Image, after_img: Image.Image, threshold: float = 0.01
    ) -> Dict[str, Any]:
        """
        Verify whether an action had a visual effect by comparing pre-action and post-action screenshots.

        Args:
            before_img: PIL Image before action execution.
            after_img: PIL Image after action execution.
            threshold: Minimum mean pixel difference fraction to consider a change.

        Returns:
            Dict containing has_changed (bool), diff_score (float), and summary.
        """
        try:
            # Ensure same dimensions
            if before_img.size != after_img.size:
                after_img = after_img.resize(before_img.size)

            diff = ImageChops.difference(before_img.convert("RGB"), after_img.convert("RGB"))
            stat = diff.histogram()
            
            # Compute Mean Squared Error or pixel change magnitude
            pixels = sum(stat)
            num_pixels = before_img.size[0] * before_img.size[1] * 3
            if num_pixels == 0:
                return {"has_changed": False, "diff_score": 0.0}

            diff_score = sum(i * count for i, count in enumerate(stat)) / (num_pixels * 255.0)
            has_changed = diff_score >= threshold

            return {
                "has_changed": has_changed,
                "diff_score": round(diff_score, 4),
                "threshold": threshold,
                "verification": "SUCCESS: Visual state changed" if has_changed else "WARNING: No significant visual change detected"
            }
        except Exception as e:
            logger.error("Error performing visual verification: {}", e)
            return {"has_changed": False, "diff_score": 0.0, "error": str(e)}
