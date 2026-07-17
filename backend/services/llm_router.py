import asyncio
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.models.database import ProviderMetric, RoutingDecision

class LLMRoutingEngine:
    """
    Intelligent LLM orchestrator that continuously benchmarks providers,
    ranks them dynamically, manages circuit breakers, and handles silent failovers.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.data_dir = settings.data_path
        self.db_engine = None
        self.session_factory = None
        self.background_task = None
        self.is_running = False

        # Providers config
        self.primary_provider = (settings.LLM_PROVIDER or "gemini").lower()
        self.gemini_key = settings.GEMINI_API_KEY
        self.gemini_model_name = settings.GEMINI_MODEL or "gemini-1.5-flash"
        self.openai_key = settings.OPENAI_API_KEY
        self.openai_model_name = settings.OPENAI_MODEL or "gpt-4o"
        self.openrouter_key = settings.OPENROUTER_API_KEY
        self.openrouter_model_name = settings.OPENROUTER_MODEL or "meta-llama/llama-3.3-70b-instruct:free"
        self.groq_key = settings.GROQ_API_KEY
        self.groq_model_name = settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        self.nvidia_key = settings.NVIDIA_API_KEY
        self.nvidia_model_name = settings.NIM_MODEL or "meta/llama-3.1-8b-instruct"
        self.ollama_base_url = settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.ollama_model_name = settings.OLLAMA_MODEL or "qwen2.5-coder:3b"

        # Model cost profiles (Cost per 1M tokens)
        self.costs = {
            "prash": 0.0,
            "ollama": 0.0,
            "openrouter": 0.0,
            "groq": 0.69,
            "gemini": 0.15,
            "openai": 4.50,
            "nvidia": 0.0
        }

        # Circuit breakers & Metrics state
        self.circuit_state = {
            "prash": "CLOSED",
            "ollama": "CLOSED",
            "gemini": "CLOSED",
            "openai": "CLOSED",
            "openrouter": "CLOSED",
            "groq": "CLOSED",
            "nvidia": "CLOSED"
        }
        self.consecutive_failures = {p: 0 for p in self.circuit_state}
        self.last_tripped = {p: 0.0 for p in self.circuit_state}

        # Live performance rolling metrics (latency, throughput, success rate)
        self.metrics = {
            p: {"latency": 1.0, "throughput": 30.0, "success_rate": 1.0}
            for p in self.circuit_state
        }

        # Client Initializations
        self.clients = {}
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize OpenAI-compatible client libraries for all providers."""
        # Ollama
        try:
            self.clients["ollama"] = AsyncOpenAI(
                base_url=f"{self.ollama_base_url}/v1",
                api_key="ollama"
            )
        except Exception as e:
            logger.error(f"Failed to init Ollama client: {e}")

        # OpenAI
        if self.openai_key:
            try:
                self.clients["openai"] = AsyncOpenAI(api_key=self.openai_key)
            except Exception as e:
                logger.error(f"Failed to init OpenAI client: {e}")

        # Gemini (OpenAI compatible endpoint or key verification)
        if self.gemini_key:
            # We can use google-generativeai directly in llm.py, but for the router
            # we register Gemini availability
            self.clients["gemini"] = True

        # OpenRouter
        if self.openrouter_key:
            try:
                self.clients["openrouter"] = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.openrouter_key,
                    default_headers={
                        "HTTP-Referer": "https://github.com/Ashrit-Raghupatruni/JARVIS",
                        "X-Title": "JARVIS AI",
                    }
                )
            except Exception as e:
                logger.error(f"Failed to init OpenRouter client: {e}")

        # Groq
        if self.groq_key:
            try:
                self.clients["groq"] = AsyncOpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=self.groq_key
                )
            except Exception as e:
                logger.error(f"Failed to init Groq client: {e}")

        # NVIDIA
        if self.nvidia_key:
            try:
                self.clients["nvidia"] = AsyncOpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=self.nvidia_key
                )
            except Exception as e:
                logger.error(f"Failed to init NVIDIA client: {e}")

    async def init(self) -> None:
        """Setup SQLite engine and spin up background benchmark poller."""
        db_path = self.data_dir / "jarvis.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        self.db_engine = create_async_engine(db_url, echo=False)
        self.session_factory = async_sessionmaker(self.db_engine, expire_on_commit=False)

        # Create all registered tables if not exist
        from backend.models.database import Base
        async with self.db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Run background loop
        self.is_running = True
        self.background_task = asyncio.create_task(self._background_benchmark_loop())
        logger.info("✓ LLM Router Engine fully initialized and background poller active")

    async def shutdown(self) -> None:
        """Clean up background tasks and database engine."""
        self.is_running = False
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
        if self.db_engine:
            await self.db_engine.dispose()
        logger.info("LLM Router Engine shut down successfully")

    async def get_ranked_providers(self) -> List[str]:
        """Rank providers based on dynamic utility scoring."""
        scores = {}
        for p, client in self.clients.items():
            if not client:
                continue

            # If circuit is tripped, check if cooldown is over (5 mins)
            if self.circuit_state[p] == "OPEN":
                if time.time() - self.last_tripped[p] > 300:
                    logger.info(f"Resetting circuit breaker for {p} to HALF-OPEN for testing")
                    self.circuit_state[p] = "CLOSED"
                    self.consecutive_failures[p] = 0
                else:
                    scores[p] = -99999.0
                    continue

            # Calculate score: prioritize success, reward speed/low-latency, penalize cost
            success_rate = self.metrics[p]["success_rate"]
            latency = max(0.05, self.metrics[p]["latency"])
            throughput = self.metrics[p]["throughput"]
            cost = self.costs.get(p, 0.0)

            # Score formula
            score = (success_rate * 60.0) + (1.0 / latency * 15.0) + (throughput * 0.1) - (cost * 8.0)
            
            # Primary provider bias
            if p == self.primary_provider:
                score += 15.0

            # Prash (local AI engine) always gets massive priority
            if p == "prash":
                score += 100.0

            scores[p] = score

        # Sort descending
        ranked = sorted([p for p in scores], key=lambda x: scores[x], reverse=True)
        logger.debug(f"LLM Provider Rankings: { {p: round(scores[p], 2) for p in ranked} }")
        return ranked

    async def record_metric(
        self, provider: str, model: str, latency: float, throughput: Optional[float], cost: float, success: bool, error_msg: Optional[str] = None
    ) -> None:
        """Update local metrics state, manage circuit breakers, and log to SQLite database."""
        success_val = 1 if success else 0

        # Update local rolling metrics
        alpha = 0.3  # Exponential moving average factor
        if success:
            self.consecutive_failures[provider] = 0
            self.circuit_state[provider] = "CLOSED"
            self.metrics[provider]["latency"] = (alpha * latency) + ((1 - alpha) * self.metrics[provider]["latency"])
            if throughput:
                self.metrics[provider]["throughput"] = (alpha * throughput) + ((1 - alpha) * self.metrics[provider]["throughput"])
            self.metrics[provider]["success_rate"] = (alpha * 1.0) + ((1 - alpha) * self.metrics[provider]["success_rate"])
        else:
            self.consecutive_failures[provider] += 1
            self.metrics[provider]["success_rate"] = (alpha * 0.0) + ((1 - alpha) * self.metrics[provider]["success_rate"])
            
            # Trip circuit breaker on 3 consecutive failures
            if self.consecutive_failures[provider] >= 3 and self.circuit_state[provider] == "CLOSED":
                logger.warning(f"!!! CIRCUIT BREAKER TRIPPED FOR {provider} !!! Consecutive failures={self.consecutive_failures[provider]}")
                self.circuit_state[provider] = "OPEN"
                self.last_tripped[provider] = time.time()

        # Save to SQLite
        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    metric = ProviderMetric(
                        provider_name=provider,
                        model_name=model,
                        latency=latency,
                        throughput=throughput,
                        cost=cost,
                        success=success_val,
                        error_message=error_msg
                    )
                    session.add(metric)
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to log metric to DB: {e}")

    async def record_decision(
        self, selected_provider: str, selected_model: str, latency: float, success: bool, fallback_count: int, prompt_tokens: int, completion_tokens: int, cost: float
    ) -> None:
        """Save a final routing decision to the database."""
        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    decision = RoutingDecision(
                        selected_provider=selected_provider,
                        selected_model=selected_model,
                        latency=latency,
                        success=1 if success else 0,
                        fallback_count=fallback_count,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        cost=cost
                    )
                    session.add(decision)
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to log routing decision to DB: {e}")

    async def _background_benchmark_loop(self) -> None:
        """Periodically run tiny health check calls against all configured providers."""
        # Initial sleep to let server boot
        await asyncio.sleep(5)
        
        while self.is_running:
            for p, client in self.clients.items():
                if not client:
                    continue

                # Skip health checks for local Prash engine (not an API)
                if p == "prash":
                    continue
                
                # Run health check
                try:
                    start_time = time.time()
                    success = False
                    error_msg = None
                    tokens = 0
                    model_name = self._get_model_name(p)

                    if p == "gemini":
                        from google import genai
                        client = genai.Client(api_key=self.gemini_key)
                        response = await asyncio.wait_for(
                            client.aio.models.generate_content(
                                model=self.gemini_model_name,
                                contents="Hi"
                            ),
                            timeout=6.0
                        )
                        if response and response.text:
                            success = True
                            tokens = 1
                    else:
                        # Standard OpenAI compatible endpoints
                        response = await asyncio.wait_for(
                            client.chat.completions.create(
                                model=model_name,
                                messages=[{"role": "user", "content": "Hi"}],
                                max_tokens=1,
                            ),
                            timeout=6.0
                        )
                        if response and response.choices:
                            success = True
                            tokens = 1

                    latency = time.time() - start_time
                    cost = (tokens / 1000000) * self.costs.get(p, 0.0)
                    throughput = tokens / max(0.01, latency)

                    await self.record_metric(p, model_name, latency, throughput, cost, success)

                except Exception as e:
                    latency = time.time() - start_time
                    error_msg = str(e)
                    model_name = self._get_model_name(p)
                    await self.record_metric(p, model_name, latency, 0.0, 0.0, False, error_msg)

            # Polling frequency
            await asyncio.sleep(60)

    def _get_model_name(self, provider: str) -> str:
        """Resolve model name string based on provider."""
        names = {
            "prash": "prash-local-v0.1",
            "ollama": self.ollama_model_name,
            "gemini": self.gemini_model_name,
            "openai": self.openai_model_name,
            "openrouter": self.openrouter_model_name,
            "groq": self.groq_model_name,
            "nvidia": self.nvidia_model_name
        }
        return names.get(provider, "unknown")
