"""
Desktop Automation Service for JARVIS (Facade).
================================================
Backward-compatible facade delegating directly to backend.services.automation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.services.automation.orchestrator import AutomationOrchestrator
from backend.services.automation.desktop_executor import DesktopExecutor


class DesktopAutomationService(AutomationOrchestrator):
    """Service for Desktop Automation & RPA Workflows (Facade)."""

    def __init__(
        self,
        workflows_dir: Optional[Path] = None,
        desktop_executor: Optional[DesktopExecutor] = None,
    ) -> None:
        super().__init__(workflows_dir=workflows_dir, desktop_executor=desktop_executor)

    # ── Delegated Desktop Actions for 100% backward compatibility ────────

    def arrange_windows_layout(
        self,
        layout_preset: str = "split_left_right",
        window_titles: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        return self.desktop.arrange_windows_layout(layout_preset=layout_preset, window_titles=window_titles)

    def get_clipboard_content(self) -> Dict[str, Any]:
        return self.desktop.get_clipboard_content()

    def get_clipboard_history(self) -> List[Dict[str, Any]]:
        return self.desktop.get_clipboard_history()

    def check_folder_changes(self, folder_path: str, known_files: Optional[List[str]] = None) -> Dict[str, Any]:
        return self.desktop.check_folder_changes(folder_path=folder_path, known_files=known_files)


__all__ = ["DesktopAutomationService"]
