"""
Voice Intelligence Service for JARVIS.

Provides acoustic feature & emotion detection, speaker profile management,
full-duplex streaming status, and wake word sensitivity tuning.
"""

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger


class VoiceIntelligenceService:
    """Service for Phase 11 Voice Intelligence."""

    def __init__(self, profiles_file: Optional[Path] = None):
        self.profiles_file = profiles_file or Path("data/speaker_profiles.json")
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        self.wake_word_threshold = 0.50
        self._profiles = self._load_profiles()
        logger.info("VoiceIntelligenceService initialized. Profiles file: {}", self.profiles_file)

    def _load_profiles(self) -> Dict[str, Any]:
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Could not load speaker profiles JSON: {}", e)
        return {
            "primary_user": {
                "name": "Ashrit",
                "role": "Owner",
                "preferred_tts_voice": "en-US-GuyNeural",
                "speech_rate": "+0%",
                "created_at": time.time()
            }
        }

    def _save_profiles(self) -> None:
        try:
            with open(self.profiles_file, "w", encoding="utf-8") as f:
                json.dump(self._profiles, f, indent=2)
        except Exception as e:
            logger.error("Failed to save speaker profiles JSON: {}", e)

    # ── 1. Emotion Detection (Acoustic Feature Analyzer) ───────────────

    def detect_speaker_emotion(self, audio_rms: float = 0.05, pitch_hz: float = 180.0) -> Dict[str, Any]:
        """
        Classify speaker emotion state based on acoustic energy (RMS) and pitch features.

        Args:
            audio_rms: Root Mean Square volume level (0.0 to 1.0).
            pitch_hz: Fundamental pitch estimate in Hz.

        Returns:
            Dict containing emotion classification (Calm, Energetic, Hurried, Neutral) and confidence.
        """
        if audio_rms > 0.15 and pitch_hz > 220:
            emotion = "Energetic"
            confidence = 0.88
            speech_adaptation = "Respond with high energy and concise facts."
        elif audio_rms > 0.10:
            emotion = "Hurried / Urgent"
            confidence = 0.82
            speech_adaptation = "Accelerate TTS rate by +10% and keep responses direct."
        elif audio_rms < 0.02:
            emotion = "Calm / Quiet"
            confidence = 0.90
            speech_adaptation = "Maintain soft, soothing tone."
        else:
            emotion = "Neutral / Focused"
            confidence = 0.95
            speech_adaptation = "Standard conversational response."

        return {
            "emotion": emotion,
            "confidence": confidence,
            "acoustic_features": {"rms_energy": round(audio_rms, 4), "pitch_estimate_hz": round(pitch_hz, 1)},
            "speech_adaptation": speech_adaptation
        }

    # ── 2. Speaker Profiles ───────────────────────────────────────────────

    def manage_speaker_profile(self, action: str = "get", name: str = "Ashrit", details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create, update, retrieve, or list speaker profiles.

        Args:
            action: 'get', 'update', 'list'
            name: Speaker profile key/name.
            details: Profile fields to update.

        Returns:
            Dict with profile data or list.
        """
        key = name.lower().strip()

        if action == "update" and details:
            if key not in self._profiles:
                self._profiles[key] = {"name": name, "created_at": time.time()}
            self._profiles[key].update(details)
            self._save_profiles()
            return {"status": "profile_updated", "profile": self._profiles[key]}

        elif action == "list":
            return {"status": "profiles_listed", "profiles": list(self._profiles.values())}

        # Default get
        profile = self._profiles.get(key) or self._profiles.get("primary_user") or {"name": name}
        return {"status": "profile_retrieved", "profile": profile}

    # ── 3. Wake Word Threshold Tuning ─────────────────────────────────────

    def tune_wake_word_threshold(self, new_threshold: float) -> Dict[str, Any]:
        """
        Tune openwakeword sensitivity threshold.

        Args:
            new_threshold: Value between 0.1 (very sensitive) and 0.9 (strict).

        Returns:
            Status summary.
        """
        clamped = max(0.1, min(0.9, new_threshold))
        self.wake_word_threshold = clamped
        logger.info("Updated wake word threshold to: {}", clamped)
        return {
            "status": "threshold_updated",
            "wake_word": "hey_jarvis",
            "threshold": self.wake_word_threshold,
            "sensitivity": "High" if clamped < 0.4 else ("Medium" if clamped < 0.7 else "Strict")
        }

    def get_voice_intelligence_status(self) -> Dict[str, Any]:
        """Get full voice intelligence status."""
        return {
            "stt_engine": "Faster-Whisper (small)",
            "tts_engine": "Edge-TTS Neural (en-US-GuyNeural)",
            "wake_word_model": "hey_jarvis",
            "wake_word_threshold": self.wake_word_threshold,
            "full_duplex_enabled": True,
            "active_speaker_profiles": len(self._profiles)
        }
