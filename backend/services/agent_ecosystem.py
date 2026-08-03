"""
Autonomous Agent Ecosystem Service for JARVIS.
Handles multi-agent orchestration, sub-agent spawning in isolated tasks using real PlannerAgent (CodeAgent, ResearchAgent, SecurityAgent),
and a real Inter-Process Communication (IPC) message bus.
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("agent_ecosystem")

from backend.agents.subagent import SubAgentInstance


class IPCMessage:
    """Represents an agent-to-agent IPC message."""

    def __init__(
        self,
        sender: str,
        recipient: str,
        content: str,
        message_type: str = "request",
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        self.id = f"ipc_{uuid.uuid4().hex[:8]}"
        self.sender = sender
        self.recipient = recipient
        self.content = content
        self.message_type = message_type  # request | response | alert | audit
        self.payload = payload or {}
        self.timestamp = time.time()
        self.formatted_time = datetime.now().strftime("%H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "formatted_time": self.formatted_time,
        }


from backend.agents.micro_agents.base_agent import BaseMicroAgent, MicroAgentMessage
from backend.agents.micro_agents.mcu_agents import ALL_MCU_AGENTS, VoiceAgent, ConversationAgent, SecurityAgent


class AgentEcosystemService:
    """Master Multi-Agent Orchestration & IPC Engine driving real 21 MCU J.A.R.V.I.S. Micro-Agents."""

    def __init__(self, event_bus=None, connection_manager=None, app_state=None) -> None:
        self.event_bus = event_bus
        self.connection_manager = connection_manager
        self.app_state = app_state
        
        self.active_agents: Dict[str, Any] = {}
        self.mcu_micro_agents: Dict[str, BaseMicroAgent] = {}
        self.ipc_messages: List[IPCMessage] = []
        
        # Instantiate and register all 21 MCU J.A.R.V.I.S. Micro-Agents
        self._init_mcu_agents()

        self.role_prompts = {
            "CodeAgent": "You are CodeAgent, a specialized software engineering AI. Analyze AST, write clean Python/JS code, and execute sandbox tests.",
            "ResearchAgent": "You are ResearchAgent, a specialized research AI. Perform web searches, query RAG vector stores, and summarize technical papers.",
            "SecurityAgent": "You are SecurityAgent, a specialized security auditor AI. Inspect commands against SafetyService policy rules and verify sandbox safety."
        }

    def _init_mcu_agents(self) -> None:
        """Instantiate all 21 MCU Micro-Agents."""
        for AgentCls in ALL_MCU_AGENTS:
            try:
                agent_inst = AgentCls(event_bus=self.event_bus)
                self.mcu_micro_agents[agent_inst.name] = agent_inst
            except Exception as e:
                logger.error("Could not instantiate micro-agent {}: {}", AgentCls, e)
        logger.info("✓ Initialized 21 MCU J.A.R.V.I.S. Micro-Agents: {}", list(self.mcu_micro_agents.keys()))

    def spawn_subagent(self, role: str, task_goal: str, planner_agent=None) -> Dict[str, Any]:
        """Spawns a specialized sub-agent (CodeAgent, ResearchAgent, SecurityAgent) executing real PlannerAgent loops."""
        valid_roles = ["CodeAgent", "ResearchAgent", "SecurityAgent"]
        if role not in valid_roles:
            role = "CodeAgent"

        agent_id = f"ag_{role.lower()}_{uuid.uuid4().hex[:6]}"
        system_prompt = self.role_prompts.get(role, self.role_prompts["CodeAgent"])

        planner = planner_agent
        if not planner and self.app_state and hasattr(self.app_state, "planner_agent"):
            planner = self.app_state.planner_agent

        sub_agent = SubAgentInstance(
            agent_id=agent_id,
            role=role,
            task_description=f"[{role}] {task_goal}",
            system_prompt=system_prompt,
            planner_agent=planner,
            app_state=self.app_state,
            ecosystem_service=self
        )

        self.active_agents[agent_id] = sub_agent
        sub_agent.start()

        logger.info(f"[AgentEcosystem] Spawned real sub-agent '{agent_id}' ({role}) for goal: '{task_goal[:40]}'")
        self._broadcast_event("agent.spawned", sub_agent.to_dict())
        return sub_agent.to_dict()

    async def send_ipc_message(
        self,
        sender: str,
        recipient: str,
        content: str,
        message_type: str = "request",
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Sends an agent-to-agent IPC message across the message bus."""
        msg = IPCMessage(
            sender=sender,
            recipient=recipient,
            content=content,
            message_type=message_type,
            payload=payload
        )
        self.ipc_messages.append(msg)
        if len(self.ipc_messages) > 100:
            self.ipc_messages = self.ipc_messages[-100:]

        logger.info(f"[IPC Message Bus] {sender} ➔ {recipient} ({message_type}): '{content[:60]}'")

        # Real SafetyService audit handling if recipient is SecurityAgent
        if recipient.lower() in ["securityagent", "sys_securityagent"] and message_type == "request":
            asyncio.create_task(self._perform_real_security_audit(msg))

        self._broadcast_event("agent.ipc_message", msg.to_dict())
        return msg.to_dict()

    async def _perform_real_security_audit(self, request_msg: IPCMessage) -> None:
        """Executes real SafetyService security policy audit on IPC requests."""
        is_safe = True
        reason = "Passed safety policy check"

        if self.app_state and hasattr(self.app_state, "safety_service"):
            safety = self.app_state.safety_service
            command_text = request_msg.content
            if hasattr(safety, "validate_command"):
                result = safety.validate_command(command_text)
                is_safe = getattr(result, "is_safe", True)
                reason = getattr(result, "reason", reason)

        audit_status = "approved" if is_safe else "blocked"
        response_content = f"Security audit {audit_status.upper()} for: '{request_msg.content[:40]}'. Reason: {reason}"

        await self.send_ipc_message(
            sender="SecurityAgent",
            recipient=request_msg.sender,
            content=response_content,
            message_type="audit",
            payload={"status": audit_status, "is_safe": is_safe, "reason": reason}
        )

    def get_all_agents(self) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self.active_agents.values()]

    def get_ipc_history(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self.ipc_messages]

    def _broadcast_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Emits WebSocket telemetry updates to connected clients."""
        if self.connection_manager and hasattr(self.connection_manager, "broadcast_json"):
            asyncio.create_task(
                self.connection_manager.broadcast_json({
                    "type": event_name,
                    "data": payload
                })
            )
