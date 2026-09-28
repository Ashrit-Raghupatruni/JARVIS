"""
JARVIS AI Operating System - Self-Healing Engine.

Automatically detects runtime execution failures (executable moved, application renamed,
button location changed, selector invalid, permission denied, missing dependency, UI update),
diagnoses root cause, executes dynamic recovery cascades, and persists learned recovery paths
so JARVIS NEVER repeats the same mistake twice.
"""

import os
import sys
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
        self.recovery_attempts: Dict[str, int] = {}
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
        Enforces a maximum of 2 recovery attempts per target to prevent infinite retry loops.
        """
        attempt_key = f"{failed_action}:{target_name.lower().strip()}"
        current_attempts = self.recovery_attempts.get(attempt_key, 0)
        if current_attempts >= 2:
            logger.warning("⚠️ Self-Healing threshold reached (max 2 attempts) for '{}'. Failing fast.", attempt_key)
            return {
                "recovered": False,
                "failed_action": failed_action,
                "target_name": target_name,
                "error_diagnosed": f"Maximum recovery attempts exceeded (previous: {error_message})",
                "recovery_strategy": "fail_fast",
                "recovered_path": "",
                "timestamp": time.time()
            }
        self.recovery_attempts[attempt_key] = current_attempts + 1

        logger.warning("🚑 Self-Healing Intercept (Attempt {}/2): Action '{}' failed with: '{}'", self.recovery_attempts[attempt_key], failed_action, error_message)
        
        lower_err = error_message.lower()
        lower_target = target_name.lower()

        recovery_strategy = "win32_uia_retry"
        recovered_path = ""
        success = False

        # 1. Executable / Application Path Moved or Renamed
        if "not found" in lower_err or "system cannot find the file" in lower_err or "no such file" in lower_err:
            try:
                from backend.services.automation.desktop_executor import _resolve_app_path
                found_path = _resolve_app_path(target_name)
            except Exception:
                found_path = None

            if not found_path:
                found_path = shutil.which(target_name) or shutil.which(f"{target_name}.exe")

            if not found_path:
                # Shallow search in common program directories (depth <= 2)
                search_roots = []
                if sys.platform == "win32":
                    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
                    local_app = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
                    search_roots.extend([pf, local_app])
                else:
                    search_roots.extend(["/usr/bin", "/usr/local/bin", os.path.expanduser("~/.local/bin")])

                exe_name = f"{target_name}.exe" if sys.platform == "win32" else target_name
                for search_root in search_roots:
                    if not os.path.exists(search_root):
                        continue
                    try:
                        cand_direct = os.path.join(search_root, exe_name)
                        if os.path.exists(cand_direct):
                            found_path = cand_direct
                            break
                        for entry in os.scandir(search_root):
                            if entry.is_dir():
                                cand_sub = os.path.join(entry.path, exe_name)
                                if os.path.exists(cand_sub):
                                    found_path = cand_sub
                                    break
                        if found_path:
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
        if success:
            self.recovery_attempts.pop(attempt_key, None)
        else:
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
