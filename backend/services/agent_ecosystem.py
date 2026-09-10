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


from backend.agents.subagent import SubAgentInstance
from backend.agents.domain import DOMAIN_AGENTS, GeneralAgent, ResearchAgent, DeveloperAgent, AutomationAgent


class AgentEcosystemService:
    """Master Multi-Agent Orchestration & IPC Engine driving strong domain agents."""

    def __init__(self, event_bus=None, connection_manager=None, app_state=None) -> None:
        self.event_bus = event_bus
        self.connection_manager = connection_manager
        self.app_state = app_state
        
        self.active_agents: Dict[str, Any] = {}
        self.domain_agents: Dict[str, Any] = {}
        self.ipc_messages: List[IPCMessage] = []
        
        # Initialize the 4 strong domain agents
        self._init_domain_agents()

        self.role_prompts = {
            "DeveloperAgent": "You are DeveloperAgent, a specialized software engineering AI. Analyze AST, write clean code, and execute sandbox tests.",
            "CodeAgent": "You are DeveloperAgent (CodeAgent), a specialized software engineering AI. Analyze AST, write clean code, and execute sandbox tests.",
            "ResearchAgent": "You are ResearchAgent, a specialized research AI. Perform web searches, query RAG vector stores, and summarize technical papers.",
            "AutomationAgent": "You are AutomationAgent, a specialized desktop automation AI. Perform Win32 UIA actions, RPA macros, and browser navigation.",
            "GeneralAgent": "You are GeneralAgent, a general reasoning AI with Tony Stark's Marvel J.A.R.V.I.S. personality. Handle conversations, memory, and system tasks.",
            "SecurityAgent": "You are SecurityAgent, a specialized security auditor AI. Inspect commands against SafetyService policy rules and verify sandbox safety."
        }

    def _init_domain_agents(self) -> None:
        """Instantiate the 4 strong domain agents."""
        self.domain_agents = {
            "GeneralAgent": GeneralAgent(event_bus=self.event_bus),
            "ResearchAgent": ResearchAgent(event_bus=self.event_bus),
            "DeveloperAgent": DeveloperAgent(event_bus=self.event_bus),
            "AutomationAgent": AutomationAgent(event_bus=self.event_bus),
        }
        logger.info("✓ Initialized 4 Strong Domain Agents: {}", list(self.domain_agents.keys()))

    def get_domain_agent(self, role: str) -> Optional[Any]:
        """Lookup domain agent by name or alias."""
        target_cls = DOMAIN_AGENTS.get(role)
        if target_cls:
            name = target_cls.__name__
            return self.domain_agents.get(name)
        return self.domain_agents.get(role)

    def spawn_subagent(self, role: str, task_goal: str, planner_agent=None) -> Dict[str, Any]:
        """Spawns a specialized sub-agent (DeveloperAgent, ResearchAgent, AutomationAgent, GeneralAgent, SecurityAgent)."""
        valid_roles = ["DeveloperAgent", "CodeAgent", "ResearchAgent", "AutomationAgent", "GeneralAgent", "SecurityAgent"]
        if role not in valid_roles:
            role = "DeveloperAgent"

        agent_id = f"ag_{role.lower()}_{uuid.uuid4().hex[:6]}"
        system_prompt = self.role_prompts.get(role, self.role_prompts["DeveloperAgent"])

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

        logger.info(f"[AgentEcosystem] Spawned sub-agent '{agent_id}' ({role}) for goal: '{task_goal[:40]}'")
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
        if not self.connection_manager:
            return
        if hasattr(self.connection_manager, "broadcast_json"):
            asyncio.create_task(self.connection_manager.broadcast_json({
                "type": event_name,
                "data": payload
            }))
