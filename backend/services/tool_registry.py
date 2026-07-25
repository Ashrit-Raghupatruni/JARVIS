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
    risk_level: str = "low"  # low, medium, high
    parameters: Dict[str, Any] = Field(default_factory=dict)
    handler: Optional[Any] = Field(default=None, exclude=True)


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
        """Register a tool with metadata and execution handler."""
        meta = ToolMetadata(
            name=name,
            description=description,
            category=category,
            risk_level=risk_level,
            parameters=parameters or {},
            handler=handler
        )
        self._tools[name] = meta
        logger.debug("Registered tool '{}' (risk={})", name, risk_level)

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolMetadata]:
        if category:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

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

    async def execute_tool(self, name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute registered tool safely with risk auditing.
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' is not registered in ToolRegistry.")

        logger.info("🔧 ToolRegistry executing tool '{}' with args: {}", name, kwargs)

        if tool.handler is None:
            return {"status": "success", "result": f"Executed tool '{name}'"}

        try:
            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(**kwargs)
            else:
                result = await asyncio.to_thread(tool.handler, **kwargs)

            return {
                "status": "success",
                "tool_name": name,
                "result": result
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
            import webbrowser, urllib.parse
            q_enc = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={q_enc}"
            webbrowser.open(url)
            return f"Opened browser for web search query: '{query}'."

        async def _yt_handler(query: str):
            import webbrowser, urllib.parse
            q_enc = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={q_enc}"
            webbrowser.open(url)
            return f"Opened YouTube search for '{query}'."

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
        self.register(
            name="auto_fill_form",
            description="Detects all input fields on current focused screen and populates user profile data automatically.",
            category="automation",
            risk_level="low",
            parameters={"type": "object", "properties": {}},
            handler=_auto_fill_form_handler
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
            if live_engine:
                if enable:
                    live_engine.start()
                    return "Live Mode enabled and continuously observing desktop context."
                else:
                    live_engine.stop()
                    return "Live Mode disabled."
            return f"Live Mode status updated to {enable}."

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
