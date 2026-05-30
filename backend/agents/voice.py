"""
Voice pipeline agent for JARVIS.

Manages the full voice interaction flow: wake word detection → 
speech-to-text → planner → text-to-speech. Handles state transitions,
interruptions, acknowledgments, and push-to-talk mode.
"""

import asyncio
import io
import random
import time
from enum import Enum
from typing import AsyncGenerator, Optional

import numpy as np
from loguru import logger

from backend.models.schemas import (
    AssistantState,
    ResponseMessage,
    StatusMessage,
    TranscriptMessage,
    WSMessage,
)


# Acknowledgment phrases when wake word is detected
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


class VoiceAgent:
    """Manages the voice interaction pipeline and state machine."""

    def __init__(
        self,
        wake_word_service,
        stt_service,
        tts_service,
        planner_agent,
    ):
        self.wake_word = wake_word_service
        self.stt = stt_service
        self.tts = tts_service
        self.planner = planner_agent

        self._state = AssistantState.IDLE
        self._audio_buffer: list[bytes] = []
        self._listening_start_time: float = 0
        self._silence_timeout = 10.0  # seconds
        self._min_audio_length = 0.5  # minimum seconds of audio to process
        self._is_speaking = False
        self._cancel_speech = False
        self._push_to_talk_active = False

        # Audio accumulation settings
        self._sample_rate = 16000
        self._bytes_per_sample = 2  # 16-bit
        self._silence_frames = 0
        self._silence_threshold = 30  # frames of silence before processing
        self._has_speech = False

    @property
    def state(self) -> AssistantState:
        return self._state

    @state.setter
    def state(self, new_state: AssistantState) -> None:
        if new_state != self._state:
            logger.info(f"Voice state: {self._state.value} → {new_state.value}")
            self._state = new_state

    async def handle_audio_chunk(self, chunk: bytes) -> AsyncGenerator[WSMessage, None]:
        """
        Process an incoming audio chunk through the voice pipeline.

        Yields WSMessage objects for state changes, transcripts, responses, and TTS audio.
        """
        if self._state == AssistantState.IDLE:
            # Check for wake word
            if self.wake_word:
                try:
                    detected = self.wake_word.process_audio(chunk)
                    if detected:
                        logger.info("Wake word detected!")
                        self.state = AssistantState.WAKE_WORD_DETECTED
                        yield WSMessage(
                            type="status",
                            data=StatusMessage(state=AssistantState.WAKE_WORD_DETECTED).model_dump(),
                        )
                        yield WSMessage(
                            type="wake_word",
                            data={"detected": True},
                        )

                        # Send acknowledgment
                        ack = random.choice(ACKNOWLEDGMENTS)
                        yield WSMessage(
                            type="response",
                            data=ResponseMessage(text=ack).model_dump(),
                        )

                        # Generate TTS for acknowledgment
                        async for tts_msg in self._speak(ack):
                            yield tts_msg

                        # Transition to listening
                        self.state = AssistantState.LISTENING
                        self._audio_buffer.clear()
                        self._listening_start_time = time.time()
                        self._silence_frames = 0
                        self._has_speech = False
                        yield WSMessage(
                            type="status",
                            data=StatusMessage(state=AssistantState.LISTENING).model_dump(),
                        )
                except Exception as e:
                    logger.error(f"Wake word processing error: {e}")

        elif self._state == AssistantState.LISTENING:
            # Accumulate audio for transcription
            self._audio_buffer.append(chunk)

            # Check for voice activity (simple energy-based)
            try:
                audio_array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                energy = np.sqrt(np.mean(audio_array ** 2))

                if energy > 500:  # Speech threshold
                    self._has_speech = True
                    self._silence_frames = 0
                elif self._has_speech:
                    self._silence_frames += 1
            except Exception:
                self._silence_frames += 1

            # Check for silence timeout (end of speech)
            elapsed = time.time() - self._listening_start_time

            if self._has_speech and self._silence_frames > self._silence_threshold:
                # User finished speaking — process the audio
                async for msg in self._process_speech():
                    yield msg

            elif elapsed > self._silence_timeout:
                # Timeout — no speech detected
                logger.info("Listening timeout — returning to idle")
                self.state = AssistantState.IDLE
                self._audio_buffer.clear()
                yield WSMessage(
                    type="status",
                    data=StatusMessage(state=AssistantState.IDLE).model_dump(),
                )

        elif self._state == AssistantState.SPEAKING:
            # Check if user is interrupting
            try:
                audio_array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                energy = np.sqrt(np.mean(audio_array ** 2))

                if energy > 1000:  # Higher threshold for interruption
                    logger.info("User interruption detected — stopping speech")
                    self._cancel_speech = True
                    self.state = AssistantState.LISTENING
                    self._audio_buffer.clear()
                    self._audio_buffer.append(chunk)
                    self._listening_start_time = time.time()
                    self._silence_frames = 0
                    self._has_speech = True
                    yield WSMessage(
                        type="status",
                        data=StatusMessage(state=AssistantState.LISTENING).model_dump(),
                    )
            except Exception:
                pass

    async def handle_push_to_talk_start(self) -> AsyncGenerator[WSMessage, None]:
        """Handle push-to-talk activation."""
        self._push_to_talk_active = True
        self._cancel_speech = True  # Stop any current speech
        self.state = AssistantState.LISTENING
        self._audio_buffer.clear()
        self._listening_start_time = time.time()
        self._silence_frames = 0
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
        """Handle explicit interrupt request from frontend."""
        self._cancel_speech = True
        self.state = AssistantState.IDLE
        self._audio_buffer.clear()
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.IDLE).model_dump(),
        )

    async def _process_speech(self) -> AsyncGenerator[WSMessage, None]:
        """Process accumulated audio: STT → Planner → TTS."""
        if not self._audio_buffer:
            self.state = AssistantState.IDLE
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.IDLE).model_dump(),
            )
            return

        # Combine audio buffer
        combined_audio = b"".join(self._audio_buffer)
        self._audio_buffer.clear()

        # Check minimum audio length
        audio_duration = len(combined_audio) / (self._sample_rate * self._bytes_per_sample)
        if audio_duration < self._min_audio_length:
            logger.debug(f"Audio too short ({audio_duration:.1f}s), ignoring")
            self.state = AssistantState.IDLE
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.IDLE).model_dump(),
            )
            return

        # Signal processing state
        self.state = AssistantState.PROCESSING
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
        )

        # Speech-to-text
        try:
            transcript = await self.stt.transcribe(combined_audio)
            transcript = transcript.strip()

            if not transcript or transcript.lower() in ["", "you", "thank you", "thanks"]:
                logger.debug(f"Empty or noise transcript: '{transcript}'")
                self.state = AssistantState.IDLE
                yield WSMessage(
                    type="status",
                    data=StatusMessage(state=AssistantState.IDLE).model_dump(),
                )
                return

            logger.info(f"Transcript: '{transcript}'")
            yield WSMessage(
                type="transcript",
                data={"text": transcript, "is_final": True},
            )
        except Exception as e:
            logger.error(f"STT failed: {e}")
            self.state = AssistantState.IDLE
            yield WSMessage(type="error", data={"message": f"Speech recognition failed: {e}"})
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.IDLE).model_dump(),
            )
            return

        # Process through planner
        response_text = ""
        try:
            async for planner_msg in self.planner.plan_and_execute(transcript):
                yield planner_msg
                if planner_msg.type == "response":
                    response_text = planner_msg.data.get("text", "")
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            response_text = "I'm sorry sir, I encountered an error processing that request."
            yield WSMessage(
                type="response",
                data=ResponseMessage(text=response_text).model_dump(),
            )

        # Text-to-speech
        if response_text:
            async for tts_msg in self._speak(response_text):
                yield tts_msg

        # Return to idle
        self.state = AssistantState.IDLE
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.IDLE).model_dump(),
        )

    async def _speak(self, text: str) -> AsyncGenerator[WSMessage, None]:
        """Generate and stream TTS audio for the given text."""
        self._is_speaking = True
        self._cancel_speech = False
        self.state = AssistantState.SPEAKING

        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.SPEAKING).model_dump(),
        )

        try:
            async for audio_chunk in self.tts.stream_speech(text):
                if self._cancel_speech:
                    logger.info("Speech cancelled by interruption")
                    break

                # Send audio chunk as base64 in JSON
                import base64
                audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                yield WSMessage(
                    type="tts_audio",
                    data={"audio": audio_b64, "format": "mp3"},
                )
        except Exception as e:
            logger.error(f"TTS failed: {e}")

        self._is_speaking = False
        self._cancel_speech = False

    async def handle_text_command(self, text: str) -> AsyncGenerator[WSMessage, None]:
        """Handle a text command (typed, not spoken)."""
        # Skip wake word and STT — go directly to planner
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
        )

        response_text = ""
        async for msg in self.planner.plan_and_execute(text):
            yield msg
            if msg.type == "response":
                response_text = msg.data.get("text", "")

        # TTS for the response
        if response_text:
            async for tts_msg in self._speak(response_text):
                yield tts_msg

        self.state = AssistantState.IDLE
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.IDLE).model_dump(),
        )
