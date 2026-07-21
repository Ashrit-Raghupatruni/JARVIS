"""
Voice Skill for FastMCP & Skill Registry integration.
Exposes Phase 11 tools: acoustic emotion detection, speaker profile manager, wake word tuning, voice intelligence status.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.voice_intelligence import VoiceIntelligenceService


class VoiceSkill(BaseSkill):
    """Skill exposing Phase 11 Voice Intelligence tools."""

    name = "VoiceSkill"
    description = "Acoustic speaker emotion classification, speaker profiles manager, wake word threshold tuner, voice status."

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
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "detect_speaker_emotion":
            return self.voice_service.detect_speaker_emotion(
                parameters.get("audio_rms", 0.05),
                parameters.get("pitch_hz", 180.0)
            )
        elif tool_name == "manage_speaker_profile":
            return self.voice_service.manage_speaker_profile(
                parameters.get("action", "get"),
                parameters.get("name", "Ashrit")
            )
        elif tool_name == "tune_wake_word_threshold":
            return self.voice_service.tune_wake_word_threshold(parameters.get("new_threshold", 0.5))
        elif tool_name == "get_voice_intelligence_status":
            return self.voice_service.get_voice_intelligence_status()
        else:
            raise ValueError(f"Unknown voice tool: {tool_name}")
