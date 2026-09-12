"""
JARVIS AI Operating System - Native Windows UI Automation (UIA) Engine (Facade).
================================================================================
Backward-compatible facade delegating directly to backend.services.automation.uia_perception.
"""

from backend.services.automation.uia_perception import (
    UIAPerceptionEngine,
    UIAEngine,
)

__all__ = ["UIAEngine", "UIAPerceptionEngine"]
