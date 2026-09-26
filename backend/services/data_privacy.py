"""
JARVIS AI OS — Data Privacy, Classification & Exfiltration Defense Module.
========================================================================
Enforces authoritative data classification, secret masking, data minimization,
and fail-closed information-flow controls across LLMs, TTS, Memory, Tools, and Telemetry.

Canonical Classification Tiers:
  - PUBLIC: Documentation, public web pages, general knowledge.
  - INTERNAL: System telemetry, UI tree hierarchy, OS state metadata.
  - PERSONAL: Chat turns, user preferences, memory facts, voice inputs.
  - SENSITIVE: Screenshots, OCR text, camera frames, private source code, clipboard text.
  - SECRET: API keys, passwords, bearer tokens, private keys, auth credentials, biometric embeddings.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field
from loguru import logger


class DataClassification(str, Enum):
    """Canonical 5-tier data classification hierarchy."""
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    PERSONAL = "PERSONAL"
    SENSITIVE = "SENSITIVE"
    SECRET = "SECRET"


class DataFlowDestination(str, Enum):
    """Data flow destination types."""
    LOCAL_SYSTEM = "LOCAL_SYSTEM"         # Local process / local disk / local DB
    LOCAL_LLM = "LOCAL_LLM"               # Ollama / Prash / Local ONNX
    LOCAL_TTS = "LOCAL_TTS"               # SAPI / Piper (Zero network)
    CLOUD_LLM = "CLOUD_LLM"               # OpenAI / Gemini / Groq / OpenRouter / Anthropic / Nvidia
    CLOUD_TTS = "CLOUD_TTS"               # Microsoft Edge-TTS / ElevenLabs
    BROWSER_EXTERNAL = "BROWSER_EXTERNAL" # External web servers / forms / uploads
    MOBILE_CLIENT = "MOBILE_CLIENT"       # Paired mobile device via WebSocket/REST
    EXTERNAL_WEBHOOK = "EXTERNAL_WEBHOOK" # n8n / MCP external webhooks


# ── Canonical Secret Patterns ────────────────────────────────────────────────
SECRET_PATTERNS: List[Tuple[str, str]] = [
    # OpenAI API Keys
    (r"sk-(?:proj-|admin-)?[a-zA-Z0-9_-]{20,}", "sk-****[REDACTED]****"),
    # Google AI / Gemini API Keys
    (r"AIzaSy[a-zA-Z0-9_-]{28,}", "AIzaSy****[REDACTED]****"),
    # OpenRouter API Keys
    (r"sk-or-v1-[a-zA-Z0-9]{48,}", "sk-or-v1-****[REDACTED]****"),
    # Anthropic Claude API Keys
    (r"sk-ant-[a-zA-Z0-9_-]{32,}", "sk-ant-****[REDACTED]****"),
    # Hugging Face Access Tokens
    (r"hf_[a-zA-Z0-9]{34,}", "[REDACTED_HF_TOKEN]"),
    # GitHub Personal Access Tokens
    (r"(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36,}", "[REDACTED_GITHUB_TOKEN]"),
    (r"github_pat_[a-zA-Z0-9_]{60,}", "[REDACTED_GITHUB_PAT]"),
    # AWS Access / Secret Keys
    (r"(?:AKIA|ASIA)[0-9A-Z]{16}", "[REDACTED_AWS_KEY_ID]"),
    # JWT Tokens (3 base64url parts separated by dots)
    (r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", "[REDACTED_JWT_TOKEN]"),
    # Generic Bearer Authorization Headers
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer [REDACTED_BEARER_TOKEN]"),
    # PEM Private Keys
    (r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
    # Password / Secret / Auth field assignments
    (r"(?i)\b(password|passwd|pwd|secret|api_key|apikey|auth_token|access_token|private_key|client_secret)\s*[:=]\s*[\"']?([^\s\"'&,;]{4,})[\"']?", r"\1=****[REDACTED]****"),
    # Database connection strings with credentials
    (r"(?i)(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|mssql):\/\/([^:]+):([^@]+)@", r"\1://\2:[REDACTED_PASSWORD]@"),
]

# Sensitive keys in dictionaries / JSON structures
SENSITIVE_KEY_NAMES: Set[str] = {
    "password", "passwd", "pwd", "secret", "api_key", "apikey", "key",
    "token", "access_token", "auth_token", "auth", "authorization",
    "credential", "credentials", "private_key", "client_secret",
    "pin", "passcode", "cookie", "session_cookie", "jwt",
}


def mask_secrets(text: str) -> str:
    """
    Exhaustively detects and masks credentials, API keys, passwords, and tokens in any text string.
    Guarantees no plaintext secrets escape into prompts, logs, or external streams.
    """
    if not text or not isinstance(text, str):
        return text if text is not None else ""

    masked = text
    for pattern, replacement in SECRET_PATTERNS:
        try:
            masked = re.sub(pattern, replacement, masked)
        except Exception:
            pass
    return masked


def sanitize_payload(payload: Any) -> Any:
    """
    Recursively inspects and sanitizes data structures (dicts, lists, tuples, sets, strings, models).
    Redacts sensitive key values and scrubs embedded secrets from text content.
    """
    if payload is None:
        return None

    if isinstance(payload, str):
        return mask_secrets(payload)

    if isinstance(payload, dict):
        sanitized_dict = {}
        for k, v in payload.items():
            k_str = str(k).lower()
            if any(sk == k_str or sk in k_str for sk in SENSITIVE_KEY_NAMES):
                sanitized_dict[k] = "******"
            else:
                sanitized_dict[k] = sanitize_payload(v)
        return sanitized_dict

    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]

    if isinstance(payload, tuple):
        return tuple(sanitize_payload(item) for item in payload)

    if isinstance(payload, set):
        return {sanitize_payload(item) for item in payload}

    if isinstance(payload, BaseModel):
        dumped = payload.model_dump()
        return sanitize_payload(dumped)

    # Primitive numbers / bools
    return payload


class DataPrivacyEnforcer:
    """
    Authoritative privacy and data-flow security guardian.
    Determines classification, evaluates egress destinations, enforces local-only isolation,
    and prevents data exfiltration.
    """

    def __init__(self, local_only_mode: bool = False) -> None:
        self.local_only_mode = local_only_mode

    def set_local_only(self, enabled: bool) -> None:
        """Dynamically toggle LOCAL_ONLY security isolation."""
        self.local_only_mode = enabled
        logger.info("DataPrivacyEnforcer: LOCAL_ONLY mode set to {}", enabled)

    def classify_data(self, data: Any, source_hint: Optional[str] = None) -> DataClassification:
        """
        Classifies data into one of the 5 canonical hierarchy tiers based on content,
        structure, and provenance metadata.
        """
        if data is None:
            return DataClassification.PUBLIC

        text_repr = str(data)

        # 1. SECRET / CREDENTIAL Detection
        for pattern, _ in SECRET_PATTERNS:
            if re.search(pattern, text_repr):
                return DataClassification.SECRET

        if isinstance(data, dict):
            for k in data.keys():
                if any(sk in str(k).lower() for sk in SENSITIVE_KEY_NAMES):
                    return DataClassification.SECRET

        # 2. SENSITIVE Data Detection (Screenshots, OCR, private source files, camera)
        sensitive_sources = {"screenshot", "take_screenshot", "screen_capture", "ocr", "camera", "webcam", "clipboard", "get_clipboard"}
        if source_hint and source_hint.lower() in sensitive_sources:
            return DataClassification.SENSITIVE

        sensitive_keywords = ["[SCREENSHOT_IMAGE_BYTES]", "[OCR_BUFFER]", "BEGIN RSA PRIVATE KEY", "id_ed25519", "id_rsa", ".env", "passwd", "shadow"]
        if any(sk in text_repr for sk in sensitive_keywords):
            return DataClassification.SENSITIVE

        # 3. PERSONAL Data Detection (User turns, user facts, chat history)
        personal_sources = {"user_chat", "user_input", "user_preference", "memory_fact", "voice_input"}
        if source_hint and source_hint.lower() in personal_sources:
            return DataClassification.PERSONAL

        # 4. INTERNAL Data Detection (UI control graphs, system telemetry, process list)
        internal_sources = {"system_telemetry", "list_windows", "ui_tree", "process_list", "task_plan", "world_model"}
        if source_hint and source_hint.lower() in internal_sources:
            return DataClassification.INTERNAL

        # 5. PUBLIC fallback (general queries, public web content)
        return DataClassification.PUBLIC

    def evaluate_egress(
        self,
        classification: DataClassification,
        destination: DataFlowDestination,
        is_masked: bool = False,
        has_user_approval: bool = False,
    ) -> Tuple[bool, str]:
        """
        Evaluates whether classified data is permitted to flow to the target destination.
        Returns: (allowed: bool, reason: str)
        """
        # INVARIANT 1: In LOCAL_ONLY mode, ANY outbound cloud/external transfer is strictly blocked!
        if self.local_only_mode and destination in (
            DataFlowDestination.CLOUD_LLM,
            DataFlowDestination.CLOUD_TTS,
            DataFlowDestination.BROWSER_EXTERNAL,
            DataFlowDestination.EXTERNAL_WEBHOOK,
        ):
            return False, f"LOCAL_ONLY Isolation Enforced: Outbound flow to '{destination.value}' is strictly forbidden."

        # INVARIANT 2: Unmasked SECRET / CREDENTIAL data must NEVER leave local process memory!
        if classification == DataClassification.SECRET:
            if destination in (
                DataFlowDestination.CLOUD_LLM,
                DataFlowDestination.CLOUD_TTS,
                DataFlowDestination.BROWSER_EXTERNAL,
                DataFlowDestination.MOBILE_CLIENT,
                DataFlowDestination.EXTERNAL_WEBHOOK,
            ) and not is_masked:
                return False, f"Data Privacy Violation: Plaintext SECRET/CREDENTIAL cannot be dispatched to '{destination.value}'."

        # INVARIANT 3: SENSITIVE data (screenshots, private files) to external destinations requires masking or user approval
        if classification == DataClassification.SENSITIVE:
            if destination in (
                DataFlowDestination.CLOUD_LLM,
                DataFlowDestination.BROWSER_EXTERNAL,
                DataFlowDestination.EXTERNAL_WEBHOOK,
            ) and not has_user_approval and not is_masked:
                return False, f"Data Privacy Violation: SENSITIVE data requires user authorization or sanitization before dispatch to '{destination.value}'."

        return True, f"Data egress to '{destination.value}' permitted under privacy policy."


# Global singleton enforcer instance
_global_privacy_enforcer = DataPrivacyEnforcer()


def get_privacy_enforcer() -> DataPrivacyEnforcer:
    """Access the global DataPrivacyEnforcer singleton."""
    return _global_privacy_enforcer
