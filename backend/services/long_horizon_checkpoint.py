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
                (status, now, goal_id)
            )
            await db.commit()
            return cursor.rowcount > 0
