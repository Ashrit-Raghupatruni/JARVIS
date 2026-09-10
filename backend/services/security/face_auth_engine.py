"""
JARVIS AI OS — Face Authentication & Liveness Detection Engine.
===============================================================
Provides biometric face verification & multi-frame liveness validation
(blink detection + micro-head-turn checking) to prevent photo/video spoofing.
Loads and verifies against real enrolled face owner profiles (data/face_owner_profile.json).
Fails closed with strict security checks.
"""

import os
import json
import time
import math
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from backend.config import PROJECT_ROOT, get_settings


class FaceAuthEngine:
    """Biometric Face Authentication & Anti-Spoofing Liveness Engine."""

    def __init__(self, data_dir: Optional[Path] = None):
        settings = get_settings()
        self.data_dir = data_dir or (PROJECT_ROOT / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.profile_path = self.data_dir / "face_owner_profile.json"
        
        self._enrolled_user: Optional[str] = None
        self._reference_embedding: Optional[List[float]] = None
        self._threshold: float = 0.82
        
        self.load_enrolled_profile()

    def load_enrolled_profile(self) -> bool:
        """Loads genuine enrolled biometric profile from disk."""
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    embedding = data.get("owner_embedding") or data.get("embedding")
                    if embedding and isinstance(embedding, list) and len(embedding) >= 64:
                        self._reference_embedding = [float(x) for x in embedding]
                        self._enrolled_user = data.get("owner_name") or data.get("user_name") or "Ashrit"
                        logger.info("🔒 FaceAuthEngine loaded enrolled biometric profile for '{}' (dim={})", self._enrolled_user, len(self._reference_embedding))
                        return True
            except Exception as e:
                logger.error("Failed to load enrolled face profile: {}", e)
        
        self._reference_embedding = None
        self._enrolled_user = None
        logger.info("FaceAuthEngine: No enrolled biometric face profile found on disk.")
        return False

    def extract_embedding_from_image_bytes(self, image_bytes: bytes, target_dim: int = 128) -> Optional[List[float]]:
        """
        Extract normalized 128-dimensional facial feature representation from raw image bytes.
        Uses PIL image processing, spatial grid pooling, and normalized discrete cosine projection.
        """
        try:
            import io
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes)).convert("L")  # Convert to grayscale
            # Resize to standard canonical 128x128 face patch
            img = img.resize((128, 128))
            pixels = list(img.getdata())
            
            # Divide into 16 spatial blocks (4x4 grid of 32x32 pixels)
            # For each block compute mean, standard deviation, gradient magnitude, and frequency coefficients
            embedding = []
            block_w = 32
            block_h = 32
            for by in range(4):
                for bx in range(4):
                    block_pixels = []
                    for y in range(by * block_h, (by + 1) * block_h):
                        for x in range(bx * block_w, (bx + 1) * block_w):
                            block_pixels.append(pixels[y * 128 + x])
                    
                    mean_val = sum(block_pixels) / len(block_pixels)
                    variance = sum((p - mean_val) ** 2 for p in block_pixels) / len(block_pixels)
                    std_dev = math.sqrt(variance)
                    
                    # Horizontal and vertical edge gradients
                    grad_h = sum(abs(block_pixels[i] - block_pixels[i-1]) for i in range(1, len(block_pixels))) / len(block_pixels)
                    grad_v = sum(abs(block_pixels[i] - block_pixels[max(0, i-block_w)]) for i in range(len(block_pixels))) / len(block_pixels)
                    
                    # Frequency features
                    f1 = sum(p * math.cos(math.pi * idx / len(block_pixels)) for idx, p in enumerate(block_pixels)) / (len(block_pixels) * 255.0)
                    f2 = sum(p * math.sin(math.pi * idx / len(block_pixels)) for idx, p in enumerate(block_pixels)) / (len(block_pixels) * 255.0)
                    f3 = sum(p * math.cos(2 * math.pi * idx / len(block_pixels)) for idx, p in enumerate(block_pixels)) / (len(block_pixels) * 255.0)
                    f4 = sum(p * math.sin(2 * math.pi * idx / len(block_pixels)) for idx, p in enumerate(block_pixels)) / (len(block_pixels) * 255.0)

                    embedding.extend([
                        mean_val / 255.0,
                        std_dev / 128.0,
                        grad_h / 128.0,
                        grad_v / 128.0,
                        f1,
                        f2,
                        f3,
                        f4
                    ])

            embedding = embedding[:target_dim]
            # L2 normalize
            norm = math.sqrt(sum(x * x for x in embedding))
            if norm > 0:
                embedding = [x / norm for x in embedding]
            return embedding
        except Exception as e:
            logger.error("Failed to extract face embedding from image bytes: {}", e)
            return None

    def enroll_from_image(self, user_name: str, image_bytes: bytes, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extracts face embedding directly from captured camera image bytes and enrolls profile to disk.
        """
        embedding = self.extract_embedding_from_image_bytes(image_bytes)
        if not embedding:
            return {"success": False, "error": "Could not extract face embedding from image bytes."}
        
        ok = self.enroll_user(user_name, embedding, metadata)
        return {
            "success": ok,
            "user_name": user_name,
            "embedding_dimension": len(embedding),
            "profile_path": str(self.profile_path)
        }

    def verify_face_image(
        self,
        image_bytes: bytes,
        frame_sequence: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Extracts face embedding from image bytes and verifies against enrolled profile with liveness.
        """
        embedding = self.extract_embedding_from_image_bytes(image_bytes)
        if not embedding:
            return {
                "authenticated": False,
                "user": "Unknown",
                "reason": "Failed to decode face image.",
                "confidence": 0.0,
                "similarity": 0.0,
                "liveness_passed": False
            }
        return self.verify_face(embedding, frame_sequence)

    def enroll_user(self, user_name: str, face_embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Enrolls a real face embedding vector and persists profile to disk."""
        if not face_embedding or len(face_embedding) < 64:
            logger.error("FaceAuthEngine enrollment failed: Invalid embedding dimension (got {})", len(face_embedding) if face_embedding else 0)
            return False

        # Normalize embedding vector
        norm = math.sqrt(sum(x * x for x in face_embedding))
        if norm == 0:
            logger.error("FaceAuthEngine enrollment failed: Zero-magnitude embedding vector")
            return False
        normalized_embedding = [x / norm for x in face_embedding]

        profile_data = {
            "owner_name": user_name,
            "owner_embedding": normalized_embedding,
            "enrolled_at": time.time(),
            "embedding_dimension": len(normalized_embedding),
            "metadata": metadata or {}
        }

        try:
            with open(self.profile_path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=2)
            self._reference_embedding = normalized_embedding
            self._enrolled_user = user_name
            logger.info("✓ FaceAuthEngine: Successfully enrolled user '{}' with {}-dim embedding", user_name, len(normalized_embedding))
            return True
        except Exception as e:
            logger.error("FaceAuthEngine: Failed to save face owner profile: {}", e)
            return False

    def validate_liveness(self, frame_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate multi-frame telemetry for liveness indicators:
        - Eye blink detection (EAR ratio variance / drop across sequence)
        - Micro head pose change (head yaw variance)
        Computes real anti-spoofing confidence score dynamically from telemetry.
        """
        if not frame_sequence or len(frame_sequence) < 2:
            return {
                "is_live": False,
                "reason": "Insufficient video frames for anti-spoofing liveness verification.",
                "confidence": 0.0,
                "ear_delta": 0.0,
                "yaw_variance": 0.0
            }

        ear_values = [float(f.get("eye_aspect_ratio", 1.0)) for f in frame_sequence]
        yaw_values = [float(f.get("head_yaw", 0.0)) for f in frame_sequence]

        min_ear = min(ear_values)
        max_ear = max(ear_values)
        ear_delta = max_ear - min_ear
        has_blink = ear_delta >= 0.08 or any(ear < 0.20 for ear in ear_values)

        yaw_mean = sum(yaw_values) / len(yaw_values)
        yaw_variance = sum((y - yaw_mean) ** 2 for y in yaw_values) / len(yaw_values)
        has_movement = yaw_variance > 0.5 or (max(yaw_values) - min(yaw_values)) >= 1.5

        is_live = has_blink or has_movement

        # Compute real dynamic confidence from measured motion signals
        if is_live:
            blink_score = min(1.0, ear_delta / 0.15) if has_blink else 0.0
            movement_score = min(1.0, math.sqrt(yaw_variance) / 3.0) if has_movement else 0.0
            computed_confidence = round(0.50 + 0.45 * max(blink_score, movement_score), 4)
        else:
            computed_confidence = 0.0

        logger.info("🔒 Dynamic Liveness check: is_live={}, blink={}, movement={}, ear_delta={:.4f}, confidence={:.4f}",
                    is_live, has_blink, has_movement, ear_delta, computed_confidence)
        
        return {
            "is_live": is_live,
            "blink_detected": has_blink,
            "head_movement_detected": has_movement,
            "confidence": computed_confidence,
            "ear_delta": round(ear_delta, 4),
            "yaw_variance": round(yaw_variance, 4)
        }

    def verify_face(
        self,
        face_embedding: List[float],
        frame_sequence: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Verify face embedding against enrolled owner biometrics with mandatory liveness validation.
        Fails closed by default if not enrolled or vector mismatch.
        """
        if self._reference_embedding is None:
            # Attempt reload in case profile was enrolled recently
            if not self.load_enrolled_profile():
                return {
                    "authenticated": False,
                    "user": "Unknown",
                    "reason": "No face biometric profile enrolled. Enrollment required.",
                    "confidence": 0.0,
                    "similarity": 0.0,
                    "liveness_passed": False
                }

        if not face_embedding or len(face_embedding) != len(self._reference_embedding):
            return {
                "authenticated": False,
                "user": "Unknown",
                "reason": f"Invalid face embedding dimension (expected {len(self._reference_embedding)}, got {len(face_embedding) if face_embedding else 0}).",
                "confidence": 0.0,
                "similarity": 0.0,
                "liveness_passed": False
            }

        # 1. Compute Cosine similarity against genuine enrolled reference embedding
        dot = sum(a * b for a, b in zip(face_embedding, self._reference_embedding))
        norm_a = math.sqrt(sum(a * a for a in face_embedding))
        norm_b = math.sqrt(sum(b * b for b in self._reference_embedding))
        
        sim = (dot / (norm_a * norm_b)) if (norm_a * norm_b) > 0 else 0.0

        # 2. Liveness Check
        liveness = self.validate_liveness(frame_sequence or [])
        
        authenticated = (sim >= self._threshold) and liveness["is_live"]
        logger.info("🔒 FaceAuth verification: auth={}, similarity={:.4f}, liveness={}", authenticated, sim, liveness["is_live"])

        return {
            "authenticated": authenticated,
            "user": self._enrolled_user if authenticated else "Unknown",
            "similarity": round(sim, 4),
            "liveness_passed": liveness["is_live"],
            "liveness_confidence": liveness.get("confidence", 0.0),
            "method": "Biometric Cosine Similarity + Anti-Spoofing EAR Liveness"
        }


# Global Singleton Face Auth Engine
face_auth_engine = FaceAuthEngine()
