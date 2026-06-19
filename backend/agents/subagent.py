"""
Sub-Agent execution runner for JARVIS.
Spawns, monitors, and executes headless background task agents.
"""

import asyncio
import uuid
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from loguru import logger

from backend.models.schemas import WSMessage, ResponseMessage


class SubAgentInstance:
    """Represents a running background instance of a PlannerAgent executing a specific task."""

    def __init__(self, agent_id: str, task_description: str, planner_agent, app_state=None) -> None:
        self.agent_id = agent_id
        self.task_description = task_description
        self.planner = planner_agent
        self.app_state = app_state
        
        # State
        self.status = "running"  # running | completed | failed | cancelled
        self.progress = 0.0
        self.started_at = time.time()
        self.completed_at: Optional[float] = None
        self.logs: List[str] = []
        self.result: Optional[str] = None
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Launches the background async task runner."""
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Sub-Agent [{}] spawned for task: '{}'", self.agent_id, self.task_description[:50])

    def abort(self) -> None:
        """Cancels the running agent task."""
        if self._task and not self._task.done():
            self._task.cancel()
            self.status = "cancelled"
            self.completed_at = time.time()
            self.logs.append("Task aborted by user request.")
            logger.info("Sub-Agent [{}] aborted.", self.agent_id)

    async def _run_loop(self) -> None:
        self.logs.append(f"[{datetime_now_str()}] Agent spawned. Task: {self.task_description}")
        
        try:
            # Capture outputs yielded by planner. We execute it in a clean history session.
            # Create a separate history context to avoid polluting user chat
            history: List[dict] = [{"role": "system", "content": "You are a sub-agent executing a background task. Complete it efficiently. Keep updates short."}]
            
            async for update in self.planner.plan_and_execute(self.task_description, conversation_history=history):
                # Update progress based on yielded WSMessage
                msg_type = update.type
                data = update.data
                
                if msg_type == "agent_progress":
                    steps = data.get("steps", [])
                    self.progress = data.get("progress", 0.0)
                    self.logs.append(f"[{datetime_now_str()}] Step: {steps[-1]['description'] if steps else 'working'}")
                    await self._broadcast_status()

                elif msg_type == "response":
                    self.result = data.get("text", "")
                    self.logs.append(f"[{datetime_now_str()}] Result: {self.result}")
                
                elif msg_type == "error":
                    self.status = "failed"
                    self.logs.append(f"[{datetime_now_str()}] Error: {data.get('message', 'unknown')}")

            if self.status == "running":
                self.status = "completed"
                self.progress = 1.0
                self.completed_at = time.time()
                self.logs.append(f"[{datetime_now_str()}] Task completed successfully.")
                logger.info("Sub-Agent [{}] completed successfully.", self.agent_id)
                
            await self._broadcast_status()

        except asyncio.CancelledError:
            self.status = "cancelled"
            self.completed_at = time.time()
            await self._broadcast_status()
            
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.logs.append(f"[{datetime_now_str()}] Exception: {e}")
            logger.error("Sub-Agent [{}] failed: {}", self.agent_id, e)
            await self._broadcast_status()

    async def _broadcast_status(self) -> None:
        """Pushes subagent updates to active websockets."""
        if not self.app_state:
            return
        manager = getattr(self.app_state, "connection_manager", None)
        if manager:
            # Send status update
            await manager.broadcast(WSMessage(
                type="subagent_status",
                data={
                    "agent_id": self.agent_id,
                    "task": self.task_description,
                    "status": self.status,
                    "progress": self.progress,
                    "logs": self.logs[-5:],  # last 5 log items
                    "result": self.result
                }
            ))


def datetime_now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")
