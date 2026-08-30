"""
Auto-Start on Boot & User Logon Utility for JARVIS.

Registers JARVIS desktop assistant in:
1. Windows Task Scheduler (Task: 'JARVIS_Desktop_Assistant' on user logon)
   - Guarantees execution in the interactive user desktop session (Session 1+).
   - Has full access to UI Automation, display surfaces, and input hardware.
2. Windows Registry HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run (Fallback/Alternative).
"""

import sys
import os
import subprocess
from typing import Dict, Any
from loguru import logger

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

APP_NAME = "JARVIS_AI_OS"
TASK_NAME = "JARVIS_Desktop_Assistant"


class AutoStartService:
    """Manages OS startup & user logon registration for JARVIS."""

    @staticmethod
    def get_launcher_command() -> str:
        """Resolve absolute path to the desktop launcher."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        start_bat = os.path.join(project_root, "start.bat")
        if os.path.exists(start_bat):
            return f'"{start_bat}"'
        
        # Fallback to python main.py
        py_exe = sys.executable
        main_py = os.path.join(project_root, "backend", "main.py")
        return f'"{py_exe}" "{main_py}"'

    # ── TASK SCHEDULER (Primary: Interactive Session 1+) ────────────────────

    @classmethod
    def is_task_scheduled(cls) -> bool:
        """Check if Windows Task Scheduler has JARVIS registered."""
        try:
            res = subprocess.run(
                ["schtasks", "/Query", "/TN", TASK_NAME],
                capture_output=True,
                text=True,
                timeout=5
            )
            return res.returncode == 0
        except Exception as e:
            logger.debug(f"Task Scheduler query failed: {e}")
            return False

    @classmethod
    def enable_task_scheduler(cls) -> Dict[str, Any]:
        """
        Create a Windows Scheduled Task to run on user logon.
        Ensures execution within the interactive desktop session (Session 1+),
        retaining full UI Automation (UIA) and display capture access.
        """
        cmd = cls.get_launcher_command()
        try:
            # Create scheduled task running on user logon with highest available privileges
            args = [
                "schtasks", "/Create",
                "/TN", TASK_NAME,
                "/TR", cmd,
                "/SC", "ONLOGON",
                "/RL", "HIGHEST",
                "/F"  # Force overwrite
            ]
            res = subprocess.run(args, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                logger.info(f"✓ Registered Windows Scheduled Task '{TASK_NAME}' on logon: {cmd}")
                return {"status": "ok", "method": "task_scheduler", "task_name": TASK_NAME, "command": cmd}
            else:
                # If HIGHEST fails without admin rights, retry without /RL HIGHEST (standard user level)
                args_std = [
                    "schtasks", "/Create",
                    "/TN", TASK_NAME,
                    "/TR", cmd,
                    "/SC", "ONLOGON",
                    "/F"
                ]
                res_std = subprocess.run(args_std, capture_output=True, text=True, timeout=10)
                if res_std.returncode == 0:
                    logger.info(f"✓ Registered Windows Scheduled Task '{TASK_NAME}' (standard privileges): {cmd}")
                    return {"status": "ok", "method": "task_scheduler", "task_name": TASK_NAME, "command": cmd}
                
                err = res.stderr.strip() or res_std.stderr.strip()
                logger.warning(f"Task scheduler creation returned code {res.returncode}: {err}")
                return {"status": "error", "message": err}
        except Exception as e:
            logger.error(f"Failed to register task scheduler: {e}")
            return {"status": "error", "message": str(e)}

    @classmethod
    def disable_task_scheduler(cls) -> Dict[str, Any]:
        """Delete the Windows Scheduled Task."""
        try:
            res = subprocess.run(
                ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                logger.info(f"✓ Deleted Windows Scheduled Task '{TASK_NAME}'.")
                return {"status": "ok", "task_name": TASK_NAME, "enabled": False}
            return {"status": "ok", "message": "Task was not registered", "enabled": False}
        except Exception as e:
            logger.error(f"Failed to delete scheduled task: {e}")
            return {"status": "error", "message": str(e)}

    # ── REGISTRY RUN KEY (Secondary / Fallback) ─────────────────────────────

    @staticmethod
    def is_registry_enabled() -> bool:
        """Check if JARVIS auto-start registry key exists."""
        if not HAS_WINREG:
            return False
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ
            )
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return bool(val)
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.debug(f"Auto-start registry read error: {e}")
            return False

    @classmethod
    def enable_registry(cls) -> Dict[str, Any]:
        """Register executable in Windows Run registry key."""
        if not HAS_WINREG:
            return {"status": "error", "message": "winreg module not available on host OS"}

        cmd = cls.get_launcher_command()
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            logger.info(f"✓ Enabled JARVIS Auto-Start registry key: {cmd}")
            return {"status": "ok", "method": "registry", "enabled": True, "command": cmd}
        except Exception as e:
            logger.error(f"Failed to enable auto-start registry key: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def disable_registry() -> Dict[str, Any]:
        """Delete JARVIS auto-start registry key."""
        if not HAS_WINREG:
            return {"status": "error", "message": "winreg module not available on host OS"}

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
            logger.info("✓ Disabled JARVIS Auto-Start registry key.")
            return {"status": "ok", "method": "registry", "enabled": False}
        except FileNotFoundError:
            return {"status": "ok", "enabled": False}
        except Exception as e:
            logger.error(f"Failed to disable auto-start registry key: {e}")
            return {"status": "error", "message": str(e)}

    # ── STARTUP FOLDER (Direct User Shell Autorun) ──────────────────────────

    @classmethod
    def get_startup_folder_path(cls) -> str:
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")

    @classmethod
    def is_startup_folder_enabled(cls) -> bool:
        cmd_file = os.path.join(cls.get_startup_folder_path(), "JARVIS_Assistant.cmd")
        return os.path.exists(cmd_file)

    @classmethod
    def enable_startup_folder(cls) -> Dict[str, Any]:
        """Create a logon script in the user's Windows Startup folder."""
        folder = cls.get_startup_folder_path()
        os.makedirs(folder, exist_ok=True)
        cmd_file = os.path.join(folder, "JARVIS_Assistant.cmd")
        launcher = cls.get_launcher_command()
        content = f'@echo off\r\nstart "" {launcher} --autostart\r\n'
        with open(cmd_file, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"✓ Created startup folder shortcut: {cmd_file}")
        return {"status": "ok", "method": "startup_folder", "enabled": True, "path": cmd_file}

    @classmethod
    def disable_startup_folder(cls) -> Dict[str, Any]:
        """Remove the logon script from the user's Windows Startup folder."""
        cmd_file = os.path.join(cls.get_startup_folder_path(), "JARVIS_Assistant.cmd")
        if os.path.exists(cmd_file):
            try:
                os.remove(cmd_file)
                logger.info(f"✓ Removed startup folder shortcut: {cmd_file}")
                return {"status": "ok", "method": "startup_folder", "enabled": False}
            except Exception as e:
                logger.error(f"Failed to remove startup folder shortcut: {e}")
                return {"status": "error", "message": str(e)}
        return {"status": "ok", "method": "startup_folder", "enabled": False}

    # ── UNIFIED STATUS & CONFIGURATION ──────────────────────────────────────

    @classmethod
    def is_enabled(cls) -> bool:
        """True if Task Scheduler, Startup folder, or Registry key is active."""
        return cls.is_task_scheduled() or cls.is_startup_folder_enabled() or cls.is_registry_enabled()

    @classmethod
    def enable(cls, prefer_task_scheduler: bool = True) -> Dict[str, Any]:
        """
        Enable auto-start on user logon:
        Tries Task Scheduler first; if restricted, uses Startup folder and Registry Run key.
        """
        if prefer_task_scheduler:
            res = cls.enable_task_scheduler()
            if res.get("status") == "ok":
                return res

        # Fallback to Startup folder & Registry
        sf_res = cls.enable_startup_folder()
        reg_res = cls.enable_registry()
        return {
            "status": "ok",
            "method": "startup_folder_and_registry",
            "enabled": True,
            "startup_folder": sf_res,
            "registry": reg_res
        }

    @classmethod
    def disable(cls) -> Dict[str, Any]:
        """Disable all auto-start mechanisms."""
        r1 = cls.disable_task_scheduler()
        r2 = cls.disable_startup_folder()
        r3 = cls.disable_registry()
        return {
            "status": "ok",
            "enabled": False,
            "task_scheduler_disabled": r1.get("status") == "ok",
            "startup_folder_disabled": r2.get("status") == "ok",
            "registry_disabled": r3.get("status") == "ok"
        }

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Get full auto-start configuration status."""
        return {
            "enabled": cls.is_enabled(),
            "task_scheduler_active": cls.is_task_scheduled(),
            "startup_folder_active": cls.is_startup_folder_enabled(),
            "registry_run_active": cls.is_registry_enabled(),
            "launcher_command": cls.get_launcher_command()
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Boot Auto-Start Manager")
    parser.add_argument("--enable", action="store_true", help="Enable auto-start at user logon")
    parser.add_argument("--disable", action="store_true", help="Disable auto-start")
    parser.add_argument("--status", action="store_true", help="Query current auto-start status")
    args = parser.parse_args()

    if args.enable:
        res = AutoStartService.enable()
        print("Enable Result:", res)
    elif args.disable:
        res = AutoStartService.disable()
        print("Disable Result:", res)
    else:
        res = AutoStartService.get_status()
        print("Auto-Start Status:", res)

