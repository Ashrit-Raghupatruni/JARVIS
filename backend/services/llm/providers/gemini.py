"""
Google Gemini provider implementation using google-genai SDK.
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


class GeminiProvider:
    def __init__(self, service):
        self.service = service

    async def process_message(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Gemini-specific message streaming and tool iteration loop."""

        # Maintain standard OpenAI format history internally for simple conversion
        messages = self.service._build_messages(user_message, conversation_history)
        query_str = user_message if isinstance(user_message, str) else (user_message.get("content", "") if isinstance(user_message, dict) else "")
        yield_final = True

        from google.genai import types

        use_gemini_tools = True
        while True:
            # Map history and tools to Google's schema on each turn
            gemini_contents = self.service._convert_history_to_gemini(messages)
            gemini_tools = self.service._convert_tools_to_gemini(self.service.get_tools(query_str)) if use_gemini_tools else []

            config = types.GenerateContentConfig(
                system_instruction=self.get_system_prompt(),
                tools=[{"function_declarations": gemini_tools}] if gemini_tools else None
            )

            try:
                # Request streaming generator from Google API
                response = await self.service.gemini_client.aio.models.generate_content_stream(
                    model=self.service.gemini_model_name,
                    contents=gemini_contents,
                    config=config
                )
            except Exception as e:
                # Rotate key and retry
                if self.service._rotate_gemini_key():
                    try:
                        response = await self.service.gemini_client.aio.models.generate_content_stream(
                            model=self.service.gemini_model_name,
                            contents=gemini_contents,
                            config=config
                        )
                    except Exception as e2:
                        if use_gemini_tools:
                            logger.warning(f"Gemini streaming failed with tools: {e2}. Retrying without tools...")
                            use_gemini_tools = False
                            config = types.GenerateContentConfig(
                                system_instruction=self.get_system_prompt(),
                                tools=None
                            )
                            response = await self.service.gemini_client.aio.models.generate_content_stream(
                                model=self.service.gemini_model_name,
                                contents=gemini_contents,
                                config=config
                            )
                        else:
                            raise e2
                elif use_gemini_tools:
                    logger.warning(f"Gemini streaming failed with tools: {e}. Retrying without tools...")
                    use_gemini_tools = False
                    config = types.GenerateContentConfig(
                        system_instruction=self.get_system_prompt(),
                        tools=None
                    )
                    response = await self.service.gemini_client.aio.models.generate_content_stream(
                        model=self.service.gemini_model_name,
                        contents=gemini_contents,
                        config=config
                    )
                else:
                    raise e

            full_text = ""
            current_tool_calls = {}
            text_filter = StreamTextFilter()

            async for chunk in response:
                # 1. Extract text content delta safely
                try:
                    if chunk.text:
                        full_text += chunk.text
                        for text_to_yield in text_filter.feed(chunk.text):
                            yield {"type": "text_delta", "content": text_to_yield}
                except Exception:
                    pass

                # 2. Extract tool call elements safely
                fn_calls = getattr(chunk, "function_calls", None)
                if fn_calls:
                    for fn_call in fn_calls:
                        tc_id = f"tc-{int(time.time())}-{len(current_tool_calls)}"
                        current_tool_calls[tc_id] = {
                            "id": tc_id,
                            "name": fn_call.name,
                            "arguments": json.dumps(dict(fn_call.args))
                        }

            for text_to_yield in text_filter.flush():
                yield {"type": "text_delta", "content": text_to_yield}

            self.total_requests += 1
            # Estimation for stats
            prompt_est = sum(len(str(p).split()) for c in gemini_contents for p in c.get("parts", [])) * 2
            comp_est = len(full_text.split()) * 2
            self.service.total_prompt_tokens += int(prompt_est)
            self.service.total_completion_tokens += int(comp_est)

            # If tool calls were initiated, trigger execution and feed result back
            if current_tool_calls:
                tool_call_messages = []
                for tc_id in sorted(current_tool_calls.keys()):
                    tc = current_tool_calls[tc_id]
                    tool_call_messages.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    })

                assistant_msg = {
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
                        "name": tool_name,
                        "content": str(result),
                    })

                # Clear response and re-loop so LLM answers based on new context
                full_text = ""
                continue

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

            # Finish conversation turn
            if full_text and yield_final:
                yield {"type": "text_done", "content": clean_function_calls_from_text(full_text)}

            yield {
                "type": "usage",
                "prompt_tokens": self.service.total_prompt_tokens,
                "completion_tokens": self.service.total_completion_tokens,
                "total_requests": self.total_requests,
            }
            break

