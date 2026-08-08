import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.utils.event_bus import EventBus

class UserRole:
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

class ToolLevel:
    READ_ONLY = 0
    FILE_MODIFY = 1
    SYSTEM_EXECUTE = 2

class SecurityOrchestrator:
    """Manages role-based authorizations, command confirmations, logs, and output masking."""
    
    def __init__(self, event_bus: EventBus, audit_dir: str = "data/security"):
        self.event_bus = event_bus
        self.audit_log_path = Path(audit_dir) / "audit.log"
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._current_role = UserRole.USER
        self._tool_levels: Dict[str, int] = {
            "file_system_tool:read_file": ToolLevel.READ_ONLY,
            "file_system_tool:search": ToolLevel.READ_ONLY,
            "web_search_tool": ToolLevel.READ_ONLY,
            "memory_tool": ToolLevel.READ_ONLY,
            "file_system_tool:create_file": ToolLevel.FILE_MODIFY,
            "file_system_tool:edit_file": ToolLevel.FILE_MODIFY,
            "file_system_tool:delete": ToolLevel.FILE_MODIFY,
            "python_tool": ToolLevel.SYSTEM_EXECUTE,
            "cmd_tool": ToolLevel.SYSTEM_EXECUTE,
        }
        
    def set_role(self, role: str) -> None:
        if role in (UserRole.ADMIN, UserRole.USER, UserRole.GUEST):
            self._current_role = role
            logger.info(f"User security role changed to: {role}")
            
    @property
    def current_role(self) -> str:
        return self._current_role
        
    def check_authorization(self, tool_name: str, action: str = "") -> bool:
        """Verify if current role is authorized to execute a tool level."""
        key = f"{tool_name}:{action}" if action else tool_name
        req_level = self._tool_levels.get(key, self._tool_levels.get(tool_name, ToolLevel.READ_ONLY))
        
        if self._current_role == UserRole.ADMIN:
            return True
        if self._current_role == UserRole.USER:
            return req_level <= ToolLevel.SYSTEM_EXECUTE
        if self._current_role == UserRole.GUEST:
            return req_level == ToolLevel.READ_ONLY
            
        return False

    def classify_command(self, command: str) -> str:
        """Classify a shell command into SAFE, CONFIRM, or DANGEROUS categories."""
        cmd_lower = command.lower().strip()
        
        dangerous_patterns = [
            "del ", "rm ", "rmdir ", "rd ", "format ", "erase ", 
            "mkfs", "shutdown", "reboot", "reg ", "net user", "net localgroup"
        ]
        if any(pat in cmd_lower for pat in dangerous_patterns):
            return "DANGEROUS"
            
        confirm_patterns = [
            "install", "pip ", "npm ", "docker", "git commit", "git push", 
            "git checkout", "setup", "build"
        ]
        if any(pat in cmd_lower for pat in confirm_patterns):
            return "CONFIRM"
            
        return "SAFE"
        
    async def request_approval(self, action_description: str) -> bool:
        """Pause caller and broadcast a safety approval check on the Event Bus."""
        logger.warning(f"Security Alert: Approval required for action: '{action_description}'")
        await self.event_bus.publish("security.approval_required", {
            "action": action_description,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
        return self._current_role == UserRole.ADMIN

    def log_audit(self, agent_name: str, tool_name: str, args: Dict[str, Any], status: str) -> None:
        """Log a structured entry to the persistent audit log file."""
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        log_line = f"[{timestamp}] Agent: {agent_name} | Tool: {tool_name} | Args: {args} | Status: {status}\n"
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            logger.error(f"Failed to write to security audit log: {e}")
            
    def mask_secrets(self, text: str, sensitive_words: List[str] = None) -> str:
        """Mask secrets and passwords in any output text."""
        import os
        masked_text = text
        
        # Always mask known environment credentials
        secrets_to_mask = sensitive_words or []
        env_keys = [
            "GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY",
            "OPENROUTER_API_KEY", "AZURE_OPENAI_API_KEY", "GITHUB_TOKEN"
        ]
        for key in env_keys:
            val = os.getenv(key)
            if val and len(val) > 4:
                secrets_to_mask.append(val)
                
        for word in set(secrets_to_mask):
            masked_text = masked_text.replace(word, "[REDACTED]")
            
        return masked_text

