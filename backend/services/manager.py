from typing import Dict, Type, Any, TypeVar, Optional, cast
from loguru import logger
from backend.services.base import BaseService

T = TypeVar("T")


class ServiceManager:
    """Centralized service manager supporting typed dependency injection, registration, lazy-loading, and lifecycle coordination."""

    _services: Dict[str, Any] = {}
    _classes: Dict[str, Type] = {}
    _typed_instances: Dict[Type, Any] = {}

    @classmethod
    def register(cls, service_type: Type[T], instance: T) -> None:
        """Register a service by its explicit Type for compile-time/static type safety."""
        cls._typed_instances[service_type] = instance
        # Also register under class name for string compatibility
        cls._services[service_type.__name__] = instance
        cls._services[service_type.__name__.lower()] = instance
        logger.debug("Service instance for type '{}' registered via typed DI", service_type.__name__)

    @classmethod
    def resolve(cls, service_type: Type[T]) -> T:
        """Type-safe dependency injection lookup. Returns strictly typed instance or raises KeyError."""
        if service_type in cls._typed_instances:
            return cast(T, cls._typed_instances[service_type])

        # Check by instance type
        for instance in cls._typed_instances.values():
            if isinstance(instance, service_type):
                return cast(T, instance)

        for instance in cls._services.values():
            if isinstance(instance, service_type):
                return cast(T, instance)

        # Check by name keys
        for key in (service_type.__name__, service_type.__name__.lower()):
            if key in cls._services and isinstance(cls._services[key], service_type):
                return cast(T, cls._services[key])

        raise KeyError(f"Service of type '{service_type.__name__}' is not registered in ServiceManager")

    @classmethod
    def get_typed(cls, service_type: Type[T]) -> Optional[T]:
        """Type-safe dependency injection lookup returning Optional[T] if not found."""
        try:
            return cls.resolve(service_type)
        except KeyError:
            return None

    @classmethod
    def inject(cls, service_type: Type[T]) -> T:
        """FastAPI-compatible Depends resolver for typed dependency injection."""
        return cls.resolve(service_type)

    @classmethod
    def register_class(cls, name: str, service_class: Type) -> None:
        """Register a class for lazy-loading."""
        cls._classes[name] = service_class
        logger.info(f"Service class '{name}' registered for lazy loading")

    @classmethod
    def register_instance(cls, name: str, instance: Any) -> None:
        """Register a pre-initialized service instance and index its concrete type."""
        cls._services[name] = instance
        if instance is not None:
            cls._typed_instances[type(instance)] = instance
        logger.info(f"Service instance '{name}' registered")

    @classmethod
    def get_instance(cls, name: str) -> Any:
        """Synchronously get a pre-registered service instance, returning None if not found."""
        return cls._services.get(name)

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
                cls._typed_instances[type(instance)] = instance
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
        cls._typed_instances.clear()

