"""
JARVIS AI Desktop Assistant - Unified Voice Manager.

Coordinates the full voice interaction lifecycle:
Audio Capture → Wake Word Detection → Speech-to-Text → Intent / Planner Execution → Text-to-Speech.
Handles state transitions, self-voice echo suppression, intelligent barge-in,
acknowledgments, push-to-talk mode, and clean resource lifecycle.
"""

from __future__ import annotations

import asyncio
import io
import os
import random
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import numpy as np
from loguru import logger

from backend.models.schemas import (
    AssistantState,
    ResponseMessage,
    StatusMessage,
    TranscriptMessage,
    WSMessage,
)
from backend.services.voice.audio_device_manager import AudioDeviceManager
from backend.services.voice.intelligence import VoiceIntelligenceService
from backend.services.voice.stt_manager import STTManager
from backend.services.voice.tts_manager import TTSManager
from backend.services.voice.wake_word_manager import WakeWordManager


ACKNOWLEDGMENTS = [
    "Yes sir?",
    "At your service.",
    "How can I help?",
    "Ready, sir.",
    "I'm here, sir.",
    "What can I do for you?",
    "Listening, sir.",
    "Go ahead, sir.",
]

SERIOUS_ACKNOWLEDGMENTS = [
    "Standing by.",
    "Directive received.",
    "Command confirmed.",
    "Executing.",
    "Ready for mission instruction.",
    "Tactical link online.",
]


def clean_text_for_tts(text: str) -> str:
    """Clean markdown, code blocks, and formatting from text for TTS."""
    if not text:
        return ""

    try:
        from backend.services.llm import clean_function_calls_from_text
        text = clean_function_calls_from_text(text)
    except Exception:
        pass

    # 1. Remove code blocks (``` ... ```)
    text = re.sub(r"```[\s\S]*?```", "", text)

    # 2. Remove inline code backticks (`code`)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # 3. Remove markdown formatting asterisks/underscores
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # 4. Remove links (e.g., [text](url) -> text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # 5. Clean up extra whitespace/newlines
    text = re.sub(r"\s+", " ", text).strip()

    return text


def expects_follow_up(text: str) -> bool:
    """Check if text expects a follow-up answer (ends with question mark or typical prompt)."""
    if not text:
        return False
    text = text.strip()
    if text.endswith("?"):
        return True

    lower_text = text.lower()
    sentences = re.split(r"[.!?]+", text)
    last_sentence = ""
    for s in reversed(sentences):
        if s.strip():
            last_sentence = s.strip().lower()
            break

    if last_sentence:
        question_starts = [
            "what", "how", "why", "who", "where", "when", "which", "whose", "whom",
            "would you", "could you", "can you", "do you", "are you", "is there", "should we",
        ]
        for start in question_starts:
            if last_sentence.startswith(start):
                return True

    follow_up_patterns = [
        r"what do you think",
        r"would you like",
        r"do you want",
        r"let me know",
        r"anything else",
        r"how about you",
        r"tell me",
        r"feel free to ask",
        r"any questions",
        r"need help with anything",
    ]
    for pattern in follow_up_patterns:
        if re.search(pattern, lower_text):
            return True

    return False


class VoiceManager:
    """
    Coordinates the full voice interaction pipeline and state machine.
    """

    def __init__(
        self,
        wake_word_service: Optional[WakeWordManager] = None,
        stt_service: Optional[STTManager] = None,
        tts_service: Optional[TTSManager] = None,
        planner_agent=None,
        audio_device_manager: Optional[AudioDeviceManager] = None,
        voice_intelligence_service: Optional[VoiceIntelligenceService] = None,
    ) -> None:
        self.wake_word = wake_word_service
        self.stt = stt_service
        self.tts = tts_service
        self.planner = planner_agent
        self.audio_devices = audio_device_manager or AudioDeviceManager()
        self.intelligence = voice_intelligence_service or VoiceIntelligenceService()

        self._state = (
            AssistantState.SLEEPING
            if (wake_word_service and getattr(wake_word_service, "is_loaded", False))
            else AssistantState.IDLE
        )
        self._audio_buffer: list[bytes] = []
        self._listening_start_time: float = 0.0
        self._silence_timeout = 4.0  # seconds (snappy follow-up listening window)
        self._min_audio_length = 0.4  # minimum seconds of audio to process
        self._is_speaking = False
        self._cancel_speech = False
        self._push_to_talk_active = False

        # Voice Settings & Serious Mode
        self.serious_mode = False
        self.barge_in_enabled = True
        self.barge_in_sensitivity = 0.7
        self.mic_sensitivity = 0.8

        # Audio accumulation settings
        self._sample_rate = 16000
        self._bytes_per_sample = 2  # 16-bit
        self._silence_frames = 0
        self._has_speech = False
        self._played_ack = False
        self._last_speech_time = 0.0
        self._speech_silence_timeout = 0.55  # 0.55s silence window for instant speech completion
        self._rolling_audio_history: list[bytes] = []
        self._session_id = 0
        self._is_running = False

    @property
    def state(self) -> AssistantState:
        return self._state

    @state.setter
    def state(self, new_state: AssistantState) -> None:
        if new_state != self._state:
            logger.info(f"Voice state: {self._state.value} → {new_state.value}")
            self._state = new_state

    # ── Lifecycle Control ────────────────────────────────────────────────

    def start(self) -> None:
        """Enable voice processing."""
        self._is_running = True
        self.reset()
        logger.info("✓ VoiceManager started.")

    def stop(self) -> None:
        """Disable voice processing and release active audio buffers."""
        self._is_running = False
        self._cancel_speech = True
        if self.tts:
            self.tts.cancel_playback()
        if self.wake_word and hasattr(self.wake_word, "stop_standalone_listener"):
            self.wake_word.stop_standalone_listener()
        self.reset()
        self.state = AssistantState.IDLE
        logger.info("VoiceManager stopped.")

    def reset(self) -> None:
        """Reset internal buffers and session counters."""
        self._audio_buffer.clear()
        self._rolling_audio_history.clear()
        self._has_speech = False
        self._played_ack = False
        self._is_speaking = False
        self._cancel_speech = False
        self._push_to_talk_active = False
        if self.wake_word and hasattr(self.wake_word, "reset"):
            self.wake_word.reset()

    # ── Audio Ingestion & Pipeline ───────────────────────────────────────

    async def handle_audio_chunk(self, chunk: bytes) -> AsyncGenerator[WSMessage, None]:
        """
        Process an incoming audio chunk through the voice pipeline.
        Includes Self-Voice Echo Suppression & Intelligent Barge-In.
        """
        # Compute RMS energy of incoming microphone chunk
        energy = self.audio_devices.calculate_rms(chunk)

        # ── Self-Voice Echo Suppression & Barge-In Handling ───────────
        if self._state == AssistantState.SPEAKING or self._is_speaking:
            if self.barge_in_enabled:
                barge_threshold = max(600.0, 1500.0 * (1.2 - self.barge_in_sensitivity * 0.6))
                if energy > barge_threshold:
                    logger.info(f"Intelligent Barge-In detected! Energy {energy:.1f} > threshold {barge_threshold:.1f}")
                    self._cancel_speech = True
                    if self.tts:
                        self.tts.cancel_playback()
                    self._session_id += 1
                    self.state = AssistantState.INTERRUPTED
                    yield WSMessage(
                        type="status",
                        data=StatusMessage(state=AssistantState.INTERRUPTED, message="Barge-in interrupt").model_dump(),
                    )
                    await asyncio.sleep(0.1)
                    self.state = AssistantState.LISTENING
                    self._audio_buffer = [chunk]
                    self._listening_start_time = time.time()
                    self._last_speech_time = time.time()
                    self._has_speech = True
                    self._played_ack = True
                    yield WSMessage(
                        type="status",
                        data=StatusMessage(state=AssistantState.LISTENING).model_dump(),
                    )
                    return
            return

        # Maintain rolling audio history when not actively capturing user speech
        if self._state != AssistantState.LISTENING:
            self._rolling_audio_history.append(chunk)
            total_bytes = sum(len(c) for c in self._rolling_audio_history)
            while total_bytes > 48000 and self._rolling_audio_history:
                removed = self._rolling_audio_history.pop(0)
                total_bytes -= len(removed)

        # 1. Wake word detection in SLEEPING, IDLE, and PROCESSING states
        if (
            self.wake_word
            and getattr(self.wake_word, "is_loaded", False)
            and self._state in [AssistantState.SLEEPING, AssistantState.IDLE, AssistantState.PROCESSING]
        ):
            try:
                detected = self.wake_word.process_audio(chunk)
                if detected:
                    logger.info(f"Wake word detected in state: {self._state.value}!")
                    if self._state == AssistantState.SPEAKING:
                        self._cancel_speech = True
                        if self.tts:
                            self.tts.cancel_playback()

                    self._session_id += 1
                    self.state = AssistantState.LISTENING
                    self._audio_buffer = list(self._rolling_audio_history)
                    self._rolling_audio_history.clear()
                    self._listening_start_time = time.time()
                    self._last_speech_time = time.time()
                    self._has_speech = False
                    self._played_ack = False

                    yield WSMessage(
                        type="status",
                        data=StatusMessage(state=AssistantState.LISTENING).model_dump(),
                    )
                    yield WSMessage(
                        type="wake_word",
                        data={"detected": True},
                    )
                    return
            except Exception as e:
                logger.error(f"Wake word processing error: {e}")

        # 2. Listening state processing
        if self._state == AssistantState.LISTENING:
            self._audio_buffer.append(chunk)

            vad_threshold = max(450.0, 800.0 * (1.2 - self.mic_sensitivity * 0.5))
            if energy > vad_threshold:
                if not self._has_speech:
                    logger.info("Speech detected, listening...")
                self._has_speech = True
                self._last_speech_time = time.time()

            elapsed = time.time() - self._listening_start_time

            if self._has_speech:
                silence_duration = time.time() - self._last_speech_time
                if silence_duration > self._speech_silence_timeout:
                    logger.info("Silence detected after speech — processing speech...")
                    async for msg in self._process_speech():
                        yield msg
                elif elapsed > 30.0:
                    logger.info("Max speech duration reached — processing speech...")
                    async for msg in self._process_speech():
                        yield msg
            else:
                if elapsed > 1.5 and not self._played_ack and not self._push_to_talk_active:
                    self._played_ack = True
                    ack = random.choice(SERIOUS_ACKNOWLEDGMENTS if self.serious_mode else ACKNOWLEDGMENTS)
                    yield WSMessage(
                        type="response",
                        data=ResponseMessage(text=ack).model_dump(),
                    )
                    async for tts_msg in self._speak(ack):
                        yield tts_msg

                    self.state = AssistantState.LISTENING
                    self._listening_start_time = time.time()
                    self._last_speech_time = time.time()
                elif elapsed > self._silence_timeout:
                    next_idle_state = (
                        AssistantState.SLEEPING
                        if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                        else AssistantState.IDLE
                    )
                    logger.info(f"Listening timeout — returning to {next_idle_state.value}")
                    self.state = next_idle_state
                    self._audio_buffer.clear()
                    yield WSMessage(
                        type="status",
                        data=StatusMessage(state=next_idle_state).model_dump(),
                    )

    # ── Push to Talk & Interruption ───────────────────────────────────────

    async def handle_push_to_talk_start(self) -> AsyncGenerator[WSMessage, None]:
        """Handle push-to-talk activation."""
        self._push_to_talk_active = True
        self._cancel_speech = True
        if self.tts:
            self.tts.cancel_playback()
        self._session_id += 1
        logger.info(f"Session ID incremented to {self._session_id} on PTT start.")
        self.state = AssistantState.LISTENING
        self._audio_buffer.clear()
        self._listening_start_time = time.time()
        self._has_speech = False

        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.LISTENING).model_dump(),
        )

    async def handle_push_to_talk_stop(self) -> AsyncGenerator[WSMessage, None]:
        """Handle push-to-talk release — process accumulated audio."""
        self._push_to_talk_active = False

        if self._audio_buffer:
            self._has_speech = True
            async for msg in self._process_speech():
                yield msg
        else:
            self.state = AssistantState.IDLE
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.IDLE).model_dump(),
            )

    async def handle_interrupt(self) -> AsyncGenerator[WSMessage, None]:
        """Handle explicit interrupt request from frontend or WebSocket."""
        self._cancel_speech = True
        if self.tts:
            self.tts.cancel_playback()
        self.state = AssistantState.IDLE
        self._audio_buffer.clear()
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.IDLE).model_dump(),
        )

    # ── Core Speech Processing ───────────────────────────────────────────

    async def _process_speech(self) -> AsyncGenerator[WSMessage, None]:
        """Process accumulated audio: STT → Planner → TTS."""
        session_id = self._session_id

        if not self._audio_buffer:
            if self._session_id != session_id:
                return
            self.state = AssistantState.IDLE
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.IDLE).model_dump(),
            )
            return

        combined_audio = b"".join(self._audio_buffer)
        self._audio_buffer.clear()

        audio_duration = len(combined_audio) / (self._sample_rate * self._bytes_per_sample)
        if audio_duration < self._min_audio_length:
            logger.debug(f"Audio too short ({audio_duration:.1f}s), ignoring")
            if self._session_id != session_id:
                return
            self.state = AssistantState.IDLE
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.IDLE).model_dump(),
            )
            return

        if self._session_id != session_id:
            return
        self.state = AssistantState.PROCESSING
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
        )

        try:
            transcript = ""
            if self.stt and hasattr(self.stt, "transcribe_stream"):
                try:
                    stream_res = self.stt.transcribe_stream(combined_audio)
                    if hasattr(stream_res, "__aiter__"):
                        async for item in stream_res:
                            if self._session_id != session_id:
                                return
                            if isinstance(item, dict):
                                if item.get("type") == "interim" and item.get("text"):
                                    yield WSMessage(
                                        type="transcript",
                                        data={"text": item["text"], "is_final": False},
                                    )
                                elif item.get("type") == "final":
                                    transcript = item.get("text", "")
                    elif hasattr(self.stt, "transcribe"):
                        transcript = await self.stt.transcribe(combined_audio)
                except (TypeError, AttributeError):
                    if hasattr(self.stt, "transcribe"):
                        transcript = await self.stt.transcribe(combined_audio)
            elif self.stt and hasattr(self.stt, "transcribe"):
                transcript = await self.stt.transcribe(combined_audio)
            else:
                transcript = ""

            transcript = transcript.strip()

            if self._session_id != session_id:
                return

            if not transcript or transcript.lower() in ["", "subtitles", "[music]", "watching", "[applause]"]:
                logger.debug(f"Empty or noise transcript: '{transcript}'")
                next_state = (
                    AssistantState.SLEEPING
                    if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                    else AssistantState.IDLE
                )
                self.state = next_state
                yield WSMessage(
                    type="status",
                    data=StatusMessage(state=next_state).model_dump(),
                )
                return

            # Quick command intercepts
            clean_tr = transcript.lower().strip(".,!? ")
            if clean_tr in [
                "enable hand control", "activate hand control", "hand control on",
                "enable gesture control", "activate gesture control",
            ]:
                yield WSMessage(type="transcript", data={"text": transcript, "is_final": True})
                yield WSMessage(type="hand_control_changed", data={"enabled": True})
                resp_text = "Hand gesture control enabled, sir."
                async for tts_msg in self._speak(resp_text, session_id):
                    yield tts_msg
                next_state = (
                    AssistantState.SLEEPING
                    if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                    else AssistantState.IDLE
                )
                self.state = next_state
                yield WSMessage(type="status", data=StatusMessage(state=next_state).model_dump())
                return
            elif clean_tr in [
                "disable hand control", "deactivate hand control", "hand control off",
                "disable gesture control", "deactivate gesture control",
            ]:
                yield WSMessage(type="transcript", data={"text": transcript, "is_final": True})
                yield WSMessage(type="hand_control_changed", data={"enabled": False})
                resp_text = "Hand gesture control disabled."
                async for tts_msg in self._speak(resp_text, session_id):
                    yield tts_msg
                next_state = (
                    AssistantState.SLEEPING
                    if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                    else AssistantState.IDLE
                )
                self.state = next_state
                yield WSMessage(type="status", data=StatusMessage(state=next_state).model_dump())
                return
            elif clean_tr in [
                "run system diagnostic", "run a system diagnostic",
                "run full system diagnostic", "run a full system diagnostic", "system diagnostic",
            ]:
                yield WSMessage(type="transcript", data={"text": transcript, "is_final": True})
                from backend.services.manager import ServiceManager
                dev_service = ServiceManager.get_instance("self_development_service")
                if dev_service:
                    diag = dev_service.run_system_diagnostic()
                    issues_count = len(diag.get("discovered_issues", []))
                    if issues_count == 0:
                        resp_text = "All systems report nominal, sir. All core capabilities are functional."
                    else:
                        resp_text = f"Diagnostics complete, sir. I have detected {issues_count} potential issues. Please check the Developer Dashboard."
                else:
                    resp_text = "Diagnostic service is offline, sir."

                async for tts_msg in self._speak(resp_text, session_id):
                    yield tts_msg
                next_state = (
                    AssistantState.SLEEPING
                    if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                    else AssistantState.IDLE
                )
                self.state = next_state
                yield WSMessage(type="status", data=StatusMessage(state=next_state).model_dump())
                return

            if clean_tr in ["enable serious mode", "activate serious mode", "serious mode on", "serious mode"]:
                self.serious_mode = True
                logger.info("Serious Mode ACTIVATED via voice command.")
                resp_text = "Serious Mode activated, sir. Tactical interface and mission protocols online."
                yield WSMessage(type="transcript", data={"text": transcript, "is_final": True})
                yield WSMessage(type="serious_mode_changed", data={"enabled": True})
                async for tts_msg in self._speak(resp_text, session_id):
                    yield tts_msg
                next_state = (
                    AssistantState.SLEEPING
                    if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                    else AssistantState.IDLE
                )
                self.state = next_state
                yield WSMessage(type="status", data=StatusMessage(state=next_state).model_dump())
                return
            elif clean_tr in ["disable serious mode", "deactivate serious mode", "serious mode off"]:
                self.serious_mode = False
                logger.info("Serious Mode DEACTIVATED via voice command.")
                resp_text = "Serious Mode deactivated. Returning to standard protocol, sir."
                yield WSMessage(type="transcript", data={"text": transcript, "is_final": True})
                yield WSMessage(type="serious_mode_changed", data={"enabled": False})
                async for tts_msg in self._speak(resp_text, session_id):
                    yield tts_msg
                next_state = (
                    AssistantState.SLEEPING
                    if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                    else AssistantState.IDLE
                )
                self.state = next_state
                yield WSMessage(type="status", data=StatusMessage(state=next_state).model_dump())
                return

            if clean_tr in ["stop listening", "cancel", "goodbye", "bye", "stop"]:
                logger.info("User explicitly ended the conversation.")
                next_state = (
                    AssistantState.SLEEPING
                    if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                    else AssistantState.IDLE
                )
                self.state = next_state
                yield WSMessage(
                    type="status",
                    data=StatusMessage(state=next_state).model_dump(),
                )
                return

            logger.info(f"Transcript: '{transcript}'")
            yield WSMessage(
                type="transcript",
                data={"text": transcript, "is_final": True},
            )
        except Exception as e:
            logger.error(f"STT failed: {e}")
            if self._session_id != session_id:
                return
            self.state = AssistantState.ERROR
            yield WSMessage(type="error", data={"message": f"Speech recognition failed: {e}"})
            next_state = (
                AssistantState.SLEEPING
                if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                else AssistantState.IDLE
            )
            self.state = next_state
            yield WSMessage(
                type="status",
                data=StatusMessage(state=next_state).model_dump(),
            )
            return

        # Execute through planner / intent router
        planner_input = transcript
        if self.serious_mode:
            planner_input = f"[SERIOUS MODE ACTIVE: Tactical, mission-focused, concise, authoritative response] {transcript}"

        response_text = ""
        try:
            if self.planner and hasattr(self.planner, "plan_and_execute"):
                async for planner_msg in self.planner.plan_and_execute(planner_input):
                    if self._session_id != session_id:
                        return
                    yield planner_msg
                    if hasattr(planner_msg, "type") and planner_msg.type == "response":
                        response_text = planner_msg.data.get("text", "")
                    elif isinstance(planner_msg, dict) and planner_msg.get("type") == "response":
                        response_text = planner_msg.get("data", {}).get("text", "")
            else:
                response_text = f"Processed voice input: '{transcript}'"
                yield WSMessage(type="response", data=ResponseMessage(text=response_text).model_dump())
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            if self._session_id != session_id:
                return
            response_text = (
                "Command execution failed, sir. Systems reporting error."
                if self.serious_mode
                else "I'm sorry sir, I encountered an error processing that request."
            )
            yield WSMessage(
                type="response",
                data=ResponseMessage(text=response_text).model_dump(),
            )

        # Synthesize TTS response
        if response_text:
            if self._session_id != session_id:
                return
            async for tts_msg in self._speak(response_text, session_id):
                yield tts_msg

        if self._session_id != session_id:
            return

        # Follow-up listening or idle return
        if response_text and expects_follow_up(response_text) and not self._cancel_speech:
            logger.info("Response expects follow-up — entering listening mode silently...")
            self.state = AssistantState.LISTENING
            self._audio_buffer.clear()
            self._listening_start_time = time.time()
            self._last_speech_time = time.time()
            self._has_speech = False
            self._played_ack = True
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.LISTENING).model_dump(),
            )
        else:
            next_state = (
                AssistantState.SLEEPING
                if (self.wake_word and getattr(self.wake_word, "is_loaded", False))
                else AssistantState.IDLE
            )
            self.state = next_state
            yield WSMessage(
                type="status",
                data=StatusMessage(state=next_state).model_dump(),
            )

    async def _speak(self, text: str, session_id: Optional[int] = None) -> AsyncGenerator[WSMessage, None]:
        """Generate and yield TTS audio for text."""
        if session_id is not None and self._session_id != session_id:
            return
        cleaned_text = clean_text_for_tts(text)
        if not cleaned_text or not cleaned_text.strip():
            return

        self._is_speaking = True
        self._cancel_speech = False

        if session_id is not None and self._session_id != session_id:
            self._is_speaking = False
            return
        self.state = AssistantState.SPEAKING

        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.SPEAKING).model_dump(),
        )

        try:
            logger.info(f"Synthesizing full TTS: '{cleaned_text[:60]}...'")
            audio_bytes = b""
            if self.tts and hasattr(self.tts, "synthesize"):
                audio_bytes = await self.tts.synthesize(cleaned_text)

            if session_id is not None and self._session_id != session_id:
                self._is_speaking = False
                return

            if audio_bytes and not self._cancel_speech:
                import base64
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                yield WSMessage(
                    type="tts_audio",
                    data={"audio": audio_b64, "format": "mp3"},
                )
        except Exception as e:
            logger.error(f"TTS failed: {e}")

        if session_id is not None and self._session_id != session_id:
            return
        self._is_speaking = False
        self._cancel_speech = False

    async def handle_text_command(self, text: str) -> AsyncGenerator[WSMessage, None]:
        """Handle a text command (typed, not spoken)."""
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
        )

        response_text = ""
        if self.planner and hasattr(self.planner, "plan_and_execute"):
            async for msg in self.planner.plan_and_execute(text):
                yield msg
                if hasattr(msg, "type") and msg.type == "response":
                    response_text = msg.data.get("text", "")
                elif isinstance(msg, dict) and msg.get("type") == "response":
                    response_text = msg.get("data", {}).get("text", "")

        # Persist conversation to memory
        if response_text:
            from backend.services.manager import ServiceManager
            mem_svc = ServiceManager.get_instance("memory_service")
            if mem_svc and hasattr(mem_svc, "store_conversation"):
                try:
                    conv_id = str(int(time.time() * 1000))
                    title = text[:45].strip() or "Chat Session"
                    await mem_svc.store_conversation(
                        conv_id,
                        [
                            {"role": "user", "content": text},
                            {"role": "assistant", "content": response_text},
                        ],
                        title=title,
                    )
                    logger.info("✓ Saved voice/text conversation to database: '{}'", title)
                except Exception as save_err:
                    logger.warning("Failed to store voice conversation history: {}", save_err)

        if response_text:
            try:
                async for tts_msg in self._speak(response_text):
                    yield tts_msg
            except Exception as tts_err:
                logger.warning(f"TTS audio notice in text command: {tts_err}")

        self.state = AssistantState.IDLE
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.IDLE).model_dump(),
        )
