"""
Planner agent for JARVIS.

The central orchestrator that receives user intents from the LLM,
routes tool calls to appropriate services, handles multi-step task
execution, and manages safety checks.
"""

import asyncio
import json
import traceback
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from loguru import logger

from backend.models.schemas import (
    AgentStep,
    AgentStepStatus,
    AssistantState,
    ResponseMessage,
    StatusMessage,
    WSMessage,
)
from backend.services.safety import SafetyService, ActionCategory


class PlannerAgent:
    """Central orchestrator agent that plans and executes user commands."""

    def __init__(
        self,
        llm_service,
        automation_service,
        screen_service,
        browser_service,
        memory_service,
        safety_service: SafetyService,
    ):
        self.llm = llm_service
        self.automation = automation_service
        self.screen = screen_service
        self.browser = browser_service
        self.memory = memory_service
        self.safety = safety_service
        self._conversation_history: list[dict] = []
        self._max_history = 20  # Keep last 20 messages for context

    async def plan_and_execute(
        self, user_message: str, conversation_history: Optional[list[dict]] = None
    ) -> AsyncGenerator[WSMessage, None]:
        """
        Process a user message: understand intent, execute tools, return response.

        Yields WSMessage objects for real-time updates to the frontend.
        """
        if conversation_history is not None:
            self._conversation_history = conversation_history

        # Add user message to history
        self._conversation_history.append({"role": "user", "content": user_message})
        self._trim_history()

        # Signal processing state
        yield WSMessage(
            type="status",
            data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
        )

        # Get relevant context from memory
        context = ""
        if self.memory:
            try:
                context = await self.memory.get_relevant_context(user_message)
            except Exception as e:
                logger.warning(f"Failed to get memory context: {e}")

        # Build messages for LLM
        messages_for_llm = list(self._conversation_history)
        if context:
            # Inject context as a system message before the user's message
            messages_for_llm.insert(
                -1,
                {
                    "role": "system",
                    "content": f"Relevant context from memory:\n{context}",
                },
            )

        try:
            # Get LLM response with potential tool calls
            response_text = ""
            tool_calls_made = []

            async for event in self.llm.process_message(messages_for_llm):
                if event["type"] == "text_delta":
                    response_text += event["content"]

                elif event["type"] == "text_done":
                    response_text = event["content"]

                elif event["type"] == "tool_calls":
                    tool_calls = event["tool_calls"]
                    tool_results = []

                    # Yield progress update
                    steps = [
                        AgentStep(
                            description=f"{tc['function']['name']}({self._summarize_args(tc['function']['arguments'])})",
                            status=AgentStepStatus.PENDING,
                        )
                        for tc in tool_calls
                    ]
                    yield WSMessage(
                        type="agent_progress",
                        data={
                            "task": user_message[:100],
                            "steps": [s.model_dump() for s in steps],
                            "current_step": 0,
                        },
                    )

                    # Execute each tool call
                    for i, tool_call in enumerate(tool_calls):
                        func_name = tool_call["function"]["name"]
                        func_args_str = tool_call["function"]["arguments"]
                        tool_call_id = tool_call["id"]

                        try:
                            func_args = json.loads(func_args_str)
                        except json.JSONDecodeError:
                            func_args = {}

                        # Update progress — mark current step as running
                        steps[i].status = AgentStepStatus.RUNNING
                        yield WSMessage(
                            type="agent_progress",
                            data={
                                "task": user_message[:100],
                                "steps": [s.model_dump() for s in steps],
                                "current_step": i,
                            },
                        )

                        # Safety check
                        safety_category = self.safety.classify_action(
                            f"{func_name}: {json.dumps(func_args)}"
                        )

                        if safety_category == ActionCategory.BLOCKED:
                            result = f"Action blocked by safety system: {func_name} is not allowed."
                            steps[i].status = AgentStepStatus.FAILED
                            logger.warning(f"Blocked action: {func_name}")
                        elif safety_category == ActionCategory.NEEDS_CONFIRMATION:
                            # For now, add a warning but still execute
                            # In production, this would pause and ask the user
                            logger.info(f"Action needs confirmation: {func_name}")
                            result = await self._execute_tool(func_name, func_args)
                            steps[i].status = AgentStepStatus.COMPLETED
                        else:
                            result = await self._execute_tool(func_name, func_args)
                            steps[i].status = AgentStepStatus.COMPLETED

                        tool_results.append(
                            {
                                "tool_call_id": tool_call_id,
                                "content": str(result),
                            }
                        )
                        tool_calls_made.append(
                            {"function": func_name, "args": func_args, "result": str(result)[:200]}
                        )

                        # Update progress
                        yield WSMessage(
                            type="agent_progress",
                            data={
                                "task": user_message[:100],
                                "steps": [s.model_dump() for s in steps],
                                "current_step": i,
                            },
                        )

                    # Feed tool results back to LLM for final response
                    async for follow_up in self.llm.process_tool_results(
                        messages_for_llm, tool_calls, tool_results
                    ):
                        if follow_up["type"] == "text_done":
                            response_text = follow_up["content"]
                        elif follow_up["type"] == "tool_calls":
                            # Handle chained tool calls (recursive execution)
                            for tc in follow_up["tool_calls"]:
                                fn = tc["function"]["name"]
                                try:
                                    fa = json.loads(tc["function"]["arguments"])
                                except json.JSONDecodeError:
                                    fa = {}
                                chained_result = await self._execute_tool(fn, fa)
                                tool_results.append(
                                    {"tool_call_id": tc["id"], "content": str(chained_result)}
                                )

                elif event["type"] == "error":
                    error_detail = event.get("error") or event.get("content") or "Unknown error"
                    response_text = f"I encountered an error processing your request: {error_detail}"

            # Add assistant response to history
            if response_text:
                self._conversation_history.append(
                    {"role": "assistant", "content": response_text}
                )

            # Log command to memory
            if self.memory and tool_calls_made:
                try:
                    await self.memory.log_command(
                        command=user_message,
                        result=response_text[:500],
                        status="success",
                    )
                except Exception:
                    pass

            # Yield final response
            yield WSMessage(
                type="response",
                data=ResponseMessage(
                    text=response_text,
                    conversation_id=None,
                ).model_dump(),
            )

        except Exception as e:
            logger.error(f"Planner execution error: {e}\n{traceback.format_exc()}")
            error_text = "I apologize, sir. I encountered an unexpected error. Please try again."
            yield WSMessage(
                type="response",
                data=ResponseMessage(text=error_text).model_dump(),
            )

    async def _execute_tool(self, func_name: str, func_args: dict) -> str:
        """Route a tool call to the appropriate service and execute it."""
        try:
            logger.info(f"Executing tool: {func_name}({json.dumps(func_args)[:100]})")

            # Automation tools
            if func_name == "open_application":
                return await asyncio.to_thread(
                    self.automation.open_application, func_args.get("app_name", "")
                )
            elif func_name == "close_application":
                return await asyncio.to_thread(
                    self.automation.close_application, func_args.get("app_name", "")
                )
            elif func_name == "type_text":
                return await asyncio.to_thread(
                    self.automation.type_text, func_args.get("text", "")
                )
            elif func_name == "press_hotkey":
                keys = func_args.get("keys", [])
                if isinstance(keys, str):
                    keys = [keys]
                return await asyncio.to_thread(self.automation.press_hotkey, *keys)
            elif func_name == "move_mouse":
                return await asyncio.to_thread(
                    self.automation.move_mouse, func_args.get("x", 0), func_args.get("y", 0)
                )
            elif func_name == "click_mouse":
                return await asyncio.to_thread(
                    self.automation.click_mouse,
                    func_args.get("button", "left"),
                    func_args.get("x"),
                    func_args.get("y"),
                )
            elif func_name == "scroll":
                return await asyncio.to_thread(
                    self.automation.scroll,
                    func_args.get("direction", "down"),
                    func_args.get("amount", 3),
                )
            elif func_name == "create_file":
                return await asyncio.to_thread(
                    self.automation.create_file,
                    func_args.get("path", ""),
                    func_args.get("content", ""),
                )
            elif func_name == "create_folder":
                return await asyncio.to_thread(
                    self.automation.create_folder, func_args.get("path", "")
                )
            elif func_name == "rename_file":
                return await asyncio.to_thread(
                    self.automation.rename_file,
                    func_args.get("old_path", ""),
                    func_args.get("new_path", ""),
                )
            elif func_name == "delete_file":
                return await asyncio.to_thread(
                    self.automation.delete_file, func_args.get("path", "")
                )
            elif func_name == "run_terminal_command":
                return await asyncio.to_thread(
                    self.automation.run_terminal_command, func_args.get("command", "")
                )
            elif func_name == "minimize_all_windows":
                return await asyncio.to_thread(self.automation.minimize_all_windows)
            elif func_name == "get_system_info":
                return json.dumps(await asyncio.to_thread(self.automation.get_system_info))

            # Screen tools
            elif func_name == "take_screenshot":
                image = await asyncio.to_thread(self.screen.take_screenshot)
                text = await asyncio.to_thread(self.screen.extract_text, image)
                return f"Screenshot captured. Visible text:\n{text[:1500]}"
            elif func_name == "read_screen_text":
                image = await asyncio.to_thread(self.screen.take_screenshot)
                text = await asyncio.to_thread(self.screen.extract_text, image)
                return text[:2000]
            elif func_name == "analyze_screen":
                image = await asyncio.to_thread(self.screen.take_screenshot)
                question = func_args.get("question", "Describe what you see on screen.")
                analysis = await self.screen.analyze_with_vision(image, question)
                return analysis

            # Browser tools
            elif func_name == "open_url":
                return await self.browser.open_url(func_args.get("url", ""))
            elif func_name == "search_web":
                return await self.browser.search_web(func_args.get("query", ""))
            elif func_name == "browser_navigate":
                return await self.browser.navigate(func_args.get("action", ""))
            elif func_name == "get_page_content":
                return await self.browser.get_page_content()

            # Memory tools
            elif func_name == "remember":
                key = func_args.get("key", "")
                value = func_args.get("value", "")
                # Store as both a preference and a memory
                if self.memory:
                    await self.memory.set_user_preference(key, value)
                    await self.memory.store_memory(
                        f"{key}: {value}", metadata={"type": "user_info", "key": key}
                    )
                return f"I'll remember that: {key} = {value}"
            elif func_name == "recall":
                query = func_args.get("query", "")
                if self.memory:
                    memories = await self.memory.search_memories(query, n_results=5)
                    if memories:
                        results = "\n".join([f"- {m['content']}" for m in memories])
                        return f"Here's what I remember:\n{results}"
                    return "I don't have any relevant memories about that."
                return "Memory system is not available."

            else:
                return f"Unknown tool: {func_name}"

        except Exception as e:
            logger.error(f"Tool execution error ({func_name}): {e}")
            return f"Error executing {func_name}: {str(e)}"

    def _trim_history(self) -> None:
        """Keep conversation history within the max limit."""
        if len(self._conversation_history) > self._max_history:
            # Keep the system message (if any) and the most recent messages
            self._conversation_history = self._conversation_history[-self._max_history :]

    @staticmethod
    def _summarize_args(args_str: str) -> str:
        """Create a short summary of function arguments."""
        try:
            args = json.loads(args_str)
            parts = []
            for k, v in args.items():
                v_str = str(v)
                if len(v_str) > 30:
                    v_str = v_str[:30] + "..."
                parts.append(f"{k}={v_str}")
            return ", ".join(parts)
        except Exception:
            return args_str[:50]

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()
        logger.info("Conversation history cleared")
