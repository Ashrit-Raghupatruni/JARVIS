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

    def enqueue_task(self, name: str, payload: Dict[str, Any], priority: TaskPriority = TaskPriority.MEDIUM) -> Dict[str, Any]:
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
            "created_at": time.time(),
            "completed_at": None
        }
        self.tasks[task_id] = task_record
        self.queue.append(task_id)
        logger.info("📋 Enqueued task '{}' (ID: {}, Priority: {})", name, task_id, priority.value)
        return task_record

    async def execute_next_task(self, executor_fn: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None) -> Optional[Dict[str, Any]]:
        """Process and execute the highest-priority pending task."""
        if not self.queue:
            return None

        # Sort queue by priority: HIGH -> MEDIUM -> LOW
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        self.queue.sort(key=lambda tid: priority_order.get(self.tasks[tid]["priority"], 1))
        
        task_id = self.queue.pop(0)
        task = self.tasks[task_id]
        task["status"] = TaskStatus.RUNNING.value
        
        start_t = time.time()
        logger.info("🚀 Processing background task '{}' (ID: {})", task["name"], task_id)

        try:
            if executor_fn:
                res = await executor_fn(task["payload"])
            else:
                await asyncio.sleep(0.05)
                res = {"status": "success", "message": f"Completed background task '{task['name']}'."}

            task["status"] = TaskStatus.COMPLETED.value
            task["result"] = res
            task["completed_at"] = time.time()
            logger.info("✓ Completed task '{}' in {:.2f}s", task_id, time.time() - start_t)

        except Exception as e:
            task["status"] = TaskStatus.FAILED.value
            task["error"] = str(e)
            logger.error("❌ Task '{}' failed: {}", task_id, e)

        return task

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status and result for a specific task ID."""
        return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending background task."""
        if task_id in self.tasks and self.tasks[task_id]["status"] == TaskStatus.PENDING.value:
            self.tasks[task_id]["status"] = TaskStatus.CANCELLED.value
            if task_id in self.queue:
                self.queue.remove(task_id)
            logger.info("🚫 Cancelled task '{}'", task_id)
            return True
        return False


# Global Singleton Task Queue Manager
task_queue_manager = TaskQueueManager()
