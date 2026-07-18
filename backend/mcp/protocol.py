import json
from typing import Dict, Any, Optional

class MCPProtocol:
    """Helper class to build JSON-RPC 2.0 messages compliant with the Model Context Protocol."""
    
    @staticmethod
    def request(method: str, params: Optional[Dict[str, Any]] = None, msg_id: int = 1) -> str:
        """Create a JSON-RPC 2.0 Request."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": msg_id
        }
        if params is not None:
            payload["params"] = params
        return json.dumps(payload) + "\n"
        
    @staticmethod
    def response(result: Any, msg_id: int) -> str:
        """Create a JSON-RPC 2.0 Success Response."""
        payload = {
            "jsonrpc": "2.0",
            "result": result,
            "id": msg_id
        }
        return json.dumps(payload) + "\n"
        
    @staticmethod
    def error(code: int, message: str, msg_id: Optional[int] = None) -> str:
        """Create a JSON-RPC 2.0 Error Response."""
        payload = {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message
            },
            "id": msg_id
        }
        return json.dumps(payload) + "\n"
        
    @staticmethod
    def parse(message_str: str) -> Dict[str, Any]:
        """Parse a raw JSON-RPC string."""
        try:
            return json.loads(message_str.strip())
        except json.JSONDecodeError as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {e}"
                },
                "id": None
            }
