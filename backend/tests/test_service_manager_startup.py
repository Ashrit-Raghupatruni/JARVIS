"""
Unit tests for ServiceManager lifecycle, circular dependency detection, and startup bootstrap.
"""

import pytest
import asyncio
from backend.services.manager import ServiceManager, ServiceState, CircularDependencyError
from backend.services.base import BaseService


class DummyCoreService(BaseService):
    def __init__(self):
        super().__init__()
        self.initialized = False
        self.stopped = False

    async def initialize(self):
        self.initialized = True

    async def shutdown(self):
        self.stopped = True


class ServiceA:
    def __init__(self):
        self.b = ServiceManager.get_instance("service_b")


class ServiceB:
    def __init__(self):
        self.a = ServiceManager.get_instance("service_a")


def test_service_manager_registration_and_state():
    dummy = DummyCoreService()
    ServiceManager.register_instance("test_dummy_service", dummy)
    
    assert ServiceManager.is_initialized("test_dummy_service") is True
    assert ServiceManager.get_state("test_dummy_service") == ServiceState.READY
    assert ServiceManager.get_instance("test_dummy_service") is dummy


def test_service_manager_lazy_factory():
    created = False
    def factory():
        nonlocal created
        created = True
        return {"status": "ok"}

    ServiceManager.register_factory("test_lazy_service", factory)
    assert ServiceManager.get_state("test_lazy_service") == ServiceState.UNINITIALIZED
    assert not created

    inst = ServiceManager.get_instance("test_lazy_service")
    assert created is True
    assert inst == {"status": "ok"}
    assert ServiceManager.get_state("test_lazy_service") == ServiceState.READY


def test_circular_dependency_detection():
    ServiceManager.register_factory("service_a", lambda: ServiceA())
    ServiceManager.register_factory("service_b", lambda: ServiceB())

    with pytest.raises(CircularDependencyError) as exc_info:
        ServiceManager.get_instance("service_a")
    
    assert "Circular dependency detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_service_manager_shutdown_lifecycle():
    dummy = DummyCoreService()
    ServiceManager.register_instance("test_shutdown_svc", dummy)
    assert dummy.stopped is False

    await ServiceManager.shutdown_all()
    assert dummy.stopped is True
    assert ServiceManager.get_state("test_shutdown_svc") == ServiceState.STOPPED
