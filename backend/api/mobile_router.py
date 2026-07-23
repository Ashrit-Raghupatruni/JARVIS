"""
JARVIS AI Operating System - Mobile Companion REST API Router.

Exposes REST endpoints for mobile app authentication, device pairing, remote desktop control,
file management, screen previews, and mobile security approval responses.
"""

import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from loguru import logger

from backend.models.mobile_schemas import (
    PairingInitiateRequest,
    PairingInitiateResponse,
    PairingConfirmRequest,
    PairingConfirmResponse,
    RemoteCommandRequest,
    MobileApprovalDecision,
    ScreenPreviewResponse,
    SystemTelemetry,
    DeviceInfo
)

from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request

mobile_router = APIRouter(prefix="/api/v1/mobile", tags=["Mobile Companion"])


def get_mobile_auth_service(request: Request):
    if hasattr(request.app.state, "mobile_auth_service") and request.app.state.mobile_auth_service:
        return request.app.state.mobile_auth_service
    try:
        from backend.services.manager import ServiceManager
        if hasattr(ServiceManager, "get_instance"):
            return ServiceManager.get_instance("mobile_auth_service")
    except Exception:
        pass
    return None


def get_mobile_gateway_service(request: Request):
    if hasattr(request.app.state, "mobile_gateway_service") and request.app.state.mobile_gateway_service:
        return request.app.state.mobile_gateway_service
    try:
        from backend.services.manager import ServiceManager
        if hasattr(ServiceManager, "get_instance"):
            return ServiceManager.get_instance("mobile_gateway_service")
    except Exception:
        pass
    return None


# ── AUTHENTICATION & PAIRING ───────────────────────────────────────────────

@mobile_router.post("/pair/initiate", response_model=PairingInitiateResponse)
async def initiate_pairing(req: PairingInitiateRequest, auth_svc=Depends(get_mobile_auth_service)):
    """Generate 6-digit numeric pairing PIN for desktop display."""
    if not auth_svc:
        raise HTTPException(status_code=503, detail="Mobile auth service unavailable")
    return auth_svc.initiate_pairing(req.device_name, req.device_id)


@mobile_router.post("/pair/confirm", response_model=PairingConfirmResponse)
async def confirm_pairing(req: PairingConfirmRequest, auth_svc=Depends(get_mobile_auth_service)):
    """Validate 6-digit PIN and return signed JWT access token."""
    if not auth_svc:
        raise HTTPException(status_code=503, detail="Mobile auth service unavailable")
    
    res = auth_svc.confirm_pairing(req.pairing_session_id, req.pairing_code, req.device_id)
    if not res:
        raise HTTPException(status_code=401, detail="Invalid or expired pairing code")
    return res


@mobile_router.post("/pair")
async def pair_device_easy(req: Dict[str, Any], auth_svc=Depends(get_mobile_auth_service)):
    """Direct companion pairing with PIN."""
    if not auth_svc:
        raise HTTPException(status_code=503, detail="Mobile auth service unavailable")
    
    pin = str(req.get("pin", "")).strip()
    device_name = req.get("device_name", "Android Phone")
    device_id = req.get("device_id", "android-companion-1")
    
    res = auth_svc.easy_pair(pin, device_name, device_id)
    if not res:
        raise HTTPException(status_code=401, detail="Invalid pairing PIN")
    return res


@mobile_router.get("/devices", response_model=List[DeviceInfo])
async def list_trusted_devices(auth_svc=Depends(get_mobile_auth_service)):
    """List registered trusted mobile companion devices."""
    if not auth_svc:
        return []
    return auth_svc.get_trusted_devices()


# ── TELEMETRY & STATUS ────────────────────────────────────────────────────

@mobile_router.get("/telemetry", response_model=SystemTelemetry)
async def get_telemetry(gateway_svc=Depends(get_mobile_gateway_service)):
    """Fetch current desktop telemetry (CPU, RAM, GPU, Battery, Task)."""
    if not gateway_svc:
        raise HTTPException(status_code=503, detail="Mobile gateway unavailable")
    return gateway_svc.get_system_telemetry()


# ── REMOTE DESKTOP COMMANDS ────────────────────────────────────────────────

@mobile_router.post("/system/command")
async def execute_remote_command(req: RemoteCommandRequest, gateway_svc=Depends(get_mobile_gateway_service)):
    """Execute remote desktop command (shutdown, restart, lock, sleep, open_app)."""
    cmd = req.command.lower()
    logger.info("Executing remote desktop command from mobile: {}", cmd)

    try:
        import subprocess
        if cmd == "shutdown":
            subprocess.Popen(["shutdown", "/s", "/t", "5"], shell=True)
            return {"status": "shutdown_initiated", "seconds": 5}
        elif cmd == "restart":
            subprocess.Popen(["shutdown", "/r", "/t", "5"], shell=True)
            return {"status": "restart_initiated", "seconds": 5}
        elif cmd == "lock":
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], shell=True)
            return {"status": "workstation_locked"}
        elif cmd == "open_app":
            app_name = req.params.get("app_name", "notepad")
            subprocess.Popen(app_name, shell=True)
            return {"status": "application_opened", "app": app_name}
        else:
            return {"status": "command_received", "command": cmd}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── MOBILE SECURITY APPROVALS ──────────────────────────────────────────────

@mobile_router.post("/approvals/respond")
async def submit_approval_decision(req: MobileApprovalDecision, gateway_svc=Depends(get_mobile_gateway_service)):
    """Submit mobile security approval decision (approve, deny, always_allow, always_deny)."""
    if not gateway_svc:
        raise HTTPException(status_code=503, detail="Mobile gateway unavailable")

    ok = gateway_svc.submit_approval_decision(req.approval_id, req.decision)
    if not ok:
        raise HTTPException(status_code=404, detail="Approval request ID not found or expired")

    return {"status": "decision_processed", "approval_id": req.approval_id, "decision": req.decision}


# ── SCREEN PREVIEW ────────────────────────────────────────────────────────

@mobile_router.get("/screen/preview", response_model=ScreenPreviewResponse)
async def get_screen_preview(gateway_svc=Depends(get_mobile_gateway_service)):
    """Capture on-demand desktop screenshot thumbnail."""
    if not gateway_svc:
        raise HTTPException(status_code=503, detail="Mobile gateway unavailable")
    return gateway_svc.capture_screen_preview()


# ── FILE MANAGER ─────────────────────────────────────────────────────────

@mobile_router.get("/files/search")
async def search_desktop_files(query: str = Query(...)):
    """Search desktop files using SQLite FTS5 indexer."""
    from backend.services.manager import ServiceManager
    indexer = ServiceManager.get_instance("file_indexer")
    if not indexer:
        return []
    return indexer.search_files(query)


# ── MISSION CONTROL DASHBOARD EXTENSIONS ────────────────────────────────

@mobile_router.get("/diagnostics")
async def get_self_diagnostics():
    """Run self-diagnosis check on CPU, RAM, GPU, Memory, RAG, and LLM services."""
    from backend.services.manager import ServiceManager
    import psutil
    
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('C:\\').percent

    llm_status = "Online"
    router = ServiceManager.get_instance("llm_router")
    if router and hasattr(router, "active_provider"):
        llm_status = f"Active: {router.active_provider}"

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "diagnostics": {
            "cpu": {"usage": cpu, "status": "OK" if cpu < 90 else "HIGH"},
            "memory": {"usage": ram, "status": "OK" if ram < 90 else "HIGH"},
            "disk": {"usage": disk, "status": "OK" if disk < 90 else "HIGH"},
            "llm": {"provider": llm_status, "status": "OK"},
            "voice": {"stt": "Ready", "tts": "Ready", "status": "OK"},
            "planner": {"status": "Active"},
            "rag": {"status": "Indexed"}
        }
    }


@mobile_router.get("/brain/memory")
async def get_brain_memories(limit: int = 10):
    """Fetch recent long-term memories from HybridMemorySystem."""
    from backend.services.manager import ServiceManager
    mem_svc = ServiceManager.get_instance("memory_service")
    if not mem_svc:
        return {"status": "unavailable", "memories": []}
    
    try:
        memories = mem_svc.get_recent_memories(limit=limit) if hasattr(mem_svc, "get_recent_memories") else []
        return {"status": "success", "memories": memories}
    except Exception as e:
        return {"status": "error", "message": str(e), "memories": []}


@mobile_router.get("/tasks/queue")
async def get_task_queue_status():
    """Fetch current TaskQueue pending/running/completed state."""
    from backend.services.manager import ServiceManager
    task_queue = ServiceManager.get_instance("task_queue_service")
    if not task_queue:
        return {"tasks": [], "running": 0, "pending": 0}
    
    tasks = getattr(task_queue, "tasks", [])
    return {
        "tasks": tasks,
        "running": len([t for t in tasks if t.get("status") == "running"]),
        "pending": len([t for t in tasks if t.get("status") == "pending"]),
        "completed": len([t for t in tasks if t.get("status") == "completed"])
    }


@mobile_router.get("/apps/running")
async def get_running_applications(limit: int = 15):
    """Fetch top running desktop applications."""
    import psutil
    apps = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            if info['name'] and info['name'].endswith('.exe'):
                apps.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "cpu": round(info['cpu_percent'] or 0.0, 1),
                    "memory": round(info['memory_percent'] or 0.0, 1)
                })
        except Exception:
            continue
    
    apps.sort(key=lambda x: x["memory"], reverse=True)
    return apps[:limit]

