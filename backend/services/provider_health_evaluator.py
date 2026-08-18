"""
JARVIS AI OS — Provider Health Manager & Response Quality Evaluator.
===================================================================
Maintains real-time health state (AVAILABLE, DEGRADED, COOLDOWN, DISABLED) for LLM providers
(Groq, Ollama, OpenRouter, Gemini, OpenAI, Prash).
Enforces cooldown timers (60s default) to prevent wasteful retries of dead providers.
Evaluates LLM response quality to trigger context-preserving fallback when responses are insufficient.
"""

import time
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from loguru import logger


class ProviderStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    COOLDOWN = "COOLDOWN"
    DISABLED = "DISABLED"


class ProviderHealthState(BaseModel):
    provider: str
    status: ProviderStatus = ProviderStatus.AVAILABLE
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    cooldown_seconds: float = 60.0
    avg_latency_ms: float = 0.0

    def is_usable(self) -> bool:
        if self.status == ProviderStatus.DISABLED:
            return False
        if self.status == ProviderStatus.COOLDOWN:
            # Check if cooldown period has expired
            if time.time() - self.last_failure_time >= self.cooldown_seconds:
                logger.info("Provider '{}' cooldown period ({}s) expired. Marking DEGRADED for probe.", self.provider, self.cooldown_seconds)
                self.status = ProviderStatus.DEGRADED
                return True
            return False
        return True

    def record_success(self, latency_ms: float) -> None:
        self.success_count += 1
        self.failure_count = 0
        self.status = ProviderStatus.AVAILABLE
        # Exponential moving average for latency
        if self.avg_latency_ms == 0:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = 0.8 * self.avg_latency_ms + 0.2 * latency_ms

    def record_failure(self, error_reason: str = "") -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= 2:
            self.status = ProviderStatus.COOLDOWN
            logger.warning("Provider '{}' placed in COOLDOWN mode for {}s (Reason: {})", self.provider, self.cooldown_seconds, error_reason)
        else:
            self.status = ProviderStatus.DEGRADED
            logger.warning("Provider '{}' marked DEGRADED (Failure #{}: {})", self.provider, self.failure_count, error_reason)


class QualityEvaluationResult(BaseModel):
    is_sufficient: bool
    score: float  # 0.0 to 1.0
    reason: str
    should_fallback: bool


class ProviderHealthEvaluator:
    """Central Health Manager & Quality Evaluator for Model Routing."""

    def __init__(self):
        self.providers: Dict[str, ProviderHealthState] = {
            "groq": ProviderHealthState(provider="groq"),
            "ollama": ProviderHealthState(provider="ollama"),
            "openrouter": ProviderHealthState(provider="openrouter"),
            "gemini": ProviderHealthState(provider="gemini"),
            "openai": ProviderHealthState(provider="openai"),
            "prash": ProviderHealthState(provider="prash")
        }

    def get_healthy_provider(self, preferred_order: List[str]) -> Optional[str]:
        """Returns the first healthy provider from preferred_order, skipping COOLDOWN/DISABLED providers."""
        for p in preferred_order:
            state = self.providers.get(p.lower())
            if state and state.is_usable():
                return p
        # Fallback to local Prash if all cloud providers are in cooldown
        if self.providers.get("prash", ProviderHealthState(provider="prash")).is_usable():
            return "prash"
        return preferred_order[0] if preferred_order else "ollama"

    def record_provider_success(self, provider: str, latency_ms: float) -> None:
        p = provider.lower()
        if p in self.providers:
            self.providers[p].record_success(latency_ms)

    def record_provider_failure(self, provider: str, error_reason: str = "") -> None:
        p = provider.lower()
        if p in self.providers:
            self.providers[p].record_failure(error_reason)

    def evaluate_response(
        self,
        user_request: str,
        response_text: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        request_category: str = "KNOWLEDGE"
    ) -> QualityEvaluationResult:
        """
        Evaluate if a model's response is complete, accurate, and non-hallucinated.
        Triggers fallback if model output is insufficient for executable requests.
        """
        resp = (response_text or "").strip()
        cat = request_category.upper()

        if not resp and not tool_calls:
            return QualityEvaluationResult(
                is_sufficient=False,
                score=0.0,
                reason="Empty model response and zero tool calls.",
                should_fallback=True
            )

        resp_lower = resp.lower()

        # Check for hallucinated inability for ACTION requests
        if cat in ("ACTION", "AUTOMATION", "WORKFLOW", "SYSTEM"):
            hallucination_phrases = [
                "cannot access",
                "cannot open",
                "cannot execute",
                "cannot run",
                "cannot launch",
                "cannot perform",
                "don't have access to your computer",
                "do not have access to your computer",
                "cannot click",
                "unable to perform",
                "as an ai"
            ]
            if any(hp in resp_lower for hp in hallucination_phrases) and not tool_calls:
                logger.warning("QualityEvaluator: Detected hallucinated inability for ACTION request: '{}'", resp[:80])
                return QualityEvaluationResult(
                    is_sufficient=False,
                    score=0.1,
                    reason="Model hallucinated inability to execute action.",
                    should_fallback=True
                )

        # Check for repetitive error loops
        if "error 401" in resp_lower or "rate limit exceeded" in resp_lower or "api key invalid" in resp_lower:
            return QualityEvaluationResult(
                is_sufficient=False,
                score=0.0,
                reason="API error signature contained in response text.",
                should_fallback=True
            )

        return QualityEvaluationResult(
            is_sufficient=True,
            score=0.95,
            reason="Response satisfies request parameters cleanly.",
            should_fallback=False
        )


# Global Singleton Evaluator
evaluator = ProviderHealthEvaluator()
