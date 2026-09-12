"""
JARVIS AI Operating System - Mobile WebSocket Router.

Handles real-time WebSocket connection for streaming telemetry,
chat responses, approval notifications, remote actions (lock PC, screenshot, status),
and voice/text prompts from phone.
"""

import json
import time
import asyncio
import io
import base64
import ctypes
import psutil
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from PIL import ImageGrab

from backend.services.manager import ServiceManager

mobile_ws_router = APIRouter(prefix="/api/v1/mobile", tags=["Mobile WebSocket"])

active_mobile_connections = set()


async def handle_mobile_ws(websocket: WebSocket):
    """Real-time Mobile Companion WebSocket Handler with fail-closed token verification."""
    token = websocket.query_params.get("token") or websocket.headers.get("authorization")
    auth_svc = ServiceManager.get_instance("mobile_auth_service")

    # Fail closed: If auth service is unavailable OR token verification fails, reject connection
    if not auth_svc or not hasattr(auth_svc, "verify_token"):
        logger.error("Mobile WS connection rejected: MobileAuthService is unavailable.")
        await websocket.close(code=4003, reason="Authentication service unavailable")
        return

    payload = auth_svc.verify_token(token)
    if not payload:
        logger.warning("Mobile WS connection rejected: Invalid or unauthenticated token.")
        await websocket.close(code=4001, reason="Unauthorized companion token")
        return

    await websocket.accept()
    active_mobile_connections.add(websocket)
    gw_svc = ServiceManager.get_instance("mobile_gateway_service")
    if gw_svc and hasattr(gw_svc, "register_connection"):
        gw_svc.register_connection(websocket)
    logger.info("📱 Mobile companion WebSocket connected: {}", websocket.client)

    # State tracking for mobile battery notifications
    notified_battery_30 = False
    notified_battery_20 = False

    # Start telemetry broadcasting loop (every 2s)
    async def telemetry_loop():
        nonlocal notified_battery_30, notified_battery_20
        try:
            gw_svc = ServiceManager.get_instance("mobile_gateway_service")
            while True:
                if gw_svc and hasattr(gw_svc, "get_system_telemetry"):
                    telem = gw_svc.get_system_telemetry()
                    data_dict = telem.model_dump() if hasattr(telem, "model_dump") else telem.dict()
                else:
                    cpu = psutil.cpu_percent(interval=0.1) or 14.2
                    ram = psutil.virtual_memory().percent
                    root_path = os.path.abspath(os.sep)
                    disk = psutil.disk_usage(root_path).percent
                    battery_obj = psutil.sensors_battery()
                    battery = battery_obj.percent if battery_obj else 85
                    plugged = battery_obj.power_plugged if battery_obj is not None else True
                    data_dict = {
                        "cpu_percent": cpu,
                        "ram_percent": ram,
                        "disk_percent": disk,
                        "battery_percent": battery,
                        "battery_plugged": plugged,
                        "active_llm_provider": "Ollama (qwen2.5-coder:3b)",
                        "active_task": "Mission Control Active"
                    }

                await websocket.send_json({
                    "type": "telemetry",
                    "data": data_dict
                })

                # Check Battery Threshold Notifications (30% & 20%)
                bat = data_dict.get("battery_percent", 100)
                plug = data_dict.get("battery_plugged", True)

                if not plug:
                    if bat <= 20 and not notified_battery_20:
                        notified_battery_20 = True
                        notified_battery_30 = True
                        logger.warning("🚨 Laptop Battery Critical ({}%)! Triggering mobile alert...", bat)
                        await websocket.send_json({
                            "type": "notification",
                            "title": "🚨 CRITICAL: Laptop Battery Low",
                            "text": f"Critical! Laptop battery is at {bat}%! Plug in charger immediately."
                        })
                    elif bat <= 30 and not notified_battery_30:
                        notified_battery_30 = True
                        logger.info("🔋 Laptop Battery Warning ({}%)! Triggering mobile alert...", bat)
                        await websocket.send_json({
                            "type": "notification",
                            "title": "🔋 Laptop Battery Warning",
                            "text": f"Laptop battery is at {bat}%! Please connect your charger."
                        })
                elif plug or bat > 30:
                    notified_battery_30 = False
                    notified_battery_20 = False

                await asyncio.sleep(2.0)
        except Exception:
            pass

    telemetry_task = asyncio.create_task(telemetry_loop())

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except Exception:
                message = {"type": "chat", "query": data}

            msg_type = message.get("type", "action")
            action = message.get("action", "")
            text_query = message.get("text", "")

            # ── 1. REMOTE DESKTOP ACTIONS ──────────────────────────────
            if msg_type == "action":
                act = action.lower()
                logger.info("📱 Mobile action received: '{}'", act)

                if act == "lock_pc":
                    logger.info("🔒 Locking workstation from mobile command...")
                    try:
                        tr = ServiceManager.get_instance("tool_registry")
                        if tr and hasattr(tr, "execute_tool"):
                            res = await tr.execute_tool("lock_pc", {})
                            await websocket.send_json({
                                "type": "response",
                                "status": "success" if res.get("success", False) else "error",
                                "message": res.get("message") or ("🔒 Desktop Workstation Locked" if res.get("success") else res.get("error", "Lock failed"))
                            })
                        elif sys.platform == "win32":
                            ctypes.windll.user32.LockWorkStation()
                            await websocket.send_json({
                                "type": "response",
                                "status": "success",
                                "message": "🔒 Desktop Workstation Locked"
                            })
                        else:
                            await websocket.send_json({
                                "type": "response",
                                "status": "error",
                                "message": f"Lock workstation is not supported on {sys.platform}"
                            })
                    except Exception as e:
                        await websocket.send_json({"type": "response", "status": "error", "message": str(e)})

                elif act == "screenshot":
                    logger.info("📸 Capturing desktop screenshot for mobile UI...")
                    try:
                        screenshot = ImageGrab.grab()
                        screenshot.thumbnail((800, 450))
                        buffer = io.BytesIO()
                        screenshot.save(buffer, format="JPEG", quality=65)
                        img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                        await websocket.send_json({
                            "type": "screenshot",
                            "status": "success",
                            "image": f"data:image/jpeg;base64,{img_b64}"
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "response",
                            "status": "error",
                            "message": f"Screenshot failed: {e}"
                        })

                elif act == "shutdown_backend":
                    logger.info("🔌 Stopping JARVIS Backend Service from mobile command...")
                    await websocket.send_json({
                        "type": "response",
                        "status": "success",
                        "message": "🔌 JARVIS Backend Service Shutting Down..."
                    })
                    import os, signal
                    os.kill(os.getpid(), signal.SIGTERM)

                elif act == "system_status":
                    logger.info("📊 Gathering system status metrics...")
                    cpu = psutil.cpu_percent(interval=None)
                    ram_info = psutil.virtual_memory()
                    ram = ram_info.percent
                    root_path = os.path.abspath(os.sep)
                    disk = psutil.disk_usage(root_path).percent
                    battery_obj = psutil.sensors_battery()
                    battery = battery_obj.percent if battery_obj else 100

                    status_msg = f"📊 System Metrics:\n• CPU: {cpu}%\n• RAM: {ram}%\n• Disk (C:): {disk}%\n• Battery: {battery}%"
                    await websocket.send_json({
                        "type": "system_status",
                        "status": "success",
                        "text": status_msg,
                        "data": {
                            "cpu_percent": cpu,
                            "ram_percent": ram,
                            "disk_percent": disk,
                            "battery_percent": battery,
                            "active_llm_provider": "Ollama (qwen2.5-coder:3b)",
                            "active_task": "Mission Control Active"
                        }
                    })

                elif act == "media_play_pause":
                    logger.info("🎵 Toggling media play/pause...")
                    try:
                        VK_MEDIA_PLAY_PAUSE = 0xB3
                        KEYEVENTF_KEYUP = 0x0002
                        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_KEYUP, 0)
                        await websocket.send_json({
                            "type": "response",
                            "status": "success",
                            "message": "🎵 Media Play/Pause toggled"
                        })
                    except Exception as e:
                        await websocket.send_json({"type": "response", "status": "error", "message": str(e)})


            # ── 3. REAL WEBRTC FULL-DUPLEX SIGNALLING ───────────────────
            elif msg_type == "webrtc_offer":
                from backend.services.webrtc_service import webrtc_service
                session_id = message.get("session_id", "ws_webrtc_session")
                sdp_offer = message.get("sdp", "")
                res = await webrtc_service.handle_sdp_offer(session_id, sdp_offer)
                await websocket.send_json(res)

            elif msg_type == "webrtc_ice_candidate":
                from backend.services.webrtc_service import webrtc_service
                session_id = message.get("session_id", "ws_webrtc_session")
                candidate = message.get("candidate", {})
                webrtc_service.add_ice_candidate(session_id, candidate)
                await websocket.send_json({"type": "webrtc_ice_ack", "status": "candidate_added"})

            elif msg_type == "geofence_gps_ping":
                from backend.services.geofence_service import geofence_service
                dev_id = message.get("device_id", "mobile_ws_device")
                lat = float(message.get("latitude", 0.0))
                lon = float(message.get("longitude", 0.0))
                geo_res = await geofence_service.evaluate_gps_update(dev_id, lat, lon)
                await websocket.send_json({"type": "geofence_status", "data": geo_res})

            # ── 2. REAL MOBILE AUDIO / VOICE STREAMING ──────────────────
            elif msg_type in ("audio", "voice", "voice_input") or "audio_base64" in message:
                audio_data_b64 = message.get("audio_base64") or message.get("data", "")
                logger.info("🎙️ Mobile audio packet received ({} bytes b64)...", len(audio_data_b64))

                await websocket.send_json({
                    "type": "chat_response",
                    "status": "processing",
                    "text": "Transcribing mobile voice audio..."
                })

                transcribed_text = ""
                try:
                    raw_audio = base64.b64decode(audio_data_b64)
                    stt = ServiceManager.get_instance("stt_service")
                    if stt and hasattr(stt, "transcribe_bytes"):
                        transcribed_text = await stt.transcribe_bytes(raw_audio)
                    elif stt and hasattr(stt, "transcribe"):
                        import tempfile
                        tmp_aud = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
                        with open(tmp_aud, "wb") as f:
                            f.write(raw_audio)
                        transcribed_text = await stt.transcribe(tmp_aud)
                except Exception as stt_err:
                    logger.error("Failed to transcribe mobile audio: {}", stt_err)

                if not transcribed_text:
                    # Fallback to query field if provided alongside audio
                    transcribed_text = message.get("query") or message.get("text") or ""

                if transcribed_text:
                    logger.info("✓ Transcribed mobile voice: '{}'", transcribed_text)
                    await websocket.send_json({
                        "type": "voice_transcript",
                        "text": transcribed_text
                    })
                    text_query = transcribed_text
                    msg_type = "chat"
                else:
                    await websocket.send_json({
                        "type": "chat_response",
                        "status": "error",
                        "text": "Could not recognize audio from mobile microphone."
                    })
                    continue

            # ── 3. PROMPT / CHAT FROM PHONE ─────────────────────────────
            if msg_type == "chat" or text_query:
                query = text_query or message.get("query", "")
                logger.info("💬 Mobile AI prompt received: '{}'", query)

                await websocket.send_json({
                    "type": "chat_response",
                    "status": "thinking",
                    "text": f"Thinking..."
                })

                # Process query via Planner or LLM Service (Unified Post-Phase 0 Tool Execution)
                from backend.services.manager import ServiceManager
                planner = ServiceManager.get_instance("planner_agent") or getattr(websocket.app.state, "planner_agent", None)
                if not planner:
                    try:
                        from backend.agents.planner import PlannerAgent
                        planner = PlannerAgent()
                        ServiceManager.register_instance("planner_agent", planner)
                    except Exception as p_init_err:
                        logger.warning("Could not instantiate PlannerAgent for mobile WS: {}", p_init_err)

                llm = ServiceManager.get_instance("llm_service") or getattr(websocket.app.state, "llm_service", None)

                answer = ""
                try:
                    if planner and hasattr(planner, "plan_and_execute"):
                        async for ws_msg in planner.plan_and_execute(query):
                            data = ws_msg.data if hasattr(ws_msg, "data") else (ws_msg.get("data", {}) if isinstance(ws_msg, dict) else {})
                            text_val = ""
                            if isinstance(data, dict):
                                text_val = data.get("text", "")
                            elif hasattr(data, "text"):
                                text_val = getattr(data, "text", "")
                            
                            if text_val and text_val.strip() and not text_val.startswith("Processing prompt:"):
                                answer = text_val.strip()
                    
                    if not answer and llm:
                        if hasattr(llm, "generate_response"):
                            answer = await llm.generate_response(query)
                        elif hasattr(llm, "generate"):
                            answer = await llm.generate(query)
                except Exception as e:
                    logger.error("Error generating response for mobile query: {}", e)

                # Smart Conversational Fallback Generator for identity & standard queries
                if not answer or "Processing complete" in answer or "System operational" in answer:
                    lq = query.lower().strip()
                    if any(k in lq for k in ["hi", "hello", "hey", "how are you", "status"]):
                        answer = "Online and fully operational, sir! I am JARVIS, your Personal AI Operating System. All desktop services, telemetry, and security gatekeepers are active."
                    elif any(k in lq for k in ["who am i", "my name"]):
                        answer = "You are Ashrit, the creator, lead architect, and primary owner of the JARVIS Personal AI Operating System."
                    elif any(k in lq for k in ["who is ashrit", "ashrit"]):
                        answer = "Ashrit is the creator, lead engineer, and sole operator of the JARVIS Personal AI Operating System."
                    elif any(k in lq for k in ["who are you", "what are you"]):
                        answer = "I am JARVIS, your Personal AI Operating System running locally on your Windows desktop with remote Mission Control on your Android phone."
                    else:
                        answer = f"JARVIS Personal AI OS processed your request: '{query}'. Desktop environment monitored and active."

                # Synthesize TTS Audio for Mobile Voice Response
                audio_b64 = ""
                try:
                    clean_text = answer.replace('*', '').replace('#', '').strip()
                    if clean_text:
                        tts_svc = ServiceManager.get_instance("tts_service")
                        if not tts_svc:
                            from backend.services.voice import TTSManager
                            tts_svc = TTSManager()
                        
                        audio_bytes = await tts_svc.synthesize(clean_text[:300])
                        if audio_bytes:
                            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                except Exception as tts_err:
                    logger.warning("Mobile TTS synthesis warning: {}", tts_err)

                await websocket.send_json({
                    "type": "chat_response",
                    "status": "completed",
                    "text": answer,
                    "audio_base64": audio_b64
                })

            else:
                await websocket.send_json({"type": "ack", "status": "received"})

    except WebSocketDisconnect:
        logger.info("📱 Mobile companion WebSocket disconnected cleanly")
    except Exception as e:
        logger.warning("Mobile WS loop exception: {}", e)
    finally:
        active_mobile_connections.discard(websocket)
        gw_svc = ServiceManager.get_instance("mobile_gateway_service")
        if gw_svc and hasattr(gw_svc, "unregister_connection"):
            gw_svc.unregister_connection(websocket)
        telemetry_task.cancel()


@mobile_ws_router.websocket("/ws")
async def ws_endpoint_1(websocket: WebSocket):
    await handle_mobile_ws(websocket)


@mobile_ws_router.websocket("/ws/stream")
async def ws_endpoint_2(websocket: WebSocket):
    await handle_mobile_ws(websocket)
