"""
JARVIS AI OS — Action Execution & Result Verification Loop Engine (Facade).
============================================================================
Backward-compatible facade delegating directly to backend.services.automation.verifier.
"""

from backend.services.automation.verifier import (
    ActionExecutionVerifier,
    ActionVerificationResult,
    ActionVerifier,
    action_verifier,
)

__all__ = [
    "ActionExecutionVerifier",
    "ActionVerificationResult",
    "ActionVerifier",
    "action_verifier",
]
