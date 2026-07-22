"""
JARVIS AI Desktop Assistant — FastAPI Backend Entry Point.

Initializes all services, configures the API, and starts the server.
"""

import os
import sys
import time
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

# Force huggingface hub and transformers to run offline to prevent connection pool hangs
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from fastapi import FastAPI
from loguru import logger

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings
from backend.utils.logger import setup_logger
from backend.utils.event_bus import EventBus
from backend.agents.context_manager import SharedContextManager
from backend.utils.task_queue import AsyncTaskQueue
from backend.services.config_manager import ConfigurationManager
from backend.services.manager import ServiceManager
from backend.models.schemas import AssistantState, WSMessage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize and cleanup services."""
    settings = get_settings()
    setup_logger()
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("  JARVIS AI Desktop Assistant — Starting Up")
    logger.info("=" * 60)

    # ── Initialize Event Bus, Context, Task Queue, Config Manager ───────
    event_bus = EventBus()
    from backend.utils.logger import register_event_bus_sink
    register_event_bus_sink(event_bus)
    context_manager = SharedContextManager(event_bus)
    task_queue = AsyncTaskQueue(event_bus)
    task_queue.start()
    config_manager = ConfigurationManager(event_bus)
    
    app.state.event_bus = event_bus
    app.state.context_manager = context_manager
    app.state.task_queue = task_queue
    app.state.config_manager = config_manager
    app.state.service_manager = ServiceManager

    # ── Initialize Security Components ────────────────────────────────────
    from backend.services.security.vault import CredentialVault
    from backend.services.security.sandbox import SecuritySandbox
    from backend.services.security.rbac import SecurityOrchestrator
    
    credential_vault = CredentialVault()
    security_sandbox = SecuritySandbox()
    security_orchestrator = SecurityOrchestrator(event_bus)
    
    app.state.credential_vault = credential_vault
    app.state.security_sandbox = security_sandbox
    app.state.security_orchestrator = security_orchestrator
    
    ServiceManager.register_instance("credential_vault", credential_vault)
    ServiceManager.register_instance("security_sandbox", security_sandbox)
    ServiceManager.register_instance("security_orchestrator", security_orchestrator)

    # ── Initialize MCP Client Manager ──────────────────────────────────────
    from backend.mcp.client import MCPClientManager
    mcp_client_manager = MCPClientManager()
    
    # Register the local stdin/stdout File MCP Server
    import sys
    python_bin = sys.executable or "python"
    file_server_path = str(Path(__file__).parent / "mcp" / "servers" / "file_server.py")
    
    async def start_mcp_servers():
        await asyncio.sleep(0.5) # Let system settle
        await mcp_client_manager.register_and_start_server(
            "file_server", 
            [python_bin, file_server_path]
        )
    asyncio.create_task(start_mcp_servers())
    
    app.state.mcp_client_manager = mcp_client_manager
    ServiceManager.register_instance("mcp_client_manager", mcp_client_manager)

    # ── Initialize Multi-Agent Orchestrator ─────────────────────────────────
    from backend.agents.multi_agent.orchestrator import HierarchicalOrchestrator
    orchestrator = HierarchicalOrchestrator(event_bus, ServiceManager)
    
    app.state.orchestrator = orchestrator
    ServiceManager.register_instance("orchestrator", orchestrator)

    # ── Initialize Hybrid Memory System ─────────────────────────────────────
    from backend.services.hybrid_memory_system import HybridMemorySystem
    hybrid_memory = HybridMemorySystem()
    
    app.state.hybrid_memory = hybrid_memory
    ServiceManager.register_instance("hybrid_memory", hybrid_memory)

    app.loop = asyncio.get_running_loop()

    # Safety Service (no external deps, always available)
    from backend.services.safety import SafetyService
    safety_service = SafetyService()
    app.state.safety_service = safety_service
    ServiceManager.register_instance("safety_service", safety_service)
    logger.info("✓ Safety service initialized")

    # LLM Service
    llm_service = None
    try:
        from backend.services.llm import LLMService
        llm_service = LLMService()
        app.state.llm_service = llm_service
        ServiceManager.register_instance("llm_service", llm_service)
        # Log active provider and model
        provider = settings.LLM_PROVIDER or "gemini"
        if provider == "ollama":
            active_model = settings.OLLAMA_MODEL
        elif provider == "gemini":
            active_model = settings.GEMINI_MODEL
        elif provider == "groq":
            active_model = settings.GROQ_MODEL
        elif provider == "openrouter":
            active_model = settings.OPENROUTER_MODEL
        elif provider == "nvidia":
            active_model = settings.NIM_MODEL
        else:
            active_model = settings.OPENAI_MODEL
        logger.info(f"✓ LLM service initialized (provider: {provider}, model: {active_model})")
        # Initialize Router
        if llm_service and hasattr(llm_service, "router") and llm_service.router:
            try:
                await llm_service.router.init()
                app.state.llm_router = llm_service.router
                logger.info("✓ Dynamic LLM Router initialized and registered in App state")
            except Exception as e:
                logger.error(f"✗ LLM Router failed to start: {e}")
    except Exception as e:
        logger.error(f"✗ LLM service failed: {e}")
        app.state.llm_service = None

    # Speech-to-Text Service
    stt_service = None
    try:
        from backend.services.stt import STTService
        stt_service = STTService()
        app.state.stt_service = stt_service
        ServiceManager.register_instance("stt_service", stt_service)
        app.state.stt_model_name = settings.WHISPER_MODEL
        logger.info(f"✓ STT service initialized (model: {settings.WHISPER_MODEL})")
    except Exception as e:
        logger.error(f"✗ STT service failed: {e}")
        app.state.stt_service = None

    # Text-to-Speech Service
    tts_service = None
    try:
        from backend.services.tts import TTSService
        tts_service = TTSService()
        app.state.tts_service = tts_service
        ServiceManager.register_instance("tts_service", tts_service)
        logger.info(f"✓ TTS service initialized (voice: {settings.TTS_VOICE})")
    except Exception as e:
        logger.error(f"✗ TTS service failed: {e}")
        app.state.tts_service = None

    # Wake Word Service
    wake_word_service = None
    try:
        from backend.services.wake_word import WakeWordService
        wake_word_service = WakeWordService()
        asyncio.create_task(wake_word_service.load_model())
        app.state.wake_word_service = wake_word_service
        ServiceManager.register_instance("wake_word_service", wake_word_service)
        logger.info("✓ Wake word service initialized (model loading in background)")
    except Exception as e:
        logger.warning(f"✗ Wake word service unavailable: {e}")
        app.state.wake_word_service = None

    # Clap Service
    clap_service = None
    try:
        from backend.services.clap import ClapService
        clap_service = ClapService()
        clap_service.start()
        app.state.clap_service = clap_service
        ServiceManager.register_instance("clap_service", clap_service)
        logger.info("✓ Clap service initialized and listening")
    except Exception as e:
        logger.error(f"✗ Clap service failed: {e}")
        app.state.clap_service = None

    # Automation Service
    automation_service = None
    try:
        from backend.services.automation import AutomationService
        automation_service = AutomationService()
        app.state.automation_service = automation_service
        ServiceManager.register_instance("automation_service", automation_service)
        logger.info("✓ Automation service initialized")
    except Exception as e:
        logger.error(f"✗ Automation service failed: {e}")
        app.state.automation_service = None

    # Screen Service
    screen_service = None
    try:
        from backend.services.screen import ScreenService
        screen_service = ScreenService()
        app.state.screen_service = screen_service
        ServiceManager.register_instance("screen_service", screen_service)
        logger.info("✓ Screen service initialized")
    except Exception as e:
        logger.error(f"✗ Screen service failed: {e}")
    # Vision Service (Phase 7)
    vision_service = None
    try:
        from backend.services.vision_service import VisionService
        vision_service = VisionService()
        app.state.vision_service = vision_service
        ServiceManager.register_instance("vision_service", vision_service)
        logger.info("✓ Vision service initialized")
    except Exception as e:
        logger.error(f"✗ Vision service failed: {e}")
        app.state.vision_service = None

    # Desktop Automation Service (Phase 8)
    desktop_automation_service = None
    try:
        from backend.services.desktop_automation import DesktopAutomationService
        desktop_automation_service = DesktopAutomationService()
        app.state.desktop_automation_service = desktop_automation_service
        ServiceManager.register_instance("desktop_automation_service", desktop_automation_service)
        logger.info("✓ Desktop automation service initialized")
    except Exception as e:
        logger.error(f"✗ Desktop automation service failed: {e}")
        app.state.desktop_automation_service = None

    # Developer Assistant Service (Phase 9)
    developer_assistant_service = None
    try:
        from backend.services.developer_assistant import DeveloperAssistantService
        developer_assistant_service = DeveloperAssistantService()
        app.state.developer_assistant_service = developer_assistant_service
        ServiceManager.register_instance("developer_assistant_service", developer_assistant_service)
        logger.info("✓ Developer assistant service initialized")
    except Exception as e:
        logger.error(f"✗ Developer assistant service failed: {e}")
    # Research Agent Service (Phase 10)
    research_service = None
    try:
        from backend.services.research_agent import ResearchAgentService
        research_service = ResearchAgentService()
        app.state.research_service = research_service
        ServiceManager.register_instance("research_service", research_service)
        logger.info("✓ Research agent service initialized")
    except Exception as e:
        logger.error(f"✗ Research agent service failed: {e}")
        app.state.research_service = None

    # Voice Intelligence Service (Phase 11)
    voice_intelligence_service = None
    try:
        from backend.services.voice_intelligence import VoiceIntelligenceService
        voice_intelligence_service = VoiceIntelligenceService()
        app.state.voice_intelligence_service = voice_intelligence_service
        ServiceManager.register_instance("voice_intelligence_service", voice_intelligence_service)
        logger.info("✓ Voice intelligence service initialized")
    except Exception as e:
        logger.error(f"✗ Voice intelligence service failed: {e}")
        app.state.voice_intelligence_service = None

    # Productivity Service (Phase 12)
    productivity_service = None
    try:
        from backend.services.productivity_service import ProductivityService
        productivity_service = ProductivityService()
        app.state.productivity_service = productivity_service
        ServiceManager.register_instance("productivity_service", productivity_service)
        logger.info("✓ Productivity service initialized")
    except Exception as e:
        logger.error(f"✗ Productivity service failed: {e}")
        app.state.productivity_service = None

    # Browser Service
    browser_service = None
    try:
        from backend.services.browser import BrowserService
        browser_service = BrowserService()
        app.state.browser_service = browser_service
        ServiceManager.register_instance("browser_service", browser_service)
        logger.info("✓ Browser service initialized (lazy start)")
    except Exception as e:
        logger.error(f"✗ Browser service failed: {e}")
        app.state.browser_service = None

    # Task Queue Service
    task_queue_service = None
    try:
        from backend.services.task_queue import TaskQueueService
        task_queue_service = TaskQueueService()
        app.state.task_queue_service = task_queue_service
        ServiceManager.register_instance("task_queue_service", task_queue_service)
        logger.info("✓ Task queue service initialized")
    except Exception as e:
        logger.error(f"✗ Task queue service failed: {e}")
        app.state.task_queue_service = None

    # Memory Service
    memory_service = None
    try:
        from backend.services.memory import MemoryService
        memory_service = MemoryService()
        await memory_service.init()
        app.state.memory_service = memory_service
        ServiceManager.register_instance("memory_service", memory_service)
        logger.info("✓ Memory service initialized")
    except Exception as e:
        logger.error(f"✗ Memory service failed: {e}")
        app.state.memory_service = None

    # RAG Service
    rag_service = None
    try:
        from backend.services.rag_service import RAGService
        chroma_client = getattr(memory_service, "_chroma_client", None) if memory_service else None
        rag_service = RAGService(chroma_client=chroma_client)
        app.state.rag_service = rag_service
        ServiceManager.register_instance("rag_service", rag_service)
        logger.info("✓ RAG service initialized")
    except Exception as e:
        logger.error(f"✗ RAG service failed: {e}")
        app.state.rag_service = None

    # ── Initialize Agents ────────────────────────────────────

    # Planner Agent
    planner_agent = None
    if llm_service:
        try:
            from backend.agents.planner import PlannerAgent
            planner_agent = PlannerAgent(
                llm_service=llm_service,
                automation_service=automation_service,
                screen_service=screen_service,
                browser_service=browser_service,
                memory_service=memory_service,
                safety_service=safety_service,
                vision_service=vision_service,
                desktop_automation_service=desktop_automation_service,
                developer_assistant_service=developer_assistant_service,
                research_service=research_service,
                voice_intelligence_service=voice_intelligence_service,
                productivity_service=productivity_service,
            )
            app.state.planner_agent = planner_agent
            app.state.active_subagents = {}
            logger.info("✓ Planner agent initialized")
        except Exception as e:
            logger.error(f"✗ Planner agent failed: {e}")
            app.state.planner_agent = None
    else:
        app.state.planner_agent = None

    # Voice Agent
    voice_agent = None
    try:
        from backend.agents.voice import VoiceAgent
        voice_agent = VoiceAgent(
            wake_word_service=wake_word_service,
            stt_service=stt_service,
            tts_service=tts_service,
            planner_agent=planner_agent,
        )
        app.state.voice_agent = voice_agent
        logger.info("✓ Voice agent initialized")

        # Connect Clap Listener to Voice Agent wake trigger
        if clap_service:
            def handle_clap_wake(clap_mode: str):
                v_agent = getattr(app.state, "voice_agent", None)
                if v_agent:
                    # Ignore clap triggers if assistant is already speaking, processing, executing, or listening
                    if v_agent.state in (AssistantState.SPEAKING, AssistantState.PROCESSING, AssistantState.EXECUTING, AssistantState.LISTENING):
                        logger.info(f"Ignoring clap trigger during active voice state ({v_agent.state.value})")
                        return
                    logger.info(f"Clap trigger activated (mode={clap_mode}) — transitioning voice agent to listening!")
                    v_agent._session_id += 1
                    v_agent.state = AssistantState.LISTENING
                    v_agent._listening_start_time = time.time()
                    v_agent._last_speech_time = time.time()
                    v_agent._has_speech = False
                    v_agent._played_ack = False
                conn_mgr = getattr(app.state, "connection_manager", None)
                if conn_mgr and hasattr(app, "loop") and app.loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        conn_mgr.broadcast(WSMessage(type="status", data={"state": "listening", "message": f"{clap_mode.capitalize()} clap trigger"})),
                        app.loop
                    )
            clap_service.on_clap_detected = handle_clap_wake
    except Exception as e:
        logger.error(f"✗ Voice agent failed: {e}")
        app.state.voice_agent = None

    # Proactive Skill & background worker
    proactive_task = None
    try:
        from backend.services.skills.proactive_skill import ProactiveSkill
        proactive_skill = ProactiveSkill(app_state=app.state)
        app.state.proactive_skill = proactive_skill
        
        # Register in skills registry if planner exists
        if planner_agent and hasattr(planner_agent, "skills_registry"):
            planner_agent.skills_registry.register_skill(proactive_skill)
            
        async def proactive_worker():
            logger.info("✓ Proactive background worker started")
            while True:
                try:
                    await proactive_skill.check_triggers()
                except Exception as ex:
                    logger.error("Error in proactive check loop: {}", ex)
                await asyncio.sleep(10)  # Check every 10 seconds
                
        proactive_task = asyncio.create_task(proactive_worker())
        app.state.proactive_task = proactive_task
        logger.info("✓ Proactive background checks initialized")
    except Exception as e:
        logger.error(f"✗ Proactive checks failed: {e}")

    # Context Skill background worker
    context_task = None
    try:
        if planner_agent and hasattr(planner_agent, "skills_registry"):
            context_skill = planner_agent.skills_registry.skills.get("ContextSkill")
            if context_skill:
                async def context_worker():
                    logger.info("✓ Context background worker started")
                    while True:
                        try:
                            # Update active foreground window
                            changed = context_skill.update_active_window()
                            # Broadcast context update to all WS clients when window changes
                            if changed:
                                from backend.api.websocket import manager as ws_manager
                                try:
                                    from backend.models.schemas import WSMessage
                                    ctx = context_skill.active_context
                                    await ws_manager.broadcast(WSMessage(
                                        type="context_update",
                                        data={
                                            "window_title": ctx.get("window_title", ""),
                                            "process_name": ctx.get("process_name", ""),
                                            "inferred_project": ctx.get("inferred_project", ""),
                                            "start_time": ctx.get("start_time", "")
                                        }
                                    ))
                                except Exception as ws_err:
                                    logger.debug("WS broadcast context_update failed: {}", ws_err)
                        except Exception as ex:
                            logger.error("Error in context scanner loop: {}", ex)
                        await asyncio.sleep(30)  # Poll every 30s (was 5s)

                context_task = asyncio.create_task(context_worker())
                app.state.context_task = context_task
                logger.info("✓ Context background scanner initialized")
    except Exception as e:
        logger.error(f"✗ Context worker initialization failed: {e}")

    # Sync Service
    sync_service = None
    try:
        from backend.services.sync_service import SyncService
        sync_service = SyncService(app_state=app.state)
        sync_service.start()
        app.state.sync_service = sync_service
    except Exception as e:
        logger.error(f"✗ Sync service failed: {e}")

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"  JARVIS is online! (startup: {elapsed:.1f}s)")
    logger.info(f"  Server: http://{settings.SERVER_HOST}:{settings.SERVER_PORT}")
    logger.info(f"  WebSocket: ws://{settings.SERVER_HOST}:{settings.SERVER_PORT}/ws")
    logger.info("=" * 60)

    # Launch Electron frontend if not already spawned by Electron
    if os.environ.get("SPAWNED_BY_ELECTRON") != "true":
        async def launch_frontend():
            await asyncio.sleep(1.5)  # Let uvicorn start listening on the port
            try:
                import subprocess
                import os
                
                frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
                logger.info(f"Auto-launching Electron frontend from {frontend_dir}...")
                
                # Clean environment variable that causes VS Code / IDE issues
                env = os.environ.copy()
                if "ELECTRON_RUN_AS_NODE" in env:
                    del env["ELECTRON_RUN_AS_NODE"]
                
                # Launch Electron in the background
                subprocess.Popen(
                    ["npm", "run", "dev"],
                    cwd=frontend_dir,
                    shell=True,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info("✓ Electron frontend launch process spawned")
            except Exception as ex:
                logger.error(f"Failed to auto-launch Electron frontend: {ex}")

        asyncio.create_task(launch_frontend())

    # ── Yield to application ──────────────────────────────────
    yield

    # ── Shutdown ──────────────────────────────────────────────
    logger.info("JARVIS shutting down...")

    if hasattr(app.state, "task_queue") and app.state.task_queue:
        try:
            await app.state.task_queue.stop()
        except Exception as e:
            logger.error(f"Task queue shutdown error: {e}")

    if hasattr(app.state, "mcp_client_manager") and app.state.mcp_client_manager:
        try:
            await app.state.mcp_client_manager.shutdown()
        except Exception as e:
            logger.error(f"MCP client shutdown error: {e}")

    if hasattr(app.state, "proactive_task") and app.state.proactive_task:
        try:
            app.state.proactive_task.cancel()
            logger.info("✓ Proactive background worker cancelled")
        except Exception as e:
            logger.error(f"Proactive checks cleanup error: {e}")

    if hasattr(app.state, "context_task") and app.state.context_task:
        try:
            app.state.context_task.cancel()
            logger.info("✓ Context background worker cancelled")
        except Exception as e:
            logger.error(f"Context worker cleanup error: {e}")

    if hasattr(app.state, "sync_service") and app.state.sync_service:
        try:
            app.state.sync_service.stop()
        except Exception as e:
            logger.error(f"Sync service cleanup error: {e}")

    if hasattr(app.state, "clap_service") and app.state.clap_service:
        try:
            app.state.clap_service.stop()
            logger.info("✓ Clap service stopped cleanly")
        except Exception as e:
            logger.error(f"Clap service cleanup error: {e}")

    if browser_service and browser_service.is_started:
        try:
            await browser_service.stop()
        except Exception as e:
            logger.error(f"Browser cleanup error: {e}")

    if hasattr(app.state, "llm_router") and app.state.llm_router:
        try:
            await app.state.llm_router.shutdown()
            logger.info("✓ LLM Router shut down cleanly")
        except Exception as e:
            logger.error(f"Router cleanup error: {e}")

    if memory_service:
        try:
            await memory_service.shutdown()
        except Exception as e:
            logger.error(f"Memory cleanup error: {e}")

    logger.info("JARVIS offline. Goodbye, sir.")


# ── Create FastAPI App ──────────────────────────────────────

app = FastAPI(
    title="JARVIS AI Desktop Assistant",
    description="A production-grade, voice-controlled AI desktop assistant for Windows.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Include Routers ─────────────────────────────────────────

from backend.api.middleware import setup_middleware
from backend.api.routes import router as api_router
from backend.api.websocket import router as ws_router
from backend.api.routes_ui import router as ui_router

setup_middleware(app)
app.include_router(api_router, tags=["API"])
app.include_router(ws_router, tags=["WebSocket"])
app.include_router(ui_router)


# ── Root route (browser-friendly status page) ───────────────

from fastapi.responses import JSONResponse

@app.get("/", include_in_schema=False)
async def root():
    """Friendly landing page — open http://localhost:5173 for the full UI."""
    return JSONResponse({
        "status": "online",
        "name": "JARVIS AI Desktop Assistant",
        "version": "1.0.0",
        "message": "Backend is running ✓  —  Open the Electron app or http://localhost:5173 for the dashboard.",
        "endpoints": {
            "api_docs": "http://127.0.0.1:8000/docs",
            "health": "http://127.0.0.1:8000/health",
            "websocket": "ws://127.0.0.1:8000/ws",
            "frontend": "http://localhost:5173"
        }
    })


# ── Run with uvicorn ────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=False,
        log_level="info",
    )
