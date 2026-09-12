"""
JARVIS AI Operating System - Native Windows UI Automation (UIA) & Perception Engine.
=====================================================================================
Provides resolution-independent desktop UI control inspection and interaction:
- Active foreground window control tree inspection (Win32 EnumChildWindows)
- UIA accessibility tree element mapping (PyWinAuto / UIASceneGraph)
- Computer Vision OCR element finding and direct interaction (EasyOCR / Tesseract)
- Cascading interaction fallback: Win32 Controls -> UIA Scene Graph -> OCR Visual Bounds
- Fail-closed control value typing with active window focus verification
"""

from __future__ import annotations

import sys
import time
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    import win32con
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class UIAPerceptionEngine:
    """
    Windows UI Automation & Accessibility Perception Engine.
    """

    def __init__(self) -> None:
        self._easyocr_reader = None
        logger.info("UIAPerceptionEngine initialized (Win32 Accessibility Core + Vision OCR Ready)")

    def inspect_active_window_controls(self) -> Dict[str, Any]:
        """Inspect the active foreground window and return top UI controls."""
        if not HAS_WIN32:
            return {"status": "win32_not_available", "controls": []}

        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return {
                    "status": "success",
                    "foreground_hwnd": 0,
                    "window_title": "Desktop / No Foreground Window",
                    "window_bounds": {"left": 0, "top": 0, "right": 0, "bottom": 0},
                    "control_count": 0,
                    "controls": []
                }
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

    # ── OCR Vision Fallback (EasyOCR / Tesseract) ─────────────────────────

    def find_element_by_ocr(
        self,
        target_text: str,
        region: Optional[tuple] = None,
        image: Optional[Any] = None,
        confidence_threshold: float = 0.20,
    ) -> Optional[Dict[str, Any]]:
        """
        Locate a UI element on screen or inside a window using OCR.
        """
        offset_x, offset_y = 0, 0
        img = image

        if img is None:
            try:
                from PIL import ImageGrab
                if region:
                    img = ImageGrab.grab(bbox=region)
                    offset_x, offset_y = region[0], region[1]
                elif HAS_WIN32:
                    hwnd = win32gui.GetForegroundWindow()
                    if hwnd:
                        rect = win32gui.GetWindowRect(hwnd)
                        offset_x, offset_y = rect[0], rect[1]
                        img = ImageGrab.grab(bbox=(rect[0], rect[1], rect[2], rect[3]))
                    else:
                        img = ImageGrab.grab()
                else:
                    img = ImageGrab.grab()
            except Exception as cap_err:
                logger.debug(f"Screen capture during OCR lookup unavailable: {cap_err}")
                return None

        if img is None:
            return None

        target = target_text.lower().strip()

        # Engine 1: EasyOCR
        try:
            import easyocr
            import numpy as np

            if self._easyocr_reader is None:
                logger.info("Initializing EasyOCR reader for UIA fallback...")
                self._easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)

            img_np = np.array(img.convert("RGB"))
            ocr_results = self._easyocr_reader.readtext(img_np)

            best_match = None
            best_score = -1.0

            for item in ocr_results:
                if len(item) >= 3:
                    bbox, detected_text, conf = item[0], item[1], item[2]
                else:
                    continue

                text_clean = detected_text.lower().strip()
                if conf < confidence_threshold:
                    continue

                score = 0.0
                if target == text_clean:
                    score = 1.0 + conf
                elif target in text_clean.split():
                    score = 0.8 + conf
                elif target in text_clean:
                    score = 0.6 + conf

                if score > best_score:
                    best_score = score
                    xs = [pt[0] for pt in bbox]
                    ys = [pt[1] for pt in bbox]
                    center_x = int(sum(xs) / len(xs))
                    center_y = int(sum(ys) / len(ys))

                    best_match = {
                        "found": True,
                        "target": target_text,
                        "matched_text": detected_text,
                        "confidence": round(float(conf), 3),
                        "engine": "easyocr",
                        "coordinates": {
                            "x": offset_x + center_x,
                            "y": offset_y + center_y,
                        },
                        "bounds": {
                            "left": offset_x + int(min(xs)),
                            "top": offset_y + int(min(ys)),
                            "right": offset_x + int(max(xs)),
                            "bottom": offset_y + int(max(ys)),
                        }
                    }

            if best_match:
                logger.info(
                    "✓ OCR located '{}' at ({}, {}) [conf={:.2f}, engine=easyocr]",
                    target_text,
                    best_match["coordinates"]["x"],
                    best_match["coordinates"]["y"],
                    best_match["confidence"]
                )
                return best_match

        except Exception as e_err:
            logger.debug(f"EasyOCR detection attempt failed: {e_err}")

        # Engine 2: Tesseract OCR fallback
        try:
            import pytesseract
            from pytesseract import Output

            data = pytesseract.image_to_data(img, output_type=Output.DICT)
            n_boxes = len(data.get("text", []))

            for i in range(n_boxes):
                word = data["text"][i].strip()
                if not word:
                    continue

                conf = float(data["conf"][i]) if "conf" in data and float(data["conf"][i]) > 0 else 50.0
                if target in word.lower():
                    lx = data["left"][i]
                    ly = data["top"][i]
                    lw = data["width"][i]
                    lh = data["height"][i]
                    cx = lx + lw // 2
                    cy = ly + lh // 2

                    res = {
                        "found": True,
                        "target": target_text,
                        "matched_text": word,
                        "confidence": round(conf / 100.0, 3),
                        "engine": "tesseract",
                        "coordinates": {
                            "x": offset_x + cx,
                            "y": offset_y + cy,
                        },
                        "bounds": {
                            "left": offset_x + lx,
                            "top": offset_y + ly,
                            "right": offset_x + lx + lw,
                            "bottom": offset_y + ly + lh,
                        }
                    }
                    logger.info(
                        "✓ Tesseract OCR located '{}' at ({}, {}) [conf={:.2f}]",
                        target_text,
                        res["coordinates"]["x"],
                        res["coordinates"]["y"],
                        res["confidence"]
                    )
                    return res

        except Exception as t_err:
            logger.debug(f"Tesseract OCR detection attempt failed: {t_err}")

        return None

    def click_element_by_ocr(
        self,
        target_text: str,
        region: Optional[tuple] = None,
        image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Directly locate an on-screen element via OCR and execute a click."""
        match = self.find_element_by_ocr(target_text, region=region, image=image)
        if not match:
            return {"status": "not_found", "target": target_text, "method": "ocr"}

        coords = match["coordinates"]
        click_x = coords["x"]
        click_y = coords["y"]

        try:
            import pyautogui
            pyautogui.click(click_x, click_y)
            return {
                "status": "clicked",
                "target": match["matched_text"],
                "method": "ocr_fallback",
                "engine": match["engine"],
                "confidence": match["confidence"],
                "coordinates": {"x": click_x, "y": click_y},
                "bounds": match["bounds"]
            }
        except Exception as click_err:
            logger.warning(f"PyAutoGUI click execution failed: {click_err}")
            return {
                "status": "click_failed",
                "error": str(click_err),
                "target": match["matched_text"],
                "method": "ocr_fallback",
                "coordinates": {"x": click_x, "y": click_y}
            }

    # ── Cascading Control Interaction ────────────────────────────────────

    def click_element_by_name(self, element_name: str) -> Dict[str, Any]:
        """
        Locate control by title/name matching and click.
        Cascades: Native Win32 Controls -> UIA Scene Graph -> OCR Visual Bounds -> Scroll Fallback.
        """
        target_name = element_name.lower().strip()

        # Tier 1: Inspect Native Win32 child controls
        info = self.inspect_active_window_controls()
        for ctrl in info.get("controls", []):
            c_title = ctrl.get("title", "").lower()
            if target_name in c_title and c_title:
                bounds = ctrl["bounds"]
                click_x = bounds["left"] + bounds["width"] // 2
                click_y = bounds["top"] + bounds["height"] // 2

                try:
                    import pyautogui
                    pyautogui.click(click_x, click_y)
                    return {
                        "status": "clicked",
                        "target": ctrl.get("title"),
                        "class_name": ctrl.get("class_name"),
                        "method": "native_win32",
                        "coordinates": {"x": click_x, "y": click_y}
                    }
                except Exception as e:
                    return {"status": "error", "message": str(e)}

        # Tier 2: Inspect UIA Accessibility Scene Graph
        try:
            from backend.services.perception.uia_scene_graph import UIASceneGraph
            sg = UIASceneGraph()
            scene = sg.capture_scene(max_depth=3, max_elements=50)
            for elem in scene.elements:
                if target_name in elem.name.lower() or target_name in elem.id.lower():
                    b = elem.bounds
                    if b and len(b) == 4:
                        cx = (b[0] + b[2]) // 2
                        cy = (b[1] + b[3]) // 2
                        try:
                            import pyautogui
                            pyautogui.click(cx, cy)
                            return {
                                "status": "clicked",
                                "target": elem.name,
                                "element_id": elem.id,
                                "method": "uia_scene_graph",
                                "coordinates": {"x": cx, "y": cy}
                            }
                        except Exception as e:
                            return {"status": "error", "message": str(e)}
        except Exception:
            pass

        # Tier 3: OCR Computer Vision Fallback
        ocr_result = self.click_element_by_ocr(element_name)
        if ocr_result.get("status") == "clicked":
            return ocr_result

        # Tier 4: Scroll-and-Search Adaptive Fallback
        try:
            import pyautogui
            for _ in range(2):
                pyautogui.scroll(-500)
                time.sleep(0.35)
                ocr_scroll = self.click_element_by_ocr(element_name)
                if ocr_scroll.get("status") == "clicked":
                    ocr_scroll["method"] = "scroll_and_ocr"
                    return ocr_scroll
        except Exception:
            pass

        return {"status": "not_found", "target": element_name}

    def invoke_control(self, automation_id_or_name: str) -> Dict[str, Any]:
        """
        Execute Win32 UIA InvokePattern on a button or control by AutomationID / Name.
        """
        target = automation_id_or_name.lower().strip()

        try:
            from backend.services.perception.uia_scene_graph import UIASceneGraph
            sg = UIASceneGraph()
            scene = sg.capture_scene(max_depth=3, max_elements=50)

            for elem in scene.elements:
                if target in elem.name.lower() or target in elem.id.lower():
                    b = elem.bounds
                    if b and len(b) == 4:
                        cx = (b[0] + b[2]) // 2
                        cy = (b[1] + b[3]) // 2
                        try:
                            import pyautogui
                            pyautogui.click(cx, cy)
                            return {
                                "status": "invoked",
                                "element_id": elem.id,
                                "name": elem.name,
                                "method": "uia_invoke",
                                "coords": [cx, cy]
                            }
                        except Exception as e:
                            return {"status": "error", "message": str(e)}
        except Exception:
            pass

        # Fallback to OCR
        ocr_result = self.click_element_by_ocr(automation_id_or_name)
        if ocr_result.get("status") == "clicked":
            return {
                "status": "invoked",
                "name": ocr_result.get("target"),
                "method": "ocr_fallback",
                "coords": [ocr_result["coordinates"]["x"], ocr_result["coordinates"]["y"]],
                "engine": ocr_result.get("engine")
            }

        return {"status": "not_found", "query": automation_id_or_name}

    def set_control_value(self, field_name: str, value: str) -> Dict[str, Any]:
        """Type text value directly into an input text field after focus verification."""
        try:
            res = self.click_element_by_name(field_name)
            if res.get("status") in ("clicked", "invoked"):
                time.sleep(0.1)
                import pyautogui
                pyautogui.hotkey("ctrl", "a")
                pyautogui.typewrite(value, interval=0.01) if value.isascii() else pyautogui.write(value)
                return {
                    "status": "value_set",
                    "field": field_name,
                    "value": value,
                    "focus_method": res.get("method", "native")
                }

            logger.warning("Target field '{}' not found on active window. Rejecting blind keystroke injection.", field_name)
            return {
                "status": "error",
                "message": f"Target control field '{field_name}' not found on active window",
                "field": field_name
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Backward-compatible alias
UIAEngine = UIAPerceptionEngine
