"""
Voice Skill for FastMCP & Skill Registry integration.
Exposes Phase 11 tools: acoustic emotion detection, speaker profile manager,
wake word tuning, voice intelligence status, neural voice synthesis (TTS),
and sound effect audio generation with fail-closed hardware guards.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.voice_intelligence import VoiceIntelligenceService


class VoiceSkill(BaseSkill):
    """Skill exposing Voice Intelligence, Speech Synthesis, and Audio Generation tools."""

    name = "VoiceSkill"
    description = "Speaker emotion detection, speaker profile manager, wake word tuning, neural TTS voice synthesis, and audio effect generation."

    def __init__(self, voice_intelligence_service: Optional[VoiceIntelligenceService] = None):
        self.voice_service = voice_intelligence_service or VoiceIntelligenceService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "detect_speaker_emotion",
                "description": "Classify speaker emotion state based on audio RMS energy and pitch estimates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "audio_rms": {"type": "number", "description": "RMS volume level (0.0 to 1.0)."},
                        "pitch_hz": {"type": "number", "description": "Pitch estimate in Hz."}
                    }
                }
            },
            {
                "name": "manage_speaker_profile",
                "description": "Retrieve, update, or list speaker profiles and speech preferences.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["get", "update", "list"]},
                        "name": {"type": "string", "description": "Speaker name."}
                    }
                }
            },
            {
                "name": "tune_wake_word_threshold",
                "description": "Tune openwakeword detection threshold (0.1 sensitive to 0.9 strict).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_threshold": {"type": "number", "description": "Threshold value."}
                    },
                    "required": ["new_threshold"]
                }
            },
            {
                "name": "get_voice_intelligence_status",
                "description": "Get full status of STT, TTS, wake-word, and full-duplex stream.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "synthesize_voice",
                "description": "Synthesize text into natural streaming speech audio via Edge-TTS / local neural voice engine.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text content to speak/synthesize."},
                        "voice_name": {"type": "string", "description": "Neural voice ID (e.g. 'en-US-GuyNeural', 'en-US-AriaNeural')."},
                        "speed": {"type": "number", "description": "Speech rate multiplier (default 1.0)."},
                        "pitch": {"type": "string", "description": "Pitch adjustment (e.g. '+0Hz', '+5Hz')."}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "list_available_voices",
                "description": "List available neural voices with gender, locale, and tone attributes.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "generate_audio_effect",
                "description": "Synthesize a sound effect or ambient audio clip with fail-closed hardware preflight validation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Sound effect description (e.g. 'laser beam pulse', 'rain on window')."},
                        "duration_seconds": {"type": "number", "description": "Audio length in seconds (default: 5.0)."}
                    },
                    "required": ["prompt"]
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "detect_speaker_emotion":
            return self.voice_service.detect_speaker_emotion(
                parameters.get("audio_rms", 0.0),
                parameters.get("pitch_hz", 150.0)
            )
        elif tool_name == "manage_speaker_profile":
            return self.voice_service.manage_speaker_profile(
                action=parameters.get("action", "get"),
                name=parameters.get("name", "Ashrit"),
                details=parameters.get("details")
            )
        elif tool_name == "tune_wake_word_threshold":
            return self.voice_service.tune_wake_word_threshold(parameters.get("new_threshold", 0.5))
        elif tool_name == "get_voice_intelligence_status":
            return self.voice_service.get_voice_intelligence_status()
        elif tool_name == "synthesize_voice":
            return await self.voice_service.synthesize_voice(
                parameters.get("text", ""),
                voice_name=parameters.get("voice_name", "en-US-GuyNeural"),
                speed=parameters.get("speed", 1.0),
                pitch=parameters.get("pitch", "+0Hz")
            )
        elif tool_name == "list_available_voices":
            return self.voice_service.list_available_voices()
        elif tool_name == "generate_audio_effect":
            return self.voice_service.generate_audio_effect(
                parameters.get("prompt", ""),
                duration_seconds=parameters.get("duration_seconds", 5.0)
            )
        else:
            raise ValueError(f"Unknown voice tool: {tool_name}")
