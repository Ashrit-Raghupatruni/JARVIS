"""
Observability Skill for FastMCP & Skill Registry integration.
Exposes Phase 15 tools: get_cache_stats, get_gpu_vram_status, get_system_health, export_telemetry_metrics.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.redis_cache import RedisCacheService
from backend.services.gpu_scheduler import GPUSchedulerService
from backend.services.observability import ObservabilityService


class ObservabilitySkill(BaseSkill):
    """Skill exposing Phase 15 Observability tools."""

    name = "ObservabilitySkill"
    description = "Redis caching metrics, GPU VRAM scheduler status, system health diagnostics, telemetry traces."

    def __init__(
        self,
        cache_service: Optional[RedisCacheService] = None,
        gpu_service: Optional[GPUSchedulerService] = None,
        obs_service: Optional[ObservabilityService] = None
    ):
        self.cache_service = cache_service or RedisCacheService()
        self.gpu_service = gpu_service or GPUSchedulerService()
        self.obs_service = obs_service or ObservabilityService()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_cache_stats",
                "description": "Get dual-layer cache hit ratio, memory usage, and Redis status.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_gpu_vram_status",
                "description": "Get CUDA GPU VRAM usage and lazy model load allocations.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_system_health",
                "description": "Get hardware CPU/RAM health, crash reports count, and active trace IDs.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "export_telemetry_metrics",
                "description": "Export aggregated telemetry metrics for diagnostics.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "get_cache_stats":
            return self.cache_service.get_stats()
        elif tool_name == "get_gpu_vram_status":
            return self.gpu_service.get_vram_status()
        elif tool_name == "get_system_health":
            return self.obs_service.get_system_health()
        elif tool_name == "export_telemetry_metrics":
            return {
                "cache": self.cache_service.get_stats(),
                "gpu": self.gpu_service.get_vram_status(),
                "health": self.obs_service.get_system_health()
            }
        else:
            raise ValueError(f"Unknown observability tool: {tool_name}")
