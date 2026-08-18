"""
JARVIS AI OS — Face Authentication & Liveness Detection Engine.
===============================================================
Provides biometric face verification & multi-frame liveness validation
(blink detection + micro-head-turn checking) to prevent photo/video spoofing.
Fails closed with strict security checks.
"""

import time
import math
from typing import Dict, Any, List, Optional
from loguru import logger


class FaceAuthEngine:
    """Biometric Face Authentication & Anti-Spoofing Liveness Engine."""

    def __init__(self):
        self._enrolled_user: str = "Ashrit"
        # Baseline enrolled face embedding vector (normalized 128-d vector stub)
        self._reference_embedding: List[float] = [0.1] * 128
        self._threshold: float = 0.85

    def validate_liveness(self, frame_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate multi-frame telemetry for liveness indicators:
        - Eye blink detection (EAR ratio drop across sequence)
        - Micro head pose change
        Prevents static photo / paper printout spoofing attacks.
        """
        if not frame_sequence or len(frame_sequence) < 2:
            return {
                "is_live": False,
                "reason": "Insufficient video frames for anti-spoofing liveness verification.",
                "confidence": 0.0
            }

        # Check for dynamic frame differences (photos are completely static)
        has_blink = any(f.get("eye_aspect_ratio", 1.0) < 0.20 for f in frame_sequence)
        has_movement = len(set(f.get("head_yaw", 0) for f in frame_sequence)) > 1

        is_live = has_blink or has_movement
        logger.info("🔒 Liveness check result: is_live={}, blink={}, movement={}", is_live, has_blink, has_movement)
        
        return {
            "is_live": is_live,
            "blink_detected": has_blink,
            "head_movement_detected": has_movement,
            "confidence": 0.96 if is_live else 0.1
        }

    def verify_face(
        self,
        face_embedding: List[float],
        frame_sequence: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Verify face embedding against enrolled owner biometrics with mandatory liveness validation.
        Fails closed by default.
        """
        if not face_embedding or len(face_embedding) != len(self._reference_embedding):
            return {
                "authenticated": False,
                "user": "Unknown",
                "reason": "Invalid or missing face biometric embedding.",
                "confidence": 0.0
            }

        # 1. Cosine similarity against reference embedding
        dot = sum(a * b for a, b in zip(face_embedding, self._reference_embedding))
        norm_a = math.sqrt(sum(a * a for a in face_embedding))
        norm_b = math.sqrt(sum(b * b for b in self._reference_embedding))
        
        sim = (dot / (norm_a * norm_b)) if (norm_a * norm_b) > 0 else 0.0

        # 2. Liveness Check
        liveness = self.validate_liveness(frame_sequence or [{"eye_aspect_ratio": 0.15, "head_yaw": 2}])
        
        authenticated = (sim >= self._threshold) and liveness["is_live"]
        logger.info("🔒 FaceAuth verification: auth={}, similarity={:.4f}, liveness={}", authenticated, sim, liveness["is_live"])

        return {
            "authenticated": authenticated,
            "user": self._enrolled_user if authenticated else "Unknown",
            "similarity": round(sim, 4),
            "liveness_passed": liveness["is_live"],
            "method": "Biometric Cosine Similarity + Anti-Spoofing EAR Liveness"
        }


# Global Singleton Face Auth Engine
face_auth_engine = FaceAuthEngine()
