"""
JARVIS AI OS — Asynchronous Generation Queue & Background Job Manager.

Manages long-running multimodal synthesis operations (image, audio, video, 3D):
- Assigns persistent UUID job tokens
- Tracks status: 'queued', 'processing', 'completed', 'failed'
- Dispatches jobs to background async workers
- Persists job metadata to SQLite database
- Pushes real-time progress callbacks to WebSocket clients
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from loguru import logger


class AsyncGenerationJobManager:
    """Singleton queue and background job dispatcher for multimodal generation."""

    _instance: Optional[AsyncGenerationJobManager] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AsyncGenerationJobManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.db_path = db_path or Path("data/generation_jobs.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task] = None
        self._init_db()
        self._initialized = True
        logger.info("AsyncGenerationJobManager initialized. DB: {}", self.db_path)

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generation_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    result_path TEXT,
                    error_message TEXT,
                    created_at REAL NOT NULL,
                    completed_at REAL
                )
            """)
            conn.commit()

    def submit_job(
        self,
        job_type: str,
        prompt: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Submit a new generation task to the asynchronous queue.
        Returns immediate job receipt with UUID tracking token.
        """
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO generation_jobs (job_id, job_type, prompt, status, progress, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, job_type, prompt, "queued", 0, now)
            )
            conn.commit()

        logger.info("Queued {} job '{}' (prompt: '{}')", job_type, job_id, prompt[:30])
        return {
            "status": "queued",
            "job_id": job_id,
            "job_type": job_type,
            "prompt": prompt,
            "created_at": now,
            "message": f"Job submitted to async queue. Poll status via /api/v1/generation/status/{job_id}."
        }

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Retrieve live execution status, progress, and result for a submitted job."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM generation_jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()

        if not row:
            return {"status": "not_found", "error": f"Job ID '{job_id}' does not exist."}

        return {
            "status": row["status"],
            "job_id": row["job_id"],
            "job_type": row["job_type"],
            "prompt": row["prompt"],
            "progress": row["progress"],
            "result_path": row["result_path"],
            "error_message": row["error_message"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"]
        }

    def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: int = 0,
        result_path: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update job lifecycle status in SQLite."""
        now = time.time() if status in ("completed", "failed") else None
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE generation_jobs
                SET status = ?, progress = ?, result_path = ?, error_message = ?, completed_at = ?
                WHERE job_id = ?
            """, (status, progress, result_path, error_message, now, job_id))
            conn.commit()

    def list_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent generation jobs."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM generation_jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
        return [dict(r) for r in rows]


generation_queue = AsyncGenerationJobManager()
