"""
JARVIS AI Desktop Assistant - Task Queue & Scheduler Service.

Provides a multi-task execution queue with support for task prioritization,
reordering, pause, resume, cancellation, and execution progress streaming.
"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class QueuedTask:
    id: str
    title: str
    command: str
    priority: int = 1  # Higher number = higher priority
    status: str = "pending"  # "pending", "running", "paused", "completed", "failed", "cancelled"
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    logs: List[str] = field(default_factory=list)
    result: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "command": self.command,
            "priority": self.priority,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "logs": self.logs[-10:],
            "result": self.result,
            "metadata": self.metadata,
        }


class TaskQueueService:
    """
    Manages task scheduling, multi-task execution queue, reordering, and state persistence.
    """

    def __init__(self, max_concurrent_tasks: int = 3) -> None:
        self.max_concurrent_tasks = max_concurrent_tasks
        self.tasks: Dict[str, QueuedTask] = {}
        self.task_order: List[str] = []
        self._lock = asyncio.Lock()
        self._paused = False
        logger.info("TaskQueueService initialized (max_concurrent={})", max_concurrent_tasks)

        # Seed default initial system tasks
        self._seed_default_tasks()

    def _seed_default_tasks(self) -> None:
        t1 = QueuedTask(
            id="task-001",
            title="System Diagnostics & Telemetry Check",
            command="Check system status and hardware gauges",
            priority=2,
            status="completed",
            progress=1.0,
            result="All hardware metrics nominal. Temperature 42°C, RAM 38%.",
            logs=["Task queued", "Running diagnostics...", "Metrics collected", "Completed successfully"]
        )
        t2 = QueuedTask(
            id="task-002",
            title="Local Knowledge Base Indexing",
            command="Index project codebase and docs",
            priority=1,
            status="running",
            progress=0.65,
            logs=["Task queued", "Scanning project files...", "Vectorizing chunks in ChromaDB..."]
        )
        self.tasks[t1.id] = t1
        self.tasks[t2.id] = t2
        self.task_order = [t2.id, t1.id]

    async def add_task(self, title: str, command: str, priority: int = 1, metadata: Optional[Dict[str, Any]] = None) -> QueuedTask:
        async with self._lock:
            task_id = f"task-{uuid.uuid4().hex[:6]}"
            task = QueuedTask(
                id=task_id,
                title=title,
                command=command,
                priority=priority,
                status="pending",
                metadata=metadata or {}
            )
            task.logs.append(f"Task queued at {time.strftime('%H:%M:%S')}")
            self.tasks[task_id] = task
            self.task_order.insert(0, task_id)
            logger.info("Task queued: {} (id={}, priority={})", title, task_id, priority)
            return task

    async def reorder_tasks(self, new_order: List[str]) -> List[Dict[str, Any]]:
        async with self._lock:
            valid_order = [t_id for t_id in new_order if t_id in self.tasks]
            for t_id in self.task_order:
                if t_id not in valid_order:
                    valid_order.append(t_id)
            self.task_order = valid_order
            logger.info("Task queue reordered — count={}", len(self.task_order))
            return self.get_queue_summary()

    async def pause_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status in ["pending", "running"]:
                    task.status = "paused"
                    task.logs.append(f"Task paused by user at {time.strftime('%H:%M:%S')}")
                    logger.info("Task paused: {}", task_id)
                    return True
        return False

    async def resume_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status == "paused":
                    task.status = "pending"
                    task.logs.append(f"Task resumed at {time.strftime('%H:%M:%S')}")
                    logger.info("Task resumed: {}", task_id)
                    return True
        return False

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status not in ["completed", "failed", "cancelled"]:
                    task.status = "cancelled"
                    task.logs.append(f"Task cancelled at {time.strftime('%H:%M:%S')}")
                    logger.info("Task cancelled: {}", task_id)
                    return True
        return False

    async def set_task_priority(self, task_id: str, priority: int) -> bool:
        async with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].priority = priority
                logger.info("Task priority updated: {} -> {}", task_id, priority)
                return True
        return False

    def get_queue_summary(self) -> List[Dict[str, Any]]:
        result = []
        for t_id in self.task_order:
            if t_id in self.tasks:
                result.append(self.tasks[t_id].to_dict())
        return result
