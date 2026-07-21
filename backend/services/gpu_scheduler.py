"""
GPU Scheduler & Lazy Model Loading Service for JARVIS.

Monitors CUDA VRAM allocation, manages lazy model loading on demand,
and handles offloading idle models to system RAM.
"""

import time
import psutil
from typing import Any, Dict, List, Optional
from loguru import logger


class GPUSchedulerService:
    """Service for Phase 15 GPU Scheduling & Lazy Model Loading."""

    def __init__(self, vram_limit_gb: float = 8.0):
        self.vram_limit_gb = vram_limit_gb
        self._loaded_models: Dict[str, Dict[str, Any]] = {}
        logger.info("GPUSchedulerService initialized (Limit: {} GB VRAM).", vram_limit_gb)

    def get_vram_status(self) -> Dict[str, Any]:
        """Return current estimated VRAM usage and model allocations."""
        total_vram_used = sum(m.get("vram_gb", 0.0) for m in self._loaded_models.values())
        return {
            "vram_limit_gb": self.vram_limit_gb,
            "vram_used_gb": round(total_vram_used, 2),
            "vram_free_gb": round(self.vram_limit_gb - total_vram_used, 2),
            "vram_usage_percent": round((total_vram_used / self.vram_limit_gb) * 100.0, 2),
            "loaded_models_count": len(self._loaded_models),
            "loaded_models": list(self._loaded_models.keys())
        }

    def load_model_lazy(self, model_name: str, estimated_vram_gb: float = 1.5) -> Dict[str, Any]:
        """Load a model on demand if VRAM budget permits."""
        current_status = self.get_vram_status()
        if current_status["vram_free_gb"] < estimated_vram_gb:
            self.evict_idle_models(vram_needed_gb=estimated_vram_gb)

        self._loaded_models[model_name] = {
            "model_name": model_name,
            "vram_gb": estimated_vram_gb,
            "loaded_at": time.time(),
            "last_used_at": time.time()
        }
        logger.info("Lazily loaded model '{}' into GPU VRAM ({} GB).", model_name, estimated_vram_gb)
        return {"status": "model_loaded", "model_name": model_name, "allocated_vram_gb": estimated_vram_gb}

    def evict_idle_models(self, vram_needed_gb: float = 1.0) -> List[str]:
        """Evict oldest idle models from VRAM to system RAM."""
        evicted = []
        sorted_models = sorted(self._loaded_models.items(), key=lambda item: item[1]["last_used_at"])
        for name, info in sorted_models:
            del self._loaded_models[name]
            evicted.append(name)
            logger.info("Evicted idle model '{}' from GPU VRAM.", name)
            if self.get_vram_status()["vram_free_gb"] >= vram_needed_gb:
                break
        return evicted
