"""
Multimodal Generation Skill for FastMCP & Skill Registry integration.
Exposes tools: image synthesis, video generation, procedural 3D scenes,
neural 3D meshes, and async generation job queue management.
"""

from typing import Any, Dict, List, Optional
from backend.services.skills.base import BaseSkill
from backend.services.image_generator import image_generator
from backend.services.video_generator import video_generator
from backend.services.threed_generator import threed_generator
from backend.services.async_generation_queue import generation_queue


class MultimodalSkill(BaseSkill):
    """Skill exposing Multimodal Synthesis & Generative Media tools."""

    name = "MultimodalSkill"
    description = "Text-to-Image synthesis, Video generation queue, Three.js 3D scene builder, Neural 3D mesh generator, and generation job tracking."

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "generate_image",
                "description": "Generate an image from prompt using DALL-E 3, Stability AI, or local CUDA diffusion.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Text description of the image to generate."},
                        "resolution": {"type": "string", "enum": ["512x512", "1024x1024", "1920x1080"]},
                        "style": {"type": "string", "enum": ["vivid", "natural", "cinematic", "cyberpunk"]},
                        "async_mode": {"type": "boolean", "description": "Whether to return immediately with an async tracking job ID."}
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "check_image_generation_capabilities",
                "description": "Inspect available local GPU VRAM and configured cloud generation providers.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "generate_video",
                "description": "Submit a text-to-video generation job to the async queue (requires cloud video API key).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Video action and scene description."},
                        "duration_seconds": {"type": "integer", "description": "Duration in seconds (e.g. 5)."}
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "generate_procedural_3d_scene",
                "description": "Generate interactive Three.js WebGL 3D scene code for holograms, orbs, and HUD elements.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "scene_type": {"type": "string", "enum": ["hud_orb", "particle_grid", "holographic_cube", "neural_network"]},
                        "theme": {"type": "string", "description": "Visual theme preset (e.g. 'cyan_hologram', 'matrix_green')."}
                    }
                }
            },
            {
                "name": "generate_neural_3d_mesh",
                "description": "Submit a text-to-3D GLTF/GLB mesh generation job to the cloud queue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Description of the 3D object to model."},
                        "target_format": {"type": "string", "enum": ["glb", "gltf", "obj"]}
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "get_generation_job_status",
                "description": "Check status, progress (0-100%), and file output path for an async generation job ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "UUID token returned when job was submitted."}
                    },
                    "required": ["job_id"]
                }
            },
            {
                "name": "list_generation_jobs",
                "description": "List recent async multimodal generation tasks and their completion states.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max number of jobs to retrieve."}
                    }
                }
            }
        ]

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        if tool_name == "generate_image":
            return await image_generator.generate_image(
                parameters.get("prompt", ""),
                resolution=parameters.get("resolution", "1024x1024"),
                style=parameters.get("style", "vivid"),
                async_mode=parameters.get("async_mode", False)
            )
        elif tool_name == "check_image_generation_capabilities":
            return image_generator.check_capabilities()
        elif tool_name == "generate_video":
            return video_generator.generate_video(
                parameters.get("prompt", ""),
                duration_seconds=parameters.get("duration_seconds", 5)
            )
        elif tool_name == "generate_procedural_3d_scene":
            return threed_generator.generate_procedural_3d_scene(
                scene_type=parameters.get("scene_type", "hud_orb"),
                theme=parameters.get("theme", "cyan_hologram")
            )
        elif tool_name == "generate_neural_3d_mesh":
            return threed_generator.generate_neural_3d_mesh(
                parameters.get("prompt", ""),
                target_format=parameters.get("target_format", "glb")
            )
        elif tool_name == "get_generation_job_status":
            return generation_queue.get_job_status(parameters.get("job_id", ""))
        elif tool_name == "list_generation_jobs":
            return generation_queue.list_jobs(limit=parameters.get("limit", 20))
        else:
            raise ValueError(f"Unknown multimodal tool: {tool_name}")
