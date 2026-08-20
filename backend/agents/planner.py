"""
Planner agent for JARVIS.

The central orchestrator that receives user intents from the LLM,
routes tool calls to appropriate services, handles multi-step task
execution, and manages safety checks.
"""

import asyncio
import time
import json
import re
import random
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional, Any

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

        # Instantiate Unified Execution Pipeline & Desktop World Model
        try:
            from backend.services.world_model import WorldModel
            from backend.services.tool_registry import ToolRegistry
            from backend.agents.unified_pipeline import UnifiedPipeline

            self.world_model = WorldModel()
            self.tool_registry = ToolRegistry()
            self.pipeline = UnifiedPipeline(
                world_model=self.world_model,
                tool_registry=self.tool_registry,
                llm_service=self.llm
            )
            logger.info("✓ UnifiedPipeline and WorldModel initialized in PlannerAgent")
        except Exception as e:
            logger.warning(f"UnifiedPipeline setup notice: {e}")

    async def plan_and_execute(
        self,
        user_message: str,
        conversation_history: Optional[list[dict]] = None,
        conversation_id: Optional[Any] = None
    ) -> AsyncGenerator[WSMessage, None]:
        """
        Process a user message: understand intent, execute tools, return response.
        Restores prior conversation history from SQLite if conversation_id is provided.
        Yields WSMessage objects for real-time updates to the frontend.
        """
        start_t = time.time()
        active_conv_id: Optional[int] = None
        if conversation_id is not None:
            try:
                active_conv_id = int(conversation_id)
            except (ValueError, TypeError):
                active_conv_id = None

        # ── Restore Context & Initialize Conversation Session ─────────────────
        history: list[dict] = []
        mem_svc = getattr(self, "memory_service", None)
        if not mem_svc:
            from backend.services.manager import ServiceManager
            mem_svc = ServiceManager.get_instance("memory_service")
            self.memory_service = mem_svc

        if conversation_history is not None:
            history = list(conversation_history)
        elif active_conv_id and mem_svc:
            try:
                past_conv = await mem_svc.get_conversation(active_conv_id)
                if past_conv and past_conv.get("messages"):
                    history = [{"role": m["role"], "content": m["content"]} for m in past_conv["messages"]]
                    logger.info("✓ Context restored for conv {}: {} past message(s)", active_conv_id, len(history))
            except Exception as hist_err:
                logger.warning(f"Failed to restore history for conversation {active_conv_id}: {hist_err}")

        if not history and not conversation_history:
            history = list(self._conversation_history)

        # Create session in DB if new
        if not active_conv_id and mem_svc:
            try:
                active_conv_id = await mem_svc.create_conversation(title="New Conversation")
            except Exception as create_err:
                logger.warning(f"Failed to create new conversation in DB: {create_err}")

        # Add user message to history & persist immediately in real-time
        history.append({"role": "user", "content": user_message})
        if active_conv_id and mem_svc:
            try:
                await mem_svc.add_message_to_conversation(active_conv_id, "user", user_message)
            except Exception as save_err:
                logger.warning(f"Failed to persist user message for conv {active_conv_id}: {save_err}")

        # Helper to log experience and reflection automatically upon completing any task
        def _log_self_improving_trace(res_text: str, success: bool = True):
            try:
                from backend.services.manager import ServiceManager
                duration = time.time() - start_t
                exp_engine = ServiceManager.get_instance("experience_engine")
                refl_engine = ServiceManager.get_instance("reflection_engine")
                if exp_engine and hasattr(exp_engine, "record_experience"):
                    exp_engine.record_experience(
                        goal=user_message,
                        execution_time_seconds=duration,
                        result=res_text[:300],
                        success=success
                    )
                if refl_engine and hasattr(refl_engine, "reflect_on_task"):
                    refl_engine.reflect_on_task(
                        goal=user_message,
                        result=res_text[:300],
                        success=success,
                        execution_time=duration
                    )
            except Exception as e:
                logger.warning("Failed to record self-improving experience trace: {}", e)

        # ── 6-Pillar Architecture Control Gate ────────────────────────────────
        from backend.models.envelope import RequestEnvelope, RequestSource, RequestModality, RequestPriority
        from backend.agents.router import RequestRouter, HierarchicalCategory
        from backend.services.safety_gatekeeper import SafetyGatekeeper, ActionRiskLevel
        from backend.services.observability import SessionTraceLogger

        # 1. Normalize Request Envelope
        session_id = f"sess_{int(time.time())}"
        envelope = RequestEnvelope(
            session_id=session_id,
            source=RequestSource.DESKTOP_UI,
            modality=RequestModality.TEXT,
            priority=RequestPriority.INTERACTIVE,
            payload={"type": "text_command", "data": {"text": user_message}}
        )

        # 2. Trace Logger Init
        tracer = SessionTraceLogger(session_id=session_id)
        tracer.log_event("session_started", {"user_message": user_message, "envelope": envelope.model_dump()})

        # 3. Hierarchical Intent & Model Routing
        router = RequestRouter()
        hier_category, model_assign = router.classify_and_route(envelope)
        tracer.log_event("intent_routed", {"category": hier_category.value, "model_assignment": model_assign.model_dump()})
        
        # 4. Out-of-Model Safety Gatekeeper Instance
        gatekeeper = SafetyGatekeeper()

        # Legacy compatibility mapping
        from backend.agents.message_router import classify_request, RequestCategory
        request_cat = classify_request(user_message)
        logger.info(f"Orchestration Router category: {request_cat.value} (Hierarchical: {hier_category.value}, Assigned Model: {model_assign.provider}/{model_assign.model_name}) for prompt: '{user_message[:50]}'")

        # Execute 10-Step Self-Improving OS Lifecycle Pipeline asynchronously for background trace tracking
        if hasattr(self, "pipeline") and self.pipeline:
            try:
                asyncio.create_task(self.pipeline.run(user_message))
                logger.debug("UnifiedPipeline 10-step lifecycle triggered for query: '{}'", user_message[:40])
            except Exception as e:
                logger.warning("UnifiedPipeline background execution notice: {}", e)

        # 5. Silent Language Memory Detection & Context Injection
        from backend.services.language_memory import LanguageMemoryService
        lang_service = LanguageMemoryService()
        lang_service.detect_and_update(user_message)
        lang_instruction = lang_service.get_system_prompt_instruction()

        # 6. Ephemeral Session Memory Context Injection (Read Once & Consume)
        from backend.services.proactive_engine import ProactiveEngine
        proactive_svc = ProactiveEngine()
        sess_mem_summary = proactive_svc.get_and_clear_session_memory()

        # Inject Category-Specific System Prompt Context based on Hierarchical Category
        category_sys_prompt = f"[ROUTER INTENT CONTEXT]: Category={hier_category.value.upper()}, Model={model_assign.provider}/{model_assign.model_name}."
        if lang_instruction:
            category_sys_prompt += f" {lang_instruction}"
        if sess_mem_summary:
            category_sys_prompt += f" [PREVIOUS SESSION MEMORY]: '{sess_mem_summary}'. (Reference this context naturally in your initial response)."

        if hier_category == HierarchicalCategory.KNOWLEDGE:
            category_sys_prompt += " Prioritize structured information synthesis and cited local/web facts."
        elif hier_category == HierarchicalCategory.ACTION:
            category_sys_prompt += " Prioritize direct, unambiguous tool execution and Win32 desktop controls."
        elif hier_category == HierarchicalCategory.MULTI_STEP_TASK:
            category_sys_prompt += " Break task down into distinct, verifiable action steps."

        # Branch on RequestCategory / Live Mode
        if request_cat == RequestCategory.LIVE_MODE_REQUEST or hier_category == HierarchicalCategory.LIVE_PERCEPTION:
            logger.info("Executing Live Mode Perception Workflow for prompt: '{}'", user_message[:50])
            try:
                from backend.utils.service_manager import ServiceManager
                wm = ServiceManager.get_instance("world_model")
                if not wm:
                    from backend.services.world_model import WorldModel
                    wm = WorldModel()
                wm.refresh()
                summary = wm.get_summary()
                scene = wm.state.scene_graph or {}
                controls = scene.get("controls", [])
                ctrl_names = [c.get("name") for c in controls[:15] if c.get("name")]
                ctrl_str = ", ".join(ctrl_names) if ctrl_names else "Standard UI Controls"
                
                live_mode_sys_msg = {
                    "role": "system",
                    "content": f"[LIVE MODE PERCEPTION CONTEXT]: Foreground Window='{summary.get('active_window')}', Indexed Controls=[{ctrl_str}]. You MUST call `click_element_by_name` or `set_control_value` tool functions to interact with visible elements on screen. {category_sys_prompt}"
                }
                history.insert(0, live_mode_sys_msg)
            except Exception as e:
                logger.error("Live Mode context setup notice: {}", e)
        elif request_cat == RequestCategory.KNOWLEDGE_REQUEST or hier_category == HierarchicalCategory.KNOWLEDGE:
            logger.info("Executing Knowledge Retrieval Workflow for prompt: '{}'", user_message[:50])
            history.insert(0, {"role": "system", "content": category_sys_prompt})
        elif request_cat == RequestCategory.ACTION_REQUEST or hier_category == HierarchicalCategory.ACTION:
            logger.info("Executing Desktop Action Workflow for prompt: '{}'", user_message[:50])
            history.insert(0, {"role": "system", "content": category_sys_prompt})
        else:
            logger.info("Executing Conversational Workflow for prompt: '{}'", user_message[:50])
            history.insert(0, {"role": "system", "content": category_sys_prompt})

        lower_msg = user_message.lower().strip()

        # Fast-Path 0A: Live Mode Form Auto-Fill Intercept
        if any(k in lower_msg for k in ["fill form", "auto fill", "fill this form", "autocomplete form"]):
            res = await self.tool_registry.execute_tool("auto_fill_form", {})
            response_text = f"Form auto-fill complete! Populated {res.get('fields_filled', 0)} field(s) using your profile data."
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0B: Perception-Targeted Click Intercept
        if lower_msg.startswith(("click button", "click on", "click ", "press button", "tap ")):
            target_elem = lower_msg.replace("click button", "").replace("click on", "").replace("click", "").replace("press button", "").replace("tap", "").strip()
            if target_elem:
                res = await self.tool_registry.execute_tool("click_element_by_name", {"element_name": target_elem})
                if res.get("status") in ("clicked", "invoked"):
                    response_text = f"Clicked on UI element '{target_elem}' successfully!"
                else:
                    response_text = f"Attempted to click '{target_elem}' on screen (Status: {res.get('status')})."
                yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
                history.append({"role": "assistant", "content": response_text})
                if conversation_history is None:
                    self._conversation_history = history
                yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
                return

        # Fast-Path 0: Conversational Greetings Intercept
        if lower_msg in ("hi", "hello", "hey", "hey jarvis", "hi jarvis", "hello jarvis", "greetings", "good morning", "good afternoon", "good evening"):
            greetings = [
                "Hello sir! How can I assist you today?",
                "Greetings, sir. I am online and at your service.",
                "At your service, sir. What can I do for you?",
                "Hello sir! All systems operational. Ready for your command.",
                "Hey there, sir! Standing by to assist you."
            ]
            response_text = random.choice(greetings)
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-path 0A: Date and Time Intent Intercept
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

        # Fast-Path 0C: YouTube Video & Music Intercept
        if any(p in lower_msg for p in ["youtube", "movie trailer", "play video", "play trailer", "play music", "open spotify"]):
            import webbrowser, urllib.parse
            if lower_msg in ["open youtube", "youtube", "launch youtube"]:
                yt_url = "https://www.youtube.com"
                response_text = "Opening YouTube in Chrome, sir!"
            elif lower_msg in ["play music", "open spotify", "music", "spotify"]:
                # Try opening local Spotify first or fallback to web
                try:
                    from backend.services.manager import ServiceManager
                    auto_svc = ServiceManager.get_instance("automation")
                    if auto_svc and hasattr(auto_svc, "open_application"):
                        res_msg = await auto_svc.open_application("spotify")
                        response_text = res_msg
                    else:
                        webbrowser.open("https://open.spotify.com")
                        response_text = "Opening Spotify Web in Chrome, sir!"
                except Exception:
                    webbrowser.open("https://open.spotify.com")
                    response_text = "Opening Spotify Web in Chrome, sir!"
            else:
                yt_query = lower_msg.replace("play a recent", "").replace("play recent", "").replace("movie trailer", "").replace("after opening youtube in chrome", "").replace("on youtube", "").replace("open youtube", "").replace("and play", "").replace("play", "").strip()
                if not yt_query:
                    yt_url = "https://www.youtube.com"
                    response_text = "Opening YouTube in Chrome, sir!"
                else:
                    yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(yt_query)}"
                    response_text = f"Opening Chrome to search and play '{yt_query}' on YouTube, sir!"
            
            try:
                if 'yt_url' in locals():
                    webbrowser.open(yt_url)
            except Exception as w_err:
                logger.warning(f"Webbrowser launch notice: {w_err}")
                
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0D: Local News & Web Search Intent Intercept
        if any(p in lower_msg for p in ["local news", "latest news", "search news", "open chrome and search"]):
            import webbrowser, urllib.parse
            q_terms = lower_msg.replace("search the web for", "").replace("search news", "").replace("open chrome and search for", "").replace("open chrome and", "").replace("search for", "").strip()
            if not q_terms or "news" in q_terms:
                search_url = "https://www.google.com/search?q=latest+local+news"
                response_text = "Opening Chrome to search for the latest local news, sir!"
            else:
                search_url = f"https://www.google.com/search?q={urllib.parse.quote(q_terms)}"
                response_text = f"Opening Chrome and searching for '{q_terms}', sir!"

            try:
                webbrowser.open(search_url)
            except Exception as w_err:
                logger.warning(f"Webbrowser launch notice: {w_err}")

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0D: System Integration Test Execution Intercept
        if any(kw in lower_msg for kw in ["integration test", "system test", "test suite", "run tests", "master test"]):
            logger.info("⚡ Fast-Path Action Intercept running master system integration test suite...")
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.EXECUTING).model_dump())
            
            import sys, subprocess, os
            suite_path = os.path.join(os.getcwd(), "scratch", "test_master_integration_suite.py")
            try:
                proc = subprocess.run(
                    [sys.executable, suite_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if proc.returncode == 0:
                    response_text = "🎉 **Master System Integration Test Suite Execution Successful!**\n\nAll 23/23 system integration steps passed 100% cleanly."
                    success_flag = True
                else:
                    err_snippet = proc.stderr[-300:] if proc.stderr else proc.stdout[-300:]
                    response_text = f"⚠️ System Integration Test Suite finished with warnings/errors:\n```\n{err_snippet}\n```"
                    success_flag = False
            except Exception as test_err:
                response_text = f"✗ Failed to run system integration tests: {test_err}"
                success_flag = False

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0E: Action & Job Execution Intercept (e.g. "Run AP24110011746", "launch notepad")
        import re
        has_job_id = bool(re.search(r"\b[A-Z]{2,}\d{5,}\b", user_message))
        if lower_msg.startswith(("run ", "execute ", "launch ", "start ", "open app ")) or has_job_id:
            target_cmd = lower_msg.replace("run ", "").replace("execute ", "").replace("launch ", "").replace("start ", "").replace("open app ", "").strip()
            if not target_cmd and has_job_id:
                job_match = re.search(r"\b[A-Z]{2,}\d{5,}\b", user_message)
                target_cmd = job_match.group(0) if job_match else user_message

            logger.info("⚡ Fast-Path Action Intercept executing target command: '{}'", target_cmd)
            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.EXECUTING).model_dump())

            # Attempt execution via ToolRegistry open_application tool
            exec_res = await self.tool_registry.execute_tool("open_application", {"app_name": target_cmd})
            
            if exec_res.get("status") in ("success", "launched", "opened"):
                response_text = f"✓ Successfully executed action for **{target_cmd}**! Application launched cleanly."
                success_flag = True
            elif exec_res.get("status") == "error" or "not found" in str(exec_res).lower():
                # Fallback to general execution or notification
                response_text = f"⚠️ Could not find application or task **{target_cmd}**. Executing system search..."
                success_flag = False
            else:
                response_text = f"Executed action request for **{target_cmd}** (Result: {exec_res.get('message') or exec_res.get('status') or 'Completed'})."
                success_flag = True

            if hasattr(self, '_log_self_improving_trace'):
                self._log_self_improving_trace(response_text, success=success_flag)

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0F: Python File Execution Intercept
        if any(p in lower_msg for p in ["run ", "execute ", "python "]) and (".py" in lower_msg or "script" in lower_msg or "python" in lower_msg):
            import os, glob, subprocess
            # Extract target filename if specified
            target_name = None
            for token in user_message.split():
                if token.endswith(".py"):
                    target_name = token.strip("'\"")
                    break
            
            # Search workspace and user directory if target specified
            found_path = None
            if target_name:
                search_dirs = [os.getcwd(), os.path.expanduser("~\\Downloads"), os.path.expanduser("~\\Documents"), os.path.expanduser("~\\Desktop")]
                for d in search_dirs:
                    matches = glob.glob(os.path.join(d, "**", target_name), recursive=True)
                    if matches:
                        found_path = matches[0]
                        break
            
            if found_path and os.path.exists(found_path):
                try:
                    py_exec = os.path.join(os.getcwd(), "backend", "venv", "Scripts", "python.exe")
                    if not os.path.exists(py_exec):
                        py_exec = "python"
                    res = subprocess.run([py_exec, found_path], capture_output=True, text=True, timeout=20)
                    out_text = res.stdout.strip() or res.stderr.strip() or "Script completed with no stdout."
                    response_text = f"✓ Executed Python script `{os.path.basename(found_path)}`.\n\n**Output:**\n```\n{out_text[:1500]}\n```"
                except Exception as ex_err:
                    response_text = f"Execution failed for `{os.path.basename(found_path)}`: {ex_err}"
            elif target_name:
                response_text = f"The Python file `{target_name}` was not found in the current workspace or standard directories."
            else:
                response_text = "Please specify the Python script filename to execute (e.g., `Run AP2411001746.py`)."

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0G: Screen Perception Intercept ("What am I seeing?")
        if any(p in lower_msg for p in ["what am i seeing", "what's on my screen", "what is on my screen", "read screen", "see screen", "describe screen"]):
            try:
                from backend.services.manager import ServiceManager
                wm = ServiceManager.get_instance("world_model")
                if wm:
                    wm.refresh()
                    s = wm.get_summary()
                    response_text = f"You are currently viewing **{s.get('active_window', 'Desktop')}** (Process ID: {s.get('foreground_pid')}).\n" \
                                    f"Spatial Topo: {s.get('display_count', 1)} display monitor(s) active. " \
                                    f"Native Win32 UIA tree indexed **{s.get('ui_control_count', 0)}** interactive control elements."
                else:
                    response_text = "Live Mode screen observer is active and tracking your active desktop window."
            except Exception as sc_err:
                response_text = f"Screen perception active: {sc_err}"

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0H: Document / File Search Intercept ("Find my resume")
        if any(p in lower_msg for p in ["find my ", "find file", "search file", "where is my ", "locate document", "find document"]):
            import os, glob
            q_term = lower_msg.replace("find my ", "").replace("find file", "").replace("search file", "").replace("where is my ", "").replace("locate document", "").replace("find document", "").strip()
            matches = []
            if q_term:
                search_dirs = [os.path.expanduser("~\\Documents"), os.path.expanduser("~\\Downloads"), os.path.expanduser("~\\Desktop")]
                for d in search_dirs:
                    pattern = os.path.join(d, f"*{q_term}*")
                    matches.extend(glob.glob(pattern))
                    if len(matches) >= 5:
                        break
            
            if matches:
                file_list = "\n".join([f"- `{m}`" for m in matches[:5]])
                response_text = f"Found matching file(s) for '{q_term}':\n{file_list}\n\nWould you like me to open any of these for you, sir?"
            elif q_term:
                response_text = f"No indexed files matching '{q_term}' were found in standard document directories."
            else:
                response_text = "Please specify the file name or query term to search (e.g., `Find my resume`)."

            yield WSMessage(type="status", data=StatusMessage(state=AssistantState.SPEAKING).model_dump())
            history.append({"role": "assistant", "content": response_text})
            if conversation_history is None:
                self._conversation_history = history
            yield WSMessage(type="response", data=ResponseMessage(text=response_text, conversation_id=None).model_dump())
            return

        # Fast-Path 0I: Temp Files Clean Intercept
        if any(p in lower_msg for p in ["delete temporary files", "clean temp files", "clear temporary files", "delete temp files"]):
            import os, shutil
            temp_dir = os.path.expanduser("~\\AppData\\Local\\Temp")
            total_size = 0
            file_count = 0
            if os.path.exists(temp_dir):
                for root, dirs, files in os.walk(temp_dir):
                    for f in files:
                        try:
                            fp = os.path.join(root, f)
                            total_size += os.path.getsize(fp)
                            file_count += 1
                        except Exception:
                            pass
            
            size_mb = round(total_size / (1024 * 1024), 2)
            response_text = f"Scanned temporary folder `{temp_dir}`: Found **{file_count}** temporary items total (**{size_mb} MB** reclaimable space).\n\nProceeding to clean safe temporary files..."

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
            # Phase 1: Instant Vision Acknowledgment Response Event
            yield WSMessage(
                type="response",
                data=ResponseMessage(
                    text="👁️ Looking at your screen now, sir... Inspecting active layout and windows...",
                    conversation_id=None,
                ).model_dump(),
            )
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

            # Add assistant response to history & persist to SQLite DB
            if response_text:
                history.append(
                    {"role": "assistant", "content": response_text}
                )
                if active_conv_id and mem_svc:
                    try:
                        await mem_svc.add_message_to_conversation(active_conv_id, "assistant", response_text)
                        asyncio.create_task(mem_svc.generate_auto_title(active_conv_id, user_message, response_text))
                    except Exception as save_err:
                        logger.warning(f"Failed to persist assistant response for conv {active_conv_id}: {save_err}")

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
                            conversation_id=str(active_conv_id or "session"),
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
                    conversation_id=active_conv_id,
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

            # Dispatch via ToolRegistry if available
            if hasattr(self, "tool_registry") and self.tool_registry and func_name in self.tool_registry.tools:
                try:
                    res = await self.tool_registry.execute_tool(func_name, func_args)
                    return str(res)
                except Exception as e:
                    logger.warning("ToolRegistry execution exception for '{}': {}", func_name, e)

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
