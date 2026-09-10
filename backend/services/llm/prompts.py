"""System prompts, tool definitions, and sanitizers."""
from typing import Any, Dict, List
import re

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


def extract_clean_user_request(messages_or_query: Any) -> str:
    """
    Extracts ONLY the actual raw user request text from whatever object is passed
    (string, list of dicts, or other data structure).
    Guarantees that system prompts, memory context, router metadata,
    tool definitions, and internal instructions are NEVER leaked into search queries or fallbacks.
    """
    if not messages_or_query:
        return ""
        
    raw_text = ""
    if isinstance(messages_or_query, str):
        raw_text = messages_or_query
    elif isinstance(messages_or_query, list):
        # Look backwards for the most recent message with role == 'user'
        for msg in reversed(messages_or_query):
            if isinstance(msg, dict) and msg.get("role") == "user":
                raw_text = str(msg.get("content") or "")
                break
        if not raw_text and messages_or_query:
            # If no user role was explicitly found, look for any dict with content
            for msg in reversed(messages_or_query):
                if isinstance(msg, dict) and msg.get("content"):
                    raw_text = str(msg.get("content"))
                    break
    elif isinstance(messages_or_query, dict):
        raw_text = str(messages_or_query.get("content") or messages_or_query.get("text") or "")
    else:
        raw_text = str(messages_or_query)

    # Clean out any internal prefixes or prompt injections
    internal_prefixes = [
        r"^\[ROUTER INTENT CONTEXT\].*?\.\s*",
        r"^\[LIVE MODE PERCEPTION CONTEXT\].*?\.\s*",
        r"^\[LIVE DESKTOP WORLD MODEL\].*?\.\s*",
        r"^Relevant context from memory:\s*",
        r"^\[SYSTEM\].*?\s*",
        r"^System:\s*",
    ]
    import re
    cleaned = raw_text.strip()
    for pattern in internal_prefixes:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()

    # Never allow stringified message arrays to leak through
    if cleaned.startswith("[{") or cleaned.startswith("({'") or "role': 'system" in cleaned or 'role": "system' in cleaned:
        user_match = re.findall(r"['\"]role['\"]\s*:\s*['\"]user['\"]\s*,\s*['\"]content['\"]\s*:\s*['\"]([^'\"]+)['\"]", cleaned)
        if user_match:
            cleaned = user_match[-1].strip()
        else:
            cleaned = ""

    return cleaned

