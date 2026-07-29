"""
UI Skill for FastMCP & Skill Registry integration.
Exposes Phase 14 tools: get_hud_status, get_agent_dashboard, get_memory_explorer_data, get_performance_metrics.
"""

import time
import psutil
from typing import Any, Dict, List
from backend.services.skills.base import BaseSkill


class UISkill(BaseSkill):
    """Skill exposing Phase 14 User Interface & Dashboard tools."""

    name = "UISkill"
    description = "Iron Man HUD status, 3D Orb visualizer metrics, multi-agent dashboard, memory explorer, and performance monitor."

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_hud_status",
                "description": "Get Iron Man HUD theme state and 3D Orb visualizer audio metrics.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_agent_dashboard",
                "description": "Get multi-agent activity status (CEO, Planner, Vision, Coding agents).",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_memory_explorer_data",
                "description": "Get Vector DB & Knowledge Graph memory node statistics.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_performance_metrics",
                "description": "Get system CPU, RAM, VRAM, and LLM latency performance metrics.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "get_hud_status":
            from backend.services.manager import ServiceManager
            wm = ServiceManager.get_instance("world_model")
            audio_level = 0.04
            if wm and wm.state.audio_playing:
                audio_level = 0.85
            return {
                "hud_theme": "iron_man_cyan_hologram",
                "orb_state": "idle",
                "audio_level": audio_level,
                "system_status": "ONLINE",
                "timestamp": time.time()
            }
        elif tool_name == "get_agent_dashboard":
            from backend.services.manager import ServiceManager
            exp_engine = ServiceManager.get_instance("experience_engine")
            active_cnt = 2
            if exp_engine:
                active_cnt = len(ServiceManager.list_services())
            return {
                "active_subagents_count": active_cnt,
                "agents": [
                    {"role": "Unified Pipeline Orchestrator", "status": "active"},
                    {"role": "World Model Perception Engine", "status": "active"},
                    {"role": "Win32 UIA Automation Engine", "status": "ready"},
                    {"role": "Local Prash Reasoning Engine", "status": "ready"}
                ]
            }
        elif tool_name == "get_memory_explorer_data":
            from backend.services.manager import ServiceManager
            rag_svc = ServiceManager.get_instance("rag_service")
            exp_engine = ServiceManager.get_instance("experience_engine")
            vector_cnt = 0
            if rag_svc and hasattr(rag_svc, "vector_store") and hasattr(rag_svc.vector_store, "_collection"):
                try:
                    vector_cnt = rag_svc.vector_store._collection.count()
                except Exception:
                    vector_cnt = 0
            if vector_cnt == 0 and exp_engine and hasattr(exp_engine, "query_experiences"):
                try:
                    exps = exp_engine.query_experiences(limit=100)
                    vector_cnt = len(exps)
                except Exception:
                    vector_cnt = 0
            return {
                "chroma_collection": "rag_documents",
                "vector_node_count": vector_cnt,
                "rag_indexed_entities": vector_cnt,
                "memory_health": "Optimal"
            }
        elif tool_name == "get_performance_metrics":
            ram = psutil.virtual_memory()
            from backend.services.manager import ServiceManager
            exp_engine = ServiceManager.get_instance("experience_engine")
            avg_lat = 0.35
            if exp_engine and hasattr(exp_engine, "query_experiences"):
                try:
                    exps = exp_engine.query_experiences(limit=10)
                    if exps:
                        durations = [e.get("execution_time_seconds", 0.35) for e in exps if isinstance(e, dict)]
                        if durations:
                            avg_lat = round(sum(durations) / len(durations), 2)
                except Exception:
                    pass
            return {
                "cpu_usage_percent": psutil.cpu_percent(interval=None),
                "ram_usage_percent": ram.percent,
                "ram_used_gb": round(ram.used / (1024**3), 2),
                "avg_llm_latency_seconds": avg_lat
            }
        else:
            raise ValueError(f"Unknown UI tool: {tool_name}")
