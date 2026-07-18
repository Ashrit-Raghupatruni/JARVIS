from typing import Dict, Type, Any
from loguru import logger
from backend.services.base import BaseService

class ServiceManager:
    """Centralized service manager supporting registration, lazy-loading, and lifecycle coordination."""
    
    _services: Dict[str, Any] = {}
    _classes: Dict[str, Type] = {}
    
    @classmethod
    def register_class(cls, name: str, service_class: Type) -> None:
        """Register a class for lazy-loading."""
        cls._classes[name] = service_class
        logger.info(f"Service class '{name}' registered for lazy loading")
        
    @classmethod
    def register_instance(cls, name: str, instance: Any) -> None:
        """Register a pre-initialized service instance."""
        cls._services[name] = instance
        logger.info(f"Service instance '{name}' registered")
        
    @classmethod
    async def get(cls, name: str) -> Any:
        """Get or lazily initialize a registered service."""
        if name in cls._services:
            return cls._services[name]
            
        if name in cls._classes:
            service_class = cls._classes[name]
            logger.info(f"Lazily initializing service '{name}'...")
            try:
                instance = service_class()
                cls._services[name] = instance
                if isinstance(instance, BaseService) or hasattr(instance, "initialize"):
                    await instance.initialize()
                logger.info(f"✓ Service '{name}' initialized successfully")
                return instance
            except Exception as e:
                logger.error(f"✗ Failed to initialize service '{name}': {e}")
                raise e
                
        raise ValueError(f"Service '{name}' is not registered")
        
    @classmethod
    async def shutdown_all(cls) -> None:
        """Shutdown all active services."""
        for name, service in list(cls._services.items()):
            if isinstance(service, BaseService) or hasattr(service, "shutdown"):
                logger.info(f"Shutting down service '{name}'...")
                try:
                    await service.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down service '{name}': {e}")
        cls._services.clear()
