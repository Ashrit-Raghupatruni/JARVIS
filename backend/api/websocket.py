"""
JARVIS AI OS — Robust Connection Manager & WebSocket Router.
============================================================
Handles real-time bidirectional communication between desktop/mobile clients and backend.
Features:
- Connection state tracking (CONNECTED, RECONNECTING, DISCONNECTED)
- Disconnect-before-send checking & WebSocketDisconnect exception handling
- Message queuing, sequence ID assignment (msg_id), and ACK acknowledgments
- Automatic replay of unacknowledged messages upon client reconnection
- Duplicate connection eviction and non-blocking background queue execution
"""

import asyncio
import json
import time
from typing import Optional, Dict, List, Set, Any
from starlette.websockets import WebSocketState
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from backend.models.schemas import WSMessage

router = APIRouter()


class ConnectionSession:
    """Session tracking per connected client for ACK queuing and replay resilience."""

    def __init__(self, client_id: str, websocket: WebSocket):
        self.client_id = client_id
        self.websocket = websocket
        self.state: str = "CONNECTED"  # CONNECTED, RECONNECTING, DISCONNECTED
        self.pending_acks: Dict[int, WSMessage] = {}
        self.next_msg_id: int = 1
        self.last_heartbeat: float = time.time()

    def is_alive(self) -> bool:
        return (
            self.state == "CONNECTED"
            and self.websocket is not None
            and getattr(self.websocket, "client_state", None) == WebSocketState.CONNECTED
        )

    def acknowledge(self, msg_id: int) -> None:
        """Remove acknowledged message from pending retry buffer."""
        if msg_id in self.pending_acks:
            del self.pending_acks[msg_id]
            logger.debug("Client '{}' acknowledged message ID {}", self.client_id, msg_id)

    def prepare_message(self, message: WSMessage) -> WSMessage:
        """Assign auto-incrementing sequence msg_id for ACK tracking."""
        message.msg_id = self.next_msg_id
        
        # Track in pending_acks if not a transient ping/pong
        if message.type not in ("ping", "pong", "heartbeat"):
            self.pending_acks[self.next_msg_id] = message
            
        self.next_msg_id += 1
        return message


class RobustConnectionManager:
    """Manager for active WebSocket connections supporting ACK replay & duplicate eviction."""

    def __init__(self):
        self.sessions: Dict[str, ConnectionSession] = {}
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> ConnectionSession:
        """Connect client, evict duplicates, and return session instance."""
        cid = client_id or f"client_{id(websocket)}"
        
        # Evict existing duplicate connection for same client_id if present
        if cid in self.sessions:
            old_session = self.sessions[cid]
            if old_session.is_alive():
                logger.info("Evicting duplicate connection for client_id '{}'", cid)
                try:
                    await old_session.websocket.close(code=1000, reason="Replaced by new connection")
                except Exception:
                    pass
            # Transfer pending ACKs to new session
            old_acks = old_session.pending_acks
        else:
            old_acks = {}

        await websocket.accept()
        
        session = ConnectionSession(cid, websocket)
        session.pending_acks = old_acks
        self.sessions[cid] = session
        
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)

        logger.info("✓ WebSocket connected: client_id='{}'. Total active: {}", cid, len(self.active_connections))

        # Replay unacknowledged messages upon reconnect
        if old_acks:
            logger.info("Replaying {} unacknowledged messages for reconnected client '{}'", len(old_acks), cid)
            for m_id, unacked_msg in list(old_acks.items()):
                await self.send_message(websocket, unacked_msg, client_id=cid)

        return session

    def disconnect(self, websocket: WebSocket, client_id: Optional[str] = None) -> None:
        """Disconnect websocket cleanly."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        cid = client_id
        if not cid:
            for k, sess in list(self.sessions.items()):
                if sess.websocket == websocket:
                    cid = k
                    break

        if cid and cid in self.sessions:
            self.sessions[cid].state = "DISCONNECTED"
            logger.info("WebSocket disconnected cleanly: client_id='{}'. Active: {}", cid, len(self.active_connections))

    async def send_message(self, websocket: WebSocket, message: WSMessage, client_id: Optional[str] = None) -> bool:
        """Send a typed message safely with pre-send disconnect check."""
        if not websocket or getattr(websocket, "client_state", None) != WebSocketState.CONNECTED:
            logger.debug("Skipped send: WebSocket client is disconnected.")
            return False

        try:
            # Look up session if client_id present
            cid = client_id
            if cid and cid in self.sessions:
                prepared_msg = self.sessions[cid].prepare_message(message)
                data_json = prepared_msg.model_dump(mode="json")
            else:
                data_json = message.model_dump(mode="json")

            await websocket.send_json(data_json)
            return True
        except (WebSocketDisconnect, RuntimeError, ConnectionResetError) as e:
            logger.info("Connection closed during send: {}", e)
            self.disconnect(websocket, client_id)
            return False
        except Exception as e:
            logger.error("Failed to send WebSocket message: {}", e)
            return False

    async def broadcast(self, message: WSMessage) -> None:
        """Broadcast message safely to all connected clients."""
        disconnected = []
        for connection in list(self.active_connections):
            success = await self.send_message(connection, message)
            if not success:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    def acknowledge_message(self, client_id: str, msg_id: int) -> None:
        """Handle incoming client ACK message."""
        if client_id in self.sessions:
            self.sessions[client_id].acknowledge(msg_id)


# Global connection manager
manager = RobustConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for JARVIS communication.
    Supports non-blocking queue processing during heavy LLM inference.
    """
    app = websocket.app
    client_id = websocket.query_params.get("client_id") or f"desktop_{id(websocket)}"
    session = await manager.connect(websocket, client_id=client_id)

    app.state.connection_manager = manager

    # Send initial status
    await manager.send_message(
        websocket,
        WSMessage(type="status", data={"state": "idle", "message": "JARVIS online", "client_id": client_id}),
        client_id=client_id
    )

    # Decoupled queue for heavy LLM & voice execution to prevent socket blocking
    work_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    async def background_worker():
        while True:
            try:
                action_type, payload = await work_queue.get()
                
                # Check connection status before proceeding
                if not session.is_alive():
                    logger.debug("Skipping queued background action '{}': client disconnected.", action_type)
                    work_queue.task_done()
                    continue

                v_agent = getattr(app.state, "voice_agent", None)
                planner = getattr(app.state, "planner", None)

                if action_type == "text_command":
                    if v_agent and hasattr(v_agent, "handle_text_command"):
                        async for response_msg in v_agent.handle_text_command(payload):
                            await manager.send_message(websocket, response_msg, client_id=client_id)
                    elif planner and hasattr(planner, "plan_and_execute"):
                        async for msg in planner.plan_and_execute(payload):
                            await manager.send_message(websocket, msg, client_id=client_id)
                    else:
                        logger.warning("No agent or planner available to process text command: {}", payload)

                elif action_type == "audio":
                    if v_agent and hasattr(v_agent, "handle_audio_chunk"):
                        async for response_msg in v_agent.handle_audio_chunk(payload):
                            await manager.send_message(websocket, response_msg, client_id=client_id)

                elif action_type == "ptt_start":
                    if v_agent and hasattr(v_agent, "handle_push_to_talk_start"):
                        async for response_msg in v_agent.handle_push_to_talk_start():
                            await manager.send_message(websocket, response_msg, client_id=client_id)

                elif action_type == "ptt_stop":
                    if v_agent and hasattr(v_agent, "handle_push_to_talk_stop"):
                        async for response_msg in v_agent.handle_push_to_talk_stop():
                            await manager.send_message(websocket, response_msg, client_id=client_id)

                work_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in WebSocket background worker: {}", e)
                try:
                    work_queue.task_done()
                except ValueError:
                    pass

    worker_task = asyncio.create_task(background_worker())

    try:
        while True:
            # Check connection state before waiting
            if getattr(websocket, "client_state", None) != WebSocketState.CONNECTED:
                logger.info("WebSocket disconnect detected before receive call. Ending loop.")
                break

            try:
                # Receive text or binary frame with heartbeat timeout
                message = await asyncio.wait_for(websocket.receive(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send periodic heartbeat pong
                if getattr(websocket, "client_state", None) == WebSocketState.CONNECTED:
                    success = await manager.send_message(
                        websocket,
                        WSMessage(type="pong", data={"timestamp": time.time()}),
                        client_id=client_id
                    )
                    if not success:
                        break
                else:
                    break
                continue

            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type", "")
                    msg_data = data.get("data", {})
                    msg_id = data.get("msg_id")

                    # Handle ACK response from client
                    if msg_type == "ack" and msg_id is not None:
                        manager.acknowledge_message(client_id, int(msg_id))

                    elif msg_type in ("ping", "heartbeat"):
                        await manager.send_message(
                            websocket,
                            WSMessage(type="pong", data={"timestamp": time.time()}),
                            client_id=client_id
                        )

                    elif msg_type in ("command", "text_command"):
                        text = msg_data.get("text", "")
                        if text:
                            # Acknowledge receipt of command back to client
                            await manager.send_message(
                                websocket,
                                WSMessage(type="ack", data={"received": text}),
                                client_id=client_id
                            )
                            await work_queue.put(("text_command", text))

                    elif msg_type == "push_to_talk_start":
                        while not work_queue.empty():
                            try:
                                work_queue.get_nowait()
                                work_queue.task_done()
                            except (asyncio.QueueEmpty, ValueError):
                                break
                        await work_queue.put(("ptt_start", None))

                    elif msg_type == "push_to_talk_stop":
                        await work_queue.put(("ptt_stop", None))

                    elif msg_type == "interrupt":
                        v_agent = getattr(app.state, "voice_agent", None)
                        if v_agent and hasattr(v_agent, "handle_interrupt"):
                            async for msg in v_agent.handle_interrupt():
                                await manager.send_message(websocket, msg, client_id=client_id)
                        while not work_queue.empty():
                            try:
                                work_queue.get_nowait()
                                work_queue.task_done()
                            except (asyncio.QueueEmpty, ValueError):
                                break

                    elif msg_type == "get_tasks":
                        t_q = getattr(app.state, "task_queue_service", None)
                        if t_q and hasattr(t_q, "get_queue_summary"):
                            tasks_summary = t_q.get_queue_summary()
                            await manager.send_message(websocket, WSMessage(type="status", data={"task_queue": tasks_summary}), client_id=client_id)

                    elif msg_type == "settings":
                        logger.info("Settings update received on WebSocket: {}", msg_data)
                        await manager.send_message(
                            websocket,
                            WSMessage(type="status", data={"state": "idle", "message": "Settings updated"}),
                            client_id=client_id
                        )

                    elif msg_type == "audio_data":
                        import base64
                        audio_b64 = msg_data.get("audio", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            await work_queue.put(("audio", audio_bytes))

                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON format received: {}", e)
                    await manager.send_message(
                        websocket,
                        WSMessage(type="error", data={"message": "Invalid JSON format"}),
                        client_id=client_id
                    )

            elif "bytes" in message:
                audio_bytes = message.get("bytes")
                if audio_bytes:
                    await work_queue.put(("audio", audio_bytes))

    except WebSocketDisconnect:
        logger.info("WebSocket client '{}' disconnected normally", client_id)
    except Exception as e:
        logger.info("WebSocket connection closed cleanly for client '{}': {}", client_id, e)
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        manager.disconnect(websocket, client_id=client_id)


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
                payload = sync_service.decrypt_data(data)
                sync_service.apply_sync_payload(payload)
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
