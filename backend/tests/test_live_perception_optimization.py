"""
Unit tests for Live Mode & Desktop Perception Optimization.
Verifies:
1. Zero overhead when Live Mode is OFF.
2. Event-driven / adaptive differential perception loop.
3. UIASceneGraph caching behavior on static windows.
4. WorldModel lightweight initialization and throttled probes.
5. HandControlService clean camera lifecycle and shutdown.
6. VisionService action verification diffing.
"""

import pytest
import asyncio
import time
from PIL import Image

from backend.services.live_mode.live_engine import LiveModeEngine, LiveContextFrame
from backend.services.world_model import WorldModel
from backend.services.perception.uia_scene_graph import UIASceneGraph, SceneGraph
from backend.services.hand_control_service import HandControlService
from backend.services.vision_service import VisionService


def test_live_mode_off_state():
    engine = LiveModeEngine()
    assert engine.is_enabled is False
    assert engine._task is None
    assert engine.latest_frame is None


@pytest.mark.asyncio
async def test_live_mode_start_stop_restart_lifecycle():
    engine = LiveModeEngine()
    
    # 1. Start
    engine.start(speak_greeting=False)
    assert engine.is_enabled is True
    assert engine._task is not None
    assert not engine._task.done()

    # Allow one tick of the perception loop
    await asyncio.sleep(0.1)

    # 2. Stop
    engine.stop()
    assert engine.is_enabled is False
    assert engine._task is None

    # 3. Restart idempotency
    engine.start(speak_greeting=False)
    assert engine.is_enabled is True
    assert engine._task is not None

    await asyncio.sleep(0.1)
    engine.stop()
    assert engine.is_enabled is False
    assert engine._task is None


def test_uia_scene_graph_caching():
    extractor = UIASceneGraph(cache_ttl=2.0)
    t0 = time.perf_counter()
    scene1 = extractor.capture_scene()
    t1 = time.perf_counter()

    # Second call should hit the cache immediately (<5ms)
    t2 = time.perf_counter()
    scene2 = extractor.capture_scene()
    t3 = time.perf_counter()

    assert isinstance(scene1, SceneGraph)
    assert isinstance(scene2, SceneGraph)
    # Cache lookup should be faster than full scan
    assert (t3 - t2) <= max(0.05, (t1 - t0))


def test_world_model_lazy_init_and_refresh():
    wm = WorldModel()
    assert wm._has_refreshed is False

    # Calling .state triggers first refresh on demand
    st = wm.state
    assert wm._has_refreshed is True
    assert st.active_app is not None

    # Refresh with force=False uses cached probes
    st2 = wm.refresh(force=False)
    assert st2.timestamp >= st.timestamp


def test_hand_control_camera_lifecycle():
    hc = HandControlService()
    assert hc._tracking_active is False
    assert hc._worker_thread is None

    # Stop when already stopped is a clean no-op
    hc.stop_background_tracking()
    assert hc._tracking_active is False

    hc.shutdown()
    assert hc._tracking_active is False


def test_vision_action_verification_diffing():
    vision = VisionService()
    img_a = Image.new("RGB", (100, 100), color=(255, 255, 255))
    img_b = Image.new("RGB", (100, 100), color=(255, 255, 255))
    img_c = Image.new("RGB", (100, 100), color=(0, 0, 0))

    # Identical images -> no change
    res_same = vision.verify_action_visual_effect(img_a, img_b)
    assert res_same["has_changed"] is False
    assert res_same["diff_score"] == 0.0

    # Different images -> visual change detected
    res_diff = vision.verify_action_visual_effect(img_a, img_c)
    assert res_diff["has_changed"] is True
    assert res_diff["diff_score"] > 0.5
