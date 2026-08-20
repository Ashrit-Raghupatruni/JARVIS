"""
JARVIS AI Desktop Assistant - Text-to-Speech Service.

Provides multi-tiered text-to-speech synthesis:
1. Primary Online: edge-tts (Microsoft Edge streaming neural voice)
2. Resilient Offline: Windows Native SAPI SpVoice (100% offline local synthesis)
Automatically falls back to offline SAPI when internet is disconnected.
Preserves real-time streaming chunks, barge-in cancellation, and voice settings.
"""

from __future__ import annotations

import os
import io
import asyncio
import tempfile
from typing import AsyncGenerator, List, Optional, Dict, Any

from backend.utils.logger import logger


class EdgeTTSProvider:
    """Online streaming neural voice provider via Microsoft Edge TTS."""

    def __init__(self, voice: str = "en-US-GuyNeural", rate: str = "+0%"):
        self.voice = voice
        self.rate = rate

    async def stream(self, text: str, cancel_flag_fn) -> AsyncGenerator[bytes, None]:
        import edge_tts

        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
        )

        async for chunk in communicate.stream():
            if cancel_flag_fn():
                logger.info("Edge-TTS stream cancelled by user barge-in")
                break

            if chunk["type"] == "audio":
                yield chunk["data"]


class LocalTTSProvider:
    """Offline Windows Native SAPI voice provider. Operates with zero internet connectivity."""

    def __init__(self, rate: str = "+0%"):
        self.rate = rate

    def _synthesize_wav_sync(self, text: str) -> bytes:
        import win32com.client
        import pythoncom

        pythoncom.CoInitialize()
        try:
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            filestream = win32com.client.Dispatch("SAPI.SpFileStream")
            
            tmp_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            try:
                # 3 = SSFMCreateForWrite
                filestream.Open(tmp_path, 3, False)
                speaker.AudioOutputStream = filestream
                speaker.Speak(text)
                filestream.Close()

                with open(tmp_path, "rb") as f:
                    data = f.read()
                return data
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
        finally:
            pythoncom.CoUninitialize()

    async def stream(self, text: str, cancel_flag_fn) -> AsyncGenerator[bytes, None]:
        loop = asyncio.get_running_loop()
        wav_data = await loop.run_in_executor(None, self._synthesize_wav_sync, text)

        # Chunk the synthesized WAV data into streaming buffers (4KB per chunk)
        chunk_size = 4096
        for i in range(0, len(wav_data), chunk_size):
            if cancel_flag_fn():
                logger.info("Local SAPI TTS stream cancelled by user barge-in")
                break
            yield wav_data[i : i + chunk_size]
            await asyncio.sleep(0.01)  # Micro-yield for real-time audio pipeline


class TTSService:
    """
    Unified Text-to-Speech service with automatic Online Edge-TTS -> Offline SAPI failover.
    Streams audio chunks asynchronously, supporting real-time playback and barge-in cancellation.
    """

    def __init__(self, voice: str = "en-US-GuyNeural", rate: str = "+0%") -> None:
        self.voice = voice
        self.rate = rate
        self._cancel_flag = False
        self.edge_provider = EdgeTTSProvider(voice=voice, rate=rate)
        self.local_provider = LocalTTSProvider(rate=rate)
        self.last_provider_used = "edge-tts"
        logger.info("TTSService initialised — voice={}, rate={}, offline_sapi=Ready", voice, rate)

    # ── Public API ───────────────────────────────────────────────────────

    async def stream_speech(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Convert text to speech and yield audio chunks (MP3 for EdgeTTS, WAV for SAPI).
        Falls back to local SAPI if EdgeTTS fails or internet is unreachable.
        """
        if not text or not text.strip():
            logger.debug("TTS received empty text, skipping")
            return

        self._cancel_flag = False
        logger.info("TTS synthesizing — text='{}'", text[:60])

        # Attempt 1: Try Primary Online Edge TTS
        edge_success = False
        try:
            async for chunk in self.edge_provider.stream(text, lambda: self._cancel_flag):
                edge_success = True
                self.last_provider_used = "edge-tts"
                yield chunk
        except Exception as edge_err:
            logger.warning("⚠️ Edge-TTS failed ({}: {}). Failing over to Offline Local SAPI Provider...", type(edge_err).__name__, edge_err)

        if edge_success:
            logger.debug("✓ TTS stream completed via Edge-TTS")
            self._cancel_flag = False
            return

        # Attempt 2: Resilient Offline SAPI Fallback
        try:
            logger.info("🎙️ Synthesizing speech via Local Offline SAPI Provider...")
            self.last_provider_used = "sapi"
            async for chunk in self.local_provider.stream(text, lambda: self._cancel_flag):
                yield chunk
            logger.info("✓ TTS stream completed via Local Offline SAPI")
        except Exception as local_err:
            logger.error("❌ Both Edge-TTS and Local SAPI TTS failed: {}", local_err)
        finally:
            self._cancel_flag = False

    async def synthesize(self, text: str) -> bytes:
        """Synthesise the full audio bytes for a text string."""
        chunks: List[bytes] = []
        async for chunk in self.stream_speech(text):
            chunks.append(chunk)
        return b"".join(chunks)

    def cancel(self) -> None:
        """Signal the current TTS stream to stop immediately."""
        self._cancel_flag = True
        logger.info("TTS cancellation requested (Barge-In triggered)")

    def cancel_playback(self) -> None:
        """Alias for instant interrupt / barge-in playback cancellation."""
        self.cancel()

    @property
    def is_cancelled(self) -> bool:
        """Whether a cancellation has been requested."""
        return self._cancel_flag

    # ── Voice Management ─────────────────────────────────────────────────

    async def get_available_voices(self) -> List[dict]:
        """Retrieve the list of available edge-tts voices with fallback."""
        import edge_tts

        try:
            voices = await edge_tts.list_voices()
            male_voices = [v for v in voices if v.get("Gender", "").lower() == "male"]
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
            logger.warning("Failed to list online TTS voices (offline mode active): {}", e)
            return [
                {
                    "name": "Microsoft David - English (United States)",
                    "short_name": "SAPI-David",
                    "gender": "Male",
                    "locale": "en-US",
                    "friendly_name": "Windows SAPI Local Voice",
                }
            ]

    def set_voice(self, voice: str) -> None:
        self.voice = voice
        self.edge_provider.voice = voice
        logger.info("TTS voice changed to: {}", voice)

    def set_rate(self, rate: str) -> None:
        self.rate = rate
        self.edge_provider.rate = rate
        self.local_provider.rate = rate
        logger.info("TTS rate changed to: {}", rate)

    def get_status(self) -> dict:
        return {
            "voice": self.voice,
            "rate": self.rate,
            "is_cancelled": self._cancel_flag,
            "active_provider": self.last_provider_used,
            "offline_capable": True
        }

