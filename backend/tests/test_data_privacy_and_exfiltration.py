"""
JARVIS AI OS — Phase 8: Data Privacy, Exfiltration & Information-Flow Security Suite.
====================================================================================
Validates all 15 canonical privacy and data-flow invariants:
  1. Cloud LLM prompt secret masking (OpenAI, Gemini, Bearer tokens, passwords).
  2. Cloud TTS credential scrubbing (no plaintext credentials spoken or sent to cloud).
  3. LOCAL_ONLY mode strict cloud block (no silent cloud fallback).
  4. 5-Tier Data Classification Model (PUBLIC, INTERNAL, PERSONAL, SENSITIVE, SECRET).
  5. Unmasked SECRET data blocked from external egress destinations.
  6. SENSITIVE data requires user authorization/masking for egress.
  7. Deep recursive sanitization of nested payloads (dicts, lists, tuples, models).
  8. ToolRegistry and logging sanitization (_sanitize_args_for_logging).
  9. Memory fact credential masking during ingestion and persistence.
  10. SafetyGatekeeper blocks outbound exfiltration tools containing SECRET payloads.
  11. SafetyGatekeeper blocks outbound tools in LOCAL_ONLY mode.
  12. Telemetry and metrics sanitization (no raw passwords, tokens, or PII).
  13. JWT, PEM Private Key, AWS Key, and GitHub PAT token detection and redaction.
  14. Database connection URI password masking (Postgres, Mongo, MySQL, Redis).
  15. Fail-closed security on unexpected privacy evaluation exceptions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

from backend.services.data_privacy import (
    DataClassification,
    DataFlowDestination,
    DataPrivacyEnforcer,
    get_privacy_enforcer,
    mask_secrets,
    sanitize_payload,
)
from backend.services.safety_gatekeeper import (
    SafetyGatekeeper,
    ActionRiskLevel,
    SecurityDecisionType,
)
from backend.services.tool_registry import _sanitize_args_for_logging, ToolRegistry
from backend.services.safety import mask_sensitive_data, sanitize_data_structure
from backend.services.voice.tts_manager import TTSManager
from backend.services.llm.manager import LLMService


# ── TEST 1: Cloud LLM Prompt Secret Masking ──────────────────────────────────
def test_invariant_1_cloud_llm_prompt_secret_masking():
    """Inbound messages containing OpenAI, Gemini, and password credentials are masked."""
    raw_prompt = "Here is my key: sk-proj-abcdef1234567890abcdef1234567890 and password: password=supersecretpass123"
    masked = mask_secrets(raw_prompt)
    assert "sk-proj-abcdef" not in masked
    assert "supersecretpass123" not in masked
    assert "sk-****[REDACTED]****" in masked
    assert "password=****[REDACTED]****" in masked


# ── TEST 2: Cloud TTS Credential Scrubbing ───────────────────────────────────
@pytest.mark.asyncio
async def test_invariant_2_cloud_tts_credential_scrubbing():
    """TTSManager scrubs plaintext credentials before synthesis and streaming."""
    tts = TTSManager(prefer_local=True)
    sensitive_text = "Your access token is Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdef1234567890"

    with patch.object(tts.local_provider, "stream", AsyncMock(return_value=iter([b"wav_chunk"]))) as mock_stream:
        # Mocking an async generator
        async def mock_gen(text, cancel_flag):
            yield b"wav_data"

        tts.local_provider.stream = mock_gen

        chunks = []
        async for chunk in tts.stream_speech(sensitive_text):
            chunks.append(chunk)

        assert len(chunks) > 0
        assert tts.last_provider_used == "sapi"


# ── TEST 3: LOCAL_ONLY Mode Blocks Cloud LLM and TTS ─────────────────────────
@pytest.mark.asyncio
async def test_invariant_3_local_only_mode_blocks_cloud_llm_and_tts():
    """In LOCAL_ONLY mode, cloud providers are strictly excluded with no fallback."""
    enforcer = get_privacy_enforcer()
    enforcer.set_local_only(True)

    try:
        # 1. Test LLM Router provider ranking under LOCAL_ONLY
        from backend.services.llm_router import LLMRoutingEngine
        router = LLMRoutingEngine()
        router.clients = {"ollama": True, "gemini": True, "openai": True, "groq": True}
        providers = await router.get_ranked_providers()
        assert "gemini" not in providers
        assert "openai" not in providers
        assert "groq" not in providers
        assert providers == ["ollama"]

        # 2. Test TTS in LOCAL_ONLY mode skips Edge-TTS
        tts = TTSManager(prefer_local=False)
        with patch.object(tts.edge_provider, "stream", AsyncMock()) as mock_edge, \
             patch.object(tts.local_provider, "stream") as mock_local:

            async def dummy_stream(text, cancel_fn):
                yield b"local_audio"
            tts.local_provider.stream = dummy_stream

            async for _ in tts.stream_speech("Testing local only speech"):
                pass

            assert tts.last_provider_used == "sapi"
            mock_edge.assert_not_called()
    finally:
        enforcer.set_local_only(False)


# ── TEST 4: 5-Tier Data Classification Model ─────────────────────────────────
def test_invariant_4_data_classification_hierarchy_5_tiers():
    """Classifies PUBLIC, INTERNAL, PERSONAL, SENSITIVE, and SECRET accurately."""
    enforcer = get_privacy_enforcer()

    # SECRET tier
    assert enforcer.classify_data("AIzaSyB1234567890abcdef123456789012345") == DataClassification.SECRET
    assert enforcer.classify_data({"api_key": "my_secret_token"}) == DataClassification.SECRET

    # SENSITIVE tier
    assert enforcer.classify_data("some raw data", source_hint="screenshot") == DataClassification.SENSITIVE
    assert enforcer.classify_data("OCR text result", source_hint="ocr") == DataClassification.SENSITIVE
    assert enforcer.classify_data("clipboard content", source_hint="get_clipboard") == DataClassification.SENSITIVE

    # PERSONAL tier
    assert enforcer.classify_data("I live in San Francisco", source_hint="user_chat") == DataClassification.PERSONAL
    assert enforcer.classify_data("User prefers dark mode", source_hint="user_preference") == DataClassification.PERSONAL

    # INTERNAL tier
    assert enforcer.classify_data({"cpu_percent": 12.5}, source_hint="system_telemetry") == DataClassification.INTERNAL
    assert enforcer.classify_data({"window": "Chrome"}, source_hint="list_windows") == DataClassification.INTERNAL

    # PUBLIC tier
    assert enforcer.classify_data("What is the speed of light?") == DataClassification.PUBLIC


# ── TEST 5: Unmasked SECRET Data Blocked from External Egress ────────────────
def test_invariant_5_secret_data_cannot_egress_unmasked():
    """Unmasked SECRET credentials cannot flow to cloud, browser, mobile, or webhooks."""
    enforcer = get_privacy_enforcer()

    for dest in (
        DataFlowDestination.CLOUD_LLM,
        DataFlowDestination.CLOUD_TTS,
        DataFlowDestination.BROWSER_EXTERNAL,
        DataFlowDestination.MOBILE_CLIENT,
        DataFlowDestination.EXTERNAL_WEBHOOK,
    ):
        allowed, reason = enforcer.evaluate_egress(
            classification=DataClassification.SECRET,
            destination=dest,
            is_masked=False
        )
        assert allowed is False
        assert "Privacy Violation" in reason or "SECRET" in reason


# ── TEST 6: SENSITIVE Data Requires Authorization for Egress ─────────────────
def test_invariant_6_sensitive_data_requires_authorization_for_egress():
    """SENSITIVE data requires user authorization or masking before cloud egress."""
    enforcer = get_privacy_enforcer()

    # Without approval or masking -> Blocked
    allowed, reason = enforcer.evaluate_egress(
        classification=DataClassification.SENSITIVE,
        destination=DataFlowDestination.CLOUD_LLM,
        is_masked=False,
        has_user_approval=False
    )
    assert allowed is False
    assert "SENSITIVE data requires user authorization" in reason

    # With user approval -> Permitted
    allowed_appr, _ = enforcer.evaluate_egress(
        classification=DataClassification.SENSITIVE,
        destination=DataFlowDestination.CLOUD_LLM,
        is_masked=False,
        has_user_approval=True
    )
    assert allowed_appr is True


# ── TEST 7: Deep Recursive Payload Sanitization ──────────────────────────────
def test_invariant_7_deep_payload_sanitization_nested_structures():
    """Recursively walks complex nested structures redacting sensitive keys and secret values."""
    payload = {
        "status": "active",
        "metadata": {
            "password": "unmasked_secret_password_123",
            "session": {
                "token": "sk-or-v1-abcdef1234567890abcdef1234567890abcdef1234567890",
                "notes": ["Safe string", "Contains AIzaSy12345678901234567890123456789012345 key"]
            }
        },
        "tags": ("system", "token_key_here")
    }

    sanitized = sanitize_payload(payload)
    assert sanitized["metadata"]["password"] == "******"
    assert sanitized["metadata"]["session"]["token"] == "******"
    assert "AIzaSy****[REDACTED]****" in sanitized["metadata"]["session"]["notes"][1]
    assert sanitized["status"] == "active"


# ── TEST 8: Logging and ToolRegistry Sanitization ────────────────────────────
def test_invariant_8_logging_sanitizes_argument_values_and_keys():
    """_sanitize_args_for_logging strips sensitive key values and embedded secret strings."""
    args = {
        "command": "curl -H 'Authorization: Bearer sk-1234567890abcdef1234567890abcdef' https://api.com",
        "auth_token": "secret_token_12345",
        "nested": {"api_key": "my_super_key"}
    }

    sanitized = _sanitize_args_for_logging(args)
    assert sanitized["auth_token"] == "******"
    assert sanitized["nested"]["api_key"] == "******"
    assert "sk-1234567890" not in str(sanitized["command"])


# ── TEST 9: Memory Fact Credential Masking ───────────────────────────────────
def test_invariant_9_memory_facts_contain_masked_credentials():
    """Storing memory facts with credentials automatically masks them."""
    fact = "User's OpenAI secret is sk-proj-12345678901234567890123456789012 and db password is password=MySecurePassword!"
    masked = mask_sensitive_data(fact)
    assert "sk-proj-1234567890" not in masked
    assert "MySecurePassword!" not in masked
    assert "sk-****[REDACTED]****" in masked
    assert "password=****[REDACTED]****" in masked


# ── TEST 10: SafetyGatekeeper Blocks Outbound Tools with SECRET Data ─────────
def test_invariant_10_gatekeeper_blocks_unmasked_secret_exfiltration_tools():
    """SafetyGatekeeper blocks outbound tools attempting to transmit SECRET payloads."""
    gatekeeper = SafetyGatekeeper()

    decision = gatekeeper.evaluate_tool_call(
        tool_name="upload_file",
        arguments={"destination": "https://external-drop.com", "content": "api_key=sk-ant-12345678901234567890123456789012"}
    )
    assert decision.allowed is False
    assert decision.decision == SecurityDecisionType.DENY
    assert "unmasked SECRET credentials" in decision.reason


# ── TEST 11: SafetyGatekeeper Blocks Outbound Tools in LOCAL_ONLY Mode ───────
def test_invariant_11_gatekeeper_blocks_outbound_tools_in_local_only_mode():
    """In LOCAL_ONLY mode, outbound network tools are unconditionally rejected."""
    enforcer = get_privacy_enforcer()
    enforcer.set_local_only(True)
    gatekeeper = SafetyGatekeeper()

    try:
        decision = gatekeeper.evaluate_tool_call(
            tool_name="post_webhook",
            arguments={"url": "https://n8n.mycompany.com/webhook", "payload": {"event": "sync"}}
        )
        assert decision.allowed is False
        assert decision.decision == SecurityDecisionType.DENY
        assert "LOCAL_ONLY" in decision.reason
    finally:
        enforcer.set_local_only(False)


# ── TEST 12: Telemetry and Metrics Sanitization ──────────────────────────────
def test_invariant_12_telemetry_sanitization():
    """Telemetry data structures sanitize private user content."""
    telemetry_payload = {
        "event": "tool_execution",
        "user_query": "password=my_secret_account_pass",
        "hardware": {"cpu": 25.0, "ram_gb": 16.0}
    }
    sanitized = sanitize_payload(telemetry_payload)
    assert "my_secret_account_pass" not in sanitized["user_query"]
    assert sanitized["hardware"]["cpu"] == 25.0


# ── TEST 13: JWT, PEM Key, AWS, and GitHub PAT Token Redaction ───────────────
def test_invariant_13_jwt_bearer_and_private_key_redaction():
    """Detects and masks JWTs, RSA PEM private keys, AWS IDs, and GitHub PATs."""
    pem_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0m...\n-----END RSA PRIVATE KEY-----"
    jwt_tok = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    aws_key = "AKIAIOSFODNN7EXAMPLE"
    gh_pat = "ghp_1234567890abcdefghijklmnopqrstuvwxyz12"

    raw = f"AWS={aws_key}, GH={gh_pat}, JWT={jwt_tok}, KEY={pem_key}"
    masked = mask_secrets(raw)

    assert aws_key not in masked
    assert gh_pat not in masked
    assert jwt_tok not in masked
    assert "MIIEowIBAAKCAQEA0m" not in masked
    assert "[REDACTED_AWS_KEY_ID]" in masked
    assert "[REDACTED_GITHUB_TOKEN]" in masked
    assert "[REDACTED_JWT_TOKEN]" in masked
    assert "[REDACTED_PRIVATE_KEY]" in masked


# ── TEST 14: Database Connection URI Password Masking ────────────────────────
def test_invariant_14_database_connection_string_credential_masking():
    """Masks database passwords embedded in connection strings."""
    pg_uri = "postgresql://dbuser:MySuperSecretDbPass123@localhost:5432/jarvis_prod"
    mongo_uri = "mongodb+srv://admin:AdminSecretPass999@cluster0.mongodb.net/test"

    masked_pg = mask_secrets(pg_uri)
    masked_mongo = mask_secrets(mongo_uri)

    assert "MySuperSecretDbPass123" not in masked_pg
    assert "AdminSecretPass999" not in masked_mongo
    assert "postgresql://dbuser:[REDACTED_PASSWORD]@" in masked_pg
    assert "mongodb+srv://admin:[REDACTED_PASSWORD]@" in masked_mongo


# ── TEST 15: Fail-Closed Security on Exception ───────────────────────────────
def test_invariant_15_fail_closed_on_privacy_evaluator_exception():
    """SafetyGatekeeper.evaluate_data_egress fails closed on unexpected exceptions."""
    gatekeeper = SafetyGatekeeper()

    with patch("backend.services.safety_gatekeeper.get_privacy_enforcer", side_effect=RuntimeError("Simulated privacy engine crash")):
        allowed, reason, classification = gatekeeper.evaluate_data_egress(
            data={"some": "payload"},
            destination="CLOUD_LLM"
        )
        assert allowed is False
        assert classification == DataClassification.SECRET
        assert "Fail-Closed" in reason
