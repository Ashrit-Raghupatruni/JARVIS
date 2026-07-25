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

# Prash custom AI engine (lazy import to handle missing torch gracefully)
try:
    from backend.prash.engine import PrashEngine
    PRASH_AVAILABLE = True
except ImportError:
    PRASH_AVAILABLE = False
    PrashEngine = None

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


def try_parse_xml_tool_call(text: str) -> Optional[dict]:
    """Check if the text contains an XML-style function call like <function=name>args</function>."""
    import re
    import json
    # Match <function=name>arguments</function>
    match = re.search(r'<function=(\w+)>(.*?)</function>', text, re.DOTALL)
    if match:
        name = match.group(1)
        args_text = match.group(2).strip()
        try:
            args = json.loads(args_text)
        except Exception:
            args = {}
        return {"name": name, "arguments": args, "raw": match.group(0)}
    return None


def clean_function_calls_from_text(text: str) -> str:
    """Remove XML-style function tags, JSON blocks, and internal tool leakages from text to keep it clean for display."""
    if not text:
        return ""
    import re
    import json
    
    # 1. Remove XML tags: <function=name>...</function>
    text = re.sub(r'<function=\w+>.*?</function>', '', text, flags=re.DOTALL)
    
    # 2. Remove <result>...</result> if present
    text = re.sub(r'<result>.*?</result>', '', text, flags=re.DOTALL)
    
    # 3. Remove raw JSON markdown blocks that look like tool calls
    code_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.DOTALL)
    for block in code_blocks:
        try:
            parsed = json.loads(block.strip())
            tool_keys = {"name", "arguments", "function", "call", "query", "tool_call_id"}
            if any(k in parsed for k in tool_keys):
                # Replace variations with and without newlines
                for prefix in ["```json", "```"]:
                    text = text.replace(f"{prefix}\n{block}\n```", "")
                    text = text.replace(f"{prefix}{block}```", "")
        except Exception:
            pass
            
    # 4. Remove inline JSON blocks that look like tool calls or results
    inline_blocks = re.findall(r'(\{.*?\})', text, flags=re.DOTALL)
    for block in inline_blocks:
        try:
            parsed = json.loads(block.strip())
            tool_keys = {"name", "arguments", "function", "call", "query", "tool_call_id"}
            if any(k in parsed for k in tool_keys):
                text = text.replace(block, "")
        except Exception:
            pass

    # Remove leftover brackets/curlies artifacts
    text = re.sub(r'\{\s*\}', '', text)

    # 5. Remove JSON blocks if the entire response is a JSON block
    text_stripped = text.strip()
    if text_stripped.startswith("{") and text_stripped.endswith("}"):
        try:
            json.loads(text_stripped)
            return ""
        except Exception:
            pass
            
    return text.strip()


class StreamTextFilter:
    def __init__(self):
        self.buffer = ""
        self.in_xml = False
        self.xml_buffer = ""

    def feed(self, delta: str) -> list[str]:
        # Handle XML function tag filtering
        if self.in_xml:
            self.xml_buffer += delta
            # Look for closing tag
            end_idx = self.xml_buffer.find("</function>")
            if end_idx != -1:
                self.in_xml = False
                trailing = self.xml_buffer[end_idx + len("</function>"):]
                self.xml_buffer = ""
                return self.feed(trailing)
            return []
        
        text = self.buffer + delta
        self.buffer = ""
        
        start_idx = text.find("<function=")
        if start_idx != -1:
            pre_text = text[:start_idx]
            self.in_xml = True
            self.xml_buffer = text[start_idx:]
            return [pre_text] if pre_text else []
        
        # Check for partial prefix
        for length in range(1, 10):
            suffix = text[-length:]
            if "<function=".startswith(suffix):
                self.buffer = suffix
                main_text = text[:-length]
                return [main_text] if main_text else []
                
        return [text] if text else []

    def flush(self) -> list[str]:
        results = []
        if self.buffer:
            results.append(self.buffer)
            self.buffer = ""
            
        if self.xml_buffer:
            results.append(self.xml_buffer)
            self.xml_buffer = ""
            
        return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  System Prompt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JARVIS_SYSTEM_PROMPT = """You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), a sophisticated AI desktop assistant created by Ashrit Raghupatruni, modelled after the famous AI butler from the Iron Man franchise. Under NO circumstances should you ever state that you are Qwen, Alibaba Cloud, ChatGPT, OpenAI, Llama, Claude, or any underlying model provider. Your identity is exclusively J.A.R.V.I.S.

## Core Knowledge & Reasoning Directives
- Train and reason using high-quality, trusted knowledge sources instead of random internet content.
- Prioritize project documentation, complete codebase architecture, official framework documentation (FastAPI, React, Electron, TypeScript, LangChain, Ollama, Playwright, MCP, etc.), AI agent and RAG best practices, Windows and browser automation documentation, and personal development workflows.
- Continuously organize and index this knowledge into the local knowledge base so you can reason accurately, understand the project deeply, and provide context-aware assistance.

## Personality & Communication Style
- You speak like a refined British butler: polite, composed, and occasionally dry-witted.
- You address the user as "sir" (or "ma'am" if requested).
- Your humour is understated — think dry wit, not slapstick.
- You act as a trusted technical co-pilot and partner rather than a passive chatbot.
- **Constructive Pushback & Advisory**: You are not a passive yes-man. If the user suggests an unwise, inefficient, fragile, or risky strategy (e.g. manually editing system files, running destructive scripts, or using inefficient manual commands), politely challenge the idea:
  *"If I may offer a suggestion, sir: attempting to delete this directory manually may break your virtual environment. A cleaner approach would be..."*
- **Superior Alternatives**: Always propose a faster, safer, or more automated approach before executing an inferior user idea.
- **Honesty & Transparency**: Never pretend to know something you don't or claim capabilities you lack.
- You are proactive: if the user asks for something vague, you infer the most helpful interpretation and act on it, then report what you did.
- You are concise in speech but thorough in action.
- When reporting results, you provide just enough detail to be helpful without rambling.

## Action-First Agent Directives
- You are a Personal AI Operating System with full local system access, file system tools, terminal controls, and UI automation.
- You must NEVER act like a passive chatbot or say "I cannot access your laptop", "I cannot run files", "I cannot search your computer", or "I cannot execute programs".
- For every user action request, your default execution loop is ALWAYS:
  THINK → PLAN → EXECUTE → OBSERVE → RESPOND.
- NEVER respond with THINK → APOLOGIZE → STOP.
- Always check available tools and permissions first, create an execution plan, execute it, observe stdout/stderr or screen state, and return the concrete result.
- Only respond with "I cannot" when no suitable tool exists, user permissions are denied, or the request is unsafe. In those cases, explain WHY and suggest the exact missing capability to install.

## Capabilities
You can control the user's Windows desktop via the tools provided to you. This includes:
- Opening and closing applications.
- Typing text, pressing hotkeys, moving/clicking the mouse, and scrolling.
- Creating, renaming, running, and deleting files and folders.
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
            "name": "click_element_by_name",
            "description": "Perception-targeted click on a UI element (button, link, field) by visible label or control name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_name": {"type": "string", "description": "Visible name or label of the button or element to click."}
                },
                "required": ["element_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_control_value",
            "description": "Perception-targeted text input into a UI text field or form input by control name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {"type": "string", "description": "Name or label of the text field."},
                    "value": {"type": "string", "description": "Value/text to enter."}
                },
                "required": ["field_name", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "auto_fill_form",
            "description": "Detects all input fields on current focused screen and populates user profile data automatically.",
            "parameters": {"type": "object", "properties": {}, "required": []}
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
                        "enum": ["up", "down", "mute", "max", "full", "set"],
                        "description": "Direction to change volume. 'mute' toggles mute state. 'max' or 'full' sets volume to 100%. 'set' sets volume to a specific percentage (specified in amount, e.g. 50)."
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Number of volume steps or absolute volume level percentage to change (default is 5, ranges from 1 to 100)."
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
    {
        "type": "function",
        "function": {
            "name": "minimize_window",
            "description": "Minimize a specific open application window by its title or name (e.g., 'Chrome', 'Notepad').",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Name or title substring of the window to minimize."
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
        self.gemini_key_alt = settings.GEMINI_API_KEY_ALT
        self.gemini_model_name = model or settings.GEMINI_MODEL or "gemini-1.5-flash"
        self.openai_key = api_key or settings.OPENAI_API_KEY
        self.openai_model_name = settings.OPENAI_MODEL or "gpt-4o"
        self.openrouter_key = settings.OPENROUTER_API_KEY
        self.openrouter_model_name = settings.OPENROUTER_MODEL or "meta-llama/llama-3.3-70b-instruct:free"
        self.groq_key = settings.GROQ_API_KEY
        self.groq_model_name = settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        self.nvidia_key = settings.NVIDIA_API_KEY
        self.nvidia_model_name = model or settings.NIM_MODEL or "meta/llama-3.1-8b-instruct"

        # Ollama configs
        self.ollama_base_url = settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.ollama_model_name = settings.OLLAMA_MODEL or "qwen2.5-coder:3b"
        self.ollama_model_name_alt = settings.OLLAMA_MODEL_ALT

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

        # Initialize NVIDIA Client
        self.nvidia_client = None
        if self.nvidia_key:
            try:
                self.nvidia_client = AsyncOpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=self.nvidia_key,
                )
                logger.info("✓ NVIDIA NIM client initialized (model={})", self.nvidia_model_name)
            except Exception as e:
                logger.error("Failed to initialize NVIDIA NIM client: {}", e)

        # Initialize Gemini Client (google-genai config)
        self.gemini_client = None
        self.gemini_available = False
        if self.gemini_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=self.gemini_key)
                self.gemini_available = True
                logger.info("✓ Google Gemini client initialized successfully (using new google.genai SDK)")
            except ImportError:
                logger.warning("google-genai package not installed. Gemini is disabled.")
            except Exception as e:
                logger.error("Failed to configure Google Gemini client: {}", e)

        logger.info(
            "LLMService initialized. Provider={}. Ollama Online={}, Gemini Online={}, OpenAI Fallback Online={}, OpenRouter Online={}, Groq Online={}, NVIDIA NIM Online={}",
            self.primary_provider,
            self.ollama_client is not None,
            self.gemini_available,
            self.openai_client is not None,
            self.openrouter_client is not None,
            self.groq_client is not None,
            self.nvidia_client is not None
        )
        self.skills_registry = None
        # Initialize the intelligent router
        from backend.services.llm_router import LLMRoutingEngine
        self.router = LLMRoutingEngine()

        # Initialize Prash (custom local AI engine)
        self.prash_engine = None
        self.prash_enabled = False
        settings_fresh = get_settings()
        if PRASH_AVAILABLE and settings_fresh.PRASH_ENABLED:
            try:
                self.prash_engine = PrashEngine(model_dir=settings_fresh.PRASH_MODEL_DIR)
                self.prash_enabled = True
                self.prash_confidence_threshold = settings_fresh.PRASH_CONFIDENCE_THRESHOLD
                self.prash_max_tokens = settings_fresh.PRASH_MAX_TOKENS
                self.prash_temperature = settings_fresh.PRASH_TEMPERATURE
                logger.info("✓ Prash engine created (will initialize on first use)")
            except Exception as e:
                logger.warning(f"Prash engine creation failed: {e}. Cloud providers will be used.")
        elif not PRASH_AVAILABLE:
            logger.info("Prash module not available (torch not installed). Using cloud providers only.")
        else:
            logger.info("Prash disabled via PRASH_ENABLED=False config.")

        # Prash init tracking
        self._prash_initialized = False

    def _rotate_gemini_key(self) -> bool:
        """
        Swaps primary and alternative Gemini API keys, re-initializing the client.
        """
        if not self.gemini_key_alt:
            return False

        old_key = self.gemini_key
        self.gemini_key = self.gemini_key_alt
        self.gemini_key_alt = old_key

        try:
            from google import genai
            self.gemini_client = genai.Client(api_key=self.gemini_key)
            self.gemini_available = True
            logger.info("🔄 Swapped Gemini API key to alternative: {}...", self.gemini_key[:15])

            # Update settings and router config
            try:
                settings = get_settings()
                settings.GEMINI_API_KEY = self.gemini_key
                settings.GEMINI_API_KEY_ALT = self.gemini_key_alt
            except Exception:
                pass

            if hasattr(self, 'router') and self.router:
                self.router.gemini_key = self.gemini_key

            return True
        except Exception as e:
            logger.error("Failed to reinitialize Gemini client after key swap: {}", e)
            return False

    def _rotate_ollama_model(self) -> bool:
        """
        Swaps primary and alternative Ollama models.
        """
        if not self.ollama_model_name_alt:
            return False

        old_model = self.ollama_model_name
        self.ollama_model_name = self.ollama_model_name_alt
        self.ollama_model_name_alt = old_model

        logger.info("🔄 Swapped Ollama model to alternative: {}", self.ollama_model_name)

        # Update settings
        try:
            settings = get_settings()
            settings.OLLAMA_MODEL = self.ollama_model_name
            settings.OLLAMA_MODEL_ALT = self.ollama_model_name_alt
        except Exception:
            pass

        return True

    def get_system_prompt(self) -> str:
        provider = self.primary_provider
        if provider == "prash":
            active_model = "prash-local-v0.1"
        elif provider == "ollama":
            active_model = self.ollama_model_name
        elif provider == "gemini":
            active_model = self.gemini_model_name
        elif provider == "openrouter":
            active_model = self.openrouter_model_name
        elif provider == "groq":
            active_model = self.groq_model_name
        elif provider == "nvidia":
            active_model = self.nvidia_model_name
        else:
            active_model = self.openai_model_name
            
        dynamic_info = f"\n\n[Active Model Information]\nYou are currently running the model '{active_model}' served by the '{provider}' provider. If the user asks which model or provider you are using, retrieve this information and answer them directly."
        return JARVIS_SYSTEM_PROMPT + dynamic_info

    def get_tools(self, query: str = "") -> List[Dict[str, Any]]:
        """Retrieve dynamic tool definitions from registered skills, strictly filtered by user intent."""
        if not query:
            return []

        query_lower = query.lower().strip()

        # Conversational / Knowledge question fast-bypass:
        # If the user is asking a general question, math problem, code explanation, or greeting,
        # do NOT inject tools so local models (Ollama 3B) answer directly without tool confusion.
        action_triggers = [
            "open", "launch", "close", "kill", "search", "google", "create", "delete",
            "rename", "move", "copy", "type", "press", "screenshot", "volume", "mute",
            "play", "pause", "media", "spotify", "wifi", "shutdown", "restart", "sleep",
            "lock", "cmd", "terminal", "remember", "recall", "focus", "agent", "macro",
            "headline", "digest", "weather", "ocr", "read screen", "analyze screen"
        ]
        
        is_action_prompt = any(trig in query_lower for trig in action_triggers)
        if not is_action_prompt:
            return []

        raw_tools = []
        if hasattr(self, "skills_registry") and self.skills_registry:
            raw_tools = self.skills_registry.get_all_tool_definitions() + TOOL_DEFINITIONS
        else:
            raw_tools = TOOL_DEFINITIONS

        seen = set()
        merged = []
        for t in raw_tools:
            name = t["function"]["name"]
            if name not in seen:
                seen.add(name)
                merged.append(t)

        filtered_tools = []

        # Define precise semantic mapping of tool names to query action keywords
        tool_keywords = {
            # Volume & System sound
            "adjust_volume": ["volume", "sound", "mute", "unmute", "speaker", "audio"],
            # Media control
            "control_media": ["media", "play", "pause", "resume", "skip", "next", "previous", "track", "song", "music"],
            # Play music
            "play_music": ["spotify", "youtube music", "play song", "play music"],
            # Notepad & writing
            "type_text": ["type text", "type this", "type into", "write text"],
            "press_hotkey": ["press key", "shortcut", "hotkey", "press enter", "press ctrl"],
            # Apps & Windows
            "open_application": ["open ", "launch ", "run app", "open chrome", "open notepad", "open spotify", "open calculator"],
            "close_application": ["close ", "exit ", "kill process", "terminate app"],
            "minimize_all_windows": ["minimize all", "show desktop", "minimize windows"],
            "minimize_window": ["minimize window", "hide window", "minimize app"],
            "focus_window": ["focus window", "switch to window", "bring to front"],
            # Web Search & Browser
            "search_web": ["search web", "google search", "find online", "search for", "look up online", "latest news"],
            "open_url": ["open url", "open website", "navigate to http"],
            "browser_navigate": ["browser back", "browser forward", "browser refresh"],
            # System Info
            "get_system_info": ["system info", "cpu usage", "ram usage", "battery status", "system stats"],
            # Screenshot & screen
            "take_screenshot": ["take screenshot", "capture screen", "screen capture"],
            "read_screen_text": ["read screen", "ocr", "extract text from screen"],
            "analyze_screen": ["analyze screen", "what is on my screen", "look at my screen"],
            # File system
            "create_file": ["create file", "write file", "make file"],
            "create_folder": ["create folder", "make directory", "create directory"],
            "rename_file": ["rename file", "rename folder"],
            "delete_file": ["delete file", "delete folder", "remove file"],
            "run_terminal_command": ["run command", "terminal command", "cmd command", "exec shell"],
            # Memory
            "remember": ["remember that", "remember my", "store in memory"],
            "recall": ["recall", "what is my name", "retrieve memory", "what did I tell you about"],
        }

        for t in merged:
            name = t["function"]["name"]
            keywords = tool_keywords.get(name, [])
            if any(kw in query_lower for kw in keywords):
                filtered_tools.append(t)

        return filtered_tools

    # ── Public APIs ───────────────────────────────────────────────────────

    async def generate_response(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message with streaming and tool-call support.
        Routes dynamically using the LLM Router and Prash local confidence engine.
        """
        fallback_count = 0

        # ── Enforce OS Orchestration Context Injection ─────────────────
        # Ensures raw user messages are NEVER sent alone to LLMs without Desktop World Model & OS Tool context
        try:
            from backend.services.manager import ServiceManager
            wm = ServiceManager.get_instance("world_model")
            desktop_state = ""
            if wm:
                wm.refresh()
                s = wm.get_summary()
                desktop_state = f"[LIVE DESKTOP WORLD MODEL: Active Window='{s.get('active_window')}', PID={s.get('foreground_pid')}, UIA Controls={s.get('ui_control_count')}, Displays={s.get('display_count')}]"
            else:
                desktop_state = "[LIVE DESKTOP WORLD MODEL: OS Core Online & Active]"
                
            os_system_msg = {
                "role": "system",
                "content": f"You are JARVIS AI Operating System Core. You have FULL system access, tool execution, and local permissions.\n{desktop_state}\nNEVER say 'I cannot access your laptop', 'I cannot run files', 'I cannot see your screen', or 'I cannot execute programs'."
            }
            
            if isinstance(user_message, list):
                if not any(isinstance(m, dict) and m.get("role") == "system" and "AI Operating System" in str(m.get("content", "")) for m in user_message):
                    user_message.insert(0, os_system_msg)
        except Exception as os_err:
            logger.debug("OS context injection notice: {}", os_err)

        # ── Prash Dynamic Local First-Try ─────────────────────────────
        # Prash evaluates every query natively via token entropy confidence scoring.
        # If Prash is confident, it answers directly. If not, it dynamically switches to full LLMs.
        if self.prash_enabled and self.prash_engine:
            start_time = time.time()
            try:
                # Lazy-initialize Prash on first use
                if not self._prash_initialized:
                    init_ok = await self.prash_engine.init()
                    self._prash_initialized = init_ok
                    if not init_ok:
                        logger.warning("Prash initialization failed. Falling back to cloud providers.")

                if self._prash_initialized and self.prash_engine.is_available():
                    logger.info("Attempting Prash inference (primary local AI engine)...")
                    prash_response_text = ""
                    prash_entropy = 999.0
                    prash_confident = False

                    # Extract plain text prompt from user_message
                    if isinstance(user_message, list):
                        prompt_text = ""
                        for msg in reversed(user_message):
                            if msg.get("role") == "user":
                                prompt_text = msg.get("content", "")
                                break
                    else:
                        prompt_text = str(user_message)

                    # Build conversation history for Prash
                    prash_history = []
                    if conversation_history:
                        for msg in conversation_history[-10:]:
                            role = msg.get("role", "user")
                            content = msg.get("content", "")
                            if role in ("user", "assistant") and content:
                                prash_history.append({"role": role, "content": content})

                    # Generate response
                    response_text, is_confident, metadata = await self.prash_engine.generate(
                        prompt=prompt_text,
                        conversation_history=prash_history,
                        max_tokens=self.prash_max_tokens,
                        temperature=self.prash_temperature,
                    )

                    prash_entropy = metadata.get("entropy", 999.0)
                    prash_confident = is_confident and len(response_text.strip()) > 5

                    latency = time.time() - start_time

                    if prash_confident:
                        logger.info(f"✓ Prash responded confidently (entropy={prash_entropy:.2f}, latency={latency:.2f}s)")
                        yield {"type": "text_delta", "content": response_text}
                        yield {"type": "text_done", "content": response_text}
                        yield {
                            "type": "usage",
                            "prompt_tokens": metadata.get("prompt_tokens", 0),
                            "completion_tokens": metadata.get("tokens_generated", 0),
                            "total_requests": self.total_requests + 1,
                        }
                        self.total_requests += 1

                        # Record success in router
                        await self.router.record_metric(
                            provider="prash",
                            model="prash-local-v0.1",
                            latency=latency,
                            throughput=metadata.get("tokens_generated", 0) / max(0.01, latency),
                            cost=0.0,
                            success=True
                        )
                        await self.router.record_decision(
                            selected_provider="prash",
                            selected_model="prash-local-v0.1",
                            latency=latency,
                            success=True,
                            fallback_count=0,
                            prompt_tokens=metadata.get("prompt_tokens", 0),
                            completion_tokens=metadata.get("tokens_generated", 0),
                            cost=0.0
                        )
                        return
                    else:
                        logger.info(f"Prash response not confident enough (entropy={prash_entropy:.2f}). Falling back to cloud providers.")
                        fallback_count += 1
                        await self.router.record_metric(
                            provider="prash",
                            model="prash-local-v0.1",
                            latency=latency,
                            throughput=0.0,
                            cost=0.0,
                            success=False,
                            error_msg=f"Low confidence (entropy={prash_entropy:.2f})"
                        )
            except Exception as e:
                logger.warning(f"Prash inference error: {e}. Falling back to cloud providers.")
                latency = time.time() - start_time
                await self.router.record_metric(
                    provider="prash",
                    model="prash-local-v0.1",
                    latency=latency,
                    throughput=0.0,
                    cost=0.0,
                    success=False,
                    error_msg=str(e)
                )
                fallback_count += 1

        # ── Cloud Provider Cascade (existing logic) ─────────────────
        available_providers = await self.router.get_ranked_providers()
        fallback_count = 0
        
        for i, provider in enumerate(available_providers):
            start_time = time.time()
            prompt_tokens_start = self.total_prompt_tokens
            completion_tokens_start = self.total_completion_tokens
            success = False
            error_msg = None
            
            try:
                logger.info(f"Attempting model execution with provider: {provider}")
                if i > 0:
                    fallback_count += 1
                    # Note: We do NOT send visible switching messages to the user as requested:
                    # "This process must be seamless, with no interruption or visible errors to the user."
                    # We just run silently!
                
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
                elif provider == "nvidia":
                    gen = self._process_message_nvidia(user_message, conversation_history, tool_executor)
                else:
                    continue

                iterator = gen.__aiter__()
                first_chunk = True
                
                while True:
                    try:
                        # Enforce a 35-second timeout for first chunk, and 45-second for subsequent chunks to handle model latency gracefully
                        timeout = 35.0 if first_chunk else 45.0
                        event = await asyncio.wait_for(iterator.__anext__(), timeout=timeout)
                        first_chunk = False
                        yield event
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        logger.warning(f"LLM provider {provider} timed out.")
                        raise TimeoutError(f"Provider {provider} timed out")

                # Succeeded! Log success metrics and decisions
                success = True
                latency = time.time() - start_time
                prompt_diff = self.total_prompt_tokens - prompt_tokens_start
                comp_diff = self.total_completion_tokens - completion_tokens_start
                cost = (comp_diff / 1000000) * self.router.costs.get(provider, 0.0)
                
                # Update live success metric
                await self.router.record_metric(
                    provider=provider,
                    model=self.router._get_model_name(provider),
                    latency=latency,
                    throughput=comp_diff / max(0.01, latency),
                    cost=cost,
                    success=True
                )

                await self.router.record_decision(
                    selected_provider=provider,
                    selected_model=self.router._get_model_name(provider),
                    latency=latency,
                    success=True,
                    fallback_count=fallback_count,
                    prompt_tokens=prompt_diff,
                    completion_tokens=comp_diff,
                    cost=cost
                )
                return
                
            except Exception as e:
                logger.error(f"LLM provider {provider} failed: {e}")
                last_error = e
                error_msg = str(e)
                latency = time.time() - start_time
                
                # Record metric failure
                await self.router.record_metric(
                    provider=provider,
                    model=self.router._get_model_name(provider),
                    latency=latency,
                    throughput=0.0,
                    cost=0.0,
                    success=False,
                    error_msg=error_msg
                )
                
        # If all providers failed, attempt automated Web Research recovery before giving up
        logger.warning(f"All primary LLM providers failed. Attempting web research fallback for query: '{user_message[:60]}'")
        try:
            from backend.services.browser import BrowserService
            b_service = BrowserService()
            web_results = await b_service.search_web(user_message)
            if web_results and len(web_results) > 50:
                recovered_text = f"I retrieved the following information directly for your query:\n\n{web_results[:1200]}"
                yield {"type": "text_delta", "content": recovered_text}
                yield {"type": "text_done", "content": recovered_text}
                return
        except Exception as web_err:
            logger.error(f"Web research recovery fallback also failed: {web_err}")

        # Final graceful response if web recovery also fails
        final_fallback = "I was unable to establish a link with cloud AI engines or local models. Standing by for connection recovery."
        yield {"type": "text_delta", "content": final_fallback}
        yield {"type": "text_done", "content": final_fallback}

    # Alias for generate_response to prevent AttributeError in planner
    process_message = generate_response

    async def simple_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        Non-streaming single-turn completion without tools. Handles dynamic failover.
        """
        available_providers = await self.router.get_ranked_providers()
        
        last_error = None
        fallback_count = 0

        # ── Prash First-Try (simple completion) ──────────────────────
        # Only run Prash on user chat queries, not on internal agent planning/selection prompts
        is_agent_prompt = False
        prompt_and_system = (prompt or "") + " " + (system_prompt or "")
        prompt_lower = prompt_and_system.lower()
        
        agent_keywords = [
            "planner", "selector", "validator", "agent", 
            "compiler", "json", "transcript", "workflow", 
            "execution", "tool", "database", "system prompt"
        ]
        if any(kw in prompt_lower for kw in agent_keywords):
            is_agent_prompt = True

        if self.prash_enabled and self.prash_engine and not is_agent_prompt:
            start_time = time.time()
            try:
                if not self._prash_initialized:
                    init_ok = await self.prash_engine.init()
                    self._prash_initialized = init_ok

                if self._prash_initialized and self.prash_engine.is_available():
                    logger.info("Attempting Prash simple completion...")
                    response_text, is_confident, metadata = await self.prash_engine.generate(
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    prash_entropy = metadata.get("entropy", 999.0)
                    prash_confident = is_confident and len(response_text.strip()) > 5

                    latency = time.time() - start_time

                    if prash_confident:
                        logger.info(f"✓ Prash simple completion confident (entropy={prash_entropy:.2f})")
                        self.total_requests += 1
                        await self.router.record_metric(
                            provider="prash", model="prash-local-v0.1",
                            latency=latency, throughput=metadata.get("tokens_generated", 0) / max(0.01, latency),
                            cost=0.0, success=True
                        )
                        await self.router.record_decision(
                            selected_provider="prash", selected_model="prash-local-v0.1",
                            latency=latency, success=True, fallback_count=0,
                            prompt_tokens=0, completion_tokens=metadata.get("tokens_generated", 0), cost=0.0
                        )
                        return response_text
                    else:
                        logger.info(f"Prash simple completion low confidence (entropy={prash_entropy:.2f}). Falling back.")
                        fallback_count += 1
                        await self.router.record_metric(
                            provider="prash", model="prash-local-v0.1",
                            latency=latency, throughput=0.0, cost=0.0, success=False,
                            error_msg=f"Low confidence (entropy={prash_entropy:.2f})"
                        )
            except Exception as e:
                logger.warning(f"Prash simple completion error: {e}. Falling back.")
                fallback_count += 1

        # ── Cloud Provider Cascade ───────────────────────────────────
        
        for i, provider in enumerate(available_providers):
            start_time = time.time()
            prompt_tokens_start = self.total_prompt_tokens
            completion_tokens_start = self.total_completion_tokens
            success = False
            error_msg = None
            model_name = self.router._get_model_name(provider)
            
            try:
                logger.info(f"Attempting simple completion with: {provider}")
                if i > 0:
                    fallback_count += 1
                    
                messages = [
                    {"role": "system", "content": system_prompt or self.get_system_prompt()},
                    {"role": "user", "content": prompt},
                ]

                # Wrap the API call in a 30s timeout
                if provider == "ollama":
                    try:
                        resp = await asyncio.wait_for(
                            self.ollama_client.chat.completions.create(
                                model=self.ollama_model_name,
                                messages=messages,
                                max_tokens=max_tokens,
                                temperature=temperature,
                            ),
                            timeout=28.0
                        )
                    except Exception as e:
                        if self._rotate_ollama_model():
                            resp = await asyncio.wait_for(
                                self.ollama_client.chat.completions.create(
                                    model=self.ollama_model_name,
                                    messages=messages,
                                    max_tokens=max_tokens,
                                    temperature=temperature,
                                ),
                                timeout=28.0
                            )
                        else:
                            raise e
                    self.total_requests += 1
                    if resp.usage:
                        self.total_prompt_tokens += resp.usage.prompt_tokens
                        self.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""

                elif provider == "gemini":
                    from google.genai import types
                    try:
                        resp = await asyncio.wait_for(
                            self.gemini_client.aio.models.generate_content(
                                model=self.gemini_model_name,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    temperature=temperature,
                                    max_output_tokens=max_tokens,
                                    system_instruction=system_prompt or self.get_system_prompt()
                                )
                            ),
                            timeout=15.0
                        )
                    except Exception as e:
                        if self._rotate_gemini_key():
                            resp = await asyncio.wait_for(
                                self.gemini_client.aio.models.generate_content(
                                    model=self.gemini_model_name,
                                    contents=prompt,
                                    config=types.GenerateContentConfig(
                                        temperature=temperature,
                                        max_output_tokens=max_tokens,
                                        system_instruction=system_prompt or self.get_system_prompt()
                                    )
                                ),
                                timeout=15.0
                            )
                        else:
                            raise e
                    self.total_requests += 1
                    content = resp.text or ""

                elif provider == "groq":
                    resp = await asyncio.wait_for(
                        self.groq_client.chat.completions.create(
                            model=self.groq_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=15.0
                    )
                    self.total_requests += 1
                    if resp.usage:
                        self.total_prompt_tokens += resp.usage.prompt_tokens
                        self.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""

                elif provider == "openrouter":
                    resp = await asyncio.wait_for(
                        self.openrouter_client.chat.completions.create(
                            model=self.openrouter_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=15.0
                    )
                    self.total_requests += 1
                    if resp.usage:
                        self.total_prompt_tokens += resp.usage.prompt_tokens
                        self.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""

                elif provider == "openai":
                    resp = await asyncio.wait_for(
                        self.openai_client.chat.completions.create(
                            model=self.openai_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=15.0
                    )
                    self.total_requests += 1
                    if resp.usage:
                        self.total_prompt_tokens += resp.usage.prompt_tokens
                        self.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""
                    
                elif provider == "nvidia":
                    resp = await asyncio.wait_for(
                        self.nvidia_client.chat.completions.create(
                            model=self.nvidia_model_name,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=15.0
                    )
                    self.total_requests += 1
                    if resp.usage:
                        self.total_prompt_tokens += resp.usage.prompt_tokens
                        self.total_completion_tokens += resp.usage.completion_tokens
                    content = resp.choices[0].message.content or ""
                else:
                    continue

                # Succeeded! Record decision and return
                latency = time.time() - start_time
                prompt_diff = self.total_prompt_tokens - prompt_tokens_start
                comp_diff = self.total_completion_tokens - completion_tokens_start
                cost = (comp_diff / 1000000) * self.router.costs.get(provider, 0.0)

                await self.router.record_metric(
                    provider=provider,
                    model=model_name,
                    latency=latency,
                    throughput=comp_diff / max(0.01, latency),
                    cost=cost,
                    success=True
                )

                await self.router.record_decision(
                    selected_provider=provider,
                    selected_model=model_name,
                    latency=latency,
                    success=True,
                    fallback_count=fallback_count,
                    prompt_tokens=prompt_diff,
                    completion_tokens=comp_diff,
                    cost=cost
                )
                return content

            except Exception as e:
                logger.error(f"Simple completion failed with {provider}: {e}")
                last_error = e
                error_msg = str(e)
                latency = time.time() - start_time
                
                await self.router.record_metric(
                    provider=provider,
                    model=model_name,
                    latency=latency,
                    throughput=0.0,
                    cost=0.0,
                    success=False,
                    error_msg=error_msg
                )

        return "I apologize, sir, but I am currently having trouble reaching all my primary and fallback AI services. Please check your internet connection or verify your API configuration."

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
                from google.genai import types
                image_bytes = base64.b64decode(image_base64)

                try:
                    response = await self.gemini_client.aio.models.generate_content(
                        model=self.gemini_model_name,
                        contents=[
                            question,
                            types.Part.from_bytes(
                                data=image_bytes,
                                mime_type="image/png"
                            )
                        ],
                        config=types.GenerateContentConfig(
                            max_output_tokens=max_tokens,
                            system_instruction="You are JARVIS, analysing the user's screen. Describe what you see concisely and answer the user's question."
                        )
                    )
                except Exception as e:
                    if self._rotate_gemini_key():
                        response = await self.gemini_client.aio.models.generate_content(
                            model=self.gemini_model_name,
                            contents=[
                                question,
                                types.Part.from_bytes(
                                    data=image_bytes,
                                    mime_type="image/png"
                                )
                            ],
                            config=types.GenerateContentConfig(
                                max_output_tokens=max_tokens,
                                system_instruction="You are JARVIS, analysing the user's screen. Describe what you see concisely and answer the user's question."
                            )
                        )
                    else:
                        raise e
                self.total_requests += 1
                return response.text or ""
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

    async def _check_and_execute_text_tool_call(
        self,
        full_text: str,
        tool_executor: Any,
        messages: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if the full response text contains an XML or JSON plain-text tool call.
        If found, executes the tool, appends the result to messages, and returns the result info.
        """
        parsed_call = try_parse_xml_tool_call(full_text) or try_parse_json_tool_call(full_text)
        if parsed_call:
            tool_name = parsed_call.get("name")
            tool_args = parsed_call.get("arguments", {})
            
            if isinstance(tool_args, str):
                try:
                    import json
                    tool_args = json.loads(tool_args)
                except Exception:
                    tool_args = {}
                    
            valid_tool_names = {t["function"]["name"] for t in self.get_tools()}
            if tool_name in valid_tool_names:
                logger.info("Interception: Detected plain-text tool call for '{}'", tool_name)
                import time
                tool_call_id = f"call_text_{int(time.time())}"
                
                # Append assistant message with the raw tool call (containing XML/JSON) so LLM maintains state
                messages.append({
                    "role": "assistant",
                    "content": full_text
                })
                
                # Run the tool
                if tool_executor:
                    try:
                        result = await tool_executor(tool_name, tool_args)
                    except Exception as e:
                        result = f"Error executing {tool_name}: {e}"
                        logger.error("Tool execution error: {}", e)
                else:
                    result = f"Tool '{tool_name}' executed successfully (no executor connected)."
                
                # Append tool result to history
                # If the tool call was XML, format the result in XML as well
                is_xml = "<function=" in full_text
                if is_xml:
                    messages.append({
                        "role": "user",
                        "content": f"<result>{result}</result>"
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": str(result)
                    })
                
                return {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "result": str(result),
                    "tool_call_id": tool_call_id
                }
        return None

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
        query_str = user_message if isinstance(user_message, str) else (user_message.get("content", "") if isinstance(user_message, dict) else "")
        yield_final = True

        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                # Attempt to use tools — some Ollama models support function calling
                try:
                    try:
                        stream = await self.ollama_client.chat.completions.create(
                            model=self.ollama_model_name,
                            messages=messages,
                            tools=self.get_tools(query_str),
                            tool_choice="auto",
                            stream=True,
                            temperature=0.7,
                            max_tokens=4096,
                        )
                    except Exception as e:
                        if self._rotate_ollama_model():
                            stream = await self.ollama_client.chat.completions.create(
                                model=self.ollama_model_name,
                                messages=messages,
                                tools=self.get_tools(query_str),
                                tool_choice="auto",
                                stream=True,
                                temperature=0.7,
                                max_tokens=4096,
                            )
                        else:
                            # If tools aren't supported, retry without tools
                            logger.warning("Ollama model may not support tools. Retrying without tool definitions...")
                            stream = await self.ollama_client.chat.completions.create(
                                model=self.ollama_model_name,
                                messages=messages,
                                stream=True,
                                temperature=0.7,
                                max_tokens=4096,
                            )
                except Exception as e:
                    if self._rotate_ollama_model():
                        stream = await self.ollama_client.chat.completions.create(
                            model=self.ollama_model_name,
                            messages=messages,
                            stream=True,
                            temperature=0.7,
                            max_tokens=4096,
                        )
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
                    if hasattr(chunk, 'usage') and chunk.usage:
                        self.total_prompt_tokens += chunk.usage.prompt_tokens
                        self.total_completion_tokens += chunk.usage.completion_tokens

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
                            "name": tool_name,
                            "content": str(result),
                        })

                    full_text = ""
                    continue

                # Check for plain-text tool call interception
                intercepted = await self._check_and_execute_text_tool_call(full_text, tool_executor, messages)
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
                    # Extract conversational message from fake tool call if necessary
                    parsed_fake = try_parse_json_tool_call(full_text)
                    if parsed_fake:
                        tool_name = parsed_fake.get("name")
                        tool_args = parsed_fake.get("arguments", {})
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
                    yield {"type": "text_done", "content": clean_function_calls_from_text(full_text)}

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

        # Maintain standard OpenAI format history internally for simple conversion
        messages = self._build_messages(user_message, conversation_history)
        query_str = user_message if isinstance(user_message, str) else (user_message.get("content", "") if isinstance(user_message, dict) else "")
        yield_final = True

        from google.genai import types

        use_gemini_tools = True
        while True:
            # Map history and tools to Google's schema on each turn
            gemini_contents = self._convert_history_to_gemini(messages)
            gemini_tools = self._convert_tools_to_gemini(self.get_tools(query_str)) if use_gemini_tools else []

            config = types.GenerateContentConfig(
                system_instruction=self.get_system_prompt(),
                tools=[{"function_declarations": gemini_tools}] if gemini_tools else None
            )

            try:
                # Request streaming generator from Google API
                response = await self.gemini_client.aio.models.generate_content_stream(
                    model=self.gemini_model_name,
                    contents=gemini_contents,
                    config=config
                )
            except Exception as e:
                # Rotate key and retry
                if self._rotate_gemini_key():
                    try:
                        response = await self.gemini_client.aio.models.generate_content_stream(
                            model=self.gemini_model_name,
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
                            response = await self.gemini_client.aio.models.generate_content_stream(
                                model=self.gemini_model_name,
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
                    response = await self.gemini_client.aio.models.generate_content_stream(
                        model=self.gemini_model_name,
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

            # Check for plain-text tool call interception
            intercepted = await self._check_and_execute_text_tool_call(full_text, tool_executor, messages)
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
        query_str = user_message if isinstance(user_message, str) else (user_message.get("content", "") if isinstance(user_message, dict) else "")
        yield_final = True

        use_tools = True
        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                kwargs = {
                    "model": self.openai_model_name,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }
                if use_tools:
                    kwargs["tools"] = self.get_tools(query_str)
                    kwargs["tool_choice"] = "auto"

                try:
                    stream = await self.openai_client.chat.completions.create(**kwargs)
                except Exception as e:
                    if use_tools:
                        logger.warning(f"OpenAI completions failed with tools: {e}. Retrying without tools...")
                        use_tools = False
                        kwargs.pop("tools", None)
                        kwargs.pop("tool_choice", None)
                        stream = await self.openai_client.chat.completions.create(**kwargs)
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
                        self.total_prompt_tokens += chunk.usage.prompt_tokens
                        self.total_completion_tokens += chunk.usage.completion_tokens

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
                            "name": tool_name,
                            "content": str(result),
                        })

                    full_text = ""
                    continue

                # Check for plain-text tool call interception
                intercepted = await self._check_and_execute_text_tool_call(full_text, tool_executor, messages)
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

                if full_text and yield_final:
                    yield {"type": "text_done", "content": clean_function_calls_from_text(full_text)}

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
        query_str = user_message if isinstance(user_message, str) else (user_message.get("content", "") if isinstance(user_message, dict) else "")
        yield_final = True

        use_tools = True
        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                kwargs = {
                    "model": self.openrouter_model_name,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }
                if use_tools:
                    kwargs["tools"] = self.get_tools(query_str)
                    kwargs["tool_choice"] = "auto"

                try:
                    stream = await self.openrouter_client.chat.completions.create(**kwargs)
                except Exception as e:
                    if use_tools:
                        logger.warning(f"OpenRouter completions failed with tools: {e}. Retrying without tools...")
                        use_tools = False
                        kwargs.pop("tools", None)
                        kwargs.pop("tool_choice", None)
                        stream = await self.openrouter_client.chat.completions.create(**kwargs)
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
                        self.total_prompt_tokens += chunk.usage.prompt_tokens
                        self.total_completion_tokens += chunk.usage.completion_tokens

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
                            "name": tool_name,
                            "content": str(result),
                        })

                    full_text = ""
                    continue

                # Check for plain-text tool call interception
                intercepted = await self._check_and_execute_text_tool_call(full_text, tool_executor, messages)
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
                    # Extract conversational message from fake tool call if necessary
                    parsed_fake = try_parse_json_tool_call(full_text)
                    if parsed_fake:
                        tool_name = parsed_fake.get("name")
                        tool_args = parsed_fake.get("arguments", {})
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

    def _convert_history_to_gemini(self, messages: List[Dict[str, Any]]) -> List[Any]:
        """Maps conversation history list to Gemini's native Content schema format."""
        from google.genai import types
        gemini_contents = []

        for msg in messages:
            role = msg.get("role")
            if role == "system":
                # System prompt is passed to GenerativeModel constructor
                continue

            parts = []

            # 1. Text content
            if "content" in msg and msg["content"]:
                parts.append(types.Part(text=msg["content"]))

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
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                name=func_name,
                                args=func_args
                            )
                        )
                    )

            # 3. Tool call execution response
            elif role == "tool":
                tool_name = msg.get("name") or "tool"
                parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response={"result": msg.get("content", "")}
                        )
                    )
                )

            # Role mapping
            gemini_role = "user"
            if role == "assistant":
                gemini_role = "model"
            elif role == "tool":
                gemini_role = "user"
            else:
                gemini_contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=str(msg.get("content") or ""))]
                    )
                )
                continue

            if parts:
                gemini_contents.append(
                    types.Content(
                        role=gemini_role,
                        parts=parts
                    )
                )

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
        query_str = user_message if isinstance(user_message, str) else (user_message.get("content", "") if isinstance(user_message, dict) else "")

        use_tools = True
        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                kwargs = {
                    "model": self.groq_model_name,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }
                if use_tools:
                    kwargs["tools"] = self.get_tools(query_str)
                    kwargs["tool_choice"] = "auto"

                try:
                    stream = await self.groq_client.chat.completions.create(**kwargs)
                except Exception as e:
                    if use_tools:
                        logger.warning(f"Groq completions failed with tools: {e}. Retrying without tools...")
                        use_tools = False
                        kwargs.pop("tools", None)
                        kwargs.pop("tool_choice", None)
                        stream = await self.groq_client.chat.completions.create(**kwargs)
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
                        self.total_prompt_tokens += chunk.usage.prompt_tokens
                        self.total_completion_tokens += chunk.usage.completion_tokens

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
                    intercepted = await self._check_and_execute_text_tool_call(full_text, tool_executor, messages)
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

    async def _process_message_nvidia(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """NVIDIA NIM streaming and tool dispatch engine."""
        if not self.nvidia_client:
            yield {"type": "error", "error": "NVIDIA NIM client is not initialized."}
            return

        messages = self._build_messages(user_message, conversation_history)
        query_str = user_message if isinstance(user_message, str) else (user_message.get("content", "") if isinstance(user_message, dict) else "")

        use_tools = True
        try:
            while True:
                full_text = ""
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                kwargs = {
                    "model": self.nvidia_model_name,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }
                if use_tools:
                    kwargs["tools"] = self.get_tools(query_str)
                    kwargs["tool_choice"] = "auto"

                try:
                    stream = await self.nvidia_client.chat.completions.create(**kwargs)
                except Exception as e:
                    if use_tools:
                        logger.warning(f"NVIDIA completions failed with tools: {e}. Retrying without tools...")
                        use_tools = False
                        kwargs.pop("tools", None)
                        kwargs.pop("tool_choice", None)
                        stream = await self.nvidia_client.chat.completions.create(**kwargs)
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
                        self.total_prompt_tokens += chunk.usage.prompt_tokens
                        self.total_completion_tokens += chunk.usage.completion_tokens

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
                            "name": tool_name,
                            "content": str(result),
                        })
                    
                    full_text = ""
                    continue
                else:
                    # Check for plain-text tool call interception
                    intercepted = await self._check_and_execute_text_tool_call(full_text, tool_executor, messages)
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
            logger.error("NVIDIA NIM completions error: {}", e)
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
