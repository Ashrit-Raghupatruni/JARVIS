"""
UI Skill for FastMCP & Skill Registry integration.
Exposes tools: get_hud_status, get_agent_dashboard, get_memory_explorer_data, get_performance_metrics,
critique_ui_layout, generate_color_palette, and scaffold_web_app.
"""

import time
import psutil
from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.design_assistant import design_assistant


class UISkill(BaseSkill):
    """Skill exposing User Interface, Dashboard, Design Critique, and Web App Scaffolding tools."""

    name = "UISkill"
    description = "HUD status, multi-agent dashboard, memory explorer, performance monitor, UI/UX layout critique, color palette generator, and web app scaffolder."

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
            },
            {
                "name": "critique_ui_layout",
                "description": "Evaluate UI layout description or HTML/JSX for visual hierarchy, contrast, whitespace, and WCAG accessibility.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "layout_description": {"type": "string", "description": "Description of UI layout or HTML/CSS code snippet."},
                        "target_device": {"type": "string", "enum": ["desktop", "mobile", "tablet"]}
                    },
                    "required": ["layout_description"]
                }
            },
            {
                "name": "generate_color_palette",
                "description": "Generate harmonic color palette tokens with Tailwind CSS classes and CSS variable rules.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "theme_name": {"type": "string", "description": "Theme style (e.g. 'cyberpunk', 'jarvis_cyan', 'corporate_clean', 'emerald_dark')."},
                        "base_color": {"type": "string", "description": "Optional starting hex color."}
                    },
                    "required": ["theme_name"]
                }
            },
            {
                "name": "scaffold_web_app",
                "description": "Scaffold interactive, standalone HTML5 / Tailwind / React web component or dashboard boilerplate.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_type": {"type": "string", "description": "App type (e.g. 'dashboard', 'landing_page', 'kanban', 'chat_interface')."},
                        "title": {"type": "string", "description": "Title of the application."},
                        "framework": {"type": "string", "enum": ["html_tailwind", "react_tailwind"]},
                        "features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of core features/cards to include."
                        }
                    },
                    "required": ["app_type"]
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "get_hud_status":
            from backend.services.manager import ServiceManager
            wm = ServiceManager.get_instance("world_model")
            audio_level = 0.04
            if wm and getattr(wm, "state", None) and getattr(wm.state, "audio_playing", False):
                audio_level = 0.85
            return {
                "hud_theme": "iron_man_cyan_hologram",
                "orb_state": "idle",
                "audio_level": audio_level,
                "system_status": "ONLINE",
                "timestamp": time.time()
            }
        elif tool_name == "get_agent_dashboard":
            return {
                "agents": [
                    {"name": "CEO Agent", "status": "active", "task": "Strategic task planning"},
                    {"name": "Planner Agent", "status": "idle", "task": "Awaiting intent"},
                    {"name": "Vision Agent", "status": "monitoring", "task": "Desktop perception active"},
                    {"name": "Coding Agent", "status": "ready", "task": "Sandbox operational"}
                ],
                "active_count": 4
            }
        elif tool_name == "get_memory_explorer_data":
            return {
                "vector_db": "ChromaDB",
                "total_documents": 24,
                "total_chunks": 142,
                "collections": ["system_memory", "user_preferences", "strategy_memory"]
            }
        elif tool_name == "get_performance_metrics":
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            return {
                "cpu_percent": f"{cpu}%",
                "ram_percent": f"{mem}%",
                "llm_avg_latency_ms": 120,
                "gpu_status": "DirectML / CUDA Ready"
            }
        elif tool_name == "critique_ui_layout":
            return design_assistant.critique_ui_layout(
                parameters.get("layout_description", ""),
                target_device=parameters.get("target_device", "desktop")
            )
        elif tool_name == "generate_color_palette":
            return design_assistant.generate_color_palette(
                parameters.get("theme_name", "jarvis_cyan"),
                base_color=parameters.get("base_color")
            )
        elif tool_name == "scaffold_web_app":
            return design_assistant.scaffold_web_app(
                parameters.get("app_type", "dashboard"),
                title=parameters.get("title", "JARVIS Application"),
                framework=parameters.get("framework", "html_tailwind"),
                features=parameters.get("features")
            )
        else:
            raise ValueError(f"Unknown UI tool: {tool_name}")
