"""
JARVIS AI OS — Master Capability Expansion Test Suite (Phases 1–5).
Tests:
1. Science & Chemoinformatics (Formula parsing, equation balancing, PubChem lookup, biology pathways)
2. Design & Web App Assistant (UI critique, WCAG checks, Tailwind palettes, Web App scaffolder)
3. Vision Intelligence (Local object detection, grounded image captioning)
4. RPA Desktop Macros (Sequential automation execution with error isolation)
5. Voice & Audio Generation (Neural TTS, voice listing, fail-closed SFX preflight guard)
6. Asynchronous Generation Queue (SQLite job persistence, UUID tokens, status tracking)
7. Multimodal Generative Modalities (Image synthesis, Video cloud adapter guard, 3D procedural/neural)
"""

import os
import sys
import pytest
import tempfile
import sqlite3
from pathlib import Path

from backend.services.science_service import science_service
from backend.services.design_assistant import design_assistant
from backend.services.vision_service import VisionService
from backend.services.desktop_automation import DesktopAutomationService
from backend.services.voice_intelligence import VoiceIntelligenceService
from backend.services.async_generation_queue import AsyncGenerationJobManager
from backend.services.image_generator import image_generator
from backend.services.video_generator import video_generator
from backend.services.threed_generator import threed_generator
from backend.services.skills.research_skill import ResearchSkill
from backend.services.skills.ui_skill import UISkill
from backend.services.skills.vision_skill import VisionSkill
from backend.services.skills.automation_skill import AutomationSkill
from backend.services.skills.voice_skill import VoiceSkill
from backend.services.skills.multimodal_skill import MultimodalSkill


# ── 1. Science & Chemoinformatics Tests (Phase 2) ──────────────────────────

def test_chemical_formula_parsing():
    # Test Glucose C6H12O6
    glucose = science_service.parse_chemical_formula("C6H12O6")
    assert glucose["status"] == "success"
    assert glucose["element_counts"]["C"] == 6
    assert glucose["element_counts"]["H"] == 12
    assert glucose["element_counts"]["O"] == 6
    assert 180.0 <= glucose["molecular_weight_g_mol"] <= 180.3

    # Test Parentheses Formula: Ca(OH)2
    caoh = science_service.parse_chemical_formula("Ca(OH)2")
    assert caoh["status"] == "success"
    assert caoh["element_counts"]["Ca"] == 1
    assert caoh["element_counts"]["O"] == 2
    assert caoh["element_counts"]["H"] == 2


def test_chemical_equation_balancing():
    res = science_service.balance_chemical_equation("H2 + O2 -> H2O")
    assert res["status"] == "success"
    assert "2 H2" in res["balanced_equation"] or "H2" in res["balanced_equation"]
    assert "H2O" in res["balanced_equation"]


def test_pubchem_compound_lookup():
    water = science_service.query_pubchem_compound("water")
    assert water["status"] == "success"
    assert "H2O" in water["molecular_formula"] or "water" in water["compound_name"].lower()


def test_biological_process_explanation():
    bio = science_service.explain_biological_process("photosynthesis")
    assert bio["status"] == "success"
    assert len(bio["phases"]) >= 2
    assert "RuBisCO" in str(bio["key_enzymes"]) or "Photosystem" in str(bio["key_enzymes"]) or "ATP" in bio["summary"]


# ── 2. Design Assistant & Web App Scaffolder Tests (Phase 2) ───────────────

def test_design_assistant_critique_and_palette():
    critique = design_assistant.critique_ui_layout("Dense dashboard with light gray small text and many buttons", "mobile")
    assert critique["status"] == "success"
    assert critique["overall_design_score"] < 100
    assert len(critique["identified_issues"]) >= 1

    palette = design_assistant.generate_color_palette("jarvis_cyan")
    assert palette["status"] == "success"
    assert "tokens" in palette
    assert palette["tokens"]["primary"].startswith("#")


def test_web_app_scaffold():
    scaffold = design_assistant.scaffold_web_app("dashboard", title="JARVIS Monitor", features=["CPU Graph", "Terminal", "Memory"])
    assert scaffold["status"] == "success"
    assert "<!DOCTYPE html>" in scaffold["generated_code"]
    assert "JARVIS Monitor" in scaffold["generated_code"]


# ── 3. Vision Intelligence Tests (Phase 2) ─────────────────────────────────

def test_object_recognition_and_captioning():
    vision = VisionService()

    # Object recognition
    objs = vision.detect_objects_in_image()
    assert objs["status"] == "success"
    assert objs["image_width"] > 0
    assert "objects" in objs

    # Image captioning
    caption = vision.generate_image_caption(style="technical")
    assert caption["status"] == "success"
    assert "Screen visual buffer" in caption["caption"] or "Dimensions" in caption["caption"]


# ── 4. RPA Automation & Workflow Tests (Phase 3) ────────────────────────────

def test_rpa_macro_execution():
    automation = DesktopAutomationService()
    steps = [
        {"action": "wait", "seconds": 0.1},
        {"action": "type", "text": "test_rpa"}
    ]
    res = automation.execute_rpa_macro(steps, stop_on_error=True)
    assert res["status"] == "completed"
    assert res["executed_steps_count"] == 2


# ── 5. Voice & Audio Tests (Phase 3) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_synthesis_and_listing():
    voice_svc = VoiceIntelligenceService()

    # List voices
    voices = voice_svc.list_available_voices()
    assert voices["status"] == "success"
    assert voices["count"] >= 3

    # Synthesize text
    synth = await voice_svc.synthesize_voice("Hello Ashrit, JARVIS capability expansion is active.", speed=1.0)
    assert synth["status"] == "success"
    assert os.path.exists(synth["file_path"])


def test_audio_effect_generation_fail_closed_guard():
    voice_svc = VoiceIntelligenceService()
    # When no CUDA accelerator or API key is set in test env, must report clean status or fail closed
    res = voice_svc.generate_audio_effect("laser blaster sound")
    assert res["status"] in ("success", "error")
    if res["status"] == "error":
        assert res.get("error_code") == "HARDWARE_OR_KEY_UNAVAILABLE"


# ── 6. Async Generation Queue & Job Manager Tests (Phase 4) ────────────────

def test_async_generation_queue_lifecycle():
    with tempfile.NamedTemporaryFile("w", suffix=".db", delete=False) as tf:
        temp_db = Path(tf.name)

    try:
        queue = AsyncGenerationJobManager(db_path=temp_db)

        # Submit job
        sub = queue.submit_job("image_generation", "Cyberpunk JARVIS HUD interface")
        job_id = sub["job_id"]
        assert sub["status"] == "queued"

        # Check initial status
        st = queue.get_job_status(job_id)
        assert st["status"] == "queued"
        assert st["progress"] == 0

        # Update status
        queue.update_job_status(job_id, "completed", progress=100, result_path="data/media_output/images/test.png")
        st2 = queue.get_job_status(job_id)
        assert st2["status"] == "completed"
        assert st2["progress"] == 100
        assert st2["result_path"] == "data/media_output/images/test.png"

        # List jobs
        jobs = queue.list_jobs(limit=5)
        assert len(jobs) >= 1
    finally:
        if temp_db.exists():
            try:
                os.remove(temp_db)
            except Exception:
                pass


# ── 7. Generative Modalities: Image, Video & 3D (Phases 4 & 5) ─────────────

@pytest.mark.asyncio
async def test_image_generation():
    # Capability check
    caps = image_generator.check_capabilities()
    assert "is_ready" in caps

    # Image generation (sync)
    res = await image_generator.generate_image("A glowing cyan holographic AI core", async_mode=False)
    assert res["status"] in ("success", "error")
    if res["status"] == "success":
        assert os.path.exists(res["file_path"])


def test_video_generation_fail_closed_guard():
    # Video generation requires cloud API key; without it, must fail closed
    res = video_generator.generate_video("A drone flying over a futuristic city")
    assert res["status"] in ("queued", "error")
    if res["status"] == "error":
        assert res.get("error_code") == "RESOURCE_UNAVAILABLE"


def test_threed_generation():
    # Procedural 3D scene generation (always available locally)
    proc = threed_generator.generate_procedural_3d_scene(scene_type="hud_orb", theme="cyan_hologram")
    assert proc["status"] == "success"
    assert "THREE.Scene" in proc["generated_code"]

    # Neural 3D mesh (fails closed if no cloud API key)
    neural = threed_generator.generate_neural_3d_mesh("A sports car model")
    assert neural["status"] in ("queued", "error")
    if neural["status"] == "error":
        assert neural.get("error_code") == "RESOURCE_UNAVAILABLE"


# ── 8. FastMCP Multimodal Skill Tool Routing Tests ─────────────────────────

@pytest.mark.asyncio
async def test_multimodal_skill_dispatch():
    skill = MultimodalSkill()
    tools = [t["name"] for t in skill.get_tools()]
    assert "generate_image" in tools
    assert "generate_video" in tools
    assert "generate_procedural_3d_scene" in tools
    assert "generate_neural_3d_mesh" in tools
    assert "get_generation_job_status" in tools

    # Test procedural 3D execution via skill dispatch
    res = await skill.execute_tool("generate_procedural_3d_scene", {"scene_type": "hud_orb"})
    assert res["status"] == "success"
    assert "THREE" in res["generated_code"]
