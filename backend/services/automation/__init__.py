"""
JARVIS AI Operating System - Automation Package.
================================================
Unified automation architecture package exporting:
- AutomationOrchestrator: Multi-step macro & workflow coordinator
- DesktopExecutor: Low-level Win32, PyAutoGUI, application, window, and file actions
- BrowserExecutor: Playwright Chromium automation and search fallback
- UIAPerceptionEngine: Win32 controls inspection, UIA accessibility, and vision OCR
- ActionExecutionVerifier: Action verification and self-healing loop
- APP_PATHS, APP_PROCESS_NAMES: Standard application registry mappings
"""

from backend.services.automation.desktop_executor import (
    DesktopExecutor,
    APP_PATHS,
    APP_PROCESS_NAMES,
)
from backend.services.automation.browser_executor import (
    BrowserExecutor,
    BrowserService,
)
from backend.services.automation.uia_perception import (
    UIAPerceptionEngine,
    UIAEngine,
)
from backend.services.automation.verifier import (
    ActionExecutionVerifier,
    ActionVerifier,
    action_verifier,
)
from backend.services.automation.orchestrator import (
    AutomationOrchestrator,
)

# Backward-compatible alias
AutomationService = DesktopExecutor

__all__ = [
    "AutomationOrchestrator",
    "AutomationService",
    "DesktopExecutor",
    "BrowserExecutor",
    "BrowserService",
    "UIAPerceptionEngine",
    "UIAEngine",
    "ActionExecutionVerifier",
    "ActionVerifier",
    "action_verifier",
    "APP_PATHS",
    "APP_PROCESS_NAMES",
]
