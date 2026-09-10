from __future__ import annotations

import inspect
import threading
from typing import Dict, Type, Any, TypeVar, Optional, Callable, List, cast
from loguru import logger
from backend.services.base import BaseService

T = TypeVar("T")


class ServiceManager:
    """Centralized service container supporting typed dependency injection, registration, lazy-loading factories, and lifecycle coordination."""

    _instances: Dict[str, Any] = {}
    _typed_instances: Dict[Type, Any] = {}
    _factories: Dict[str, Callable[[], Any]] = {}
    _typed_factories: Dict[Type, Callable[[], Any]] = {}
    _classes: Dict[str, Type] = {}
    _initialized_flags: Dict[str, bool] = {}
    _lock = threading.RLock()

    # ── Registration Methods ───────────────────────────────────────────────

    @classmethod
    def register_factory(
        cls,
        name: str,
        factory: Callable[[], Any],
        service_type: Optional[Type] = None
    ) -> None:
        """Register a lazy-loading factory that is invoked only when the service is first requested."""
        with cls._lock:
            cls._factories[name] = factory
            cls._factories[name.lower()] = factory
            if service_type is not None:
                cls._typed_factories[service_type] = factory
                cls._factories[service_type.__name__] = factory
                cls._factories[service_type.__name__.lower()] = factory
            logger.debug(f"Service factory for '{name}' registered for lazy loading")

    @classmethod
    def register_instance(cls, name: str, instance: Any) -> None:
        """Register a pre-initialized service instance and index its concrete type."""
        with cls._lock:
            cls._instances[name] = instance
            cls._instances[name.lower()] = instance
            if instance is not None:
                concrete_type = type(instance)
                cls._typed_instances[concrete_type] = instance
                cls._instances[concrete_type.__name__] = instance
                cls._instances[concrete_type.__name__.lower()] = instance
            logger.info(f"Service instance '{name}' registered")

    @classmethod
    def register(cls, service_type: Type[T], instance: T) -> None:
        """Register a service by its explicit Type for compile-time/static type safety."""
        with cls._lock:
            cls._typed_instances[service_type] = instance
            cls._instances[service_type.__name__] = instance
            cls._instances[service_type.__name__.lower()] = instance
            if instance is not None and type(instance) != service_type:
                cls._typed_instances[type(instance)] = instance
            logger.debug(f"Service instance for type '{service_type.__name__}' registered via typed DI")

    @classmethod
    def register_class(cls, name: str, service_class: Type) -> None:
        """Register a class for lazy-loading instantiation."""
        with cls._lock:
            cls._classes[name] = service_class
            cls._classes[name.lower()] = service_class
            logger.debug(f"Service class '{name}' registered for lazy loading")

    # ── Resolution & Getter Methods ────────────────────────────────────────

    @classmethod
    def get_instance(cls, name: str) -> Any:
        """
        Synchronously get a service instance.
        If not yet instantiated but registered via factory or class, it is lazily initialized on demand.
        Returns None if the service is unknown.
        """
        # 1. Fast check without acquiring lock if already instantiated
        if name in cls._instances:
            return cls._instances[name]
        lower_name = name.lower()
        if lower_name in cls._instances:
            return cls._instances[lower_name]

        with cls._lock:
            # Double-check inside lock
            if name in cls._instances:
                return cls._instances[name]
            if lower_name in cls._instances:
                return cls._instances[lower_name]

            # 2. Check registered factory
            factory = cls._factories.get(name) or cls._factories.get(lower_name)
            if factory is not None:
                try:
                    logger.info(f"⚡ Lazily initializing service '{name}' via factory...")
                    instance = factory()
                    cls._instances[name] = instance
                    cls._instances[lower_name] = instance
                    if instance is not None:
                        concrete_type = type(instance)
                        cls._typed_instances[concrete_type] = instance
                        cls._instances[concrete_type.__name__] = instance
                        cls._instances[concrete_type.__name__.lower()] = instance
                    logger.info(f"✓ Service '{name}' lazily instantiated successfully")
                    return instance
                except Exception as e:
                    logger.error(f"✗ Failed to lazily instantiate service '{name}' via factory: {e}")
                    raise e

            # 3. Check registered class
            service_class = cls._classes.get(name) or cls._classes.get(lower_name)
            if service_class is not None:
                try:
                    logger.info(f"⚡ Lazily initializing service class '{name}'...")
                    instance = service_class()
                    cls._instances[name] = instance
                    cls._instances[lower_name] = instance
                    if instance is not None:
                        cls._typed_instances[type(instance)] = instance
                    logger.info(f"✓ Service '{name}' instantiated from class successfully")
                    return instance
                except Exception as e:
                    logger.error(f"✗ Failed to lazily instantiate service class '{name}': {e}")
                    raise e

        return None

    @classmethod
    def resolve(cls, service_type: Type[T]) -> T:
        """Type-safe dependency injection lookup. Returns strictly typed instance or raises KeyError."""
        # 1. Check existing typed instances
        if service_type in cls._typed_instances:
            return cast(T, cls._typed_instances[service_type])

        # 2. Check instances by isinstance
        for instance in cls._typed_instances.values():
            if isinstance(instance, service_type):
                return cast(T, instance)

        for instance in cls._instances.values():
            if isinstance(instance, service_type):
                return cast(T, instance)

        # 3. Check name lookup
        name_keys = (service_type.__name__, service_type.__name__.lower())
        for key in name_keys:
            if key in cls._instances and isinstance(cls._instances[key], service_type):
                return cast(T, cls._instances[key])

        # 4. Check lazy factories by type or name
        with cls._lock:
            if service_type in cls._typed_factories:
                instance = cls._typed_factories[service_type]()
                cls._typed_instances[service_type] = instance
                cls._instances[service_type.__name__] = instance
                cls._instances[service_type.__name__.lower()] = instance
                return cast(T, instance)

            for key in name_keys:
                if key in cls._factories:
                    instance = cls._factories[key]()
                    cls._typed_instances[service_type] = instance
                    cls._instances[key] = instance
                    return cast(T, instance)

            for key in name_keys:
                if key in cls._classes:
                    instance = cls._classes[key]()
                    cls._typed_instances[service_type] = instance
                    cls._instances[key] = instance
                    return cast(T, instance)

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
    async def get(cls, name: str) -> Any:
        """Get or lazily initialize a registered service, invoking async initialize() lifecycle if present."""
        instance = cls.get_instance(name)
        if instance is not None:
            # Check if async initialize needs to be run once
            if not cls._initialized_flags.get(name, False):
                if isinstance(instance, BaseService) or hasattr(instance, "initialize"):
                    init_fn = getattr(instance, "initialize", None)
                    if init_fn and callable(init_fn):
                        if inspect.iscoroutinefunction(init_fn):
                            await init_fn()
                        else:
                            init_fn()
                cls._initialized_flags[name] = True
            return instance

        raise ValueError(f"Service '{name}' is not registered")

    # ── Inspection & Diagnostics ───────────────────────────────────────────

    @classmethod
    def is_initialized(cls, name: str) -> bool:
        """Check if a service is actively instantiated in memory."""
        return name in cls._instances or name.lower() in cls._instances

    @classmethod
    def list_active_services(cls) -> List[str]:
        """List all currently instantiated service names."""
        return list(cls._instances.keys())

    @classmethod
    def list_registered_factories(cls) -> List[str]:
        """List all registered lazy factory names."""
        return list(cls._factories.keys())

    # ── Lifecycle Shutdown ─────────────────────────────────────────────────

    @classmethod
    async def shutdown_all(cls) -> None:
        """Shutdown all active service singletons gracefully."""
        with cls._lock:
            active_items = list(cls._instances.items())
            seen_ids = set()

            for name, service in active_items:
                if service is None or id(service) in seen_ids:
                    continue
                seen_ids.add(id(service))

                if isinstance(service, BaseService) or hasattr(service, "shutdown") or hasattr(service, "close"):
                    logger.info(f"Shutting down service '{name}'...")
                    try:
                        shutdown_fn = getattr(service, "shutdown", None) or getattr(service, "close", None)
                        if shutdown_fn and callable(shutdown_fn):
                            if inspect.iscoroutinefunction(shutdown_fn):
                                await shutdown_fn()
                            else:
                                shutdown_fn()
                    except Exception as e:
                        logger.error(f"Error shutting down service '{name}': {e}")

            cls._instances.clear()
            cls._typed_instances.clear()
            cls._initialized_flags.clear()
            logger.info("✓ All active services shut down successfully.")

