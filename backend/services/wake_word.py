"""
JARVIS AI Desktop Assistant - Wake Word Detection Service Facade.

Backward-compatible facade delegating to WakeWordManager in backend.services.voice.wake_word_manager.
"""

from backend.services.voice.wake_word_manager import (
    WakeWordManager as WakeWordService,
)

__all__ = ["WakeWordService"]
