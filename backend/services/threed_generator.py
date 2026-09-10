"""
JARVIS AI OS — 3D Asset & Scene Generation Service.

Provides:
1. Procedural 3D Scene / GLTF Generator (Three.js code snippets & procedural geometry meshes)
2. Cloud API 3D Mesh Generator Adapter (Meshy / Tripo3D) with fail-closed key validation.
"""

from __future__ import annotations

import os
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger
from backend.services.async_generation_queue import generation_queue


class ThreeDGeneratorService:
    """Service for Text/Image-to-3D Mesh and Procedural Scene Generation."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or Path("data/media_output/3d")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("ThreeDGeneratorService initialized. Output dir: {}", self.output_dir)

    def check_capabilities(self) -> Dict[str, Any]:
        """Check for active 3D API keys (Meshy / Tripo3D)."""
        meshy_key = bool(os.getenv("MESHY_API_KEY", "").strip())
        tripo_key = bool(os.getenv("TRIPO3D_API_KEY", "").strip())

        providers = []
        if meshy_key:
            providers.append("Meshy AI")
        if tripo_key:
            providers.append("Tripo3D")

        return {
            "has_neural_3d_api": len(providers) > 0,
            "configured_providers": providers,
            "has_procedural_3d": True,
            "hardware_note": "Deep neural text-to-3D mesh generation requires cloud APIs; procedural Three.js/GLTF is supported locally."
        }

    def generate_procedural_3d_scene(
        self,
        scene_type: str = "hud_orb",
        theme: str = "cyan_hologram"
    ) -> Dict[str, Any]:
        """
        Generate standalone Three.js procedural 3D scene code and metadata.
        """
        code = f"""// Three.js Procedural {scene_type.title()} Scene
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
renderer.setSize(window.innerWidth, window.innerHeight);

// Procedural Hologram Geometry
const geometry = new THREE.IcosahedronGeometry(2, 4);
const material = new THREE.MeshStandardMaterial({{
  color: 0x00e5ff,
  wireframe: true,
  emissive: 0x00e5ff,
  emissiveIntensity: 0.8
}});
const orb = new THREE.Mesh(geometry, material);
scene.add(orb);

camera.position.z = 5;
function animate() {{
  requestAnimationFrame(animate);
  orb.rotation.x += 0.005;
  orb.rotation.y += 0.01;
  renderer.render(scene, camera);
}}
animate();"""

        return {
            "status": "success",
            "scene_type": scene_type,
            "theme": theme,
            "framework": "Three.js / WebGL",
            "generated_code": code
        }

    def generate_neural_3d_mesh(
        self,
        prompt: str,
        target_format: str = "glb"
    ) -> Dict[str, Any]:
        """
        Submit neural text-to-3D mesh job to the Async Queue with fail-closed key validation.
        """
        caps = self.check_capabilities()
        if not caps["has_neural_3d_api"]:
            return {
                "status": "error",
                "error_code": "RESOURCE_UNAVAILABLE",
                "message": (
                    "Neural 3D mesh generation requires an active Meshy (MESHY_API_KEY) or Tripo3D (TRIPO3D_API_KEY) API key. "
                    "You can use procedural 3D generation locally via generate_procedural_3d_scene."
                ),
                "capabilities": caps
            }

        receipt = generation_queue.submit_job(
            "threed_mesh_generation",
            prompt,
            {"target_format": target_format}
        )
        return receipt


threed_generator = ThreeDGeneratorService()
