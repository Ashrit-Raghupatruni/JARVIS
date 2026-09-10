"""
JARVIS AI OS — Video Generation Service (Cloud API Adapter).

Video generation requires heavy compute (24-80GB VRAM) and is dispatched via
external cloud provider APIs (Replicate SVD/CogVideoX, Runway, Luma) through the
Asynchronous Generation Queue with strict fail-closed resource checks.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger
from backend.services.async_generation_queue import generation_queue


class VideoGeneratorService:
    """Service for Text-to-Video and Image-to-Video synthesis."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or Path("data/media_output/videos")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("VideoGeneratorService initialized. Output dir: {}", self.output_dir)

    def check_capabilities(self) -> Dict[str, Any]:
        """Check for active video API keys (Replicate / Runway / Luma / Stability)."""
        replicate_key = bool(os.getenv("REPLICATE_API_TOKEN", "").strip())
        runway_key = bool(os.getenv("RUNWAY_API_SECRET", "").strip())
        luma_key = bool(os.getenv("LUMA_API_KEY", "").strip())

        providers = []
        if replicate_key:
            providers.append("Replicate (CogVideoX/SVD)")
        if runway_key:
            providers.append("Runway Gen-3")
        if luma_key:
            providers.append("Luma Dream Machine")

        return {
            "has_video_api": len(providers) > 0,
            "configured_providers": providers,
            "is_local_gpu_feasible": False,
            "hardware_note": "Local video generation requires >=24GB VRAM and is redirected to cloud workers."
        }

    def generate_video(
        self,
        prompt: str,
        duration_seconds: int = 5,
        fps: int = 24,
        aspect_ratio: str = "16:9"
    ) -> Dict[str, Any]:
        """
        Submit a video generation job to the Async Queue with fail-closed key validation.
        """
        caps = self.check_capabilities()
        if not caps["has_video_api"]:
            return {
                "status": "error",
                "error_code": "RESOURCE_UNAVAILABLE",
                "message": (
                    "Video generation is not feasible on local consumer hardware (requires >=24GB VRAM). "
                    "An active cloud API key (REPLICATE_API_TOKEN, RUNWAY_API_SECRET, or LUMA_API_KEY) must be configured in settings."
                ),
                "capabilities": caps
            }

        receipt = generation_queue.submit_job(
            "video_generation",
            prompt,
            {"duration_seconds": duration_seconds, "fps": fps, "aspect_ratio": aspect_ratio}
        )
        return receipt


video_generator = VideoGeneratorService()
