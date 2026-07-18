import asyncio
import uuid
from typing import Callable, Any, Dict, Awaitable, Optional
from loguru import logger
from backend.utils.event_bus import EventBus

class AsyncTask:
    def __init__(self, name: str, coro_func: Callable[[], Awaitable[Any]]):
        self.id = str(uuid.uuid4())
        self.name = name
        self.coro_func = coro_func
        self.status = "pending"
        self.result = None
        self.error = None

class AsyncTaskQueue:
    """Manages sequential execution of async backend tasks with logging and state updates."""
    
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._queue: asyncio.Queue[AsyncTask] = asyncio.Queue()
        self._tasks_registry: Dict[str, AsyncTask] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        
    def start(self) -> None:
        """Start the queue worker."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._queue_worker())
            logger.info("✓ Async task queue worker started")
            
    async def stop(self) -> None:
        """Stop the queue worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Async task queue worker stopped")
            
    async def submit(self, name: str, coro_func: Callable[[], Awaitable[Any]]) -> str:
        """Submit a task to the queue and return its ID."""
        task = AsyncTask(name, coro_func)
        self._tasks_registry[task.id] = task
        await self._queue.put(task)
        logger.info(f"Task '{name}' submitted (ID: {task.id})")
        await self._event_bus.publish("task.submitted", {"task_id": task.id, "name": name})
        return task.id
        
    async def _queue_worker(self) -> None:
        while self._running:
            try:
                task = await self._queue.get()
                task.status = "running"
                await self._event_bus.publish("task.started", {"task_id": task.id, "name": task.name})
                logger.info(f"Running task '{task.name}'...")
                
                try:
                    task.result = await task.coro_func()
                    task.status = "completed"
                    await self._event_bus.publish("task.completed", {"task_id": task.id, "name": task.name, "result": task.result})
                    logger.info(f"✓ Task '{task.name}' completed successfully")
                except Exception as e:
                    task.error = e
                    task.status = "failed"
                    await self._event_bus.publish("task.failed", {"task_id": task.id, "name": task.name, "error": str(e)})
                    logger.error(f"✗ Task '{task.name}' failed: {e}")
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in task queue worker loop: {e}")
                await asyncio.sleep(1)
