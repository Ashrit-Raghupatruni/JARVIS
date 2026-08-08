"""
JARVIS AI OS - Request Envelope & Input Normalizer Schema.

Provides standardized request envelopes across WebSockets, REST API,
voice streams, and mobile companion app with explicit request_id,
session_id, source, modality, and priority routing.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RequestSource(str, Enum):
    DESKTOP_UI = "desktop_ui"
    VOICE_STREAM = "voice_stream"
    SIRI_WIDGET = "siri_widget"
    MOBILE_APP = "mobile_app"
    BACKGROUND_THREAD = "background_thread"
    SYSTEM_CRON = "system_cron"


class RequestModality(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    VISION = "vision"
    GESTURE = "gesture"
    HYBRID = "hybrid"


class RequestPriority(str, Enum):
    INTERACTIVE = "interactive"  # High-priority user real-time request
    BACKGROUND = "background"    # Async background task execution
    TELEMETRY = "telemetry"      # Passive perception / telemetry update


class RequestEnvelope(BaseModel):
    """Standardized envelope wrapping all incoming commands."""
    request_id: str = Field(default_factory=lambda: f"req_{uuid.uuid4().hex[:8]}")
    session_id: str = Field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:8]}")
    source: RequestSource = RequestSource.DESKTOP_UI
    modality: RequestModality = RequestModality.TEXT
    priority: RequestPriority = RequestPriority.INTERACTIVE
    timestamp: float = Field(default_factory=time.time)
    payload: Dict[str, Any] = Field(default_factory=dict)


class InputNormalizer:
    """Converts raw WebSocket JSON or REST parameters into validated RequestEnvelopes."""

    @staticmethod
    def normalize_ws_message(
        raw_data: Dict[str, Any], default_session_id: Optional[str] = None
    ) -> RequestEnvelope:
        msg_type = raw_data.get("type", "text_command")
        data = raw_data.get("data", {})

        # Determine modality
        modality = RequestModality.TEXT
        if msg_type in ("audio", "audio_data"):
            modality = RequestModality.AUDIO
        elif msg_type == "hand_action":
            modality = RequestModality.GESTURE
        elif msg_type == "live_frame":
            modality = RequestModality.VISION

        # Determine source
        src_str = raw_data.get("source", "desktop_ui")
        try:
            source = RequestSource(src_str)
        except ValueError:
            source = RequestSource.DESKTOP_UI

        # Determine priority
        priority = RequestPriority.INTERACTIVE
        if msg_type in ("ping", "heartbeat", "status"):
            priority = RequestPriority.TELEMETRY

        session_id = (
            raw_data.get("session_id")
            or default_session_id
            or f"sess_{uuid.uuid4().hex[:8]}"
        )

        return RequestEnvelope(
            request_id=raw_data.get("request_id") or f"req_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            source=source,
            modality=modality,
            priority=priority,
            payload={"type": msg_type, "data": data},
        )
