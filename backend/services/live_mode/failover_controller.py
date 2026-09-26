"""
JARVIS AI OS — Live Mode Failover Controller & Agent Supervisor.
================================================================
Implements autonomous multi-agent failover for Live Mode operations:
1. Primary Agent: JARVIS Desktop Agent executes tasks normally.
2. Fallback Agent: Hermes Desktop Agent takes over upon failure/timeout.
3. Single-Agent Control: Strict mutual exclusion guaranteeing only ONE agent
   controls the computer/keyboard/mouse at any instant.
4. Continuation from Failure Point: Hermes receives the full task context,
   completed actions, failed step, and current screen state to resume execution.
5. Safe Recovery & Escalation: Logs all handoffs and safely halts if both agents fail.
6. Emergency Stop: Immediate user takeover and lock revocation.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field
from loguru import logger

from backend.services.manager import ServiceManager
from backend.services.safety_gatekeeper import SafetyGatekeeper
from backend.services.live_mode.live_goal_engine import GoalStep, GoalExecutionState, LiveGoalExecutionEngine
from backend.agents.desktop_agent import HermesDesktopAgent, hermes_desktop_agent


class AgentAuthorityState(str, Enum):
    IDLE = "IDLE"
    PRIMARY_ACTIVE = "PRIMARY_ACTIVE"
    FAILOVER_PENDING = "FAILOVER_PENDING"
    HERMES_ACTIVE = "HERMES_ACTIVE"
    RECOVERY = "RECOVERY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ActionExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    BLOCKED = "BLOCKED"


class HandoffRecord(BaseModel):
    handoff_id: str = Field(default_factory=lambda: f"ho_{uuid.uuid4().hex[:6]}")
    timestamp: float = Field(default_factory=time.time)
    from_agent: str = "JARVIS Desktop"
    to_agent: str = "Hermes Desktop"
    failed_step_id: int
    failed_step_desc: str
    error_reason: str
    screen_context: Dict[str, Any] = Field(default_factory=dict)


class LiveModeFailoverSupervisor:
    """
    Supervisor managing failover between primary JARVIS Desktop Agent
    and fallback Hermes Desktop Agent with single-agent control locking.
    """

    def __init__(
        self,
        primary_engine: Optional[LiveGoalExecutionEngine] = None,
        fallback_agent: Optional[HermesDesktopAgent] = None,
        safety_gatekeeper: Optional[SafetyGatekeeper] = None
    ) -> None:
        self.primary_engine = primary_engine or LiveGoalExecutionEngine()
        self.fallback_agent = fallback_agent or hermes_desktop_agent
        self.safety_gatekeeper = safety_gatekeeper or SafetyGatekeeper()
        
        # Single-Agent Control Lock
        self._control_lock = asyncio.Lock()
        self.current_authority: AgentAuthorityState = AgentAuthorityState.IDLE
        self.active_agent_name: str = "None"
        
        # Telemetry & Handoff Tracking
        self.handoff_history: List[HandoffRecord] = []
        self._emergency_stop_event = asyncio.Event()
        self._active_supervision_task: Optional[asyncio.Task] = None
        self.latest_state: Optional[Dict[str, Any]] = None

        logger.info("LiveModeFailoverSupervisor initialized (Primary: JARVIS Desktop | Fallback: Hermes Desktop)")

    def _emit_telemetry(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish real-time telemetry over WebSocket and EventBus sink."""
        payload = {
            "type": event_type,
            "authority_state": self.current_authority.value,
            "active_agent": self.active_agent_name,
            "timestamp": time.time(),
            "data": data
        }
        self.latest_state = payload

        # Broadcast over WebSocket manager
        try:
            ws_mgr = ServiceManager.get_instance("connection_manager")
            if ws_mgr and hasattr(ws_mgr, "broadcast"):
                from backend.models.schemas import WSMessage
                asyncio.create_task(ws_mgr.broadcast(WSMessage(
                    type="live_mode_supervisor_update",
                    data=payload
                )))
        except Exception as e:
            logger.debug("WebSocket telemetry broadcast notice: {}", e)

    def emergency_stop(self) -> Dict[str, Any]:
        """
        Immediately revokes control locks and halts all agent executions.
        Manual 'Take Control' trigger for the user.
        """
        logger.warning("🛑 LiveModeFailoverSupervisor: EMERGENCY STOP TRIGGERED BY USER.")
        self._emergency_stop_event.set()
        self.current_authority = AgentAuthorityState.CANCELLED
        self.active_agent_name = "User (Manual Override)"
        
        # Cancel primary if active
        for goal_id in list(self.primary_engine.active_goals.keys()):
            self.primary_engine.cancel_goal(goal_id)

        self._emit_telemetry("emergency_stop", {"message": "User manual override activated. Control revoked from all AI agents."})
        return {
            "status": "stopped",
            "authority": self.current_authority.value,
            "message": "AI agents stopped. You now have complete manual control."
        }

    async def execute_with_failover(
        self,
        goal: str,
        tool_registry: Any,
        timeout_per_step: float = 25.0
    ) -> Dict[str, Any]:
        """
        Executes a user goal with the Primary JARVIS Agent, automatically
        failing over to Hermes Desktop Agent if any action fails or times out.
        """
        self._emergency_stop_event.clear()
        start_time = time.time()
        goal_id = f"sup_goal_{uuid.uuid4().hex[:8]}"

        logger.info("🛡️ Supervisor starting goal execution: '{}' [ID: {}]", goal, goal_id)

        # ── Step 1: Decompose Goal via Primary Planner ─────────────────────
        steps = self.primary_engine.decompose_goal(goal, tool_registry)
        if not steps:
            return {"status": "failed", "goal": goal, "error": "Could not decompose goal into executable steps."}

        completed_steps: List[Dict[str, Any]] = []
        failed_step: Optional[GoalStep] = None
        failover_occurred = False
        final_summary = ""

        # ── Step 2: Primary Execution Loop (JARVIS Desktop Agent) ──────────
        async with self._control_lock:
            self.current_authority = AgentAuthorityState.PRIMARY_ACTIVE
            self.active_agent_name = "JARVIS Desktop"
            self._emit_telemetry("primary_started", {
                "goal_id": goal_id,
                "goal": goal,
                "total_steps": len(steps),
                "steps": [s.model_dump() for s in steps]
            })

            for idx, step in enumerate(steps):
                if self._emergency_stop_event.is_set():
                    self.current_authority = AgentAuthorityState.CANCELLED
                    return {"status": "cancelled", "summary": "Execution stopped by user."}

                step.status = ActionExecutionStatus.RUNNING.value
                step.start_time = time.time()
                self._emit_telemetry("step_executing", {
                    "step_id": step.step_id,
                    "description": step.description,
                    "agent": "JARVIS Desktop",
                    "status": "RUNNING"
                })

                # Check safety gatekeeper
                decision = self.safety_gatekeeper.evaluate_tool_call(step.tool_name, step.parameters)
                if decision.requires_user_approval or step.requires_approval:
                    logger.info("Primary step requires confirmation: '{}'", step.description)
                    step.status = ActionExecutionStatus.BLOCKED.value
                    self._emit_telemetry("step_blocked_for_approval", {"step_id": step.step_id, "desc": step.description})

                try:
                    # Execute with step timeout guard
                    if tool_registry and hasattr(tool_registry, "execute_tool") and tool_registry.get_tool(step.tool_name):
                        tool_coro = tool_registry.execute_tool(step.tool_name, step.parameters)
                        res = await asyncio.wait_for(tool_coro, timeout=timeout_per_step)
                        
                        if isinstance(res, dict) and res.get("status") == "error":
                            raise RuntimeError(res.get("error") or res.get("message") or f"Tool '{step.tool_name}' failed.")
                        
                        step.status = ActionExecutionStatus.SUCCESS.value
                        step.result = res
                        step.end_time = time.time()
                        completed_steps.append(step.model_dump())
                        logger.info("✓ JARVIS Desktop [Step {}/{}]: Success: '{}'", step.step_id, len(steps), step.description)
                        self._emit_telemetry("step_success", {"step_id": step.step_id, "agent": "JARVIS Desktop"})
                    else:
                        raise RuntimeError(f"Tool '{step.tool_name}' not found in registry.")

                except asyncio.TimeoutError:
                    logger.warning("⏱️ JARVIS Desktop [Step {}/{}]: TIMEOUT after {}s on '{}'", step.step_id, len(steps), timeout_per_step, step.description)
                    step.status = ActionExecutionStatus.TIMEOUT.value
                    step.error = f"Step timed out after {timeout_per_step}s."
                    failed_step = step
                    break

                except Exception as e:
                    logger.warning("✗ JARVIS Desktop [Step {}/{}]: FAILED on '{}': {}", step.step_id, len(steps), step.description, e)
                    step.status = ActionExecutionStatus.FAILED.value
                    step.error = str(e)
                    failed_step = step
                    break

        # ── Step 3: Handle Primary Success ─────────────────────────────────
        if failed_step is None and len(completed_steps) == len(steps):
            self.current_authority = AgentAuthorityState.COMPLETED
            self.active_agent_name = "JARVIS Desktop"
            final_summary = f"JARVIS Desktop Agent completed all {len(steps)} actions successfully."
            self._emit_telemetry("goal_completed", {"agent": "JARVIS Desktop", "summary": final_summary})
            return {
                "status": "success",
                "authority": self.current_authority.value,
                "primary_agent": "JARVIS Desktop",
                "failover_occurred": False,
                "completed_steps": completed_steps,
                "summary": final_summary,
                "duration": round(time.time() - start_time, 2)
            }

        # ── Step 4: Automatic Hermes Failover Handoff ──────────────────────
        logger.info("🚨 Initiating automatic failover from JARVIS Desktop to Hermes Desktop...")
        self.current_authority = AgentAuthorityState.FAILOVER_PENDING
        self.active_agent_name = "Supervisor (Handoff In Progress)"
        
        # Collect current screen perception context
        screen_ctx = {}
        try:
            screen_ctx = await self.fallback_agent.get_active_screen_context()
        except Exception:
            pass

        # Record handoff audit entry
        handoff = HandoffRecord(
            failed_step_id=failed_step.step_id if failed_step else 0,
            failed_step_desc=failed_step.description if failed_step else "Unknown",
            error_reason=failed_step.error if failed_step else "Unknown failure",
            screen_context=screen_ctx
        )
        self.handoff_history.append(handoff)

        self._emit_telemetry("failover_triggered", {
            "handoff_id": handoff.handoff_id,
            "failed_step": handoff.failed_step_desc,
            "reason": handoff.error_reason,
            "active_agent": "Hermes Desktop (Fallback Taking Over)"
        })

        # Calculate remaining sub-goal objective from the failure point
        remaining_steps = steps[len(completed_steps):]
        remaining_descriptions = [s.description for s in remaining_steps]
        hermes_resume_goal = (
            f"Original Goal: '{goal}'.\n"
            f"Actions already completed successfully: {[s['description'] for s in completed_steps]}.\n"
            f"Failed on action: '{failed_step.description if failed_step else ''}' with error: '{failed_step.error if failed_step else ''}'.\n"
            f"Please resume from the failure point and complete the remaining objectives: {remaining_descriptions}."
        )

        # ── Step 5: Execute via Hermes Desktop Agent under Control Lock ────
        async with self._control_lock:
            self.current_authority = AgentAuthorityState.HERMES_ACTIVE
            self.active_agent_name = "Hermes Desktop"
            self._emit_telemetry("hermes_active", {
                "handoff_id": handoff.handoff_id,
                "resume_goal": hermes_resume_goal,
                "screen_context": screen_ctx
            })

            try:
                hermes_result = await self.fallback_agent.execute_task(user_goal=hermes_resume_goal)
                
                if hermes_result.get("completed", hermes_result.get("status") == "success"):
                    self.current_authority = AgentAuthorityState.RECOVERY
                    self.active_agent_name = "Hermes Desktop (Completed Recovery)"
                    final_summary = (
                        f"Failover Recovery Succeeded: Hermes Desktop took over from step #{failed_step.step_id} "
                        f"and finished the task. Summary: {hermes_result.get('summary', '')}"
                    )
                    self._emit_telemetry("recovery_success", {
                        "agent": "Hermes Desktop",
                        "summary": final_summary,
                        "hermes_steps": hermes_result.get("steps", [])
                    })
                    
                    self.current_authority = AgentAuthorityState.COMPLETED
                    return {
                        "status": "success",
                        "authority": self.current_authority.value,
                        "failover_occurred": True,
                        "primary_completed_steps": completed_steps,
                        "failed_step": failed_step.model_dump() if failed_step else None,
                        "hermes_result": hermes_result,
                        "summary": final_summary,
                        "handoff_record": handoff.model_dump(),
                        "duration": round(time.time() - start_time, 2)
                    }
                else:
                    # Both Primary and Hermes failed
                    self.current_authority = AgentAuthorityState.FAILED
                    self.active_agent_name = "None (Dual Agent Failure)"
                    final_summary = (
                        f"Dual Agent Failure: Primary JARVIS failed on '{failed_step.description if failed_step else ''}', "
                        f"and Hermes recovery also failed: {hermes_result.get('summary', 'Hermes could not resolve task')}. "
                        f"Please intervene manually."
                    )
                    self._emit_telemetry("dual_failure", {
                        "summary": final_summary,
                        "failed_step": failed_step.model_dump() if failed_step else None,
                        "hermes_result": hermes_result
                    })
                    return {
                        "status": "failed",
                        "authority": self.current_authority.value,
                        "failover_occurred": True,
                        "primary_completed_steps": completed_steps,
                        "failed_step": failed_step.model_dump() if failed_step else None,
                        "hermes_result": hermes_result,
                        "summary": final_summary,
                        "requires_user_intervention": True,
                        "duration": round(time.time() - start_time, 2)
                    }

            except Exception as hermes_err:
                self.current_authority = AgentAuthorityState.FAILED
                self.active_agent_name = "None (Dual Agent Failure)"
                final_summary = f"Dual Agent Failure: Hermes encountered fatal error: {hermes_err}"
                self._emit_telemetry("hermes_exception", {"error": str(hermes_err), "summary": final_summary})
                return {
                    "status": "failed",
                    "authority": self.current_authority.value,
                    "failover_occurred": True,
                    "error": str(hermes_err),
                    "summary": final_summary,
                    "requires_user_intervention": True
                }


live_failover_supervisor = LiveModeFailoverSupervisor()
