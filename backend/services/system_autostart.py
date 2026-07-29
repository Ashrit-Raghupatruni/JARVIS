"""
Auto-Start on Boot Utility for JARVIS.

Registers JARVIS desktop assistant in Windows Registry HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
"""

import sys
import os
from typing import Dict, Any
from loguru import logger

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

APP_NAME = "JARVIS_AI_OS"


class AutoStartService:
    """Manages OS startup registration for JARVIS."""

    @staticmethod
    def is_enabled() -> bool:
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

    @staticmethod
    def enable() -> Dict[str, Any]:
        """Register executable / python entrypoint in Windows Run registry key."""
        if not HAS_WINREG:
            return {"status": "error", "message": "winreg module not available on host OS"}

        executable = sys.executable
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        cmd = f'"{executable}" "{script}"'

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
            return {"status": "ok", "enabled": True, "command": cmd}
        except Exception as e:
            logger.error(f"Failed to enable auto-start registry key: {e}")
            return {"status": "error", "message": str(e)}

    @staticmethod
    def disable() -> Dict[str, Any]:
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
            return {"status": "ok", "enabled": False}
        except FileNotFoundError:
            return {"status": "ok", "enabled": False}
        except Exception as e:
            logger.error(f"Failed to disable auto-start registry key: {e}")
            return {"status": "error", "message": str(e)}
