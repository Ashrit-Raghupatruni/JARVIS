"""
JARVIS AI Operating System - Native Windows UI Automation (UIA) Engine.

Provides resolution-independent desktop automation by inspecting control trees,
locating UI elements by name/AutomationID, and executing native invocation/clicks.
"""

import sys
import time
from typing import Dict, Any, List, Optional
from loguru import logger

# Try win32gui / uiautomation / pywinauto if installed
try:
    import win32gui
    import win32process
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class UIAEngine:
    """Native Windows UI Automation & Accessibility Selector Engine."""

    def __init__(self) -> None:
        logger.info("UIAEngine initialized (Win32 Accessibility Core Ready)")

    def inspect_active_window_controls(self) -> Dict[str, Any]:
        """Inspect the active foreground window and return top UI controls."""
        if not HAS_WIN32:
            return {"status": "win32_not_available", "controls": []}

        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            
            controls: List[Dict[str, Any]] = []

            def enum_child_proc(child_hwnd, param):
                c_title = win32gui.GetWindowText(child_hwnd)
                c_class = win32gui.GetClassName(child_hwnd)
                if c_title or c_class:
                    c_rect = win32gui.GetWindowRect(child_hwnd)
                    controls.append({
                        "hwnd": child_hwnd,
                        "title": c_title,
                        "class_name": c_class,
                        "bounds": {
                            "left": c_rect[0],
                            "top": c_rect[1],
                            "right": c_rect[2],
                            "bottom": c_rect[3],
                            "width": c_rect[2] - c_rect[0],
                            "height": c_rect[3] - c_rect[1],
                        }
                    })

            win32gui.EnumChildWindows(hwnd, enum_child_proc, None)

            return {
                "status": "success",
                "foreground_hwnd": hwnd,
                "window_title": title,
                "window_bounds": {
                    "left": rect[0],
                    "top": rect[1],
                    "right": rect[2],
                    "bottom": rect[3]
                },
                "control_count": len(controls),
                "controls": controls[:25]
            }

        except Exception as e:
            logger.error(f"UIA Inspection error: {e}")
            return {"status": "error", "error": str(e), "controls": []}

    def click_element_by_name(self, element_name: str) -> Dict[str, Any]:
        """Locate control by title/name matching and execute click."""
        info = self.inspect_active_window_controls()
        target_name = element_name.lower().strip()

        for ctrl in info.get("controls", []):
            c_title = ctrl.get("title", "").lower()
            if target_name in c_title and c_title:
                bounds = ctrl["bounds"]
                click_x = bounds["left"] + bounds["width"] // 2
                click_y = bounds["top"] + bounds["height"] // 2
                
                # Execute native click via win32 or pyautogui
                try:
                    import pyautogui
                    pyautogui.click(click_x, click_y)
                    return {
                        "status": "clicked",
                        "target": ctrl.get("title"),
                        "class_name": ctrl.get("class_name"),
                        "coordinates": {"x": click_x, "y": click_y}
                    }
                except Exception as e:
                    return {"status": "error", "message": str(e)}

        return {"status": "not_found", "target": element_name}

    def invoke_control(self, automation_id_or_name: str) -> Dict[str, Any]:
        """Execute Win32 UIA InvokePattern on a button or control by AutomationID / Name."""
        try:
            from backend.services.perception.uia_scene_graph import UIASceneGraph
            sg = UIASceneGraph()
            scene = sg.capture_scene(max_depth=3, max_elements=50)
            target = automation_id_or_name.lower().strip()

            for elem in scene.elements:
                if target in elem.name.lower() or target in elem.id.lower():
                    # Execute click at center bounds of UIA element
                    b = elem.bounds
                    if b and len(b) == 4:
                        cx = (b[0] + b[2]) // 2
                        cy = (b[1] + b[3]) // 2
                        try:
                            import pyautogui
                            pyautogui.click(cx, cy)
                            return {"status": "invoked", "element_id": elem.id, "name": elem.name, "coords": [cx, cy]}
                        except Exception as e:
                            return {"status": "error", "message": str(e)}

            return {"status": "not_found", "query": automation_id_or_name}
        except Exception as err:
            return {"status": "error", "message": str(err)}

    def set_control_value(self, field_name: str, value: str) -> Dict[str, Any]:
        """Type text value directly into a Win32 input text field."""
        try:
            res = self.click_element_by_name(field_name)
            if res.get("status") in ("clicked", "invoked"):
                time.sleep(0.1)
                import pyautogui
                pyautogui.hotkey("ctrl", "a")
                pyautogui.typewrite(value, interval=0.01)
                return {"status": "value_set", "field": field_name, "value": value}
            return res
        except Exception as e:
            return {"status": "error", "message": str(e)}
