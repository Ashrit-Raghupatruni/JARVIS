"""
JARVIS AI Desktop Assistant - Wake Word Detection Service.

Listens for the "hey jarvis" wake word using openwakeword,
processing 16 kHz mono PCM audio in 1280-sample (80 ms) chunks.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from backend.utils.logger import logger


class WakeWordService:
    """
    Wake word detection using openwakeword.

    Processes small audio chunks and returns ``True`` when the
    configured wake word is detected with sufficient confidence.
    """

    def __init__(self, threshold: float = 0.35) -> None:
        """
        Initialise the wake word service.

        Args:
            threshold: Confidence threshold (0.0–1.0) above which
                       a detection is triggered.
        """
        self.threshold = threshold
        self._model = None
        self._is_loaded = False
        self._warned_not_loaded = False
        self._last_detection_time: float = 0.0
        self._cooldown_seconds: float = 2.0  # Prevent rapid re-triggers
        logger.info("WakeWordService created — threshold={}", threshold)

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def load_model(self) -> None:
        """
        Load the openwakeword model.

        Should be called once during application startup.
        """
        if self._is_loaded:
            logger.debug("Wake word model already loaded")
            return

        import asyncio

        loop = asyncio.get_running_loop() if hasattr(asyncio, "get_running_loop") else asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model_sync)

    def _load_model_sync(self, wakeword_name: str = "hey_jarvis") -> None:
        """Synchronous model loading, run in a thread executor."""
        try:
            import openwakeword
            from openwakeword.model import Model

            # Download default models if not present
            openwakeword.utils.download_models()

            models_to_load = [wakeword_name] if wakeword_name else ["hey_jarvis"]
            try:
                self._model = Model(
                    wakeword_models=models_to_load,
                    inference_framework="onnx",
                )
                self.selected_model = wakeword_name
            except Exception as e:
                logger.warning("Could not load specific wake word model '{}': {}. Using default models.", wakeword_name, e)
                self._model = Model(inference_framework="onnx")
                self.selected_model = "default"

            self._is_loaded = True
            self._warned_not_loaded = False
            logger.info("Wake word model loaded successfully — model={}", self.selected_model)

        except Exception as e:
            logger.debug("Failed to load preferred wake word model: {}", e)
            # Attempt fallback with any available model
            try:
                import openwakeword
                from openwakeword.model import Model

                openwakeword.utils.download_models()
                self._model = Model(inference_framework="onnx")
                self._is_loaded = True
                self._warned_not_loaded = False
                self.selected_model = "fallback"
                logger.info("Wake word model loaded with default models (fallback)")
            except Exception as fallback_err:
                logger.warning("Wake word model not available: {}. Wake word detection disabled.", fallback_err)
                self._is_loaded = False
                self._model = None

    # ── Detection ────────────────────────────────────────────────────────

    def process_audio(self, audio_chunk: bytes) -> bool:
        """
        Process an audio chunk and check for the wake word.

        Expects 16 kHz, 16-bit, mono PCM audio. The recommended
        chunk size is 1280 samples (2560 bytes, 80 ms of audio).

        Args:
            audio_chunk: Raw PCM audio bytes.

        Returns:
            ``True`` if the wake word was detected above the
            configured threshold; ``False`` otherwise.
        """
        if not self._is_loaded or self._model is None:
            if not self._warned_not_loaded:
                logger.warning("Wake word model not loaded — wake word detection inactive.")
                self._warned_not_loaded = True
            return False

        # Cooldown check
        now = time.time()
        if now - self._last_detection_time < self._cooldown_seconds:
            return False

        try:
            # Convert bytes to int16 numpy array
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)

            # Run prediction
            prediction = self._model.predict(audio_array)

            # Check each model's score
            for model_name, score in prediction.items():
                if score >= self.threshold:
                    self._last_detection_time = now
                    logger.info(
                        "Wake word detected! model={}, score={:.3f}, threshold={}",
                        model_name, score, self.threshold,
                    )
                    self.reset()
                    return True

            return False

        except Exception as e:
            logger.error("Wake word processing error: {}", e)
            return False

    def process_audio_numpy(self, audio_array: np.ndarray) -> bool:
        """
        Process a numpy audio array for wake word detection.

        Args:
            audio_array: Int16 numpy array of audio samples at 16 kHz.

        Returns:
            ``True`` if the wake word was detected.
        """
        if not self._is_loaded or self._model is None:
            if not self._warned_not_loaded:
                logger.warning("Wake word model not loaded — wake word detection inactive.")
                self._warned_not_loaded = True
            return False

        now = time.time()
        if now - self._last_detection_time < self._cooldown_seconds:
            return False

        try:
            prediction = self._model.predict(audio_array)
            for model_name, score in prediction.items():
                if score >= self.threshold:
                    self._last_detection_time = now
                    logger.info(
                        "Wake word detected! model={}, score={:.3f}",
                        model_name, score,
                    )
                    self.reset()
                    return True
            return False

        except Exception as e:
            logger.error("Wake word numpy processing error: {}", e)
            return False

    # ── State Management ─────────────────────────────────────────────────

    def start_standalone_listener(self, event_bus=None, on_wake_word_callback=None, main_loop=None) -> None:
        """
        Starts a dedicated background hardware microphone capture thread via sounddevice.
        Runs continuous openwakeword inference even when the frontend browser is minimized or idle.
        """
        if getattr(self, "_listener_running", False):
            return

        import threading
        self._listener_running = True
        self.event_bus = event_bus
        self.on_wake_word_callback = on_wake_word_callback
        self.main_loop = main_loop

        def _bg_audio_loop():
            try:
                import sounddevice as sd
                chunk_samples = 1280
                logger.info("🎙️ Standalone Wake Word Background Microphone Listener Started (16kHz PCM).")

                def _callback(indata, frames, time_info, status):
                    if not self._listener_running:
                        return
                    pcm_bytes = indata.tobytes()
                    detected = self.process_audio(pcm_bytes)
                    if detected:
                        logger.info("🔥 [WakeWord Listener] Wake word 'Hey Jarvis' detected in background audio stream!")
                        if self.event_bus:
                            import asyncio
                            try:
                                target_loop = self.main_loop
                                if target_loop and target_loop.is_running():
                                    asyncio.run_coroutine_threadsafe(
                                        self.event_bus.publish("wake_word.detected", {"threshold": self.threshold}),
                                        target_loop
                                    )
                                else:
                                    logger.warning("Event bus available but main_loop is not running; skipping event bus publish.")
                            except Exception as e:
                                logger.error("Error publishing wake_word event: {}", e)

                        if self.on_wake_word_callback:
                            try:
                                self.on_wake_word_callback()
                            except Exception as e:
                                logger.error("Error in wake word callback: {}", e)

                with sd.InputStream(samplerate=16000, channels=1, dtype='int16', blocksize=chunk_samples, callback=_callback):
                    while self._listener_running:
                        time.sleep(0.2)
            except Exception as e:
                logger.error("Standalone Wake Word listener encountered error: {}", e)
                self._listener_running = False

        thread = threading.Thread(target=_bg_audio_loop, daemon=True, name="WakeWordBackgroundThread")
        thread.start()

    def reset(self) -> None:
        """
        Reset the internal detection state.

        Call this after a wake word is detected and handled to
        clear any accumulated audio context in the model.
        """
        if self._model is not None:
            try:
                self._model.reset()
                logger.debug("Wake word detection state reset")
            except Exception as e:
                logger.warning("Could not reset wake word model state: {}", e)

    def set_threshold(self, threshold: float) -> None:
        """
        Update the detection threshold.

        Args:
            threshold: New confidence threshold (0.0–1.0).
        """
        self.threshold = max(0.0, min(1.0, threshold))
        logger.info("Wake word threshold updated to {}", self.threshold)

    @property
    def is_loaded(self) -> bool:
        """Whether the wake word model is loaded."""
        return self._is_loaded

    def get_status(self) -> dict:
        """Return service status information."""
        return {
            "loaded": self._is_loaded,
            "threshold": self.threshold,
            "cooldown_seconds": self._cooldown_seconds,
            "background_listener_active": getattr(self, "_listener_running", False)
        }
