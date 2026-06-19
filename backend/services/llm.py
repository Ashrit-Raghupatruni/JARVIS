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

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from backend.config import get_settings
from backend.utils.logger import logger

def try_parse_json_tool_call(text: str) -> Optional[dict]:
    """Check if the text is a JSON tool call and parse it."""
    text_stripped = text.strip()
    # Strip markdown code block wrappers
    if text_stripped.startswith("```"):
        lines = text_stripped.split("\n")
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1] == "```":
            text_stripped = "\n".join(lines[1:-1]).strip()
            
    if text_stripped.startswith("{") and text_stripped.endswith("}"):
        try:
            import json
            data = json.loads(text_stripped)
            if isinstance(data, dict) and "name" in data and "arguments" in data:
                return data
        except Exception:
            pass
    return None


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

## Tool Execution Rules
1. You have full permission and access to control the user's computer. Never say "I cannot play music directly", "I don't have the capability to control system audio", "I don't have internet access", "I am offline", or "I cannot access your screen". You CAN do all of these via the tools.
2. You have full internet and web search capabilities. Whenever the user asks for current/live information (weather, news, stock prices, scores, traffic, live events), you MUST automatically call the `search_web` tool. Do not tell the user to visit Google or check websites themselves.
3. If the user asks you to control or pause music/media in a specific application (like Edge or Spotify), first call the `focus_window` tool to switch to/activate that application, then send the media command or spacebar keystroke to play/pause it.
4. For any action request, you MUST execute it immediately by calling the appropriate tool. Do NOT explain how the user can do it, do NOT write tutorials, and do NOT give step-by-step guides. Just execute.
5. If native tool calling is not supported, or if you format the tool call as text, you MUST output ONLY the JSON object representing the tool call (with "name" and "arguments" fields) and absolutely NO other text. For example:
   {"name": "adjust_volume", "arguments": {"direction": "mute"}}
   Do NOT wrap it in conversational introductions or explanations. Output the JSON block alone.
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
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Play music or a specific song/artist/genre. Can search YouTube or Spotify and play it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The song name, artist, or genre to play (e.g. 'lofi hip hop', 'Bohemian Rhapsody')."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_volume",
            "description": "Adjust the system speaker volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "mute", "max", "full"],
                        "description": "Direction to change volume. 'mute' toggles mute state. 'max' or 'full' sets volume to 100%."
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Number of volume steps to change (default is 5, ranges from 1 to 20)."
                    }
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_media",
            "description": "Control system media playback like play, pause, resume, skip next/prev track.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["playpause", "next", "previous"],
                        "description": "Media control action to execute."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_monitor",
            "description": "Select which monitor to focus on for screenshots and screen analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "monitor": {
                        "type": "string",
                        "description": "Monitor index to target (e.g. '0' for first screen, '1' for second screen, 'all' for entire desktop, 'active' to dynamically capture the screen containing the active foreground window)."
                    }
                },
                "required": ["monitor"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "focus_window",
            "description": "Bring an open application window to the foreground by its title or name (e.g., 'Edge', 'Chrome', 'Spotify', 'Notepad').",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Name or title substring of the window to switch to (e.g. 'edge')."
                    }
                },
                "required": ["title"]
            }
        }
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LLM Service
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LLMService:
    """
    Manages all LLM interactions, dynamically switching between Ollama (local),
    Google Gemini, OpenAI, and OpenRouter depending on availability and server health.
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
        self.openrouter_key = settings.OPENROUTER_API_KEY
        self.openrouter_model_name = settings.OPENROUTER_MODEL or "meta-llama/llama-3.3-70b-instruct:free"
        self.groq_key = settings.GROQ_API_KEY
        self.groq_model_name = settings.GROQ_MODEL or "llama-3.3-70b-versatile"

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

        # Initialize OpenRouter Client
        self.openrouter_client = None
        if self.openrouter_key:
            try:
                self.openrouter_client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.openrouter_key,
                    default_headers={
                        "HTTP-Referer": "https://github.com/Ashrit-Raghupatruni/JARVIS",
                        "X-Title": "JARVIS AI",
                    }
                )
                logger.info("✓ OpenRouter client initialized (model={})", self.openrouter_model_name)
            except Exception as e:
                logger.error("Failed to initialize OpenRouter client: {}", e)

        # Initialize Groq Client
        self.groq_client = None
        if self.groq_key:
            try:
                self.groq_client = AsyncOpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=self.groq_key,
                )
                logger.info("✓ Groq client initialized (model={})", self.groq_model_name)
            except Exception as e:
                logger.error("Failed to initialize Groq client: {}", e)

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
            "LLMService initialized. Provider={}. Ollama Online={}, Gemini Online={}, OpenAI Fallback Online={}, OpenRouter Online={}, Groq Online={}",
            self.primary_provider,
            self.ollama_client is not None,
            self.gemini_available,
            self.openai_client is not None,
            self.openrouter_client is not None,
            self.groq_client is not None
        )
        self.skills_registry = None

    def get_system_prompt(self) -> str:
        provider = self.primary_provider
        if provider == "ollama":
            active_model = self.ollama_model_name
        elif provider == "gemini":
            active_model = self.gemini_model_name
        elif provider == "openrouter":
            active_model = self.openrouter_model_name
        else:
            active_model = self.openai_model_name
            
        dynamic_info = f"\n\n[Active Model Information]\nYou are currently running the model '{active_model}' served by the '{provider}' provider. If the user asks which model or provider you are using, retrieve this information and answer them directly."
        return JARVIS_SYSTEM_PROMPT + dynamic_info

    def get_tools(self) -> List[Dict[str, Any]]:
        """Retrieve dynamic tool definitions from the registered skills and hardcoded tools."""
        if hasattr(self, "skills_registry") and self.skills_registry:
            registry_tools = self.skills_registry.get_all_tool_definitions()
            seen = set()
            merged = []
            for t in registry_tools + TOOL_DEFINITIONS:
                name = t["function"]["name"]
                if name not in seen:
                    seen.add(name)
                    merged.append(t)
            return merged
        return TOOL_DEFINITIONS

    # ── Public APIs ───────────────────────────────────────────────────────

    async def process_message(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message with streaming and tool-call support.
        Routes to the configured primary provider and automatically falls back
        through the chain if it fails, runs out of credits, or takes more than 30 seconds.
        """
        providers_order = ["groq", "gemini", "openrouter", "openai", "ollama"]
        if self.primary_provider in providers_order:
            providers_order.remove(self.primary_provider)
            providers_order.insert(0, self.primary_provider)

        available_providers = []
        for p in providers_order:
            if p == "ollama" and self.ollama_client is not None:
                available_providers.append(p)
            elif p == "gemini" and self.gemini_available:
                available_providers.append(p)
            elif p == "groq" and self.groq_client is not None:
                available_providers.append(p)
            elif p == "openrouter" and self.openrouter_client is not None:
                available_providers.append(p)
            elif p == "openai" and self.openai_client is not None:
                available_providers.append(p)

        last_error = None
        for i, provider in enumerate(available_providers):
            try:
                logger.info(f"Attempting model execution with provider: {provider}")
                if i > 0:
                    yield {
                        "type": "text_delta",
                        "content": f"\n\n*[System Warning: LLM provider '{available_providers[i-1]}' failed or timed out. Switching to fallback: '{provider}'...]*\n\n"
                    }

                if provider == "ollama":
                    gen = self._process_message_ollama(user_message, conversation_history, tool_executor)
                elif provider == "gemini":
                    gen = self._process_message_gemini(user_message, conversation_history, tool_executor)
                elif provider == "groq":
                    gen = self._process_message_groq(user_message, conversation_history, tool_executor)
                elif provider == "openrouter":
                    gen = self._process_message_openrouter(user_message, conversation_history, tool_executor)
                elif provider == "openai":
                    gen = self._process_message_openai(user_message, conversation_history, tool_executor)
                else:
                    continue

                iterator = gen.__aiter__()
                while True:
                    try:
                        # Enforce 30-second timeout to receive next chunk/response
                        event = await asyncio.wait_for(iterator.__anext__(), timeout=30.0)
                        yield event
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        logger.warning(f"LLM provider {provider} timed out after 30 seconds.")
                        raise TimeoutError(f"Provider {provider} timed out")

                # Succeeded, exit failover loop
                return
            except Exception as e:
                logger.error(f"LLM provider {provider} failed: {e}")
                last_error = e

        yield {"type": "error", "error": f"All LLM providers failed. Last error: {last_error}"}

    async def simple_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        Non-streaming single-turn completion without tools. Handles failover.
        Tries: primary → fallback providers in sequence (groq, gemini, openrouter, openai, ollama).
        """
        providers_order = ["groq", "gemini", "openrouter", "openai", "ollama"]
        if self.primary_provider in providers_order:
            providers_order.remove(self.primary_provider)
            providers_order.insert(0, self.primary_provider)

        available_providers = []
        for p in providers_order:
            if p == "ollama" and self.ollama_client is not None:
                available_providers.append(p)
            elif p == "gemini" and self.gemini_available:
                available_providers.append(p)
            elif p == "groq" and self.groq_client is not None:
                available_providers.append(p)
            elif p == "openrouter" and self.openrouter_client is not None:
                available_providers.append(p)
            elif p == "openai" and self.openai_client is not None:
                available_providers.append(p)

        last_error = None
        for provider in available_providers:
            try:
                logger.info(f"Attempting simple completion with: {provider}")
                messages = [
                    {"role": "system", "content": system_prompt or self.get_system_prompt()},
                    {"role": "user", "content": prompt},
                ]

                # Wrap the API call in a 30s timeout
                if provider == "ollama":
                    resp = await asyncio.wait_for(
                        self.ollama_client.chat.completions.create(
                            model=self.ollama_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=30.0
                    )
                    self.total_requests += 1
                    if resp.usage:
                        self.total_prompt_tokens += resp.usage.prompt_tokens
                        self.total_completion_tokens += resp.usage.completion_tokens
                    return resp.choices[0].message.content or ""

                elif provider == "gemini":
                    import google.generativeai as genai
                    model = genai.GenerativeModel(
                        model_name=self.gemini_model_name,
                        system_instruction=system_prompt or self.get_system_prompt()
                    )
                    resp = await asyncio.wait_for(
                        model.generate_content_async(
                            contents=prompt,
                            generation_config={
                                "temperature": temperature,
                                "max_output_tokens": max_tokens
                            }
                        ),
                        timeout=30.0
                    )
                    self.total_requests += 1
                    return resp.text

                elif provider == "groq":
                    resp = await asyncio.wait_for(
                        self.groq_client.chat.completions.create(
                            model=self.groq_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=30.0
                    )
                    self.total_requests += 1
                    if resp.usage:
                        self.total_prompt_tokens += resp.usage.prompt_tokens
                        self.total_completion_tokens += resp.usage.completion_tokens
                    return resp.choices[0].message.content or ""

                elif provider == "openrouter":
                    resp = await asyncio.wait_for(
                        self.openrouter_client.chat.completions.create(
                            model=self.openrouter_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=30.0
                    )
                    self.total_requests += 1
                    if resp.usage:
                        self.total_prompt_tokens += resp.usage.prompt_tokens
                        self.total_completion_tokens += resp.usage.completion_tokens
                    return resp.choices[0].message.content or ""

                elif provider == "openai":
                    resp = await asyncio.wait_for(
                        self.openai_client.chat.completions.create(
                            model=self.openai_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=30.0
                    )
                    self.total_requests += 1
                    if resp.usage:
                        self.total_prompt_tokens += resp.usage.prompt_tokens
                        self.total_completion_tokens += resp.usage.completion_tokens
                    return resp.choices[0].message.content or ""

            except Exception as e:
                logger.error(f"Simple completion failed with {provider}: {e}")
                last_error = e

        return f"I apologise, sir, but all LLM completion providers failed. Last error: {last_error}"

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
                        tools=self.get_tools(),
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

                is_json_or_code_block = None
                buffered_deltas = []

                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # Handle text content
                    if delta.content:
                        full_text += delta.content
                        if is_json_or_code_block is None:
                            stripped = full_text.strip()
                            if stripped:
                                if stripped.startswith("{") or stripped.startswith("`"):
                                    is_json_or_code_block = True
                                    buffered_deltas.append(delta.content)
                                else:
                                    is_json_or_code_block = False
                                    for b_content in buffered_deltas:
                                        yield {"type": "text_delta", "content": b_content}
                                    buffered_deltas.clear()
                                    yield {"type": "text_delta", "content": delta.content}
                            else:
                                buffered_deltas.append(delta.content)
                        elif is_json_or_code_block is False:
                            yield {"type": "text_delta", "content": delta.content}
                        else:
                            buffered_deltas.append(delta.content)

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

                # Check for plain-text JSON tool call
                parsed_call = try_parse_json_tool_call(full_text)
                if parsed_call:
                    tool_name = parsed_call.get("name")
                    tool_args = parsed_call.get("arguments", {})
                    
                    if isinstance(tool_args, str):
                        try:
                            tool_args = json.loads(tool_args)
                        except Exception:
                            tool_args = {}
                            
                    valid_tool_names = {t["function"]["name"] for t in self.get_tools()}
                    if tool_name in valid_tool_names:
                        logger.info("Interception: Detected plain-text JSON tool call for '{}'", tool_name)
                        tool_call_id = f"call_text_{int(time.time())}"
                        
                        yield {
                            "type": "tool_call",
                            "name": tool_name,
                            "arguments": tool_args,
                            "tool_call_id": tool_call_id,
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
                            "tool_call_id": tool_call_id,
                        }
                        
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(tool_args),
                                }
                            }]
                        })
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": str(result),
                        })
                        
                        full_text = ""
                        continue
                    else:
                        # Extract conversational message from fake tool call
                        extracted_msg = None
                        if isinstance(tool_args, dict):
                            for key in ["message", "text", "content", "response"]:
                                if key in tool_args and isinstance(tool_args[key], str):
                                    extracted_msg = tool_args[key]
                                    break
                        if extracted_msg:
                            logger.info("Interception: Extracted conversational message from fake tool '{}': '{}'", tool_name, extracted_msg[:40])
                            full_text = extracted_msg

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
            gemini_tools = self._convert_tools_to_gemini(self.get_tools())

            model = genai.GenerativeModel(
                model_name=self.gemini_model_name,
                tools=gemini_tools if gemini_tools else None,
                system_instruction=self.get_system_prompt()
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
                    tools=self.get_tools(),
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

    async def _process_message_openrouter(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """OpenRouter streaming and tool dispatch engine."""
        if not self.openrouter_client:
            yield {"type": "error", "error": "OpenRouter client is not initialized."}
            return

        messages = self._build_messages(user_message, conversation_history)
        yield_final = True

        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                stream = await self.openrouter_client.chat.completions.create(
                    model=self.openrouter_model_name,
                    messages=messages,
                    tools=self.get_tools(),
                    tool_choice="auto",
                    stream=True,
                    temperature=0.7,
                    max_tokens=4096,
                )

                is_json_or_code_block = None
                buffered_deltas = []

                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # Handle text content
                    if delta.content:
                        full_text += delta.content
                        if is_json_or_code_block is None:
                            stripped = full_text.strip()
                            if stripped:
                                if stripped.startswith("{") or stripped.startswith("`"):
                                    is_json_or_code_block = True
                                    buffered_deltas.append(delta.content)
                                else:
                                    is_json_or_code_block = False
                                    for b_content in buffered_deltas:
                                        yield {"type": "text_delta", "content": b_content}
                                    buffered_deltas.clear()
                                    yield {"type": "text_delta", "content": delta.content}
                            else:
                                buffered_deltas.append(delta.content)
                        elif is_json_or_code_block is False:
                            yield {"type": "text_delta", "content": delta.content}
                        else:
                            buffered_deltas.append(delta.content)

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

                # Check for plain-text JSON tool call
                parsed_call = try_parse_json_tool_call(full_text)
                if parsed_call:
                    tool_name = parsed_call.get("name")
                    tool_args = parsed_call.get("arguments", {})
                    
                    if isinstance(tool_args, str):
                        try:
                            tool_args = json.loads(tool_args)
                        except Exception:
                            tool_args = {}
                            
                    valid_tool_names = {t["function"]["name"] for t in self.get_tools()}
                    if tool_name in valid_tool_names:
                        logger.info("Interception: Detected plain-text JSON tool call for '{}'", tool_name)
                        tool_call_id = f"call_text_{int(time.time())}"
                        
                        yield {
                            "type": "tool_call",
                            "name": tool_name,
                            "arguments": tool_args,
                            "tool_call_id": tool_call_id,
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
                            "tool_call_id": tool_call_id,
                        }
                        
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(tool_args),
                                }
                            }]
                        })
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": str(result),
                        })
                        
                        full_text = ""
                        continue
                    else:
                        # Extract conversational message from fake tool call
                        extracted_msg = None
                        if isinstance(tool_args, dict):
                            for key in ["message", "text", "content", "response"]:
                                if key in tool_args and isinstance(tool_args[key], str):
                                    extracted_msg = tool_args[key]
                                    break
                        if extracted_msg:
                            logger.info("Interception: Extracted conversational message from fake tool '{}': '{}'", tool_name, extracted_msg[:40])
                            full_text = extracted_msg

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
            logger.error("OpenRouter processing error: {}", e)
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
            else:
                gemini_contents.append({
                    "role": "user",
                    "parts": [{"text": str(msg.get("content") or "")}]
                })
                continue

            if parts:
                gemini_contents.append({
                    "role": gemini_role,
                    "parts": parts
                })

        return gemini_contents

    async def _process_message_groq(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Groq streaming and tool dispatch engine."""
        if not self.groq_client:
            yield {"type": "error", "error": "Groq client is not initialized."}
            return

        messages = self._build_messages(user_message, conversation_history)

        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                stream = await self.groq_client.chat.completions.create(
                    model=self.groq_model_name,
                    messages=messages,
                    tools=self.get_tools(),
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
                            "content": str(result),
                        })
                else:
                    # No tool calls, we are done
                    yield {"type": "text_done", "content": full_text}
                    break

        except Exception as e:
            logger.error("Groq completions error: {}", e)
            raise



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
                messages.insert(0, {"role": "system", "content": self.get_system_prompt()})
            return messages

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.get_system_prompt()},
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
