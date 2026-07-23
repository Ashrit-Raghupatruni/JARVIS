"""
JARVIS AI Operating System - Reflection Engine Service.

Performs post-task reflection and self-evaluation after every completed operation.
Answers internal self-evaluation criteria:
1. Did the task succeed or fail? Why?
2. What could have been better/faster/safer?
3. Should another tool or strategy have been used?
4. Should this procedure become the preferred strategy?

Stores permanent procedural reflections into HybridMemorySystem for future task planning.
"""

import time
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.services.manager import ServiceManager


class ReflectionEngineService:
    """Reflection Engine for post-execution self-evaluation and strategy optimization."""

    def __init__(self):
        logger.info("ReflectionEngineService initialized.")

    def reflect_on_task(
        self,
        goal: str,
        result: str,
        success: bool,
        execution_time: float,
        tools_used: Optional[List[str]] = None,
        failure_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute post-task reflection and return self-evaluation metrics.
        """
        tools = tools_used or []
        
        # Self-evaluation questions synthesis
        faster_approach = "Use cached selector or Win32 HWND directly" if execution_time > 3.0 else "Optimal"
        safer_approach = "Require Mobile Gatekeeper confirmation for high-risk action" if "system" in goal.lower() or "delete" in goal.lower() else "Safe"
        preferred_strategy = True if success and execution_time < 2.5 else False

        reflection = {
            "reflection_id": f"refl_{int(time.time() * 1000)}",
            "goal": goal,
            "success": success,
            "why": "Executed smoothly with verified outcome" if success else f"Execution failed: {failure_reason or 'Unknown error'}",
            "execution_time_seconds": execution_time,
            "faster_approach": faster_approach,
            "safer_approach": safer_approach,
            "recommended_tools": tools,
            "become_preferred_strategy": preferred_strategy,
            "timestamp": time.time()
        }

        # Store reflection in HybridMemorySystem
        try:
            hybrid_mem = ServiceManager.get_instance("hybrid_memory")
            if hybrid_mem and hasattr(hybrid_mem, "record_episode"):
                hybrid_mem.record_episode(
                    goal=goal,
                    result=f"Reflection: {reflection['why']} | Strategy Preferred: {preferred_strategy}",
                    success=success
                )
        except Exception as e:
            logger.warning("Failed to store reflection in HybridMemorySystem: {}", e)

        logger.info("🔮 Reflection completed for '{}': Preferred={}", goal, preferred_strategy)
        return reflection
