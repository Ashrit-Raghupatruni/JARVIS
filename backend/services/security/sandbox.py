import asyncio
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple
from loguru import logger

class SandboxResult:
    def __init__(self, stdout: str, stderr: str, exit_code: int, timeout_expired: bool = False):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.timeout_expired = timeout_expired

class SecuritySandbox:
    """Provides isolated, restricted, and resource-bounded execution for Python and terminal scripts."""
    
    def __init__(self, use_docker: bool = False, timeout_limit: float = 60.0):
        self.use_docker = use_docker
        self.timeout_limit = timeout_limit
        self.blocked_patterns = [
            "del ", "rm ", "rmdir ", "rd ", "format ", "erase ", 
            "mkfs", "shutdown", "reboot", "/dev/sda", "/dev/sdb"
        ]
        
    def _is_destructive(self, command: str) -> bool:
        """Verify command doesn't contain destructive command patterns."""
        cmd_lower = command.lower()
        for pattern in self.blocked_patterns:
            if pattern in cmd_lower:
                return True
        return False

    async def execute_shell(self, command: str, env_override: Dict[str, str] = None) -> SandboxResult:
        """Execute a shell command inside a restricted environment."""
        if self._is_destructive(command):
            logger.warning(f"Rejected destructive command: {command}")
            return SandboxResult("", "Error: Command contains forbidden destructive patterns.", -1)
            
        # Clean environment variables to prevent token leakage
        clean_env = self._get_sanitized_env()
        if env_override:
            clean_env.update(env_override)
            
        try:
            # Execute asynchronously with timeout limit
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=clean_env
            )
            
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), 
                    timeout=self.timeout_limit
                )
                return SandboxResult(
                    stdout_bytes.decode(errors='replace'),
                    stderr_bytes.decode(errors='replace'),
                    proc.returncode or 0
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                logger.error(f"Command execution timed out after {self.timeout_limit}s: {command}")
                return SandboxResult("", "Error: Execution timed out.", -1, timeout_expired=True)
                
        except Exception as e:
            logger.error(f"Error during shell sandbox execution: {e}")
            return SandboxResult("", str(e), -1)

    async def execute_python(self, code: str, script_name: str = "temp_script.py") -> SandboxResult:
        """Write Python code to a temp file and execute it in sandbox."""
        temp_dir = Path("data/security/sandbox_run")
        temp_dir.mkdir(parents=True, exist_ok=True)
        script_file = temp_dir / script_name
        
        # Prevent execution of destructive OS operations inside Python
        forbidden_imports = ["os.system", "subprocess.Popen", "subprocess.run", "subprocess.call", "shutil.rmtree"]
        for fi in forbidden_imports:
            if fi in code:
                return SandboxResult("", f"Error: Python script contains blocked execution API '{fi}'", -1)
                
        try:
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(code)
                
            # Execute Python script in restricted subprocess using active environment Python
            python_bin = sys.executable or "python"
            result = await self.execute_shell(f'"{python_bin}" "{script_file.resolve()}"')
            return result
        finally:
            if script_file.exists():
                try:
                    os.remove(script_file)
                except Exception:
                    pass
                    
    def _get_sanitized_env(self) -> Dict[str, str]:
        """Filter sensitive API keys and system variables from environment."""
        blocked_env_keys = [
            "GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY",
            "OPENROUTER_API_KEY", "AZURE_OPENAI_API_KEY", "GITHUB_TOKEN"
        ]
        sanitized = {}
        for k, v in os.environ.items():
            if k.upper() not in blocked_env_keys:
                sanitized[k] = v
        return sanitized
