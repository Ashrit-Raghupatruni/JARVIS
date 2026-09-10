"""
JARVIS AI Desktop Assistant — FastAPI Backend Entry Point.

Initializes all services, configures the API, and starts the server.
"""

import os
import sys
import time
import asyncio
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_settings
from backend.utils.logger import setup_logger
from backend.utils.event_bus import EventBus

# Configure HuggingFace & Transformers offline mode dynamically from settings
_init_settings = get_settings()
if getattr(_init_settings, "FORCE_OFFLINE_MODE", True):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
else:
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "False"

from fastapi import FastAPI, Request
from loguru import logger
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

    # ── Instant Socket Binding & Async Background Service Initializer ────
    async def _init_background_services():
        await asyncio.sleep(0.01)  # Allow uvicorn socket to bind immediately
        
        # ── 1. Core Services (Eagerly Initialized) ─────────────────────────
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

        # Security & Safety Core (Zero external network overhead, fail-closed)
        from backend.services.security.vault import CredentialVault
        from backend.services.security.sandbox import SecuritySandbox
        from backend.services.security.rbac import SecurityOrchestrator
        from backend.services.safety import SafetyService
        
        credential_vault = CredentialVault()
        security_sandbox = SecuritySandbox()
        security_orchestrator = SecurityOrchestrator(event_bus)
        safety_service = SafetyService()
        
        app.state.credential_vault = credential_vault
        app.state.security_sandbox = security_sandbox
        app.state.security_orchestrator = security_orchestrator
        app.state.safety_service = safety_service
        
        ServiceManager.register_instance("credential_vault", credential_vault)
        ServiceManager.register_instance("security_sandbox", security_sandbox)
        ServiceManager.register_instance("security_orchestrator", security_orchestrator)
        ServiceManager.register_instance("safety_service", safety_service)

        # Fast Intent Router Core
        from backend.services.fast_intent_router import fast_intent_router
        app.state.fast_intent_router = fast_intent_router
        ServiceManager.register_instance("fast_intent_router", fast_intent_router)

        # Basic LLM Interface Core
        llm_service = None
        try:
            from backend.services.llm import LLMService
            llm_service = LLMService()
            app.state.llm_service = llm_service
            ServiceManager.register_instance("llm_service", llm_service)
            provider = settings.LLM_PROVIDER or "gemini"
            logger.info(f"✓ Core LLM service initialized (provider: {provider})")
        except Exception as e:
            logger.error(f"✗ LLM service failed: {e}")
            app.state.llm_service = None

        from backend.api.websocket import manager as connection_manager
        app.state.connection_manager = connection_manager

        # ── 2. Register Lazy Factories for Heavy / Optional Services ────────

        # Autonomous Agent Ecosystem
        def _make_agent_ecosystem():
            from backend.services.agent_ecosystem import AgentEcosystemService
            return AgentEcosystemService(event_bus=event_bus, connection_manager=connection_manager)
        ServiceManager.register_factory("agent_ecosystem", _make_agent_ecosystem)

        # Checkpoint Service & KV Cache Pruner
        def _make_checkpoint_service():
            from backend.services.long_horizon_checkpoint import LongHorizonCheckpointService
            svc = LongHorizonCheckpointService()
            asyncio.create_task(svc.initialize())
            return svc
        ServiceManager.register_factory("checkpoint_service", _make_checkpoint_service)

        def _make_kv_pruner():
            from backend.services.kv_cache_pruner import KVCachePruner
            return KVCachePruner()
        ServiceManager.register_factory("kv_pruner", _make_kv_pruner)

        # World Model
        def _make_world_model():
            from backend.services.world_model import WorldModel
            return WorldModel(event_bus=event_bus)
        ServiceManager.register_factory("world_model", _make_world_model)

        # Biometrics & Security Extensions
        def _make_face_biometrics():
            from backend.services.face_biometrics import FaceBiometricsService
            return FaceBiometricsService()
        ServiceManager.register_factory("face_biometrics_service", _make_face_biometrics)

        # Audio / Speech Subsystems (STT, TTS, WakeWord, Clap)
        def _make_stt_service():
            from backend.services.stt import STTService
            return STTService()
        ServiceManager.register_factory("stt_service", _make_stt_service)

        def _make_tts_service():
            from backend.services.tts import TTSService
            return TTSService()
        ServiceManager.register_factory("tts_service", _make_tts_service)

        def _make_wake_word_service():
            from backend.services.wake_word import WakeWordService
            ww = WakeWordService()
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                loop.create_task(ww.load_model())
            except (RuntimeError, AttributeError):
                pass
            return ww
        ServiceManager.register_factory("wake_word_service", _make_wake_word_service)

        def _make_clap_service():
            from backend.services.clap import ClapService
            def handle_clap_event(mode):
                logger.info("👏 Double clap event triggered (mode={}). Restoring JARVIS desktop window...", mode)
                try:
                    auto_svc = ServiceManager.get_instance("automation_service")
                    if auto_svc and hasattr(auto_svc, "focus_window"):
                        auto_svc.focus_window("JARVIS")
                except Exception as e:
                    logger.warning("Could not focus JARVIS window on clap: {}", e)
            cs = ClapService(on_clap_detected=handle_clap_event)
            cs.start()
            return cs
        ServiceManager.register_factory("clap_service", _make_clap_service)

        # Automation & Win32 UIA
        def _make_automation_service():
            from backend.services.automation import AutomationService
            return AutomationService()
        ServiceManager.register_factory("automation_service", _make_automation_service)
        ServiceManager.register_factory("automation", _make_automation_service)

        def _make_uia_engine():
            from backend.services.uia_engine import UIAEngine
            return UIAEngine()
        ServiceManager.register_factory("uia_engine", _make_uia_engine)

        def _make_desktop_automation():
            from backend.services.desktop_automation import DesktopAutomationService
            return DesktopAutomationService()
        ServiceManager.register_factory("desktop_automation_service", _make_desktop_automation)

        # Perception & Vision
        def _make_screen_service():
            from backend.services.screen import ScreenService
            return ScreenService()
        ServiceManager.register_factory("screen_service", _make_screen_service)

        def _make_vision_service():
            from backend.services.vision_service import VisionService
            return VisionService()
        ServiceManager.register_factory("vision_service", _make_vision_service)

        def _make_hand_control():
            from backend.services.hand_control_service import HandControlService
            return HandControlService()
        ServiceManager.register_factory("hand_control_service", _make_hand_control)

        # Developer & Research Subsystems
        def _make_developer_assistant():
            from backend.services.developer_assistant import DeveloperAssistantService
            return DeveloperAssistantService()
        ServiceManager.register_factory("developer_assistant_service", _make_developer_assistant)

        def _make_self_development():
            from backend.services.self_development_service import SelfDevelopmentService
            return SelfDevelopmentService()
        ServiceManager.register_factory("self_development_service", _make_self_development)

        def _make_research_service():
            from backend.services.research_agent import ResearchAgentService
            return ResearchAgentService()
        ServiceManager.register_factory("research_service", _make_research_service)

        def _make_voice_intelligence():
            from backend.services.voice_intelligence import VoiceIntelligenceService
            return VoiceIntelligenceService()
        ServiceManager.register_factory("voice_intelligence_service", _make_voice_intelligence)

        def _make_productivity_service():
            from backend.services.productivity_service import ProductivityService
            return ProductivityService()
        ServiceManager.register_factory("productivity_service", _make_productivity_service)

        def _make_workspace_intel():
            from backend.services.workspace_intelligence import WorkspaceIntelligenceService
            return WorkspaceIntelligenceService()
        ServiceManager.register_factory("workspace_intelligence", _make_workspace_intel)

        # Browser Automation
        def _make_browser_service():
            from backend.services.browser import BrowserService
            return BrowserService()
        ServiceManager.register_factory("browser_service", _make_browser_service)

        def _make_task_queue_service():
            from backend.services.task_queue import TaskQueueService
            return TaskQueueService()
        ServiceManager.register_factory("task_queue_service", _make_task_queue_service)

        # Mobile Gateway & Bridge Subsystems
        def _make_file_indexer():
            from backend.services.file_indexer import FileIndexerService
            return FileIndexerService()
        ServiceManager.register_factory("file_indexer", _make_file_indexer)

        def _make_mobile_bridge():
            from backend.services.mobile_bridge import MobileBridgeService
            return MobileBridgeService()
        ServiceManager.register_factory("mobile_bridge", _make_mobile_bridge)

        def _make_mobile_auth():
            from backend.services.mobile_auth import MobileAuthService
            return MobileAuthService()
        ServiceManager.register_factory("mobile_auth_service", _make_mobile_auth)

        def _make_mobile_gateway():
            from backend.services.mobile_gateway import MobileGatewayService
            return MobileGatewayService()
        ServiceManager.register_factory("mobile_gateway_service", _make_mobile_gateway)

        def _make_oauth_service():
            from backend.services.oauth_service import oauth_service
            return oauth_service
        ServiceManager.register_factory("oauth_service", _make_oauth_service)

        def _make_bt_proximity():
            from backend.services.bluetooth_proximity import bluetooth_proximity_service
            return bluetooth_proximity_service
        ServiceManager.register_factory("bluetooth_proximity_service", _make_bt_proximity)

        # Self-Improving Engines & Strategy Memory
        def _make_experience_engine():
            from backend.services.experience_engine import ExperienceEngineService
            return ExperienceEngineService()
        ServiceManager.register_factory("experience_engine", _make_experience_engine)

        def _make_reflection_engine():
            from backend.services.reflection_engine import ReflectionEngineService
            return ReflectionEngineService()
        ServiceManager.register_factory("reflection_engine", _make_reflection_engine)

        def _make_self_healing():
            from backend.services.self_healing import SelfHealingEngine
            return SelfHealingEngine()
        ServiceManager.register_factory("self_healing", _make_self_healing)

        def _make_strategy_memory():
            from backend.services.strategy_memory import StrategyMemoryService
            return StrategyMemoryService()
        ServiceManager.register_factory("strategy_memory", _make_strategy_memory)

        def _make_skill_library():
            from backend.services.skills.skill_library import SkillLibraryService
            return SkillLibraryService()
        ServiceManager.register_factory("skill_library", _make_skill_library)

        def _make_live_mode():
            from backend.services.live_mode.live_engine import LiveModeEngine
            return LiveModeEngine()
        ServiceManager.register_factory("live_mode_engine", _make_live_mode)

        # Memory & RAG Subsystems
        def _make_memory_service():
            from backend.services.memory import MemoryService
            return MemoryService()
        ServiceManager.register_factory("memory_service", _make_memory_service)

        def _make_rag_service():
            from backend.services.rag_service import RAGService
            mem = ServiceManager.get_instance("memory_service")
            chroma_client = getattr(mem, "_chroma_client", None) if mem else None
            return RAGService(chroma_client=chroma_client)
        ServiceManager.register_factory("rag_service", _make_rag_service)

        # MCP Client Manager
        def _make_mcp():
            from backend.mcp.client import MCPClientManager
            return MCPClientManager()
        ServiceManager.register_factory("mcp_client_manager", _make_mcp)

        # Orchestration Agents (Planner & Voice)
        def _make_planner():
            from backend.agents.planner import PlannerAgent
            return PlannerAgent(
                llm_service=ServiceManager.get_instance("llm_service"),
                automation_service=ServiceManager.get_instance("automation_service"),
                screen_service=ServiceManager.get_instance("screen_service"),
                browser_service=ServiceManager.get_instance("browser_service"),
                memory_service=ServiceManager.get_instance("memory_service"),
                safety_service=ServiceManager.get_instance("safety_service"),
                vision_service=ServiceManager.get_instance("vision_service"),
                desktop_automation_service=ServiceManager.get_instance("desktop_automation_service"),
                developer_assistant_service=ServiceManager.get_instance("developer_assistant_service"),
                research_service=ServiceManager.get_instance("research_service"),
                voice_intelligence_service=ServiceManager.get_instance("voice_intelligence_service"),
                productivity_service=ServiceManager.get_instance("productivity_service"),
            )
        ServiceManager.register_factory("planner_agent", _make_planner)

        def _make_voice_agent():
            from backend.agents.voice import VoiceAgent
            return VoiceAgent(
                wake_word_service=ServiceManager.get_instance("wake_word_service"),
                stt_service=ServiceManager.get_instance("stt_service"),
                tts_service=ServiceManager.get_instance("tts_service"),
                planner_agent=ServiceManager.get_instance("planner_agent"),
            )
        ServiceManager.register_factory("voice_agent", _make_voice_agent)

        logger.info("✓ Core services initialized; {} optional/heavy services registered for lazy loading", len(ServiceManager.list_registered_factories()))

    asyncio.create_task(_init_background_services())

    asyncio.create_task(_init_background_services())


    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"  JARVIS is online! (Instant socket bind: {elapsed:.3f}s)")
    logger.info(f"  Server: http://{settings.SERVER_HOST}:{settings.SERVER_PORT}")
    logger.info(f"  WebSocket: ws://{settings.SERVER_HOST}:{settings.SERVER_PORT}/ws")
    logger.info("=" * 60)

    # Launch Electron frontend if not already spawned by Electron or managed by launcher
    if os.environ.get("SPAWNED_BY_ELECTRON") != "true" and os.environ.get("LAUNCHER_MANAGED") != "1":
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

    # ── Mobile Gatekeeper Desktop Shutdown Approval Check ──────
    if hasattr(app.state, "mobile_gateway_service") and app.state.mobile_gateway_service:
        try:
            logger.info("🛡️ Requesting Mobile Gatekeeper approval for Desktop shutdown...")
            decision = await app.state.mobile_gateway_service.request_approval(
                action_type="desktop_shutdown",
                description="JARVIS Desktop OS is closing / shutting down.",
                dangerous_target="JARVIS Desktop Core Process",
                timeout_seconds=15.0
            )
            if decision != "approve":
                logger.warning("⛔ Mobile Gatekeeper denied or timed out desktop shutdown.")
            else:
                logger.info("✅ Mobile Gatekeeper approved desktop shutdown.")
        except Exception as gate_err:
            logger.warning("Mobile shutdown approval check error: {}", gate_err)

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

    if hasattr(app.state, "zeroconf_service") and app.state.zeroconf_service:
        try:
            app.state.zeroconf_service.stop()
        except Exception as e:
            logger.warning(f"Zeroconf shutdown notice: {e}")


    if hasattr(app.state, "clap_service") and app.state.clap_service:
        try:
            app.state.clap_service.stop()
            logger.info("✓ Clap service stopped cleanly")
        except Exception as e:
            logger.error(f"Clap service cleanup error: {e}")

    if hasattr(app.state, "browser_service") and app.state.browser_service:
        try:
            b_svc = app.state.browser_service
            if hasattr(b_svc, "is_started") and b_svc.is_started:
                await b_svc.stop()
        except Exception as e:
            logger.error(f"Browser cleanup error: {e}")

    if hasattr(app.state, "llm_router") and app.state.llm_router:
        try:
            await app.state.llm_router.shutdown()
            logger.info("✓ LLM Router shut down cleanly")
        except Exception as e:
            logger.error(f"Router cleanup error: {e}")

    if hasattr(app.state, "memory_service") and app.state.memory_service:
        try:
            await app.state.memory_service.shutdown()
        except Exception as e:
            logger.error(f"Memory cleanup error: {e}")

    # ── Shutdown all ServiceManager active singletons ─────────
    try:
        await ServiceManager.shutdown_all()
    except Exception as e:
        logger.error(f"ServiceManager shutdown error: {e}")

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
from backend.api.mobile_router import mobile_router
from backend.api.mobile_ws import mobile_ws_router
from backend.api.debug_router import debug_router
from backend.api.integrations_router import integrations_router
from backend.api.oauth import router as oauth_router

setup_middleware(app)
app.include_router(api_router, tags=["API"])
app.include_router(ws_router, tags=["WebSocket"])
app.include_router(ui_router)
app.include_router(mobile_router)
app.include_router(mobile_ws_router)
app.include_router(debug_router)
app.include_router(integrations_router)
app.include_router(oauth_router)


@app.get("/api/live_mode/status")
@app.get("/live_mode/status")
@app.get("/api/v1/live_mode/status")
async def get_live_mode_status_global(request: Request):
    """Global API endpoint for Live Mode status."""
    live_engine = ServiceManager.get_instance("live_mode_engine")
    if not live_engine and hasattr(request.app.state, "live_mode_engine"):
        live_engine = request.app.state.live_mode_engine
    if not live_engine or not live_engine.is_enabled:
        return {"status": "inactive", "live_mode_enabled": False}

    frame = getattr(live_engine, "latest_frame", None)
    return {
        "status": "active",
        "live_mode_enabled": True,
        "frame": frame.model_dump() if frame and hasattr(frame, "model_dump") else None
    }


@app.post("/api/live_mode/toggle")
@app.post("/live_mode/toggle")
@app.post("/api/v1/live_mode/toggle")
@app.get("/api/live_mode/toggle")
@app.get("/live_mode/toggle")
@app.get("/api/v1/live_mode/toggle")
async def toggle_live_mode_global(request: Request, enable: bool = True):
    """Global API endpoint for toggling Live Mode perception loop."""
    live_engine = ServiceManager.get_instance("live_mode_engine")
    if not live_engine and hasattr(request.app.state, "live_mode_engine"):
        live_engine = request.app.state.live_mode_engine
    if not live_engine:
        from backend.services.live_mode.live_engine import LiveModeEngine
        live_engine = LiveModeEngine()
        request.app.state.live_mode_engine = live_engine
        ServiceManager.register_instance("live_mode_engine", live_engine)

    greeting_msg = None
    if enable:
        live_engine.start(speak_greeting=True)
        greeting_msg = live_engine.get_activation_greeting()
    else:
        live_engine.stop()

    return {
        "status": "ok",
        "live_mode_enabled": live_engine.is_enabled,
        "greeting": greeting_msg,
        "message": f"Live Mode {'enabled' if enable else 'disabled'}"
    }


# ── Native System Lock Endpoint ────────────────────────────
@app.post("/api/system/lock")
@app.get("/api/system/lock")
async def system_lock_global():
    """Execute native Windows LockWorkStation."""
    import ctypes
    try:
        res = ctypes.windll.user32.LockWorkStation()
        return {"status": "success", "locked": bool(res), "message": "Workstation locked successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Global Chat History Endpoints ───────────────────────────

@app.get("/api/conversations")
@app.get("/api/v1/conversations")
@app.get("/history")
@app.get("/api/v1/history")
async def get_conversations_global(request: Request, limit: int = 30):
    """Fetch conversation list for sidebar UI."""
    mem_svc = ServiceManager.get_instance("memory_service") or getattr(request.app.state, "memory_service", None)
    if mem_svc:
        try:
            conversations = await mem_svc.get_recent_conversations(limit=limit)
            return {"status": "ok", "conversations": conversations}
        except Exception as e:
            logger.error("Failed to get conversations: {}", e)
            return {"status": "error", "conversations": [], "error": str(e)}
    return {"status": "ok", "conversations": []}


@app.get("/api/conversations/{conv_id}")
@app.get("/api/v1/conversations/{conv_id}")
async def get_conversation_by_id_global(conv_id: int, request: Request):
    """Fetch single conversation transcript."""
    mem_svc = ServiceManager.get_instance("memory_service") or getattr(request.app.state, "memory_service", None)
    if mem_svc:
        conv = await mem_svc.get_conversation(conv_id)
        if conv:
            return {"status": "ok", "conversation": conv}
        return JSONResponse(status_code=404, content={"status": "error", "message": "Conversation not found"})
    return JSONResponse(status_code=503, content={"status": "error", "message": "Memory service unavailable"})


@app.put("/api/conversations/{conv_id}")
@app.put("/api/v1/conversations/{conv_id}")
async def rename_conversation_by_id_global(conv_id: int, payload: Dict[str, Any], request: Request):
    """Rename a conversation by ID."""
    mem_svc = ServiceManager.get_instance("memory_service") or getattr(request.app.state, "memory_service", None)
    new_title = payload.get("title") or "Untitled Conversation"
    if mem_svc:
        success = await mem_svc.rename_conversation(conv_id, new_title)
        if success:
            return {"status": "ok", "message": f"Conversation {conv_id} renamed to '{new_title}'"}
        return JSONResponse(status_code=404, content={"status": "error", "message": "Conversation not found"})
    return JSONResponse(status_code=503, content={"status": "error", "message": "Memory service unavailable"})


@app.delete("/api/conversations/{conv_id}")
@app.delete("/api/v1/conversations/{conv_id}")
async def delete_conversation_by_id_global(conv_id: int, request: Request):
    """Delete a conversation by ID."""
    mem_svc = ServiceManager.get_instance("memory_service") or getattr(request.app.state, "memory_service", None)
    if mem_svc:
        success = await mem_svc.delete_conversation(conv_id)
        if success:
            return {"status": "ok", "message": f"Conversation {conv_id} deleted"}
        return JSONResponse(status_code=404, content={"status": "error", "message": "Conversation not found"})
    return JSONResponse(status_code=503, content={"status": "error", "message": "Memory service unavailable"})


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
