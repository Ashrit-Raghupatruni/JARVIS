import os
from pathlib import Path
from loguru import logger
from backend.config import get_settings, Settings
from backend.utils.event_bus import EventBus

class ConfigurationManager:
    """Manages centralized settings loading, runtime overrides, and hot-reload triggers."""
    
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._settings = get_settings()
        self._env_path = Path(self._settings.model_config.get("env_file", ".env"))
        self._last_modified = self._get_env_modified_time()
        
    def _get_env_modified_time(self) -> float:
        if self._env_path.exists():
            return os.path.getmtime(self._env_path)
        return 0.0
        
    @property
    def settings(self) -> Settings:
        return self._settings
        
    async def reload_if_changed(self) -> bool:
        """Check if .env was updated on disk and trigger reload."""
        current_modified = self._get_env_modified_time()
        if current_modified > self._last_modified:
            logger.info("Detecting changes in .env file, hot-reloading configurations...")
            self._last_modified = current_modified
            return await self.reload()
        return False
        
    async def reload(self) -> bool:
        """Reload configuration settings and broadcast changed values."""
        try:
            from backend.config import Settings
            # Force reload settings instance
            new_settings = Settings()
            
            changes = {}
            for field in new_settings.model_fields:
                old_val = getattr(self._settings, field, None)
                new_val = getattr(new_settings, field, None)
                if old_val != new_val:
                    changes[field] = {"old": old_val, "new": new_val}
            
            if changes:
                self._settings = new_settings
                # Explicitly override the global cache as well
                import backend.config
                backend.config._settings = new_settings
                logger.info(f"✓ Configuration hot-reloaded: {list(changes.keys())}")
                await self._event_bus.publish("config.updated", changes)
                return True
            else:
                logger.info("No configuration changes detected during reload")
                return False
        except Exception as e:
            logger.error(f"✗ Failed to reload settings: {e}")
            return False
