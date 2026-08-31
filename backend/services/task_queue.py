"""
JARVIS AI OS — Task Queue & Background Job Scheduler Service.
============================================================
Provides priority background job queuing (HIGH, MEDIUM, LOW),
asynchronous worker execution, cancellation, and job status tracking.
"""

import asyncio
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Awaitable
from loguru import logger


class TaskPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskItem(BaseModel := type("BaseModel", (), {})):
    pass


class TaskQueueManager:
    """Central Priority Task Queue & Worker Pool Manager."""

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.queue: List[str] = []

    def enqueue_task(
        self,
        name: str,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.MEDIUM,
        timeout_seconds: float = 15.0,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """Enqueue a new background task for execution."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task_record = {
            "task_id": task_id,
            "name": name,
            "priority": priority.value,
            "status": TaskStatus.PENDING.value,
            "payload": payload,
            "result": None,
            "error": None,
            "timeout_seconds": timeout_seconds,
            "max_retries": max_retries,
            "retries_performed": 0,
            "created_at": time.time(),
            "completed_at": None
        }
        self.tasks[task_id] = task_record
        self.queue.append(task_id)
        logger.info("📋 Enqueued task '{}' (ID: {}, Priority: {}, Timeout: {}s)", name, task_id, priority.value, timeout_seconds)
        return task_record

    async def execute_next_task(self, executor_fn: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None) -> Optional[Dict[str, Any]]:
        """Process and execute the highest-priority pending task with timeout and retry protection."""
        if not self.queue:
            return None

        # System resource safety guard
        try:
            import psutil
            mem_pct = psutil.virtual_memory().percent
            if mem_pct > 95.0:
                logger.warning("⚠️ High RAM pressure ({}%), delaying background queue execution by 500ms...", mem_pct)
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # Sort queue by priority: HIGH -> MEDIUM -> LOW
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        self.queue.sort(key=lambda tid: priority_order.get(self.tasks[tid]["priority"], 1))
        
        task_id = self.queue.pop(0)
        task = self.tasks[task_id]
        task["status"] = TaskStatus.RUNNING.value
        
        start_t = time.time()
        timeout_sec = task.get("timeout_seconds", 15.0)
        logger.info("🚀 Processing background task '{}' (ID: {}, Timeout: {}s)", task["name"], task_id, timeout_sec)

        try:
            if executor_fn:
                res = await asyncio.wait_for(executor_fn(task["payload"]), timeout=timeout_sec)
            else:
                await asyncio.sleep(0.05)
                res = {"status": "success", "message": f"Completed background task '{task['name']}'."}

            task["status"] = TaskStatus.COMPLETED.value
            task["result"] = res
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
        """Handles automatic retry for failed or timed out background tasks."""
        retries = task.get("retries_performed", 0)
        max_retries = task.get("max_retries", 2)
        if retries < max_retries:
            task["retries_performed"] = retries + 1
            task["status"] = TaskStatus.PENDING.value
            self.queue.append(task_id)
            logger.warning("🔄 Re-enqueuing task '{}' (Retry {}/{})", task_id, retries + 1, max_retries)
        else:
            task["status"] = TaskStatus.FAILED.value
            task["completed_at"] = time.time()


    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status and result for a specific task ID."""
        return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running background task."""
        if task_id in self.tasks:
            current_status = self.tasks[task_id]["status"]
            if current_status in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
                self.tasks[task_id]["status"] = TaskStatus.CANCELLED.value
                self.tasks[task_id]["completed_at"] = time.time()
                if task_id in self.queue:
                    self.queue.remove(task_id)
                logger.info("🚫 Cancelled task '{}' (prior state: {})", task_id, current_status)
                return True
        return False

    def cancel_all(self) -> int:
        """Cancel all pending and running background tasks."""
        cancelled = 0
        for tid in list(self.tasks.keys()):
            if self.cancel_task(tid):
                cancelled += 1
        return cancelled


# Global Singleton Task Queue Manager
task_queue_manager = TaskQueueManager()


# Alias TaskQueueService for backwards-compatibility with main.py service manager
TaskQueueService = TaskQueueManager
