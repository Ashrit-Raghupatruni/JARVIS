"""
JARVIS Personal AI OS - MCU 21-Agent Ecosystem Base Micro-Agent Framework.
Defines the standard lifecycle, IPC messaging protocol, and event loop for all MCU agents.
"""

import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("micro_agent")


class MicroAgentMessage:
    """Standardized IPC & Event Message between MCU Micro-Agents."""

    def __init__(
        self,
        sender: str,
        recipient: str,
        content: str,
        message_type: str = "request",
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        self.id = f"msg_{uuid.uuid4().hex[:8]}"
        self.sender = sender
        self.recipient = recipient
        self.content = content
        self.message_type = message_type  # request | response | event | alert | telemetry
        self.payload = payload or {}
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class BaseMicroAgent:
    """Abstract Base Class for all 21 MCU J.A.R.V.I.S. Micro-Agents."""

    def __init__(self, name: str, role_description: str, event_bus=None) -> None:
        self.name = name
        self.role_description = role_description
        self.event_bus = event_bus
        self.agent_id = f"ag_{name.lower()}_{uuid.uuid4().hex[:6]}"
        self.status = "idle"  # idle | processing | error | offline
        self.processed_count = 0
        self.last_active = time.time()
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self._loop_task: Optional[asyncio.Task] = None

    async def start() -> None:
        """Start the background micro-agent task loop."""
        if self.is_running:
            return
        self.is_running = True
        self.status = "idle"
        self._loop_task = asyncio.create_task(self._agent_loop())
        logger.info("🤖 Micro-Agent [{}] ({}) initialized & active.", self.name, self.agent_id)

    async def stop() -> None:
        """Gracefully stop the background agent loop."""
        self.is_running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
        self.status = "offline"

    async def _agent_loop() -> None:
        """Internal asynchronous event message consumer loop."""
        while self.is_running:
            try:
                msg: MicroAgentMessage = await asyncio.wait_for(self.inbox.get(), timeout=1.0)
                self.status = "processing"
                self.last_active = time.time()
                
                response = await self.process_message(msg)
                self.processed_count += 1
                
                if response and self.event_bus:
                    await self.event_bus.publish(f"agent.{self.name.lower()}.response", response.to_dict())
                
                self.status = "idle"
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Error in agent loop [{}]: {}", self.name, e)
                self.status = "error"

    async def process_message(self, message: MicroAgentMessage) -> Optional[MicroAgentMessage]:
        """Override in specialized micro-agents to execute agent-specific logic."""
        logger.debug("[{}] Processing message from {}: {}", self.name, message.sender, message.content)
        return MicroAgentMessage(
            sender=self.name,
            recipient=message.sender,
            content=f"Processed by {self.name}: {message.content}",
            message_type="response"
        )

    def send_message_sync(self, message: MicroAgentMessage) -> None:
        """Enqueue message synchronously into inbox."""
        self.inbox.put_nowait(message)

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role_description,
            "status": self.status,
            "processed_count": self.processed_count,
            "last_active": self.last_active,
            "queue_size": self.inbox.qsize()
        }
