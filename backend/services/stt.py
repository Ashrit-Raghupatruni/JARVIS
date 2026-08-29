"""
JARVIS AI Desktop Assistant - Speech-to-Text Service.

Provides local speech-to-text transcription using faster-whisper,
a CTranslate2-optimised Whisper implementation for fast, accurate
offline transcription.
"""

from __future__ import annotations

import os
import io
import time
from typing import Optional

import numpy as np
from loguru import logger

import re

def clean_whisper_hallucinations(text: str) -> str:
    """Removes common Whisper static hallucinations and repeated-word loops."""
    if not text:
        return ""
    
    text = text.strip()
    
    # 1. Hallucinated repeated single words (e.g. "hi, hi, hi", "you, you, you")
    words = text.split()
    if len(words) >= 3:
        unique_words = set(w.lower().strip(".,!?") for w in words)
        if len(unique_words) == 1:
            logger.warning("Detected word repetition hallucination: '{}'", text)
            return list(unique_words)[0].capitalize()
            
    # 2. Hallucinated repeated phrases (e.g. "thank you thank you thank you")
    phrases = re.findall(r'\b(\w+\s+\w+)\b', text.lower())
    if phrases:
        from collections import Counter
        counts = Counter(phrases)
        most_common, count = counts.most_common(1)[0]
        if count >= 3 and (count * 2) >= len(words) * 0.6:
            logger.warning("Detected phrase repetition hallucination: '{}'", text)
            return most_common.capitalize()
            
    return text


class STTService:
    """
    Speech-to-text service using faster-whisper.

    Loads the Whisper model in the background and provides both
    byte-buffer and numpy-array transcription methods with VAD
    filtering for improved accuracy.
    """

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "auto",
        compute_type: str = "int8",
    ) -> None:
        """
        Initialise the STT service.

        The model is not loaded until :meth:`load_model` is called,
        allowing deferred initialisation during app startup.

        Args:
            model_size: Whisper model size — ``tiny``, ``base``, ``small``,
                        ``medium``, ``large-v2``, or ``large-v3``.
            device: Inference device — ``auto``, ``cpu``, or ``cuda``.
            compute_type: CTranslate2 compute type — ``int8``, ``float16``,
                          or ``float32``.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._is_loaded = False
        import threading
        self._load_lock = threading.Lock()
        logger.info(
            "STTService created — model={}, device={}, compute={}",
            model_size, device, compute_type,
        )
        # Pre-load Whisper in background thread executor immediately
        threading.Thread(target=self._load_model_sync, daemon=True).start()

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def load_model(self) -> None:
        """
        Load the faster-whisper model.

        This can take several seconds depending on the model size.
        Call this during application startup.
        """
        if self._is_loaded:
            logger.debug("Whisper model already loaded, skipping")
            return

        import asyncio

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model_sync)

    def _load_model_sync(self) -> None:
        """Synchronous model loading, run in a thread executor."""
        with self._load_lock:
            if self._is_loaded and self._model is not None:
                return

            try:
                from faster_whisper import WhisperModel

                start = time.perf_counter()

                # Resolve device
                device = self.device
                if device == "auto":
                    try:
                        import torch
                        device = "cuda" if torch.cuda.is_available() else "cpu"
                    except ImportError:
                        device = "cpu"

                # Adjust compute type for CPU
                compute = self.compute_type
                if device == "cpu" and compute == "float16":
                    compute = "int8"
                    logger.info("Switched compute_type to int8 for CPU device")

                cpu_threads = min(8, max(2, (os.cpu_count() or 4) // 2)) if device == "cpu" else 4

                self._model = WhisperModel(
                    self.model_size,
                    device=device,
                    compute_type=compute,
                    cpu_threads=cpu_threads,
                )
                elapsed = time.perf_counter() - start
                self._is_loaded = True
                logger.info(
                    "Whisper model loaded in {:.2f}s — size={}, device={}, compute={}, threads={}",
                    elapsed, self.model_size, device, compute, cpu_threads,
                )

            except Exception as e:
                logger.error("Failed to load Whisper model: {}", e)
                raise

    # ── Transcription ────────────────────────────────────────────────────

    async def transcribe(self, audio_data: bytes, use_cloud: bool = False) -> str:
        """
        Transcribe raw audio bytes to text using local faster-whisper.

        Expects 16-bit PCM audio at 16 kHz, mono channel. The audio
        is converted to a numpy float32 array before processing.

        Args:
            audio_data: Raw PCM audio bytes.
            use_cloud: Whether to attempt cloud API before local faster-whisper (default False).

        Returns:
            Transcribed text string (empty string if nothing detected).
        """
        # 1. Direct Ultra-Low Latency Local faster-whisper (Default Fast Path)
        if not use_cloud:
            if not self._is_loaded or self._model is None:
                logger.warning("STT model not loaded — attempting load now")
                await self.load_model()
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            return await self.transcribe_numpy(audio_array)

        # 2. Cloud Fallback (Optional, if explicitly requested)
        from backend.config import get_settings
        settings = get_settings()

        if settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("AIzaSy-your"):
            try:
                from google import genai
                from google.genai import types
                import wave

                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)  # 16-bit PCM
                    wav_file.setframerate(16000)
                    wav_file.writeframes(audio_data)

                wav_data = wav_buffer.getvalue()
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                model_name = settings.GEMINI_MODEL or "gemini-2.0-flash"

                logger.info(f"Transcribing speech via Google Gemini API ({model_name})...")
                start_time = time.perf_counter()

                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(
                            data=wav_data,
                            mime_type="audio/wav"
                        ),
                        "Transcribe the audio exactly as spoken. Do not include any translation, markdown formatting, explanations, or introductory remarks. Only output the transcribed text."
                    ]
                )
                text = response.text.strip()
                elapsed = time.perf_counter() - start_time
                if text:
                    logger.info("Gemini transcription completed in {:.2f}s — text='{}'", elapsed, text[:80])
                    return clean_whisper_hallucinations(text)
            except Exception as e:
                logger.error(f"Gemini API speech-to-text failed: {e}. Falling back to local Whisper...")

        if not self._is_loaded or self._model is None:
            await self.load_model()

        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        return await self.transcribe_numpy(audio_array)

    async def transcribe_numpy(self, audio_array: np.ndarray) -> str:
        """
        Transcribe a numpy array of audio samples to text.

        Args:
            audio_array: Float32 numpy array of audio samples,
                         normalised to [-1.0, 1.0], at 16 kHz sample rate.

        Returns:
            Transcribed text string.
        """
        if not self._is_loaded or self._model is None:
            logger.warning("STT model not loaded — attempting load now")
            await self.load_model()

        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_array)

    def _transcribe_sync(self, audio_array: np.ndarray) -> str:
        """
        Synchronous transcription, run in a thread executor.

        Args:
            audio_array: Float32 audio array.

        Returns:
            Transcribed text.
        """
        start = time.perf_counter()

        try:
            segments, info = self._model.transcribe(
                audio_array,
                beam_size=1,
                language="en",
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 250,
                    "speech_pad_ms": 100,
                    "threshold": 0.5,
                },
                without_timestamps=True,
            )

            # Collect all segment texts
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            full_text = " ".join(text_parts).strip()
            elapsed = time.perf_counter() - start

            if full_text:
                logger.info(
                    "Transcription completed in {:.2f}s — language={}, text='{}'",
                    elapsed, info.language, full_text[:80],
                )
            else:
                logger.debug("Transcription returned empty result in {:.2f}s", elapsed)

            return clean_whisper_hallucinations(full_text)

        except Exception as e:
            logger.error("Transcription error: {}", e)
            return ""

    async def transcribe_stream(
        self,
        audio_data: bytes | np.ndarray,
    ):
        """
        Stream interim transcription tokens and final transcription in real-time.

        Yields:
            Dict[str, Any] with keys:
                - type: "interim" or "final"
                - text: cumulative transcript text
                - segment: latest segment text chunk
                - is_final: bool (False for interim, True for final)
                - start: segment start timestamp (seconds)
                - end: segment end timestamp (seconds)
        """
        if not self._is_loaded or self._model is None:
            await self.load_model()

        if isinstance(audio_data, bytes):
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio_array = audio_data

        import asyncio
        import threading

        msg_queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _worker():
            try:
                segments, info = self._model.transcribe(
                    audio_array,
                    beam_size=1,
                    language="en",
                    temperature=0.0,
                    condition_on_previous_text=False,
                    vad_filter=True,
                    vad_parameters={
                        "min_silence_duration_ms": 250,
                        "speech_pad_ms": 100,
                        "threshold": 0.5,
                    },
                    without_timestamps=False,
                )
                accumulated = []
                for segment in segments:
                    seg_text = segment.text.strip()
                    if seg_text:
                        accumulated.append(seg_text)
                        partial_text = " ".join(accumulated).strip()
                        cleaned_partial = clean_whisper_hallucinations(partial_text)
                        loop.call_soon_threadsafe(
                            msg_queue.put_nowait,
                            {
                                "type": "interim",
                                "segment": seg_text,
                                "text": cleaned_partial,
                                "start": round(float(getattr(segment, "start", 0.0)), 2),
                                "end": round(float(getattr(segment, "end", 0.0)), 2),
                                "is_final": False,
                            }
                        )
                final_text = clean_whisper_hallucinations(" ".join(accumulated).strip())
                loop.call_soon_threadsafe(
                    msg_queue.put_nowait,
                    {
                        "type": "final",
                        "segment": "",
                        "text": final_text,
                        "start": 0.0,
                        "end": 0.0,
                        "is_final": True,
                    }
                )
            except Exception as e:
                logger.error(f"Streaming transcription error: {e}")
                loop.call_soon_threadsafe(
                    msg_queue.put_nowait,
                    {"type": "error", "error": str(e), "is_final": True}
                )
            finally:
                loop.call_soon_threadsafe(msg_queue.put_nowait, None)

        threading.Thread(target=_worker, daemon=True).start()

        while True:
            item = await msg_queue.get()
            if item is None:
                break
            yield item

    # ── Properties ───────────────────────────────────────────────────────

    transcribe_bytes = transcribe

    @property
    def is_loaded(self) -> bool:
        """Whether the Whisper model is loaded and ready."""
        return self._is_loaded

    def get_status(self) -> dict:
        """Return service status information."""
        return {
            "loaded": self._is_loaded,
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "streaming_supported": True,
        }

