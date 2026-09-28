"""
Parallel Racing LLM Provider Selection (Top-3).
==============================================
Implements a racing circuit pattern for LLM provider selection that executes
requests in parallel across the top 3 ranked providers, selects the fastest
valid response, and immediately aborts the remaining pending requests.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

from backend.utils.logger import logger


# Common API and runtime error patterns that must fail response validation
ERROR_PATTERNS: List[str] = [
    "timeout",
    "connection refused",
    "connection error",
    "quota exceeded",
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "429",
    "503 service unavailable",
    "internal server error",
    "unauthorized",
    "invalid api key",
    "invalid_api_key",
    "circuit breaker tripped",
    "name 're' is not defined",
]


def calculate_text_entropy(text: str) -> float:
    """
    Calculate Shannon entropy (base 2) of a text string.
    Natural English text typically has character entropy between 3.5 and 4.8.
    Completely random noise or high-entropy gibberish typically exceeds 6.0.
    """
    if not text or not text.strip():
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def is_valid_response(
    full_text: str,
    tool_calls: Optional[List[Any]] = None,
    events: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, str]:
    """
    Validate an LLM response against the core validation criteria:
    1. Response must be non-null and length > 10 characters (or contain valid tool calls)
    2. Response must not contain error patterns ("timeout", "connection refused", "quota exceeded", etc.)
    3. Response entropy must be < 6.0 (to avoid gibberish)
    4. Stream status must be OK (no explicit error events)
    """
    # 1. Check for error event frames
    if events:
        for ev in events:
            if ev.get("type") == "error":
                return False, f"Event stream contained error: {ev.get('error')}"

    # 2. Tool calls represent valid structured execution intents
    if tool_calls and len(tool_calls) > 0:
        return True, "Valid tool calls"

    # 3. Non-null string check
    if not full_text or not isinstance(full_text, str):
        return False, "Response is null or empty"

    stripped = full_text.strip()

    # 4. Minimum length requirement (> 10 characters)
    if len(stripped) <= 10:
        return False, f"Response length ({len(stripped)}) <= 10 characters"

    # 5. Error pattern check
    lower = stripped.lower()
    for pattern in ERROR_PATTERNS:
        if pattern in lower:
            return False, f"Response contains error pattern '{pattern}'"

    # 6. Shannon entropy check (< 6.0)
    entropy = calculate_text_entropy(stripped)
    if entropy >= 6.0:
        return False, f"Response entropy ({entropy:.2f}) >= 6.0 (gibberish detected)"

    return True, "Valid"


@dataclass
class RaceCandidateResult:
    """Individual candidate output from a provider race."""
    provider: str
    success: bool
    latency: float
    events: List[Dict[str, Any]] = field(default_factory=list)
    full_text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    entropy: float = 0.0
    error_msg: Optional[str] = None
    finish_timestamp: float = 0.0


@dataclass
class RaceResult:
    """Consolidated outcome of the parallel racing circuit."""
    winner: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    full_text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    latency: float = 0.0
    entropy: float = 0.0
    all_failed: bool = False
    error: Optional[str] = None
    candidates_raced: List[str] = field(default_factory=list)
    cancelled_providers: List[str] = field(default_factory=list)
    slower_valid_providers: List[str] = field(default_factory=list)
    failed_providers: List[Dict[str, Any]] = field(default_factory=list)


class LLMRacingCircuit:
    """
    Racing circuit pattern orchestrator for top-ranked LLM providers.
    - Executes top 3 ranked providers in parallel
    - Returns fastest valid response (< 6.0 entropy, > 10 chars, no error tokens)
    - Aborts losing pending tasks immediately to save tokens and sockets
    - Updates speed scores, participation points, and latency moving averages
    """

    def __init__(self, service: Any, router: Any) -> None:
        self.service = service
        self.router = router

        # Timeouts (in seconds)
        self.individual_timeout: float = 15.0  # 15s individual provider ceiling
        self.global_race_timeout: float = 18.0  # 18s global race ceiling

        # Supported providers catalog
        self.all_providers: List[str] = [
            "ollama", "groq", "gemini", "nvidia", "openai", "openrouter", "prash"
        ]

        # Live Metrics tracking
        self.total_races: int = 0
        self.fallback_triggers: int = 0
        self.win_counts: Dict[str, int] = {p: 0 for p in self.all_providers}
        self.participation_counts: Dict[str, int] = {p: 0 for p in self.all_providers}
        self.cancellation_counts: Dict[str, int] = {p: 0 for p in self.all_providers}
        self.failure_counts: Dict[str, int] = {p: 0 for p in self.all_providers}
        self.latencies_history: Dict[str, List[float]] = {p: [] for p in self.all_providers}

    async def _call_provider(
        self,
        provider: str,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> RaceCandidateResult:
        """
        Execute an isolated request to a single provider with a 15-second timeout,
        collecting its stream and validating its output quality.
        """
        t0 = time.time()
        events: List[Dict[str, Any]] = []
        full_text = ""
        tool_calls: List[Dict[str, Any]] = []
        stream_gen = None

        try:
            # 1. Fetch provider streaming generator
            if hasattr(self.service, "get_provider_stream"):
                stream_gen = self.service.get_provider_stream(
                    provider, user_message, conversation_history, tool_executor
                )
            else:
                stream_gen = getattr(self.service, f"_process_message_{provider}")(
                    user_message, conversation_history, tool_executor
                )

            # 2. Consume generator with 15.0s individual timeout
            async def _consume():
                nonlocal full_text
                async for chunk in stream_gen:
                    events.append(chunk)
                    if chunk.get("type") == "text_delta" and chunk.get("content"):
                        full_text += chunk["content"]
                    elif chunk.get("type") == "text_done" and chunk.get("content"):
                        if not full_text:
                            full_text = chunk["content"]
                    elif chunk.get("type") == "tool_call":
                        tool_calls.append(chunk)
                    elif chunk.get("type") == "error":
                        raise RuntimeError(chunk.get("error", "Provider error event"))

            await asyncio.wait_for(_consume(), timeout=self.individual_timeout)

            finish_t = time.time()
            latency = finish_t - t0

            # 3. Validate response criteria
            valid, reason = is_valid_response(full_text, tool_calls, events)
            entropy = calculate_text_entropy(full_text)

            return RaceCandidateResult(
                provider=provider,
                success=valid,
                latency=latency,
                events=events,
                full_text=full_text,
                tool_calls=tool_calls,
                entropy=entropy,
                error_msg=None if valid else reason,
                finish_timestamp=finish_t,
            )

        except asyncio.CancelledError:
            # Close HTTP generator cleanly to prevent socket exhaustion
            try:
                if stream_gen and hasattr(stream_gen, "aclose"):
                    await stream_gen.aclose()
            except Exception:
                pass
            raise

        except (asyncio.TimeoutError, TimeoutError):
            return RaceCandidateResult(
                provider=provider,
                success=False,
                latency=self.individual_timeout,
                error_msg=f"Provider '{provider}' timed out ({self.individual_timeout}s ceiling)",
                finish_timestamp=time.time(),
            )

        except Exception as exc:
            return RaceCandidateResult(
                provider=provider,
                success=False,
                latency=time.time() - t0,
                error_msg=str(exc),
                finish_timestamp=time.time(),
            )

    async def race_top_3(
        self,
        prompt: Any,
        context: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
        candidate_pool: Optional[List[str]] = None,
    ) -> RaceResult:
        """
        Execute requests in parallel across the top 3 ranked providers and return
        the fastest valid response. Aborts remaining requests immediately.
        """
        self.total_races += 1
        t_start = time.time()

        # 1. Identify available ranked providers
        if candidate_pool is not None:
            available = candidate_pool
        elif hasattr(self.router, "get_ranked_providers"):
            available = await self.router.get_ranked_providers()
        else:
            available = ["ollama", "groq", "gemini"]

        if not available:
            self.fallback_triggers += 1
            return RaceResult(all_failed=True, error="No available LLM providers configured")

        # Edge case: If < 3 providers exist, race with however many exist (2 or 1)
        top_3 = available[:3]
        for p in top_3:
            self.participation_counts[p] = self.participation_counts.get(p, 0) + 1

        logger.info("🏎️  LLM Racing Circuit Started: Racing Top-{} providers: {}", len(top_3), top_3)

        # 2. Fire identical requests to all providers simultaneously
        task_map: Dict[asyncio.Task, str] = {}
        for p in top_3:
            task = asyncio.create_task(
                self._call_provider(p, prompt, context, tool_executor),
                name=f"race_task_{p}_{int(t_start * 1000)}"
            )
            task_map[task] = p

        pending_tasks: Set[asyncio.Task] = set(task_map.keys())
        deadline = t_start + self.global_race_timeout

        winner_candidate: Optional[RaceCandidateResult] = None
        slower_valid: List[str] = []
        failed_candidates: List[Dict[str, Any]] = []
        cancelled: List[str] = []
        latencies: Dict[str, float] = {}

        # 3. Race condition: wait for FIRST_COMPLETED until a valid winner is found
        while pending_tasks and not winner_candidate:
            time_left = max(0.01, deadline - time.time())
            if time.time() >= deadline:
                logger.warning("Global race timeout reached ({:.1f}s) without a winner", self.global_race_timeout)
                break

            done, _ = await asyncio.wait(
                pending_tasks,
                timeout=time_left,
                return_when=asyncio.FIRST_COMPLETED
            )

            if not done:
                # Global timeout elapsed
                break

            valid_finishers: List[RaceCandidateResult] = []

            for task in done:
                pending_tasks.discard(task)
                p = task_map[task]
                try:
                    res: RaceCandidateResult = task.result()
                    latencies[p] = res.latency
                    if res.success:
                        valid_finishers.append(res)
                    else:
                        failed_candidates.append({
                            "provider": p,
                            "error_msg": res.error_msg or "Validation failure",
                            "latency": res.latency
                        })
                        self.failure_counts[p] = self.failure_counts.get(p, 0) + 1
                except Exception as exc:
                    failed_candidates.append({
                        "provider": p,
                        "error_msg": str(exc),
                        "latency": self.individual_timeout
                    })
                    self.failure_counts[p] = self.failure_counts.get(p, 0) + 1

            if valid_finishers:
                # Edge case: If 2 providers return simultaneously (within 50ms),
                # pick the one with higher historical ranking.
                if len(valid_finishers) == 1 and pending_tasks:
                    try:
                        simul_done, _ = await asyncio.wait(
                            pending_tasks,
                            timeout=0.05,  # 50ms window
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        for extra_task in simul_done:
                            pending_tasks.discard(extra_task)
                            extra_p = task_map[extra_task]
                            try:
                                extra_res: RaceCandidateResult = extra_task.result()
                                latencies[extra_p] = extra_res.latency
                                if extra_res.success:
                                    valid_finishers.append(extra_res)
                                else:
                                    failed_candidates.append({
                                        "provider": extra_p,
                                        "error_msg": extra_res.error_msg or "Validation failure",
                                        "latency": extra_res.latency
                                    })
                                    self.failure_counts[extra_p] = self.failure_counts.get(extra_p, 0) + 1
                            except Exception as extra_err:
                                failed_candidates.append({
                                    "provider": extra_p,
                                    "error_msg": str(extra_err),
                                    "latency": self.individual_timeout
                                })
                                self.failure_counts[extra_p] = self.failure_counts.get(extra_p, 0) + 1
                    except Exception:
                        pass

                # Sort valid finishers by their priority index in top_3 (higher ranking wins tie)
                valid_finishers.sort(key=lambda r: top_3.index(r.provider))
                winner_candidate = valid_finishers[0]

                # Any other valid finisher is recorded as slower valid (+5 points)
                for slower in valid_finishers[1:]:
                    slower_valid.append(slower.provider)
                break

        # 4. Immediately cancel (abort) remaining pending requests to save compute/tokens
        for remaining_task in pending_tasks:
            p = task_map[remaining_task]
            cancelled.append(p)
            self.cancellation_counts[p] = self.cancellation_counts.get(p, 0) + 1
            remaining_task.cancel()
            logger.info("🛑 Aborted losing provider '{}' (race concluded)", p)

        if pending_tasks:
            # Yield event loop cycle so cancellations finalize without throwing unhandled warnings
            await asyncio.gather(*pending_tasks, return_exceptions=True)

        # 5. Edge case: If all 3 return errors, attempt single retry with 4th ranked provider (sequential)
        if not winner_candidate and len(available) >= 4:
            fourth_provider = available[3]
            logger.warning("All top 3 racing providers failed. Attempting single retry with 4th ranked provider: '{}'", fourth_provider)
            self.participation_counts[fourth_provider] = self.participation_counts.get(fourth_provider, 0) + 1
            fourth_res = await self._call_provider(fourth_provider, prompt, context, tool_executor)
            latencies[fourth_provider] = fourth_res.latency

            if fourth_res.success:
                winner_candidate = fourth_res
            else:
                failed_candidates.append({
                    "provider": fourth_provider,
                    "error_msg": fourth_res.error_msg or "4th provider failure",
                    "latency": fourth_res.latency
                })
                self.failure_counts[fourth_provider] = self.failure_counts.get(fourth_provider, 0) + 1

        # 6. Post-Race Ranking & Metrics Updates
        if winner_candidate:
            winner_p = winner_candidate.provider
            self.win_counts[winner_p] = self.win_counts.get(winner_p, 0) + 1
            self.latencies_history.setdefault(winner_p, []).append(winner_candidate.latency)
            logger.info("🏆 LLM Race Winner: '{}' ({:.3f}s, entropy={:.2f})", winner_p, winner_candidate.latency, winner_candidate.entropy)

            if hasattr(self.router, "update_racing_rankings"):
                await self.router.update_racing_rankings(
                    winner=winner_p,
                    slower_valid=slower_valid,
                    failures=failed_candidates,
                    latencies=latencies
                )

            return RaceResult(
                winner=winner_p,
                events=winner_candidate.events,
                full_text=winner_candidate.full_text,
                tool_calls=winner_candidate.tool_calls,
                latency=winner_candidate.latency,
                entropy=winner_candidate.entropy,
                all_failed=False,
                candidates_raced=top_3,
                cancelled_providers=cancelled,
                slower_valid_providers=slower_valid,
                failed_providers=failed_candidates
            )
        else:
            self.fallback_triggers += 1
            logger.warning("❌ All racing providers failed. Triggering immediate emergency offline fallback.")

            if hasattr(self.router, "update_racing_rankings"):
                await self.router.update_racing_rankings(
                    winner=None,
                    slower_valid=slower_valid,
                    failures=failed_candidates,
                    latencies=latencies
                )

            return RaceResult(
                winner=None,
                all_failed=True,
                error="All racing LLM providers failed or timed out",
                candidates_raced=top_3,
                cancelled_providers=cancelled,
                slower_valid_providers=slower_valid,
                failed_providers=failed_candidates
            )

    # Alias for race_top_3
    race = race_top_3

    # ── Metrics Introspection APIs ────────────────────────────────────────

    def get_win_rates(self) -> Dict[str, float]:
        """Return the percentage of races won by each provider."""
        rates = {}
        for p, wins in self.win_counts.items():
            participations = self.participation_counts.get(p, 0)
            rates[p] = round((wins / participations) * 100, 1) if participations > 0 else 0.0
        return rates

    def get_cancellation_rates(self) -> Dict[str, float]:
        """Return the percentage of times a provider was cancelled due to a faster winner."""
        rates = {}
        for p, cancels in self.cancellation_counts.items():
            participations = self.participation_counts.get(p, 0)
            rates[p] = round((cancels / participations) * 100, 1) if participations > 0 else 0.0
        return rates

    def get_average_response_times(self) -> Dict[str, float]:
        """Return the moving average response time when racing."""
        avg_times = {}
        for p, history in self.latencies_history.items():
            if history:
                avg_times[p] = round(sum(history[-20:]) / len(history[-20:]), 3)
            else:
                avg_times[p] = 0.0
        return avg_times

    def get_fallback_trigger_rate(self) -> float:
        """Return the percentage of races where all candidates failed."""
        if self.total_races == 0:
            return 0.0
        return round((self.fallback_triggers / self.total_races) * 100, 1)

    def get_metrics(self) -> Dict[str, Any]:
        """Consolidated racing metrics for telemetry and dashboard monitoring."""
        return {
            "total_races": self.total_races,
            "fallback_triggers": self.fallback_triggers,
            "fallback_trigger_rate_percent": self.get_fallback_trigger_rate(),
            "win_counts": self.win_counts,
            "win_rates_percent": self.get_win_rates(),
            "cancellation_counts": self.cancellation_counts,
            "cancellation_rates_percent": self.get_cancellation_rates(),
            "failure_counts": self.failure_counts,
            "participation_counts": self.participation_counts,
            "average_response_times_sec": self.get_average_response_times(),
        }
