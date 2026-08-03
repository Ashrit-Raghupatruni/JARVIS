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

    def verify_speaker_biometrics(self, audio_features: Optional[List[float]] = None) -> Dict[str, Any]:
        """Verify speaker identity using acoustic embedding vector cosine similarity. Fails closed by default."""
        if not audio_features or not isinstance(audio_features, list) or len(audio_features) == 0:
            return {
                "verified": False,
                "speaker_name": "Unknown",
                "confidence": 0.0,
                "biometric_match": False,
                "method": "Acoustic Embedding Cosine Distance",
                "reason": "No audio feature vector supplied for verification."
            }

        ref_vector = self._profiles.get("primary_user", {}).get("reference_embedding")
        if not ref_vector or not isinstance(ref_vector, list) or len(ref_vector) != len(audio_features):
            logger.warning("Speaker verification failed: No valid enrolled reference embedding found for primary_user.")
            return {
                "verified": False,
                "speaker_name": "Unknown",
                "confidence": 0.0,
                "biometric_match": False,
                "method": "Acoustic Embedding Cosine Distance",
                "reason": "No enrolled reference speaker embedding configured."
            }

        # Compute dot product and norms for cosine similarity
        dot_prod = sum(a * b for a, b in zip(audio_features, ref_vector))
        norm_a = math.sqrt(sum(a * a for a in audio_features))
        norm_b = math.sqrt(sum(b * b for b in ref_vector))

        if norm_a == 0 or norm_b == 0:
            similarity = 0.0
        else:
            similarity = dot_prod / (norm_a * norm_b)

        is_verified = similarity >= 0.85  # Strict biometric threshold
        return {
            "verified": is_verified,
            "speaker_name": "Ashrit (Primary Owner)" if is_verified else "Unknown / Unverified Speaker",
            "confidence": round(max(0.0, min(1.0, similarity)), 4),
            "biometric_match": is_verified,
            "method": "Acoustic Embedding Cosine Distance"
        }

    def detect_face_presence(self, frame_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Detect face presence in camera frame using OpenCV Haar Cascade.
        NOTE: Haar Cascade detects face presence/location only, NOT identity recognition.
        Returns presence status and face count without claiming owner identity verification.
        """
        if not frame_bytes:
            return {
                "detected": False,
                "verified": False,
                "confidence": 0.0,
                "faces_detected": 0,
                "method": "OpenCV Haar Cascade Presence Detection",
                "reason": "No video frame provided for analysis."
            }

        try:
            import cv2
            import numpy as np
            nparr = np.frombuffer(frame_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return {
                    "detected": False,
                    "verified": False,
                    "confidence": 0.0,
                    "faces_detected": 0,
                    "method": "OpenCV Haar Cascade Presence Detection",
                    "reason": "Failed to decode camera frame bytes."
                }

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            face_cascade = cv2.CascadeClassifier(cascade_path)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

            num_faces = len(faces)
            has_face = num_faces >= 1
            conf = min(0.98, 0.75 + (num_faces * 0.05)) if has_face else 0.0

            return {
                "detected": has_face,
                "verified": False,  # Explicitly False: Haar Cascade does not verify identity
                "confidence": round(conf, 2),
                "faces_detected": num_faces,
                "method": "OpenCV Haar Cascade Presence Detection",
                "note": "Presence detection only. Facial identity verification requires DeepFace/dlib enrollment."
            }
        except Exception as e:
            logger.error("Facial presence detection failed: {}", e)
            return {
                "detected": False,
                "verified": False,
                "confidence": 0.0,
                "faces_detected": 0,
                "method": "OpenCV Haar Cascade Presence Detection",
                "error": str(e)
            }

    def verify_face_biometrics(self, frame_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        """Delegate face biometric verification to FaceBiometricsService 128-d embedding engine."""
        try:
            from backend.services.face_biometrics import FaceBiometricsService
            face_bio = FaceBiometricsService()
            return face_bio.verify_face_identity(frame_bytes)
        except Exception as e:
            return self.detect_face_presence(frame_bytes)

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
