"""
Planner agent for JARVIS — Central Orchestrator.
"""
import asyncio
import json
import random
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
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
from backend.agents.planner.execution_plan import ExecutionPlanTracker
from backend.agents.planner.plan_validator import PlanValidator
from backend.agents.planner.task_decomposer import TaskDecomposer
from backend.services.llm import clean_function_calls_from_text

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
        llm_service=None,
        automation_service=None,
        screen_service=None,
        browser_service=None,
        memory_service=None,
        safety_service=None,
        vision_service=None,
        desktop_automation_service=None,
        developer_assistant_service=None,
        research_service=None,
        voice_intelligence_service=None,
        productivity_service=None,
    ):
        from backend.services.manager import ServiceManager
        self.llm = llm_service or ServiceManager.get_instance("llm_service")
        if not self.llm:
            try:
                from backend.services.llm import LLMService
                self.llm = LLMService()
                ServiceManager.register_instance("llm_service", self.llm)
            except Exception as llm_init_err:
                logger.warning(f"Could not auto-initialize LLMService fallback: {llm_init_err}")
        self.automation = automation_service or ServiceManager.get_instance("automation_service")
        self.screen = screen_service or ServiceManager.get_instance("screen_service")
        self.browser = browser_service or ServiceManager.get_instance("browser_service")
        self.memory = memory_service or ServiceManager.get_instance("memory_service")
        self.safety = safety_service or ServiceManager.get_instance("safety_service")
        self.vision_service = vision_service or ServiceManager.get_instance("vision_service")
        self.desktop_automation_service = desktop_automation_service or ServiceManager.get_instance("desktop_automation_service")
        self.developer_assistant_service = developer_assistant_service or ServiceManager.get_instance("developer_assistant_service")
        self.research_service = research_service or ServiceManager.get_instance("research_service")
        self.voice_intelligence_service = voice_intelligence_service or ServiceManager.get_instance("voice_intelligence_service")
        self.productivity_service = productivity_service or ServiceManager.get_instance("productivity_service")
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

        from backend.services.safety import BLOCKED_COMMAND_PATTERNS, DANGEROUS_COMMAND_PATTERNS
        for pat in BLOCKED_COMMAND_PATTERNS + DANGEROUS_COMMAND_PATTERNS:
            if re.search(pat, user_message, re.IGNORECASE):
                logger.warning("⛔ Dangerous command intercepted by SafetyGatekeeper: '{}'", user_message)
                yield WSMessage(
                    type="approval_required",
                    data={
                        "status": "pending_approval",
                        "action": "system_command",
                        "reason": f"Safety Policy Required: Command matches guarded pattern ('{pat}')",
                        "risk_level": "destructive"
                    }
                )
                _log_self_improving_trace(f"Blocked by safety policy: {pat}", success=False)
                return

        # ── HYBRID FAST-PATH EXECUTION GATE ──────────────────────────────
        from backend.services.fast_intent_router import fast_intent_router
        fast_intent = fast_intent_router.classify(user_message)
        
        if fast_intent.is_atomic and fast_intent.confidence >= 0.95 and fast_intent.tool_name:
            logger.info("⚡ FastIntentRouter match: tool='{}' (confidence={:.2f}, router_time={:.2f}ms)", 
                        fast_intent.tool_name, fast_intent.confidence, fast_intent.routing_time_ms)
            
            # Phase 1: Immediate Acknowledgment (Streamed in < 25ms)
            if fast_intent.ack_phrase:
                yield WSMessage(type="chat_response", data={"status": "executing", "text": fast_intent.ack_phrase})
            
            # Phase 2: Safety Gatekeeper Evaluation (Inviolable Gate)
            target_win = ""
            if hasattr(self, "world_model") and self.world_model and hasattr(self.world_model, "state"):
                target_win = getattr(self.world_model.state, "window_title", "") or ""
            
            safety_decision = gatekeeper.evaluate_tool_call(
                tool_name=fast_intent.tool_name,
                arguments=fast_intent.tool_params
            )
            
            if safety_decision.requires_user_approval or not safety_decision.allowed:
                logger.warning("⛔ Fast path tool '{}' halted by Safety Gatekeeper: {}", fast_intent.tool_name, safety_decision.reason)
                yield WSMessage(
                    type="approval_required",
                    data={
                        "status": "pending_approval",
                        "action": fast_intent.tool_name,
                        "reason": safety_decision.reason,
                        "risk_level": safety_decision.risk_level.value
                    }
                )
                _log_self_improving_trace(f"Blocked by safety gate: {safety_decision.reason}", success=False)
                return

            # Phase 3: ToolRegistry Direct Execution
            try:
                tool_reg = getattr(self, "tool_registry", None)
                if not tool_reg:
                    from backend.services.tool_registry import ToolRegistry
                    tool_reg = ToolRegistry()
                    self.tool_registry = tool_reg
                
                exec_res = await tool_reg.execute_tool(fast_intent.tool_name, safety_decision.validated_args or fast_intent.tool_params)
                
                # Phase 4: ActionExecutionVerifier Verification
                from backend.services.action_verifier import ActionExecutionVerifier
                verifier = ActionExecutionVerifier()
                is_verified = True
                verification_note = "Verified execution"
                
                if fast_intent.tool_name == "open_application":
                    app_target = (safety_decision.validated_args or fast_intent.tool_params).get("app_name", "")
                    is_verified, verification_note = verifier.verify_application_launched(app_target)
                elif exec_res.get("status") != "success":
                    is_verified = False
                    verification_note = exec_res.get("error", "Execution returned error status")

                if is_verified:
                    # Phase 5: Verified Response & Strategy Reward
                    from backend.services.manager import ServiceManager
                    strat_mem = ServiceManager.get_instance("strategy_memory")
                    if strat_mem and hasattr(strat_mem, "record_task_strategy_outcome"):
                        strat_mem.record_task_strategy_outcome(task=user_message, strategy="fast_path_direct_execution", success=True)
                    
                    completion_text = fast_intent.completion_phrase
                    if not completion_text:
                        res_val = exec_res.get("result")
                        if isinstance(res_val, dict) and "summary" in res_val:
                            completion_text = res_val["summary"]
                        elif isinstance(res_val, str):
                            completion_text = res_val
                        else:
                            completion_text = str(res_val or "Action completed successfully.")
                    
                    history.append({"role": "assistant", "content": completion_text})
                    self._conversation_history = list(history[-self._max_history:])
                    if active_conv_id and mem_svc:
                        try:
                            await mem_svc.add_message_to_conversation(active_conv_id, "assistant", completion_text)
                        except Exception as m_err:
                            logger.debug("Failed to persist assistant msg: {}", m_err)
                    
                    yield WSMessage(type="chat_response", data={"status": "completed", "text": completion_text})
                    _log_self_improving_trace(completion_text, success=True)
                    return
                else:
                    logger.warning("Fast path execution for '{}' unverified ({}). Falling back to PlannerAgent...", fast_intent.tool_name, verification_note)
            except Exception as fast_err:
                logger.error("Fast path execution error for '{}': {}. Falling back to PlannerAgent...", fast_intent.tool_name, fast_err)

        # ── CONFIDENCE-BASED PRASH NEURAL REASONING GATE ───────────────────
        try:
            from backend.services.manager import ServiceManager
            prash_eng = ServiceManager.get_instance("prash_engine")
            if not prash_eng and hasattr(self, "prash_engine"):
                prash_eng = self.prash_engine
            if not prash_eng:
                from backend.prash.engine import PrashEngine
                prash_eng = PrashEngine()
                asyncio.create_task(prash_eng.init())
                ServiceManager.register_instance("prash_engine", prash_eng)
                self.prash_engine = prash_eng

            if prash_eng and getattr(prash_eng, "is_available", False):
                # Issue 3: Construct unified context payload (World Model + User Memory)
                context_prefix = ""
                try:
                    wm_inst = ServiceManager.get_instance("world_model")
                    if wm_inst:
                        ws = wm_inst.get_summary()
                        context_prefix += f"[Desktop: App={ws.get('active_app', 'Desktop')}, Window={ws.get('active_window', 'Desktop')}] "
                except Exception:
                    pass
                try:
                    mem_svc = ServiceManager.get_instance("memory_service")
                    if mem_svc and hasattr(mem_svc, "get_user_preference"):
                        u_name = await mem_svc.get_user_preference("user_name")
                        if u_name:
                            context_prefix += f"[User: {u_name}] "
                except Exception:
                    pass

                augmented_prompt = f"{context_prefix}{user_message}" if context_prefix else user_message
                prash_resp, is_confident, meta = await prash_eng.generate(augmented_prompt, max_tokens=128, temperature=0.1)
                entropy = meta.get("entropy", 999.0) if isinstance(meta, dict) else 999.0

                # Check confidence threshold (mean Shannon entropy <= 1.05 and validate_response passed)
                if is_confident and entropy <= 1.05:
                    from backend.services.prash_tool_validator import prash_tool_validator
                    val_res = prash_tool_validator.validate_raw_response(prash_resp, user_message)

                    if val_res.is_valid and val_res.tool_name:
                        logger.info("🧠 Prash High-Confidence Tool Match: '{}' (entropy={:.3f}, params={})",
                                    val_res.tool_name, entropy, val_res.parameters)

                        # Phase 1: Safety Gatekeeper Evaluation (Inviolable Gate)
                        safety_decision = gatekeeper.evaluate_tool_call(
                            tool_name=val_res.tool_name,
                            arguments=val_res.parameters
                        )

                        if safety_decision.requires_user_approval or not safety_decision.allowed:
                            logger.warning("⛔ Prash proposed tool '{}' halted by Safety Gatekeeper: {}", val_res.tool_name, safety_decision.reason)
                            yield WSMessage(
                                type="approval_required",
                                data={
                                    "status": "pending_approval",
                                    "action": val_res.tool_name,
                                    "reason": safety_decision.reason,
                                    "risk_level": safety_decision.risk_level.value
                                }
                            )
                            _log_self_improving_trace(f"Blocked by safety gate: {safety_decision.reason}", success=False)
                            return

                        # Phase 2: ToolRegistry Execution
                        tool_reg = getattr(self, "tool_registry", None)
                        if not tool_reg:
                            from backend.services.tool_registry import ToolRegistry
                            tool_reg = ToolRegistry()
                            self.tool_registry = tool_reg

                        exec_res = await tool_reg.execute_tool(val_res.tool_name, safety_decision.validated_args or val_res.parameters)

                        # Phase 3: ActionExecutionVerifier Verification
                        from backend.services.action_verifier import ActionExecutionVerifier
                        verifier = ActionExecutionVerifier()
                        is_verified = True
                        verification_note = "Verified execution"

                        if val_res.tool_name == "open_application":
                            app_target = (safety_decision.validated_args or val_res.parameters).get("app_name", "")
                            is_verified, verification_note = verifier.verify_application_launched(app_target)
                        elif exec_res.get("status") != "success":
                            is_verified = False
                            verification_note = exec_res.get("error", "Execution returned error status")

                        if is_verified:
                            # Record successful strategy outcome
                            strat_mem = ServiceManager.get_instance("strategy_memory")
                            if strat_mem and hasattr(strat_mem, "record_task_strategy_outcome"):
                                strat_mem.record_task_strategy_outcome(task=user_message, strategy="prash_neural_execution", success=True)

                            # Build completion response
                            res_val = exec_res.get("result")
                            if isinstance(res_val, dict) and "summary" in res_val:
                                completion_text = res_val["summary"]
                            elif isinstance(res_val, str):
                                completion_text = res_val
                            else:
                                completion_text = f"Action '{val_res.tool_name}' executed and verified successfully."

                            history.append({"role": "assistant", "content": completion_text})
                            self._conversation_history = list(history[-self._max_history:])
                            if active_conv_id and mem_svc:
                                try:
                                    await mem_svc.add_message_to_conversation(active_conv_id, "assistant", completion_text)
                                except Exception as m_err:
                                    logger.debug("Failed to persist assistant msg: {}", m_err)

                            yield WSMessage(type="chat_response", data={"status": "completed", "text": completion_text})
                            _log_self_improving_trace(completion_text, success=True)
                            return
                        else:
                            logger.warning("Prash tool execution for '{}' unverified ({}). Falling back to PlannerAgent...", val_res.tool_name, verification_note)
                    elif val_res.is_valid and val_res.is_conversational and val_res.conversational_text:
                        if hier_category in (HierarchicalCategory.CONVERSATIONAL, HierarchicalCategory.KNOWLEDGE) and entropy < 0.75:
                            completion_text = val_res.conversational_text
                            history.append({"role": "assistant", "content": completion_text})
                            self._conversation_history = list(history[-self._max_history:])
                            if active_conv_id and mem_svc:
                                try:
                                    await mem_svc.add_message_to_conversation(active_conv_id, "assistant", completion_text)
                                except Exception as m_err:
                                    logger.debug("Failed to persist assistant msg: {}", m_err)
                            yield WSMessage(type="chat_response", data={"status": "completed", "text": completion_text})
                            _log_self_improving_trace(completion_text, success=True)
                            return
                    else:
                        logger.info("Prash validation rejection: {}. Safely falling back to PlannerAgent...", val_res.rejection_reason)
                else:
                    logger.debug("Prash confidence check unfulfilled (entropy={:.3f}, confident={}). Falling back to PlannerAgent...", entropy, is_confident)
        except Exception as prash_gate_err:
            logger.debug("Prash reasoning gate notice: {}. Continuing to standard PlannerAgent...", prash_gate_err)

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

        # Response-Length & Conciseness Discipline
        wants_detailed = any(w in user_message.lower() for w in ["detailed", "explain in depth", "comprehensive", "deep dive", "elaborate", "step by step", "full tutorial", "thorough"])
        if not wants_detailed:
            category_sys_prompt += " [RESPONSE DISCIPLINE]: Default to concise, direct, high-signal output (1-3 sentences or focused bullets). Omit conversational filler. Only provide extensive details when explicitly requested."
        else:
            category_sys_prompt += " [RESPONSE DISCIPLINE]: Detailed mode active. Provide thorough, structured, comprehensive explanation."

        # Branch on RequestCategory / Live Mode
        # Prepare transient router context for this turn (do not mutate persistent history)
        current_router_context = category_sys_prompt
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
                
                current_router_context = f"[LIVE MODE PERCEPTION CONTEXT]: Foreground Window='{summary.get('active_window')}', Indexed Controls=[{ctrl_str}]. You MUST call `click_element_by_name` or `set_control_value` tool functions to interact with visible elements on screen. {category_sys_prompt}"
            except Exception as e:
                logger.error("Live Mode context setup notice: {}", e)
        elif request_cat == RequestCategory.KNOWLEDGE_REQUEST or hier_category == HierarchicalCategory.KNOWLEDGE:
            logger.info("Executing Knowledge Retrieval Workflow for prompt: '{}'", user_message[:50])
        elif request_cat == RequestCategory.ACTION_REQUEST or hier_category == HierarchicalCategory.ACTION:
            logger.info("Executing Desktop Action Workflow for prompt: '{}'", user_message[:50])
        else:
            logger.info("Executing Conversational Workflow for prompt: '{}'", user_message[:50])

        lower_msg = user_message.lower().strip()



        # ── FAST-PATH DECOMPOSER DISPATCH ─────────────────────────────
        handled = False
        async for msg in TaskDecomposer.try_fast_path_intercept(
            planner=self,
            user_message=user_message,
            lower_msg=lower_msg,
            history=history,
            conversation_history=conversation_history,
            active_conv_id=active_conv_id,
            mem_svc=mem_svc,
            gatekeeper=gatekeeper,
            _log_self_improving_trace=_log_self_improving_trace,
        ):
            yield msg
            handled = True
        if handled:
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
        # Guarantee router intent context is added exactly once and never duplicated
        clean_history = [
            m for m in history 
            if not (isinstance(m, dict) and m.get("role") == "system" and (
                "[ROUTER INTENT CONTEXT]" in str(m.get("content", "")) or 
                "[LIVE MODE PERCEPTION CONTEXT]" in str(m.get("content", ""))
            ))
        ]
        messages_for_llm = list(clean_history)
        if current_router_context:
            messages_for_llm.insert(0, {"role": "system", "content": current_router_context})

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
                        
                        # Update status in steps list with genuine outcome verification
                        for s in steps_list:
                            if s.id == tool_call_id:
                                is_err = "status': 'error'" in str(result).lower() or '"status": "error"' in str(result).lower() or "action blocked" in str(result).lower()
                                s.status = AgentStepStatus.FAILED if is_err else AgentStepStatus.COMPLETED
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
                    conversation_id=str(active_conv_id) if active_conv_id is not None else None,
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

            # Out-of-Model SafetyGatekeeper Evaluation (Inviolable Policy Check)
            from backend.services.safety_gatekeeper import SafetyGatekeeper
            gatekeeper = SafetyGatekeeper()
            safety_decision = gatekeeper.evaluate_tool_call(tool_name=func_name, arguments=func_args)
            if safety_decision.requires_user_approval or not safety_decision.allowed:
                logger.warning("⛔ Tool execution halted by Safety Gatekeeper: {}", safety_decision.reason)
                return f"Action blocked by Safety Gatekeeper: {safety_decision.reason}"

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
                    # Closed-loop continuous learning: update StrategyMemoryService
                    try:
                        from backend.services.manager import ServiceManager
                        strat_mem = ServiceManager.get_instance("strategy_memory")
                        if strat_mem and hasattr(strat_mem, "record_task_strategy_outcome"):
                            is_success = res.get("status") == "success" if isinstance(res, dict) else ("error" not in str(res).lower() and "failed" not in str(res).lower())
                            strat_mem.record_task_strategy_outcome(func_name, func_name, is_success)
                    except Exception:
                        pass

                    # Autonomous recovery: if UI action failed, re-observe environment
                    if isinstance(res, dict) and res.get("status") == "error" and func_name in ("click_element_by_name", "set_control_value"):
                        logger.info("Autonomous UI Action Recovery: tool '{}' returned error. Refreshing WorldModel state...", func_name)
                        try:
                            from backend.services.manager import ServiceManager
                            wm = ServiceManager.get_instance("world_model")
                            if wm and hasattr(wm, "refresh"):
                                wm.refresh()
                        except Exception:
                            pass

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
