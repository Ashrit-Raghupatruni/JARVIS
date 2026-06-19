"""
JARVIS AI Desktop Assistant - Safety Service.

Classifies user-requested actions into safety categories and
sanitises terminal commands before execution. Prevents JARVIS
from carrying out destructive, malicious, or illegal operations.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import List, Tuple

from backend.utils.logger import logger
import asyncio
from backend.models.schemas import WSMessage


def mask_sensitive_data(text: str) -> str:
    """Masks API keys, passwords, and other credentials inside logged strings."""
    if not text:
        return text
    # Mask keys
    text = re.sub(r'sk-[a-zA-Z0-9]{32,}', 'sk-****[REDACTED]****', text)
    text = re.sub(r'AIzaSy[a-zA-Z0-9_-]{33}', 'AIzaSy****[REDACTED]****', text)
    text = re.sub(r'sk-or-v1-[a-zA-Z0-9]{48,}', 'sk-or-v1-****[REDACTED]****', text)
    # Mask common password patterns
    text = re.sub(r'(password|passwd|pwd|pass)\s*[:=]\s*["\']?[^\s"\'&,;]+["\']?', r'\1=****[REDACTED]****', text, flags=re.IGNORECASE)
    return text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Enums
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ActionCategory(str, Enum):
    """Safety classification for an action JARVIS is asked to perform."""

    SAFE = "safe"
    NEEDS_CONFIRMATION = "needs_confirmation"
    BLOCKED = "blocked"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Keyword Lists
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Actions that require explicit user confirmation before execution.
DANGEROUS_KEYWORDS: List[str] = [
    "delete",
    "remove",
    "erase",
    "format disk",
    "format drive",
    "shutdown",
    "restart",
    "reboot",
    "power off",
    "send message",
    "send email",
    "send mail",
    "purchase",
    "buy",
    "payment",
    "pay for",
    "registry",
    "regedit",
    "modify registry",
    "uninstall",
    "rm -rf",
    "rmdir",
    "del /f",
    "del /s",
    "system restore",
    "disk cleanup",
    "wipe",
    "overwrite",
    "drop table",
    "truncate",
]

# Actions that are unconditionally blocked.
BLOCKED_KEYWORDS: List[str] = [
    "malware",
    "virus",
    "ransomware",
    "keylogger",
    "trojan",
    "credential theft",
    "steal password",
    "steal credentials",
    "phishing",
    "exploit",
    "hack into",
    "brute force",
    "ddos",
    "denial of service",
    "illegal",
    "harmful content",
    "self-harm",
    "violence against",
    "bomb",
    "weapon",
    "drug synthesis",
    "child exploitation",
    "bypass security",
    "disable antivirus",
    "disable firewall",
    "privilege escalation",
    "inject payload",
    "reverse shell",
    "crypto miner",
    "cryptojack",
]

# Dangerous terminal command patterns (regex).
DANGEROUS_COMMAND_PATTERNS: List[str] = [
    r"rm\s+(-rf?|--recursive)\s+[/\\]",         # rm -rf /
    r"del\s+/[sfq]\s+",                          # del /s /f /q
    r"format\s+[a-zA-Z]:",                        # format C:
    r"diskpart",                                   # diskpart
    r"mkfs\.",                                     # mkfs.*
    r"dd\s+if=.*of=.*/dev/",                      # dd to device
    r"shutdown\s+(/s|/r|-h|-r|now)",              # shutdown commands
    r"reg\s+(delete|add)",                         # registry modification
    r"net\s+user\s+.*\s+/add",                    # add user
    r"netsh\s+advfirewall\s+set.*off",            # disable firewall
    r"powershell.*-enc",                          # encoded powershell
    r"wget.*\|\s*(bash|sh|powershell)",           # download-and-execute
    r"curl.*\|\s*(bash|sh|powershell)",           # download-and-execute
    r"taskkill\s+/f\s+/im\s+(csrss|lsass|svchost|winlogon)", # kill system processes
    r"bcdedit",                                    # boot config
    r"sfc\s+/scannow",                            # system file checker
    r"chkdsk.*(/f|/r)",                           # disk repair
]

# Absolutely blocked terminal commands.
BLOCKED_COMMAND_PATTERNS: List[str] = [
    r"rm\s+(-rf?|--recursive)\s+/\s*$",          # rm -rf /  (root wipe)
    r":(){ :\|:& };:",                            # fork bomb
    r">\s*/dev/sda",                              # write to raw device
    r"mkfs\.\w+\s+/dev/sd[a-z]$",                # format entire disk
    r"dd\s+if=/dev/(zero|random)\s+of=/dev/sd",  # dd wipe disk
    r"format\s+c:\s*/y",                          # format C: confirmed
    r"cipher\s+/w:c:\\",                          # secure wipe C:
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Pure Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def classify_action(action_description: str) -> ActionCategory:
    """
    Classify a natural-language action description into a safety category.

    Args:
        action_description: Free-text description of the action JARVIS
                            is about to perform.

    Returns:
        ActionCategory indicating whether the action is SAFE,
        NEEDS_CONFIRMATION, or BLOCKED.
    """
    lower = action_description.lower().strip()

    # Check blocked keywords first (highest priority)
    for keyword in BLOCKED_KEYWORDS:
        if keyword in lower:
            logger.warning("Action BLOCKED — matched keyword '{}': {}", keyword, action_description)
            return ActionCategory.BLOCKED

    # Check dangerous keywords
    for keyword in DANGEROUS_KEYWORDS:
        if keyword in lower:
            logger.info("Action NEEDS_CONFIRMATION — matched keyword '{}': {}", keyword, action_description)
            return ActionCategory.NEEDS_CONFIRMATION

    return ActionCategory.SAFE


def sanitize_command(cmd: str) -> Tuple[bool, str]:
    """
    Check a terminal/shell command for safety.

    Args:
        cmd: The shell command string to evaluate.

    Returns:
        A tuple of ``(is_safe, reason)``. If the command is safe,
        ``is_safe`` is ``True`` and ``reason`` is ``"Command is safe"``.
        Otherwise ``is_safe`` is ``False`` and ``reason`` explains why.
    """
    lower = cmd.lower().strip()

    # Check absolutely blocked patterns
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, lower):
            reason = f"Command blocked — matches critical danger pattern: {pattern}"
            logger.error(reason)
            return False, reason

    # Check dangerous patterns (needs confirmation, but we flag as unsafe here)
    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if re.search(pattern, lower):
            reason = f"Command is potentially dangerous — matches pattern: {pattern}"
            logger.warning(reason)
            return False, reason

    return True, "Command is safe"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Service Class
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SafetyService:
    """
    Centralised safety gate for all JARVIS actions.

    Wraps the pure classification functions and adds confirmation-flow
    support tied to application settings.
    """

    def __init__(self, confirm_dangerous: bool = True, allow_terminal: bool = True) -> None:
        """
        Initialise the safety service.

        Args:
            confirm_dangerous: If True, actions classified as
                               NEEDS_CONFIRMATION will require explicit
                               user approval before proceeding.
            allow_terminal: If False, **all** terminal commands are blocked
                            regardless of content.
        """
        self.confirm_dangerous = confirm_dangerous
        self.allow_terminal = allow_terminal
        self._pending_confirmations: dict[str, str] = {}
        self._pending_requests: dict[str, asyncio.Event] = {}
        self._request_responses: dict[str, bool] = {}
        self._dangerous_tools = {
            "safe_delete", "delete_file", "kill_process", 
            "set_wifi_power", "set_system_power_action", 
            "run_terminal_command"
        }
        logger.info(
            "SafetyService initialised — confirm_dangerous={}, allow_terminal={}",
            confirm_dangerous,
            allow_terminal,
        )

    # ── Action Classification ────────────────────────────────────────────

    def check_action(self, action_description: str) -> Tuple[ActionCategory, str]:
        """
        Classify an action and return a human-readable explanation.

        Args:
            action_description: Free-text description of the action.

        Returns:
            Tuple of (ActionCategory, explanation string).
        """
        category = classify_action(action_description)

        if category == ActionCategory.BLOCKED:
            return category, f"This action has been blocked for safety: {action_description}"

        if category == ActionCategory.NEEDS_CONFIRMATION and self.confirm_dangerous:
            return category, (
                f"This action requires your confirmation before I proceed: {action_description}"
            )

        return ActionCategory.SAFE, "Action is safe to proceed."

    def is_action_allowed(self, action_description: str) -> bool:
        """
        Quick boolean check: is this action allowed without confirmation?

        Args:
            action_description: Free-text description of the action.

        Returns:
            True if the action is SAFE; False if it needs confirmation or is blocked.
        """
        category, _ = self.check_action(action_description)
        return category == ActionCategory.SAFE

    async def request_user_permission(self, tool_name: str, args: dict, app) -> bool:
        """Prompts the user over WebSocket to authorize a dangerous action."""
        if tool_name not in self._dangerous_tools:
            return True

        import uuid
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        event = asyncio.Event()
        self._pending_requests[request_id] = event
        
        manager = getattr(app.state, "connection_manager", None)
        if manager:
            # Broadcast permission request message
            await manager.broadcast(WSMessage(
                type="permission_request",
                data={
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "args": args
                }
            ))
            
            logger.info("Waiting for user permission on request '{}' for tool '{}'...", request_id, tool_name)
            try:
                # 30 seconds timeout
                await asyncio.wait_for(event.wait(), timeout=30.0)
                allowed = self._request_responses.get(request_id, False)
                logger.info("User permission result for '{}': {}", request_id, allowed)
                return allowed
            except asyncio.TimeoutError:
                logger.warning("Permission request '{}' timed out. Defaulting to block.", request_id)
                return False
            finally:
                self._pending_requests.pop(request_id, None)
                self._request_responses.pop(request_id, None)
        else:
            logger.warning("No WebSocket connection manager active to ask for permission. Blocking dangerous tool.")
            return False

    # ── Terminal Command Safety ──────────────────────────────────────────

    def check_terminal_command(self, command: str) -> Tuple[bool, str]:
        """
        Evaluate whether a terminal command is safe to execute.

        Args:
            command: The shell command to check.

        Returns:
            Tuple of (is_allowed, reason).
        """
        if not self.allow_terminal:
            return False, "Terminal command execution is disabled in settings."

        is_safe, reason = sanitize_command(command)
        if not is_safe and self.confirm_dangerous:
            return False, reason

        return is_safe, reason

    # ── Confirmation Flow ────────────────────────────────────────────────

    def request_confirmation(self, action_id: str, description: str) -> str:
        """
        Register an action pending user confirmation.

        Args:
            action_id: Unique identifier for the pending action.
            description: Human-readable description.

        Returns:
            Confirmation prompt message.
        """
        self._pending_confirmations[action_id] = description
        logger.info("Confirmation requested for action '{}': {}", action_id, description)
        return f"Sir, I need your permission to proceed with: {description}. Shall I continue?"

    def confirm_action(self, action_id: str) -> bool:
        """
        Confirm a previously-registered pending action.

        Args:
            action_id: Identifier of the action to confirm.

        Returns:
            True if the action was found and confirmed; False otherwise.
        """
        if action_id in self._pending_confirmations:
            desc = self._pending_confirmations.pop(action_id)
            logger.info("Action confirmed: {} — {}", action_id, desc)
            return True
        logger.warning("No pending confirmation found for action '{}'", action_id)
        return False

    def deny_action(self, action_id: str) -> bool:
        """
        Deny a previously-registered pending action.

        Args:
            action_id: Identifier of the action to deny.

        Returns:
            True if the action was found and denied; False otherwise.
        """
        if action_id in self._pending_confirmations:
            desc = self._pending_confirmations.pop(action_id)
            logger.info("Action denied: {} — {}", action_id, desc)
            return True
        logger.warning("No pending confirmation found for action '{}'", action_id)
        return False

    def get_pending_confirmations(self) -> dict[str, str]:
        """Return a copy of all pending confirmations."""
        return dict(self._pending_confirmations)
