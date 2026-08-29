"""
Security Sandbox Service for Isolated Execution.

Provides isolated, restricted, and resource-bounded execution for Python and terminal scripts.
Uses strict AST-based allowlist validation (shared with DynamicSubAgentSynthesizer) to prevent
arbitrary code execution, dunder introspection, and dynamic/obfuscated API bypasses.
"""

import ast
import asyncio
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Set
from loguru import logger


class SandboxResult:
    def __init__(self, stdout: str, stderr: str, exit_code: int, timeout_expired: bool = False):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.timeout_expired = timeout_expired


class SecuritySandbox:
    """Provides isolated, restricted, and resource-bounded execution for Python and terminal scripts."""

    # STRICT ALLOWLIST: Permitted standard library modules (pure computational / utility)
    ALLOWED_MODULES: Set[str] = {
        "math", "json", "re", "hashlib", "datetime", "random", "string",
        "collections", "itertools", "functools", "typing", "time", "uuid",
        "base64", "csv", "zlib", "statistics", "decimal", "fractions",
        "urllib.parse", "pathlib", "dataclasses", "enum", "copy", "bisect", "heapq"
    }

    # FORBIDDEN CALLS & METHODS (Direct and dynamic lookup targets)
    FORBIDDEN_CALLS: Set[str] = {
        "eval", "exec", "__import__", "import_module", "load_module", "exec_module",
        "reload", "globals", "locals", "compile", "getattr", "setattr", "delattr",
        "open", "input", "breakpoint", "exit", "quit", "system", "popen",
        "spawnl", "spawnv", "spawnle", "spawnve", "spawnlp", "spawnvp",
        "spawnlpe", "spawnvpe", "fork", "kill", "rmtree"
    }

    # ALLOWED BUILTIN FUNCTIONS
    ALLOWED_BUILTINS: Set[str] = {
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable",
        "chr", "complex", "dict", "divmod", "enumerate", "filter", "float", "format",
        "frozenset", "hash", "hex", "int", "isinstance", "issubclass", "iter", "len",
        "list", "map", "max", "min", "next", "oct", "ord", "pow", "print", "range",
        "repr", "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple",
        "type", "zip", "dir", "vars", "id", "super"
    }

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

    def validate_python_ast(self, code: str) -> Tuple[bool, str]:
        """
        Statically parses Python code into an AST and verifies against strict allowlists.
        Rejects disallowed modules, dangerous function calls, and dunder attribute access.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error in script: {e}"

        local_functions: Set[str] = set()
        imported_symbols: Set[str] = set()

        # Pass 1: Collect local function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                local_functions.add(node.name)

        # Pass 2: Inspect all nodes against security allowlist
        for node in ast.walk(tree):
            # 1. Import statements: import X
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod not in self.ALLOWED_MODULES and alias.name not in self.ALLOWED_MODULES:
                        return False, f"Security Violation: Module '{alias.name}' is not in the permitted allowlist"
                    imported_symbols.add(alias.asname or alias.name)

            # 2. ImportFrom statements: from X import Y
            elif isinstance(node, ast.ImportFrom):
                mod_name = node.module or ""
                root_mod = mod_name.split(".")[0]
                if root_mod not in self.ALLOWED_MODULES and mod_name not in self.ALLOWED_MODULES:
                    return False, f"Security Violation: Module '{mod_name}' is not in the permitted allowlist"
                for alias in node.names:
                    if alias.name in self.FORBIDDEN_CALLS:
                        return False, f"Security Violation: Forbidden symbol '{alias.name}' imported from '{mod_name}'"
                    imported_symbols.add(alias.asname or alias.name)

            # 3. Function & Method Calls
            elif isinstance(node, ast.Call):
                # Bare function calls: foo(...)
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                    if call_name in self.FORBIDDEN_CALLS:
                        return False, f"Security Violation: Forbidden function call '{call_name}'"
                    if (
                        call_name not in local_functions
                        and call_name not in imported_symbols
                        and call_name not in self.ALLOWED_BUILTINS
                    ):
                        return False, f"Security Violation: Unrecognized or forbidden builtin function '{call_name}'"

                # Attribute calls: obj.method(...) or mod.func(...)
                elif isinstance(node.func, ast.Attribute):
                    attr_name = node.func.attr
                    if attr_name in self.FORBIDDEN_CALLS:
                        return False, f"Security Violation: Forbidden method/attribute call '{attr_name}'"

            # 4. Dunder Attribute Access (e.g. obj.__class__, obj.__subclasses__, obj.__globals__)
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__") and node.attr.endswith("__"):
                    if node.attr not in ("__name__", "__doc__"):
                        return False, f"Security Violation: Access to dunder attribute '{node.attr}' is strictly forbidden"

        return True, "AST security verification passed"

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
        """Verify Python code via AST allowlist, write to temp file, and execute in sandbox."""
        # 1. Strict AST security inspection
        is_safe, error_msg = self.validate_python_ast(code)
        if not is_safe:
            logger.warning(f"Python sandbox blocked unsafe code: {error_msg}")
            return SandboxResult("", f"Error: {error_msg}", -1)

        temp_dir = Path("data/security/sandbox_run")
        temp_dir.mkdir(parents=True, exist_ok=True)
        script_file = temp_dir / script_name

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
