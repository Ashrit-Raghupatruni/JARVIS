import asyncio
import sys
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.mcp.protocol import MCPProtocol

class MCPServerConnection:
    """Represents a connection to a local MCP Server subprocess."""
    
    def __init__(self, name: str, command: List[str]):
        self.name = name
        self.command = command
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.msg_id = 0
        self.tools: List[Dict[str, Any]] = []
        self._pending_responses: Dict[int, asyncio.Future] = {}
        self._listener_task: Optional[asyncio.Task] = None
        
    async def start(self) -> bool:
        """Start the MCP server subprocess and start listening for stdout."""
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            self._listener_task = asyncio.create_task(self._read_loop())
            logger.info(f"✓ Started MCP server '{self.name}' subprocess")
            
            # Perform MCP Initialization Handshake
            self.msg_id += 1
            init_res = await self._send_request(
                "initialize", 
                {"clientInfo": {"name": "jarvis-mcp-client", "version": "1.0"}}
            )
            
            # Fetch tools list
            self.msg_id += 1
            tools_res = await self._send_request("tools/list", {})
            self.tools = tools_res.get("tools", [])
            logger.info(f"✓ MCP Server '{self.name}' initialized. Discovered {len(self.tools)} tools.")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to start MCP Server '{self.name}': {e}")
            return False
            
    async def stop(self) -> None:
        """Stop the subprocess and clean up."""
        if self._listener_task:
            self._listener_task.cancel()
        if self.proc:
            try:
                self.proc.terminate()
                await self.proc.wait()
            except Exception:
                pass
            logger.info(f"Stopped MCP server '{self.name}'")
            
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on this server."""
        self.msg_id += 1
        res = await self._send_request("tools/call", {"name": name, "arguments": arguments})
        return res
        
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Any:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("Server not connected")
            
        req_str = MCPProtocol.request(method, params, self.msg_id)
        future = asyncio.get_running_loop().create_future()
        self._pending_responses[self.msg_id] = future
        
        self.proc.stdin.write(req_str.encode())
        await self.proc.stdin.drain()
        
        # Wait for the response to resolve in read_loop
        try:
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError:
            self._pending_responses.pop(self.msg_id, None)
            raise TimeoutError(f"MCP request '{method}' (ID: {self.msg_id}) timed out")

    async def _read_loop(self) -> None:
        if not self.proc or not self.proc.stdout:
            return
            
        while True:
            try:
                line = await self.proc.stdout.readline()
                if not line:
                    break
                payload = MCPProtocol.parse(line.decode())
                
                # Check if this is a response to our pending request
                msg_id = payload.get("id")
                if msg_id is not None and msg_id in self._pending_responses:
                    future = self._pending_responses.pop(msg_id)
                    if "error" in payload:
                        future.set_exception(Exception(payload["error"]["message"]))
                    else:
                        future.set_result(payload.get("result"))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading from MCP Server '{self.name}': {e}")
                await asyncio.sleep(0.1)

class MCPClientManager:
    """Discovers, starts, and routes tool calls across multiple active local FastMCP servers."""
    
    def __init__(self):
        self.connections: Dict[str, MCPServerConnection] = {}
        
    async def register_and_start_server(self, name: str, command: List[str]) -> bool:
        """Register a new MCP server and initialize its connection."""
        conn = MCPServerConnection(name, command)
        success = await conn.start()
        if success:
            self.connections[name] = conn
        return success
        
    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """Collect all discovered tools from all active servers."""
        all_tools = []
        for server_name, conn in self.connections.items():
            for tool in conn.tools:
                # Append server name to keep track of tool owner
                tool_copy = dict(tool)
                tool_copy["_server_name"] = server_name
                all_tools.append(tool_copy)
        return all_tools
        
    async def route_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Locate the server owning the tool and execute the call."""
        for server_name, conn in self.connections.items():
            for tool in conn.tools:
                if tool["name"] == tool_name:
                    return await conn.call_tool(tool_name, arguments)
        raise ValueError(f"Tool '{tool_name}' not found on any active MCP server")
        
    async def shutdown(self) -> None:
        """Shutdown all active connections."""
        for conn in list(self.connections.values()):
            await conn.stop()
        self.connections.clear()
