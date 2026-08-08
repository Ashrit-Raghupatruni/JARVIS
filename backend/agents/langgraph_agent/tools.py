import asyncio
import os
import shutil
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
from langchain_core.tools import tool, BaseTool

# Robust import of PROJECT_ROOT
try:
    from backend.config import PROJECT_ROOT
except ImportError:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    logger.warning(f"Could not import backend.config. Fallback PROJECT_ROOT: {PROJECT_ROOT}")


async def execute_command(command: str, bypass_safety: bool = False) -> str:
    """Execute a command inside the SecuritySandbox with strict permission levels."""
    # Prevent reading sensitive files directly
    command_lower = command.lower()
    blocked_files = [".env", "vault.bin", "vault.key", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials"]
    if any(bf in command_lower for bf in blocked_files):
        return "Error: Access to protected security files or keys is strictly forbidden."

    from backend.services.manager import ServiceManager
    sandbox = ServiceManager.get_instance("security_sandbox")
    security_orch = ServiceManager.get_instance("security_orchestrator")
    
    if security_orch:
        classification = security_orch.classify_command(command)
        if classification == "DANGEROUS" and not bypass_safety:
            logger.warning(f"Dangerous command blocked: {command}")
            return f"__CONFIRMATION_REQUIRED__: This is a DANGEROUS command: '{command}'. Do you confirm execution?"
        elif classification == "CONFIRM" and not bypass_safety:
            logger.warning(f"Confirmation required for command: {command}")
            return f"__CONFIRMATION_REQUIRED__: Please confirm command execution: '{command}'"

    if not sandbox:
        # Fallback to local subprocess shell if sandbox service is missing
        from backend.services.security.sandbox import SecuritySandbox
        sandbox = SecuritySandbox()

    res = await sandbox.execute_shell(command)
    
    # Mask secrets in stdout/stderr
    stdout = res.stdout
    stderr = res.stderr
    if security_orch:
        stdout = security_orch.mask_secrets(stdout)
        stderr = security_orch.mask_secrets(stderr)

    return f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}\nEXIT CODE: {res.exit_code}"


async def execute_python(code: str) -> str:
    """Write python code to a temporary script and execute it inside the SecuritySandbox."""
    code_lower = code.lower()
    
    # Block protected files from being accessed in python scripts
    blocked_files = [".env", "vault.bin", "vault.key", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials"]
    if any(bf in code_lower for bf in blocked_files):
        return json.dumps({
            "stdout": "",
            "stderr": "Error: Access to protected security files or keys is strictly forbidden.",
            "exit_code": -1,
            "new_files": []
        }, indent=2)

    from backend.services.manager import ServiceManager
    sandbox = ServiceManager.get_instance("security_sandbox")
    security_orch = ServiceManager.get_instance("security_orchestrator")
    
    if not sandbox:
        from backend.services.security.sandbox import SecuritySandbox
        sandbox = SecuritySandbox()

    res = await sandbox.execute_python(code)
    
    # Mask secrets in output
    stdout = res.stdout
    stderr = res.stderr
    if security_orch:
        stdout = security_orch.mask_secrets(stdout)
        stderr = security_orch.mask_secrets(stderr)

    result = {
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": res.exit_code,
        "new_files": []
    }
    return json.dumps(result, indent=2)


def execute_file_system(
    action: str,
    path: str,
    content: Optional[str] = None,
    destination: Optional[str] = None,
    query: Optional[str] = None
) -> str:
    """Standardizes file operations using python's os and shutil, protecting sensitive keys."""
    # Prevent reading or writing sensitive files
    path_lower = path.lower()
    dest_lower = (destination or "").lower()
    blocked_files = [".env", "vault.bin", "vault.key", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials"]
    if any(bf in path_lower or bf in dest_lower for bf in blocked_files):
        return "Error: Access to protected security files or keys is strictly forbidden."

    action_lower = action.lower()
    path_obj = Path(path)
    
    try:
        logger.info(f"File system operation: {action_lower} on '{path}'")
        if action_lower == "create_file":
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            with open(path_obj, "w", encoding="utf-8") as f:
                f.write(content or "")
            return f"Successfully created file at '{path}'."
            
        elif action_lower == "edit_file":
            # In a basic file_system_tool, edit overwrites the file with new content
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            with open(path_obj, "w", encoding="utf-8") as f:
                f.write(content or "")
            return f"Successfully edited file at '{path}'."
            
        elif action_lower == "read_file":
            if not path_obj.exists():
                return f"Error: File '{path}' does not exist."
            if not path_obj.is_file():
                return f"Error: Path '{path}' is not a file."
            with open(path_obj, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
                
        elif action_lower == "move":
            if not destination:
                return "Error: 'destination' argument is required for move action."
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path_obj), str(dest_path))
            return f"Successfully moved '{path}' to '{destination}'."
            
        elif action_lower == "rename":
            if not destination:
                return "Error: 'destination' argument is required for rename action."
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            os.rename(str(path_obj), str(dest_path))
            return f"Successfully renamed '{path}' to '{destination}'."
            
        elif action_lower == "delete":
            if not path_obj.exists():
                return f"Error: Path '{path}' does not exist."
            if path_obj.is_dir():
                shutil.rmtree(str(path_obj))
                return f"Successfully deleted directory at '{path}'."
            else:
                os.remove(str(path_obj))
                return f"Successfully deleted file at '{path}'."
                
        elif action_lower == "copy":
            if not destination:
                return "Error: 'destination' argument is required for copy action."
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if path_obj.is_dir():
                shutil.copytree(str(path_obj), str(dest_path), dirs_exist_ok=True)
                return f"Successfully copied directory from '{path}' to '{destination}'."
            else:
                shutil.copy2(str(path_obj), str(dest_path))
                return f"Successfully copied file from '{path}' to '{destination}'."
                
        elif action_lower == "search":
            if not path_obj.exists() or not path_obj.is_dir():
                return f"Error: Path '{path}' is not a valid directory for search."
            search_pattern = query or "*"
            matches = list(path_obj.rglob(search_pattern))
            matches_str = [str(p) for p in matches]
            return f"Found {len(matches_str)} matches:\n" + "\n".join(matches_str[:100])
            
        else:
            return f"Error: Unknown action '{action}'."
            
    except Exception as e:
        logger.error(f"Error performing action '{action}' on '{path}': {e}")
        return f"Error: Failed to perform action '{action}' on '{path}'. Details: {str(e)}"


def execute_memory(action: str, key: str, value: Optional[str] = None) -> str:
    """Store or retrieve variables from data/prash/agent_memory.json."""
    memory_path = PROJECT_ROOT / "data" / "prash" / "agent_memory.json"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    
    action_lower = action.lower()
    
    # Load memory dictionary
    memory = {}
    if memory_path.exists():
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                memory = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load memory from {memory_path}: {e}. Initializing empty.")
            
    try:
        if action_lower == "store":
            memory[key] = value
            with open(memory_path, "w", encoding="utf-8") as f:
                json.dump(memory, f, indent=2)
            logger.info(f"Stored '{key}' = '{value}' in agent memory.")
            return f"Successfully stored key '{key}' in memory."
            
        elif action_lower == "retrieve":
            val = memory.get(key)
            logger.info(f"Retrieved '{key}' from agent memory: '{val}'")
            if val is None:
                return f"Key '{key}' not found in memory."
            return str(val)
            
        else:
            return f"Error: Unknown memory action '{action}'."
    except Exception as e:
        logger.error(f"Error in memory operation '{action}': {e}")
        return f"Error: Failed to perform memory action '{action}'. Details: {str(e)}"


async def fallback_ddg_search(query: str) -> str:
    """Lightweight HTTP fallback search using DuckDuckGo HTML frontend."""
    import urllib.request
    import urllib.parse
    import re
    
    logger.info(f"Performing DuckDuckGo HTML fallback search for: {query}")
    try:
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )
        
        def fetch_ddg():
            with urllib.request.urlopen(req, timeout=8) as response:
                return response.read().decode("utf-8")
                
        html = await asyncio.to_thread(fetch_ddg)
        
        results = []
        blocks = re.findall(r'<div class="result__body">.*?</div>\s*</div>', html, re.DOTALL)
        for block in blocks[:5]:
            title_match = re.search(r'<a class="result__url"[^>]*>(.*?)</a>', block, re.DOTALL)
            snippet_match = re.search(r'<a class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL)
            href_match = re.search(r'href="([^"]+)"', block)
            if title_match and href_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
                href = href_match.group(1)
                if "uddg=" in href:
                    href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                results.append({
                    "title": title,
                    "url": href,
                    "snippet": snippet
                })
        
        if results:
            summary_lines = [f"Search results for '{query}' (via DuckDuckGo fallback):"]
            for i, r in enumerate(results, 1):
                summary_lines.append(f"{i}. {r['title']}")
                if r.get("snippet"):
                    summary_lines.append(f"   {r['snippet'][:150]}")
                summary_lines.append(f"   URL: {r['url']}")
            summary = "\n".join(summary_lines)
            return summary
        else:
            return f"DuckDuckGo fallback search returned no results for query: '{query}'."
    except Exception as e:
        logger.error(f"DuckDuckGo fallback search failed: {e}")
        return f"Error: DuckDuckGo search failed. Details: {str(e)}"


async def execute_web_search(query: str, browser_service: Optional[Any] = None) -> str:
    """Wraps browser service web search with fallback to DuckDuckGo."""
    if browser_service is not None:
        try:
            # Check if started, if not, call start()
            if not getattr(browser_service, "_started", False):
                logger.info("BrowserService is not started. Initializing...")
                await browser_service.start()
            logger.info(f"Searching web using BrowserService: {query}")
            return await browser_service.search_web(query)
        except Exception as e:
            logger.warning(f"BrowserService search failed: {e}. Falling back to DuckDuckGo HTML...")
            return await fallback_ddg_search(query)
    else:
        logger.info(f"BrowserService not injected. Falling back to DuckDuckGo HTML for search: {query}")
        return await fallback_ddg_search(query)


def get_tools(browser_service: Optional[Any] = None) -> List[BaseTool]:
    """Helper factory function to generate, initialize and return the set of LangChain tools.
    
    Allows injecting browser_service to support browser web search operations.
    """
    
    @tool("cmd_tool")
    async def cmd_tool(command: str, bypass_safety: bool = False) -> str:
        """Execute a shell command asynchronously. Returns stdout, stderr, and exit code.
        If the command contains destructive patterns, it returns a confirmation request instead.
        """
        return await execute_command(command, bypass_safety)
        
    @tool("python_tool")
    async def python_tool(code: str) -> str:
        """Execute python code asynchronously by writing it to data/prash/temp_script.py and running it.
        Returns stdout, stderr, exit code, and a list of new files created.
        """
        return await execute_python(code)
        
    @tool("file_system_tool")
    def file_system_tool(
        action: str,
        path: str,
        content: Optional[str] = None,
        destination: Optional[str] = None,
        query: Optional[str] = None
    ) -> str:
        """Standardized file system operations tool.
        
        Args:
            action: One of 'create_file', 'edit_file', 'read_file', 'move', 'rename', 'delete', 'copy', 'search'.
            path: Absolute path to the file or directory.
            content: Text content to write (for create_file or edit_file).
            destination: Target destination path (for move, rename, copy).
            query: Glob search pattern (for search, defaults to '*').
        """
        return execute_file_system(
            action=action,
            path=path,
            content=content,
            destination=destination,
            query=query
        )
        
    @tool("user_input_tool")
    def user_input_tool(question: str) -> str:
        """Ask the user for clarification, confirmation, or any additional input needed."""
        logger.info(f"Prompting user via user_input_tool: {question}")
        return f"__USER_INPUT_REQUIRED__: {question}"
        
    @tool("memory_tool")
    def memory_tool(action: str, key: str, value: Optional[str] = None) -> str:
        """Store or retrieve key-value parameters from agent memory in data/prash/agent_memory.json.
        
        Args:
            action: One of 'store' or 'retrieve'.
            key: Memory key to save or retrieve.
            value: Value to store (ignored for retrieve).
        """
        return execute_memory(action=action, key=key, value=value)
        
    @tool("web_search_tool")
    async def web_search_tool(query: str) -> str:
        """Search the web for information using Google or DuckDuckGo."""
        return await execute_web_search(query=query, browser_service=browser_service)
        
    return [cmd_tool, python_tool, file_system_tool, user_input_tool, memory_tool, web_search_tool]
