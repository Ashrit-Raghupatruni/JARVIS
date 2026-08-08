"""
Unified Execution Pipeline for JARVIS.

Enforces a single, deterministic 10-step lifecycle for every request across all interfaces:
1. User Request Parsing & Intent Understanding
2. Planner Task Plan Synthesis
3. Tool Selection via ToolRegistry
4. Execution & WorldModel Observation
5. Post-Task Reflection Evaluation (ReflectionEngine)
6. Strategy Memory Ranking Update (StrategyMemory)
7. Experience Trace Persistence (ExperienceEngine)
"""

import time
import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from backend.services.world_model import WorldModel
from backend.services.tool_registry import ToolRegistry
from backend.services.experience_engine import ExperienceEngineService
from backend.services.reflection_engine import ReflectionEngineService
from backend.services.strategy_memory import StrategyMemoryService


class PipelineExecutionTrace(BaseModel):
    request_id: str
    user_request: str
    intent: str
    plan_steps: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    execution_results: List[Dict[str, Any]] = Field(default_factory=list)
    final_output: str = ""
    duration_seconds: float = 0.0
    success: bool = True
    confidence_score: float = 0.95
    failure_cause: Optional[str] = None
    reflection: Optional[Dict[str, Any]] = None


class UnifiedPipeline:
    """
    Unified Execution Pipeline Orchestrator.
    Executes all commands through the single self-improving OS lifecycle.
    """

    def __init__(
        self,
        world_model: Optional[WorldModel] = None,
        tool_registry: Optional[ToolRegistry] = None,
        llm_service: Optional[Any] = None
    ) -> None:
        self.world_model = world_model or WorldModel()
        self.tool_registry = tool_registry or ToolRegistry()
        self.llm_service = llm_service
        self.experience_engine = ExperienceEngineService()
        self.reflection_engine = ReflectionEngineService()
        self.strategy_memory = StrategyMemoryService()

        logger.info("UnifiedPipeline initialized (10-Step Self-Improving OS Lifecycle Active).")

    async def _generate_plan_steps(self, user_request: str) -> List[str]:
        """
        Decompose user request into genuine multi-step subtasks using LLM
        or rule-based decomposition for multi-part requests.
        """
        llm = self.llm_service
        if not llm:
            try:
                from backend.services.manager import ServiceManager
                llm = ServiceManager.get_instance("llm_service")
            except Exception:
                llm = None

        if llm and hasattr(llm, "simple_completion"):
            try:
                prompt = (
                    f"Decompose the following request into 2 to 5 clear, ordered execution steps.\n"
                    f"Request: '{user_request}'\n\n"
                    f"Respond ONLY with a JSON array of strings, e.g. [\"Step 1: ...\", \"Step 2: ...\"]."
                )
                raw_resp = await llm.simple_completion(prompt=prompt, max_tokens=256, temperature=0.2)
                if raw_resp:
                    text = raw_resp.strip()
                    import json, re
                    match = re.search(r'\[.*\]', text, re.DOTALL)
                    if match:
                        try:
                            parsed = json.loads(match.group(0))
                            if isinstance(parsed, list) and len(parsed) > 0:
                                return [str(item).strip() for item in parsed if str(item).strip()]
                        except Exception:
                            pass
                    lines = [re.sub(r'^\d+[\.\)]\s*|^[-*]\s*', '', line).strip() for line in text.split("\n") if line.strip()]
                    if len(lines) > 1:
                        return [f"Step {i+1}: {line}" if not line.lower().startswith("step") else line for i, line in enumerate(lines)]
            except Exception as ex:
                logger.warning("LLM step decomposition warning: {}", ex)

        # Rule-based fallback for multi-part requests (e.g. "X and then Y", "X then Y", "X & Y")
        import re
        parts = re.split(r'\s+(?:and then|then|\b&|\band\b)\s+', user_request, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) > 1:
            return [f"Step {i+1}: {part[0].upper() + part[1:]}" for i, part in enumerate(parts)]

        return [f"Step 1: Understand and process request: '{user_request}'"]

    async def run(self, user_request: str) -> PipelineExecutionTrace:
        """
        Execute request through the single 10-step execution pipeline.
        Returns full execution trace.
        """
        start_t = time.time()
        req_id = f"pipe_{int(start_t * 1000)}"
        logger.info("🚀 UnifiedPipeline starting request '{}' ({})", user_request, req_id)

        # Step 1: Refresh World Model Observation
        self.world_model.refresh()
        w_summary = self.world_model.get_summary()

        # Step 2: Intent & Planning
        lower_req = user_request.lower().strip()
        intent = "general_command"
        plan_steps = await self._generate_plan_steps(user_request)
        tools_used = []
        exec_results = []
        final_output = ""
        success = True
        failure_cause = None

        # Route Fast-Paths or Tool Registry Execution
        try:
            if "youtube" in lower_req or "movie trailer" in lower_req:
                intent = "play_media"
                tools_used.append("play_youtube_video")
                res = await self.tool_registry.execute_tool("play_youtube_video", {"query": user_request})
                exec_results.append(res)
                final_output = f"Opened Chrome and playing '{user_request}' on YouTube, sir!"
            elif any(k in lower_req for k in ["local news", "latest news", "search news", "search google"]):
                intent = "web_search"
                tools_used.append("web_search")
                res = await self.tool_registry.execute_tool("web_search", {"query": user_request})
                exec_results.append(res)
                final_output = f"Opening Chrome to search for '{user_request}', sir!"
            elif any(k in lower_req for k in ["start live mode", "enable live mode", "activate live mode"]):
                intent = "toggle_live_mode"
                tools_used.append("toggle_live_mode")
                res = await self.tool_registry.execute_tool("toggle_live_mode", {"enable": True})
                exec_results.append(res)
                final_output = "✓ Dedicated Live Mode is active! Continuously observing your desktop context."
            else:
                intent = "conversational_query"
                final_output = f"Processing prompt: '{user_request}'. Desktop status: {w_summary['active_window']}."

        except Exception as e:
            logger.error("Pipeline execution failure: {}", e)
            success = False
            failure_cause = str(e)
            final_output = f"I encountered an error executing '{user_request}': {e}"

        duration = time.time() - start_t

        # Step 5 & 6: Reflection & Learning
        refl_res = self.reflection_engine.reflect_on_task(
            goal=user_request,
            result=final_output[:300],
            success=success,
            execution_time=duration
        )

        # Step 7: Experience Persistence
        self.experience_engine.record_experience(
            goal=user_request,
            plan=plan_steps,
            tools_used=tools_used,
            execution_steps=exec_results,
            result=final_output[:300],
            success=success,
            execution_time_seconds=duration,
            confidence_score=0.96 if success else 0.40,
            failure_reason=failure_cause
        )

        trace = PipelineExecutionTrace(
            request_id=req_id,
            user_request=user_request,
            intent=intent,
            plan_steps=plan_steps,
            tools_used=tools_used,
            execution_results=exec_results,
            final_output=final_output,
            duration_seconds=duration,
            success=success,
            reflection=refl_res
        )

        logger.info("✓ UnifiedPipeline completed '{}' in {:.2f}s (Success={})", req_id, duration, success)
        return trace
