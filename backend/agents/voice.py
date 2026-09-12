"""
Voice pipeline agent for JARVIS.

Backward-compatible facade delegating to the consolidated VoiceManager in
backend.services.voice.
"""

from backend.services.voice.voice_manager import (
    ACKNOWLEDGMENTS,
    SERIOUS_ACKNOWLEDGMENTS,
    VoiceManager as VoiceAgent,
    clean_text_for_tts,
    expects_follow_up,
)

__all__ = [
    "VoiceAgent",
    "ACKNOWLEDGMENTS",
    "SERIOUS_ACKNOWLEDGMENTS",
    "clean_text_for_tts",
    "expects_follow_up",
]
