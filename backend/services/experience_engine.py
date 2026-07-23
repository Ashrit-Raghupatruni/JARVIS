"""
JARVIS AI Operating System - Experience Engine Service.

Records every action, plan, tool usage, execution time, result, success/failure status,
confidence score, failure reason, recovery method, and alternative strategies into a dedicated
SQLite WAL database ('data/experiences.db') for continuous AI learning and strategy optimization.
"""

import os
import time
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger


class ExperienceEngineService:
    """Experience Engine for recording, indexing, and recalling operational experiences."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data/experiences.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info("ExperienceEngineService initialized at {}", self.db_path)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize SQLite WAL database tables for experience traces."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiences (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    plan TEXT,
                    tools_used TEXT,
                    execution_steps TEXT,
                    execution_time_seconds REAL,
                    result TEXT,
                    success INTEGER NOT NULL,
                    confidence_score REAL,
                    failure_reason TEXT,
                    recovery_method TEXT,
                    alternative_method TEXT,
                    timestamp REAL NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_goal ON experiences(goal);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_exp_success ON experiences(success);")
            conn.commit()

    def record_experience(
        self,
        goal: str,
        plan: Optional[List[str]] = None,
        tools_used: Optional[List[str]] = None,
        execution_steps: Optional[List[Dict[str, Any]]] = None,
        execution_time_seconds: float = 0.0,
        result: str = "",
        success: bool = True,
        confidence_score: float = 1.0,
        failure_reason: Optional[str] = None,
        recovery_method: Optional[str] = None,
        alternative_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record an executed action experience trace."""
        exp_id = f"exp_{int(time.time() * 1000)}"
        timestamp = time.time()

        plan_json = json.dumps(plan or [])
        tools_json = json.dumps(tools_used or [])
        steps_json = json.dumps(execution_steps or [])

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO experiences (
                    id, goal, plan, tools_used, execution_steps, execution_time_seconds,
                    result, success, confidence_score, failure_reason, recovery_method,
                    alternative_method, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exp_id, goal, plan_json, tools_json, steps_json, execution_time_seconds,
                    result, 1 if success else 0, confidence_score, failure_reason or "",
                    recovery_method or "", alternative_method or "", timestamp
                )
            )
            conn.commit()

        logger.info("🧠 Experience recorded: '{}' (success={}, confidence={:.2f})", goal, success, confidence_score)

        return {
            "id": exp_id,
            "goal": goal,
            "success": success,
            "confidence_score": confidence_score,
            "timestamp": timestamp
        }

    def query_experiences(self, goal_query: str = "", limit: int = 10) -> List[Dict[str, Any]]:
        """Query past experience traces matching a goal or task intent."""
        with self._get_connection() as conn:
            if goal_query:
                cursor = conn.execute(
                    "SELECT * FROM experiences WHERE goal LIKE ? ORDER BY timestamp DESC LIMIT ?",
                    (f"%{goal_query}%", limit)
                )
            else:
                cursor = conn.execute("SELECT * FROM experiences ORDER BY timestamp DESC LIMIT ?", (limit,))
            
            rows = cursor.fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r["id"],
                    "goal": r["goal"],
                    "plan": json.loads(r["plan"] or "[]"),
                    "tools_used": json.loads(r["tools_used"] or "[]"),
                    "execution_steps": json.loads(r["execution_steps"] or "[]"),
                    "execution_time_seconds": r["execution_time_seconds"],
                    "result": r["result"],
                    "success": bool(r["success"]),
                    "confidence_score": r["confidence_score"],
                    "failure_reason": r["failure_reason"],
                    "recovery_method": r["recovery_method"],
                    "alternative_method": r["alternative_method"],
                    "timestamp": r["timestamp"]
                })
            return results

    def get_success_rate(self, goal_keyword: str) -> float:
        """Calculate historical success rate for a specific type of task."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as total, SUM(success) as total_success FROM experiences WHERE goal LIKE ?",
                (f"%{goal_keyword}%",)
            )
            row = cursor.fetchone()
            if not row or row["total"] == 0:
                return 0.90  # Default initial confidence baseline
            return round(row["total_success"] / row["total"], 2)
