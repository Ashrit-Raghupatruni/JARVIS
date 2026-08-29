"""
JARVIS AI OS — Deterministic Fast Intent Router.
================================================
Evaluates user text and voice command transcripts in sub-millisecond time (< 0.5ms) on CPU.
Directs atomic, single-turn deterministic commands directly to ToolRegistry + SafetyGatekeeper,
while strictly rejecting compound clauses, complex workflows, and ambiguous requests to PlannerAgent.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from loguru import logger


@dataclass
class FastIntentResult:
    """Structured classification result produced by FastIntentRouter."""
    is_atomic: bool
    tool_name: Optional[str] = None
    tool_params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    ack_phrase: Optional[str] = None
    completion_phrase: Optional[str] = None
    reason: Optional[str] = None
    routing_time_ms: float = 0.0


class FastIntentRouter:
    """
    Sub-millisecond CPU-bound deterministic intent router for atomic OS commands.
    """

    # Conjunctions & multi-step marker words that disqualify a request from the fast path
    COMPOUND_MARKERS = [
        " and ", " then ", " after that ", " afterwards ", " & ",
        " summarize ", " explain ", " research ", " create a ", " generate ",
        " fix ", " write a ", " find and ", " if ", " why ", " how to ",
        " compare ", " analyze ", " plan ", " debug "
    ]

    # Blocked dangerous keywords that must never be auto-executed on fast path
    HIGH_RISK_KEYWORDS = [
        "delete", "remove", "erase", "format", "shutdown", "reboot",
        "restart", "wipe", "regedit", "kill -9", "drop table", "rmdir",
        "system32", "cleanmgr", "diskpart"
    ]

    def __init__(self) -> None:
        self._compile_patterns()
        logger.info("FastIntentRouter initialized with compiled deterministic matchers.")

    def _compile_patterns(self) -> None:
        """Compile regex patterns for high-frequency atomic action classes."""
        # 1. Lock Computer
        self._re_lock = re.compile(
            r"^(?:lock|lock\s+(?:the|my)?\s*(?:pc|computer|workstation|laptop|screen))$",
            re.IGNORECASE
        )

        # 2. Screenshot
        self._re_screenshot = re.compile(
            r"^(?:take\s+(?:a\s+)?screenshot|capture\s+(?:the\s+)?screen|screenshot)$",
            re.IGNORECASE
        )

        # 3. Open Application
        self._re_open_app = re.compile(
            r"^(?:open|launch|start)\s+([a-zA-Z0-9\s\.\-_]+)$",
            re.IGNORECASE
        )

        # 4. Close Application
        self._re_close_app = re.compile(
            r"^(?:close|quit|kill|exit)\s+([a-zA-Z0-9\s\.\-_]+)$",
            re.IGNORECASE
        )

        # 5. System Status / Metrics
        self._re_system_status = re.compile(
            r"^(?:what\s+is\s+my\s+|check\s+|show\s+|get\s+)?(?:system|cpu|ram|battery|disk|memory)\s*(?:status|metrics|level|usage)?$",
            re.IGNORECASE
        )

        # 6. Media Controls
        self._re_media_play_pause = re.compile(
            r"^(?:play|pause|resume|media\s+play|media\s+pause|play\s+music|pause\s+music|stop\s+music)$",
            re.IGNORECASE
        )
        self._re_media_next = re.compile(
            r"^(?:next\s+track|next\s+song|skip\s+track|skip\s+song)$",
            re.IGNORECASE
        )
        self._re_media_prev = re.compile(
            r"^(?:previous\s+track|previous\s+song|prev\s+song|last\s+song)$",
            re.IGNORECASE
        )
        self._re_volume_mute = re.compile(
            r"^(?:mute|unmute|mute\s+volume|unmute\s+volume)$",
            re.IGNORECASE
        )

        # 7. Live Mode Toggle
        self._re_live_mode_on = re.compile(
            r"^(?:turn\s+on|enable|start)\s+live\s+mode$",
            re.IGNORECASE
        )
        self._re_live_mode_off = re.compile(
            r"^(?:turn\s+off|disable|stop)\s+live\s+mode$",
            re.IGNORECASE
        )

        # 8. Bluetooth Proximity Telemetry
        self._re_proximity = re.compile(
            r"^(?:check\s+|show\s+|get\s+)?(?:bluetooth|proximity|rssi)\s*(?:status|signal|telemetry)?$",
            re.IGNORECASE
        )

        # 9. Email / Calendar Quick Status
        self._re_unread_emails = re.compile(
            r"^(?:check\s+|show\s+|list\s+|read\s+)?(?:my\s+)?(?:unread\s+)?(?:emails|gmail|inbox)$",
            re.IGNORECASE
        )
        self._re_calendar_today = re.compile(
            r"^(?:what\s+is\s+|show\s+|check\s+|list\s+)?(?:my\s+)?(?:today'?s?\s+)?(?:schedule|calendar|meetings|events)$",
            re.IGNORECASE
        )

    def classify(self, user_prompt: str) -> FastIntentResult:
        """
        Classifies user prompt into an atomic tool call intent or falls back to Planner.
        Guaranteed to execute in < 1.0ms on standard CPUs.
        """
        start_t = time.perf_counter()
        raw = user_prompt.strip()
        cleaned = raw.lower()

        # ── 1. Fast Disqualification Guards ─────────────────────────────
        if not raw:
            return FastIntentResult(
                is_atomic=False,
                confidence=0.0,
                reason="Empty input string",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # Excessive sentence length -> complex or conversational
        if len(raw) > 100:
            return FastIntentResult(
                is_atomic=False,
                confidence=0.0,
                reason="Input length exceeds atomic single-turn threshold (>100 chars)",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # Reject compound sentences with conjunctions or chaining markers
        for marker in self.COMPOUND_MARKERS:
            if marker in f" {cleaned} ":
                return FastIntentResult(
                    is_atomic=False,
                    confidence=0.0,
                    reason=f"Compound marker detected: '{marker.strip()}'",
                    routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
                )

        # Reject destructive high-risk operations from fast path (must go through Planner & Safety Gate)
        for dangerous in self.HIGH_RISK_KEYWORDS:
            if dangerous in cleaned:
                return FastIntentResult(
                    is_atomic=False,
                    confidence=0.0,
                    reason=f"Potentially destructive keyword '{dangerous}' requires full Planner safety graph",
                    routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
                )

        # ── 2. Deterministic Pattern Matching ────────────────────────────

        # A. Lock Computer
        if self._re_lock.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="lock_pc",
                tool_params={},
                confidence=1.0,
                ack_phrase="Locking workstation, sir.",
                completion_phrase="Workstation locked and secured.",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # B. Screenshot
        if self._re_screenshot.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="take_screenshot",
                tool_params={},
                confidence=1.0,
                ack_phrase="Capturing screen, sir.",
                completion_phrase="Screenshot captured and saved to artifacts.",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # C. System Status
        if self._re_system_status.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="get_system_status",
                tool_params={},
                confidence=0.98,
                ack_phrase="Checking system telemetry, sir...",
                completion_phrase=None,  # Will use output of system_status
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # D. Media Controls
        if self._re_media_play_pause.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="media_control",
                tool_params={"action": "play_pause"},
                confidence=0.98,
                ack_phrase="Toggling media playback, sir.",
                completion_phrase="Media playback toggled.",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        if self._re_media_next.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="media_control",
                tool_params={"action": "next_track"},
                confidence=0.98,
                ack_phrase="Skipping to next track, sir.",
                completion_phrase="Skipped to next track.",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        if self._re_media_prev.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="media_control",
                tool_params={"action": "prev_track"},
                confidence=0.98,
                ack_phrase="Returning to previous track, sir.",
                completion_phrase="Returned to previous track.",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        if self._re_volume_mute.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="media_control",
                tool_params={"action": "mute"},
                confidence=0.98,
                ack_phrase="Toggling volume mute, sir.",
                completion_phrase="System volume muted/unmuted.",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # E. Live Mode Toggle
        if self._re_live_mode_on.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="toggle_live_mode",
                tool_params={"enable": True},
                confidence=1.0,
                ack_phrase="Activating Live Mode desktop perception, sir.",
                completion_phrase="Live Mode is now active.",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        if self._re_live_mode_off.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="toggle_live_mode",
                tool_params={"enable": False},
                confidence=1.0,
                ack_phrase="Deactivating Live Mode, sir.",
                completion_phrase="Live Mode has been deactivated.",
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # F. Bluetooth Proximity Telemetry
        if self._re_proximity.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="get_proximity_telemetry",
                tool_params={},
                confidence=0.98,
                ack_phrase="Reading Bluetooth RSSI proximity telemetry, sir...",
                completion_phrase=None,
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # G. Open Application
        m_open = self._re_open_app.match(cleaned)
        if m_open:
            app_target = m_open.group(1).strip()
            # Ensure target is a single bounded app name (<= 3 words, no punctuation verbs)
            if len(app_target.split()) <= 3 and not any(w in app_target for w in ["the", "this", "file", "folder", "document"]):
                return FastIntentResult(
                    is_atomic=True,
                    tool_name="open_application",
                    tool_params={"app_name": app_target},
                    confidence=0.98,
                    ack_phrase=f"Opening {app_target.title()}, sir...",
                    completion_phrase=f"{app_target.title()} is open and ready.",
                    routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
                )

        # H. Close Application
        m_close = self._re_close_app.match(cleaned)
        if m_close:
            app_target = m_close.group(1).strip()
            if len(app_target.split()) <= 3:
                return FastIntentResult(
                    is_atomic=True,
                    tool_name="close_application",
                    tool_params={"app_name": app_target},
                    confidence=0.98,
                    ack_phrase=f"Closing {app_target.title()}, sir...",
                    completion_phrase=f"{app_target.title()} has been closed.",
                    routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
                )

        # I. Unread Emails Check
        if self._re_unread_emails.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="gmail_list_messages",
                tool_params={"query": "is:unread", "max_results": 5},
                confidence=0.95,
                ack_phrase="Fetching unread Gmail messages, sir...",
                completion_phrase=None,
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # J. Today's Calendar Schedule
        if self._re_calendar_today.match(cleaned):
            return FastIntentResult(
                is_atomic=True,
                tool_name="google_calendar_list_events",
                tool_params={"max_results": 5},
                confidence=0.95,
                ack_phrase="Fetching today's schedule from Google Calendar, sir...",
                completion_phrase=None,
                routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
            )

        # ── 3. Fallback to Planner / ReAct Loop ──────────────────────────
        return FastIntentResult(
            is_atomic=False,
            confidence=0.0,
            reason="No atomic pattern match — routing to PlannerAgent",
            routing_time_ms=round((time.perf_counter() - start_t) * 1000, 3)
        )


fast_intent_router = FastIntentRouter()
