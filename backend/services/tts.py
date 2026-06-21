"""
JARVIS AI Desktop Assistant - Text-to-Speech Service.

Provides streaming text-to-speech synthesis using edge-tts (Microsoft
Edge's online TTS service) with configurable voice and rate settings.
Returns MP3 audio chunks suitable for real-time playback.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, List, Optional

from backend.utils.logger import logger


class TTSService:
    """
    Text-to-speech service using edge-tts.

    Streams MP3 audio chunks asynchronously, supporting real-time
    playback and cancellation via a flag.
    """

    def __init__(self, voice: str = "en-US-GuyNeural", rate: str = "+0%") -> None:
        """
        Initialise the TTS service.

        Args:
            voice: Edge-tts voice identifier (e.g. ``en-US-GuyNeural``).
            rate: Speech rate adjustment (e.g. ``+10%``, ``-5%``, ``+0%``).
        """
        self.voice = voice
        self.rate = rate
        self._cancel_flag = False
        logger.info("TTSService initialised — voice={}, rate={}", voice, rate)

    # ── Public API ───────────────────────────────────────────────────────

    async def stream_speech(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Convert text to speech and yield MP3 audio chunks.

        The generator can be interrupted at any time by calling
        :meth:`cancel`. After cancellation, the generator stops
        yielding and the flag is automatically reset.

        Args:
            text: The text to synthesise.

        Yields:
            Chunks of MP3 audio bytes.
        """
        import edge_tts

        if not text or not text.strip():
            logger.debug("TTS received empty text, skipping")
            return

        self._cancel_flag = False
        logger.info("TTS streaming — voice={}, rate={}, text='{}'", self.voice, self.rate, text[:60])

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
            )

            async for chunk in communicate.stream():
                if self._cancel_flag:
                    logger.info("TTS stream cancelled by user")
                    break

                if chunk["type"] == "audio":
                    yield chunk["data"]

            logger.debug("TTS stream completed for text: '{}'", text[:40])

        except Exception as e:
            logger.error("TTS streaming error: {}", e)
            raise

        finally:
            self._cancel_flag = False

    async def synthesize(self, text: str) -> bytes:
        """
        Synthesise the full audio for a text string.

        Unlike :meth:`stream_speech`, this collects all chunks into
        a single bytes object. Useful for short utterances.

        Args:
            text: The text to synthesise.

        Returns:
            Complete MP3 audio bytes.
        """
        chunks: List[bytes] = []
        async for chunk in self.stream_speech(text):
            chunks.append(chunk)
        return b"".join(chunks)

    def cancel(self) -> None:
        """
        Signal the current TTS stream to stop.

        The :meth:`stream_speech` generator will stop yielding
        on the next iteration and reset the flag.
        """
        self._cancel_flag = True
        logger.info("TTS cancellation requested")

    @property
    def is_cancelled(self) -> bool:
        """Whether a cancellation has been requested."""
        return self._cancel_flag

    # ── Voice Management ─────────────────────────────────────────────────

    async def get_available_voices(self) -> List[dict]:
        """
        Retrieve the list of available edge-tts voices.

        Returns:
            A list of dictionaries, each containing ``Name``,
            ``ShortName``, ``Gender``, ``Locale``, etc.
        """
        import edge_tts

        try:
            voices = await edge_tts.list_voices()
            male_voices = [v for v in voices if v.get("Gender", "").lower() == "male"]
            logger.info("Retrieved {} available TTS voices (filtered to {} male voices)", len(voices), len(male_voices))
            return [
                {
                    "name": v.get("Name", ""),
                    "short_name": v.get("ShortName", ""),
                    "gender": v.get("Gender", ""),
                    "locale": v.get("Locale", ""),
                    "friendly_name": v.get("FriendlyName", ""),
                }
                for v in male_voices
            ]
        except Exception as e:
            logger.error("Failed to list TTS voices: {}", e)
            return []

    def set_voice(self, voice: str) -> None:
        """
        Change the active TTS voice.

        Args:
            voice: Edge-tts voice identifier.
        """
        self.voice = voice
        logger.info("TTS voice changed to: {}", voice)

    def set_rate(self, rate: str) -> None:
        """
        Change the speech rate.

        Args:
            rate: Rate adjustment string (e.g. ``+10%``).
        """
        self.rate = rate
        logger.info("TTS rate changed to: {}", rate)

    def get_status(self) -> dict:
        """Return current TTS service status."""
        return {
            "voice": self.voice,
            "rate": self.rate,
            "is_cancelled": self._cancel_flag,
        }
