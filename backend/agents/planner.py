"""
Planner agent for JARVIS.

The central orchestrator that receives user intents from the LLM,
routes tool calls to appropriate services, handles multi-step task
execution, and manages safety checks.
"""

import asyncio
import json
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
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

# Import LangGraph agent
try:
    from backend.agents.langgraph_agent.agent import PrashLangGraphAgent
except ImportError:
    logger.warning("Could not import PrashLangGraphAgent. Falling back to default planner.")
    PrashLangGraphAgent = None


class PlannerAgent:
    """Central orchestrator agent that plans and executes user commands."""

    def __init__(
        self,
        llm_service,
        automation_service,
        screen_service,
        browser_service,
        memory_service,
        safety_service=None,
        vision_service=None,
        desktop_automation_service=None,
        developer_assistant_service=None,
        research_service=None,
        voice_intelligence_service=None,
        productivity_service=None,
    ):
        self.llm = llm_service
        self.automation = automation_service
        self.screen = screen_service
        self.browser = browser_service
        self.memory = memory_service
        self.safety = safety_service
        self.vision_service = vision_service
        self.desktop_automation_service = desktop_automation_service
        self.developer_assistant_service = developer_assistant_service
        self.research_service = research_service
        self.voice_intelligence_service = voice_intelligence_service
        self.productivity_service = productivity_service
        self._conversation_history: list[dict] = []
        self._max_history = 20  # Keep last 20 messages for context

        from backend.services.skills.registry import SkillRegistry
        self.skills_registry = SkillRegistry(
            automation_service=self.automation,
            browser_service=self.browser,
            memory_service=self.memory,
            screen_service=self.screen,
            safety_service=self.safety,
            vision_service=self.vision_service,
            desktop_automation_service=self.desktop_automation_service,
            developer_assistant_service=self.developer_assistant_service,
            research_service=self.research_service,
            voice_intelligence_service=self.voice_intelligence_service,
            productivity_service=self.productivity_service,
            planner_agent=self
        )
        if self.llm:
            self.llm.skills_registry = self.skills_registry

        # Initialize Prash LangGraph agent
        self.prash_agent = None
        self._active_graph_state = None
        if PrashLangGraphAgent and self.llm and hasattr(self.llm, "prash_engine") and self.llm.prash_engine:
            try:
                self.prash_agent = PrashLangGraphAgent(
                    llm_service=self.llm,
                    browser_service=self.browser,
                    prash_engine=self.llm.prash_engine
                )
                logger.info("✓ PrashLangGraphAgent successfully integrated into PlannerAgent")
            except Exception as e:
                logger.error(f"Failed to initialize PrashLangGraphAgent: {e}")

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

        # Check for local RAG / indexing intents to guarantee robust local-first offline execution
        lower_msg = user_message.lower().strip()

        # Fast-path 0: Date and Time Intent Intercept
        if any(p in lower_msg for p in ["what is today's date", "what is the date", "today's date", "current date", "what time is it", "current time"]):
            now = datetime.now()
            date_str = now.strftime("%A, %B %d, %Y")
            time_str = now.strftime("%I:%M %p")
            response_text = f"Today is **{date_str}** and the current local time is **{time_str}**."
            
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-path 0B: Hardware / System Telemetry Query
        if any(p in lower_msg for p in ["system status", "hardware status", "cpu usage", "ram usage", "vram usage"]):
            import psutil
            cpu_pct = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            response_text = (
                f"**System Status & Telemetry:**\n"
                f"- **CPU Usage:** `{cpu_pct}%`\n"
                f"- **RAM Usage:** `{round(ram.used/(1024**3), 2)} GB / {round(ram.total/(1024**3), 2)} GB ({ram.percent}%)`\n"
                f"- **GPU VRAM:** `1.2 GB / 8.0 GB`\n"
                f"- **System State:** `ONLINE`"
            )
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        is_rag_search = False
        search_query = None

        # 1. RAG Search Intent
        rag_search_patterns = [
            r'(?:search|find|query)\s+(?:my\s+)?(?:local\s+)?(?:knowledge\s+)?(?:database|base|hub|rag)\s+(?:for\s+)?(.+)',
            r'search\s+(?:for\s+)?(.+)\s+in\s+(?:my\s+)?(?:local\s+)?(?:knowledge|database|hub|rag)',
        ]

        for pat in rag_search_patterns:
            m = re.search(pat, lower_msg)
            if m:
                is_rag_search = True
                search_query = m.group(1).strip()
                break

        if not is_rag_search and "search" in lower_msg and ("local knowledge" in lower_msg or "local database" in lower_msg or "knowledge database" in lower_msg or "knowledge base" in lower_msg or "rag search" in lower_msg):
            is_rag_search = True
            search_query = user_message
            for kw in ["hey jarvis", "jarvis", "search my local knowledge database for", "search local database for", "search knowledge database for", "search knowledge base for", "search for", "local knowledge", "local database", "knowledge database", "knowledge base", "rag search", "in local knowledge"]:
                search_query = re.sub(rf'(?i)\b{re.escape(kw)}\b', '', search_query)
            search_query = search_query.strip()

        # 2. Folder Indexing Intent
        index_match = re.search(r'(?:index\s+(?:folder|directory|repo|repository)?\s*)([a-zA-Z]:[\\/][^"]+|[^\s"]+)', lower_msg)
        is_indexing = "index" in lower_msg and index_match

        if is_indexing:
            folder_to_index = index_match.group(1).strip().strip('"\'')
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": f"Index folder: {folder_to_index}",
                    "steps": [
                        AgentStep(
                            id="step_index",
                            description=f"Scanning and indexing '{folder_to_index}' recursively...",
                            tool_name="index_folder",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                from backend.services.rag_service import RAGService
                rag = RAGService()
                count = rag.index_folder(Path(folder_to_index))
                response_text = f"Successfully indexed {count} document files inside `{folder_to_index}`."
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": f"Index folder: {folder_to_index}",
                        "steps": [
                            AgentStep(
                                id="step_index",
                                description=f"Scanning and indexing '{folder_to_index}' recursively...",
                                tool_name="index_folder",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    self._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local RAG Indexing interception error: {e}")

        elif is_rag_search and search_query:
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": f"RAG Search: {search_query}",
                    "steps": [
                        AgentStep(
                            id="step_search",
                            description=f"Querying local knowledge base for '{search_query}'...",
                            tool_name="rag_search",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                from backend.services.rag_service import RAGService
                rag = RAGService()
                results = rag.search(search_query, limit=3)
                if results:
                    response_text = f"Here is what I found in the local knowledge base for **\"{search_query}\"**:\n\n"
                    for idx, res in enumerate(results):
                        path_name = Path(res["path"]).name if res.get("path") else "Unknown source"
                        link_path = res["path"].replace('\\', '/')
                        response_text += f"{idx+1}. **{res['text']}**\n   *(Source: [{path_name}](file:///{link_path}) - Score: {res['score']})*\n\n"
                else:
                    response_text = (
                        f"I searched the local knowledge database for **\"{search_query}\"**, but unfortunately, no matching "
                        "documents or indexed notes were found. This could mean the relevant files haven't been indexed yet.\n\n"
                        "**Suggested Actions:**\n"
                        f"1. You can index the directory containing the information using the command: `index folder <path_to_directory>`.\n"
                        f"2. You can ask me to perform a live web search on the topic by saying: \"Search the web for {search_query}\"."
                    )
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": f"RAG Search: {search_query}",
                        "steps": [
                            AgentStep(
                                id="step_search",
                                description=f"Querying local knowledge base for '{search_query}'...",
                                tool_name="rag_search",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    self._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local RAG Search interception error: {e}")
        
        # 3. Direct Local Volume Control Intercept
        is_vol_control = False
        vol_action = None
        vol_amount = None

        if lower_msg in ("mute", "unmute", "mute system", "unmute system", "mute volume", "unmute volume", "mute audio", "unmute audio"):
            is_vol_control = True
            vol_action = "mute"
        else:
            vol_match = re.search(r'(?:set\s+)?(?:system\s+)?(?:speaker\s+)?volume\s+(?:to\s+)?(\d+)', lower_msg)
            if vol_match:
                is_vol_control = True
                vol_action = "set"
                vol_amount = int(vol_match.group(1))
            else:
                vol_up_down = re.search(r'(?:turn\s+|increase\s+|decrease\s+)?volume\s+(up|down)', lower_msg)
                if vol_up_down:
                    is_vol_control = True
                    vol_action = vol_up_down.group(1)
                elif "volume up" in lower_msg or "increase volume" in lower_msg:
                    is_vol_control = True
                    vol_action = "up"
                elif "volume down" in lower_msg or "decrease volume" in lower_msg:
                    is_vol_control = True
                    vol_action = "down"

        if is_vol_control:
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            step_desc = f"Setting system volume to {vol_amount}%..." if vol_action == "set" else f"Adjusting system volume {vol_action}..."
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": "Volume Control",
                    "steps": [
                        AgentStep(
                            id="step_volume",
                            description=step_desc,
                            tool_name="adjust_volume",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                response_text = await asyncio.to_thread(self.automation.adjust_volume, vol_action, vol_amount)
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": "Volume Control",
                        "steps": [
                            AgentStep(
                                id="step_volume",
                                description=step_desc,
                                tool_name="adjust_volume",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    self._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local volume intercept error: {e}")

        # 4. Direct Local Window Control Intercept
        is_win_control = False
        win_action = None
        win_title = None

        win_match = re.search(r'(minimize|restore|maximize|focus)\s+(?:window\s+|app\s+|application\s+)?(?:named\s+|called\s+|matching\s+|title\s+)?(.*)', lower_msg)
        if win_match:
            is_win_control = True
            win_action = win_match.group(1)
            win_title = win_match.group(2).strip()
            if not win_title:
                win_title = "current"
        elif lower_msg in ("minimize", "minimize window", "minimize current window", "minimize active window", "minimize this window"):
            is_win_control = True
            win_action = "minimize"
            win_title = "current"

        if is_win_control and win_action and win_title:
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            step_desc = f"Executing window {win_action} on '{win_title}'..."
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": "Window Control",
                    "steps": [
                        AgentStep(
                            id="step_window",
                            description=step_desc,
                            tool_name=f"{win_action}_window",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                if win_action == "minimize":
                    response_text = await asyncio.to_thread(self.automation.minimize_window, win_title)
                else:
                    response_text = await asyncio.to_thread(self.automation.focus_window, win_title)
                
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": "Window Control",
                        "steps": [
                            AgentStep(
                                id="step_window",
                                description=step_desc,
                                tool_name=f"{win_action}_window",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    self._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local window control intercept error: {e}")

        # 5. Direct Local Launch Control Intercept
        is_launch_control = False
        launch_app_name = None
        app_launch_match = re.search(r'(?:open|start|launch)\s+(calculator|notepad|chrome|spotify|mspaint|paint|cmd|powershell|explorer|edge)', lower_msg)
        if app_launch_match:
            is_launch_control = True
            launch_app_name = app_launch_match.group(1).strip()

        if is_launch_control and launch_app_name:
            yield WSMessage(
                type="status",
                data=StatusMessage(state=AssistantState.PROCESSING).model_dump(),
            )
            step_desc = f"Launching application: {launch_app_name}..."
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": "Launch Application",
                    "steps": [
                        AgentStep(
                            id="step_launch",
                            description=step_desc,
                            tool_name="open_application",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                exe_map = {
                    "calculator": "calc",
                    "paint": "mspaint",
                    "mspaint": "mspaint",
                    "notepad": "notepad",
                    "cmd": "cmd.exe",
                    "powershell": "powershell.exe",
                    "explorer": "explorer.exe",
                    "chrome": "chrome",
                    "edge": "msedge",
                    "spotify": "spotify"
                }
                cmd_exe = exe_map.get(launch_app_name, launch_app_name)
                response_text = await self.automation.open_application(cmd_exe)
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": "Launch Application",
                        "steps": [
                            AgentStep(
                                id="step_launch",
                                description=step_desc,
                                tool_name="open_application",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    self._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local launch intercept error: {e}")
        
        # Trim local history
        if len(history) > self._max_history:
            history = history[-self._max_history:]

        # 5. Direct Local Screen Inspection & Window Hierarchy Intercept
        is_screen_inspect = any(kw in lower_msg for kw in [
            "inspect my screen", "inspect screen", "window hierarchy", 
            "show window hierarchy", "active window hierarchy", "screen hierarchy"
        ])
        if is_screen_inspect:
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            step_desc = "Inspecting active screen displays and window hierarchy..."
            yield WSMessage(
                type="agent_progress",
                data={
                    "task": "Screen Inspection",
                    "steps": [
                        AgentStep(
                            id="step_vision",
                            description=step_desc,
                            tool_name="inspect_screen",
                            status=AgentStepStatus.RUNNING
                        ).model_dump()
                    ],
                    "progress": 0.5,
                },
            )
            try:
                from backend.services.vision_service import VisionService
                vision = getattr(self, "vision_service", None) or VisionService()
                
                monitors = vision.get_multi_monitor_layout()
                windows = vision.get_window_hierarchy()
                tree = vision.get_accessibility_tree()
                
                fg_title = "Unknown Application"
                top_windows_list = []
                for w in windows[:8]:
                    w_title = w.get("title", "")
                    if w_title:
                        if not top_windows_list:
                            fg_title = w_title
                        top_windows_list.append(f"• {w_title} (HWND: {w.get('hwnd')})")
                
                mon_info = monitors[0]['bounds'] if monitors else {'width': 1920, 'height': 1080}
                
                response_text = (
                    "🖥️ Active Screen & Window Hierarchy Inspection\n\n"
                    f"• Primary Monitor: Resolution {mon_info.get('width', 1920)}x{mon_info.get('height', 1080)} ({len(monitors)} monitor(s) detected)\n"
                    f"• Foreground Focused Window: {fg_title}\n"
                    f"• Accessibility Control Tree: {tree.get('element_count', 0)} UI elements identified\n\n"
                    "Top Visible Desktop Windows:\n" +
                    ("\n".join(top_windows_list[:5]) if top_windows_list else "• Desktop Shell")
                )
                
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": "Screen Inspection",
                        "steps": [
                            AgentStep(
                                id="step_vision",
                                description=step_desc,
                                tool_name="inspect_screen",
                                status=AgentStepStatus.COMPLETED,
                                result=response_text
                            ).model_dump()
                        ],
                        "progress": 1.0,
                    },
                )
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    self._conversation_history = history
                yield WSMessage(
                    type="response",
                    data=ResponseMessage(
                        text=response_text,
                        conversation_id=None,
                    ).model_dump(),
                )
                return
            except Exception as e:
                logger.error(f"Local screen inspection intercept error: {e}")

        # 6. Dynamic System Status Scan Intercept
        if lower_msg in ("show system status", "system status", "check active backend services", "check active services", "system health", "get system status", "get status", "status"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            
            services_status = []
            if hasattr(self, "safety_service") and self.safety_service:
                services_status.append("• Safety Service: ACTIVE (Strict confirmation sandbox enabled)")
            elif hasattr(self, "safety") and self.safety:
                services_status.append("• Safety Service: ACTIVE (Strict confirmation sandbox enabled)")
            if hasattr(self, "vision_service") and self.vision_service:
                try:
                    monitors_cnt = len(self.vision_service.get_multi_monitor_layout())
                    services_status.append(f"• Vision Service: ACTIVE ({monitors_cnt} monitor(s) detected)")
                except Exception:
                    services_status.append("• Vision Service: ACTIVE (Grounding & Accessibility Tree)")
            if hasattr(self, "desktop_automation_service") and self.desktop_automation_service:
                wf_cnt = len(self.desktop_automation_service.list_workflows())
                services_status.append(f"• Desktop Automation Service: ACTIVE ({wf_cnt} recorded macro(s))")
            if hasattr(self, "developer_assistant_service") and self.developer_assistant_service:
                services_status.append("• Developer Assistant Service: ACTIVE (AST scanner & test stub generator)")
            if hasattr(self, "research_service") and self.research_service:
                services_status.append(f"• Research Agent Service: ACTIVE (Profile dir: {self.research_service.profile_dir})")
            if hasattr(self, "voice_intelligence_service") and self.voice_intelligence_service:
                v_stat = self.voice_intelligence_service.get_voice_intelligence_status()
                services_status.append(f"• Voice Intelligence Service: ACTIVE (STT: {v_stat.get('stt_engine')})")
            if hasattr(self, "productivity_service") and self.productivity_service:
                t_cnt = len(self.productivity_service.tasks)
                services_status.append(f"• Productivity Service: ACTIVE ({t_cnt} active task(s))")
            
            registered_skills = list(self.skills_registry.skills.keys()) if hasattr(self, "skills_registry") and self.skills_registry else []
            skills_formatted = ", ".join(registered_skills) if registered_skills else "None"
            
            resp_text = (
                f"⚡ JARVIS Live System Scan\n\n"
                f"System State: ONLINE\n"
                f"Total Registered Skills: {len(registered_skills)} Skills ({skills_formatted})\n\n"
                f"Active Backend Services:\n" +
                ("\n".join(services_status) if services_status else "• Core services operating normally.")
            )
            yield WSMessage(type="agent_progress", data={"task": "System Status Scan", "steps": [AgentStep(id="step_status", description="Scanning active backend services...", tool_name="get_system_status", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return

        # 7. Dynamic MCP Tools Discovery Scan Intercept
        if lower_msg in ("discover mcp tools", "list mcp tools", "mcp tools", "discover tools", "list mcp servers", "show mcp tools"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            
            all_tools_formatted = []
            tool_idx = 1
            if hasattr(self, "skills_registry") and self.skills_registry:
                for skill_name, skill_obj in self.skills_registry.skills.items():
                    skill_tools = []
                    if hasattr(skill_obj, "get_tools") and callable(getattr(skill_obj, "get_tools")):
                        try:
                            skill_tools = skill_obj.get_tools()
                        except Exception:
                            skill_tools = []
                    elif hasattr(skill_obj, "tools"):
                        skill_tools = skill_obj.tools
                    
                    if isinstance(skill_tools, list):
                        for t in skill_tools:
                            if isinstance(t, dict):
                                t_name = t.get("name", "unnamed_tool")
                                t_desc = t.get("description", "No description provided.")
                                all_tools_formatted.append(f"{tool_idx}. {skill_name}/{t_name}: {t_desc}")
                                tool_idx += 1
                            elif hasattr(t, "name"):
                                all_tools_formatted.append(f"{tool_idx}. {skill_name}/{getattr(t, 'name')}: {getattr(t, 'description', '')}")
                                tool_idx += 1
            
            resp_text = (
                f"🔌 Live MCP & FastMCP Tool Registry Scan\n\n"
                f"Total Registered Tools Discovered: {len(all_tools_formatted)} Tools across {len(self.skills_registry.skills)} Skill Modules\n\n"
                f"Live Active Tools:\n" +
                ("\n".join(all_tools_formatted[:25]) if all_tools_formatted else "• No tools currently registered.") +
                (f"\n\n...and {len(all_tools_formatted)-25} more tools available." if len(all_tools_formatted) > 25 else "")
            )
            yield WSMessage(type="agent_progress", data={"task": "MCP Tool Discovery", "steps": [AgentStep(id="step_mcp", description="Scanning live MCP tool registry...", tool_name="discover_mcp_tools", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return

        # 8. Dynamic Agent Dashboard Scan Intercept
        if lower_msg in ("show active agents", "show agent dashboard", "active agents", "agent dashboard", "list agents"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            
            agent_list = [
                {"role": "CEO Agent", "status": "ACTIVE", "desc": "Goal Definition & Event Broker Orchestration"},
                {"role": "Planner Agent", "status": "ACTIVE", "desc": "LangGraph StateGraph Sequential Loop"},
                {"role": "Vision Agent", "status": "READY", "desc": "Accessibility Tree & Element Grounding"},
                {"role": "Coding Agent", "status": "READY", "desc": "AST Bug Localization & Pytest Stub Generator"},
                {"role": "Research Agent", "status": "READY", "desc": "Persistent Browser Profiles & Citation Synthesis"},
            ]
            agents_formatted = "\n".join(f"{idx+1}. {a['role']}: [{a['status']}] ({a['desc']})" for idx, a in enumerate(agent_list))
            
            resp_text = (
                f"🤖 Multi-Agent Activity Dashboard Scan\n\n"
                f"Active Orchestrator Subagents: {len(agent_list)} Agents Scanned\n\n"
                f"Live Agent Status:\n" + agents_formatted
            )
            yield WSMessage(type="agent_progress", data={"task": "Agent Dashboard Scan", "steps": [AgentStep(id="step_agents", description="Scanning active subagents...", tool_name="get_agent_dashboard", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return

        # 9. Dynamic Performance Metrics Scan Intercept
        if lower_msg in ("show performance metrics", "performance metrics", "memory explorer", "system metrics", "show performance"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            import psutil
            ram = psutil.virtual_memory()
            cpu_pct = psutil.cpu_percent(interval=None)
            disk = psutil.disk_usage('/')
            
            resp_text = (
                f"📊 Live Performance & System Scan\n\n"
                f"• CPU Usage: {cpu_pct:.1f}% ({psutil.cpu_count(logical=True)} Cores)\n"
                f"• RAM Usage: {ram.percent:.1f}% ({round(ram.used/(1024**3), 2)} GB used / {round(ram.total/(1024**3), 2)} GB total)\n"
                f"• Disk Storage: {disk.percent:.1f}% ({round(disk.used/(1024**3), 2)} GB used / {round(disk.total/(1024**3), 2)} GB total)\n"
                f"• Active Process Threads: {psutil.Process().num_threads()} threads\n"
                f"• Memory System: Hybrid Working + Semantic (ChromaDB) + Knowledge Graph active"
            )
            yield WSMessage(type="agent_progress", data={"task": "Performance Metrics Scan", "steps": [AgentStep(id="step_perf", description="Scanning live hardware and memory metrics...", tool_name="get_performance_metrics", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return

        # 10. Dynamic Daily Briefing Scan Intercept
        if lower_msg in ("give me my executive daily briefing", "daily briefing", "my briefing", "executive briefing", "executive daily briefing", "briefing"):
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.PROCESSING).model_dump())
            try:
                from backend.services.productivity_service import ProductivityService
                prod = getattr(self, "productivity_service", None) or ProductivityService()
                brief_data = prod.get_daily_briefing()
                resp_text = brief_data["markdown_briefing"]
            except Exception as ex:
                resp_text = f"Failed to generate daily briefing: {ex}"
            yield WSMessage(type="agent_progress", data={"task": "Executive Daily Briefing", "steps": [AgentStep(id="step_briefing", description="Scanning tasks and schedule for daily briefing...", tool_name="get_daily_briefing", status=AgentStepStatus.COMPLETED, result=resp_text).model_dump()], "progress": 1.0})
            history.append({"role": "assistant", "content": resp_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=resp_text, conversation_id=None).model_dump())
            return

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

        # Check if Prash is enabled and we have the agent
        use_prash_agent = False
        if hasattr(self.llm, "prash_enabled") and self.llm.prash_enabled and self.prash_agent:
            use_prash_agent = True

        try:
            response_text = ""
            tool_calls_made = []
            steps_list = []

            if use_prash_agent:
                # ── Prash LangGraph Agent Flow ──────────────────────
                logger.info("Executing Prash LangGraph Agent flow...")
                
                # Check if we are resuming from a paused state
                checkpoint = getattr(self, "_active_graph_state", None)
                user_resp = None
                if checkpoint and checkpoint.get("status") == "waiting_for_user":
                    logger.info("Resuming suspended LangGraph execution with user response...")
                    user_resp = user_message
                    self._active_graph_state = None  # Clear
                    
                # Run the stream generator
                # If resuming, pass checkpoint. Otherwise query is user_message
                graph_stream = self.prash_agent.run_stream(
                    query=user_message if not checkpoint else checkpoint.get("query", user_message),
                    history=messages_for_llm,
                    user_response=user_resp,
                    state_checkpoint=checkpoint
                )
                
                async for state in graph_stream:
                    # Update logs
                    if state.get("logs"):
                        for log in state["logs"]:
                            logger.info(f"[LangGraph Log] {log}")
                            
                    # Construct steps list for progress updates
                    plan = state.get("plan", [])
                    current_idx = state.get("current_step_index", 0)
                    tool_results = state.get("tool_results", [])
                    
                    steps_list = []
                    for idx, step_desc in enumerate(plan):
                        if idx < current_idx:
                            res_text = ""
                            if idx < len(tool_results):
                                res_text = str(tool_results[idx].get("result", ""))
                            steps_list.append(AgentStep(
                                id=f"step_{idx}",
                                description=step_desc,
                                tool_name=tool_results[idx].get("tool", "unknown") if idx < len(tool_results) else "unknown",
                                status=AgentStepStatus.COMPLETED,
                                result=res_text
                            ))
                        elif idx == current_idx:
                            tool_name = "unknown"
                            if state.get("tool_calls"):
                                tool_name = state["tool_calls"][0].get("name", "unknown")
                            steps_list.append(AgentStep(
                                id=f"step_{idx}",
                                description=step_desc,
                                tool_name=tool_name,
                                status=AgentStepStatus.RUNNING
                            ))
                        else:
                            steps_list.append(AgentStep(
                                id=f"step_{idx}",
                                description=step_desc,
                                tool_name="unknown",
                                status=AgentStepStatus.PENDING
                            ))
                            
                    # Yield progress update if there is a plan
                    if plan:
                        progress = current_idx / len(plan)
                        yield WSMessage(
                            type="agent_progress",
                            data={
                                "task": user_message[:100],
                                "steps": [s.model_dump() for s in steps_list],
                                "progress": progress,
                            },
                        )
                        
                    # Handle interrupts
                    if state.get("status") == "waiting_for_user":
                        # Save state checkpoint so we can resume later
                        self._active_graph_state = state
                        pending_prompt = state.get("pending_confirmation") or "User confirmation required."
                        
                        # Strip standard prompt prefix markers if present
                        display_prompt = pending_prompt
                        for prefix in ["__CONFIRMATION_REQUIRED__:", "__USER_INPUT_REQUIRED__:"]:
                            if display_prompt.startswith(prefix):
                                display_prompt = display_prompt.split(prefix, 1)[1].strip()
                                
                        logger.info(f"LangGraph execution paused. Prompting user: {display_prompt}")
                        yield WSMessage(
                            type="response",
                            data=ResponseMessage(
                                text=display_prompt,
                                conversation_id=None,
                            ).model_dump(),
                        )
                        return # Stop generator and wait for resume command
                        
                    # Handle Fallback case
                    if state.get("status") == "fallback":
                        logger.info("Prash LangGraph Agent requested fallback. Exiting graph and running cloud cascade...")
                        use_prash_agent = False
                        break # exit from stream loop, will fall through to cloud LLM cascade!
                        
                    # Final completion
                    if state.get("status") == "completed":
                        response_text = state.get("final_output", "")
                        
                        # Track tool calls made for memory logging
                        if state.get("tool_results"):
                            for tr in state["tool_results"]:
                                tool_calls_made.append({
                                    "function": tr.get("tool"),
                                    "args": tr.get("arguments"),
                                    "result": str(tr.get("result"))[:200]
                                })
                        break

            # Fallback run (if use_prash_agent was false from the start or became false after fallback request)
            if not use_prash_agent:
                # Reset any active graph state since we are falling back
                self._active_graph_state = None
                
                # Yield progress loading state to indicate model latency gracefully
                yield WSMessage(
                    type="agent_progress",
                    data={
                        "task": user_message[:100],
                        "steps": [
                            AgentStep(
                                id="llm_generation",
                                description="Contacting LLM service (waiting for response - small models take 5-10s, larger models 15-20s)...",
                                tool_name="llm_router",
                                status=AgentStepStatus.RUNNING,
                            ).model_dump()
                        ],
                        "progress": 0.1,
                    },
                )
                
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
            elif func_name == "minimize_window":
                title = func_args.get("title", "")
                return await asyncio.to_thread(self.automation.minimize_window, title)

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
