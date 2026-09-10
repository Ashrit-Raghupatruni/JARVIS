"""
Central LLM Manager Service for JARVIS.
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
from backend.services.llm.prompts import (
    JARVIS_SYSTEM_PROMPT,
    TOOL_DEFINITIONS,
    extract_clean_user_request,
)
from backend.services.llm.streaming import StreamTextFilter
from backend.services.llm.tool_calling import (
    try_parse_json_tool_call,
    try_parse_xml_tool_call,
    clean_function_calls_from_text,
    filter_tools_for_query,
    check_and_execute_text_tool_call,
)
from backend.services.llm.multimodal import vision_analysis_impl
from backend.services.llm.structured_output import simple_completion_impl
from backend.services.llm.providers import (
    OllamaProvider,
    GeminiProvider,
    OpenAIProvider,
    OpenRouterProvider,
    GroqProvider,
    NvidiaProvider,
)

# Prash custom AI engine (lazy import to handle missing torch gracefully)
try:
    from backend.prash.engine import PrashEngine
    PRASH_AVAILABLE = True
except ImportError:
    PRASH_AVAILABLE = False
    PrashEngine = None


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

    def _filter_tools_for_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Builds and merges the complete set of tool definitions from ToolRegistry,
        SkillsRegistry, and core TOOL_DEFINITIONS. Guarantees that tool schemas are
        available for LLM function calling without hardcoded keyword suppression.
        """
        raw_tools = []
        # Pull tools from ToolRegistry singleton
        try:
            from backend.services.manager import ServiceManager
            tr = ServiceManager.get_instance("tool_registry")
            if not tr:
                from backend.services.tool_registry import ToolRegistry
                tr = ToolRegistry()
            raw_tools.extend(tr.get_tools_schema())
        except Exception as tr_err:
            logger.debug("ToolRegistry schema load notice: {}", tr_err)

        if hasattr(self, "skills_registry") and self.skills_registry:
            try:
                raw_tools.extend(self.skills_registry.get_all_tool_definitions())
            except Exception as sk_err:
                logger.debug("SkillsRegistry schema load notice: {}", sk_err)
        
        raw_tools.extend(TOOL_DEFINITIONS)

        seen = set()
        merged = []
        for t in raw_tools:
            if isinstance(t, dict) and "function" in t and isinstance(t["function"], dict):
                name = t["function"].get("name")
                if name and name not in seen:
                    seen.add(name)
                    merged.append(t)

        if len(merged) > 20:
            core_priority = {
                "search_files", "read_file", "write_file", "create_file",
                "open_application", "click_element_by_name", "set_control_value", "type_text",
                "get_process_info", "list_running_processes", "web_search",
                "smart_file_search", "copy_file", "take_screenshot"
            }
            q_words = set(query.lower().split()) if query else set()

            def _score_tool(tool_item):
                fn = tool_item.get("function", {})
                t_name = fn.get("name", "").lower()
                t_desc = fn.get("description", "").lower()
                score = 0
                if t_name in core_priority:
                    score += 15
                for w in q_words:
                    if len(w) > 2:
                        if w in t_name:
                            score += 10
                        if w in t_desc:
                            score += 5
                return score

            merged.sort(key=_score_tool, reverse=True)
            merged = merged[:20]

        return merged

    def get_tools(self, query: str = "") -> List[Dict[str, Any]]:
        """Retrieve merged tool definitions from ToolRegistry, SkillsRegistry, and core tools."""
        return self._filter_tools_for_query(query)

    # ── Public APIs ───────────────────────────────────────────────────────


    async def process_message(
        self,
        messages: List[Dict[str, Any]],
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        user_message = messages[-1]["content"] if messages else ""
        history = messages[:-1] if len(messages) > 1 else []
        async for event in self.generate_response(user_message, history, tool_executor):
            yield event

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

        # ── Active KV-Cache Context Pruning ───────────────────────────
        if conversation_history:
            try:
                from backend.utils.service_manager import ServiceManager
                pruner = ServiceManager.get_sync("kv_pruner")
                if pruner and hasattr(pruner, "evaluate_and_prune"):
                    pruned_res = pruner.evaluate_and_prune(conversation_history)
                    if pruned_res.get("pruned"):
                        conversation_history = pruned_res.get("pruned_messages", conversation_history)
            except Exception:
                pass

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

                    # Generate response with 4.0s CPU fail-safe timeout
                    try:
                        response_text, is_confident, metadata = await asyncio.wait_for(
                            self.prash_engine.generate(
                                prompt=prompt_text,
                                conversation_history=prash_history,
                                max_tokens=min(128, self.prash_max_tokens),
                                temperature=self.prash_temperature,
                            ),
                            timeout=4.0
                        )
                    except (asyncio.TimeoutError, TimeoutError):
                        logger.warning("PrashEngine CPU inference exceeded 4.0s. Falling back to active local/cloud LLM cascade.")
                        response_text, is_confident, metadata = "", False, {"entropy": 999.0}

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
        clean_query = extract_clean_user_request(user_message)
        logger.warning(f"All primary LLM providers failed. Attempting web research fallback for query: '{clean_query[:60]}'")
        
        # Guard: Never search the public web for personal identity, location, or hardware status
        skip_web_topics = [
            "where am i", "my location", "current location", "who am i",
            "my name", "my skills", "battery", "my screen", "tools you have",
            "what tools", "my preferences", "resume"
        ]
        should_skip_web = any(topic in clean_query.lower() for topic in skip_web_topics)
        
        if clean_query and not should_skip_web:
            try:
                from backend.services.browser import BrowserService
                b_service = BrowserService()
                web_results = await b_service.search_web(clean_query)
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
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> str:
        return await simple_completion_impl(
            service=self,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def vision_analysis(
        self,
        image_base64: str,
        prompt: str = "Describe what you see on the screen and identify key UI elements.",
    ) -> str:
        return await vision_analysis_impl(
            service=self,
            image_base64=image_base64,
            prompt=prompt,
        )

    async def _check_and_execute_text_tool_call(
        self,
        full_text: str,
        tool_executor: Any,
        messages: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        valid_tool_names = {t["function"]["name"] for t in self.get_tools()}
        return await check_and_execute_text_tool_call(
            full_text=full_text,
            tool_executor=tool_executor,
            messages=messages,
            valid_tool_names=valid_tool_names,
        )

    async def _process_message_ollama(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        provider = OllamaProvider(self)
        async for event in provider.process_message(user_message, conversation_history, tool_executor):
            yield event

    async def _process_message_gemini(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        provider = GeminiProvider(self)
        async for event in provider.process_message(user_message, conversation_history, tool_executor):
            yield event

    async def _process_message_openai(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        provider = OpenAIProvider(self)
        async for event in provider.process_message(user_message, conversation_history, tool_executor):
            yield event

    async def _process_message_openrouter(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        provider = OpenRouterProvider(self)
        async for event in provider.process_message(user_message, conversation_history, tool_executor):
            yield event

    async def _process_message_groq(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        provider = GroqProvider(self)
        async for event in provider.process_message(user_message, conversation_history, tool_executor):
            yield event

    async def _process_message_nvidia(
        self,
        user_message: Any,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Any = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        provider = NvidiaProvider(self)
        async for event in provider.process_message(user_message, conversation_history, tool_executor):
            yield event

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
