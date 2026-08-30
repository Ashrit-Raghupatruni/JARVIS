"""
Windows Explorer Right-Click Context Menu ("Ask JARVIS") Manager.

Registers static Windows Explorer context menu actions under:
- HKEY_CURRENT_USER\\Software\\Classes\\*\\shell\\JARVIS.Analyze
- HKEY_CURRENT_USER\\Software\\Classes\\*\\shell\\JARVIS.Summarize
- HKEY_CURRENT_USER\\Software\\Classes\\Directory\\shell\\JARVIS.Analyze
- HKEY_CURRENT_USER\\Software\\Classes\\Directory\\shell\\JARVIS.Summarize

Architectural Note & Scope Tradeoff:
This integration intentionally uses static Registry Shell Verb registration under HKCU.
- Advantages: 100% crash-proof, requires zero administrator elevation, survives Explorer crashes,
  and avoids compiling brittle unmanaged In-Process C++ COM Shell Extension DLLs (IShellExtInit).
- Tradeoff: Static registry verbs cannot conditionally hide/show based on dynamic file metadata
  or render custom high-DPI icon bitmaps without an in-proc DLL. This is a deliberate, reliable tradeoff.
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

ACTIONS = [
    {
        "id": "JARVIS.Analyze",
        "action_param": "analyze",
        "file_label": "Analyze with JARVIS",
        "dir_label": "Analyze Folder with JARVIS",
    },
    {
        "id": "JARVIS.Summarize",
        "action_param": "summarize",
        "file_label": "Summarize with JARVIS",
        "dir_label": "Summarize Folder with JARVIS",
    }
]


class ExplorerContextMenuManager:
    """Manages Windows Explorer context menu entries for JARVIS."""

    @staticmethod
    def get_handler_command(action_param: str) -> str:
        """Resolve python executable and handler script."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        
        # Prefer venv python if available
        venv_py = os.path.join(project_root, "backend", "venv", "Scripts", "python.exe")
        py_exe = venv_py if os.path.exists(venv_py) else sys.executable
        
        handler_script = os.path.join(project_root, "backend", "services", "context_menu_handler.py")
        return f'"{py_exe}" "{handler_script}" {action_param} "%1"'

    @classmethod
    def install(cls) -> Dict[str, Any]:
        """Register context menu entries in HKCU."""
        if not HAS_WINREG:
            return {"status": "error", "message": "winreg not supported on this OS"}

        installed = []
        targets = [
            ("r'Software\\Classes\\*\\shell'", r"Software\Classes\*\shell", "file_label"),
            ("r'Software\\Classes\\Directory\\shell'", r"Software\Classes\Directory\shell", "dir_label")
        ]

        try:
            for root_desc, base_path, label_key in targets:
                for act in ACTIONS:
                    verb_key_path = f"{base_path}\\{act['id']}"
                    label = act[label_key]
                    cmd = cls.get_handler_command(act["action_param"])

                    # Create verb key
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, verb_key_path) as key:
                        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, label)
                        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, "shell32.dll,277")  # Clean system AI/lightning glyph

                    # Create command subkey
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{verb_key_path}\\command") as cmd_key:
                        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)

                    installed.append({"path": verb_key_path, "label": label, "command": cmd})
                    logger.info(f"✓ Registered Windows Context Menu: '{label}' -> {verb_key_path}")

            return {"status": "ok", "installed_count": len(installed), "entries": installed}
        except Exception as e:
            logger.error(f"Context menu installation error: {e}")
            return {"status": "error", "message": str(e)}

    @classmethod
    def uninstall(cls) -> Dict[str, Any]:
        """Remove context menu entries from HKCU."""
        if not HAS_WINREG:
            return {"status": "error", "message": "winreg not supported on this OS"}

        removed = []
        base_paths = [r"Software\Classes\*\shell", r"Software\Classes\Directory\shell"]

        for base in base_paths:
            for act in ACTIONS:
                verb_path = f"{base}\\{act['id']}"
                try:
                    # Must delete child 'command' key first
                    try:
                        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{verb_path}\\command")
                    except FileNotFoundError:
                        pass
                    
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, verb_path)
                    removed.append(verb_path)
                    logger.info(f"✓ Removed Context Menu entry: {verb_path}")
                except FileNotFoundError:
                    pass
                except Exception as e:
                    logger.warning(f"Error removing {verb_path}: {e}")

        return {"status": "ok", "removed_count": len(removed), "removed": removed}

    @classmethod
    def is_installed(cls) -> bool:
        """Check if context menu entries exist."""
        if not HAS_WINREG:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell\JARVIS.Analyze"):
                return True
        except FileNotFoundError:
            return False
        except Exception:
            return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Windows Explorer 'Ask JARVIS' Context Menu Manager")
    parser.add_argument("--install", action="store_true", help="Install context menu entries")
    parser.add_argument("--uninstall", action="store_true", help="Remove context menu entries")
    parser.add_argument("--status", action="store_true", help="Check status")
    args = parser.parse_args()

    if args.install:
        res = ExplorerContextMenuManager.install()
        print("Install Result:", res)
    elif args.uninstall:
        res = ExplorerContextMenuManager.uninstall()
        print("Uninstall Result:", res)
    else:
        status = ExplorerContextMenuManager.is_installed()
        print("Context Menu Installed:", status)
