"""
WebSocket endpoint for JARVIS.

Handles real-time bidirectional communication between the Electron
frontend and the Python backend. Routes audio streams, text commands,
and control messages through the voice pipeline.
"""

import asyncio
import json
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from backend.models.schemas import WSMessage

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Active connections: {len(self.active_connections)}")

    async def send_message(self, websocket: WebSocket, message: WSMessage) -> None:
        """Send a typed message to a specific client."""
        try:
            await websocket.send_json(message.model_dump(mode="json"))
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def broadcast(self, message: WSMessage) -> None:
        """Send a message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message.model_dump(mode="json"))
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for JARVIS communication.

    Protocol:
    - Text frames: JSON messages with {type, data, timestamp}
    - Binary frames: Raw audio data (16kHz, 16-bit, mono PCM)

    Incoming message types:
    - audio_data: Audio chunk for processing
    - command: Text command
    - push_to_talk_start: Begin PTT recording
    - push_to_talk_stop: End PTT recording and process
    - interrupt: Stop current TTS playback
    - settings: Update runtime settings
    - ping: Heartbeat

    Outgoing message types:
    - status: Assistant state changes
    - transcript: Speech-to-text results
    - response: AI response text
    - tts_audio: Audio chunks for playback
    - agent_progress: Multi-step task progress
    - wake_word: Wake word detection event
    - error: Error messages
    - pong: Heartbeat response
    """
    app = websocket.app
    await manager.connect(websocket)

    # Store manager on app state for other routes to access
    app.state.connection_manager = manager

    # Get voice agent
    voice_agent = getattr(app.state, "voice_agent", None)

    # Send initial status
    await manager.send_message(
        websocket,
        WSMessage(type="status", data={"state": "idle", "message": "JARVIS online"}),
    )

    # Decoupled voice action queue and worker task to prevent WebSocket blocking
    voice_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    async def voice_worker():
        while True:
            try:
                action_type, payload = await voice_queue.get()
                if not voice_agent:
                    voice_queue.task_done()
                    continue

                if action_type == "audio":
                    async for response_msg in voice_agent.handle_audio_chunk(payload):
                        await manager.send_message(websocket, response_msg)
                elif action_type == "ptt_start":
                    async for response_msg in voice_agent.handle_push_to_talk_start():
                        await manager.send_message(websocket, response_msg)
                elif action_type == "ptt_stop":
                    async for response_msg in voice_agent.handle_push_to_talk_stop():
                        await manager.send_message(websocket, response_msg)
                elif action_type == "text_command":
                    async for response_msg in voice_agent.handle_text_command(payload):
                        await manager.send_message(websocket, response_msg)

                voice_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket voice worker: {e}")
                try:
                    voice_queue.task_done()
                except ValueError:
                    pass

    worker_task = asyncio.create_task(voice_worker())

    try:
        while True:
            try:
                # Receive message (text or binary)
                message = await asyncio.wait_for(
                    websocket.receive(), timeout=60.0
                )
            except asyncio.TimeoutError:
                # Send heartbeat on timeout
                try:
                    await websocket.send_json(
                        WSMessage(type="pong", data={"timestamp": time.time()}).model_dump(mode="json")
                    )
                except Exception:
                    break
                continue

            if "text" in message:
                # JSON text message
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type", "")
                    msg_data = data.get("data", {})

                    if msg_type in ("ping", "heartbeat"):
                        await websocket.send_json(
                            WSMessage(
                                type="pong", data={"timestamp": time.time()}
                            ).model_dump(mode="json")
                        )

                    elif msg_type in ("command", "text_command"):
                        text = msg_data.get("text", "")
                        if text:
                            await voice_queue.put(("text_command", text))

                    elif msg_type == "push_to_talk_start":
                        # Drain the queue to immediately prepare for new PTT
                        while not voice_queue.empty():
                            try:
                                voice_queue.get_nowait()
                                voice_queue.task_done()
                            except (asyncio.QueueEmpty, ValueError):
                                break
                        await voice_queue.put(("ptt_start", None))

                    elif msg_type == "push_to_talk_stop":
                        await voice_queue.put(("ptt_stop", None))

                    elif msg_type == "interrupt":
                        # Process interrupt IMMEDIATELY to stop speaking instantly
                        if voice_agent:
                            async for msg in voice_agent.handle_interrupt():
                                await manager.send_message(websocket, msg)
                        # Drain the queue
                        while not voice_queue.empty():
                            try:
                                voice_queue.get_nowait()
                                voice_queue.task_done()
                            except (asyncio.QueueEmpty, ValueError):
                                break

                    elif msg_type == "get_tasks":
                        t_q = getattr(app.state, "task_queue_service", None)
                        if t_q:
                            tasks_summary = t_q.get_queue_summary()
                            await manager.send_message(websocket, WSMessage(type="status", data={"task_queue": tasks_summary}))

                    elif msg_type == "reorder_tasks":
                        order = msg_data.get("order", [])
                        t_q = getattr(app.state, "task_queue_service", None)
                        if t_q:
                            updated_queue = await t_q.reorder_tasks(order)
                            await manager.send_message(websocket, WSMessage(type="status", data={"task_queue": updated_queue}))

                    elif msg_type == "pause_task":
                        task_id = str(msg_data.get("id", ""))
                        t_q = getattr(app.state, "task_queue_service", None)
                        if t_q:
                            await t_q.pause_task(task_id)
                            await manager.send_message(websocket, WSMessage(type="status", data={"task_queue": t_q.get_queue_summary()}))

                    elif msg_type == "resume_task":
                        task_id = str(msg_data.get("id", ""))
                        t_q = getattr(app.state, "task_queue_service", None)
                        if t_q:
                            await t_q.resume_task(task_id)
                            await manager.send_message(websocket, WSMessage(type="status", data={"task_queue": t_q.get_queue_summary()}))

                    elif msg_type == "cancel_task":
                        task_id = str(msg_data.get("id", ""))
                        t_q = getattr(app.state, "task_queue_service", None)
                        if t_q:
                            await t_q.cancel_task(task_id)
                            await manager.send_message(websocket, WSMessage(type="status", data={"task_queue": t_q.get_queue_summary()}))

                    elif msg_type == "add_task":
                        title = str(msg_data.get("title", "Custom Task"))
                        cmd = str(msg_data.get("command", ""))
                        pri = int(msg_data.get("priority", 1))
                        t_q = getattr(app.state, "task_queue_service", None)
                        if t_q:
                            await t_q.add_task(title, cmd, pri)
                            await manager.send_message(websocket, WSMessage(type="status", data={"task_queue": t_q.get_queue_summary()}))

                    elif msg_type == "settings":
                        # Handle settings update immediately
                        logger.info(f"Settings update received: {msg_data}")
                        
                        # Voice & Serious Mode settings
                        voice_settings = msg_data.get("voice", {})
                        if voice_agent:
                            if "seriousMode" in voice_settings:
                                voice_agent.serious_mode = bool(voice_settings["seriousMode"])
                                logger.info(f"Updated VoiceAgent seriousMode to: {voice_agent.serious_mode}")
                            if "bargeInEnabled" in voice_settings:
                                voice_agent.barge_in_enabled = bool(voice_settings["bargeInEnabled"])
                            if "bargeInSensitivity" in voice_settings:
                                voice_agent.barge_in_sensitivity = float(voice_settings["bargeInSensitivity"])
                            if "micSensitivity" in voice_settings:
                                voice_agent.mic_sensitivity = float(voice_settings["micSensitivity"])

                        # Wake word service updates
                        if hasattr(app.state, "wake_word_service") and app.state.wake_word_service:
                            ww_service = app.state.wake_word_service
                            if "wakeWordSensitivity" in voice_settings:
                                ww_service.set_threshold(float(voice_settings["wakeWordSensitivity"]))

                        # Clap service updates
                        if hasattr(app.state, "clap_service") and app.state.clap_service:
                            clap_service = app.state.clap_service
                            if "clapEnabled" in voice_settings:
                                clap_enabled = bool(voice_settings["clapEnabled"])
                                clap_service.settings.CLAP_ENABLED = clap_enabled
                                if clap_enabled:
                                    clap_service.start()
                                else:
                                    clap_service.stop()
                            if "clapMode" in voice_settings:
                                clap_service.settings.CLAP_MODE = str(voice_settings["clapMode"])
                            if "clapSensitivity" in voice_settings:
                                clap_service.settings.CLAP_SENSITIVITY = float(voice_settings["clapSensitivity"])

                        if hasattr(app.state, "llm_service") and app.state.llm_service:
                            llm = app.state.llm_service
                            ai_settings = msg_data.get("ai", {})
                            
                            # Update model/provider
                            if "model" in ai_settings:
                                model = ai_settings["model"]
                                if model.startswith("gemini"):
                                    llm.primary_provider = "gemini"
                                    llm.gemini_model_name = model
                                elif model.startswith("gpt") or model.startswith("o1"):
                                    llm.primary_provider = "openai"
                                    llm.openai_model_name = model
                                elif "/" in model:
                                    llm.primary_provider = "openrouter"
                                    llm.openrouter_model_name = model
                                else:
                                    llm.primary_provider = "ollama"
                                    llm.ollama_model_name = model
                                logger.info(f"Updated LLM provider to {llm.primary_provider} and model to {model}")

                            # Update API keys
                            if "openrouterApiKey" in ai_settings:
                                or_key = ai_settings["openrouterApiKey"]
                                if or_key and or_key.strip():
                                    llm.openrouter_key = or_key.strip()
                                    from openai import AsyncOpenAI
                                    llm.openrouter_client = AsyncOpenAI(
                                        base_url="https://openrouter.ai/api/v1",
                                        api_key=llm.openrouter_key,
                                        default_headers={
                                            "HTTP-Referer": "https://github.com/Ashrit-Raghupatruni/JARVIS",
                                            "X-Title": "JARVIS AI",
                                        }
                                    )
                                    logger.info("✓ Re-initialized OpenRouter client with new key")

                            if "openaiApiKey" in ai_settings:
                                oa_key = ai_settings["openaiApiKey"]
                                if oa_key and oa_key.strip():
                                    llm.openai_key = oa_key.strip()
                                    from openai import AsyncOpenAI
                                    llm.openai_client = AsyncOpenAI(api_key=llm.openai_key)
                                    logger.info("✓ Re-initialized OpenAI client with new key")

                        # Update selected monitor in screen service if provided
                        display_settings = msg_data.get("display", {})
                        if "selectedMonitor" in display_settings and hasattr(app.state, "screen_service") and app.state.screen_service:
                            sel_mon = display_settings["selectedMonitor"]
                            if sel_mon is None or sel_mon == "all":
                                app.state.screen_service.selected_monitor = None
                            else:
                                try:
                                    app.state.screen_service.selected_monitor = int(sel_mon)
                                except (ValueError, TypeError):
                                    app.state.screen_service.selected_monitor = None
                            logger.info(f"Updated selected monitor to: {app.state.screen_service.selected_monitor}")

                        current_state = voice_agent.state.value if voice_agent else "idle"
                        await websocket.send_json(
                            WSMessage(
                                type="status",
                                data={"state": current_state, "message": "Settings updated"},
                            ).model_dump(mode="json")
                        )

                    elif msg_type == "subagent_list":
                        active_dict = getattr(app.state, "active_subagents", {})
                        agents_data = []
                        for a_id, agent in active_dict.items():
                            agents_data.append({
                                "agent_id": agent.agent_id,
                                "task": agent.task_description,
                                "status": agent.status,
                                "progress": agent.progress,
                                "logs": agent.logs[-5:],
                                "result": agent.result
                            })
                        await websocket.send_json(
                            WSMessage(
                                type="subagent_list_response",
                                data={"subagents": agents_data}
                            ).model_dump(mode="json")
                        )

                    elif msg_type == "subagent_abort":
                        a_id = msg_data.get("agent_id")
                        active_dict = getattr(app.state, "active_subagents", {})
                        agent = active_dict.get(a_id)
                        if agent:
                            agent.abort()
                            await websocket.send_json(
                                WSMessage(
                                    type="status",
                                    data={"state": "idle", "message": f"Aborted subagent {a_id}"}
                                ).model_dump(mode="json")
                            )
                        else:
                            await websocket.send_json(
                                WSMessage(
                                    type="error",
                                    data={"message": f"Subagent {a_id} not found"}
                                ).model_dump(mode="json")
                            )

                    elif msg_type == "audio_data":
                        # Audio sent as base64 in JSON (fallback mode)
                        import base64
                        audio_b64 = msg_data.get("audio", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            await voice_queue.put(("audio", audio_bytes))

                    else:
                        logger.warning(f"Unknown message type: {msg_type}")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    await manager.send_message(
                        websocket,
                        WSMessage(type="error", data={"message": "Invalid JSON format"}),
                    )

            elif "bytes" in message:
                # Binary audio data
                audio_bytes = message["bytes"]
                if audio_bytes:
                    await voice_queue.put(("audio", audio_bytes))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except (RuntimeError, Exception) as e:
        err_str = str(e).lower()
        if "disconnect" in err_str or "receive" in err_str or "closed" in err_str:
            logger.info(f"WebSocket connection closed cleanly: {e}")
        else:
            logger.error(f"WebSocket error: {e}")
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        manager.disconnect(websocket)


@router.websocket("/sync")
async def sync_endpoint(websocket: WebSocket):
    """WebSocket endpoint for secure cross-device synchronization."""
    app = websocket.app
    sync_service = getattr(app.state, "sync_service", None)
    
    if not sync_service:
        await websocket.close(code=1008)
        return
        
    await websocket.accept()
    logger.info("Incoming sync connection established.")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                # Decrypt payload
                payload = sync_service.decrypt_data(data)
                
                # Apply peer state
                sync_service.apply_sync_payload(payload)
                
                # Send back encrypted response
                our_payload = sync_service.get_sync_payload()
                encrypted_resp = sync_service.encrypt_data(our_payload)
                await websocket.send_text(encrypted_resp)
            except Exception as e:
                logger.error("Failed to process sync package: {}", e)
                await websocket.send_json({"error": str(e)})
    except WebSocketDisconnect:
        logger.info("Sync connection closed.")
    except Exception as e:
        logger.error("Sync connection error: {}", e)
