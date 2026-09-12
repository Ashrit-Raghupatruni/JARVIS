"""
JARVIS Voice Architecture Package.

Provides consolidated managers for Voice Lifecycle, Audio Devices,
Wake Word Detection, Speech-to-Text (STT), Text-to-Speech (TTS),
and Voice Intelligence.
"""

from backend.services.voice.audio_device_manager import AudioDeviceManager
from backend.services.voice.intelligence import VoiceIntelligenceService
from backend.services.voice.stt_manager import STTManager, clean_whisper_hallucinations
from backend.services.voice.tts_manager import (
    EdgeTTSProvider,
    LocalTTSProvider,
    PiperTTSProvider,
    TTSManager,
)
from backend.services.voice.voice_manager import (
    ACKNOWLEDGMENTS,
    SERIOUS_ACKNOWLEDGMENTS,
    VoiceManager,
    clean_text_for_tts,
    expects_follow_up,
)
from backend.services.voice.wake_word_manager import WakeWordManager

__all__ = [
    "VoiceManager",
    "STTManager",
    "TTSManager",
    "WakeWordManager",
    "AudioDeviceManager",
    "VoiceIntelligenceService",
    "clean_whisper_hallucinations",
    "clean_text_for_tts",
    "expects_follow_up",
    "EdgeTTSProvider",
    "PiperTTSProvider",
    "LocalTTSProvider",
    "ACKNOWLEDGMENTS",
    "SERIOUS_ACKNOWLEDGMENTS",
]
