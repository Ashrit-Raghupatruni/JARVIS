import pytest
import asyncio
from typing import Any, Dict
from backend.services.tool_registry import ToolRegistry, ToolMetadata, _sanitize_args_for_logging


@pytest.fixture
def registry():
    return ToolRegistry()


def test_tool_metadata_is_executable():
    meta_executable = ToolMetadata(
        name="test_tool",
        description="A test tool",
        handler=lambda: "done"
    )
    assert meta_executable.is_executable is True

    meta_non_executable = ToolMetadata(
        name="test_tool_no_handler",
        description="No handler",
        handler=None
    )
    assert meta_non_executable.is_executable is False


def test_sanitize_args_for_logging():
    args = {
        "username": "alice",
        "password": "super_secret_password",
        "api_key": "sk-1234567890",
        "token": "bearer xyz",
        "count": 42
    }
    sanitized = _sanitize_args_for_logging(args)
    assert sanitized["username"] == "alice"
    assert sanitized["password"] == "******"
    assert sanitized["api_key"] == "******"
    assert sanitized["token"] == "******"
    assert sanitized["count"] == 42


@pytest.mark.asyncio
async def test_execute_unregistered_tool(registry: ToolRegistry):
    res = await registry.execute_tool("completely_nonexistent_tool", {})
    assert res["status"] == "error"
    assert res["tool_name"] == "completely_nonexistent_tool"
    assert "not registered" in res["error"]


@pytest.mark.asyncio
async def test_execute_tool_with_no_handler(registry: ToolRegistry):
    # Register tool without handler
    registry.register(
        name="handlerless_tool",
        description="A tool declared without an implementation handler",
        category="custom",
        risk_level="low",
        parameters={"type": "object", "properties": {}},
        handler=None
    )
    
    res = await registry.execute_tool("handlerless_tool", {})
    assert res["status"] == "error"
    assert res["tool_name"] == "handlerless_tool"
    assert "has no execution handler" in res["error"]


@pytest.mark.asyncio
async def test_execute_sync_handler(registry: ToolRegistry):
    call_count = 0
    def sync_worker(x: int, y: int):
        nonlocal call_count
        call_count += 1
        return {"sum": x + y}

    registry.register(
        name="sync_calc",
        description="Synchronous calculator tool",
        parameters={
            "type": "object",
            "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            "required": ["x", "y"]
        },
        handler=sync_worker
    )

    res = await registry.execute_tool("sync_calc", {"x": 10, "y": 25})
    assert res["status"] == "success"
    assert res["tool_name"] == "sync_calc"
    assert res["sum"] == 35
    assert call_count == 1


@pytest.mark.asyncio
async def test_execute_async_handler(registry: ToolRegistry):
    call_count = 0
    async def async_worker(msg: str):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"echo": msg.upper()}

    registry.register(
        name="async_echo",
        description="Asynchronous echo tool",
        parameters={
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "required": ["msg"]
        },
        handler=async_worker
    )

    res = await registry.execute_tool("async_echo", {"msg": "hello world"})
    assert res["status"] == "success"
    assert res["tool_name"] == "async_echo"
    assert res["echo"] == "HELLO WORLD"
    assert call_count == 1


@pytest.mark.asyncio
async def test_execute_missing_required_argument(registry: ToolRegistry):
    def dummy_handler(required_field: str):
        return {"result": required_field}

    registry.register(
        name="strict_tool",
        description="Requires required_field",
        parameters={
            "type": "object",
            "properties": {"required_field": {"type": "string"}},
            "required": ["required_field"]
        },
        handler=dummy_handler
    )

    res = await registry.execute_tool("strict_tool", {})
    assert res["status"] == "error"
    assert res["tool_name"] == "strict_tool"
    assert "Missing required parameter" in res["error"]


@pytest.mark.asyncio
async def test_execute_handler_exception_handling(registry: ToolRegistry):
    def failing_handler():
        raise ValueError("Simulated hardware bus fault")

    registry.register(
        name="faulty_tool",
        description="A tool that explodes",
        parameters={"type": "object", "properties": {}},
        handler=failing_handler
    )

    res = await registry.execute_tool("faulty_tool", {})
    assert res["status"] == "error"
    assert res["tool_name"] == "faulty_tool"
    assert "Simulated hardware bus fault" in res["error"]


@pytest.mark.asyncio
async def test_inner_error_dictionary_truthful_propagation(registry: ToolRegistry):
    async def failing_inner_service():
        return {
            "status": "error",
            "message": "Target window handle 0x0000 not found"
        }

    registry.register(
        name="inner_failing_tool",
        description="Tool returning error dict",
        parameters={"type": "object", "properties": {}},
        handler=failing_inner_service
    )

    res = await registry.execute_tool("inner_failing_tool", {})
    assert res["status"] == "error"
    assert res["tool_name"] == "inner_failing_tool"
    assert "Target window handle 0x0000 not found" in res["error"]


@pytest.mark.asyncio
async def test_list_tools_filtering(registry: ToolRegistry):
    registry.register(
        name="exec_tool_test",
        description="Has handler",
        handler=lambda: None
    )
    registry.register(
        name="schema_only_tool_test",
        description="No handler",
        handler=None
    )

    all_tools = registry.list_tools()
    exec_tools = registry.list_tools(executable_only=True)
    
    assert any(t.name == "schema_only_tool_test" for t in all_tools)
    assert not any(t.name == "schema_only_tool_test" for t in exec_tools)
    assert any(t.name == "exec_tool_test" for t in exec_tools)
