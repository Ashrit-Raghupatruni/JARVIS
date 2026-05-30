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

                    elif msg_type == "command":
                        text = msg_data.get("text", "")
                        if text and voice_agent:
                            async for response_msg in voice_agent.handle_text_command(text):
                                await manager.send_message(websocket, response_msg)

                    elif msg_type == "push_to_talk_start":
                        if voice_agent:
                            async for msg in voice_agent.handle_push_to_talk_start():
                                await manager.send_message(websocket, msg)

                    elif msg_type == "push_to_talk_stop":
                        if voice_agent:
                            async for msg in voice_agent.handle_push_to_talk_stop():
                                await manager.send_message(websocket, msg)

                    elif msg_type == "interrupt":
                        if voice_agent:
                            async for msg in voice_agent.handle_interrupt():
                                await manager.send_message(websocket, msg)

                    elif msg_type == "settings":
                        # Handle settings update
                        logger.info(f"Settings update received: {msg_data}")
                        await websocket.send_json(
                            WSMessage(
                                type="status",
                                data={"state": "idle", "message": "Settings updated"},
                            ).model_dump(mode="json")
                        )

                    elif msg_type == "audio_data":
                        # Audio sent as base64 in JSON (fallback mode)
                        import base64
                        audio_b64 = msg_data.get("audio", "")
                        if audio_b64 and voice_agent:
                            audio_bytes = base64.b64decode(audio_b64)
                            async for response_msg in voice_agent.handle_audio_chunk(
                                audio_bytes
                            ):
                                await manager.send_message(websocket, response_msg)

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
                if voice_agent and audio_bytes:
                    async for response_msg in voice_agent.handle_audio_chunk(audio_bytes):
                        await manager.send_message(websocket, response_msg)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
