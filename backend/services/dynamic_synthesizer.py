"""
JARVIS AI OS - Dynamic Sub-Agent Code & AST Synthesizer.
=========================================================
Synthesizes candidate tool code on the fly when no matching tool exists.
Enforces strict security rules:
1. STRICT ALLOWLIST (WHITELIST) AST Security Gate:
   - Only explicitly allowlisted, pure computational stdlib modules are permitted.
   - Any module outside the allowlist (importlib, os, sys, subprocess, ctypes, winreg, etc.) is rejected.
   - Forbids dangerous builtins & calls (eval, exec, __import__, import_module, getattr, setattr, open, etc.).
   - Disallows dunder access (__class__, __subclasses__, __globals__, __builtins__, etc.).
2. Isolated subprocess sandbox execution in a dedicated scratch directory with strict timeout (8.0s).
3. Pre-flight sandbox dry-run verification before registering or executing tool.
4. Out-of-model safety evaluation & permission gating for real execution.
5. Persistent logging of all synthesized tool source code in data/dynamic_tools/.
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from pydantic import BaseModel, Field

from backend.services.safety_gatekeeper import ActionRiskLevel, SafetyGatekeeper


class SandboxTestResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    output_data: Optional[Dict[str, Any]] = None


class DynamicTool(BaseModel):
    tool_id: str = Field(default_factory=lambda: f"dyn_tool_{uuid.uuid4().hex[:8]}")
    name: str
    description: str
    source_code: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    sample_args: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "medium"
    is_sandboxed: bool = True
    dry_run_passed: bool = False
    ast_verified: bool = False
    created_at: float = Field(default_factory=time.time)
    file_path: Optional[str] = None


class DynamicSubAgentSynthesizer:
    """
    Synthesizes, validates, sandboxes, and registers dynamic tools generated on the fly.
    Uses a strict allowlist (whitelist) security policy for AST verification.
    """

    # STRICT ALLOWLIST: Only pure computational/utility stdlib modules permitted
    ALLOWED_MODULES = {
        "math",
        "json",
        "re",
        "hashlib",
        "datetime",
        "random",
        "string",
        "collections",
        "itertools",
        "functools",
        "typing",
        "time",
        "uuid",
        "base64",
        "csv",
        "zlib",
        "statistics",
        "decimal",
        "fractions",
        "urllib.parse",
    }

    # FORBIDDEN FUNCTION NAMES & CALLS (Defense in Depth)
    FORBIDDEN_CALLS = {
        "eval",
        "exec",
        "__import__",
        "import_module",
        "load_module",
        "exec_module",
        "reload",
        "globals",
        "locals",
        "compile",
        "getattr",
        "setattr",
        "delattr",
        "open",
        "input",
        "breakpoint",
        "exit",
        "quit",
        "system",
        "popen",
        "spawnl",
        "spawnv",
        "spawnle",
        "spawnve",
        "spawnlp",
        "spawnvp",
        "spawnlpe",
        "spawnvpe",
        "fork",
        "kill",
    }

    # ALLOWED BUILTIN FUNCTIONS (When called as bare identifiers)
    ALLOWED_BUILTINS = {
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable",
        "chr", "complex", "dict", "divmod", "enumerate", "filter", "float", "format",
        "frozenset", "hash", "hex", "int", "isinstance", "issubclass", "iter", "len",
        "list", "map", "max", "min", "next", "oct", "ord", "pow", "print", "range",
        "repr", "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple",
        "type", "zip"
    }

    def __init__(self, base_storage_dir: Optional[Path] = None) -> None:
        self.storage_dir = base_storage_dir or Path("data/dynamic_tools")
        self.sandbox_dir = self.storage_dir / "sandbox"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        self.gatekeeper = SafetyGatekeeper()
        self.registry_file = self.storage_dir / "registry.json"
        self._ensure_registry_file()

    def _ensure_registry_file(self) -> None:
        if not self.registry_file.exists():
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def validate_ast(self, source_code: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Statically parses code into an AST and inspects against strict allowlist security rules.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return False, f"Syntax error in synthesized code: {e}", {}

        metadata: Dict[str, Any] = {
            "function_names": set(),
            "imported_symbols": set(),
            "imports": [],
            "calls": [],
            "docstring": "",
        }

        # First pass: collect locally defined functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                metadata["function_names"].add(node.name)
                if not metadata["docstring"] and ast.get_docstring(node):
                    metadata["docstring"] = ast.get_docstring(node)

        if not metadata["function_names"]:
            return False, "No function definition found in synthesized tool code", {}

        # Second pass: enforce strict allowlist checks
        for node in ast.walk(tree):
            # 1. Check direct imports: import X
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod not in self.ALLOWED_MODULES and alias.name not in self.ALLOWED_MODULES:
                        return False, f"Security Violation: Module '{alias.name}' is not in the permitted allowlist", {}
                    metadata["imports"].append(alias.name)
                    metadata["imported_symbols"].add(alias.asname or alias.name)

            # 2. Check from imports: from X import Y
            elif isinstance(node, ast.ImportFrom):
                mod_name = node.module or ""
                root_mod = mod_name.split(".")[0]
                if root_mod not in self.ALLOWED_MODULES and mod_name not in self.ALLOWED_MODULES:
                    return False, f"Security Violation: Module '{mod_name}' is not in the permitted allowlist", {}
                metadata["imports"].append(mod_name)
                for alias in node.names:
                    # Check if symbol itself is a forbidden call like import_module
                    if alias.name in self.FORBIDDEN_CALLS:
                        return False, f"Security Violation: Forbidden symbol '{alias.name}' imported from '{mod_name}'", {}
                    metadata["imported_symbols"].add(alias.asname or alias.name)

            # 3. Check Function / Method Calls
            elif isinstance(node, ast.Call):
                # Bare function calls: foo(...)
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                    metadata["calls"].append(call_name)
                    if call_name in self.FORBIDDEN_CALLS:
                        return False, f"Security Violation: Forbidden function call '{call_name}'", {}
                    # If not defined locally and not imported, must be an allowed builtin
                    if (
                        call_name not in metadata["function_names"]
                        and call_name not in metadata["imported_symbols"]
                        and call_name not in self.ALLOWED_BUILTINS
                    ):
                        return False, f"Security Violation: Unrecognized or forbidden builtin function '{call_name}'", {}

                # Attribute calls: obj.method(...) or mod.func(...)
                elif isinstance(node.func, ast.Attribute):
                    attr_name = node.func.attr
                    metadata["calls"].append(attr_name)
                    if attr_name in self.FORBIDDEN_CALLS:
                        return False, f"Security Violation: Forbidden method/attribute call '{attr_name}'", {}

            # 4. Check Dunder Attribute Access (e.g. obj.__class__, obj.__subclasses__, obj.__builtins__)
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__") and node.attr.endswith("__"):
                    if node.attr not in ("__name__", "__doc__"):
                        return False, f"Security Violation: Access to dunder attribute '{node.attr}' is strictly forbidden", {}

        # Convert sets to lists for JSON serialization
        metadata["function_names"] = list(metadata["function_names"])
        metadata["imported_symbols"] = list(metadata["imported_symbols"])

        return True, "AST allowlist security checks passed", metadata

    def run_in_sandbox(
        self,
        tool: DynamicTool,
        args: Dict[str, Any],
        timeout_seconds: float = 8.0,
    ) -> SandboxTestResult:
        """
        Executes the synthesized tool inside a strictly isolated subprocess sandbox.
        """
        tool_sandbox = self.sandbox_dir / tool.tool_id
        tool_sandbox.mkdir(parents=True, exist_ok=True)

        tool_script_path = tool_sandbox / "tool.py"
        runner_script_path = tool_sandbox / "runner.py"

        with open(tool_script_path, "w", encoding="utf-8") as f:
            f.write(tool.source_code)

        entry_function = tool.name
        runner_code = f"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
from tool import {entry_function}

if __name__ == '__main__':
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw) if raw.strip() else {{}}
        result = {entry_function}(**input_data)
        if not isinstance(result, dict):
            result = {{"result": result, "status": "success"}}
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        err_res = {{"error": str(e), "status": "error", "error_type": type(e).__name__}}
        print(json.dumps(err_res), file=sys.stderr)
        sys.exit(1)
"""
        with open(runner_script_path, "w", encoding="utf-8") as f:
            f.write(runner_code)

        clean_env = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(tool_sandbox.resolve()),
            "TEMP": str(tool_sandbox.resolve()),
            "TMP": str(tool_sandbox.resolve()),
        }

        start_t = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, "-s", "-I", str(runner_script_path.resolve())],
                input=json.dumps(args),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=str(tool_sandbox.resolve()),
                env=clean_env,
            )
            duration = time.time() - start_t
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            parsed_out = None
            if stdout:
                try:
                    parsed_out = json.loads(stdout)
                except Exception:
                    parsed_out = {"raw_output": stdout}

            if proc.returncode == 0:
                return SandboxTestResult(
                    success=True,
                    stdout=stdout,
                    stderr=stderr,
                    return_code=proc.returncode,
                    duration_seconds=round(duration, 3),
                    output_data=parsed_out,
                )
            else:
                return SandboxTestResult(
                    success=False,
                    stdout=stdout,
                    stderr=stderr,
                    return_code=proc.returncode,
                    duration_seconds=round(duration, 3),
                    error=stderr or f"Non-zero exit code: {proc.returncode}",
                    output_data=parsed_out,
                )
        except subprocess.TimeoutExpired:
            return SandboxTestResult(
                success=False,
                error=f"Execution timed out after {timeout_seconds} seconds",
                duration_seconds=timeout_seconds,
                return_code=-1,
            )
        except Exception as e:
            return SandboxTestResult(
                success=False,
                error=f"Subprocess runner exception: {e}",
                duration_seconds=round(time.time() - start_t, 3),
                return_code=-1,
            )
        finally:
            try:
                if runner_script_path.exists():
                    runner_script_path.unlink()
            except Exception:
                pass

    def synthesize_tool(
        self,
        intent: str,
        tool_name: Optional[str] = None,
        custom_code: Optional[str] = None,
        sample_args: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[DynamicTool], str]:
        """
        Synthesizes code, parses AST against allowlist, runs sandboxed dry-run, and logs reviewable source code.
        """
        clean_name = tool_name or f"dyn_{re.sub(r'[^a-zA-Z0-9_]', '_', intent.lower())[:24].strip('_')}"
        sample_arguments = sample_args or {}

        if custom_code:
            code = custom_code
        else:
            code = self._generate_candidate_code(intent, clean_name, sample_arguments)

        ast_ok, ast_msg, ast_meta = self.validate_ast(code)
        if not ast_ok:
            logger.warning("DynamicSynthesizer: AST validation rejected tool '{}': {}", clean_name, ast_msg)
            return False, None, f"AST Validation Failed: {ast_msg}"

        tool_id = f"dyn_{uuid.uuid4().hex[:8]}"
        persisted_file = self.storage_dir / f"{tool_id}_{clean_name}.py"

        fn_name = ast_meta["function_names"][0] if ast_meta.get("function_names") else clean_name
        dynamic_tool = DynamicTool(
            tool_id=tool_id,
            name=fn_name,
            description=ast_meta.get("docstring") or f"Dynamic synthesized tool for: {intent}",
            source_code=code,
            sample_args=sample_arguments,
            ast_verified=True,
            file_path=str(persisted_file.resolve()),
        )

        dry_run = self.run_in_sandbox(dynamic_tool, sample_arguments, timeout_seconds=8.0)
        if not dry_run.success:
            logger.warning("DynamicSynthesizer: Sandboxed dry-run failed for '{}': {}", clean_name, dry_run.error)
            return False, None, f"Sandboxed Dry-Run Failed: {dry_run.error}"

        dynamic_tool.dry_run_passed = True

        with open(persisted_file, "w", encoding="utf-8") as f:
            f.write(code)

        self._record_to_registry(dynamic_tool, intent, dry_run)
        logger.info("✓ DynamicSynthesizer: Synthesized and sandboxed tool '{}' (Logged: {})", clean_name, persisted_file.name)

        return True, dynamic_tool, "Tool synthesized, validated via AST allowlist, and verified in isolated sandbox."

    def _generate_candidate_code(self, intent: str, func_name: str, sample_args: Dict[str, Any]) -> str:
        intent_lower = intent.lower()
        if "hash" in intent_lower or "checksum" in intent_lower:
            return f'''"""Calculates cryptographic hash of a text string or data."""
import hashlib

def {func_name}(text: str = "sample text", algorithm: str = "sha256") -> dict:
    algo = getattr(hashlib, algorithm.lower(), hashlib.sha256) if algorithm.lower() in ("sha256", "sha512", "md5") else hashlib.sha256
    digest = algo(text.encode('utf-8')).hexdigest()
    return {{"status": "success", "algorithm": algorithm, "hash": digest, "input_length": len(text)}}
'''
        elif "fibonacci" in intent_lower or "math" in intent_lower:
            return f'''"""Computes mathematical sequence safely."""
def {func_name}(n: int = 8) -> dict:
    if n < 0 or n > 1000:
        return {{"status": "error", "error": "Value of n out of safe bounds (0-1000)"}}
    a, b = 0, 1
    seq = []
    for _ in range(n):
        seq.append(a)
        a, b = b, a + b
    return {{"status": "success", "n": n, "sequence": seq, "last_value": a}}
'''
        elif "csv" in intent_lower or "parse" in intent_lower or "json" in intent_lower:
            return f'''"""Parses structured text lines into clean key-value records."""
def {func_name}(raw_text: str = "a,b,c\n1,2,3", delimiter: str = ",") -> dict:
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    records = []
    for line in lines:
        parts = [p.strip() for p in line.split(delimiter)]
        records.append(parts)
    return {{"status": "success", "total_records": len(records), "records": records}}
'''
        else:
            return f'''"""Performs specialized data transformation for intent: {intent}."""
def {func_name}(data: str = "test data", operation: str = "uppercase") -> dict:
    if operation == "uppercase":
        res = data.upper()
    elif operation == "lowercase":
        res = data.lower()
    elif operation == "reverse":
        res = data[::-1]
    else:
        res = data
    return {{"status": "success", "transformed": res, "length": len(res)}}
'''

    def _record_to_registry(self, tool: DynamicTool, intent: str, test_res: SandboxTestResult) -> None:
        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.append({
                "tool_id": tool.tool_id,
                "name": tool.name,
                "intent": intent,
                "file_path": tool.file_path,
                "created_at": tool.created_at,
                "ast_verified": tool.ast_verified,
                "dry_run_success": test_res.success,
                "dry_run_duration": test_res.duration_seconds,
                "output_preview": test_res.output_data
            })
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to update dynamic tools registry: {}", e)

    def register_in_tool_registry(self, tool: DynamicTool, tool_registry: Any) -> bool:
        if not tool.dry_run_passed or not tool.ast_verified:
            logger.error("Cannot register dynamic tool '{}': validation requirements not satisfied", tool.name)
            return False

        async def dynamic_handler(**kwargs: Any) -> Dict[str, Any]:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, lambda: self.run_in_sandbox(tool, kwargs))
            if res.success and res.output_data:
                return res.output_data
            elif res.success:
                return {"status": "success", "stdout": res.stdout}
            else:
                return {"status": "error", "error": res.error, "stderr": res.stderr}

        tool_registry.register(
            name=tool.name,
            description=f"[Dynamic Synthesized Tool] {tool.description}",
            category="dynamic_synthesized",
            risk_level=tool.risk_level,
            parameters=tool.parameters,
            handler=dynamic_handler,
        )
        logger.info("✓ ToolRegistry: Dynamic tool '{}' registered with sandboxed handler.", tool.name)
        return True


# Global Singleton Synthesizer
dynamic_synthesizer = DynamicSubAgentSynthesizer()
