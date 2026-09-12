from __future__ import annotations

import enum
import inspect
import threading
from typing import Dict, Type, Any, TypeVar, Optional, Callable, List, Set, cast
from loguru import logger
from backend.services.base import BaseService

T = TypeVar("T")


class ServiceState(str, enum.Enum):
    """Lifecycle states of a registered service."""
    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class CircularDependencyError(RuntimeError):
    """Raised when a circular dependency is detected during service resolution."""
    pass


class _ThreadLocalStack(threading.local):
    """Thread-local storage for tracking active service resolution stacks."""
    def __init__(self):
        super().__init__()
        self.stack: List[str] = []


_thread_local = _ThreadLocalStack()


class ServiceManager:
    """
    Centralized service container supporting typed dependency injection,
    lazy-loading factories, circular dependency detection, and lifecycle coordination.
    """

    _instances: Dict[str, Any] = {}
    _canonical_names: Dict[str, str] = {}
    _typed_instances: Dict[Type, Any] = {}
    _factories: Dict[str, Callable[[], Any]] = {}
    _typed_factories: Dict[Type, Callable[[], Any]] = {}
    _classes: Dict[str, Type] = {}
    _states: Dict[str, ServiceState] = {}
    _initialized_flags: Dict[str, bool] = {}
    _init_order: List[str] = []
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
        canonical = name.strip()
        lower_name = canonical.lower()

        with cls._lock:
            cls._factories[canonical] = factory
            cls._factories[lower_name] = factory
            cls._canonical_names[lower_name] = canonical
            cls._states[canonical] = ServiceState.UNINITIALIZED
            cls._states[lower_name] = ServiceState.UNINITIALIZED

            if service_type is not None:
                cls._typed_factories[service_type] = factory
                cls._factories[service_type.__name__] = factory
                cls._factories[service_type.__name__.lower()] = factory
                cls._canonical_names[service_type.__name__.lower()] = service_type.__name__

            logger.debug(f"Service factory for '{canonical}' registered for lazy loading")

    @classmethod
    def register_instance(cls, name: str, instance: Any) -> None:
        """Register a pre-initialized service instance and index its concrete type."""
        canonical = name.strip()
        lower_name = canonical.lower()

        with cls._lock:
            cls._instances[canonical] = instance
            cls._instances[lower_name] = instance
            cls._canonical_names[lower_name] = canonical
            cls._states[canonical] = ServiceState.READY
            cls._states[lower_name] = ServiceState.READY

            if canonical not in cls._init_order:
                cls._init_order.append(canonical)

            if instance is not None:
                concrete_type = type(instance)
                cls._typed_instances[concrete_type] = instance
                cls._instances[concrete_type.__name__] = instance
                cls._instances[concrete_type.__name__.lower()] = instance
                cls._canonical_names[concrete_type.__name__.lower()] = concrete_type.__name__

            logger.info(f"Service instance '{canonical}' registered (state: READY)")

    @classmethod
    def register(cls, service_type: Type[T], instance: T) -> None:
        """Register a service by its explicit Type for compile-time/static type safety."""
        canonical = service_type.__name__
        lower_name = canonical.lower()

        with cls._lock:
            cls._typed_instances[service_type] = instance
            cls._instances[canonical] = instance
            cls._instances[lower_name] = instance
            cls._canonical_names[lower_name] = canonical
            cls._states[canonical] = ServiceState.READY
            cls._states[lower_name] = ServiceState.READY

            if canonical not in cls._init_order:
                cls._init_order.append(canonical)

            if instance is not None and type(instance) != service_type:
                cls._typed_instances[type(instance)] = instance

            logger.debug(f"Service instance for type '{canonical}' registered via typed DI")

    @classmethod
    def register_class(cls, name: str, service_class: Type) -> None:
        """Register a class for lazy-loading instantiation."""
        canonical = name.strip()
        lower_name = canonical.lower()

        with cls._lock:
            cls._classes[canonical] = service_class
            cls._classes[lower_name] = service_class
            cls._canonical_names[lower_name] = canonical
            cls._states[canonical] = ServiceState.UNINITIALIZED
            cls._states[lower_name] = ServiceState.UNINITIALIZED
            logger.debug(f"Service class '{canonical}' registered for lazy loading")

    # ── Resolution & Getter Methods ────────────────────────────────────────

    @classmethod
    def get_instance(cls, name: str) -> Any:
        """
        Synchronously get a service instance.
        If not yet instantiated but registered via factory or class, it is lazily initialized on demand.
        Detects circular dependencies and tracks lifecycle states.
        Returns None if the service is unknown.
        """
        canonical = name.strip()
        lower_name = canonical.lower()

        # 1. Fast check without acquiring lock if already ready
        if canonical in cls._instances:
            return cls._instances[canonical]
        if lower_name in cls._instances:
            return cls._instances[lower_name]

        with cls._lock:
            # Double-check inside lock
            if canonical in cls._instances:
                return cls._instances[canonical]
            if lower_name in cls._instances:
                return cls._instances[lower_name]

            # 2. Check registered factory
            factory = cls._factories.get(canonical) or cls._factories.get(lower_name)
            if factory is not None:
                stack = _thread_local.stack
                if lower_name in stack:
                    chain = " -> ".join(stack + [lower_name])
                    cls._states[canonical] = ServiceState.FAILED
                    cls._states[lower_name] = ServiceState.FAILED
                    raise CircularDependencyError(f"Circular dependency detected in ServiceManager: {chain}")

                stack.append(lower_name)
                cls._states[canonical] = ServiceState.INITIALIZING
                cls._states[lower_name] = ServiceState.INITIALIZING

                try:
                    logger.info(f"⚡ Lazily initializing service '{canonical}' via factory...")
                    instance = factory()
                    cls._instances[canonical] = instance
                    cls._instances[lower_name] = instance
                    cls._states[canonical] = ServiceState.READY
                    cls._states[lower_name] = ServiceState.READY

                    if canonical not in cls._init_order:
                        cls._init_order.append(canonical)

                    if instance is not None:
                        concrete_type = type(instance)
                        cls._typed_instances[concrete_type] = instance
                        cls._instances[concrete_type.__name__] = instance
                        cls._instances[concrete_type.__name__.lower()] = instance
                        cls._canonical_names[concrete_type.__name__.lower()] = concrete_type.__name__

                    logger.info(f"✓ Service '{canonical}' lazily instantiated successfully")
                    return instance
                except Exception as e:
                    cls._states[canonical] = ServiceState.FAILED
                    cls._states[lower_name] = ServiceState.FAILED
                    logger.error(f"✗ Failed to lazily instantiate service '{canonical}' via factory: {e}")
                    raise e
                finally:
                    if stack and stack[-1] == lower_name:
                        stack.pop()

            # 3. Check registered class
            service_class = cls._classes.get(canonical) or cls._classes.get(lower_name)
            if service_class is not None:
                stack = _thread_local.stack
                if lower_name in stack:
                    chain = " -> ".join(stack + [lower_name])
                    cls._states[canonical] = ServiceState.FAILED
                    cls._states[lower_name] = ServiceState.FAILED
                    raise CircularDependencyError(f"Circular dependency detected in ServiceManager: {chain}")

                stack.append(lower_name)
                cls._states[canonical] = ServiceState.INITIALIZING
                cls._states[lower_name] = ServiceState.INITIALIZING

                try:
                    logger.info(f"⚡ Lazily initializing service class '{canonical}'...")
                    instance = service_class()
                    cls._instances[canonical] = instance
                    cls._instances[lower_name] = instance
                    cls._states[canonical] = ServiceState.READY
                    cls._states[lower_name] = ServiceState.READY

                    if canonical not in cls._init_order:
                        cls._init_order.append(canonical)

                    if instance is not None:
                        cls._typed_instances[type(instance)] = instance
                    logger.info(f"✓ Service '{canonical}' instantiated from class successfully")
                    return instance
                except Exception as e:
                    cls._states[canonical] = ServiceState.FAILED
                    cls._states[lower_name] = ServiceState.FAILED
                    logger.error(f"✗ Failed to lazily instantiate service class '{canonical}': {e}")
                    raise e
                finally:
                    if stack and stack[-1] == lower_name:
                        stack.pop()

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
                cls._states[service_type.__name__] = ServiceState.READY
                return cast(T, instance)

            for key in name_keys:
                if key in cls._factories:
                    instance = cls._factories[key]()
                    cls._typed_instances[service_type] = instance
                    cls._instances[key] = instance
                    cls._states[key] = ServiceState.READY
                    return cast(T, instance)

            for key in name_keys:
                if key in cls._classes:
                    instance = cls._classes[key]()
                    cls._typed_instances[service_type] = instance
                    cls._instances[key] = instance
                    cls._states[key] = ServiceState.READY
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
    def get_state(cls, name: str) -> ServiceState:
        """Get the current lifecycle state of a service."""
        canonical = cls._canonical_names.get(name.lower(), name)
        return cls._states.get(canonical, ServiceState.UNINITIALIZED)

    @classmethod
    def is_initialized(cls, name: str) -> bool:
        """Check if a service is actively instantiated in memory."""
        return name in cls._instances or name.lower() in cls._instances

    @classmethod
    def list_active_services(cls) -> List[str]:
        """List canonical names of all currently instantiated services."""
        seen = set()
        active = []
        for name in cls._instances.keys():
            canonical = cls._canonical_names.get(name.lower(), name)
            if canonical not in seen and not name.islower():
                seen.add(canonical)
                active.append(canonical)
        return active or list(cls._instances.keys())

    @classmethod
    def list_registered_factories(cls) -> List[str]:
        """List canonical names of all registered lazy factories."""
        seen = set()
        factories = []
        for name in cls._factories.keys():
            canonical = cls._canonical_names.get(name.lower(), name)
            if canonical not in seen:
                seen.add(canonical)
                factories.append(canonical)
        return factories

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        """Return container diagnostics and metrics."""
        with cls._lock:
            return {
                "active_services_count": len(cls.list_active_services()),
                "lazy_factories_count": len(cls.list_registered_factories()),
                "typed_instances_count": len(cls._typed_instances),
                "initialized_order": list(cls._init_order),
                "service_states": {k: v.value for k, v in cls._states.items() if not k.islower()},
            }

    # ── Lifecycle Shutdown ─────────────────────────────────────────────────

    @classmethod
    async def shutdown_all(cls) -> None:
        """Shutdown all active service singletons in reverse initialization order."""
        with cls._lock:
            seen_ids: Set[int] = set()
            
            # Shutdown in reverse of initialization order for clean dependency unwinding
            ordered_names = list(reversed(cls._init_order))
            for name in list(cls._instances.keys()):
                if name not in ordered_names:
                    ordered_names.append(name)

            for name in ordered_names:
                service = cls._instances.get(name)
                if service is None or id(service) in seen_ids:
                    continue
                seen_ids.add(id(service))

                if isinstance(service, BaseService) or hasattr(service, "shutdown") or hasattr(service, "close") or hasattr(service, "stop"):
                    logger.info(f"Shutting down service '{name}'...")
                    try:
                        shutdown_fn = getattr(service, "shutdown", None) or getattr(service, "close", None) or getattr(service, "stop", None)
                        if shutdown_fn and callable(shutdown_fn):
                            if inspect.iscoroutinefunction(shutdown_fn):
                                await shutdown_fn()
                            else:
                                shutdown_fn()
                    except Exception as e:
                        logger.error(f"Error shutting down service '{name}': {e}")
                
                cls._states[name] = ServiceState.STOPPED
                cls._states[name.lower()] = ServiceState.STOPPED

            cls._instances.clear()
            cls._typed_instances.clear()
            cls._initialized_flags.clear()
            cls._init_order.clear()
            logger.info("✓ All active services shut down successfully.")


