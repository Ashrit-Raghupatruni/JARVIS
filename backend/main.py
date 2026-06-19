"""
JARVIS AI Desktop Assistant — FastAPI Backend Entry Point.

Initializes all services, configures the API, and starts the server.
"""

import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings
from backend.utils.logger import setup_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize and cleanup services."""
    settings = get_settings()
    setup_logger()
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("  JARVIS AI Desktop Assistant — Starting Up")
    logger.info("=" * 60)

    # ── Initialize Services ──────────────────────────────────

    # Safety Service (no external deps, always available)
    from backend.services.safety import SafetyService
    safety_service = SafetyService()
    app.state.safety_service = safety_service
    logger.info("✓ Safety service initialized")

    # LLM Service
    llm_service = None
    try:
        from backend.services.llm import LLMService
        llm_service = LLMService()
        app.state.llm_service = llm_service
        # Log active provider and model
        provider = settings.LLM_PROVIDER or "gemini"
        if provider == "ollama":
            active_model = settings.OLLAMA_MODEL
        elif provider == "gemini":
            active_model = settings.GEMINI_MODEL
        else:
            active_model = settings.OPENAI_MODEL
        logger.info(f"✓ LLM service initialized (provider: {provider}, model: {active_model})")
    except Exception as e:
        logger.error(f"✗ LLM service failed: {e}")
        app.state.llm_service = None

    # Speech-to-Text Service
    stt_service = None
    try:
        from backend.services.stt import STTService
        stt_service = STTService()
        app.state.stt_service = stt_service
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
        logger.info(f"✓ TTS service initialized (voice: {settings.TTS_VOICE})")
    except Exception as e:
        logger.error(f"✗ TTS service failed: {e}")
        app.state.tts_service = None

    # Wake Word Service
    wake_word_service = None
    try:
        from backend.services.wake_word import WakeWordService
        wake_word_service = WakeWordService()
        import asyncio
        asyncio.create_task(wake_word_service.load_model())
        app.state.wake_word_service = wake_word_service
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
        logger.info("✓ Screen service initialized")
    except Exception as e:
        logger.error(f"✗ Screen service failed: {e}")
        app.state.screen_service = None

    # Browser Service
    browser_service = None
    try:
        from backend.services.browser import BrowserService
        browser_service = BrowserService()
        app.state.browser_service = browser_service
        logger.info("✓ Browser service initialized (lazy start)")
    except Exception as e:
        logger.error(f"✗ Browser service failed: {e}")
        app.state.browser_service = None

    # Memory Service
    memory_service = None
    try:
        from backend.services.memory import MemoryService
        memory_service = MemoryService()
        await memory_service.init()
        app.state.memory_service = memory_service
        logger.info("✓ Memory service initialized")
    except Exception as e:
        logger.error(f"✗ Memory service failed: {e}")
        app.state.memory_service = None

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
                
        import asyncio
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
                            context_skill.update_active_window()
                        except Exception as ex:
                            logger.error("Error in context scanner loop: {}", ex)
                        await asyncio.sleep(5)  # Check every 5 seconds
                
                import asyncio
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

    # ── Yield to application ──────────────────────────────────
    yield

    # ── Shutdown ──────────────────────────────────────────────
    logger.info("JARVIS shutting down...")

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

setup_middleware(app)
app.include_router(api_router, tags=["API"])
app.include_router(ws_router, tags=["WebSocket"])


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
