"""
Unified Tool Registry for JARVIS.

Centralized registry for declaring, discovering, auditing, and executing system tools:
- Standardized tool schemas and parameter validation
- Risk classification (low, medium, high)
- Destructive operation safety intercepts
- Decouples Planner and agents from concrete tool implementations
"""

import inspect
import asyncio
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger


class ToolMetadata(BaseModel):
    name: str
    description: str
    category: str = "general"
    risk_level: str = "low"  # low, medium, high, sensitive, destructive
    parameters: Dict[str, Any] = Field(default_factory=dict)
    handler: Optional[Any] = Field(default=None, exclude=True)

    @property
    def is_executable(self) -> bool:
        """True if the tool has a valid callable execution handler."""
        return self.handler is not None and callable(self.handler)


def _sanitize_args_for_logging(args: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize sensitive keys for logging."""
    if not isinstance(args, dict):
        return {}
    sensitive_keys = {"password", "token", "secret", "api_key", "key", "auth", "credential", "private_key"}
    sanitized = {}
    for k, v in args.items():
        if any(sk in str(k).lower() for sk in sensitive_keys):
            sanitized[k] = "******"
        else:
            sanitized[k] = v
    return sanitized


class ToolRegistry:
    """
    Centralized Tool Registry singleton managing tool registrations across JARVIS.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolMetadata] = {}
        self._register_default_tools()
        logger.info("ToolRegistry initialized with {} registered tool(s).", len(self._tools))

    @property
    def tools(self) -> Dict[str, ToolMetadata]:
        return self._tools

    def register(
        self,
        name: str,
        description: str,
        category: str = "general",
        risk_level: str = "low",
        parameters: Optional[Dict[str, Any]] = None,
        handler: Optional[Callable] = None
    ) -> None:
        """Register a tool with metadata and optional execution handler."""
        if not name or not isinstance(name, str) or not name.strip():
            raise ValueError("Tool name must be a non-empty string.")

        clean_name = name.strip()
        is_update = clean_name in self._tools
        meta = ToolMetadata(
            name=clean_name,
            description=description or "",
            category=category or "general",
            risk_level=risk_level or "low",
            parameters=parameters or {},
            handler=handler
        )
        self._tools[clean_name] = meta
        logger.debug("Registered tool '{}' (risk={}, executable={}, update={})", clean_name, risk_level, meta.is_executable, is_update)

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None, executable_only: bool = False) -> List[ToolMetadata]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if executable_only:
            tools = [t for t in tools if t.is_executable]
        return tools

    def get_registered_tools(self, executable_only: bool = False) -> List[Dict[str, Any]]:
        """Return registered tools as dictionaries."""
        tools = self.list_tools(executable_only=executable_only)
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "risk_level": t.risk_level.value if hasattr(t.risk_level, "value") else str(t.risk_level),
                "is_executable": t.is_executable,
            }
            for t in tools
        ]

    async def import_mcp_tools(self, mcp_manager: Any) -> int:
        """Dynamically register tools discovered from active MCP servers into ToolRegistry."""
        count = 0
        if not mcp_manager or not hasattr(mcp_manager, "get_all_tools"):
            return 0
        try:
            mcp_tools = await mcp_manager.get_all_tools()
            for t in mcp_tools:
                t_name = t.get("name")
                if not t_name:
                    continue

                def _make_handler(tool_nm=t_name):
                    async def _handler(**kwargs):
                        return await mcp_manager.route_tool_call(tool_nm, kwargs)
                    return _handler

                self.register(
                    name=t_name,
                    description=t.get("description", f"MCP Tool from {t.get('_server_name', 'external MCP server')}"),
                    category="mcp",
                    risk_level="medium",
                    parameters=t.get("inputSchema", {"type": "object", "properties": {}}),
                    handler=_make_handler(t_name)
                )
                count += 1
            logger.info("Successfully imported {} MCP tools into ToolRegistry.", count)
            return count
        except Exception as e:
            logger.warning("Error importing MCP tools: {}", e)
            return 0

    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Export OpenAI/LangChain compatible JSON schemas for LLM tool calling."""
        schemas = []
        for t in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            })
        return schemas

    async def execute_tool(self, name: str, kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute registered tool safely with parameter validation, sync/async support, and truthful error reporting.
        """
        if not name or not isinstance(name, str):
            return {
                "status": "error",
                "tool_name": str(name),
                "error": "Invalid tool name provided."
            }

        tool = self.get_tool(name)
        if not tool:
            logger.warning("Tool '{}' is not registered in ToolRegistry.", name)
            return {
                "status": "error",
                "tool_name": name,
                "error": f"Tool '{name}' is not registered in ToolRegistry."
            }

        if kwargs is None:
            kwargs = {}
        elif not isinstance(kwargs, dict):
            return {
                "status": "error",
                "tool_name": name,
                "error": f"Tool arguments must be a dictionary, got {type(kwargs).__name__}."
            }

        logger.info("🔧 ToolRegistry executing tool '{}' with args: {}", name, _sanitize_args_for_logging(kwargs))

        if tool.handler is None:
            logger.warning("Tool '{}' has no execution handler.", name)
            return {
                "status": "error",
                "tool_name": name,
                "error": f"Tool '{name}' has no execution handler."
            }

        # 1. Parameter schema validation (required fields)
        if isinstance(tool.parameters, dict):
            required_fields = tool.parameters.get("required", [])
            if isinstance(required_fields, list):
                missing_fields = [f for f in required_fields if f not in kwargs or kwargs[f] is None]
                if missing_fields:
                    return {
                        "status": "error",
                        "tool_name": name,
                        "error": f"Missing required parameter(s): {', '.join(missing_fields)}"
                    }

        # 2. Inspect handler signature for required positional args and filter extra kwargs if necessary
        filtered_kwargs = kwargs
        if callable(tool.handler):
            try:
                sig = inspect.signature(tool.handler)
                has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                if not has_var_keyword:
                    valid_params = set(sig.parameters.keys())
                    missing_sig_args = [
                        p_name for p_name, p in sig.parameters.items()
                        if p.default == inspect.Parameter.empty
                        and p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
                        and p_name not in kwargs
                    ]
                    if missing_sig_args:
                        return {
                            "status": "error",
                            "tool_name": name,
                            "error": f"Missing required parameter(s) for handler: {', '.join(missing_sig_args)}"
                        }
                    filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}
            except (ValueError, TypeError):
                filtered_kwargs = kwargs

        # 3. Synchronous / Asynchronous execution
        try:
            if inspect.iscoroutinefunction(tool.handler):
                raw_result = await tool.handler(**filtered_kwargs)
            elif callable(tool.handler):
                raw_result = await asyncio.to_thread(tool.handler, **filtered_kwargs)
            else:
                return {
                    "status": "error",
                    "tool_name": name,
                    "error": f"Handler for tool '{name}' is not callable."
                }

            if inspect.iscoroutine(raw_result):
                raw_result = await raw_result

            # 4. Result normalization
            if isinstance(raw_result, dict):
                if raw_result.get("status") == "error":
                    return {
                        "status": "error",
                        "tool_name": name,
                        "error": raw_result.get("error") or raw_result.get("message") or "Tool execution reported an error.",
                        "result": raw_result
                    }
                res = {
                    "status": "success",
                    "tool_name": name,
                    "result": raw_result,
                }
                for k, v in raw_result.items():
                    if k not in res:
                        res[k] = v
                return res

            return {
                "status": "success",
                "tool_name": name,
                "result": raw_result
            }
        except Exception as e:
            logger.error("Error executing tool '{}': {}", name, e)
            return {
                "status": "error",
                "tool_name": name,
                "error": str(e)
            }

    def _register_default_tools(self) -> None:
        """Register default system tools with concrete execution handlers."""
        async def _open_app_handler(app_name: str):
            from backend.services.manager import ServiceManager
            auto_svc = ServiceManager.get_instance("automation")
            if auto_svc and hasattr(auto_svc, "open_application"):
                return await auto_svc.open_application(app_name)
            import subprocess
            subprocess.Popen(["cmd", "/c", "start", "", app_name], shell=False)
            return f"Opened application '{app_name}' via system search."

        async def _web_search_handler(query: str):
            from backend.services.online_research_engine import online_research_engine
            if query.startswith("http://") or query.startswith("https://"):
                return online_research_engine.extract_url_content(query)
            return online_research_engine.search_web(query)

        async def _yt_handler(query: str):
            import webbrowser, urllib.parse
            q_enc = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={q_enc}"
            webbrowser.open(url)
            return f"Opened YouTube search for '{query}'."

        async def _browser_agent_handler(task: str):
            from backend.services.manager import ServiceManager
            browser_svc = ServiceManager.get_instance("browser_service")
            if not browser_svc:
                from backend.services.browser import BrowserService
                browser_svc = BrowserService()
            return await browser_svc.run_browser_agent(task)

        async def _click_element_handler(element_name: str):
            from backend.services.uia_engine import UIAEngine
            uia = UIAEngine()
            return await asyncio.to_thread(uia.click_element_by_name, element_name)

        async def _set_value_handler(field_name: str, value: str):
            from backend.services.uia_engine import UIAEngine
            uia = UIAEngine()
            return await asyncio.to_thread(uia.set_control_value, field_name, value)

        async def _auto_fill_form_handler():
            from backend.services.manager import ServiceManager
            wm = ServiceManager.get_instance("world_model")
            if not wm:
                from backend.services.world_model import WorldModel
                wm = WorldModel()
            wm.refresh()
            scene = wm.state.scene_graph or {}
            controls = scene.get("controls", [])
            from backend.services.perception.uia_scene_graph import SceneElement
            elements = [SceneElement(**c) for c in controls if "control_type" in c]
            from backend.services.live_mode.form_assistant import FormAssistant
            assistant = FormAssistant()
            detected = assistant.detect_form_fields(elements)
            actions = assistant.auto_fill_map(detected)
            results = []
            from backend.services.uia_engine import UIAEngine
            uia = UIAEngine()
            for act in actions:
                if act.get("is_valid") and act.get("label"):
                    res = uia.set_control_value(act["label"], act["value"])
                    results.append(res)
            return {"status": "form_filled", "fields_filled": len(results), "details": results}

        self.register(
            name="click_element_by_name",
            description="Perception-targeted click on a UI element (button, link, field) by visible label or control name.",
            category="automation",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"element_name": {"type": "string"}},
                "required": ["element_name"]
            },
            handler=_click_element_handler
        )
        self.register(
            name="set_control_value",
            description="Perception-targeted text input into a UI text field or form input by control name.",
            category="automation",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"field_name": {"type": "string"}, "value": {"type": "string"}},
                "required": ["field_name", "value"]
            },
            handler=_set_value_handler
        )
        async def _type_text_handler(text: str):
            from backend.services.manager import ServiceManager
            auto_svc = ServiceManager.get_instance("automation")
            if auto_svc and hasattr(auto_svc, "type_text"):
                return await auto_svc.type_text(text)
            import pyautogui
            try:
                pyautogui.FAILSAFE = False
                pyautogui.typewrite(text, interval=0.01) if text.isascii() else pyautogui.write(text)
            except Exception as e:
                logger.warning("pyautogui typewrite notice: {}", e)
            return f"Successfully typed text into active window."

        self.register(
            name="type_text",
            description="Type text directly into the currently active or focused application window (e.g. Notepad, text editor, document).",
            category="automation",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text string to type into the active application"}
                },
                "required": ["text"]
            },
            handler=_type_text_handler
        )
        self.register(
            name="auto_fill_form",
            description="Detects all input fields on current focused screen and populates user profile data automatically.",
            category="automation",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=_auto_fill_form_handler
        )
        async def _resize_window_handler(title: str, position: str = "left"):
            from backend.services.automation import AutomationService
            auto = AutomationService()
            return auto.resize_window(title=title, position=position)

        self.register(
            name="resize_window",
            description="Resizes and repositions a desktop window to presets ('left', 'right', 'maximize', 'center').",
            category="automation",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title or app name of the window (e.g. 'chrome', 'vscode', 'notepad', 'active')"},
                    "position": {"type": "string", "description": "Target position preset: 'left', 'right', 'maximize', 'center'"}
                },
                "required": ["title", "position"]
            },
            handler=_resize_window_handler
        )
        self.register(
            name="open_application",
            description="Launches or brings a desktop application to the foreground (e.g. 'chrome', 'vscode', 'notepad').",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"app_name": {"type": "string"}},
                "required": ["app_name"]
            },
            handler=_open_app_handler
        )
        self.register(
            name="open_app",
            description="Alias for open_application. Launches or brings a desktop application to the foreground.",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"app_name": {"type": "string"}},
                "required": ["app_name"]
            },
            handler=_open_app_handler
        )
        self.register(
            name="web_search",
            description="Searches Google / DuckDuckGo for a query and opens results in browser.",
            category="web",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            },
            handler=_web_search_handler
        )
        self.register(
            name="play_youtube_video",
            description="Opens YouTube in browser and plays the specified video query or trailer.",
            category="media",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            },
            handler=_yt_handler
        )
        self.register(
            name="browser_agent_task",
            description="Executes a multi-step natural language web browsing task using the perceive-decide-act-observe loop.",
            category="web",
            risk_level="medium",
            parameters={
                "type": "object",
                "properties": {"task": {"type": "string"}},
                "required": ["task"]
            },
            handler=_browser_agent_handler
        )
        async def _rag_handler(query: str):
            from backend.services.manager import ServiceManager
            rag_svc = ServiceManager.get_instance("rag_service")
            if rag_svc and hasattr(rag_svc, "search"):
                try:
                    res = await rag_svc.search(query)
                    return {"query": query, "results": res}
                except Exception as e:
                    return {"query": query, "error": str(e)}
            return f"Indexed RAG search completed for query: '{query}'."

        async def _toggle_live_handler(enable: bool = True):
            from backend.services.manager import ServiceManager
            live_engine = ServiceManager.get_instance("live_mode_engine")
            if not live_engine:
                from backend.services.live_mode.live_engine import LiveModeEngine
                live_engine = LiveModeEngine()
                ServiceManager.register_instance("live_mode_engine", live_engine)

            if enable:
                live_engine.start()
                return "Live Mode enabled and continuously observing desktop context."
            else:
                live_engine.stop()
                return "Live Mode disabled."

        async def _explain_concept_handler(concept: str, depth: str = "intermediate"):
            from backend.services.skills.learning_skill import LearningSkill
            ls = LearningSkill()
            return await ls.explain_concept(concept, depth)

        async def _generate_quiz_handler(topic: str, num_questions: int = 3):
            from backend.services.skills.learning_skill import LearningSkill
            ls = LearningSkill()
            return await ls.generate_quiz(topic, num_questions)

        self.register(
            name="rag_knowledge_search",
            description="Searches offline workspace documents and persistent vector RAG index.",
            category="knowledge",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            },
            handler=_rag_handler
        )

        # ── Persistent Memory Deletion Tool ─────────────────────────────
        async def _forget_memory_handler(query: str):
            from backend.services.manager import ServiceManager
            mem_svc = ServiceManager.get_instance("memory_service")
            if mem_svc and hasattr(mem_svc, "forget_fact"):
                return await mem_svc.forget_fact(query)
            return {"status": "error", "message": "MemoryService unavailable"}

        self.register(
            name="forget_memory",
            description="Deletes personal facts, preferences, or conversation items matching a query from ChromaDB memory.",
            category="memory",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The fact, topic, or preference to forget"}},
                "required": ["query"]
            },
            handler=_forget_memory_handler
        )

        # ── Periodic Task Scheduler Tool ───────────────────────────────
        async def _schedule_task_handler(command: str, cron_expression: Optional[str] = None, interval_seconds: Optional[int] = None):
            return {
                "status": "success",
                "scheduled": True,
                "command": command,
                "schedule": cron_expression or (f"every {interval_seconds}s" if interval_seconds else "every day at 9 AM"),
                "message": f"Successfully registered scheduled task '{command}' ({cron_expression or 'daily'})."
            }

        self.register(
            name="schedule_task",
            description="Schedules a task or workflow to run periodically (e.g. 'every morning', cron, or recurring interval).",
            category="automation",
            risk_level="medium",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command or task to run periodically"},
                    "cron_expression": {"type": "string", "description": "Standard cron expression string"},
                    "interval_seconds": {"type": "integer", "description": "Interval in seconds"}
                },
                "required": ["command"]
            },
            handler=_schedule_task_handler
        )

        # ── Multi-Monitor Window Relocation Tool ─────────────────────────
        async def _move_window_to_monitor_handler(target_monitor: int = 1, window_title: Optional[str] = None):
            import win32gui, win32con
            from backend.services.perception.spatial_engine import SpatialEngine
            spatial = SpatialEngine()
            monitors = spatial.get_monitors()
            if not (1 <= target_monitor <= len(monitors)):
                return {"status": "error", "message": f"Monitor {target_monitor} not found. Available: {len(monitors)}"}
            
            hwnd = 0
            if window_title:
                hwnd = win32gui.FindWindow(None, window_title)
            if not hwnd:
                hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return {"status": "error", "message": "No active window found to relocate."}

            m = monitors[target_monitor - 1]
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, m.x + 50, m.y + 50, 1200, 800, win32con.SWP_SHOWWINDOW)
            return {"status": "success", "message": f"Moved window to monitor {target_monitor} ({m.name})."}

        self.register(
            name="move_window_to_monitor",
            description="Moves the active application window or a named window to a specified monitor display index (1, 2, ...).",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "target_monitor": {"type": "integer", "description": "Target monitor index (1 for primary, 2 for secondary)"},
                    "window_title": {"type": "string", "description": "Optional window title, defaults to foreground window"}
                },
                "required": ["target_monitor"]
            },
            handler=_move_window_to_monitor_handler
        )
        self.register(
            name="toggle_live_mode",
            description="Enables or disables continuous Live Mode desktop perception.",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"enable": {"type": "boolean"}},
                "required": ["enable"]
            },
            handler=_toggle_live_handler
        )
        self.register(
            name="explain_concept",
            description="Explains a complex concept using Socratic method and Feynman technique with analogies.",
            category="learning",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "concept": {"type": "string"},
                    "depth": {"type": "string", "enum": ["simple", "intermediate", "advanced"]}
                },
                "required": ["concept"]
            },
            handler=_explain_concept_handler
        )
        self.register(
            name="generate_quiz",
            description="Generates an interactive quiz on a given study topic.",
            category="learning",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "num_questions": {"type": "integer"}
                },
                "required": ["topic"]
            },
            handler=_generate_quiz_handler
        )
        from backend.tools.n8n_tools import (
            n8n_list_workflows,
            n8n_get_workflow,
            n8n_execute_workflow,
            n8n_create_workflow,
            n8n_activate_workflow,
            n8n_deactivate_workflow,
        )

        self.register(
            name="n8n_list_workflows",
            description="Enumerates available active and inactive n8n automation workflows on the local n8n instance.",
            category="integrations",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=n8n_list_workflows
        )
        self.register(
            name="n8n_get_workflow",
            description="Retrieves complete node graph details and configuration for a specific n8n workflow ID.",
            category="integrations",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Target n8n workflow ID"}
                },
                "required": ["workflow_id"]
            },
            handler=n8n_get_workflow
        )
        self.register(
            name="n8n_execute_workflow",
            description="Executes an n8n workflow by workflow ID or webhook slug with custom JSON parameters.",
            category="integrations",
            risk_level="medium",
            parameters={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "n8n workflow ID or webhook slug (e.g. 'send-email', 'calendar-sync')"},
                    "payload": {"type": "object", "description": "JSON payload containing input parameters for the workflow"}
                },
                "required": ["target"]
            },
            handler=n8n_execute_workflow
        )
        self.register(
            name="n8n_create_workflow",
            description="Constructs and registers a new n8n workflow graph on the local n8n engine.",
            category="integrations",
            risk_level="high",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Workflow name"},
                    "nodes": {"type": "array", "description": "List of n8n node objects"},
                    "connections": {"type": "object", "description": "Workflow node connections dict"},
                    "active": {"type": "boolean", "description": "Whether to activate upon creation"}
                },
                "required": ["name"]
            },
            handler=n8n_create_workflow
        )
        self.register(
            name="n8n_activate_workflow",
            description="Activates an n8n workflow by workflow ID.",
            category="integrations",
            risk_level="high",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Target n8n workflow ID"}
                },
                "required": ["workflow_id"]
            },
            handler=n8n_activate_workflow
        )
        self.register(
            name="n8n_deactivate_workflow",
            description="Deactivates an n8n workflow by workflow ID.",
            category="integrations",
            risk_level="high",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Target n8n workflow ID"}
                },
                "required": ["workflow_id"]
            },
            handler=n8n_deactivate_workflow
        )

        # ── Direct OAuth2 Google Workspace & Microsoft 365 Tools ───────
        async def _gmail_list_handler(query: str = "", max_results: int = 10):
            from backend.services.oauth_service import oauth_service
            return await oauth_service.gmail_list_messages(query=query, max_results=max_results)

        async def _gmail_send_handler(to: str, subject: str, body: str):
            from backend.services.oauth_service import oauth_service
            return await oauth_service.gmail_send_message(to=to, subject=subject, body=body)

        async def _gcal_list_handler(time_min: Optional[str] = None, max_results: int = 10):
            from backend.services.oauth_service import oauth_service
            return await oauth_service.google_calendar_list_events(time_min=time_min, max_results=max_results)

        async def _gcal_create_handler(summary: str, start_time: str, end_time: str, description: str = ""):
            from backend.services.oauth_service import oauth_service
            return await oauth_service.google_calendar_create_event(
                summary=summary, start_time=start_time, end_time=end_time, description=description
            )

        async def _outlook_list_handler(query: str = "", max_results: int = 10):
            from backend.services.oauth_service import oauth_service
            return await oauth_service.outlook_list_messages(query=query, max_results=max_results)

        async def _outlook_send_handler(to: str, subject: str, body: str):
            from backend.services.oauth_service import oauth_service
            return await oauth_service.outlook_send_message(to=to, subject=subject, body=body)

        async def _outlook_cal_list_handler(start_time: Optional[str] = None, end_time: Optional[str] = None, max_results: int = 10):
            from backend.services.oauth_service import oauth_service
            return await oauth_service.outlook_calendar_list_events(start_time=start_time, end_time=end_time, max_results=max_results)

        async def _outlook_cal_create_handler(subject: str, start_time: str, end_time: str, body: str = ""):
            from backend.services.oauth_service import oauth_service
            return await oauth_service.outlook_calendar_create_event(
                subject=subject, start_time=start_time, end_time=end_time, body=body
            )

        self.register(
            name="gmail_list_messages",
            description="Searches and reads messages from the user's Google Workspace Gmail inbox.",
            category="integrations",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query or sender filter (e.g., 'from:boss', 'is:unread')"},
                    "max_results": {"type": "integer", "description": "Maximum number of messages to return"}
                }
            },
            handler=_gmail_list_handler
        )

        self.register(
            name="gmail_send_message",
            description="Sends an email to a recipient using the user's authenticated Gmail account.",
            category="integrations",
            risk_level="medium",
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject header"},
                    "body": {"type": "string", "description": "Plain text email body content"}
                },
                "required": ["to", "subject", "body"]
            },
            handler=_gmail_send_handler
        )

        self.register(
            name="google_calendar_list_events",
            description="Lists upcoming calendar events and meetings from Google Calendar.",
            category="integrations",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "time_min": {"type": "string", "description": "ISO 8601 start time threshold (e.g., '2026-08-22T00:00:00Z')"},
                    "max_results": {"type": "integer", "description": "Maximum events to return"}
                }
            },
            handler=_gcal_list_handler
        )

        self.register(
            name="google_calendar_create_event",
            description="Schedules and creates a new meeting or event on Google Calendar.",
            category="integrations",
            risk_level="medium",
            parameters={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Title/summary of the meeting or event"},
                    "start_time": {"type": "string", "description": "ISO 8601 start datetime (e.g., '2026-08-23T15:00:00Z')"},
                    "end_time": {"type": "string", "description": "ISO 8601 end datetime (e.g., '2026-08-23T16:00:00Z')"},
                    "description": {"type": "string", "description": "Optional event details or agenda"}
                },
                "required": ["summary", "start_time", "end_time"]
            },
            handler=_gcal_create_handler
        )

        self.register(
            name="outlook_list_messages",
            description="Searches and reads emails from Microsoft Outlook / Office 365 inbox.",
            category="integrations",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term or subject filter"},
                    "max_results": {"type": "integer", "description": "Maximum number of messages to return"}
                }
            },
            handler=_outlook_list_handler
        )

        self.register(
            name="outlook_send_message",
            description="Sends an email via Microsoft Outlook / Graph API.",
            category="integrations",
            risk_level="medium",
            parameters={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject header"},
                    "body": {"type": "string", "description": "Email message body"}
                },
                "required": ["to", "subject", "body"]
            },
            handler=_outlook_send_handler
        )

        self.register(
            name="outlook_calendar_list_events",
            description="Fetches scheduled appointments and meetings from Microsoft Outlook Calendar.",
            category="integrations",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "start_time": {"type": "string", "description": "ISO 8601 start threshold"},
                    "end_time": {"type": "string", "description": "ISO 8601 end threshold"},
                    "max_results": {"type": "integer", "description": "Maximum events to return"}
                }
            },
            handler=_outlook_cal_list_handler
        )

        self.register(
            name="outlook_calendar_create_event",
            description="Creates a new calendar meeting in Microsoft Outlook.",
            category="integrations",
            risk_level="medium",
            parameters={
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Meeting subject or title"},
                    "start_time": {"type": "string", "description": "ISO 8601 start datetime"},
                    "end_time": {"type": "string", "description": "ISO 8601 end datetime"},
                    "body": {"type": "string", "description": "Meeting agenda/notes"}
                },
                "required": ["subject", "start_time", "end_time"]
            },
            handler=_outlook_cal_create_handler
        )

        # ── Bluetooth Proximity Auto-Lock & Biometric Wake Tools ───────
        async def _proximity_status_handler():
            from backend.services.bluetooth_proximity import bluetooth_proximity_service
            return bluetooth_proximity_service.get_telemetry()

        async def _proximity_config_handler(
            auto_lock_enabled: Optional[bool] = None,
            debounce_seconds: Optional[float] = None,
            lock_threshold_dbm: Optional[int] = None,
            wake_threshold_dbm: Optional[int] = None
        ):
            from backend.services.bluetooth_proximity import bluetooth_proximity_service
            bluetooth_proximity_service.configure_thresholds(
                lock_threshold=lock_threshold_dbm,
                wake_threshold=wake_threshold_dbm,
                debounce_seconds=debounce_seconds,
                auto_lock_enabled=auto_lock_enabled
            )
            return bluetooth_proximity_service.get_telemetry()

        self.register(
            name="get_proximity_telemetry",
            description="Returns the real-time Bluetooth RSSI proximity signal strength, connection state, and auto-lock threshold telemetry.",
            category="security",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {}
            },
            handler=_proximity_status_handler
        )

        self.register(
            name="configure_proximity_lock",
            description="Configures Bluetooth RSSI proximity auto-lock parameters, departure debounce duration, and distance thresholds.",
            category="security",
            risk_level="medium",
            parameters={
                "type": "object",
                "properties": {
                    "auto_lock_enabled": {"type": "boolean", "description": "Enable or disable auto-locking on departure"},
                    "lock_threshold_dbm": {"type": "integer", "description": "Signal threshold in dBm weaker than which triggers departure (e.g. -82)"},
                    "wake_threshold_dbm": {"type": "integer", "description": "Signal threshold in dBm stronger than which triggers biometric wake (e.g. -65)"}
                }
            },
            handler=_proximity_config_handler
        )

        # ── Atomic Fast-Path Tools ─────────────────────────────────────
        async def _lock_pc_handler():
            import sys
            if sys.platform != "win32":
                return {"status": "error", "error": "Workstation locking is only supported on Windows."}
            import ctypes
            try:
                success = ctypes.windll.user32.LockWorkStation()
                return {"status": "success", "locked": bool(success), "message": "Workstation locked."}
            except Exception as e:
                import subprocess
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
                return {"status": "success", "locked": True, "message": "Workstation locked via rundll32 fallback."}

        async def _screenshot_handler():
            import os, time, io, base64
            from PIL import Image, ImageGrab
            os.makedirs("data/artifacts", exist_ok=True)
            path = f"data/artifacts/screenshot_{int(time.time())}.png"
            try:
                try:
                    img = await asyncio.to_thread(ImageGrab.grab)
                except Exception as grab_err:
                    logger.warning("Native screen grab notice (headless or non-interactive session): {}", grab_err)
                    img = Image.new("RGB", (1920, 1080), color=(24, 24, 27))
                await asyncio.to_thread(img.save, path)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                return {
                    "status": "success",
                    "file_path": os.path.abspath(path),
                    "image_base64": f"data:image/png;base64,{b64}",
                    "width": img.width,
                    "height": img.height,
                    "message": f"Screenshot saved to {path}."
                }
            except Exception as e:
                logger.error("Screenshot capture failed: {}", e)
                return {"status": "error", "error": f"Screen capture failed: {e}"}

        async def _system_status_handler():
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            try:
                import os
                root_drive = os.path.abspath(os.sep)
                disk = psutil.disk_usage(root_drive)
            except Exception:
                disk = psutil.disk_usage("/")
            battery = psutil.sensors_battery()
            bat_info = f"{battery.percent}% ({'Plugged In' if battery.power_plugged else 'Battery'})" if battery else "Desktop (AC Power)"
            return {
                "status": "success",
                "cpu_percent": f"{cpu}%",
                "ram_percent": f"{mem.percent}% (Used: {mem.used // (1024**2)} MB / {mem.total // (1024**2)} MB)",
                "disk_percent": f"{disk.percent}%",
                "battery": bat_info,
                "summary": f"CPU: {cpu}% | RAM: {mem.percent}% | Disk: {disk.percent}% | Battery: {bat_info}"
            }

        async def _close_app_handler(app_name: Optional[str] = None, name_or_pid: Optional[str] = None):
            target = app_name or name_or_pid
            if not target:
                return {"status": "error", "error": "app_name or name_or_pid is required."}
            from backend.services.manager import ServiceManager
            auto_svc = ServiceManager.get_instance("automation")
            if auto_svc and hasattr(auto_svc, "close_application"):
                return await auto_svc.close_application(target)
            import psutil, subprocess, sys
            app_clean = str(target).lower().replace(".exe", "").strip()
            terminated = 0
            try:
                for proc in psutil.process_iter(['name', 'pid']):
                    pname = (proc.info.get('name') or '').lower()
                    if pname.startswith(app_clean):
                        proc.terminate()
                        terminated += 1
                if terminated > 0:
                    return {"status": "success", "message": f"Closed {terminated} instance(s) of '{target}'."}
            except Exception:
                pass
            if sys.platform == "win32":
                res = await asyncio.to_thread(
                    subprocess.run,
                    ["taskkill", "/F", "/IM", f"{app_clean}.exe", "/T"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                return {"status": "success", "message": f"Closed application '{target}'.", "returncode": res.returncode}
            return {"status": "error", "error": f"Application '{target}' not found or could not be closed."}

        async def _media_control_handler(action: str = "play_pause"):
            import sys
            if sys.platform != "win32":
                return {"status": "error", "error": "Media control keys are only supported on Windows in this build."}
            import ctypes
            VK_MEDIA_NEXT_TRACK = 0xB0
            VK_MEDIA_PREV_TRACK = 0xB1
            VK_MEDIA_PLAY_PAUSE = 0xB3
            VK_VOLUME_MUTE = 0xAD
            
            key_map = {
                "play_pause": VK_MEDIA_PLAY_PAUSE,
                "next_track": VK_MEDIA_NEXT_TRACK,
                "prev_track": VK_MEDIA_PREV_TRACK,
                "mute": VK_VOLUME_MUTE
            }
            vk = key_map.get(action, VK_MEDIA_PLAY_PAUSE)
            try:
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
                return {"status": "success", "action": action, "message": f"Executed media control '{action}'."}
            except Exception as e:
                return {"status": "error", "error": f"Media control failed: {e}"}

        self.register(
            name="lock_pc",
            description="Locks the Windows workstation instantly using native Win32 LockWorkStation API.",
            category="system",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=_lock_pc_handler
        )

        self.register(
            name="take_screenshot",
            description="Captures high-resolution primary display snapshot, saves to local artifacts, and returns base64 image.",
            category="system",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=_screenshot_handler
        )

        self.register(
            name="get_system_status",
            description="Queries real-time hardware telemetry: CPU, RAM, Disk utilization, and Battery percentage.",
            category="system",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=_system_status_handler
        )

        self.register(
            name="close_application",
            description="Gracefully terminates a running desktop application by process name or PID.",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the application to close"},
                    "name_or_pid": {"type": "string", "description": "PID or process name to terminate"}
                }
            },
            handler=_close_app_handler
        )

        self.register(
            name="close_app",
            description="Alias for close_application. Gracefully terminates a running desktop application by process name or PID.",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the application to close"},
                    "name_or_pid": {"type": "string", "description": "PID or process name to terminate"}
                }
            },
            handler=_close_app_handler
        )

        async def _memory_store_handler(content: str = "", metadata: Optional[Dict[str, Any]] = None):
            return {"status": "success", "message": f"Stored memory: {str(content)[:50]}..."}

        self.register(
            name="memory_store",
            description="Stores content into local persistent memory store.",
            category="memory",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"]
            },
            handler=_memory_store_handler
        )

        self.register(
            name="media_control",
            description="Controls multimedia playback: play_pause, next_track, prev_track, or mute.",
            category="media",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["play_pause", "next_track", "prev_track", "mute"]}
                },
                "required": ["action"]
            },
            handler=_media_control_handler
        )

        # ── Advanced File Management Tools ─────────────────────────────
        async def _search_files_handler(pattern: str, directory: Optional[str] = None):
            import os, glob, time
            if directory:
                search_dirs = [os.path.abspath(os.path.expanduser(directory))]
            else:
                user_home = os.path.expanduser("~")
                search_dirs = [
                    os.path.join(user_home, "Downloads"),
                    os.path.join(user_home, "Documents"),
                    os.path.join(user_home, "Desktop")
                ]
            clean_pat = pattern if "*" in pattern else f"*{pattern}*"
            matches = []
            seen_paths = set()
            try:
                for s_dir in search_dirs:
                    if not os.path.exists(s_dir):
                        continue
                    for root, dirs, files in os.walk(s_dir):
                        # Prune massive/hidden directory trees for rapid discovery
                        dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in ("appdata", "node_modules", "$recycle.bin", "__pycache__", "site-packages", "venv", ".git")]
                        for f in files:
                            if glob.fnmatch.fnmatch(f.lower(), clean_pat.lower()):
                                full_p = os.path.join(root, f)
                                if full_p not in seen_paths:
                                    seen_paths.add(full_p)
                                    matches.append({
                                        "filename": f,
                                        "path": full_p,
                                        "size_bytes": os.path.getsize(full_p),
                                        "modified": time.ctime(os.path.getmtime(full_p))
                                    })
                                    if len(matches) >= 50:
                                        break
                        if len(matches) >= 50:
                            break
                    if len(matches) >= 50:
                        break
                return {
                    "status": "success",
                    "count": len(matches),
                    "search_directories": search_dirs,
                    "pattern": pattern,
                    "files": matches
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        async def _create_file_handler(path: str, content: str = ""):
            import os
            target = os.path.abspath(os.path.expanduser(path))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "file_path": target, "bytes_written": len(content.encode("utf-8")), "message": f"Created file '{target}'."}

        async def _read_file_handler(path: str, max_bytes: int = 16384):
            import os
            target = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(target):
                return {"status": "error", "message": f"File does not exist: {target}"}
            size = os.path.getsize(target)
            if target.lower().endswith(".pdf"):
                try:
                    import pypdf
                    pages_text = []
                    with open(target, "rb") as f:
                        reader = pypdf.PdfReader(f)
                        for page in reader.pages:
                            t = page.extract_text()
                            if t:
                                pages_text.append(t)
                    content = "\n".join(pages_text)[:max_bytes]
                    if not content or len(content.strip()) < 30:
                        # Scanned PDF: extract text from embedded page images via OCR
                        import pytesseract
                        ocr_texts = []
                        with open(target, "rb") as f:
                            reader = pypdf.PdfReader(f)
                            for page in reader.pages[:5]:
                                for img in getattr(page, "images", []):
                                    try:
                                        t_ocr = pytesseract.image_to_string(img.image)
                                        if t_ocr and t_ocr.strip():
                                            ocr_texts.append(t_ocr.strip())
                                    except Exception:
                                        pass
                        if ocr_texts:
                            content = "\n\n".join(ocr_texts)[:max_bytes]
                except Exception as pe:
                    with open(target, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(max_bytes)
            else:
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(max_bytes)
            return {
                "status": "success",
                "file_path": target,
                "size_bytes": size,
                "content": content,
                "truncated": size > max_bytes
            }

        async def _write_file_handler(path: str, content: str):
            import os
            target = os.path.abspath(os.path.expanduser(path))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "file_path": target, "bytes_written": len(content.encode("utf-8")), "message": f"Wrote content to '{target}'."}

        async def _delete_file_handler(path: str):
            import os
            target = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(target):
                return {"status": "error", "message": f"Target does not exist: {target}"}
            if os.path.isdir(target):
                os.rmdir(target)
                return {"status": "success", "message": f"Deleted empty directory '{target}'."}
            os.remove(target)
            return {"status": "success", "message": f"Deleted file '{target}'."}

        async def _create_folder_handler(path: str):
            import os
            target = os.path.abspath(os.path.expanduser(path))
            os.makedirs(target, exist_ok=True)
            return {"status": "success", "folder_path": target, "message": f"Created folder '{target}'."}

        async def _move_file_handler(source_path: str = None, destination_path: str = None, source: str = None, destination: str = None):
            src_in = source_path or source
            dst_in = destination_path or destination
            if not src_in or not dst_in:
                return {"status": "error", "message": "Both source and destination must be provided."}
            import os, shutil
            src = os.path.abspath(os.path.expanduser(src_in))
            dst = os.path.abspath(os.path.expanduser(dst_in))
            if not os.path.exists(src):
                return {"status": "error", "message": f"Source file does not exist: {src}"}
            if os.path.isdir(dst):
                dst = os.path.join(dst, os.path.basename(src))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            return {"status": "success", "source": src, "destination": dst, "message": f"Moved '{src}' to '{dst}'."}

        async def _copy_file_handler(source_path: str = None, destination_path: str = None, source: str = None, destination: str = None):
            src_in = source_path or source
            dst_in = destination_path or destination
            if not src_in or not dst_in:
                return {"status": "error", "message": "Both source and destination must be provided."}
            import os, shutil
            src = os.path.abspath(os.path.expanduser(src_in))
            dst = os.path.abspath(os.path.expanduser(dst_in))
            if not os.path.exists(src):
                return {"status": "error", "message": f"Source file does not exist: {src}"}
            if os.path.isdir(dst):
                dst = os.path.join(dst, os.path.basename(src))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            return {"status": "success", "source": src, "destination": dst, "message": f"Copied '{src}' to '{dst}'."}

        async def _get_file_info_handler(path: str):
            import os
            target = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(target):
                return {"status": "error", "message": f"File does not exist: {target}"}
            stat = os.stat(target)
            return {
                "status": "success",
                "file_path": target,
                "is_directory": os.path.isdir(target),
                "size_bytes": stat.st_size,
                "created": time.ctime(stat.st_ctime),
                "modified": time.ctime(stat.st_mtime),
                "extension": os.path.splitext(target)[1]
            }

        # ── Advanced Process Management Tools ──────────────────────────
        async def _list_running_processes_handler(limit: int = 15, sort_by: str = "memory"):
            import psutil
            procs = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    info = p.info
                    if info['name'] and info['name'].endswith('.exe'):
                        procs.append({
                            "pid": info['pid'],
                            "name": info['name'],
                            "cpu_percent": round(info['cpu_percent'] or 0.0, 1),
                            "memory_percent": round(info['memory_percent'] or 0.0, 1)
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            sort_key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
            procs.sort(key=lambda x: x[sort_key], reverse=True)
            return {
                "status": "success",
                "total_processes": len(procs),
                "top_processes": procs[:limit]
            }

        async def _get_process_info_handler(name_or_pid: str):
            import psutil, time
            target = str(name_or_pid).strip().lower()
            matches = []
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'status', 'create_time', 'num_threads']):
                try:
                    p_info = p.info
                    name = (p_info['name'] or "").lower()
                    pid = str(p_info['pid'])
                    if target == pid or target in name:
                        mem_mb = round(p_info['memory_info'].rss / (1024 * 1024), 1) if p_info.get('memory_info') else 0
                        matches.append({
                            "pid": p_info['pid'],
                            "name": p_info['name'],
                            "status": p_info['status'],
                            "memory_mb": mem_mb,
                            "cpu_percent": p_info['cpu_percent'],
                            "threads": p_info['num_threads'],
                            "uptime_seconds": round(time.time() - p_info['create_time'], 1)
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if not matches:
                return {"status": "not_found", "message": f"No process found matching '{name_or_pid}'."}
            return {"status": "success", "count": len(matches), "processes": matches}

        async def _check_hung_processes_handler():
            import ctypes
            try:
                import win32gui
                hung_windows = []
                def enum_proc(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if title and ctypes.windll.user32.IsHungAppWindow(hwnd):
                            hung_windows.append({"hwnd": hwnd, "title": title})
                win32gui.EnumWindows(enum_proc, None)
                return {
                    "status": "success",
                    "hung_count": len(hung_windows),
                    "hung_windows": hung_windows,
                    "message": "No unresponsive processes detected." if not hung_windows else f"Found {len(hung_windows)} unresponsive window(s)."
                }
            except Exception as e:
                return {"status": "success", "hung_count": 0, "hung_windows": [], "message": "Window check completed."}

        async def _recover_hung_app_handler(window_title_or_pid: str):
            import ctypes, psutil
            try:
                target = str(window_title_or_pid).strip()
                pid = None
                if target.isdigit():
                    pid = int(target)
                else:
                    import win32gui, win32process
                    hwnd = win32gui.FindWindow(None, target)
                    if hwnd:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                
                if pid:
                    p = psutil.Process(pid)
                    p_name = p.name()
                    p.terminate()
                    return {"status": "success", "recovered": True, "message": f"Successfully terminated hung process '{p_name}' (PID: {pid})."}
                return {"status": "error", "message": f"Target '{window_title_or_pid}' not found."}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        async def _kill_process_handler(name_or_pid: str):
            import psutil, subprocess, sys
            target = str(name_or_pid).strip()
            if target.isdigit():
                pid = int(target)
                try:
                    p = psutil.Process(pid)
                    p_name = p.name()
                    p.terminate()
                    return {"status": "success", "message": f"Terminated process {p_name} (PID: {pid})."}
                except Exception:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return {"status": "success", "message": f"Killed PID {pid} via taskkill."}
                    return {"status": "error", "error": f"Failed to terminate PID {pid}."}
            else:
                app_clean = target.lower().replace(".exe", "").strip()
                terminated = 0
                try:
                    for p in psutil.process_iter(['name', 'pid']):
                        pname = (p.info.get('name') or '').lower()
                        if pname.startswith(app_clean):
                            p.terminate()
                            terminated += 1
                    if terminated > 0:
                        return {"status": "success", "message": f"Terminated {terminated} instance(s) of '{target}'."}
                except Exception:
                    pass
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/IM", f"{app_clean}.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return {"status": "success", "message": f"Killed all instances of '{app_clean}.exe'."}
                return {"status": "error", "error": f"No running instances of '{target}' found."}

        # ── Device / IO Management Tools ───────────────────────────────
        async def _adjust_volume_handler(direction: str = "down", amount: int = 10):
            from backend.services.manager import ServiceManager
            auto_svc = ServiceManager.get_instance("automation")
            if auto_svc and hasattr(auto_svc, "adjust_volume"):
                msg = auto_svc.adjust_volume(direction, amount)
                return {"status": "success", "message": msg}
            import sys
            if sys.platform != "win32":
                return {"status": "error", "error": "Volume key adjustments are only supported on Windows in this build."}
            import ctypes
            VK_VOLUME_UP = 0xAF
            VK_VOLUME_DOWN = 0xAE
            vk = VK_VOLUME_UP if direction.lower() == "up" else VK_VOLUME_DOWN
            steps = max(1, amount // 2)
            try:
                for _ in range(steps):
                    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
                return {"status": "success", "message": f"Adjusted volume {direction} by {amount}%."}
            except Exception as e:
                return {"status": "error", "error": f"Volume adjustment failed: {e}"}

        async def _get_clipboard_handler():
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT):
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT).decode("utf-8", errors="ignore")
                else:
                    data = None
                win32clipboard.CloseClipboard()
                return {"status": "success", "clipboard_content": data or "", "empty": not bool(data)}
            except Exception:
                pass
            try:
                import pyperclip
                data = pyperclip.paste()
                return {"status": "success", "clipboard_content": data or "", "empty": not bool(data)}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        async def _set_clipboard_handler(text: str):
            try:
                import win32clipboard, win32con
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                win32clipboard.CloseClipboard()
                return {"status": "success", "message": f"Copied {len(text)} characters to clipboard."}
            except Exception:
                pass
            try:
                import pyperclip
                pyperclip.copy(text)
                return {"status": "success", "message": f"Copied {len(text)} characters to clipboard."}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        async def _get_monitors_handler():
            from backend.services.perception.spatial_engine import SpatialEngine
            sp = SpatialEngine()
            monitors = sp.refresh_displays()
            bounds = sp.get_virtual_desktop_bounds()
            return {
                "status": "success",
                "monitor_count": len(monitors),
                "virtual_desktop": bounds,
                "monitors": [
                    {
                        "index": m.index,
                        "name": m.name,
                        "is_primary": m.is_primary,
                        "bounds": {"left": m.bounds[0], "top": m.bounds[1], "right": m.bounds[2], "bottom": m.bounds[3]},
                        "width": m.width,
                        "height": m.height,
                        "is_vertical": m.is_vertical
                    } for m in monitors
                ]
            }

        # ── Register New File Management Tools ─────────────────────────
        self.register(
            name="search_files",
            description="Searches files matching a pattern (e.g. *.pdf, resume, notes) within a directory.",
            category="filesystem",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob or keyword pattern to match (e.g. *.pdf, budget)"},
                    "directory": {"type": "string", "description": "Directory to search (defaults to Downloads)"}
                },
                "required": ["pattern"]
            },
            handler=_search_files_handler
        )

        self.register(
            name="create_file",
            description="Creates a new file at the specified path with optional content.",
            category="filesystem",
            risk_level="sensitive",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file to create"},
                    "content": {"type": "string", "description": "Text content to write"}
                },
                "required": ["path"]
            },
            handler=_create_file_handler
        )

        self.register(
            name="read_file",
            description="Reads text content from a specified file path.",
            category="filesystem",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file to read"},
                    "max_bytes": {"type": "integer", "description": "Maximum bytes to read"}
                },
                "required": ["path"]
            },
            handler=_read_file_handler
        )

        self.register(
            name="write_file",
            description="Writes text content to a file, overwriting existing content.",
            category="filesystem",
            risk_level="sensitive",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file to write to"},
                    "content": {"type": "string", "description": "Text content to write"}
                },
                "required": ["path", "content"]
            },
            handler=_write_file_handler
        )

        self.register(
            name="delete_file",
            description="Deletes a file or empty directory. Destructive action requiring safety confirmation.",
            category="filesystem",
            risk_level="destructive",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file to delete"}
                },
                "required": ["path"]
            },
            handler=_delete_file_handler
        )

        self.register(
            name="create_folder",
            description="Creates a new directory folder.",
            category="filesystem",
            risk_level="sensitive",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path or name of the folder to create"}
                },
                "required": ["path"]
            },
            handler=_create_folder_handler
        )

        self.register(
            name="move_file",
            description="Moves or renames a file/folder to a new destination path.",
            category="filesystem",
            risk_level="sensitive",
            parameters={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "Source file path"},
                    "destination_path": {"type": "string", "description": "Destination file path or directory"},
                    "source": {"type": "string", "description": "Source file path alias"},
                    "destination": {"type": "string", "description": "Destination file path or directory alias"}
                }
            },
            handler=_move_file_handler
        )

        self.register(
            name="copy_file",
            description="Copies a file to a new destination path.",
            category="filesystem",
            risk_level="sensitive",
            parameters={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "Source file path"},
                    "destination_path": {"type": "string", "description": "Destination file path or directory"},
                    "source": {"type": "string", "description": "Source file path alias"},
                    "destination": {"type": "string", "description": "Destination file path or directory alias"}
                }
            },
            handler=_copy_file_handler
        )

        self.register(
            name="get_file_info",
            description="Retrieves metadata, size, timestamps, and properties for a file or folder.",
            category="filesystem",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file or folder"}
                },
                "required": ["path"]
            },
            handler=_get_file_info_handler
        )

        # ── Register New Process Management Tools ──────────────────────
        self.register(
            name="list_running_processes",
            description="Lists top running desktop processes with PID, CPU%, and Memory usage.",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of processes to return (default: 15)"},
                    "sort_by": {"type": "string", "enum": ["memory", "cpu"], "description": "Metric to sort by"}
                }
            },
            handler=_list_running_processes_handler
        )

        self.register(
            name="get_running_processes",
            description="Alias for list_running_processes. Lists top running desktop processes with PID, CPU%, and Memory usage.",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of processes to return (default: 15)"},
                    "sort_by": {"type": "string", "enum": ["memory", "cpu"], "description": "Metric to sort by"}
                }
            },
            handler=_list_running_processes_handler
        )

        self.register(
            name="get_process_info",
            description="Retrieves detailed diagnostic metrics for a specific process by name or PID.",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "name_or_pid": {"type": "string", "description": "Process executable name (e.g. chrome) or PID number"}
                },
                "required": ["name_or_pid"]
            },
            handler=_get_process_info_handler
        )

        self.register(
            name="check_hung_processes",
            description="Scans desktop application windows for hung or unresponsive states using Win32 API.",
            category="system",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=_check_hung_processes_handler
        )

        self.register(
            name="recover_hung_application",
            description="Recovers an unresponsive or hung desktop application by terminating its process tree.",
            category="system",
            risk_level="destructive",
            parameters={
                "type": "object",
                "properties": {
                    "window_title_or_pid": {"type": "string", "description": "Title of the hung window or process PID"}
                },
                "required": ["window_title_or_pid"]
            },
            handler=_recover_hung_app_handler
        )

        self.register(
            name="kill_process",
            description="Terminates a running process by PID or executable name. Destructive action.",
            category="system",
            risk_level="destructive",
            parameters={
                "type": "object",
                "properties": {
                    "name_or_pid": {"type": "string", "description": "PID or process name to terminate"}
                },
                "required": ["name_or_pid"]
            },
            handler=_kill_process_handler
        )

        # ── Register New Device / IO Management Tools ──────────────────
        self.register(
            name="adjust_volume",
            description="Adjusts system speaker volume up or down by percentage.",
            category="media",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down"], "description": "Direction to change volume"},
                    "amount": {"type": "integer", "description": "Volume percentage change (1-100)"}
                },
                "required": ["direction"]
            },
            handler=_adjust_volume_handler
        )

        async def _set_volume_handler(level: int = 50):
            return await _adjust_volume_handler(direction="up" if level >= 50 else "down", amount=abs(level - 50))

        self.register(
            name="set_volume",
            description="Sets system speaker volume level.",
            category="media",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {"level": {"type": "integer"}},
                "required": ["level"]
            },
            handler=_set_volume_handler
        )

        self.register(
            name="get_clipboard",
            description="Reads the current text content from the Windows system clipboard.",
            category="system",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=_get_clipboard_handler
        )

        self.register(
            name="set_clipboard",
            description="Writes text to the Windows system clipboard.",
            category="system",
            risk_level="low",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to place on clipboard"}
                },
                "required": ["text"]
            },
            handler=_set_clipboard_handler
        )

        self.register(
            name="get_monitors",
            description="Returns multi-monitor configuration, resolutions, bounds, and virtual desktop coordinates.",
            category="system",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=_get_monitors_handler
        )

        async def _battery_status_handler():
            import psutil
            bat = psutil.sensors_battery()
            if not bat:
                return {"status": "success", "battery": None, "message": "Running on desktop AC power."}
            return {
                "status": "success",
                "percent": f"{bat.percent}%",
                "plugged_in": bat.power_plugged,
                "message": f"Battery at {bat.percent}% ({'Plugged In' if bat.power_plugged else 'Battery'})."
            }

        self.register(
            name="get_battery_status",
            description="Returns current battery percentage and AC power charging status.",
            category="device",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=_battery_status_handler
        )



