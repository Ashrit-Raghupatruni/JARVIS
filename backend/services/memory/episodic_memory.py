"""
JARVIS AI OS — Episodic & Procedural Memory.

Consolidates:
1. High-fidelity task execution traces (SQLite WAL `data/experiences.db`).
2. Procedural strategy confidence scoring and task outcome history (`data/strategy_memory.json`).
3. Lessons learned and error corrections (ChromaDB + SQLite).
4. Reusable successful workflows (ChromaDB + SQLite).
5. Fast episodic goal history (`data/memory/episodic_memory.json`).
"""

import os
import time
import json
import uuid
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger
from sqlalchemy import select

from backend.config import get_settings
from backend.models.database import LessonLearned, SuccessfulWorkflow


class EpisodicMemory:
    """
    Episodic Memory manages:
    - Operational task experiences and metrics in `data/experiences.db`.
    - Procedural automation strategy confidence rankings in `data/strategy_memory.json`.
    - Lessons learned / user corrections in ChromaDB & SQLite.
    - Reusable action plans and successful workflows.
    """

    def __init__(
        self,
        session_factory=None,
        lessons_collection=None,
        workflows_collection=None,
        data_dir: Optional[Path] = None
    ):
        settings = get_settings()
        self.data_dir = data_dir or settings.data_path
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_factory = session_factory
        self.lessons_collection = lessons_collection
        self.workflows_collection = workflows_collection

        # Experiences DB
        self.exp_db_path = self.data_dir / "experiences.db"
        self._init_exp_db()

        # Strategy Memory JSON
        self.strategy_file = self.data_dir / "strategy_memory.json"
        self.strategies: Dict[str, Any] = self._load_strategies()

        # Simple episodic JSON log
        self.episodic_log_path = self.data_dir / "memory" / "episodic_memory.json"
        self.episodic_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.episodic_log: List[Dict[str, Any]] = self._load_episodic_log()

        logger.info("EpisodicMemory initialized.")

    def set_backends(self, session_factory=None, lessons_collection=None, workflows_collection=None):
        if session_factory:
            self.session_factory = session_factory
        if lessons_collection:
            self.lessons_collection = lessons_collection
        if workflows_collection:
            self.workflows_collection = workflows_collection

    # ── Experiences DB (SQLite WAL) ──────────────────────────────────────

    def _get_exp_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.exp_db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_exp_db(self) -> None:
        with self._get_exp_conn() as conn:
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
        """Record high-fidelity operational experience trace."""
        exp_id = f"exp_{int(time.time() * 1000)}"
        timestamp = time.time()

        plan_json = json.dumps(plan or [])
        tools_json = json.dumps(tools_used or [])
        steps_json = json.dumps(execution_steps or [])

        with self._get_exp_conn() as conn:
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

        # Also mirror to simple episodic log
        self.record_episode(goal=goal, result=result, success=success)

        return {
            "id": exp_id,
            "goal": goal,
            "success": success,
            "confidence_score": confidence_score
        }

    def query_experiences(
        self,
        goal_query: Optional[str] = None,
        limit: int = 10,
        only_successful: bool = False
    ) -> List[Dict[str, Any]]:
        """Query past experience traces matching a goal."""
        query = "SELECT * FROM experiences"
        params = []
        conditions = []

        if only_successful:
            conditions.append("success = 1")
        if goal_query:
            conditions.append("goal LIKE ?")
            params.append(f"%{goal_query}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_exp_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "goal": r["goal"],
                "plan": json.loads(r["plan"]) if r["plan"] else [],
                "tools_used": json.loads(r["tools_used"]) if r["tools_used"] else [],
                "execution_steps": json.loads(r["execution_steps"]) if r["execution_steps"] else [],
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

    def get_success_rate(self, tool_or_goal: str) -> Dict[str, Any]:
        with self._get_exp_conn() as conn:
            row = conn.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                    AVG(confidence_score) as avg_confidence
                FROM experiences
                WHERE goal LIKE ? OR tools_used LIKE ?
                """,
                (f"%{tool_or_goal}%", f"%{tool_or_goal}%")
            ).fetchone()

        total = row["total"] or 0
        successes = row["successes"] or 0
        rate = (successes / total) if total > 0 else 1.0

        return {
            "query": tool_or_goal,
            "total_attempts": total,
            "success_count": successes,
            "success_rate": rate,
            "avg_confidence": row["avg_confidence"] or 1.0
        }

    # ── Strategy Confidence & Task History ────────────────────────────────

    def _load_strategies(self) -> Dict[str, Any]:
        if self.strategy_file.exists():
            try:
                with open(self.strategy_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Could not load strategy JSON: {}", e)

        return {
            "ui_automation": [
                {"strategy": "win32_uia", "name": "Native Win32 Accessibility HWND Tree", "confidence": 0.95, "success_count": 0, "fail_count": 0},
                {"strategy": "browser_playwright", "name": "Playwright Browser Selector", "confidence": 0.92, "success_count": 0, "fail_count": 0},
                {"strategy": "ocr_screen", "name": "Tesseract/OpenCV Screen Bounds OCR", "confidence": 0.70, "success_count": 0, "fail_count": 0},
                {"strategy": "pixel_clicking", "name": "Hardcoded Pixel Coordinate Click", "confidence": 0.40, "success_count": 0, "fail_count": 0}
            ],
            "file_search": [
                {"strategy": "sqlite_fts5", "name": "SQLite FTS5 Natural Language Indexer", "confidence": 0.98, "success_count": 0, "fail_count": 0},
                {"strategy": "python_os_walk", "name": "Python os.walk Recursive Search", "confidence": 0.85, "success_count": 0, "fail_count": 0}
            ],
            "app_launch": [
                {"strategy": "shutil_which", "name": "PATH Executable Resolution", "confidence": 0.96, "success_count": 0, "fail_count": 0},
                {"strategy": "win32_start", "name": "Windows Shell Execute", "confidence": 0.90, "success_count": 0, "fail_count": 0}
            ]
        }

    def _save_strategies(self) -> None:
        try:
            with open(self.strategy_file, "w", encoding="utf-8") as f:
                json.dump(self.strategies, f, indent=2)
        except Exception as e:
            logger.error("Failed to save strategy JSON: {}", e)

    def get_ranked_strategies(self, category: str = "ui_automation") -> List[Dict[str, Any]]:
        strats = self.strategies.get(category, [])
        return sorted(strats, key=lambda x: x.get("confidence", 0.5), reverse=True)

    def get_preferred_strategy(self, category: str = "ui_automation") -> Dict[str, Any]:
        ranked = self.get_ranked_strategies(category)
        if ranked:
            return ranked[0]
        return {"strategy": "win32_uia", "confidence": 0.95, "name": "Default Win32 UIA"}

    def record_task_strategy_outcome(self, task_name: str, strategy_id: str, success: bool, failure_reason: str = "") -> None:
        t_key = task_name.lower().strip()
        task_memory = self.strategies.setdefault("_task_history", {})
        
        entry = task_memory.get(t_key, {"successful_strategy": None, "failed_strategies": []})
        if success:
            entry["successful_strategy"] = strategy_id
            self.update_strategy_outcome("ui_automation", strategy_id, reward=1.0)
        else:
            if strategy_id not in entry.get("failed_strategies", []):
                entry.setdefault("failed_strategies", []).append(strategy_id)
            self.update_strategy_outcome("ui_automation", strategy_id, reward=-2.0)
            
        task_memory[t_key] = entry
        self.strategies["_task_history"] = task_memory
        self._save_strategies()

    def get_best_strategy_for_task(self, task_name: str, category: str = "ui_automation") -> Dict[str, Any]:
        t_key = task_name.lower().strip()
        task_memory = self.strategies.get("_task_history", {}).get(t_key, {})
        
        successful_strat = task_memory.get("successful_strategy")
        if successful_strat:
            for s in self.strategies.get(category, []):
                if s.get("strategy") == successful_strat:
                    return s

        failed_strats = task_memory.get("failed_strategies", [])
        ranked = self.get_ranked_strategies(category)
        for s in ranked:
            if s.get("strategy") not in failed_strats:
                return s

        return ranked[0] if ranked else {"strategy": "win32_uia", "confidence": 0.5}

    def update_strategy_outcome(self, category: str, strategy_id: str, reward: float = 1.0) -> None:
        strats = self.strategies.get(category, [])
        for s in strats:
            if s.get("strategy") == strategy_id:
                if reward > 0:
                    s["success_count"] = s.get("success_count", 0) + 1
                    s["confidence"] = min(0.99, s.get("confidence", 0.5) + 0.02 * reward)
                else:
                    s["fail_count"] = s.get("fail_count", 0) + 1
                    s["confidence"] = max(0.10, s.get("confidence", 0.5) + 0.05 * reward)
                break
        self._save_strategies()

    # ── Lessons Learned & Successful Workflows ───────────────────────────

    async def store_lesson(self, trigger: str, error_desc: str, correction: str) -> str:
        lesson_id = f"lesson_{uuid.uuid4().hex[:12]}"
        if self.lessons_collection:
            content_str = f"Trigger: {trigger} | Error: {error_desc} | Correction: {correction}"
            try:
                self.lessons_collection.add(
                    documents=[content_str],
                    metadatas=[{"trigger": trigger, "correction": correction}],
                    ids=[lesson_id]
                )
            except Exception as e:
                logger.error("ChromaDB lesson store failed: {}", e)

        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    lesson = LessonLearned(
                        id=lesson_id,
                        trigger_keywords=trigger,
                        error_description=error_desc,
                        correction=correction
                    )
                    session.add(lesson)
                    await session.commit()
            except Exception as e:
                logger.error("SQLite lesson store failed: {}", e)

        return lesson_id

    async def store_workflow(self, task: str, steps: list, opt_prompt: str = "") -> str:
        wf_id = f"wf_{uuid.uuid4().hex[:12]}"
        steps_str = json.dumps(steps)
        content_str = f"Task: {task} | Steps: {steps_str}"

        if self.workflows_collection:
            try:
                self.workflows_collection.add(
                    documents=[content_str],
                    metadatas=[{"task": task, "opt_prompt": opt_prompt}],
                    ids=[wf_id]
                )
            except Exception as e:
                logger.error("ChromaDB workflow store failed: {}", e)

        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    workflow = SuccessfulWorkflow(
                        id=wf_id,
                        task_description=task,
                        steps_json=steps_str,
                        optimized_prompt=opt_prompt
                    )
                    session.add(workflow)
                    await session.commit()
            except Exception as e:
                logger.error("SQLite workflow store failed: {}", e)

        return wf_id

    # ── Simple Episodic JSON Backup ──────────────────────────────────────

    def _load_episodic_log(self) -> List[Dict[str, Any]]:
        if self.episodic_log_path.exists():
            try:
                with open(self.episodic_log_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def record_episode(self, goal: str, result: str, success: bool = True) -> None:
        episode = {
            "goal": goal,
            "result": result,
            "success": success,
            "timestamp": time.time()
        }
        self.episodic_log.append(episode)
        # Keep bounded to last 100 entries
        if len(self.episodic_log) > 100:
            self.episodic_log = self.episodic_log[-100:]
        try:
            with open(self.episodic_log_path, "w", encoding="utf-8") as f:
                json.dump(self.episodic_log, f, indent=2)
        except Exception as e:
            logger.error("Failed to save episodic JSON log: {}", e)
