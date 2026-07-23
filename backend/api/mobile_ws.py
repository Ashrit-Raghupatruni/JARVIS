"""
JARVIS AI Operating System - Mobile WebSocket Router.

Handles real-time WebSocket connection for streaming telemetry,
chat responses, approval notifications, remote actions (lock PC, screenshot, status),
and voice/text prompts from phone.
"""

import json
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
    """Real-time Mobile Companion WebSocket Handler."""
    await websocket.accept()
    active_mobile_connections.add(websocket)
    logger.info("📱 Mobile companion WebSocket connected: {}", websocket.client)

    # Start telemetry broadcasting loop (every 2s)
    async def telemetry_loop():
        try:
            while True:
                cpu = psutil.cpu_percent(interval=None)
                ram_info = psutil.virtual_memory()
                ram = ram_info.percent
                disk = psutil.disk_usage('C:\\').percent
                battery_obj = psutil.sensors_battery()
                battery = battery_obj.percent if battery_obj else 100
                plugged = battery_obj.power_plugged if battery_obj else True

                await websocket.send_json({
                    "type": "telemetry",
                    "data": {
                        "cpu_percent": cpu,
                        "ram_percent": ram,
                        "disk_percent": disk,
                        "battery_percent": battery,
                        "battery_plugged": plugged,
                        "active_llm_provider": "Ollama (qwen2.5-coder:3b)",
                        "active_task": "Mission Control Active"
                    }
                })
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
                    logger.info("🔒 Locking Windows workstation from mobile command...")
                    try:
                        ctypes.windll.user32.LockWorkStation()
                        await websocket.send_json({
                            "type": "response",
                            "status": "success",
                            "message": "🔒 Desktop Workstation Locked"
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
                    disk = psutil.disk_usage('C:\\').percent
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

            # ── 2. PROMPT / CHAT FROM PHONE ─────────────────────────────
            elif msg_type == "chat" or text_query:
                query = text_query or message.get("query", "")
                logger.info("💬 Mobile AI prompt received: '{}'", query)

                await websocket.send_json({
                    "type": "chat_response",
                    "status": "thinking",
                    "text": f"Processing prompt: '{query}'..."
                })

                # Process query via Planner or LLM Service
                planner = getattr(websocket.app.state, "planner_agent", None)
                llm = getattr(websocket.app.state, "llm_service", None)

                answer = ""
                try:
                    if planner and hasattr(planner, "plan_and_execute"):
                        async for ws_msg in planner.plan_and_execute(query):
                            data = ws_msg.data if hasattr(ws_msg, "data") else (ws_msg.get("data", {}) if isinstance(ws_msg, dict) else {})
                            if isinstance(data, dict) and "text" in data:
                                answer = data["text"]
                            elif hasattr(data, "text"):
                                answer = data.text
                    
                    if not answer and llm:
                        if hasattr(llm, "generate_response"):
                            answer = await llm.generate_response(query)
                        elif hasattr(llm, "generate"):
                            answer = await llm.generate(query)
                    
                    if not answer:
                        answer = f"JARVIS received your prompt: '{query}'. System operational."
                except Exception as e:
                    logger.error("Error generating response for mobile query: {}", e)
                    if llm and hasattr(llm, "generate_response"):
                        try:
                            answer = await llm.generate_response(query)
                        except Exception:
                            answer = f"Received: '{query}' — Processing complete."
                    else:
                        answer = f"Received: '{query}' — Processing complete."

                # Synthesize TTS Audio for Mobile Voice Response
                audio_b64 = ""
                try:
                    import base64
                    import edge_tts
                    
                    # Clean text for TTS (remove markdown asterisks)
                    clean_text = answer.replace('*', '').replace('#', '').strip()
                    if clean_text:
                        communicate = edge_tts.Communicate(text=clean_text[:300], voice="en-US-ChristopherNeural")
                        audio_chunks = []
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                audio_chunks.append(chunk["data"])
                        if audio_chunks:
                            audio_b64 = base64.b64encode(b"".join(audio_chunks)).decode("utf-8")
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
        telemetry_task.cancel()


@mobile_ws_router.websocket("/ws")
async def ws_endpoint_1(websocket: WebSocket):
    await handle_mobile_ws(websocket)


@mobile_ws_router.websocket("/ws/stream")
async def ws_endpoint_2(websocket: WebSocket):
    await handle_mobile_ws(websocket)
