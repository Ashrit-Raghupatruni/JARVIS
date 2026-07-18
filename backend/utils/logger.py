"""
JARVIS AI Desktop Assistant - Logger Configuration.

Configures loguru for the entire application with:
- Colorized console output for development.
- Rotating file logs (10 MB max, 5 backups retained).
- Structured format: timestamp | level | module | message.
"""

import sys
from pathlib import Path

from loguru import logger

# ── Paths ────────────────────────────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_LOG_DIR = _BACKEND_DIR / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Format Strings ───────────────────────────────────────────────────────────
_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{module}:{function}:{line} | "
    "{message}"
)


def setup_logger(
    console_level: str = "DEBUG",
    file_level: str = "DEBUG",
    log_dir: Path | None = None,
) -> "logger":
    """
    Configure and return the application-wide loguru logger.

    Removes all default handlers and sets up:
      1. A colorized stderr handler for console output.
      2. A rotating file handler that caps each log file at 10 MB
         and retains the 5 most recent rotations.

    Args:
        console_level: Minimum log level for console output.
        file_level: Minimum log level for file output.
        log_dir: Override directory for log files. Defaults to ``backend/logs/``.

    Returns:
        The configured ``loguru.logger`` instance.
    """
    target_dir = log_dir or _LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    # Remove default handlers to avoid duplicate output
    logger.remove()

    # ── Console handler ──────────────────────────────────────────────────
    logger.add(
        sys.stderr,
        format=_CONSOLE_FORMAT,
        level=console_level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # ── Rotating file handler ────────────────────────────────────────────
    logger.add(
        str(target_dir / "jarvis_{time:YYYY-MM-DD}.log"),
        format=_FILE_FORMAT,
        level=file_level,
        rotation="10 MB",
        retention=5,
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True,  # Thread-safe writing
    )

    # ── Error-specific log ───────────────────────────────────────────────
    logger.add(
        str(target_dir / "jarvis_errors.log"),
        format=_FILE_FORMAT,
        level="ERROR",
        rotation="10 MB",
        retention=5,
        compression="zip",
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )

    logger.info("Logger initialised — console={}, file={}", console_level, file_level)
    return logger


# ── Auto-configure on import ─────────────────────────────────────────────────
setup_logger()


def register_event_bus_sink(event_bus) -> None:
    """Register the event bus as a Loguru sink to stream all system logs."""
    import asyncio
    
    def event_bus_sink(message):
        try:
            record = message.record
            # Ignore event_bus logs to prevent infinite loops
            if record["module"] in ("event_bus", "logger"):
                return
                
            log_data = {
                "time": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "level": record["level"].name,
                "message": record["message"],
                "module": record["module"],
                "function": record["function"],
                "line": record["line"]
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(event_bus.publish("log.new", log_data))
            except RuntimeError:
                pass
        except Exception:
            pass

    logger.add(
        event_bus_sink,
        level="DEBUG",
        format="{message}",
        serialize=False,
    )


__all__ = ["logger", "setup_logger", "register_event_bus_sink"]
