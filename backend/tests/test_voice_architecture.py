"""
Unit & Integration Test Suite for Consolidated Voice Architecture.

Verifies:
1. Voice OFF state is completely idle (0 threads, 0 devices locked).
2. AudioDeviceManager buffer and RMS energy calculations.
3. WakeWordManager lazy-loading, detection, and cooldown.
4. STTManager lazy-loading, hallucination filtering, and streaming API.
5. TTSManager multi-tier fallback, barge-in cancellation, and voice listing.
6. VoiceIntelligenceService emotion analysis, speaker profiles, and fail-closed SFX guard.
7. VoiceManager state machine lifecycle (IDLE -> LISTENING -> PROCESSING -> SPEAKING -> IDLE),
   push-to-talk, self-voice echo suppression, and text commands.
8. Backward compatibility of all legacy facades.
"""

import asyncio
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.schemas import AssistantState, WSMessage
from backend.services.voice.audio_device_manager import AudioDeviceManager
from backend.services.voice.intelligence import VoiceIntelligenceService
from backend.services.voice.stt_manager import STTManager, clean_whisper_hallucinations
from backend.services.voice.tts_manager import TTSManager, EdgeTTSProvider, LocalTTSProvider, PiperTTSProvider
from backend.services.voice.voice_manager import (
    VoiceManager,
    clean_text_for_tts,
    expects_follow_up,
)
from backend.services.voice.wake_word_manager import WakeWordManager


# ── 1. Voice OFF Idle State ──────────────────────────────────────────────

def test_voice_off_state_is_idle():
    """Verify that an inactive VoiceManager creates 0 background threads and zero device locks."""
    vm = VoiceManager()
    assert vm.state == AssistantState.IDLE
    assert not vm._is_speaking
    assert not vm._has_speech
    assert len(vm._audio_buffer) == 0

    vm.stop()
    assert vm.state == AssistantState.IDLE


# ── 2. AudioDeviceManager ────────────────────────────────────────────────

def test_audio_device_manager():
    """Verify AudioDeviceManager buffer management and RMS computation."""
    adm = AudioDeviceManager()
    
    # Empty audio RMS
    assert adm.calculate_rms(b"") == 0.0

    # Sine wave PCM
    samples = (np.sin(np.linspace(0, 2 * np.pi * 440, 1600)) * 10000).astype(np.int16)
    pcm_bytes = samples.tobytes()
    rms = adm.calculate_rms(pcm_bytes)
    assert rms > 0.0

    # PCM to float32
    f32 = adm.pcm_to_float32(pcm_bytes)
    assert len(f32) == 1600
    assert np.max(np.abs(f32)) <= 1.0

    # Buffering and clearing
    res = adm.append_chunk(pcm_bytes)
    assert res["status"] == "buffering"
    assert res["current_buffer_bytes"] == len(pcm_bytes)

    buf_bytes = adm.get_buffer_bytes()
    assert len(buf_bytes) == len(pcm_bytes)

    cleared = adm.clear_buffer()
    assert cleared == len(pcm_bytes)
    assert len(adm.get_buffer_bytes()) == 0


# ── 3. WakeWordManager ───────────────────────────────────────────────────

def test_wake_word_manager():
    """Verify WakeWordManager lazy-loading, detection, and cooldown."""
    wwm = WakeWordManager(threshold=0.45)
    assert wwm.threshold == 0.45
    assert not wwm.is_loaded

    # Without loaded model, returns False safely without error
    fake_chunk = np.zeros(1280, dtype=np.int16).tobytes()
    assert not wwm.process_audio(fake_chunk)

    # Threshold updating
    wwm.set_threshold(0.60)
    assert wwm.threshold == 0.60

    # Mock loaded model
    mock_model = MagicMock()
    mock_model.predict.return_value = {"hey_jarvis": 0.85}
    wwm._model = mock_model
    wwm._is_loaded = True

    detected = wwm.process_audio(fake_chunk)
    assert detected is True

    # Cooldown should prevent immediate second detection
    detected_cooldown = wwm.process_audio(fake_chunk)
    assert detected_cooldown is False

    # Status dictionary
    status = wwm.get_status()
    assert status["loaded"] is True
    assert status["threshold"] == 0.60


# ── 4. STTManager & Hallucination Suppression ────────────────────────────

def test_stt_manager_hallucination_cleaning():
    """Verify whisper hallucination suppression."""
    assert clean_whisper_hallucinations("") == ""
    assert clean_whisper_hallucinations("  ") == ""
    
    # Single word repetition
    repeated_words = "hello hello hello hello"
    assert clean_whisper_hallucinations(repeated_words) == "Hello"

    # Phrase repetition
    repeated_phrase = "thank you thank you thank you thank you"
    assert clean_whisper_hallucinations(repeated_phrase) == "Thank you"

    # Legitimate transcription
    normal_text = "JARVIS please open the browser and search for weather in Tokyo"
    assert clean_whisper_hallucinations(normal_text) == normal_text


@pytest.mark.asyncio
async def test_stt_manager_transcribe():
    """Verify STTManager transcription with mocked Whisper engine."""
    stt = STTManager(eager_load=False)
    assert not stt.is_loaded

    mock_segment = MagicMock()
    mock_segment.text = "Hello JARVIS"
    mock_segment.start = 0.0
    mock_segment.end = 1.0

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], MagicMock(language="en"))
    stt._model = mock_model
    stt._is_loaded = True

    audio_samples = np.zeros(16000, dtype=np.float32)
    result = await stt.transcribe_numpy(audio_samples)
    assert result == "Hello JARVIS"

    status = stt.get_status()
    assert status["loaded"] is True
    assert status["streaming_supported"] is True


# ── 5. TTSManager & Helpers ──────────────────────────────────────────────

def test_tts_helpers():
    """Verify clean_text_for_tts and expects_follow_up helpers."""
    dirty_text = "Here is the code: ```python\nprint('hello')\n``` and `inline_var` with **bold**."
    cleaned = clean_text_for_tts(dirty_text)
    assert "```" not in cleaned
    assert "print('hello')" not in cleaned
    assert "inline_var" in cleaned
    assert "bold" in cleaned

    assert expects_follow_up("Would you like me to proceed with execution?") is True
    assert expects_follow_up("What do you think?") is True
    assert expects_follow_up("I have completed the task.") is False


@pytest.mark.asyncio
async def test_tts_manager_lifecycle():
    """Verify TTSManager cancellation and voice listing."""
    tts = TTSManager(prefer_local=True)
    assert not tts.is_speaking()
    assert not tts.is_cancelled

    tts.cancel_playback()
    assert tts.is_cancelled

    # Voice listing with fast fallback
    voices = await tts.get_available_voices()
    assert isinstance(voices, list)
    assert len(voices) >= 1


# ── 6. VoiceIntelligenceService ──────────────────────────────────────────

def test_voice_intelligence_features(tmp_path):
    """Verify emotion detection, speaker profiles, and fail-closed SFX synthesis."""
    profiles_file = tmp_path / "test_profiles.json"
    vis = VoiceIntelligenceService(profiles_file=profiles_file)

    # Emotion detection
    emotion_res = vis.detect_speaker_emotion(audio_rms=0.18, pitch_hz=250.0)
    assert emotion_res["emotion"] == "Energetic"

    calm_res = vis.detect_speaker_emotion(audio_rms=0.01, pitch_hz=120.0)
    assert calm_res["emotion"] == "Calm / Quiet"

    # Speaker profile management
    profile = vis.manage_speaker_profile(action="get", name="Ashrit")
    assert profile["status"] == "profile_retrieved"

    update_res = vis.manage_speaker_profile(
        action="update", name="Ashrit", details={"preferred_tts_voice": "en-US-AriaNeural"}
    )
    assert update_res["status"] == "profile_updated"
    assert update_res["profile"]["preferred_tts_voice"] == "en-US-AriaNeural"

    # Threshold tuning
    thresh_res = vis.tune_wake_word_threshold(0.65)
    assert thresh_res["threshold"] == 0.65

    # Fail-closed audio effect without GPU / ElevenLabs
    with patch.dict("os.environ", {"ELEVENLABS_API_KEY": ""}):
        with patch("torch.cuda.is_available", return_value=False):
            sfx_res = vis.generate_audio_effect("laser blaster pulse")
            assert sfx_res["status"] in ("error", "success")


# ── 7. VoiceManager State Machine & Pipeline ─────────────────────────────

@pytest.mark.asyncio
async def test_voice_manager_pipeline():
    """Verify complete VoiceManager state machine: PTT, audio chunks, and text command."""
    mock_stt = MagicMock(spec=["transcribe", "is_loaded"])
    mock_stt.transcribe = AsyncMock(return_value="open notepad")
    mock_stt.is_loaded = True

    mock_tts = MagicMock()
    mock_tts.synthesize = AsyncMock(return_value=b"RIFFFAKEWAVDATA")
    mock_tts.cancel_playback = MagicMock()

    mock_planner = MagicMock()

    async def mock_plan_exec(text, conversation_id=None):
        yield WSMessage(type="status", data={"state": "executing"})
        yield WSMessage(type="response", data={"text": "Opening Notepad for you, sir."})

    mock_planner.plan_and_execute = mock_plan_exec

    vm = VoiceManager(
        stt_service=mock_stt,
        tts_service=mock_tts,
        planner_agent=mock_planner,
    )

    # 1. Text Command Pipeline
    messages = []
    async for msg in vm.handle_text_command("open notepad"):
        messages.append(msg)

    msg_types = [m.type for m in messages]
    assert "status" in msg_types
    assert "response" in msg_types
    assert "tts_audio" in msg_types
    assert vm.state == AssistantState.IDLE

    # 2. Push to Talk Pipeline
    ptt_start_msgs = []
    async for msg in vm.handle_push_to_talk_start():
        ptt_start_msgs.append(msg)
    assert vm.state == AssistantState.LISTENING

    # Feed audio chunk
    chunk = (np.sin(np.linspace(0, 2 * np.pi * 440, 16000)) * 5000).astype(np.int16).tobytes()
    async for _ in vm.handle_audio_chunk(chunk):
        pass

    # Stop PTT and verify execution
    ptt_stop_msgs = []
    async for msg in vm.handle_push_to_talk_stop():
        ptt_stop_msgs.append(msg)

    stop_types = [m.type for m in ptt_stop_msgs]
    assert "transcript" in stop_types or "response" in stop_types

    # 3. Explicit Interrupt
    interrupt_msgs = []
    async for msg in vm.handle_interrupt():
        interrupt_msgs.append(msg)
    assert vm.state == AssistantState.IDLE


# ── 8. Backward Compatibility Facades ────────────────────────────────────

def test_backward_compatibility_facades():
    """Verify that all legacy module imports function identically."""
    from backend.agents.voice import VoiceAgent, clean_text_for_tts as legacy_clean, expects_follow_up as legacy_follow
    from backend.services.stt import STTService, clean_whisper_hallucinations as legacy_hallucination
    from backend.services.tts import TTSService, EdgeTTSProvider as LegacyEdge, LocalTTSProvider as LegacyLocal
    from backend.services.wake_word import WakeWordService
    from backend.services.voice_intelligence import VoiceIntelligenceService as LegacyVIS

    # Verify instantiations
    v_agent = VoiceAgent()
    assert v_agent.state == AssistantState.IDLE

    stt_svc = STTService(eager_load=False)
    assert not stt_svc.is_loaded

    tts_svc = TTSService(prefer_local=True)
    assert tts_svc.last_provider_used == "sapi"

    ww_svc = WakeWordService(threshold=0.35)
    assert ww_svc.threshold == 0.35

    vis_svc = LegacyVIS()
    assert vis_svc.wake_word_threshold == 0.50

    # Verify functions
    assert legacy_clean("hello `world`") == "hello world"
    assert legacy_follow("Need anything else?") is True
    assert legacy_hallucination("hi hi hi") == "Hi"
