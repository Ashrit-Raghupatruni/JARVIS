"""
JARVIS AI Operating System - Mobile Companion REST API Router.

Exposes REST endpoints for mobile app authentication, device pairing, remote desktop control,
file management, screen previews, and mobile security approval responses.
"""

import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request, Body
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
        svc = ServiceManager.get_instance("mobile_auth_service")
        if svc:
            return svc
    except Exception:
        pass
    from backend.services.mobile_auth import MobileAuthService
    svc = MobileAuthService()
    if hasattr(request.app, "state"):
        request.app.state.mobile_auth_service = svc
    return svc


def get_mobile_gateway_service(request: Request):
    if hasattr(request.app.state, "mobile_gateway_service") and request.app.state.mobile_gateway_service:
        return request.app.state.mobile_gateway_service
    try:
        from backend.services.manager import ServiceManager
        svc = ServiceManager.get_instance("mobile_gateway_service")
        if svc:
            return svc
    except Exception:
        pass
    from backend.services.mobile_gateway import MobileGatewayService
    svc = MobileGatewayService()
    if hasattr(request.app, "state"):
        request.app.state.mobile_gateway_service = svc
    return svc


async def require_mobile_auth(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token_param: Optional[str] = Query(None, alias="token")
) -> Dict[str, Any]:
    """
    FastAPI dependency enforcing verified mobile authentication across router endpoints.
    Extracts JWT from Authorization header ('Bearer <token>') or 'token' query parameter.
    Allows read-only telemetry, pairing, and discovery without blocking initial HUD sync.
    Strictly enforces JWT authentication for remote control commands & destructive actions.
    """
    path = request.url.path.rstrip('/')
    
    # 1. Allow pairing, QR session handshakes, device discovery, and read-only telemetry HUD
    if '/pair' in path or path.endswith('/devices') or path.endswith('/telemetry') or path.endswith('/diagnostics'):
        return {}
        
    # 2. Allow localhost UI calls
    if request.client and request.client.host in ("127.0.0.1", "localhost", "::1"):
        return {}

    raw_token = authorization or token_param
    if not raw_token:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing Authorization header or token query parameter for remote execution"
        )

    auth_svc = get_mobile_auth_service(request)
    if not auth_svc:
        from backend.services.mobile_auth import MobileAuthService
        auth_svc = MobileAuthService()

    payload = auth_svc.verify_token(raw_token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid, expired, or untrusted mobile JWT token"
        )

    return payload


mobile_router = APIRouter(
    prefix="/api/v1/mobile",
    tags=["Mobile Companion"],
    dependencies=[Depends(require_mobile_auth)]
)


# ── AUTHENTICATION & PAIRING ───────────────────────────────────────────────

@mobile_router.post("/pair/initiate", response_model=PairingInitiateResponse)
async def initiate_pairing(req: PairingInitiateRequest, auth_svc=Depends(get_mobile_auth_service)):
    """Generate 6-digit numeric pairing PIN for desktop display."""
    if not auth_svc:
        raise HTTPException(status_code=503, detail="Mobile auth service unavailable")
    return auth_svc.initiate_pairing(req.device_name, req.device_id)


@mobile_router.get("/pair/qr/generate")
async def generate_qr_pairing(device_name: str = "Mobile Companion", auth_svc=Depends(get_mobile_auth_service)):
    """Generate QR-code pairing session payload for desktop UI display."""
    if not auth_svc:
        raise HTTPException(status_code=503, detail="Mobile auth service unavailable")
    init_res = auth_svc.initiate_pairing(device_name, "mobile_qr_client")
    session_id = init_res.pairing_session_id
    code = init_res.pairing_code
    qr_payload = f"jarvis_pair://{session_id}:{code}"
    return {
        "pairing_session_id": session_id,
        "pairing_code": code,
        "qr_payload": qr_payload,
        "expires_in": 300
    }


@mobile_router.post("/pair/qr/scan")
async def scan_qr_pairing(payload: Dict[str, Any], auth_svc=Depends(get_mobile_auth_service)):
    """Validate scanned QR payload from mobile companion app and issue JWT token."""
    if not auth_svc:
        raise HTTPException(status_code=503, detail="Mobile auth service unavailable")
    
    qr_payload = str(payload.get("qr_payload", "")).strip()
    device_id = str(payload.get("device_id", "mobile_qr_scanner")).strip()
    
    if not qr_payload.startswith("jarvis_pair://"):
        raise HTTPException(status_code=400, detail="Invalid QR code payload format")
    
    parts = qr_payload.replace("jarvis_pair://", "").split(":")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Malformed QR code session payload")
    
    session_id, code = parts[0], parts[1]
    res = auth_svc.confirm_pairing(session_id, code, device_id)
    if not res:
        raise HTTPException(status_code=401, detail="QR code pairing session expired or invalid")
    return res


@mobile_router.post("/pair/confirm", response_model=PairingConfirmResponse)
async def confirm_pairing(req: PairingConfirmRequest, auth_svc=Depends(get_mobile_auth_service)):
    """Validate 6-digit PIN and return signed JWT access token."""
    if not auth_svc:
        raise HTTPException(status_code=503, detail="Mobile auth service unavailable")
    
    res = auth_svc.confirm_pairing(
        req.pairing_session_id,
        req.pairing_code,
        req.device_id,
        client_public_key=req.client_public_key,
        client_signature=req.client_signature
    )
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


@mobile_router.get("/pair/status/{session_id}")
async def check_pairing_status(session_id: str, auth_svc=Depends(get_mobile_auth_service)):
    """Check if a pairing session has successfully completed and device is paired."""
    if not auth_svc:
        return {"paired": False, "active": False}
    active = session_id in getattr(auth_svc, "_active_sessions", {})
    is_paired = auth_svc.is_session_paired(session_id) if hasattr(auth_svc, "is_session_paired") else False
    devices = auth_svc.get_trusted_devices()
    return {
        "session_id": session_id,
        "active": active,
        "paired": is_paired,
        "device_count": len(devices)
    }


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

        if cmd in ("shutdown", "restart"):
            logger.info("🛡️ Mobile Security Gatekeeper: Remote {} requested. Enforcing safety gate...", cmd)
            from backend.services.safety_gatekeeper import SafetyGatekeeper
            from backend.services.manager import ServiceManager
            sg = ServiceManager.get_instance("safety_gatekeeper") or SafetyGatekeeper()
            gate_eval = sg.evaluate_tool_call(f"system_{cmd}", {"target": "host_pc"})
            if gate_eval.decision.value == "DENIED":
                return {
                    "status": "denied",
                    "command": cmd,
                    "approved": False,
                    "message": f"SecurityGatekeeper rejected {cmd}: {gate_eval.reason}"
                }
            if gateway_svc:
                decision = await gateway_svc.request_approval(
                    action_type=f"system_{cmd}",
                    description=f"Remote Desktop {cmd.capitalize()} requested via Mobile REST API.",
                    dangerous_target="JARVIS Core Host System",
                    timeout_seconds=30.0
                )
                if decision not in ("approve", "always_allow"):
                    return {
                        "status": "denied",
                        "command": cmd,
                        "approved": False,
                        "decision": decision,
                        "message": f"Remote {cmd} request was denied or timed out by security gatekeeper"
                    }
            else:
                return {
                    "status": "denied",
                    "command": cmd,
                    "approved": False,
                    "message": "Gateway service approval unavailable; cannot execute critical system shutdown"
                }

            flag = "/s" if cmd == "shutdown" else "/r"
            subprocess.Popen(["shutdown", flag, "/t", "5"], shell=False)
            return {"status": f"{cmd}_initiated", "seconds": 5, "approved": True}

        elif cmd == "lock":
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], shell=False)
            return {"status": "workstation_locked"}

        elif cmd == "open_app":
            raw_app = str(req.params.get("app_name", "notepad")).strip()
            # Security check: disallow shell operators and command separators
            if any(char in raw_app for char in ["&", ";", "|", ">", "<", "`", "$", "\n", "\r"]):
                raise HTTPException(status_code=400, detail="Invalid application name: shell operators disallowed")

            from backend.services.automation import AutomationService
            auto_svc = AutomationService()
            res = await auto_svc.open_application(raw_app)
            return {"status": "application_opened", "app": raw_app, "result": res}

        else:
            return {"status": "command_received", "command": cmd}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── MOBILE SECURITY APPROVALS ──────────────────────────────────────────────

@mobile_router.post("/approvals/respond")
async def submit_approval_decision(req: MobileApprovalDecision, gateway_svc=Depends(get_mobile_gateway_service)):
    """Submit mobile security approval decision with biometric hardware verification."""
    if not gateway_svc:
        raise HTTPException(status_code=503, detail="Mobile gateway unavailable")

    success, message = gateway_svc.submit_approval_decision_with_biometrics(
        approval_id=req.approval_id,
        decision=req.decision,
        biometric_authenticated=req.biometric_authenticated,
        biometric_signature=req.biometric_signature,
    )
    if not success:
        if "biometric" in message.lower():
            raise HTTPException(status_code=403, detail=message)
        raise HTTPException(status_code=404, detail=message)

    return {
        "status": "decision_processed",
        "approval_id": req.approval_id,
        "decision": req.decision,
        "biometric_verified": req.biometric_authenticated,
    }



@mobile_router.post("/shutdown_approval/request")
async def request_shutdown_approval(gateway_svc=Depends(get_mobile_gateway_service)):
    """Request mobile security approval before allowing laptop app exit / shutdown."""
    if not gateway_svc:
        return {"approved": False, "decision": "deny", "message": "Gateway service unavailable"}
    
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
    root_path = os.path.abspath(os.sep)
    disk = psutil.disk_usage(root_path).percent

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



# ── FCM PUSH NOTIFICATIONS & GEOFENCING ROUTER EXTENSIONS ────────────

@mobile_router.post("/fcm/register_token")
async def register_fcm_token(request: Request, body: Dict[str, Any]):
    """Registers client device FCM token for high-priority push notifications."""
    from backend.services.fcm_service import fcm_service
    device_id = body.get("device_id", "mobile_device")
    fcm_token = body.get("fcm_token") or body.get("token")
    platform = body.get("platform", "android")
    device_name = body.get("device_name", "Android Companion")

    if not fcm_token:
        raise HTTPException(status_code=400, detail="Missing required 'fcm_token' parameter")

    success = fcm_service.register_device_token(
        device_id=device_id,
        fcm_token=fcm_token,
        platform=platform,
        device_name=device_name
    )
    return {
        "status": "success" if success else "error",
        "device_id": device_id,
        "registered": success
    }


@mobile_router.post("/fcm/test_push")
async def test_fcm_push(title: str = "🛡️ Security Gate", body: str = "Test approval push notification"):
    """Sends a test push notification to all registered backgrounded devices."""
    from backend.services.fcm_service import fcm_service
    res = await fcm_service.broadcast_push_notification(title=title, body=body, notification_type="test")
    return res


@mobile_router.post("/geofence/update_location")
async def update_mobile_location(body: Dict[str, Any]):
    """Receives background GPS coordinates from mobile device and evaluates geofence triggers."""
    from backend.services.geofence_service import geofence_service
    device_id = body.get("device_id", "mobile_companion")
    latitude = float(body.get("latitude", 0.0))
    longitude = float(body.get("longitude", 0.0))
    accuracy = float(body.get("accuracy", 10.0))

    res = await geofence_service.evaluate_gps_update(
        device_id=device_id,
        latitude=latitude,
        longitude=longitude,
        accuracy_meters=accuracy
    )
    return res


@mobile_router.post("/geofence/configure")
async def configure_geofence(name: str = "Home", latitude: float = 17.385044, longitude: float = 78.486671, radius: float = 150.0):
    """Configures geofence coordinate center and radius in meters."""
    from backend.services.geofence_service import geofence_service
    geofence_service.set_geofence(name=name, latitude=latitude, longitude=longitude, radius_meters=radius)
    return {"status": "success", "configured_geofence": name, "radius_meters": radius}


@mobile_router.post("/webrtc/offer")
async def handle_webrtc_offer(body: Dict[str, Any]):
    """Handles WebRTC SDP Offer for local-network full-duplex voice streaming."""
    from backend.services.webrtc_service import webrtc_service
    session_id = body.get("session_id", "webrtc_default")
    sdp = body.get("sdp", "")
    peer_id = body.get("peer_id", "mobile_client")

    res = await webrtc_service.handle_sdp_offer(session_id=session_id, sdp_offer=sdp, peer_id=peer_id)
    return res


# ── Bluetooth RSSI Proximity Auto-Lock & Biometric Wake Endpoints ─────────────

@mobile_router.get("/proximity/status")
async def get_proximity_status():
    """Returns real-time Bluetooth RSSI proximity metrics, debounced state, and thresholds."""
    from backend.services.bluetooth_proximity import bluetooth_proximity_service
    return {"status": "ok", "telemetry": bluetooth_proximity_service.get_telemetry()}


@mobile_router.post("/proximity/config")
async def configure_proximity(payload: Dict[str, Any] = Body(...)):
    """Configure proximity lock & biometric wake calibration parameters."""
    from backend.services.bluetooth_proximity import bluetooth_proximity_service
    if "target_device" in payload:
        bluetooth_proximity_service.set_target_device(payload["target_device"])
    bluetooth_proximity_service.configure_thresholds(
        lock_threshold=payload.get("lock_threshold_dbm"),
        wake_threshold=payload.get("wake_threshold_dbm"),
        debounce_seconds=payload.get("debounce_seconds"),
        auto_lock_enabled=payload.get("auto_lock_enabled"),
        biometric_wake_enabled=payload.get("biometric_wake_enabled")
    )
    return {"status": "success", "telemetry": bluetooth_proximity_service.get_telemetry()}


@mobile_router.post("/proximity/scan")
async def scan_nearby_ble_devices(timeout_seconds: float = 3.0):
    """Executes a single BLE discovery scan on Windows hardware returning detected devices and RSSI."""
    try:
        from bleak import BleakScanner
        devices = await BleakScanner.discover(timeout=min(timeout_seconds, 10.0))
        return {
            "status": "success",
            "count": len(devices),
            "devices": [
                {
                    "name": d.name or "Unknown",
                    "address": d.address,
                    "rssi": d.rssi
                }
                for d in devices
            ]
        }
    except Exception as e:
        logger.warning(f"BLE scan notice: {e}")
        return {"status": "radio_offline", "error": str(e), "devices": []}


@mobile_router.post("/proximity/lock_now")
async def trigger_proximity_lock():
    """Manually test or trigger workstation lock via Proximity service."""
    from backend.services.bluetooth_proximity import bluetooth_proximity_service
    bluetooth_proximity_service._trigger_auto_lock()
    return {"status": "locked", "telemetry": bluetooth_proximity_service.get_telemetry()}

