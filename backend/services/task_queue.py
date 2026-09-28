"""
JARVIS AI OS — Task Queue & Background Job Scheduler Service.
============================================================
Provides priority background job queuing (HIGH, MEDIUM, LOW),
persistent SQLite WAL durability, asynchronous worker execution,
cancellation, pause/resume, and real-time frontend synchronization.
"""

import asyncio
import json
import os
import sqlite3
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Awaitable
from loguru import logger
import aiosqlite

from backend.config import get_settings


class TaskPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


DEFAULT_SEED_TASKS = [
    {
        "id": "t-1",
        "title": "System Diagnostics & Telemetry",
        "command": "Check system status and hardware gauges",
        "priority": 2,
        "status": "completed",
        "progress": 1.0,
        "logs": ["Diagnostics started", "Metrics aggregated", "Nominal"],
        "result": "Hardware nominal: CPU 34%, RAM 41%",
        "error": None,
        "peak_memory_mb": 42.5,
        "cpu_time_seconds": 1.2,
    },
    {
        "id": "t-2",
        "title": "Local Knowledge Base Indexing",
        "command": "Index project codebase & ChromaDB vector embeddings",
        "priority": 1,
        "status": "running",
        "progress": 0.68,
        "logs": ["Scanning project tree...", "Vectorizing chunks in ChromaDB..."],
        "result": None,
        "error": None,
        "peak_memory_mb": 115.0,
        "cpu_time_seconds": 4.8,
    },
    {
        "id": "t-3",
        "title": "Automated Repository Backup",
        "command": "Generate local ZIP archive of development workspace",
        "priority": 1,
        "status": "pending",
        "progress": 0.0,
        "logs": ["Queued for background worker"],
        "result": None,
        "error": None,
        "peak_memory_mb": 0.0,
        "cpu_time_seconds": 0.0,
    },
]


def _broadcast_task_event(event_type: str, data: Dict[str, Any]) -> None:
    """Helper to broadcast task events over WebSocket and EventBus."""
    try:
        from backend.api.websocket import manager
        from backend.models.schemas import WSMessage
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast(WSMessage(
                type="task_update",
                data={"event": event_type, "task": data}
            )))
    except Exception:
        pass

    try:
        from backend.services.manager import ServiceManager
        bus = ServiceManager.get_instance("event_bus")
        if bus and hasattr(bus, "publish"):
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(bus.publish(f"task.{event_type}", data))
    except Exception:
        pass


class TaskQueueManager:
    """Central Persistent Priority Task Queue & Worker Pool Manager."""

    def __init__(self, db_path: Optional[str] = None):
        settings = get_settings()
        self.db_path = db_path or str(settings.data_path / "jarvis.db")
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.queue: List[str] = []
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize SQLite WAL table for persistent tasks and seed defaults if empty."""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL;")
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS persistent_tasks (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        command TEXT,
                        priority INTEGER DEFAULT 1,
                        status TEXT NOT NULL,
                        progress REAL DEFAULT 0.0,
                        logs_json TEXT DEFAULT '[]',
                        result TEXT,
                        error TEXT,
                        peak_memory_mb REAL DEFAULT 0.0,
                        cpu_time_seconds REAL DEFAULT 0.0,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """)
                await db.commit()

                # Seed defaults if completely empty
                async with db.execute("SELECT COUNT(*) FROM persistent_tasks") as cur:
                    row = await cur.fetchone()
                    count = row[0] if row else 0

                now = time.time()
                if count == 0:
                    for seed in DEFAULT_SEED_TASKS:
                        await db.execute(
                            """
                            INSERT INTO persistent_tasks
                            (id, title, command, priority, status, progress, logs_json, result, error, peak_memory_mb, cpu_time_seconds, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                seed["id"],
                                seed["title"],
                                seed["command"],
                                seed["priority"],
                                seed["status"],
                                seed["progress"],
                                json.dumps(seed.get("logs", [])),
                                seed.get("result"),
                                seed.get("error"),
                                seed.get("peak_memory_mb", 0.0),
                                seed.get("cpu_time_seconds", 0.0),
                                now,
                                now,
                            )
                        )
                    await db.commit()

                # Load tasks into in-memory queue
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM persistent_tasks ORDER BY priority ASC, created_at DESC") as cur:
                    async for r in cur:
                        task_dict = {
                            "id": r["id"],
                            "task_id": r["id"],
                            "name": r["title"],
                            "title": r["title"],
                            "command": r["command"] or "",
                            "priority": r["priority"],
                            "status": r["status"],
                            "progress": r["progress"],
                            "logs": json.loads(r["logs_json"] or "[]"),
                            "result": r["result"],
                            "error": r["error"],
                            "peak_memory_mb": r["peak_memory_mb"],
                            "cpu_time_seconds": r["cpu_time_seconds"],
                            "created_at": r["created_at"],
                            "updated_at": r["updated_at"],
                        }
                        self.tasks[r["id"]] = task_dict
                        if r["status"] in (TaskStatus.PENDING.value, "PENDING"):
                            if r["id"] not in self.queue:
                                self.queue.append(r["id"])

            self._initialized = True
            logger.info("[TaskQueue] Initialized persistent SQLite task queue ({} tasks loaded)", len(self.tasks))

    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Fetch all tasks from SQLite ordered by priority and recency."""
        await self.initialize()
        tasks_list = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM persistent_tasks ORDER BY priority ASC, created_at DESC") as cur:
                async for r in cur:
                    tasks_list.append({
                        "id": r["id"],
                        "title": r["title"],
                        "command": r["command"] or "",
                        "priority": r["priority"],
                        "status": r["status"].lower(),
                        "progress": float(r["progress"] or 0.0),
                        "logs": json.loads(r["logs_json"] or "[]"),
                        "result": r["result"],
                        "error": r["error"],
                        "peak_memory_mb": float(r["peak_memory_mb"] or 0.0),
                        "cpu_time_seconds": float(r["cpu_time_seconds"] or 0.0),
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                    })
        return tasks_list

    async def create_task(
        self,
        title: str,
        command: str = "",
        priority: int = 1,
        timeout_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        """Create and persist a new user or autonomous task."""
        await self.initialize()
        task_id = f"t-{uuid.uuid4().hex[:6]}"
        now = time.time()
        initial_logs = ["Task queued for background execution"]

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO persistent_tasks
                (id, title, command, priority, status, progress, logs_json, result, error, peak_memory_mb, cpu_time_seconds, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    title,
                    command or title,
                    priority,
                    TaskStatus.PENDING.value,
                    0.0,
                    json.dumps(initial_logs),
                    None,
                    None,
                    0.0,
                    0.0,
                    now,
                    now,
                )
            )
            await db.commit()

        task_record = {
            "id": task_id,
            "task_id": task_id,
            "name": title,
            "title": title,
            "command": command or title,
            "priority": priority,
            "status": TaskStatus.PENDING.value,
            "progress": 0.0,
            "logs": initial_logs,
            "result": None,
            "error": None,
            "timeout_seconds": timeout_seconds,
            "peak_memory_mb": 0.0,
            "cpu_time_seconds": 0.0,
            "created_at": now,
            "updated_at": now,
        }
        self.tasks[task_id] = task_record
        self.queue.append(task_id)

        logger.info("[TaskQueue] Created and persisted task '{}' (ID: {})", title, task_id)
        _broadcast_task_event("created", task_record)
        return task_record

    async def pause_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Pause a pending or running task and persist to SQLite."""
        await self.initialize()
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE persistent_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (TaskStatus.PAUSED.value, now, task_id)
            )
            await db.commit()

        if task_id in self.tasks:
            self.tasks[task_id]["status"] = TaskStatus.PAUSED.value
            self.tasks[task_id]["updated_at"] = now
            if task_id in self.queue:
                self.queue.remove(task_id)
            logger.info("[TaskQueue] Paused task '{}'", task_id)
            _broadcast_task_event("paused", self.tasks[task_id])
            return self.tasks[task_id]

        return None

    async def resume_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Resume a paused task and persist to SQLite."""
        await self.initialize()
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE persistent_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (TaskStatus.PENDING.value, now, task_id)
            )
            await db.commit()

        if task_id in self.tasks:
            self.tasks[task_id]["status"] = TaskStatus.PENDING.value
            self.tasks[task_id]["updated_at"] = now
            if task_id not in self.queue:
                self.queue.append(task_id)
            logger.info("[TaskQueue] Resumed task '{}'", task_id)
            _broadcast_task_event("resumed", self.tasks[task_id])
            return self.tasks[task_id]

        return None

    async def cancel_task_async(self, task_id: str) -> bool:
        """Cancel a task and persist status='cancelled' to SQLite."""
        await self.initialize()
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "UPDATE persistent_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (TaskStatus.CANCELLED.value, now, task_id)
            )
            await db.commit()
            rowcount = cur.rowcount

        if task_id in self.tasks:
            self.tasks[task_id]["status"] = TaskStatus.CANCELLED.value
            self.tasks[task_id]["updated_at"] = now
            if task_id in self.queue:
                self.queue.remove(task_id)
            logger.info("[TaskQueue] Cancelled task '{}'", task_id)
            _broadcast_task_event("cancelled", self.tasks[task_id])
            return True

        return rowcount > 0

    async def reorder_tasks(self, order: List[str]) -> bool:
        """Update priorities based on user drag-and-drop order."""
        await self.initialize()
        now = time.time()
        async with aiosqlite.connect(self.db_path) as db:
            for idx, tid in enumerate(order):
                prio = idx + 1
                await db.execute(
                    "UPDATE persistent_tasks SET priority = ?, updated_at = ? WHERE id = ?",
                    (prio, now, tid)
                )
                if tid in self.tasks:
                    self.tasks[tid]["priority"] = prio
            await db.commit()

        _broadcast_task_event("reordered", {"order": order})
        return True

    async def update_task_progress(
        self,
        task_id: str,
        progress: float,
        log_entry: Optional[str] = None,
        status: Optional[str] = None,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update progress, status, and append logs to SQLite."""
        await self.initialize()
        now = time.time()

        task = self.tasks.get(task_id)
        if not task:
            return None

        task["progress"] = min(1.0, max(0.0, progress))
        task["updated_at"] = now
        if log_entry:
            task["logs"].append(log_entry)
        if status:
            task["status"] = status
        if result:
            task["result"] = result
        if error:
            task["error"] = error

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE persistent_tasks
                SET progress = ?, logs_json = ?, status = ?, result = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    task["progress"],
                    json.dumps(task["logs"]),
                    task["status"],
                    task["result"],
                    task["error"],
                    now,
                    task_id,
                )
            )
            await db.commit()

        _broadcast_task_event("progress", task)
        return task

    # ── Legacy Synchronous API Compatibility for Test Suites & Subsystems ────

    def enqueue_task(
        self,
        name: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.MEDIUM,
        timeout_seconds: float = 15.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """Enqueue task for synchronous callers and tests."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task_record = {
            "id": task_id,
            "task_id": task_id,
            "name": name,
            "title": name,
            "command": payload.get("command", name) if isinstance(payload, dict) else name,
            "priority": priority.value if hasattr(priority, "value") else priority,
            "status": "PENDING",
            "payload": payload,
            "result": None,
            "error": None,
            "timeout_seconds": timeout_seconds,
            "max_retries": max_retries,
            "retries_performed": 0,
            "progress": 0.0,
            "logs": ["Enqueued via background worker"],
            "created_at": time.time(),
            "updated_at": time.time(),
            "completed_at": None
        }
        self.tasks[task_id] = task_record
        self.queue.append(task_id)
        logger.info("📋 Enqueued task '{}' (ID: {}, Priority: {})", name, task_id, task_record["priority"])
        return task_record

    async def execute_next_task(
        self,
        executor_fn: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Process highest-priority task in queue."""
        if not self.queue:
            return None

        # Sort queue by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, 0: 0, 1: 1, 2: 2, 3: 3}
        self.queue.sort(key=lambda tid: priority_order.get(self.tasks.get(tid, {}).get("priority", 1), 1))

        task_id = self.queue.pop(0)
        task = self.tasks[task_id]
        task["status"] = "RUNNING"
        start_t = time.time()
        timeout_sec = task.get("timeout_seconds", 15.0)

        try:
            if executor_fn:
                payload = task.get("payload", {})
                res = await asyncio.wait_for(executor_fn(payload), timeout=timeout_sec)
            else:
                await asyncio.sleep(0.05)
                res = {"status": "success", "message": f"Completed background task '{task['name']}'."}

            task["status"] = "COMPLETED"
            task["result"] = res
            task["progress"] = 1.0
            task["completed_at"] = time.time()
            logger.info("✓ Completed task '{}' in {:.2f}s", task_id, time.time() - start_t)
        except asyncio.TimeoutError:
            task["error"] = f"Task timed out after {timeout_sec}s"
            logger.error("⏱️ Task '{}' timed out after {}s", task_id, timeout_sec)
            self._handle_retry(task_id, task)
        except Exception as e:
            task["error"] = str(e)
            logger.error("❌ Task '{}' failed: {}", task_id, e)
            self._handle_retry(task_id, task)

        return task

    def _handle_retry(self, task_id: str, task: Dict[str, Any]) -> None:
        retries = task.get("retries_performed", 0)
        max_retries = task.get("max_retries", 2)
        if retries < max_retries:
            task["retries_performed"] = retries + 1
            task["status"] = "PENDING"
            self.queue.append(task_id)
            logger.warning("🔄 Re-enqueuing task '{}' (Retry {}/{})", task_id, retries + 1, max_retries)
        else:
            task["status"] = "FAILED"
            task["completed_at"] = time.time()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Synchronous cancel for test compatibility, async SQLite update in background."""
        if task_id in self.tasks:
            current_status = self.tasks[task_id].get("status", "")
            if current_status in (TaskStatus.PENDING.value, "PENDING", TaskStatus.RUNNING.value, "RUNNING"):
                self.tasks[task_id]["status"] = TaskStatus.CANCELLED.value
                self.tasks[task_id]["completed_at"] = time.time()
                if task_id in self.queue:
                    self.queue.remove(task_id)

                # Persist to SQLite if event loop is running
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.cancel_task_async(task_id))
                except Exception:
                    pass

                return True
        return False

    def cancel_all(self) -> int:
        cancelled = 0
        for tid in list(self.tasks.keys()):
            if self.cancel_task(tid):
                cancelled += 1
        return cancelled


# Global Singleton Task Queue Manager
task_queue_manager = TaskQueueManager()

# Alias TaskQueueService for backwards-compatibility with main.py service manager
TaskQueueService = TaskQueueManager
