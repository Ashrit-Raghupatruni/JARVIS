"""
Groq ultra-fast Llama-3.3 inference provider implementation.
"""
import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
from backend.utils.logger import logger
from backend.services.llm.streaming import StreamTextFilter
from backend.services.llm.tool_calling import (
    try_parse_xml_tool_call,
    try_parse_json_tool_call,
    clean_function_calls_from_text,
    check_and_execute_text_tool_call,
)


class GroqProvider:
    def __init__(self, service):
        self.service = service

    async def process_message(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Groq streaming and tool dispatch engine."""
        if not self.service.groq_client:
            yield {"type": "error", "error": "Groq client is not initialized."}
            return

        messages = self.service._build_messages(user_message, conversation_history)
        query_str = user_message if isinstance(user_message, str) else (user_message.get("content", "") if isinstance(user_message, dict) else "")

        use_tools = True
        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                kwargs = {
                    "model": self.service.groq_model_name,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }
                if use_tools:
                    kwargs["tools"] = self.service.get_tools(query_str)
                    kwargs["tool_choice"] = "auto"

                try:
                    stream = await self.service.groq_client.chat.completions.create(**kwargs)
                except Exception as e:
                    if use_tools:
                        logger.warning(f"Groq completions failed with tools: {e}. Retrying without tools...")
                        use_tools = False
                        kwargs.pop("tools", None)
                        kwargs.pop("tool_choice", None)
                        stream = await self.service.groq_client.chat.completions.create(**kwargs)
                    else:
                        raise e

                text_filter = StreamTextFilter()

                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # Handle text content
                    if delta.content:
                        full_text += delta.content
                        for text_to_yield in text_filter.feed(delta.content):
                            yield {"type": "text_delta", "content": text_to_yield}

                    # Handle tool calls
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in current_tool_calls:
                                current_tool_calls[idx] = {
                                    "id": tc.id or "",
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc.id:
                                current_tool_calls[idx]["id"] = tc.id
                            if tc.function and tc.function.name:
                                current_tool_calls[idx]["name"] = tc.function.name
                            if tc.function and tc.function.arguments:
                                current_tool_calls[idx]["arguments"] += tc.function.arguments

                    # Track usage
                    if chunk.usage:
                        self.service.total_prompt_tokens += chunk.usage.prompt_tokens
                        self.service.total_completion_tokens += chunk.usage.completion_tokens

                self.total_requests += 1

                for text_to_yield in text_filter.flush():
                    yield {"type": "text_delta", "content": text_to_yield}

                if current_tool_calls:
                    tool_call_messages = []
                    for idx in sorted(current_tool_calls.keys()):
                        tc = current_tool_calls[idx]
                        tool_call_messages.append({
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"],
                            },
                        })

                    assistant_msg: Dict[str, Any] = {
                        "role": "assistant",
                        "content": full_text or None,
                        "tool_calls": tool_call_messages,
                    }
                    messages.append(assistant_msg)

                    for tc_msg in tool_call_messages:
                        tool_name = tc_msg["function"]["name"]
                        try:
                            tool_args = json.loads(tc_msg["function"]["arguments"])
                        except json.JSONDecodeError:
                            tool_args = {}

                        yield {
                            "type": "tool_call",
                            "name": tool_name,
                            "arguments": tool_args,
                            "tool_call_id": tc_msg["id"],
                        }

                        if tool_executor:
                            try:
                                result = await tool_executor(tool_name, tool_args)
                            except Exception as e:
                                result = f"Error executing {tool_name}: {e}"
                                logger.error("Tool execution error: {}", e)
                        else:
                            result = f"Tool '{tool_name}' executed successfully (no executor connected)."

                        yield {
                            "type": "tool_result",
                            "name": tool_name,
                            "result": str(result),
                            "tool_call_id": tc_msg["id"],
                        }

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_msg["id"],
                            "content": str(result),
                        })
                    
                    full_text = ""
                    continue
                else:
                    # Check for plain-text tool call interception
                    intercepted = await self.service._check_and_execute_text_tool_call(full_text, tool_executor, messages)
                    if intercepted:
                        yield {
                            "type": "tool_call",
                            "name": intercepted["tool_name"],
                            "arguments": intercepted["tool_args"],
                            "tool_call_id": intercepted["tool_call_id"],
                        }
                        yield {
                            "type": "tool_result",
                            "name": intercepted["tool_name"],
                            "result": intercepted["result"],
                            "tool_call_id": intercepted["tool_call_id"],
                        }
                        full_text = ""
                        continue
                    else:
                        yield {"type": "text_done", "content": clean_function_calls_from_text(full_text)}
                        break

        except Exception as e:
            logger.error("Groq completions error: {}", e)
            raise

