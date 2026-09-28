"""
JARVIS AI Desktop Assistant - Speech-to-Text Manager & Service.

Provides local speech-to-text transcription using faster-whisper (CTranslate2),
with on-demand lazy loading, streaming token generation, VAD filtering,
and hallucination suppression.
"""

from __future__ import annotations

import io
import os
import re
import threading
import time
from typing import Any, AsyncGenerator, Dict, Optional

import numpy as np
from loguru import logger


NOISE_WORDS = {
    "uh", "um", "ah", "er", "hmm", "shh", "oh", "watching", "subtitles",
    "[music]", "[applause]", "you", "thanks for watching", "thank you for watching"
}


def is_valid_transcript(text: str) -> bool:
    """Validates that a transcript contains substantive, non-noise human speech."""
    if not text:
        return False
    t = text.strip()
    alnum = re.sub(r"[\W_]+", "", t)
    # Reject single-character or empty alphanumeric transcripts (e.g. 'I', 'a', '.')
    if len(alnum) <= 1:
        return False
    if t.lower() in NOISE_WORDS:
        return False
    words = [w.lower().strip(".,!?") for w in t.split() if w.strip(".,!?")]
    if not words:
        return False
    # Reject pure repetitive stutter without substantive words (e.g. 'who who who')
    if len(words) >= 3 and len(set(words)) == 1:
        return False
    return True


def clean_whisper_hallucinations(text: str) -> str:
    """Removes common Whisper static hallucinations, hyphenated stutters, and repeated-word loops."""
    if not text:
        return ""

    text = text.strip()

    # 1. Hyphenated stutter loops (e.g. "Who-who-who" -> "Who")
    text = re.sub(
        r"\b([a-zA-Z]+)(?:-[a-zA-Z]+)+\b",
        lambda m: m.group(1) if len(set(m.group(0).lower().split("-"))) == 1 else m.group(0),
        text,
        flags=re.IGNORECASE,
    )

    # 2. Hallucinated repeated single words (e.g. "hi, hi, hi", "you, you, you")
    words = text.split()
    if len(words) >= 3:
        unique_words = set(w.lower().strip(".,!?") for w in words)
        if len(unique_words) == 1:
            logger.warning("Detected word repetition hallucination: '{}'", text)
            return list(unique_words)[0].capitalize()

    # 3. Hallucinated repeated phrases (e.g. "thank you thank you thank you")
    phrases = re.findall(r"\b(\w+\s+\w+)\b", text.lower())
    if phrases:
        from collections import Counter
        counts = Counter(phrases)
        most_common, count = counts.most_common(1)[0]
        phrase_words = set(most_common.split())
        words_cleaned = set(w.lower().strip(".,!?") for w in words)
        if count >= 3 and words_cleaned == phrase_words:
            logger.warning("Detected phrase repetition hallucination: '{}'", text)
            return most_common.capitalize()

    # 4. Collapse consecutive duplicate words or multi-word phrases with comma or whitespace
    # (e.g. "How many How many", "How many, how many", "open open")
    prev = None
    cleaned = text
    while prev != cleaned:
        prev = cleaned
        cleaned = re.sub(r"\b((?:\w+[\s,]+){0,3}\w+)[,\s]+\1\b", r"\1", cleaned, flags=re.IGNORECASE)

    # 5. Clean up any duplicated leading words
    cleaned_words = cleaned.split()
    if len(cleaned_words) >= 2 and cleaned_words[0].lower().strip(".,!?") == cleaned_words[1].lower().strip(".,!?"):
        cleaned = " ".join(cleaned_words[1:])

    return cleaned.strip()


class STTManager:
    """
    Speech-to-text manager using faster-whisper with lazy loading.

    Loads the Whisper model strictly on demand and provides both
    byte-buffer and numpy-array transcription with VAD filtering.
    """

    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "auto",
        compute_type: str = "int8",
        eager_load: bool = False,
    ) -> None:
        """
        Initialise the STT manager.
        The model is NOT loaded until needed or until load_model() is called.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._is_loaded = False
        self._load_lock = threading.Lock()
        logger.info(
            "STTManager created — model={}, device={}, compute={}",
            model_size, device, compute_type,
        )
        if eager_load:
            threading.Thread(target=self._load_model_sync, daemon=True).start()

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def load_model(self) -> None:
        """Asynchronously load the faster-whisper model."""
        if self._is_loaded and self._model is not None:
            return

        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        await loop.run_in_executor(None, self._load_model_sync)

    def _load_model_sync(self) -> None:
        """Synchronous model loading, thread-safe."""
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

    def unload_model(self) -> None:
        """Unload Whisper model and free memory."""
        with self._load_lock:
            self._model = None
            self._is_loaded = False
            logger.info("Whisper model unloaded.")

    # ── Transcription ────────────────────────────────────────────────────

    async def transcribe(self, audio_data: bytes, use_cloud: bool = False) -> str:
        """
        Transcribe raw PCM audio bytes to text using local faster-whisper.
        Expects 16-bit PCM mono audio at 16 kHz.
        """
        if not use_cloud:
            if not self._is_loaded or self._model is None:
                await self.load_model()
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            return await self.transcribe_numpy(audio_array)

        # Cloud Fallback (if requested)
        from backend.config import get_settings
        settings = get_settings()

        if settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("AIzaSy-your"):
            try:
                from google import genai
                from google.genai import types
                import wave

                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, "wb") as wav_file:
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
                        types.Part.from_bytes(data=wav_data, mime_type="audio/wav"),
                        "Transcribe the audio exactly as spoken. Do not include any translation, markdown formatting, explanations, or introductory remarks. Only output the transcribed text.",
                    ],
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
        """Transcribe a float32 numpy array of audio samples [-1.0, 1.0] at 16 kHz."""
        if not self._is_loaded or self._model is None:
            await self.load_model()

        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_array)

    def _transcribe_sync(self, audio_array: np.ndarray) -> str:
        """Synchronous transcription."""
        if not self._is_loaded or self._model is None:
            self._load_model_sync()

        start = time.perf_counter()
        try:
            segments, info = self._model.transcribe(
                audio_array,
                beam_size=1,
                language="en",
                temperature=0.0,
                condition_on_previous_text=False,
                repetition_penalty=1.2,
                no_repeat_ngram_size=3,
                hallucination_silence_threshold=1.5,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 250,
                    "speech_pad_ms": 100,
                    "threshold": 0.5,
                },
                without_timestamps=True,
            )

            text_parts = [segment.text.strip() for segment in segments]
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
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream interim transcription tokens and final transcription in real-time."""
        if not self._is_loaded or self._model is None:
            await self.load_model()

        if isinstance(audio_data, bytes):
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio_array = audio_data

        import asyncio

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
                    repetition_penalty=1.2,
                    no_repeat_ngram_size=3,
                    hallucination_silence_threshold=1.5,
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
                            },
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
                    },
                )
            except Exception as e:
                logger.error(f"Streaming transcription error: {e}")
                loop.call_soon_threadsafe(
                    msg_queue.put_nowait,
                    {"type": "error", "error": str(e), "is_final": True},
                )
            finally:
                loop.call_soon_threadsafe(msg_queue.put_nowait, None)

        threading.Thread(target=_worker, daemon=True).start()

        while True:
            item = await msg_queue.get()
            if item is None:
                break
            yield item

    # ── Properties & Compatibility ───────────────────────────────────────

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
