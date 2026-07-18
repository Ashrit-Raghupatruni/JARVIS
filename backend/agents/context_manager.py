import uuid
from typing import Dict, Any
from loguru import logger
from backend.utils.event_bus import EventBus

class SharedContextManager:
    """Manages global runtime context, active sessions, and agent states."""
    
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._session_id: str = str(uuid.uuid4())
        self._state: Dict[str, Any] = {
            "status": "idle",
            "active_tasks": {},
            "active_agents": {},
            "user_preferences": {},
        }
        
    @property
    def session_id(self) -> str:
        return self._session_id
        
    def reset_session(self) -> str:
        self._session_id = str(uuid.uuid4())
        logger.info(f"Reset global session ID: {self._session_id}")
        return self._session_id
        
    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)
        
    async def set(self, key: str, value: Any) -> None:
        old_value = self._state.get(key)
        self._state[key] = value
        logger.debug(f"Shared context set: {key} = {value}")
        await self._event_bus.publish(f"context.updated.{key}", {"key": key, "old_value": old_value, "new_value": value})
        
    async def update_status(self, new_status: str) -> None:
        """Update global system status (idle, listening, processing, speaking, executing)."""
        old_status = self._state.get("status")
        if old_status != new_status:
            self._state["status"] = new_status
            logger.info(f"System status transition: {old_status} ➔ {new_status}")
            await self._event_bus.publish("system.status_changed", {"old_status": old_status, "new_status": new_status})
