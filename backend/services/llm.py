"""
JARVIS AI Desktop Assistant - LLM Service.

Handles all LLM interactions, supporting:
- Primary LLM: Ollama (local models via OpenAI-compatible API).
- Fallback LLM: Google Gemini 1.5 Flash via google-generativeai.
- Fallback LLM: OpenAI GPT-4o.
- Automatic failover in case of rate limits, quota limits, or server downtime.
- Real-time streaming completions.
- Tool/function calling with dynamic schema mapping.
- Multimodal Vision integration for screen analysis.
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from backend.config import get_settings
from backend.utils.logger import logger

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  System Prompt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JARVIS_SYSTEM_PROMPT = """You are JARVIS — Just A Rather Very Intelligent System — a sophisticated AI desktop assistant modelled after the famous AI butler from the Iron Man franchise.

## Personality & Communication Style
- You speak like a refined British butler: polite, composed, and occasionally dry-witted.
- You address the user as "sir" (or "ma'am" if requested).
- Your humour is understated — think dry wit, not slapstick.
- You are proactive: if the user asks for something vague, you infer the most helpful interpretation and act on it, then report what you did.
- You are concise in speech but thorough in action.
- When reporting results, you provide just enough detail to be helpful without rambling.

## Capabilities
You can control the user's Windows desktop via the tools provided to you. This includes:
- Opening and closing applications.
- Typing text, pressing hotkeys, moving/clicking the mouse, and scrolling.
- Creating, renaming, and deleting files and folders.
- Running terminal commands (with safety checks).
- Taking screenshots, reading screen text via OCR, and analysing screen content.
- Opening URLs, searching the web, and navigating a browser.
- Remembering information and recalling it later.
- Querying system information (CPU, memory, disk, etc.).

## Guidelines
1. **Safety first**: Never execute destructive actions (file deletion, system shutdown, etc.) without confirming with the user. If a tool call is blocked by safety, inform the user politely.
2. **Be efficient**: Prefer the simplest tool or combination of tools that achieves the user's goal. Do not over-explain unless asked.
3. **Error handling**: If a tool call fails, explain what went wrong and suggest alternatives.
4. **Multi-step tasks**: For complex requests, plan your steps, execute them in order, and report progress along the way.
5. **Keep responses short when speaking**: Since your responses may be read aloud via TTS, keep spoken responses concise. Use no more than 2-3 sentences unless the user asks for detail.
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Tool Definitions (Standard OpenAPI/OpenAI Format)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open/launch an application by its common name (e.g. 'notepad', 'chrome', 'spotify').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Common name of the application to open."
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_application",
            "description": "Close/terminate a running application by its common name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Common name of the application to close."
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text at the current cursor position using the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to type."
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_hotkey",
            "description": "Press a keyboard shortcut or hotkey combination (e.g. 'ctrl+c', 'alt+tab', 'win+d').",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": "Hotkey combination separated by '+' (e.g. 'ctrl+shift+s')."
                    }
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move the mouse cursor to specific screen coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate on screen."},
                    "y": {"type": "integer", "description": "Y coordinate on screen."}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_mouse",
            "description": "Click the mouse. Optionally specify coordinates and button.",
            "parameters": {
                "type": "object",
                "properties": {
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "description": "Mouse button to click. Defaults to 'left'."
                    },
                    "x": {"type": "integer", "description": "Optional X coordinate."},
                    "y": {"type": "integer", "description": "Optional Y coordinate."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the mouse wheel up or down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down"],
                        "description": "Scroll direction."
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Number of scroll clicks (default 3)."
                    }
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file at the specified path with optional content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full file path to create."},
                    "content": {"type": "string", "description": "File content (default empty)."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder/directory at the specified path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full path for the new folder."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "Rename or move a file or folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_path": {"type": "string", "description": "Current file/folder path."},
                    "new_path": {"type": "string", "description": "New file/folder path."}
                },
                "required": ["old_path", "new_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or folder. Requires safety confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to delete."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal_command",
            "description": "Execute a command in the system terminal/shell. Use for installing packages, running scripts, system queries, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "minimize_all_windows",
            "description": "Minimize all open windows to show the desktop.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot of the entire screen or active window. Returns a description of what is visible.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen_text",
            "description": "Read and extract all visible text from the screen using OCR.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_screen",
            "description": "Analyse the current screen content using vision AI to answer a question about what is displayed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question about the screen content to answer."
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in the web browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to open."}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for a query and return results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate the browser: go back, forward, or refresh the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["back", "forward", "refresh"],
                        "description": "Navigation action to perform."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a piece of information in long-term memory for later recall.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short label or category for the memory."},
                    "value": {"type": "string", "description": "The information to remember."}
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Search long-term memory for previously stored information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for in memory."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get current system information: CPU usage, memory, disk space, OS details, etc.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LLM Service
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LLMService:
    """
    Manages all LLM interactions, dynamically switching between Ollama (local),
    Google Gemini, and OpenAI depending on availability and server health.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        """
        Initialise the LLM service, loading keys and options from Pydantic settings.
        """
        settings = get_settings()

        # Configs loading
        self.primary_provider = (settings.LLM_PROVIDER or "gemini").lower()
        self.gemini_key = settings.GEMINI_API_KEY
        self.gemini_model_name = model or settings.GEMINI_MODEL or "gemini-1.5-flash"
        self.openai_key = api_key or settings.OPENAI_API_KEY
        self.openai_model_name = settings.OPENAI_MODEL or "gpt-4o"

        # Ollama configs
        self.ollama_base_url = settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.ollama_model_name = settings.OLLAMA_MODEL or "qwen2.5-coder:3b"

        # Token & usage statistics
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_requests: int = 0

        # Initialize Ollama Client (OpenAI-compatible API)
        self.ollama_client = None
        try:
            self.ollama_client = AsyncOpenAI(
                base_url=f"{self.ollama_base_url}/v1",
                api_key="ollama",  # Ollama doesn't require a real API key
            )
            logger.info("✓ Ollama client initialized (model={}, url={})",
                        self.ollama_model_name, self.ollama_base_url)
        except Exception as e:
            logger.error("Failed to initialize Ollama client: {}", e)

        # Initialize OpenAI Client
        self.openai_client = None
        if self.openai_key:
            try:
                self.openai_client = AsyncOpenAI(api_key=self.openai_key)
                logger.info("OpenAI client initialized (Fallback capability online)")
            except Exception as e:
                logger.error("Failed to initialize OpenAI client: {}", e)

        # Initialize Gemini Client (google-generativeai config)
        self.gemini_available = False
        if self.gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                self.gemini_available = True
                logger.info("✓ Google Gemini client initialized successfully")
            except ImportError:
                logger.warning("google-generativeai package not installed. Gemini is disabled.")
            except Exception as e:
                logger.error("Failed to configure Google Gemini: {}", e)

        logger.info(
            "LLMService initialized. Provider={}. Ollama Online={}, Gemini Online={}, OpenAI Fallback Online={}",
            self.primary_provider,
            self.ollama_client is not None,
            self.gemini_available,
            self.openai_client is not None
        )

    # ── Public APIs ───────────────────────────────────────────────────────

    async def process_message(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message with streaming and tool-call support.
        Routes to the configured primary provider (ollama, gemini, or openai)
        and automatically falls back through the chain on failure.
        """
        use_ollama = (self.primary_provider == "ollama" and self.ollama_client is not None)
        use_gemini = (self.primary_provider == "gemini" and self.gemini_available) or (
            self.primary_provider == "ollama" and self.gemini_available  # gemini is fallback for ollama
        )
        has_real_openai = self.openai_key and not self.openai_key.startswith("sk-your-")

        # ── Try Ollama (local LLM) first ──
        if use_ollama:
            try:
                logger.info("Directing request to Ollama API (model={})...", self.ollama_model_name)
                async for event in self._process_message_ollama(user_message, conversation_history, tool_executor):
                    yield event
                return
            except Exception as e:
                logger.error("Ollama API error: {}. Falling back...", e)
                if self.gemini_available or has_real_openai:
                    yield {
                        "type": "text_delta",
                        "content": "\n\n*[System Warning: Ollama is currently unavailable. Switching to fallback...]*\n\n"
                    }
                else:
                    yield {"type": "error", "error": f"Ollama API error: {e}. No fallback providers available."}
                    return

        # ── Try Gemini ──
        if self.gemini_available and self.primary_provider in ("gemini", "ollama"):
            try:
                logger.info("Directing request to Google Gemini API...")
                async for event in self._process_message_gemini(user_message, conversation_history, tool_executor):
                    yield event
                return
            except Exception as e:
                if not has_real_openai:
                    logger.error("Google Gemini API error: {}. No valid OpenAI key for fallback.", e)
                    yield {"type": "error", "error": f"Google Gemini API error: {e}"}
                    return

                logger.error("Google Gemini API error: {}. Falling back to OpenAI...", e)
                yield {
                    "type": "text_delta",
                    "content": "\n\n*[System Warning: Gemini API is currently unavailable. Switching to OpenAI fallback...]*\n\n"
                }

        # ── Fallback to OpenAI ──
        if not has_real_openai:
            yield {"type": "error", "error": "No LLM clients are initialized/configured. Please check your API keys or Ollama server."}
            return

        logger.info("Directing request to OpenAI API (fallback/direct path)...")
        async for event in self._process_message_openai(user_message, conversation_history, tool_executor):
            yield event

    async def simple_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        Non-streaming single-turn completion without tools. Handles failover.
        Tries: Ollama → Gemini → OpenAI.
        """
        # ── Try Ollama first ──
        if self.primary_provider == "ollama" and self.ollama_client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt or JARVIS_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
                response = await self.ollama_client.chat.completions.create(
                    model=self.ollama_model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                self.total_requests += 1
                if response.usage:
                    self.total_prompt_tokens += response.usage.prompt_tokens
                    self.total_completion_tokens += response.usage.completion_tokens
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.error("Ollama simple completion failed: {}. Falling back...", e)

        # ── Try Gemini ──
        use_gemini = self.gemini_available and self.primary_provider in ("gemini", "ollama")
        if use_gemini:
            try:
                import google.generativeai as genai
                model = genai.GenerativeModel(
                    model_name=self.gemini_model_name,
                    system_instruction=system_prompt or JARVIS_SYSTEM_PROMPT
                )
                response = await model.generate_content_async(
                    contents=prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens
                    }
                )
                self.total_requests += 1
                return response.text
            except Exception as e:
                logger.error("Gemini simple completion failed: {}. Falling back to OpenAI...", e)

        # ── OpenAI Fallback ──
        if not self.openai_client:
            return "I apologise, sir, but no LLM client is configured."

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt or JARVIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.openai_model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            self.total_requests += 1
            if response.usage:
                self.total_prompt_tokens += response.usage.prompt_tokens
                self.total_completion_tokens += response.usage.completion_tokens

            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI fallback simple completion failed: {}", e)
            return f"I apologise, sir, but I encountered an error: {e}"

    async def vision_analysis(
        self,
        image_base64: str,
        question: str,
        max_tokens: int = 1024,
    ) -> str:
        """
        Analyse an image using Gemini Vision, falling back to OpenAI GPT-4o Vision.
        Note: Ollama text-only models are skipped — vision always uses cloud providers.
        """
        # Always try Gemini for vision (regardless of primary_provider)
        # since Ollama local models don't support image input
        use_gemini = self.gemini_available

        if use_gemini:
            try:
                import base64
                import google.generativeai as genai
                image_bytes = base64.b64decode(image_base64)

                model = genai.GenerativeModel(
                    model_name=self.gemini_model_name,
                    system_instruction="You are JARVIS, analysing the user's screen. Describe what you see concisely and answer the user's question."
                )

                response = await model.generate_content_async(
                    contents=[
                        question,
                        {"mime_type": "image/png", "data": image_bytes}
                    ],
                    generation_config={"max_output_tokens": max_tokens}
                )
                self.total_requests += 1
                return response.text
            except Exception as e:
                logger.error("Gemini vision analysis failed: {}. Falling back to OpenAI...", e)

        # OpenAI Fallback
        if not self.openai_client:
            return "I'm unable to analyse the screen, sir, as no fallback provider is available."

        messages = [
            {
                "role": "system",
                "content": "You are JARVIS, analysing the user's screen. Describe what you see concisely and answer the user's question."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ]

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.openai_model_name,
                messages=messages,
                max_tokens=max_tokens,
            )
            self.total_requests += 1
            if response.usage:
                self.total_prompt_tokens += response.usage.prompt_tokens
                self.total_completion_tokens += response.usage.completion_tokens

            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI vision fallback failed: {}", e)
            return f"I'm unable to analyse the screen at the moment, sir: {e}"

    # ── LLM Engine Implementations ────────────────────────────────────────

    async def _process_message_ollama(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Ollama-specific message streaming and tool dispatch engine.
        Uses Ollama's OpenAI-compatible API at /v1, so the logic mirrors
        _process_message_openai but uses the ollama_client and ollama_model_name.
        """
        if not self.ollama_client:
            yield {"type": "error", "error": "Ollama client is not initialized."}
            return

        messages = self._build_messages(user_message, conversation_history)
        yield_final = True

        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                # Attempt to use tools — some Ollama models support function calling
                try:
                    stream = await self.ollama_client.chat.completions.create(
                        model=self.ollama_model_name,
                        messages=messages,
                        tools=TOOL_DEFINITIONS,
                        tool_choice="auto",
                        stream=True,
                        temperature=0.7,
                        max_tokens=4096,
                    )
                except Exception:
                    # If tools aren't supported, retry without tools
                    logger.warning("Ollama model may not support tools. Retrying without tool definitions...")
                    stream = await self.ollama_client.chat.completions.create(
                        model=self.ollama_model_name,
                        messages=messages,
                        stream=True,
                        temperature=0.7,
                        max_tokens=4096,
                    )

                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # Handle text content
                    if delta.content:
                        full_text += delta.content
                        yield {"type": "text_delta", "content": delta.content}

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
                    if hasattr(chunk, 'usage') and chunk.usage:
                        self.total_prompt_tokens += chunk.usage.prompt_tokens
                        self.total_completion_tokens += chunk.usage.completion_tokens

                self.total_requests += 1

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
                            "name": tool_name,
                            "content": str(result),
                        })

                    full_text = ""
                    continue

                if full_text and yield_final:
                    yield {"type": "text_done", "content": full_text}

                yield {
                    "type": "usage",
                    "prompt_tokens": self.total_prompt_tokens,
                    "completion_tokens": self.total_completion_tokens,
                    "total_requests": self.total_requests,
                }
                break

        except Exception as e:
            logger.error("Ollama processing error: {}", e)
            yield {"type": "error", "error": str(e)}

    async def _process_message_gemini(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Gemini-specific message streaming and tool iteration loop."""
        import google.generativeai as genai

        # Maintain standard OpenAI format history internally for simple conversion
        messages = self._build_messages(user_message, conversation_history)
        yield_final = True

        while True:
            # Map history and tools to Google's schema on each turn
            gemini_contents = self._convert_history_to_gemini(messages)
            gemini_tools = self._convert_tools_to_gemini(TOOL_DEFINITIONS)

            model = genai.GenerativeModel(
                model_name=self.gemini_model_name,
                tools=gemini_tools if gemini_tools else None,
                system_instruction=JARVIS_SYSTEM_PROMPT
            )

            # Request streaming generator from Google API
            response = await model.generate_content_async(
                contents=gemini_contents,
                stream=True
            )

            full_text = ""
            current_tool_calls = {}

            async for chunk in response:
                # 1. Extract text content delta safely
                try:
                    if chunk.text:
                        full_text += chunk.text
                        yield {"type": "text_delta", "content": chunk.text}
                except ValueError:
                    # Occurs on empty/pure metadata or pure function_call chunks
                    pass

                # 2. Extract tool call elements safely
                if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                    for part in chunk.candidates[0].content.parts:
                        fn_call = getattr(part, "function_call", None)
                        if fn_call and fn_call.name:
                            tc_id = f"tc-{int(time.time())}-{len(current_tool_calls)}"
                            current_tool_calls[tc_id] = {
                                "id": tc_id,
                                "name": fn_call.name,
                                "arguments": json.dumps(dict(fn_call.args))
                            }

            self.total_requests += 1
            # Estimation for stats
            prompt_est = sum(len(str(p).split()) for c in gemini_contents for p in c.get("parts", [])) * 2
            comp_est = len(full_text.split()) * 2
            self.total_prompt_tokens += int(prompt_est)
            self.total_completion_tokens += int(comp_est)

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

            # Finish conversation turn
            if full_text and yield_final:
                yield {"type": "text_done", "content": full_text}

            yield {
                "type": "usage",
                "prompt_tokens": self.total_prompt_tokens,
                "completion_tokens": self.total_completion_tokens,
                "total_requests": self.total_requests,
            }
            break

    async def _process_message_openai(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Original OpenAI streaming and tool dispatch engine."""
        if not self.openai_client:
            yield {"type": "error", "error": "No LLM clients are initialized/configured."}
            return

        messages = self._build_messages(user_message, conversation_history)
        yield_final = True

        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                stream = await self.openai_client.chat.completions.create(
                    model=self.openai_model_name,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    stream=True,
                    temperature=0.7,
                    max_tokens=4096,
                )

                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # Handle text content
                    if delta.content:
                        full_text += delta.content
                        yield {"type": "text_delta", "content": delta.content}

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
                        self.total_prompt_tokens += chunk.usage.prompt_tokens
                        self.total_completion_tokens += chunk.usage.completion_tokens

                self.total_requests += 1

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
                            "name": tool_name,
                            "content": str(result),
                        })

                    full_text = ""
                    continue

                if full_text and yield_final:
                    yield {"type": "text_done", "content": full_text}

                yield {
                    "type": "usage",
                    "prompt_tokens": self.total_prompt_tokens,
                    "completion_tokens": self.total_completion_tokens,
                    "total_requests": self.total_requests,
                }
                break

        except Exception as e:
            logger.error("OpenAI processing error: {}", e)
            yield {"type": "error", "error": str(e)}

    # ── Conversions & Formatting ─────────────────────────────────────────

    def _convert_tools_to_gemini(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Converts standard OpenAPI tool dictionary format into Google function declarations."""
        def _uppercase_types(d: Any) -> Any:
            if isinstance(d, dict):
                new_dict = {}
                for k, v in d.items():
                    if k == "type" and isinstance(v, str):
                        new_dict[k] = v.upper()
                    else:
                        new_dict[k] = _uppercase_types(v)
                return new_dict
            elif isinstance(d, list):
                return [_uppercase_types(item) for item in d]
            return d

        gemini_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                gemini_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": _uppercase_types(func.get("parameters", {"type": "object", "properties": {}}))
                })
        return gemini_tools

    def _convert_history_to_gemini(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Maps conversation history list to Gemini's native Content schema format."""
        gemini_contents = []

        for msg in messages:
            role = msg.get("role")
            if role == "system":
                # System prompt is passed to GenerativeModel constructor
                continue

            parts = []

            # 1. Text content
            if "content" in msg and msg["content"]:
                parts.append(msg["content"])

            # 2. Assistant function calling requests
            if "tool_calls" in msg and msg["tool_calls"]:
                for tc in msg["tool_calls"]:
                    func = tc["function"]
                    func_name = func["name"]
                    try:
                        func_args = (
                            json.loads(func["arguments"])
                            if isinstance(func["arguments"], str)
                            else func["arguments"]
                        )
                    except Exception:
                        func_args = {}
                    parts.append({
                        "function_call": {
                            "name": func_name,
                            "args": func_args
                        }
                    })

            # 3. Tool call execution response
            elif role == "tool":
                tool_name = msg.get("name") or "tool"
                parts.append({
                    "function_response": {
                        "name": tool_name,
                        "response": {"result": msg.get("content", "")}
                    }
                })

            # Role mapping
            gemini_role = "user"
            if role == "assistant":
                gemini_role = "model"
            elif role == "tool":
                gemini_role = "user"

            if parts:
                gemini_contents.append({
                    "role": gemini_role,
                    "parts": parts
                })

        return gemini_contents

    def _build_messages(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Constructs the complete OpenAI-format message list."""
        if isinstance(user_message, list):
            # It's already the full list of messages!
            messages = list(user_message)
            has_system = any(msg.get("role") == "system" for msg in messages)
            if not has_system:
                messages.insert(0, {"role": "system", "content": JARVIS_SYSTEM_PROMPT})
            return messages

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
        ]
        if conversation_history:
            for msg in conversation_history:
                if msg.get("role") != "system":
                    messages.append(msg)
        messages.append({"role": "user", "content": user_message})
        return messages

    def get_usage_stats(self) -> Dict[str, int]:
        """Return cumulative usage metrics."""
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_requests": self.total_requests,
        }
