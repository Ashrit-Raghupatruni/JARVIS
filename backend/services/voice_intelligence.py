"""
Voice Intelligence Service for JARVIS.

Backward-compatible facade delegating to VoiceIntelligenceService in
backend.services.voice.intelligence.
"""

from backend.services.voice.intelligence import VoiceIntelligenceService

__all__ = ["VoiceIntelligenceService"]
