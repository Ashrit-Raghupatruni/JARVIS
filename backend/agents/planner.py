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

        from backend.services.skills.registry import SkillRegistry
        self.skills_registry = SkillRegistry(
            automation_service=self.automation,
            browser_service=self.browser,
            memory_service=self.memory,
            screen_service=self.screen,
            safety_service=self.safety,
            planner_agent=self
        )
        if self.llm:
            self.llm.skills_registry = self.skills_registry

    async def plan_and_execute(
        self, user_message: str, conversation_history: Optional[list[dict]] = None
    ) -> AsyncGenerator[WSMessage, None]:
        """
        Process a user message: understand intent, execute tools, return response.

        Yields WSMessage objects for real-time updates to the frontend.
        """
        # Use local history instead of modifying self._conversation_history directly to avoid concurrency conflicts
        history = list(conversation_history) if conversation_history is not None else list(self._conversation_history)

        # Add user message to history
        history.append({"role": "user", "content": user_message})
        
        # Trim local history
        if len(history) > self._max_history:
            history = history[-self._max_history:]

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
        messages_for_llm = list(history)
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

            steps_list = []
            async for event in self.llm.process_message(messages_for_llm, tool_executor=self._execute_tool):
                if event["type"] == "text_delta":
                    response_text += event["content"]

                elif event["type"] == "text_done":
                    response_text = event["content"]

                elif event["type"] == "tool_call":
                    # Tool call initiated
                    tool_name = event["name"]
                    tool_args = event["arguments"]
                    tool_call_id = event["tool_call_id"]
                    
                    # Add to steps list
                    step_desc = f"{tool_name}({self._summarize_args(json.dumps(tool_args))})"
                    new_step = AgentStep(
                        id=tool_call_id,
                        description=step_desc,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        status=AgentStepStatus.RUNNING,
                    )
                    steps_list.append(new_step)
                    
                    # Yield progress update
                    completed_count = sum(1 for s in steps_list if s.status in (AgentStepStatus.COMPLETED, AgentStepStatus.FAILED))
                    progress = completed_count / len(steps_list) if steps_list else 0
                    yield WSMessage(
                        type="agent_progress",
                        data={
                            "task": user_message[:100],
                            "steps": [s.model_dump() for s in steps_list],
                            "progress": progress,
                        },
                    )

                elif event["type"] == "tool_result":
                    # Tool call completed
                    tool_name = event["name"]
                    result = event["result"]
                    tool_call_id = event["tool_call_id"]
                    
                    # Update status in steps list
                    for s in steps_list:
                        if s.id == tool_call_id:
                            s.status = AgentStepStatus.COMPLETED
                            s.result = str(result)
                            break
                    else:
                        steps_list.append(AgentStep(
                            id=tool_call_id,
                            description=f"{tool_name} completed",
                            tool_name=tool_name,
                            status=AgentStepStatus.COMPLETED,
                            result=str(result),
                        ))
                    
                    tool_calls_made.append(
                        {"function": tool_name, "args": {}, "result": str(result)[:200]}
                    )
                    
                    # Yield progress update
                    completed_count = sum(1 for s in steps_list if s.status in (AgentStepStatus.COMPLETED, AgentStepStatus.FAILED))
                    progress = completed_count / len(steps_list) if steps_list else 0
                    yield WSMessage(
                        type="agent_progress",
                        data={
                            "task": user_message[:100],
                            "steps": [s.model_dump() for s in steps_list],
                            "progress": progress,
                        },
                    )

                elif event["type"] == "error":
                    error_detail = event.get("error") or event.get("content") or "Unknown error"
                    response_text = f"I encountered an error processing your request: {error_detail}"

            # Add assistant response to history
            if response_text:
                history.append(
                    {"role": "assistant", "content": response_text}
                )

            # Update instance history if no custom history was passed (so the main chat keeps history)
            if conversation_history is None:
                self._conversation_history = history

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

            # Trigger background self-improving brain learning
            if self.memory:
                try:
                    asyncio.create_task(
                        self.memory.analyze_and_learn(
                            conversation_id="session",
                            messages=history
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to trigger conversation analysis: {e}")

            # Yield final response
            from backend.services.llm import clean_function_calls_from_text
            cleaned_text = clean_function_calls_from_text(response_text)
            yield WSMessage(
                type="response",
                data=ResponseMessage(
                    text=cleaned_text,
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

            # Check dangerous permissions before execution
            if self.safety:
                from backend.main import app
                allowed = await self.safety.request_user_permission(func_name, func_args, app)
                if not allowed:
                    logger.warning("Tool execution denied by user: {}", func_name)
                    return f"Action blocked: user denied permission to execute '{func_name}'."

            # Dispatch via dynamic skills registry if available
            try:
                res = await self.skills_registry.execute_tool(func_name, func_args)
                return str(res)
            except ValueError:
                pass

            # Automation tools
            if func_name == "open_application":
                return await self.automation.open_application(func_args.get("app_name", ""))
            elif func_name == "close_application":
                return await self.automation.close_application(func_args.get("app_name", ""))
            elif func_name == "type_text":
                return await self.automation.type_text(func_args.get("text", ""))
            elif func_name == "press_hotkey":
                keys = func_args.get("keys", "")
                return await self.automation.press_hotkey(keys)
            elif func_name == "move_mouse":
                return await self.automation.move_mouse(func_args.get("x", 0), func_args.get("y", 0))
            elif func_name == "click_mouse":
                return await self.automation.click_mouse(
                    func_args.get("button", "left"),
                    func_args.get("x"),
                    func_args.get("y"),
                )
            elif func_name == "scroll":
                return await self.automation.scroll(
                    func_args.get("direction", "down"),
                    func_args.get("amount", 3),
                )
            elif func_name == "create_file":
                return await self.automation.create_file(
                    func_args.get("path", ""),
                    func_args.get("content", ""),
                )
            elif func_name == "create_folder":
                return await self.automation.create_folder(func_args.get("path", ""))
            elif func_name == "rename_file":
                return await self.automation.rename_file(
                    func_args.get("old_path", ""),
                    func_args.get("new_path", ""),
                )
            elif func_name == "delete_file":
                return await self.automation.delete_file(func_args.get("path", ""))
            elif func_name == "run_terminal_command":
                return await self.automation.run_terminal_command(func_args.get("command", ""))
            elif func_name == "minimize_all_windows":
                return await self.automation.minimize_all_windows()
            elif func_name == "get_system_info":
                return json.dumps(await self.automation.get_system_info())
            elif func_name == "adjust_volume":
                direction = func_args.get("direction", "up")
                amount = func_args.get("amount")
                return await asyncio.to_thread(self.automation.adjust_volume, direction, amount)
            elif func_name == "control_media":
                action = func_args.get("action", "playpause")
                return await asyncio.to_thread(self.automation.control_media, action)
            elif func_name == "select_monitor":
                monitor = func_args.get("monitor", "all")
                if monitor == "all":
                    self.screen.selected_monitor = None
                elif monitor == "active":
                    self.screen.selected_monitor = "active"
                else:
                    try:
                        self.screen.selected_monitor = int(monitor)
                    except ValueError:
                        self.screen.selected_monitor = None
                return f"Monitor focus set to '{monitor}'."
            elif func_name == "focus_window":
                title = func_args.get("title", "")
                return await asyncio.to_thread(self.automation.focus_window, title)

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
            elif func_name == "play_music":
                return await self.browser.play_music(func_args.get("query", ""))
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
