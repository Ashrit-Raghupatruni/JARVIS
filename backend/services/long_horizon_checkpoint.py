"""
Long-Horizon Task Continuity & Multi-Day Checkpointing Service.
Stores persistent goal queues, step indexes, intermediate artifacts, and KV-cache states in SQLite WAL database.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger
import aiosqlite

from backend.config import get_settings


class LongHorizonCheckpointService:
    """Manages persistent goal queues and multi-day task checkpoints in SQLite WAL mode."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        settings = get_settings()
        self.db_path = db_path or str(settings.data_path / "jarvis.db")
        self._initialized = False

    async def initialize(self) -> None:
        """Initializes SQLite tables for goal_queue and agent_checkpoints."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            
            # Goal Queue Table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS goal_queue (
                    goal_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL, -- pending | running | paused | completed | failed
                    current_step_index INTEGER DEFAULT 0,
                    total_steps INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # Agent Checkpoints Table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agent_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    step_title TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    artifacts_json TEXT,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (goal_id) REFERENCES goal_queue (goal_id)
                )
            """)
            await db.commit()

        self._initialized = True
        logger.info("[LongHorizonCheckpoint] Initialized SQLite WAL goal queue & checkpoint tables.")

    async def create_goal(self, title: str, description: str = "", total_steps: int = 4) -> Dict[str, Any]:
        """Creates a new long-horizon persistent goal entry."""
        await self.initialize()
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"
        now = time.time()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO goal_queue (goal_id, title, description, status, current_step_index, total_steps, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (goal_id, title, description, "running", 0, total_steps, now, now)
            )
            await db.commit()

        # Create initial baseline checkpoint 0
        await self.create_checkpoint(
            goal_id=goal_id,
            step_title="Goal Initialized",
            state_data={"step_index": 0, "status": "running", "notes": "Baseline creation"}
        )

        return {
            "goal_id": goal_id,
            "title": title,
            "description": description,
            "status": "running",
            "current_step_index": 0,
            "total_steps": total_steps,
            "created_at": now,
            "updated_at": now
        }

    async def create_checkpoint(
        self,
        goal_id: str,
        step_title: str,
        state_data: Dict[str, Any],
        artifacts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Saves a new multi-day progress checkpoint for a goal."""
        await self.initialize()
        checkpoint_id = f"chk_{uuid.uuid4().hex[:8]}"
        now = time.time()

        state_json = json.dumps(state_data)
        artifacts_json = json.dumps(artifacts or [])

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO agent_checkpoints (checkpoint_id, goal_id, step_title, state_json, artifacts_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (checkpoint_id, goal_id, step_title, state_json, artifacts_json, now)
            )
            # Update goal progress
            step_idx = state_data.get("step_index", 0)
            await db.execute(
                "UPDATE goal_queue SET current_step_index = ?, updated_at = ? WHERE goal_id = ?",
                (step_idx, now, goal_id)
            )
            await db.commit()

        logger.info(f"[LongHorizonCheckpoint] Saved checkpoint '{checkpoint_id}' for goal '{goal_id}' (Step: {step_title})")
        return {
            "checkpoint_id": checkpoint_id,
            "goal_id": goal_id,
            "step_title": step_title,
            "timestamp": now,
            "formatted_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    async def get_goal_queue(self) -> List[Dict[str, Any]]:
        """Fetches all persistent goals and their latest checkpoints."""
        await self.initialize()
        goals: List[Dict[str, Any]] = []

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM goal_queue ORDER BY updated_at DESC") as cursor:
                async for row in cursor:
                    goals.append({
                        "goal_id": row["goal_id"],
                        "title": row["title"],
                        "description": row["description"],
                        "status": row["status"],
                        "current_step_index": row["current_step_index"],
                        "total_steps": row["total_steps"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "formatted_updated": datetime.fromtimestamp(row["updated_at"]).strftime("%m/%d %H:%M")
                    })
        return goals

    async def get_checkpoints_for_goal(self, goal_id: str) -> List[Dict[str, Any]]:
        """Fetches all checkpoint records for a specific goal."""
        await self.initialize()
        checkpoints: List[Dict[str, Any]] = []

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM agent_checkpoints WHERE goal_id = ? ORDER BY timestamp ASC",
                (goal_id,)
            ) as cursor:
                async for row in cursor:
                    checkpoints.append({
                        "checkpoint_id": row["checkpoint_id"],
                        "goal_id": row["goal_id"],
                        "step_title": row["step_title"],
                        "state_data": json.loads(row["state_json"]),
                        "artifacts": json.loads(row["artifacts_json"] or "[]"),
                        "timestamp": row["timestamp"],
                        "formatted_time": datetime.fromtimestamp(row["timestamp"]).strftime("%m/%d %H:%M:%S")
                    })
        return checkpoints

    async def set_goal_status(self, goal_id: str, status: str) -> bool:
        """Updates status of a goal (e.g. pause, resume, complete)."""
        await self.initialize()
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE goal_queue SET status = ?, updated_at = ? WHERE goal_id = ?",
                (status, now, goal_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def record_step_completion(
        self,
        goal_id: str,
        step_index: int,
        step_title: str,
        step_output: Dict[str, Any],
        artifacts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Atomically records a completed step, creates a persistent checkpoint,
        and transitions the goal to 'completed' if the final step has executed.
        """
        await self.initialize()
        now = time.time()

        # Retrieve goal metadata
        goal = None
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM goal_queue WHERE goal_id = ?", (goal_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    goal = dict(row)

        if not goal:
            raise ValueError(f"Goal '{goal_id}' not found")

        total_steps = goal.get("total_steps", 1)
        is_finished = step_index >= total_steps
        new_status = "completed" if is_finished else "running"

        state_data = {
            "step_index": step_index,
            "status": new_status,
            "output": step_output,
            "completed_at": now,
        }

        # Save checkpoint
        checkpoint = await self.create_checkpoint(
            goal_id=goal_id,
            step_title=step_title,
            state_data=state_data,
            artifacts=artifacts or [],
        )

        # Update status if completed
        if is_finished:
            await self.set_goal_status(goal_id, "completed")
            logger.info("[LongHorizonCheckpoint] Goal '{}' marked as COMPLETED (All {} steps done)", goal_id, total_steps)

        return {
            "goal_id": goal_id,
            "step_index": step_index,
            "total_steps": total_steps,
            "status": new_status,
            "checkpoint_id": checkpoint["checkpoint_id"],
            "completed": is_finished,
        }

    async def recover_interrupted_goals(self) -> List[Dict[str, Any]]:
        """
        Self-recovery engine: scans for interrupted goals (e.g. status='running' on boot),
        retrieves their latest checkpoint, and marks them as 'paused_for_resume'
        to prevent dangling states and enable automated resumption.
        """
        await self.initialize()
        recovered: List[Dict[str, Any]] = []
        now = time.time()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM goal_queue WHERE status = 'running'") as cursor:
                interrupted_rows = [dict(r) async for r in cursor]

            for row in interrupted_rows:
                g_id = row["goal_id"]
                # Fetch latest checkpoint
                checkpoints = await self.get_checkpoints_for_goal(g_id)
                latest_chk = checkpoints[-1] if checkpoints else None

                # Transition to paused_for_resume
                await db.execute(
                    "UPDATE goal_queue SET status = 'paused_for_resume', updated_at = ? WHERE goal_id = ?",
                    (now, g_id),
                )
                await db.commit()

                rec_entry = {
                    "goal_id": g_id,
                    "title": row["title"],
                    "current_step_index": row["current_step_index"],
                    "total_steps": row["total_steps"],
                    "latest_checkpoint": latest_chk,
                    "recovered_at": now,
                }
                recovered.append(rec_entry)
                logger.warning(
                    "[LongHorizonCheckpoint] Self-recovered interrupted goal '{}' ('{}') at step {}/{}",
                    g_id,
                    row["title"],
                    row["current_step_index"],
                    row["total_steps"],
                )

        return recovered

    async def resume_goal(self, goal_id: str) -> Dict[str, Any]:
        """
        Restores execution context for an interrupted or paused goal.
        Aggregates all previously created artifacts and identifies the exact next step.
        """
        await self.initialize()

        # Fetch goal
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM goal_queue WHERE goal_id = ?", (goal_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise ValueError(f"Goal '{goal_id}' does not exist")
                goal_data = dict(row)

        checkpoints = await self.get_checkpoints_for_goal(goal_id)
        latest_chk = checkpoints[-1] if checkpoints else None

        # Aggregate artifacts across all completed checkpoints
        all_artifacts: List[str] = []
        for chk in checkpoints:
            for art in chk.get("artifacts", []):
                if art not in all_artifacts:
                    all_artifacts.append(art)

        next_step_index = goal_data.get("current_step_index", 0) + 1

        # Re-activate goal to running
        await self.set_goal_status(goal_id, "running")

        logger.info(
            "[LongHorizonCheckpoint] Resumed goal '{}' ('{}') -> proceeding to Step {}/{}",
            goal_id,
            goal_data.get("title"),
            next_step_index,
            goal_data.get("total_steps"),
        )

        return {
            "goal_id": goal_id,
            "title": goal_data.get("title"),
            "description": goal_data.get("description"),
            "status": "running",
            "resume_from_step": next_step_index,
            "total_steps": goal_data.get("total_steps"),
            "latest_checkpoint": latest_chk,
            "accumulated_artifacts": all_artifacts,
        }

    async def fail_goal_with_recovery_checkpoint(
        self,
        goal_id: str,
        step_index: int,
        error_message: str,
        recoverable: bool = True,
    ) -> Dict[str, Any]:
        """
        Records an error state checkpoint preserving all context up to the failure point,
        marking the goal as 'paused_recoverable' so that self-healing or retry can take place.
        """
        await self.initialize()
        status = "paused_recoverable" if recoverable else "failed"

        chk = await self.create_checkpoint(
            goal_id=goal_id,
            step_title=f"Step {step_index} Error",
            state_data={
                "step_index": step_index,
                "error": error_message,
                "recoverable": recoverable,
                "failed_at": time.time(),
            },
        )
        await self.set_goal_status(goal_id, status)
        logger.warning(
            "[LongHorizonCheckpoint] Goal '{}' marked as '{}' at step {}: {}",
            goal_id,
            status,
            step_index,
            error_message,
        )
        return {
            "goal_id": goal_id,
            "status": status,
            "error": error_message,
            "checkpoint_id": chk["checkpoint_id"],
        }

