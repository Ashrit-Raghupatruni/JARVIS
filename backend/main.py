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
from backend.services.manager import ServiceManager
from backend.services.bootstrap import bootstrap_core_services, register_lazy_factories
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

    # 1. Bootstrap essential core services (fast, synchronous, fail-closed)
    event_bus = bootstrap_core_services(app)

    # 2. Register lazy factories for heavy/optional subsystems
    register_lazy_factories(event_bus, app.state.connection_manager)

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"  JARVIS is online! (Startup time: {elapsed:.3f}s)")
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
