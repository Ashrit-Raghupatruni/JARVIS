"""
Browser automation service for JARVIS (Facade).
================================================
Backward-compatible facade delegating directly to backend.services.automation.browser_executor.
"""

from backend.services.automation.browser_executor import (
    BrowserExecutor,
    BrowserService,
)

__all__ = ["BrowserService", "BrowserExecutor"]
