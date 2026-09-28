"""
Unit and Integration Tests for Parallel Racing LLM Provider Selection (Top-3).
"""

import asyncio
import time
import pytest
from typing import Any, AsyncGenerator, Dict, List, Optional

from backend.services.llm.racing import (
    LLMRacingCircuit,
    RaceResult,
    calculate_text_entropy,
    is_valid_response,
)
from backend.services.llm_router import LLMRoutingEngine


# ── 1. Text Entropy and Response Validation Tests ─────────────────────────────


def test_calculate_text_entropy_normal_english():
    english_text = "Good evening, sir. All system automation routines are running at peak efficiency."
    entropy = calculate_text_entropy(english_text)
    assert 3.0 < entropy < 5.5, f"Expected normal English entropy ~4.0-5.0, got {entropy}"


def test_calculate_text_entropy_gibberish():
    # Random high-entropy ASCII noise
    noise = "a!B@c#D$e%F^g&H*i(J)k_L+m=N~o`p1Q2r3S4t5U6v7W8x9Y0zZ!@#$%^&*()_+"
    entropy = calculate_text_entropy(noise)
    assert entropy >= 5.5, f"Expected high entropy for noise, got {entropy}"


def test_is_valid_response_short_and_null():
    assert is_valid_response("")[0] is False
    assert is_valid_response(None)[0] is False
    assert is_valid_response("Short")[0] is False  # <= 10 chars
    assert is_valid_response("1234567890")[0] is False  # 10 chars


def test_is_valid_response_error_patterns():
    valid, reason = is_valid_response("Request failed due to quota exceeded on upstream server.")
    assert valid is False
    assert "quota exceeded" in reason

    valid, reason = is_valid_response("Connection refused by peer port 11434.")
    assert valid is False
    assert "connection refused" in reason

    valid, reason = is_valid_response("An unexpected timeout error occurred while waiting for model.")
    assert valid is False
    assert "timeout" in reason


def test_is_valid_response_with_tool_calls():
    # Structured tool calls should be valid even if text is empty
    valid, reason = is_valid_response("", tool_calls=[{"name": "open_application"}])
    assert valid is True
    assert reason == "Valid tool calls"


def test_is_valid_response_success():
    valid, reason = is_valid_response("Online and operational, sir! All subsystems are green.")
    assert valid is True
    assert reason == "Valid"


# ── 2. Mock Provider & Service Harness ────────────────────────────────────────


class MockLLMService:
    def __init__(self, delays: Dict[str, float], responses: Dict[str, str], errors: Optional[Dict[str, Exception]] = None):
        self.delays = delays
        self.responses = responses
        self.errors = errors or {}
        self.cancelled_providers: List[str] = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def get_provider_stream(
        self,
        provider: str,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        async def _stream():
            delay = self.delays.get(provider, 0.05)
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                self.cancelled_providers.append(provider)
                raise

            if provider in self.errors:
                raise self.errors[provider]

            resp_text = self.responses.get(provider, "Default response from provider")
            yield {"type": "text_delta", "content": resp_text}
            yield {"type": "text_done", "content": resp_text}

        return _stream()


# ── 3. Parallel Racing Circuit Core Execution Tests ───────────────────────────


@pytest.mark.asyncio
async def test_racing_circuit_fastest_provider_wins_and_cancels_losers():
    """
    Test that the fastest provider (Groq: 50ms) wins over slower providers (Gemini: 200ms, Ollama: 500ms),
    and the slower pending providers are cancelled immediately.
    """
    router = LLMRoutingEngine()
    delays = {"groq": 0.05, "gemini": 0.25, "ollama": 0.50}
    responses = {
        "groq": "Groq fastest response ready for user display.",
        "gemini": "Gemini slower response that should be cancelled.",
        "ollama": "Ollama slowest response that should be cancelled."
    }
    mock_service = MockLLMService(delays, responses)
    circuit = LLMRacingCircuit(mock_service, router)

    result = await circuit.race_top_3(
        prompt="Hello JARVIS",
        candidate_pool=["groq", "gemini", "ollama"]
    )

    assert result.winner == "groq"
    assert result.all_failed is False
    assert "Groq fastest" in result.full_text
    assert "gemini" in result.cancelled_providers or "ollama" in result.cancelled_providers
    assert "groq" in mock_service.responses

    # Winner ranking check: +20 points
    assert router.speed_score_bonus["groq"] >= 20.0
    # Winner recorded in circuit metrics
    assert circuit.win_counts["groq"] == 1


@pytest.mark.asyncio
async def test_racing_circuit_tie_break_within_50ms():
    """
    If two providers finish within 50ms (simultaneous return),
    the one with higher historical ranking in top_3 wins!
    """
    router = LLMRoutingEngine()
    # Ollama is ranked #1 in candidate_pool, Groq is ranked #2.
    # Groq finishes at 0.05s, Ollama finishes at 0.07s (diff: 20ms < 50ms).
    delays = {"ollama": 0.07, "groq": 0.05, "gemini": 0.40}
    responses = {
        "ollama": "Ollama historical higher ranking response.",
        "groq": "Groq arrived slightly earlier within 50ms window.",
        "gemini": "Gemini slow response."
    }
    mock_service = MockLLMService(delays, responses)
    circuit = LLMRacingCircuit(mock_service, router)

    result = await circuit.race_top_3(
        prompt="Status report",
        candidate_pool=["ollama", "groq", "gemini"]
    )

    # Ollama has higher priority ranking in candidate_pool -> wins tie break!
    assert result.winner == "ollama"
    assert "Ollama" in result.full_text
    # Groq was valid finisher in the same window -> awarded +5 slower valid points
    assert router.speed_score_bonus["groq"] == 5.0
    assert router.speed_score_bonus["ollama"] >= 20.0


@pytest.mark.asyncio
async def test_racing_circuit_single_retry_with_fourth_provider():
    """
    If top 3 providers all fail, attempt a single sequential retry with the 4th ranked provider.
    """
    router = LLMRoutingEngine()
    delays = {"ollama": 0.02, "groq": 0.02, "gemini": 0.02, "nvidia": 0.04}
    responses = {
        "ollama": "quota exceeded error payload",  # invalid
        "groq": "Short",  # invalid (< 10 chars)
        "gemini": "timeout occurred on backend",  # invalid
        "nvidia": "NVIDIA NIM 4th ranked provider stepped in and saved the request!"
    }
    mock_service = MockLLMService(delays, responses)
    circuit = LLMRacingCircuit(mock_service, router)

    result = await circuit.race_top_3(
        prompt="Help me",
        candidate_pool=["ollama", "groq", "gemini", "nvidia"]
    )

    assert result.winner == "nvidia"
    assert result.all_failed is False
    assert "NVIDIA NIM" in result.full_text
    # 3 failures penalized -10 points each
    assert router.speed_score_bonus["ollama"] == -10.0
    assert router.speed_score_bonus["groq"] == -10.0
    assert router.speed_score_bonus["gemini"] == -10.0
    assert router.speed_score_bonus["nvidia"] >= 20.0


@pytest.mark.asyncio
async def test_racing_circuit_all_failed_triggers_offline_fallback():
    """
    If all 3 (and 4th) fail, return all_failed=True cleanly without cascading delays.
    """
    router = LLMRoutingEngine()
    delays = {"p1": 0.01, "p2": 0.01, "p3": 0.01}
    errors = {
        "p1": ConnectionResetError("Connection reset"),
        "p2": TimeoutError("Timeout"),
        "p3": RuntimeError("Service unavailable 503")
    }
    mock_service = MockLLMService(delays, {}, errors)
    circuit = LLMRacingCircuit(mock_service, router)

    result = await circuit.race_top_3(
        prompt="Tell me a joke",
        candidate_pool=["p1", "p2", "p3"]
    )

    assert result.winner is None
    assert result.all_failed is True
    assert circuit.fallback_triggers == 1
    assert circuit.get_fallback_trigger_rate() == 100.0


@pytest.mark.asyncio
async def test_racing_circuit_with_less_than_3_providers():
    """
    Edge case: If provider list has < 3 available providers (e.g. 2 or 1),
    it races with however many exist without errors.
    """
    router = LLMRoutingEngine()
    delays = {"ollama": 0.20, "groq": 0.02}
    responses = {
        "ollama": "Ollama response when racing with 2 providers.",
        "groq": "Groq faster response when racing with 2 providers."
    }
    mock_service = MockLLMService(delays, responses)
    circuit = LLMRacingCircuit(mock_service, router)

    result = await circuit.race_top_3(
        prompt="Count to 10",
        candidate_pool=["ollama", "groq"]
    )

    assert result.winner == "groq"
    assert len(result.candidates_raced) == 2


@pytest.mark.asyncio
async def test_racing_circuit_metrics_introspection():
    """
    Verify win rates, cancellation rates, and response time metrics calculation.
    """
    router = LLMRoutingEngine()
    circuit = LLMRacingCircuit(MockLLMService({}, {}), router)

    circuit.total_races = 10
    circuit.fallback_triggers = 1
    circuit.participation_counts["groq"] = 8
    circuit.win_counts["groq"] = 6
    circuit.cancellation_counts["groq"] = 2
    circuit.latencies_history["groq"] = [0.45, 0.50, 0.48]

    metrics = circuit.get_metrics()
    assert metrics["total_races"] == 10
    assert metrics["fallback_trigger_rate_percent"] == 10.0
    assert metrics["win_rates_percent"]["groq"] == 75.0
    assert metrics["cancellation_rates_percent"]["groq"] == 25.0
    assert metrics["average_response_times_sec"]["groq"] == 0.477
