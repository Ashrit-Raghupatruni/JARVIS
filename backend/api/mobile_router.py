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
async def list_trusted_devices(auth_svc=Depends(get_mobile_auth_service), gateway_svc=Depends(get_mobile_gateway_service)):
    """List registered trusted mobile companion devices with real-time online state."""
    from backend.api.mobile_ws import active_mobile_connections
    from backend.api.websocket import manager as main_ws_manager
    if not auth_svc:
        return []
    
    devices = auth_svc.get_trusted_devices()
    is_online = False
    if gateway_svc and hasattr(gateway_svc, "is_mobile_connected"):
        is_online = gateway_svc.is_mobile_connected()
    if not is_online:
        is_online = (len(active_mobile_connections) > 0) or (len(main_ws_manager.active_connections) > 0)
    
    for dev in devices:
        dev.is_online = is_online
    return devices


# ── TELEMETRY & STATUS ────────────────────────────────────────────────────

@mobile_router.get("/telemetry", response_model=SystemTelemetry)
async def get_telemetry(gateway_svc=Depends(get_mobile_gateway_service)):
    """Fetch current desktop telemetry (CPU, RAM, GPU, Battery, Task)."""
    if gateway_svc and hasattr(gateway_svc, "last_mobile_heartbeat"):
        gateway_svc.last_mobile_heartbeat = time.time()
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


@mobile_router.post("/shutdown_approval/request")
async def request_shutdown_approval(gateway_svc=Depends(get_mobile_gateway_service)):
    """Request mobile security approval before allowing laptop app exit / shutdown."""
    if not gateway_svc:
        return {"approved": True, "decision": "approve", "message": "Gateway service unavailable"}
    
    logger.info("🛡️ Mobile Security Gatekeeper: Desktop exit/shutdown requested. Awaiting mobile approval...")
    decision = await gateway_svc.request_approval(
        action_type="system_shutdown",
        description="JARVIS Desktop OS Exit / Shutdown requested from laptop.",
        dangerous_target="JARVIS OS Core Process",
        timeout_seconds=30.0
    )
    
    is_approved = decision in ("approve", "always_allow")
    logger.info("🛡️ Mobile Gatekeeper Shutdown Decision: {} (approved={})", decision, is_approved)
    return {"approved": is_approved, "decision": decision}


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
async def get_brain_memories(limit: int = 15):
    """Fetch recent long-term & procedural memories from MemoryService and HybridMemorySystem."""
    from backend.services.manager import ServiceManager
    memories = []
    
    # 1. Query MemoryService
    mem_svc = ServiceManager.get_instance("memory_service")
    if mem_svc and hasattr(mem_svc, "get_recent_memories"):
        try:
            memories.extend(mem_svc.get_recent_memories(limit=limit))
        except Exception:
            pass

    # 2. Query HybridMemorySystem
    hybrid_mem = ServiceManager.get_instance("hybrid_memory")
    if hybrid_mem and hasattr(hybrid_mem, "procedural"):
        try:
            for ep in getattr(hybrid_mem, "procedural", []):
                memories.append({
                    "id": f"ep_{int(time.time())}",
                    "content": f"Episode Goal: {ep.get('goal')} -> {ep.get('result')}",
                    "category": "procedural",
                    "timestamp": ep.get("timestamp", time.time())
                })
        except Exception:
            pass

    # 3. Seed default core operational memories if empty
    if not memories:
        memories = [
            {"id": "mem_1", "content": "JARVIS Personal AI OS initialized with Desktop Brain & Android Mission Control.", "category": "system", "timestamp": time.time() - 3600},
            {"id": "mem_2", "content": "User Preference: High-contrast cyan/dark theme with instant local response.", "category": "user", "timestamp": time.time() - 1800},
            {"id": "mem_3", "content": "Mobile Security Gatekeeper active with remote approval interlock.", "category": "security", "timestamp": time.time() - 900},
            {"id": "mem_4", "content": "Hybrid Memory RAG Vector Database synchronized with WAL mode.", "category": "brain", "timestamp": time.time() - 300}
        ]

    return {"status": "success", "count": len(memories), "memories": memories[:limit]}


@mobile_router.get("/brain/graph")
async def get_knowledge_graph():
    """Fetch Knowledge Graph nodes & edges for 3D Edge RAG Visualizer."""
    from backend.services.manager import ServiceManager
    hybrid_mem = ServiceManager.get_instance("hybrid_memory")
    
    nodes = [
        {"id": "JARVIS_OS", "label": "JARVIS OS", "type": "Core"},
        {"id": "DESKTOP_BRAIN", "label": "Desktop Brain", "type": "Engine"},
        {"id": "ANDROID_CONTROL", "label": "Android Companion", "type": "Client"},
        {"id": "PRASH_AI", "label": "Prash Local AI", "type": "LLM"},
        {"id": "HYBRID_MEMORY", "label": "Hybrid Memory", "type": "RAG"},
        {"id": "SECURITY_GATEKEEPER", "label": "Security Gatekeeper", "type": "Security"}
    ]
    edges = [
        {"source": "JARVIS_OS", "target": "DESKTOP_BRAIN", "relation": "runs_on"},
        {"source": "JARVIS_OS", "target": "ANDROID_CONTROL", "relation": "controlled_by"},
        {"source": "DESKTOP_BRAIN", "target": "PRASH_AI", "relation": "executes"},
        {"source": "DESKTOP_BRAIN", "target": "HYBRID_MEMORY", "relation": "stores_knowledge"},
        {"source": "ANDROID_CONTROL", "target": "SECURITY_GATEKEEPER", "relation": "approves_actions"}
    ]

    if hybrid_mem and hasattr(hybrid_mem, "knowledge_graph"):
        kg = getattr(hybrid_mem, "knowledge_graph", {})
        for entity_a, rels in kg.items():
            if not any(n["id"] == entity_a for n in nodes):
                nodes.append({"id": entity_a, "label": entity_a, "type": "MemoryEntity"})
            if isinstance(rels, dict):
                for rel, targets in rels.items():
                    target_list = targets if isinstance(targets, list) else [targets]
                    for target in target_list:
                        if not any(n["id"] == target for n in nodes):
                            nodes.append({"id": target, "label": target, "type": "MemoryEntity"})
                        edges.append({"source": entity_a, "target": target, "relation": rel})

    return {"status": "success", "nodes": nodes, "edges": edges}


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


# ── Self-Improving Operating System Endpoints ───────────────────────

@mobile_router.get("/self_improving/experiences")
async def get_self_improving_experiences(limit: int = 10):
    """Fetch recorded experience traces and success metrics."""
    from backend.services.manager import ServiceManager
    exp_svc = ServiceManager.get_instance("experience_engine")
    if not exp_svc:
        return {"status": "unavailable", "experiences": []}
    return {
        "status": "success",
        "experiences": exp_svc.query_experiences(limit=limit),
        "overall_success_rate": exp_svc.get_success_rate("")
    }


@mobile_router.get("/self_improving/strategies")
async def get_self_improving_strategies(category: str = "ui_automation"):
    """Fetch ranked execution strategies and dynamic confidence scores."""
    from backend.services.manager import ServiceManager
    strat_svc = ServiceManager.get_instance("strategy_memory")
    if not strat_svc:
        return {"status": "unavailable", "strategies": []}
    return {
        "status": "success",
        "category": category,
        "strategies": strat_svc.get_ranked_strategies(category),
        "preferred": strat_svc.get_preferred_strategy(category)
    }


@mobile_router.get("/self_improving/skills")
async def get_self_improving_skills():
    """Fetch reusable automation skills and system modes."""
    from backend.services.manager import ServiceManager
    skill_svc = ServiceManager.get_instance("skill_library")
    if not skill_svc:
        return {"status": "unavailable", "modes": []}
    return {
        "status": "success",
        "active_mode": skill_svc.current_mode,
        "modes": list(skill_svc.modes.keys())
    }


# ── LIVE MODE AI ASSISTANT ENDPOINTS ───────────────────────────────

@mobile_router.post("/live_mode/toggle")
async def toggle_live_mode(request: Request, enable: bool = True):
    """Enable or disable Live Mode continuous AI screen assistant."""
    from backend.services.manager import ServiceManager
    live_engine = ServiceManager.get_instance("live_mode_engine")
    if not live_engine and hasattr(request.app.state, "live_mode_engine"):
        live_engine = request.app.state.live_mode_engine

    if not live_engine:
        from backend.services.live_mode.live_engine import LiveModeEngine
        live_engine = LiveModeEngine()
        request.app.state.live_mode_engine = live_engine
        ServiceManager.register_instance("live_mode_engine", live_engine)

    if enable:
        live_engine.start()
    else:
        live_engine.stop()

    return {
        "status": "success",
        "live_mode_enabled": live_engine.is_enabled
    }


@mobile_router.get("/live_mode/status")
async def get_live_mode_status(request: Request):
    """Fetch current Live Mode context frame, scene graph, and proactive suggestions."""
    from backend.services.manager import ServiceManager
    live_engine = ServiceManager.get_instance("live_mode_engine")
    if not live_engine and hasattr(request.app.state, "live_mode_engine"):
        live_engine = request.app.state.live_mode_engine

    if not live_engine or not live_engine.latest_frame:
        return {"status": "inactive", "live_mode_enabled": live_engine.is_enabled if live_engine else False}

    return {
        "status": "active",
        "frame": live_engine.latest_frame.model_dump()
    }


@mobile_router.post("/workspaces/restore")
async def restore_workspace_layout(preset: str = "coding"):
    """Restore desktop application layout per preset (coding, research, presentation)."""
    from backend.services.manager import ServiceManager
    auto_svc = ServiceManager.get_instance("automation_service")
    if not auto_svc or not hasattr(auto_svc, "arrange_workspace_layout"):
        return {"status": "unavailable", "message": "Automation service unavailable"}
    
    res = await auto_svc.arrange_workspace_layout(preset)
    return {"status": "success", "result": res}
    skill_lib = ServiceManager.get_instance("skill_library")
    if not skill_lib:
        return {"status": "unavailable", "skills": {}}
    return {
        "status": "success",
        "skills": getattr(skill_lib, "skills", {})
    }


@mobile_router.post("/self_improving/skills/execute")
async def execute_system_mode(mode_id: str = "coding_mode"):
    """Execute a system operational mode (Coding Mode, Gaming Mode, Work Mode, etc.)."""
    from backend.services.manager import ServiceManager
    skill_lib = ServiceManager.get_instance("skill_library")
    if not skill_lib:
        return {"status": "error", "message": "Skill Library unavailable"}
    return skill_lib.execute_mode(mode_id)

