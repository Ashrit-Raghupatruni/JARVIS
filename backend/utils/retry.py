"""
Exponential Backoff & Retry Decorator for JARVIS.

Provides resilient retries with exponential backoff and jitter for transient API failures.
"""

import asyncio
import random
import functools
from typing import Callable, Any
from loguru import logger


def exponential_backoff_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator for retrying async functions with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Cap for maximum delay in seconds.
        exceptions: Tuple of exception types to catch and retry.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Function '{func.__name__}' failed after {max_retries} attempts: {e}")
                        raise
                    jitter = random.uniform(0.8, 1.2)
                    current_delay = min(max_delay, delay * jitter)
                    logger.warning(
                        f"Transient error in '{func.__name__}' (attempt {attempt}/{max_retries}): {e}. "
                        f"Retrying in {current_delay:.2f}s..."
                    )
                    await asyncio.sleep(current_delay)
                    delay *= 2.0
        return wrapper
    return decorator
