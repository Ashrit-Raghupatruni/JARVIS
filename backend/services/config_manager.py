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
                from backend.config import _settings_instance
                import backend.config as cfg
                cfg._settings_instance = new_settings
                
                await self._event_bus.publish("config_reloaded", {"changes": changes})
                logger.info(f"Configuration hot-reloaded successfully with {len(changes)} field changes.")
                return True
        except Exception as e:
            logger.error(f"Failed to hot-reload configuration: {e}")
        return False

    def update_custom_names(self, assistant_name: str, user_name: str) -> dict:
        """Dynamically update assistant and user preferred names at runtime."""
        a_name = assistant_name.strip() or "JARVIS"
        u_name = user_name.strip() or "User"
        
        setattr(self._settings, "ASSISTANT_NAME", a_name)
        setattr(self._settings, "USER_PREFERRED_NAME", u_name)
        logger.info(f"Updated Assistant Customization: Assistant='{a_name}', User='{u_name}'")
        return {"status": "ok", "assistant_name": a_name, "user_preferred_name": u_name}
