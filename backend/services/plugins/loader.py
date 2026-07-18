import importlib.util
import os
from pathlib import Path
from typing import Dict, Type, Any
from loguru import logger

class BasePlugin:
    """Base interface for all JARVIS plugins."""
    
    def __init__(self, app_state: Any = None):
        self.app_state = app_state
        
    def activate(self) -> None:
        """Called when the plugin is loaded and registered."""
        pass
        
    def deactivate(self) -> None:
        """Called when the plugin is unloaded."""
        pass

class PluginLoader:
    """Discovers and dynamically imports plugins from the plugins directory."""
    
    def __init__(self, app_state: Any = None, plugins_dir: str = "plugins"):
        self.app_state = app_state
        self.plugins_path = Path(plugins_dir)
        self.loaded_plugins: Dict[str, BasePlugin] = {}
        
    def discover_and_load(self) -> Dict[str, BasePlugin]:
        """Scan directory and dynamically load valid plugins."""
        if not self.plugins_path.exists():
            logger.warning(f"Plugins directory '{self.plugins_path}' does not exist, creating it.")
            self.plugins_path.mkdir(parents=True, exist_ok=True)
            
        for file in self.plugins_path.glob("*.py"):
            if file.name.startswith("__"):
                continue
                
            module_name = f"plugins.{file.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, file)
                if spec is None or spec.loader is None:
                    continue
                    
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Scan module classes to find BasePlugin subclasses
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type) 
                        and issubclass(attr, BasePlugin) 
                        and attr is not BasePlugin
                    ):
                        plugin_instance = attr(self.app_state)
                        plugin_instance.activate()
                        self.loaded_plugins[file.stem] = plugin_instance
                        logger.info(f"✓ Dynamic plugin '{file.stem}' loaded and activated successfully")
            except Exception as e:
                logger.error(f"✗ Failed to load plugin '{file.stem}': {e}")
                
        return self.loaded_plugins
        
    def unload_all(self) -> None:
        """Unload and deactivate all plugins."""
        for name, plugin in list(self.loaded_plugins.items()):
            try:
                plugin.deactivate()
                logger.info(f"Unloaded plugin '{name}'")
            except Exception as e:
                logger.error(f"Error unloading plugin '{name}': {e}")
        self.loaded_plugins.clear()
