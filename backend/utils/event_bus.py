import asyncio
import re
from typing import Callable, Any, Dict, List, Awaitable, Union
from loguru import logger

class Event:
    def __init__(self, topic: str, data: Any = None):
        self.topic = topic
        self.data = data

class EventBus:
    """Asynchronous, thread-safe, topic-based event bus for decoupled communication."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Event], Union[None, Awaitable[None]]]]] = {}
        self._lock = asyncio.Lock()
        
    async def subscribe(self, topic_pattern: str, callback: Callable[[Event], Union[None, Awaitable[None]]]) -> None:
        """Subscribe a callback to a topic pattern (supports simple * wildcard matching)."""
        async with self._lock:
            if topic_pattern not in self._subscribers:
                self._subscribers[topic_pattern] = []
            self._subscribers[topic_pattern].append(callback)
            logger.debug(f"Subscribed callback to topic pattern '{topic_pattern}'")
            
    async def unsubscribe(self, topic_pattern: str, callback: Callable[[Event], Union[None, Awaitable[None]]]) -> None:
        """Unsubscribe a callback from a topic pattern."""
        async with self._lock:
            if topic_pattern in self._subscribers:
                try:
                    self._subscribers[topic_pattern].remove(callback)
                    logger.debug(f"Unsubscribed callback from topic pattern '{topic_pattern}'")
                except ValueError:
                    pass

    async def publish(self, topic: str, data: Any = None) -> None:
        """Publish an event to all matching subscribers asynchronously."""
        event = Event(topic, data)
        callbacks_to_run = []
        
        async with self._lock:
            for pattern, callbacks in self._subscribers.items():
                if self._match_topic(pattern, topic):
                    callbacks_to_run.extend(callbacks)
                    
        for callback in callbacks_to_run:
            asyncio.create_task(self._safe_invoke(callback, event))
            
    def _match_topic(self, pattern: str, topic: str) -> bool:
        """Match topic string against a pattern supporting * wildcard."""
        regex_pattern = "^" + pattern.replace(".", "\\.").replace("*", ".*") + "$"
        return bool(re.match(regex_pattern, topic))
        
    async def _safe_invoke(self, callback: Callable[[Event], Union[None, Awaitable[None]]], event: Event) -> None:
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception as e:
            logger.error(f"Error in EventBus subscriber callback for topic '{event.topic}': {e}")
