"""
JARVIS AI OS - Session Trace Logger & Observability Engine.

Records structured execution traces to logs/traces/session_<id>.jsonl
for visual replay, failure analysis, and experience learning.
Includes automatic sensitive data redaction (privacy enforcement).
"""

from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.utils.logger import logger
from backend.config import PROJECT_ROOT

TRACE_DIR = PROJECT_ROOT / "logs" / "traces"
TRACE_DIR.mkdir(parents=True, exist_ok=True)


class SessionTraceLogger:
    """Session event logger recording structured execution steps for observability and replay."""

    def __init__(self, session_id: str = "global") -> None:
        self.session_id = session_id
        self.trace_file = TRACE_DIR / f"session_{session_id}.jsonl"

    def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Appends a redacted, structured trace event line to the session JSONL file."""
        redacted_data = self._redact_sensitive_data(data)
        event_record = {
            "session_id": self.session_id,
            "timestamp": time.time(),
            "event_type": event_type,
            "data": redacted_data,
        }
        try:
            with open(self.trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_record) + "\n")
        except Exception as err:
            logger.warning(f"Failed to record session trace event: {err}")

    def _redact_sensitive_data(self, obj: Any) -> Any:
        """Redacts raw images, PCM audio, passwords, and API keys to prevent security leaks in trace logs."""
        if isinstance(obj, dict):
            cleaned = {}
            for k, v in obj.items():
                lower_k = str(k).lower()
                if any(sec in lower_k for sec in ["password", "secret", "token", "api_key", "auth"]):
                    cleaned[k] = "[REDACTED_SECRET]"
                elif lower_k in ("screenshot", "image_base64", "audio_pcm"):
                    cleaned[k] = f"[RAW_BINARY_REFERENCE_LEN_{len(str(v))}]"
                else:
                    cleaned[k] = self._redact_sensitive_data(v)
            return cleaned
        elif isinstance(obj, list):
            return [self._redact_sensitive_data(item) for item in obj[:20]]
        return obj

    @staticmethod
    def get_session_trace(session_id: str) -> List[Dict[str, Any]]:
        """Reads and returns all recorded events for a given session ID."""
        trace_file = TRACE_DIR / f"session_{session_id}.jsonl"
        if not trace_file.exists():
            return []
        events = []
        try:
            with open(trace_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line.strip()))
        except Exception as err:
            logger.error(f"Error reading session trace '{session_id}': {err}")
        return events


# Backward compatibility alias for ObservabilitySkill
ObservabilityService = SessionTraceLogger
