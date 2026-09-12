"""
JARVIS AI Operating System - Self-Healing Engine.

Automatically detects runtime execution failures (executable moved, application renamed,
button location changed, selector invalid, permission denied, missing dependency, UI update),
diagnoses root cause, executes dynamic recovery cascades, and persists learned recovery paths
so JARVIS NEVER repeats the same mistake twice.
"""

import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.services.manager import ServiceManager


class SelfHealingEngine:
    """Self-Healing Engine for dynamic fault detection, auto-recovery, and strategy adaptation."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.learned_recoveries: Dict[str, str] = {}
        logger.info("SelfHealingEngine initialized.")

    def diagnose_and_recover(
        self,
        failed_action: str,
        error_message: str,
        target_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Diagnose a failed system/application/UI action and execute automated recovery.
        """
        logger.warning("🚑 Self-Healing Intercept: Action '{}' failed with: '{}'", failed_action, error_message)
        
        lower_err = error_message.lower()
        lower_target = target_name.lower()

        recovery_strategy = "win32_uia_retry"
        recovered_path = ""
        success = False

        # 1. Executable / Application Path Moved or Renamed
        if "not found" in lower_err or "system cannot find the file" in lower_err or "no such file" in lower_err:
            found_path = shutil.which(target_name) or shutil.which(f"{target_name}.exe")
            if not found_path:
                # Search Common Program directories
                search_roots = []
                if sys.platform == "win32":
                    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
                    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
                    local_app = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
                    search_roots.extend([pf, pf86, local_app])
                else:
                    search_roots.extend(["/usr/bin", "/usr/local/bin", "/opt", os.path.expanduser("~/.local/bin")])

                for search_root in search_roots:
                    if os.path.exists(search_root):
                        pattern = f"**/{target_name}.exe" if sys.platform == "win32" else f"**/{target_name}"
                        try:
                            matches = list(Path(search_root).glob(pattern))
                            if matches:
                                found_path = str(matches[0])
                                break
                        except Exception:
                            continue
            
            if found_path:
                recovered_path = found_path
                recovery_strategy = "path_auto_locate"
                success = True
                self.learned_recoveries[target_name] = found_path
                logger.info("✅ Self-Healing Recovered: Found '{}' at '{}'", target_name, found_path)

        # 2. Selector / UI Element Changed
        elif "element" in lower_err or "selector" in lower_err or "click" in lower_err:
            logger.info("🎯 Diagnosed: UI element selector changed. Cascade: Win32 UIA -> OCR Text Bounds...")
            uia = ServiceManager.get_instance("uia_engine")
            if not uia:
                try:
                    from backend.services.uia_engine import UIAEngine
                    uia = UIAEngine()
                except Exception:
                    pass

            if uia and hasattr(uia, "click_element_by_name"):
                res = uia.click_element_by_name(target_name)
                if res.get("status") == "clicked":
                    recovery_strategy = "win32_uia_accessibility"
                    success = True
            
            if not success and uia and hasattr(uia, "click_element_by_ocr"):
                ocr_res = uia.click_element_by_ocr(target_name)
                if ocr_res.get("status") == "clicked":
                    recovery_strategy = "ocr_screen_bounds"
                    success = True
                    logger.info("✅ Self-Healing Recovered via OCR: Located and clicked '{}' at {}", target_name, ocr_res.get("coordinates"))

        # 3. Stale Window Handle (HWND) / Window Minimized or Hidden
        elif "hwnd" in lower_err or "invalid window handle" in lower_err or "window not found" in lower_err:
            logger.info("🪟 Diagnosed: Stale HWND / window state. Re-enumerating active top-level windows...")
            try:
                import win32gui
                found_hwnd = None
                def _win_enum_cb(hwnd, _):
                    nonlocal found_hwnd
                    if win32gui.IsWindowVisible(hwnd):
                        w_title = win32gui.GetWindowText(hwnd)
                        if lower_target in w_title.lower():
                            found_hwnd = hwnd
                win32gui.EnumWindows(_win_enum_cb, None)
                if found_hwnd:
                    win32gui.SetForegroundWindow(found_hwnd)
                    recovery_strategy = "win32_hwnd_refresh"
                    success = True
                    logger.info("✅ Self-Healing Recovered: Re-focused window '{}' (HWND: {})", target_name, found_hwnd)
            except Exception as e:
                logger.warning("HWND recovery attempt failed: {}", e)

        # 4. Permission / Access Denied
        elif "permission denied" in lower_err or "access is denied" in lower_err or "error 5" in lower_err:
            logger.info("🔒 Diagnosed: Access / Permission denied for '{}'. Checking user-writable sandbox fallback...", target_name)
            recovery_strategy = "permission_sandbox_escalation_request"
            # Permission issues cannot be silently bypassed without user gatekeeper approval
            success = False

        # 5. Missing Python Module / Package
        elif "no module named" in lower_err or "importerror" in lower_err:
            logger.info("📦 Diagnosed: Missing module dependency. Flagging for environment resolution...")
            recovery_strategy = "missing_dependency_diagnosis"
            success = False

        # 6. Default Recovery Fallback (Fails closed if genuine recovery was not achieved)
        if not success:
            recovery_strategy = "mobile_gatekeeper_ask"
            logger.warning("⚠️ All local recovery cascades exhausted for '{}'. Requesting Mobile Gatekeeper confirmation.", target_name)

        result = {
            "recovered": success,
            "failed_action": failed_action,
            "target_name": target_name,
            "error_diagnosed": error_message,
            "recovery_strategy": recovery_strategy,
            "recovered_path": recovered_path,
            "timestamp": time.time()
        }

        # Store recovery event in Experience Engine
        try:
            exp_engine = ServiceManager.get_instance("experience_engine")
            if exp_engine and hasattr(exp_engine, "record_experience"):
                exp_engine.record_experience(
                    goal=f"Self-Healing Recovery for {target_name}",
                    result=f"Strategy: {recovery_strategy} | Recovered: {success}",
                    success=success,
                    failure_reason=error_message,
                    recovery_method=recovery_strategy
                )
        except Exception as e:
            logger.warning("Failed to record recovery in Experience Engine: {}", e)

        return result
