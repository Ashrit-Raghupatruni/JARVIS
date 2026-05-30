"""
JARVIS AI Desktop Assistant - Speech-to-Text Service.

Provides local speech-to-text transcription using faster-whisper,
a CTranslate2-optimised Whisper implementation for fast, accurate
offline transcription.
"""

from __future__ import annotations

import io
import time
from typing import Optional

import numpy as np

from backend.utils.logger import logger


class STTService:
    """
    Speech-to-text service using faster-whisper.

    Loads the Whisper model in the background and provides both
    byte-buffer and numpy-array transcription methods with VAD
    filtering for improved accuracy.
    """

    def __init__(
        self,
        model_size: str = "small",
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
        logger.info(
            "STTService created — model={}, device={}, compute={}",
            model_size, device, compute_type,
        )

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

            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute,
            )
            elapsed = time.perf_counter() - start
            self._is_loaded = True
            logger.info(
                "Whisper model loaded in {:.2f}s — size={}, device={}, compute={}",
                elapsed, self.model_size, device, compute,
            )

        except Exception as e:
            logger.error("Failed to load Whisper model: {}", e)
            raise

    # ── Transcription ────────────────────────────────────────────────────

    async def transcribe(self, audio_data: bytes) -> str:
        """
        Transcribe raw audio bytes to text.

        Expects 16-bit PCM audio at 16 kHz, mono channel. The audio
        is converted to a numpy float32 array before processing.

        Args:
            audio_data: Raw PCM audio bytes.

        Returns:
            Transcribed text string (empty string if nothing detected).
        """
        if not self._is_loaded or self._model is None:
            logger.warning("STT model not loaded — attempting load now")
            await self.load_model()

        # Convert bytes to float32 numpy array
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
                beam_size=5,
                language="en",
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 200,
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

            return full_text

        except Exception as e:
            logger.error("Transcription error: {}", e)
            return ""

    # ── Properties ───────────────────────────────────────────────────────

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
        }
