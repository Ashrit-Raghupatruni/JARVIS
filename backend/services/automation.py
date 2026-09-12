"""
JARVIS AI Desktop Assistant - Desktop Automation Service (Facade).
==================================================================
Backward-compatible facade delegating directly to backend.services.automation.desktop_executor.
"""

from __future__ import annotations

from typing import Optional

from backend.services.automation.desktop_executor import (
    DesktopExecutor,
    APP_PATHS,
    APP_PROCESS_NAMES,
    _resolve_user_path,
    _resolve_app_path,
)
from backend.services.safety import SafetyService


class AutomationService(DesktopExecutor):
    """
    Desktop automation service for Windows (Backward-compatible facade).
    """

    def __init__(self, safety_service: Optional[SafetyService] = None) -> None:
        super().__init__(safety_service=safety_service)


__all__ = [
    "AutomationService",
    "APP_PATHS",
    "APP_PROCESS_NAMES",
    "_resolve_user_path",
    "_resolve_app_path",
]
