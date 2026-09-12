"""
Audio Device & Buffer Manager for JARVIS Voice Architecture.

Handles safe sounddevice microphone stream acquisition, device queries,
RMS volume computation, and audio buffer management with overflow guards.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np
from loguru import logger


class AudioDeviceManager:
    """Manages audio capture hardware devices, stream buffers, and acoustic metrics."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._max_buffer_bytes: int = 5 * 1024 * 1024  # 5MB buffer safety guard
        self._audio_buffer: bytearray = bytearray()
        self._is_capturing: bool = False

    def list_audio_devices(self) -> List[Dict[str, Any]]:
        """List available input and output audio devices safely."""
        devices = []
        try:
            import sounddevice as sd
            dev_list = sd.query_devices()
            for idx, dev in enumerate(dev_list):
                devices.append({
                    "id": idx,
                    "name": dev.get("name", f"Device {idx}"),
                    "max_input_channels": dev.get("max_input_channels", 0),
                    "max_output_channels": dev.get("max_output_channels", 0),
                    "default_samplerate": dev.get("default_samplerate", 44100),
                    "is_default_input": idx == sd.default.device[0] if (sd.default.device and sd.default.device[0] is not None) else False,
                    "is_default_output": idx == sd.default.device[1] if (sd.default.device and len(sd.default.device) > 1 and sd.default.device[1] is not None) else False,
                })
        except Exception as e:
            logger.debug("Could not enumerate audio devices via sounddevice: {}", e)
        return devices

    @staticmethod
    def calculate_rms(audio_bytes: bytes, dtype=np.int16) -> float:
        """Compute RMS volume level from PCM audio bytes."""
        if not audio_bytes:
            return 0.0
        try:
            arr = np.frombuffer(audio_bytes, dtype=dtype).astype(np.float32)
            if arr.size == 0:
                return 0.0
            rms = float(np.sqrt(np.mean(arr ** 2)))
            return rms
        except Exception:
            return 0.0

    @staticmethod
    def pcm_to_float32(audio_bytes: bytes) -> np.ndarray:
        """Convert 16-bit PCM bytes to normalized float32 numpy array [-1.0, 1.0]."""
        if not audio_bytes:
            return np.array([], dtype=np.float32)
        return np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    def append_chunk(self, chunk: bytes) -> Dict[str, Any]:
        """Buffer incoming streaming PCM audio chunks with memory-leak protection."""
        if not chunk:
            return {"status": "empty", "current_buffer_bytes": len(self._audio_buffer)}

        if len(self._audio_buffer) + len(chunk) > self._max_buffer_bytes:
            logger.warning(
                "Audio buffer limit reached ({}MB). Truncating oldest frames.",
                self._max_buffer_bytes // (1024 * 1024),
            )
            self._audio_buffer = self._audio_buffer[-(self._max_buffer_bytes // 2):]

        self._audio_buffer.extend(chunk)
        return {
            "status": "buffering",
            "current_buffer_bytes": len(self._audio_buffer),
        }

    def clear_buffer(self) -> int:
        """Clear the audio buffer and return cleared byte count."""
        cleared = len(self._audio_buffer)
        self._audio_buffer.clear()
        return cleared

    def get_buffer_bytes(self) -> bytes:
        """Return a copy of the current buffer contents."""
        return bytes(self._audio_buffer)
