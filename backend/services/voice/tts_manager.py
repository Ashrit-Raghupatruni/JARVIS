"""
JARVIS AI Desktop Assistant - Consolidated Text-to-Speech Manager.

Provides multi-tiered text-to-speech synthesis:
1. Online Primary: Microsoft Edge-TTS (Streaming neural voice)
2. Offline Neural: Local Piper TTS (Local ONNX neural voice)
3. Offline Native: Windows Native SAPI SpVoice (Guaranteed 100% offline local synthesis)
Supports real-time streaming chunks, instant barge-in cancellation, and voice settings.
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
from typing import Any, AsyncGenerator, Dict, List, Optional

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


class PiperTTSProvider:
    """
    Offline local neural voice provider using Piper ONNX models.
    Produces natural neural voice locally with zero internet access.
    """

    def __init__(self, model_path: Optional[str] = None, config_path: Optional[str] = None, rate: str = "+0%"):
        self.rate = rate
        self.model_path = model_path
        self.config_path = config_path
        self._voice = None
        self._available = False
        self._resolve_paths()

    def _resolve_paths(self) -> None:
        from pathlib import Path
        default_dir = Path("data/models/piper")
        if not self.model_path and default_dir.exists():
            onnx_files = list(default_dir.glob("*.onnx"))
            if onnx_files:
                self.model_path = str(onnx_files[0])
                cfg = self.model_path + ".json"
                if os.path.exists(cfg):
                    self.config_path = cfg

        if self.model_path and os.path.exists(self.model_path):
            try:
                from piper.voice import PiperVoice
                self._voice = PiperVoice.load(self.model_path, config_path=self.config_path)
                self._available = True
                logger.info("✓ Piper local neural TTS initialized with model: {}", os.path.basename(self.model_path))
            except Exception as e:
                logger.warning("Could not load Piper voice from {}: {}", self.model_path, e)
                self._available = False
        else:
            self._available = False

    def is_available(self) -> bool:
        if not self._available or self._voice is None:
            self._resolve_paths()
        return self._available and self._voice is not None

    def _synthesize_wav_sync(self, text: str) -> bytes:
        import wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)
        return buf.getvalue()

    async def stream(self, text: str, cancel_flag_fn) -> AsyncGenerator[bytes, None]:
        loop = asyncio.get_running_loop()
        wav_data = await loop.run_in_executor(None, self._synthesize_wav_sync, text)

        chunk_size = 4096
        for i in range(0, len(wav_data), chunk_size):
            if cancel_flag_fn():
                logger.info("Piper neural TTS stream cancelled by user barge-in")
                break
            yield wav_data[i : i + chunk_size]
            await asyncio.sleep(0.01)


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
                filestream.Open(tmp_path, 3, False)  # 3 = SSFMCreateForWrite
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

        chunk_size = 4096
        for i in range(0, len(wav_data), chunk_size):
            if cancel_flag_fn():
                logger.info("Local SAPI TTS stream cancelled by user barge-in")
                break
            yield wav_data[i : i + chunk_size]
            await asyncio.sleep(0.01)


class TTSManager:
    """
    Unified Text-to-Speech manager with multi-tier failover:
    Tier 1: Online Microsoft Edge-TTS (Streaming neural voice)
    Tier 2: Offline Local Piper TTS (Local ONNX neural voice)
    Tier 3: Offline Windows Native SAPI SpVoice (Guaranteed local fallback)
    Streams audio chunks asynchronously, supporting real-time playback and barge-in cancellation.
    """

    def __init__(
        self,
        voice: str = "en-US-GuyNeural",
        rate: str = "+0%",
        prefer_local: Optional[bool] = None,
    ) -> None:
        self.voice = voice
        self.rate = rate
        self._cancel_flag = False
        self._is_speaking_flag = False
        self.prefer_local = (
            (os.getenv("PREFER_LOCAL_TTS", "true").lower() == "true")
            if prefer_local is None
            else prefer_local
        )
        self.edge_provider = EdgeTTSProvider(voice=voice, rate=rate)
        self.piper_provider = PiperTTSProvider(rate=rate)
        self.local_provider = LocalTTSProvider(rate=rate)
        self.last_provider_used = "sapi" if self.prefer_local else "edge-tts"
        logger.info(
            "TTSManager initialised — voice={}, rate={}, prefer_local={}, offline_piper={}, offline_sapi=Ready",
            voice,
            rate,
            self.prefer_local,
            "Ready" if self.piper_provider.is_available() else "Standby",
        )

    # ── Public API ───────────────────────────────────────────────────────

    def is_speaking(self) -> bool:
        """Return whether TTS synthesis/playback is actively running."""
        return self._is_speaking_flag

    async def stream_speech(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Convert text to speech and yield audio chunks (WAV for local SAPI/Piper, MP3 for EdgeTTS).
        Prioritizes ultra-fast local SAPI/Piper (<250ms) when prefer_local is set.
        """
        if not text or not text.strip():
            logger.debug("TTS received empty text, skipping")
            return

        self._cancel_flag = False
        self._is_speaking_flag = True
        logger.info("TTS synthesizing — text='{}'", text[:60])

        try:
            # Priority Path: Ultra-Fast Local Synthesis (<250ms)
            if self.prefer_local:
                try:
                    self.last_provider_used = "sapi"
                    async for chunk in self.local_provider.stream(text, lambda: self._cancel_flag):
                        yield chunk
                    logger.info("✓ TTS stream completed via Local Ultra-Fast SAPI")
                    self._cancel_flag = False
                    return
                except Exception as sapi_err:
                    logger.warning("Local SAPI error: {}. Falling back to Edge-TTS/Piper...", sapi_err)

            # Online Edge-TTS Path
            edge_success = False
            try:
                async for chunk in self.edge_provider.stream(text, lambda: self._cancel_flag):
                    edge_success = True
                    self.last_provider_used = "edge-tts"
                    yield chunk
            except Exception as edge_err:
                logger.warning(
                    "⚠️ Edge-TTS failed ({}: {}). Failing over to Offline Neural Piper Provider...",
                    type(edge_err).__name__,
                    edge_err,
                )

            if edge_success:
                logger.debug("✓ TTS stream completed via Edge-TTS")
                self._cancel_flag = False
                return

            # Attempt 2: Resilient Local Neural Offline Piper Fallback
            if self.piper_provider.is_available():
                try:
                    logger.info("🎙️ Synthesizing speech via Local Offline Neural Piper Provider...")
                    self.last_provider_used = "piper"
                    async for chunk in self.piper_provider.stream(text, lambda: self._cancel_flag):
                        yield chunk
                    logger.info("✓ TTS stream completed via Local Offline Neural Piper")
                    self._cancel_flag = False
                    return
                except Exception as piper_err:
                    logger.warning("⚠️ Piper neural TTS failed ({}). Failing over to SAPI...", piper_err)

            # Attempt 3: Resilient Offline Windows SAPI Fallback
            try:
                logger.info("🎙️ Synthesizing speech via Local Offline SAPI Provider...")
                self.last_provider_used = "sapi"
                async for chunk in self.local_provider.stream(text, lambda: self._cancel_flag):
                    yield chunk
                logger.info("✓ TTS stream completed via Local Offline SAPI")
            except Exception as local_err:
                logger.error("❌ All TTS providers (Edge-TTS, Piper, SAPI) failed: {}", local_err)
        finally:
            self._cancel_flag = False
            self._is_speaking_flag = False

    async def synthesize(self, text: str) -> bytes:
        """Synthesise full audio bytes for a text string."""
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
        try:
            import edge_tts
            voices = await asyncio.wait_for(edge_tts.list_voices(), timeout=2.5)
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
                    "short_name": "en-US-David",
                    "gender": "Male",
                    "locale": "en-US",
                    "friendly_name": "Microsoft David (Offline SAPI)",
                },
                {
                    "name": "Microsoft Mark - English (United States)",
                    "short_name": "en-US-Mark",
                    "gender": "Male",
                    "locale": "en-US",
                    "friendly_name": "Microsoft Mark (Offline SAPI)",
                },
            ]
