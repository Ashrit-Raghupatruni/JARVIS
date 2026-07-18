import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, r"c:\Users\ashri\JARVIS")

def handle_request(req):
    msg_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "jarvis-mcp-file-server", "version": "1.0"}
            },
            "id": msg_id
        }
        
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "read_file",
                        "description": "Read contents of a local file.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Absolute path to file."}
                            },
                            "required": ["path"]
                        }
                    },
                    {
                        "name": "write_file",
                        "description": "Write or create a file with content.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Absolute path to target file."},
                                "content": {"type": "string", "description": "Content to write."}
                            },
                            "required": ["path", "content"]
                        }
                    },
                    {
                        "name": "list_directory",
                        "description": "List files in a local directory.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Absolute path to directory."}
                            },
                            "required": ["path"]
                        }
                    },
                    {
                        "name": "index_folder",
                        "description": "Index files and documents in a folder recursively for RAG semantic search.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Absolute path to directory to index."}
                            },
                            "required": ["path"]
                        }
                    },
                    {
                        "name": "rag_search",
                        "description": "Query the RAG semantic knowledge database for answers with citations.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search keyword or question query."},
                                "limit": {"type": "integer", "description": "Maximum results to retrieve (optional, defaults to 3)."}
                            },
                            "required": ["query"]
                        }
                    }
                ]
            },
            "id": msg_id
        }
        
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        try:
            if name == "read_file":
                path = Path(arguments.get("path"))
                if not path.exists():
                    return build_error(-32001, "File not found", msg_id)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                return build_success({"content": content}, msg_id)
                
            elif name == "write_file":
                path = Path(arguments.get("path"))
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(arguments.get("content", ""))
                return build_success({"status": "success"}, msg_id)
                
            elif name == "list_directory":
                path = Path(arguments.get("path"))
                if not path.exists() or not path.is_dir():
                    return build_error(-32002, "Directory not found", msg_id)
                items = os.listdir(path)
                return build_success({"items": items}, msg_id)
                
            elif name == "index_folder":
                from backend.services.rag_service import RAGService
                path = Path(arguments.get("path"))
                rag = RAGService()
                count = rag.index_folder(path)
                return build_success({"status": "success", "indexed_files_count": count}, msg_id)
                
            elif name == "rag_search":
                from backend.services.rag_service import RAGService
                query = arguments.get("query")
                limit = int(arguments.get("limit", 3))
                rag = RAGService()
                results = rag.search(query, limit=limit)
                return build_success({"results": results}, msg_id)
                
            else:
                return build_error(-32601, f"Tool '{name}' not found", msg_id)
        except Exception as e:
            return build_error(-32000, str(e), msg_id)
            
    return build_error(-32601, f"Method '{method}' not found", msg_id)

def build_success(result, msg_id):
    return {"jsonrpc": "2.0", "result": result, "id": msg_id}

def build_error(code, message, msg_id):
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": msg_id}

def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            req = json.loads(line.strip())
            res = handle_request(req)
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception as e:
            # Output error response on parsing failure
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}, "id": None}) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
