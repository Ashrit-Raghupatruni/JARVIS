"""
JARVIS AI Desktop Assistant - Speech-to-Text Service Facade.

Backward-compatible facade delegating to STTManager in backend.services.voice.stt_manager.
"""

from backend.services.voice.stt_manager import (
    STTManager as STTService,
    clean_whisper_hallucinations,
)

__all__ = ["STTService", "clean_whisper_hallucinations"]
