"""
JARVIS AI Desktop Assistant - Text-to-Speech Service Facade.

Backward-compatible facade delegating to TTSManager in backend.services.voice.tts_manager.
"""

from backend.services.voice.tts_manager import (
    EdgeTTSProvider,
    LocalTTSProvider,
    PiperTTSProvider,
    TTSManager as TTSService,
)

__all__ = [
    "TTSService",
    "EdgeTTSProvider",
    "PiperTTSProvider",
    "LocalTTSProvider",
]
