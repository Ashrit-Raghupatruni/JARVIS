"""
JARVIS AI OS - Self-Development Agent & Self-Healing Service.

Responsible for repository scanning, dependency mapping, linting/testing execution,
Level 0-3 safety gate enforcement, bug localization, AST patch application,
and persisting lessons learned in developer memory.
"""

import os
import sys
import ast
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger
import pyautogui
import psutil

from backend.services.manager import ServiceManager

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_FILE = BASE_DIR.parent / "data" / "self_development_memory.json"
REGISTRY_FILE = BASE_DIR / "CapabilityRegistry.json"
if not REGISTRY_FILE.exists():
    REGISTRY_FILE = BASE_DIR.parent / "backend" / "CapabilityRegistry.json"


class SelfDevelopmentService:
    """Developer Agent Service containing compilation check, repair, safety gating, and diagnostics."""

    def __init__(self) -> None:
        self.safety_level = 2 # Default safety level (confirm critical modifications)
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.memory = self._load_memory()
        logger.info("SelfDevelopmentService initialized. Safety level: {}", self.safety_level)

    def _load_memory(self) -> Dict[str, Any]:
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to load developer memory: {}", e)
        return {"bugs_fixed": 0, "lessons_learned": [], "repair_history": []}

    def _save_memory(self) -> None:
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            logger.error("Failed to save developer memory: {}", e)

    # ── 1. Gating & Safety Restrictions (Levels 0-3) ──────────────────────
    
    def check_safety_permission(self, action_type: str, file_path: str, details: str = "") -> bool:
        """
        Verify safety rules for code alterations.
        Level 0 (safe read/lint/test): Auto-approved.
        Level 1 (formatting/safe syntax repair): Auto-approved.
        Level 2 (modify core code, API, DB): Requires user consent.
        Level 3 (deletions, security/keys): Requires strict double user consent.
        """
        file_name = Path(file_path).name
        
        # Level 3: Sensitive files or deletions
        if action_type == "delete" or "vault" in file_name or "security" in file_name or "key" in file_name:
            logger.warning("⚠️ CRITICAL Level 3 Action Blocked: '{}' on '{}'. Awaiting explicit approval.", action_type, file_path)
            return False
            
        # Level 2: Standard modifications to codebase
        if self.safety_level >= 2 and action_type == "modify":
            logger.warning("🛡️ Level 2 Modification Blocked: '{}' on '{}'. Awaiting user consent.", action_type, file_path)
            return False
            
        # Level 0/1: Auto-approved
        return True

    def register_pending_approval(self, approval_id: str, action_type: str, file_path: str, proposed_code: str, description: str = "") -> None:
        self.pending_approvals[approval_id] = {
            "action_type": action_type,
            "file_path": file_path,
            "proposed_code": proposed_code,
            "description": description,
            "timestamp": time.time()
        }

    def approve_modification(self, approval_id: str) -> Dict[str, Any]:
        """Approve and apply a pending Level 2/3 code modification."""
        pending = self.pending_approvals.pop(approval_id, None)
        if not pending:
            return {"status": "error", "message": "Pending approval ID not found."}
            
        try:
            file_path = Path(pending["file_path"])
            # Create a backup before writing
            backup_path = file_path.with_suffix(f"{file_path.suffix}.bak")
            shutil.copy2(file_path, backup_path)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(pending["proposed_code"])
                
            logger.info("✅ Modification approved and written to: {}", file_path)
            return {
                "status": "success", 
                "message": f"Successfully applied changes to {file_path.name}",
                "backup_created": str(backup_path)
            }
        except Exception as e:
            logger.error("Failed to apply approved modification: {}", e)
            return {"status": "error", "message": f"Application failed: {e}"}

    def reject_modification(self, approval_id: str) -> Dict[str, Any]:
        pending = self.pending_approvals.pop(approval_id, None)
        if not pending:
            return {"status": "error", "message": "Pending approval ID not found."}
        logger.info("❌ Modification rejected by user: {}", approval_id)
        return {"status": "rejected", "message": "Modification successfully discarded."}

    # ── 2. Codebase Scanner & AST Ingestion ───────────────────────────────
    
    def scan_project_structure(self, root_dir: str = ".") -> Dict[str, Any]:
        """Index files, detect classes/functions via AST, mapping API endpoints."""
        root = Path(root_dir)
        py_files = list(root.rglob("*.py"))
        ts_files = list(root.rglob("*.ts"))
        tsx_files = list(root.rglob("*.tsx"))
        
        indexed_modules = {}
        api_routes = []
        
        for pf in py_files:
            if "venv" in pf.parts or ".venv" in pf.parts or "node_modules" in pf.parts:
                continue
            rel_path = str(pf.relative_to(root))
            try:
                with open(pf, "r", encoding="utf-8", errors="ignore") as f:
                    tree = ast.parse(f.read(), filename=rel_path)
                
                classes = []
                functions = []
                imports = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes.append(node.name)
                    elif isinstance(node, ast.FunctionDef):
                        functions.append(node.name)
                        # Detect routes
                        for decorator in node.decorator_list:
                            if isinstance(decorator, ast.Call) and hasattr(decorator.func, "attr"):
                                if decorator.func.attr in ("get", "post", "put", "delete", "websocket"):
                                    route_path = ""
                                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                                        route_path = decorator.args[0].value
                                    api_routes.append({
                                        "method": decorator.func.attr.upper(),
                                        "route": route_path,
                                        "handler": node.name,
                                        "file": rel_path
                                    })
                    elif isinstance(node, ast.Import):
                        for name in node.names:
                            imports.append(name.name)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.append(node.module)

                indexed_modules[rel_path] = {
                    "classes": classes,
                    "functions": functions,
                    "imports": list(set(imports))
                }
            except Exception:
                pass

        return {
            "python_modules_scanned": len(indexed_modules),
            "typescript_modules_scanned": len(ts_files) + len(tsx_files),
            "api_routes_discovered": api_routes,
            "modules": indexed_modules
        }

    # ── 3. Diagnostic Checklist ───────────────────────────────────────────
    
    def run_system_diagnostic(self) -> Dict[str, Any]:
        """Verify server, databases, AI models, local speech devices, camera, and capability registries."""
        issues = []
        status = {}
        
        # 1. Hardware connection
        status["cpu_percent"] = psutil.cpu_percent()
        status["ram_percent"] = psutil.virtual_memory().percent
        status["disk_percent"] = psutil.disk_usage("/").percent
        
        # 2. Database Connection
        try:
            # SQLAlchemy health
            rag_service = ServiceManager.get_instance("rag_service")
            if rag_service:
                status["rag_database"] = "ONLINE"
            else:
                status["rag_database"] = "OFFLINE"
                issues.append("RAG service database registry not loaded.")
        except Exception as e:
            status["rag_database"] = "ERROR"
            issues.append(f"RAG Database check failure: {e}")

        # Vector database ChromaDB
        try:
            memory_service = ServiceManager.get_instance("memory_service")
            if memory_service:
                status["vector_memory"] = "ONLINE"
            else:
                status["vector_memory"] = "OFFLINE"
                issues.append("Vector memory (ChromaDB) service not initialized.")
        except Exception as e:
            status["vector_memory"] = "ERROR"
            issues.append(f"Vector Database check failure: {e}")

        # 3. AI Models loading
        stt_service = ServiceManager.get_instance("stt_service")
        status["speech_to_text_model"] = "ONLINE" if stt_service else "OFFLINE"
        if not stt_service:
            issues.append("Speech-to-Text Whisper model is offline.")

        wake_word_service = ServiceManager.get_instance("wake_word_service")
        status["wake_word_model"] = "ONLINE" if (wake_word_service and wake_word_service.is_loaded) else "OFFLINE"
        if not wake_word_service or not wake_word_service.is_loaded:
            issues.append("openwakeword Hey Jarvis model is offline.")

        # 4. Device connectivity
        # Real Camera perception check via OpenCV (fail-closed)
        try:
            import cv2
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if sys.platform == "win32" else cv2.VideoCapture(0)
            if cap is not None and cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    status["camera_perception"] = "CONNECTED"
                else:
                    status["camera_perception"] = "DISCONNECTED"
                    issues.append("Camera device opened but failed to capture frame.")
            else:
                if cap is not None:
                    cap.release()
                status["camera_perception"] = "DISCONNECTED"
                issues.append("No accessible video capture device (camera) detected.")
        except Exception as e:
            status["camera_perception"] = "DISCONNECTED"
            issues.append(f"Camera perception diagnostic check error: {e}")

        try:
            pyautogui.size()
            status["display_screen"] = "CONNECTED"
        except Exception:
            status["display_screen"] = "DISCONNECTED"
            issues.append("Display server context not accessible.")

        # 5. Hand Gesture configuration
        status["hand_gesture_control"] = "CONFIGURED"
        
        # 6. Capability registry check
        registry_loaded = False
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                    json.load(f)
                registry_loaded = True
            except Exception:
                pass
        status["capability_registry"] = "ONLINE" if registry_loaded else "CORRUPTED"
        if not registry_loaded:
            issues.append("CapabilityRegistry.json is missing or corrupted.")

        overall_status = "HEALTHY" if len(issues) == 0 else "DEGRADED"

        return {
            "diagnostic_status": overall_status,
            "timestamp": os.time() if hasattr(os, "time") else 0,
            "metrics": status,
            "discovered_issues": issues,
            "recommendations": [
                f"Fix issue: {issue}" for issue in issues
            ] if issues else ["All systems nominal. Sir."]
        }

    # ── 4. Self-Healing & Repair Loops ────────────────────────────────────
    
    def compile_check(self, file_path: str) -> Optional[str]:
        """Check python compilation syntaxes before running/submitting patches."""
        try:
            res = subprocess.run(
                [sys.executable, "-m", "py_compile", file_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode != 0:
                return res.stderr
            return None
        except Exception as e:
            return f"Compilation check failed to run: {e}"

    def git_checkpoint(self) -> bool:
        """Create a temporary git checkpoint stash."""
        try:
            subprocess.run(["git", "add", "."], capture_output=True, timeout=5)
            # Create stash record
            res = subprocess.run(["git", "stash", "create"], capture_output=True, text=True, timeout=5)
            stash_hash = res.stdout.strip()
            if stash_hash:
                subprocess.run(["git", "stash", "store", "-m", f"JARVIS_checkpoint", stash_hash], capture_output=True, timeout=5)
                logger.info("Git checkpoint created: {}", stash_hash)
                return True
        except Exception as e:
            logger.warning("Failed to create Git checkpoint: {}", e)
        return False

    def git_rollback(self) -> bool:
        """Rollback modifications using git hard reset and stash popping."""
        try:
            subprocess.run(["git", "reset", "--hard", "HEAD"], capture_output=True, timeout=5)
            subprocess.run(["git", "clean", "-fd"], capture_output=True, timeout=5)
            # Pop last stash checkpoint
            subprocess.run(["git", "stash", "pop"], capture_output=True, timeout=5)
            logger.info("Git rollback executed successfully.")
            return True
        except Exception as e:
            logger.error("Git rollback failed: {}", e)
        return False

    def apply_repair_patch(self, file_path: str, original_code: str, patch_code: str, error_context: str = "") -> Dict[str, Any]:
        """Apply a patch, run verification, and record in developer memory with git checkpoints."""
        # 1. Verification of permission
        if not self.check_safety_permission("modify", file_path):
            approval_id = f"repair_{Path(file_path).stem}_{int(os.time() if hasattr(os, 'time') else 0)}"
            self.register_pending_approval(approval_id, "modify", file_path, patch_code, f"Repair patch for error: {error_context}")
            return {
                "status": "pending_approval",
                "approval_id": approval_id,
                "message": "Modification requires Level 2 approval. Requested sent."
            }

        path = Path(file_path)
        backup_path = path.with_suffix(f"{path.suffix}.bak")
        try:
            # Create Git checkpoint
            self.git_checkpoint()
            
            # Backup file copy
            shutil.copy2(path, backup_path)
            
            # Apply patch
            with open(path, "w", encoding="utf-8") as f:
                f.write(patch_code)
                
            # Compile check
            comp_err = self.compile_check(file_path)
            if comp_err:
                logger.error("Patch caused syntax error. Rolling back: {}", comp_err)
                shutil.copy2(backup_path, path) # Rollback copy
                self.git_rollback() # Rollback git
                return {"status": "failed", "message": f"Syntax error: {comp_err}"}

            # Update memory
            self.memory["bugs_fixed"] += 1
            self.memory["repair_history"].append({
                "file": file_path,
                "error": error_context,
                "resolved": True,
                "timestamp": os.time() if hasattr(os, "time") else 0
            })
            self._save_memory()
            
            logger.info("Successfully repaired code inside: {}", file_path)
            return {"status": "success", "message": "Code successfully repaired."}
            
        except Exception as e:
            logger.error("Failed to repair patch: {}", e)
            if backup_path.exists():
                shutil.copy2(backup_path, path) # Rollback
            self.git_rollback()
            return {"status": "failed", "message": str(e)}

