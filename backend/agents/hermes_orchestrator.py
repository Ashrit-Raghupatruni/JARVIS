"""
JARVIS AI OS — Hermes Dual-Agent Orchestrator (Desktop + General Agent).
========================================================================
Unifies and coordinates:
1. `hermes-desktop` (Ollama): Specialized in GUI interactions, window management, screen perception, and desktop control.
2. `hermes-agent` (Ollama): Specialized in deep reasoning, function calling, code generation, and multi-step tool workflows.
"""

from __future__ import annotations

import os
import re
import aiohttp
from typing import Dict, Any, List, Optional
from loguru import logger

from backend.config import get_settings
from backend.agents.desktop_agent import HermesDesktopAgent, hermes_desktop_agent
from backend.agents.hermes_agent import HermesGeneralAgent, hermes_general_agent


class HermesOrchestrator:
    """
    Unified Orchestrator coordinating both Hermes Desktop Agent and Hermes General Agent.
    """

    # Keywords indicating direct GUI / Desktop OS interaction
    DESKTOP_GUI_KEYWORDS = [
        "click", "double click", "right click", "focus window", "open app",
        "open application", "minimize", "maximize", "type text into",
        "paste into", "scroll down", "scroll up", "switch window",
        "open notepad", "open chrome", "open calc", "open word", "bring to front"
    ]

    def __init__(
        self,
        desktop_agent: Optional[HermesDesktopAgent] = None,
        general_agent: Optional[HermesGeneralAgent] = None
    ) -> None:
        self.desktop_agent = desktop_agent or hermes_desktop_agent
        self.general_agent = general_agent or hermes_general_agent
        logger.info("HermesOrchestrator initialized with dual Hermes Desktop & General agents.")

    async def get_ollama_models(self) -> Dict[str, Any]:
        """Check Ollama API and return installed Hermes models."""
        settings = get_settings()
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        models_info = {
            "ollama_online": False,
            "has_hermes_desktop": False,
            "has_hermes_agent": False,
            "has_hermes3": False,
            "models": []
        }
        try:
            timeout = aiohttp.ClientTimeout(total=2.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{base_url}/api/tags") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models_info["ollama_online"] = True
                        for m in data.get("models", []):
                            name = m.get("name", "")
                            models_info["models"].append(name)
                            if "hermes-desktop" in name:
                                models_info["has_hermes_desktop"] = True
                            if "hermes-agent" in name:
                                models_info["has_hermes_agent"] = True
                            if "hermes3" in name:
                                models_info["has_hermes3"] = True
        except Exception as e:
            logger.debug("Ollama models query notice: {}", e)

        return models_info

    def classify_intent(self, goal: str) -> str:
        """
        Determine whether the request is primarily a GUI/Desktop task or a General Reasoning task.
        """
        goal_lower = goal.lower()
        for kw in self.DESKTOP_GUI_KEYWORDS:
            if kw in goal_lower:
                return "desktop"
        return "general"

    async def run_task(self, goal: str, mode: str = "auto") -> Dict[str, Any]:
        """
        Execute user goal through the appropriate Hermes agent or unified pipeline.
        
        mode:
        - "auto": Intelligently routes to hermes-desktop or hermes-agent based on intent.
        - "desktop": Explicitly uses hermes-desktop for GUI automation.
        - "agent": Explicitly uses hermes-agent for general reasoning & tool workflows.
        """
        logger.info("HermesOrchestrator received task: '{}' (mode: {})", goal, mode)
        selected_mode = mode.lower()
        if selected_mode == "auto":
            selected_mode = self.classify_intent(goal)

        if selected_mode == "desktop":
            logger.info("Routing task to 🖥️ Hermes Desktop Agent (hermes-desktop)...")
            result = await self.desktop_agent.execute_task(user_goal=goal)
            result["orchestration_mode"] = "hermes-desktop"
            # If desktop agent failed or encountered tool requirement, attempt fallback handover
            if result.get("status") == "timeout" and not result.get("completed"):
                logger.info("Desktop agent timeout/fallback: Handing over to Hermes General Agent...")
                fallback_res = await self.general_agent.execute_task(user_goal=f"Complete desktop task: {goal}")
                fallback_res["orchestration_mode"] = "hermes-desktop-handover-to-agent"
                return fallback_res
            return result
        elif selected_mode == "collaborative":
            logger.info("Executing task via 🤝 Hermes Collaborative Pipeline (Agent + Desktop)...")
            return await self.run_collaborative_task(goal)
        else:
            logger.info("Routing task to 🧠 Hermes General Agent (hermes-agent)...")
            result = await self.general_agent.execute_task(user_goal=goal)
            result["orchestration_mode"] = "hermes-agent"
            return result

    async def run_collaborative_task(self, goal: str) -> Dict[str, Any]:
        """
        Executes a complex multi-domain task by coordinating Hermes General Agent
        for high-level reasoning and delegating UI subtasks to Hermes Desktop Agent.
        """
        logger.info("Hermes Collaborative Pipeline starting for goal: '{}'", goal)
        # Step 1: Analyze and plan via General Agent
        plan_result = await self.general_agent.execute_task(
            user_goal=f"Analyze and execute prerequisites for: {goal}. If GUI interaction is required, perform file/data prep first."
        )
        
        # Step 2: Execute GUI actions via Desktop Agent
        gui_result = await self.desktop_agent.execute_task(
            user_goal=f"Execute desktop UI actions for: {goal}. Context: {plan_result.get('summary', '')}"
        )
        
        combined_steps = plan_result.get("steps", []) + gui_result.get("steps", [])
        return {
            "status": "success" if (plan_result.get("status") == "success" or gui_result.get("status") == "success") else "partial",
            "orchestration_mode": "collaborative",
            "goal": goal,
            "completed": gui_result.get("completed", plan_result.get("completed", True)),
            "summary": f"Plan: {plan_result.get('summary', '')} | GUI Execution: {gui_result.get('summary', '')}",
            "steps": combined_steps
        }


hermes_orchestrator = HermesOrchestrator()

