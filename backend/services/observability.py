"""
Observability, Telemetry & Diagnostics Service for JARVIS.

Handles distributed trace correlation IDs (trace_id), background worker queue monitoring,
crash reporting, system health checks, and telemetry analytics exporting.
"""

import time
import uuid
import psutil
from typing import Any, Dict, List, Optional
from loguru import logger


class ObservabilityService:
    """Service for Phase 15 Telemetry, Tracing & System Health Diagnostics."""

    def __init__(self):
        self._crash_logs: List[Dict[str, Any]] = []
        self._active_traces: Dict[str, Dict[str, Any]] = {}
        logger.info("ObservabilityService initialized (Trace correlation ID engine active).")

    def start_trace(self, operation_name: str) -> str:
        """Generate a new distributed trace correlation ID."""
        trace_id = str(uuid.uuid4())[:8]
        self._active_traces[trace_id] = {
            "trace_id": trace_id,
            "operation": operation_name,
            "start_time": time.time(),
            "status": "running"
        }
        return trace_id

    def finish_trace(self, trace_id: str, status: str = "completed") -> Optional[Dict[str, Any]]:
        """Complete an active trace and calculate latency."""
        trace = self._active_traces.get(trace_id)
        if trace:
            trace["status"] = status
            trace["end_time"] = time.time()
            trace["duration_ms"] = round((trace["end_time"] - trace["start_time"]) * 1000.0, 2)
            del self._active_traces[trace_id]
            return trace
        return None

    def log_crash_report(self, component: str, error_msg: str, traceback_str: str = "") -> Dict[str, Any]:
        """Record a system crash or error report."""
        report = {
            "id": len(self._crash_logs) + 1,
            "timestamp": time.time(),
            "component": component,
            "error_message": error_msg,
            "traceback": traceback_str[:500]
        }
        self._crash_logs.append(report)
        logger.error("Logged crash report for '{}': {}", component, error_msg)
        return report

    def get_system_health(self) -> Dict[str, Any]:
        """Return complete hardware, worker queue, and system health status."""
        ram = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=None)
        disk = psutil.disk_usage('/')

        return {
            "health_status": "HEALTHY" if cpu_pct < 95.0 and ram.percent < 95.0 else "DEGRADED",
            "cpu_usage_percent": cpu_pct,
            "ram_usage_percent": ram.percent,
            "disk_usage_percent": disk.percent,
            "active_traces_count": len(self._active_traces),
            "crash_reports_count": len(self._crash_logs),
            "timestamp": time.time()
        }
