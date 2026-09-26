"""
JARVIS AI OS — Hermes General Autonomous Agent (Reasoning, Tool Calling & Multi-Step Workflows).
================================================================================================
Powers autonomous multi-step reasoning, function execution, code generation, file manipulation,
and task planning via Ollama Hermes Agent (hermes-agent / hermes3).
"""

from __future__ import annotations

import os
import sys
import time
import json
import asyncio
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from loguru import logger
import aiohttp

from backend.config import get_settings
from backend.services.manager import ServiceManager
from backend.services.safety_gatekeeper import SafetyGatekeeper
from backend.services.tool_registry import ToolRegistry


HERMES_AGENT_SYSTEM_PROMPT = """You are the Hermes General Autonomous Agent for the JARVIS AI Operating System.
You are equipped with advanced multi-step reasoning, code execution, file management, system diagnostic, and function calling tools.

When solving user requests:
1. Think systematically step-by-step.
2. Formulate tool execution calls in valid JSON format.
3. Observe tool results and adapt your plan.
4. Conclude with a clear, concise summary when the objective is achieved.

Tool Call Format:
```json
{
  "thought": "Brief explanation of your next action",
  "tool": "tool_name",
  "parameters": {
    "param1": "value1"
  }
}
```

When finished:
```json
{
  "thought": "Task is completed",
  "action": "finish",
  "summary": "Detailed final answer and outcome for the user."
}
```
"""


class HermesGeneralAgent:
    """
    Autonomous General Agent powered by Nous Hermes Agent (hermes-agent / hermes3).
    Executes complex multi-tool workflows, file manipulations, code generation, and deep reasoning.
    """

    def __init__(
        self,
        ollama_base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        tool_registry: Optional[ToolRegistry] = None,
        gatekeeper: Optional[SafetyGatekeeper] = None,
        max_steps: int = 12
    ) -> None:
        settings = get_settings()
        self.ollama_base_url = (ollama_base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or os.getenv("HERMES_AGENT_MODEL", settings.HERMES_AGENT_MODEL or "hermes-agent")
        self.fallback_model = settings.HERMES_FALLBACK_MODEL or "hermes3"
        self.tool_registry = tool_registry or ToolRegistry()
        self.gatekeeper = gatekeeper or SafetyGatekeeper()
        self.max_steps = max_steps
        logger.info("HermesGeneralAgent initialized. Target Model: {} @ {}", self.model_name, self.ollama_base_url)

    async def check_ollama_availability(self) -> bool:
        """Verify if Ollama daemon is reachable and list available models."""
        try:
            timeout = aiohttp.ClientTimeout(total=2.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.ollama_base_url}/api/tags") as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def resolve_active_model(self) -> str:
        """
        Dynamically probe Ollama to check if hermes-agent is available,
        falling back to hermes3 if needed.
        """
        try:
            timeout = aiohttp.ClientTimeout(total=2.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.ollama_base_url}/api/tags") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        available_models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                        if self.model_name.split(":")[0] in available_models:
                            return self.model_name
                        if self.fallback_model.split(":")[0] in available_models:
                            return self.fallback_model
        except Exception:
            pass
        return self.model_name

    def _get_tools_prompt_schema(self) -> str:
        """Serialize registered tools into a compact prompt schema."""
        tools_summary = []
        for name, meta in list(self.tool_registry._tools.items())[:30]:
            params_str = ", ".join(meta.parameters.get("properties", {}).keys())
            tools_summary.append(f"- `{name}({params_str})`: {meta.description}")
        return "\n".join(tools_summary)

    async def _query_hermes_model(self, messages: List[Dict[str, str]]) -> str:
        """Query Ollama Hermes model with fallback to primary LLM Router."""
        active_model = await self.resolve_active_model()
        try:
            timeout = aiohttp.ClientTimeout(total=60.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {
                    "model": active_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.95
                    }
                }
                async with session.post(f"{self.ollama_base_url}/api/chat", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("message", {}).get("content", "")
                    else:
                        logger.warning("Ollama {} returned status {}, trying fallback router", active_model, resp.status)
        except Exception as ollama_err:
            logger.warning("Ollama connection error ({}): falling back to primary LLM Router", ollama_err)

        # Fallback to configured primary LLM Router
        try:
            router = ServiceManager.get_instance("llm_router")
            if router:
                response = await router.generate(messages=messages, temperature=0.3)
                return response if isinstance(response, str) else str(response)
        except Exception as router_err:
            logger.error("LLM Router fallback failed: {}", router_err)

        return '{"action": "finish", "summary": "Failed to connect to Hermes Agent LLM."}'

    def _parse_agent_json(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse structured JSON tool call or finish payload."""
        try:
            # 1. Markdown code block ```json ... ```
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
            if json_match:
                return json.loads(json_match.group(1))

            # 2. Raw JSON dictionary
            brace_match = re.search(r"\{[\s\S]*?\}", response_text)
            if brace_match:
                return json.loads(brace_match.group(0))
        except Exception as e:
            logger.warning("Could not parse JSON payload from response: {} | Text: {}", e, response_text[:100])
        return None

    async def execute_task(self, user_goal: str) -> Dict[str, Any]:
        """
        Execute high-level agentic task through Hermes multi-step reasoning and tool calling.
        """
        logger.info("🧠 Hermes General Agent starting task: '{}'", user_goal)
        tools_schema = self._get_tools_prompt_schema()
        
        system_content = f"{HERMES_AGENT_SYSTEM_PROMPT}\n\nAvailable System Tools:\n{tools_schema}"
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"User Goal: {user_goal}\n\nPlease analyze and begin execution."}
        ]

        steps_log: List[Dict[str, Any]] = []
        is_completed = False
        summary = ""

        for step_num in range(1, self.max_steps + 1):
            logger.info("Hermes General Agent — Step {}/{}", step_num, self.max_steps)
            
            raw_response = await self._query_hermes_model(messages)
            action_dict = self._parse_agent_json(raw_response)

            if not action_dict:
                action_dict = {"action": "finish", "summary": raw_response}

            action_type = action_dict.get("action", "").lower()
            tool_name = action_dict.get("tool")

            # Check if task is finished
            if action_type == "finish" or (not tool_name and "summary" in action_dict):
                is_completed = True
                summary = action_dict.get("summary", "Task completed.")
                steps_log.append({"step": step_num, "thought": action_dict.get("thought"), "action": "finish", "result": summary})
                break

            # Execute tool call via ToolRegistry
            tool_params = action_dict.get("parameters", {})
            logger.info("Hermes executing tool '{}' with params: {}", tool_name, tool_params)
            
            # Execute tool through ToolRegistry
            tool_result = await self.tool_registry.execute_tool(tool_name, tool_params)
            steps_log.append({
                "step": step_num,
                "thought": action_dict.get("thought"),
                "tool": tool_name,
                "parameters": tool_params,
                "result": tool_result
            })

            # Append assistant step and tool result to conversation history
            messages.append({"role": "assistant", "content": f"```json\n{json.dumps(action_dict, indent=2)}\n```"})
            messages.append({"role": "user", "content": f"Tool '{tool_name}' Result: {json.dumps(tool_result)}"})

            await asyncio.sleep(0.2)

        return {
            "status": "success" if is_completed else "timeout",
            "agent": "hermes-agent",
            "goal": user_goal,
            "completed": is_completed,
            "summary": summary or f"Executed {len(steps_log)} steps.",
            "steps": steps_log
        }


hermes_general_agent = HermesGeneralAgent()
