"""
JARVIS AI OS — Security Precedence, Canonical Hierarchy and Fail-Closed Enforcement Suite.
========================================================================================
Validates:
  - Inviolable security hierarchy (Policy DENY cannot be overridden by Approval)
  - Cryptographic approval binding (device identity, action, target, challenge nonce)
  - Replay attack defense and single-use nonce consumption
  - Immediate device and token revocation enforcement
  - Rejection of client-side booleans without cryptographic proof for high-risk actions
  - Fail-closed behavior on security exceptions or missing services
"""

import time
import base64
import pytest
import secrets
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from backend.services.safety_gatekeeper import SafetyGatekeeper, ActionRiskLevel, SafetyDecision, SecurityDecisionType
from backend.services.safe_action_executor import SafeActionExecutor
from backend.services.tool_registry import ToolRegistry
from backend.services.mobile_auth import MobileAuthService
from backend.services.mobile_gateway import MobileGatewayService


@pytest.fixture
def gatekeeper():
    return SafetyGatekeeper()


@pytest.fixture
def tool_registry():
    return ToolRegistry()


@pytest.fixture
def auth_service(tmp_path):
    return MobileAuthService(data_dir=str(tmp_path))


@pytest.fixture
def gateway_service():
    return MobileGatewayService()


# ── TEST A: Policy DENY + Approval ALLOW -> DENY ─────────────────────────────
@pytest.mark.asyncio
async def test_precedence_policy_deny_overrides_approval(gatekeeper, tool_registry):
    """Proves that a SecurityPolicy DENY cannot be overridden by user confirmation."""
    executor = SafeActionExecutor(tool_registry=tool_registry, safety_gatekeeper=gatekeeper)

    # Malicious injection in app launch
    blocked_app = "calc.exe & rm -rf /"
    result = await executor.execute_guarded(
        tool_name="open_application",
        parameters={"app_name": blocked_app},
        user_confirmed=True  # Client claims approval, but Policy is DENY
    )

    assert result.allowed is False
    assert result.status == "blocked_by_safety_gatekeeper"
    assert "Security Policy Block" in (result.error or "") or "Command injection" in (result.error or "")



# ── TEST B: Policy ALLOW + Missing Approval on Sensitive Action -> REQUIRE_APPROVAL
@pytest.mark.asyncio
async def test_precedence_sensitive_action_requires_approval(gatekeeper, tool_registry):
    """Proves that destructive/sensitive tools require explicit approval when not confirmed."""
    executor = SafeActionExecutor(tool_registry=tool_registry, safety_gatekeeper=gatekeeper)

    result = await executor.execute_guarded(
        tool_name="delete_file",
        parameters={"file_path": "C:\\temp\\test.txt"},
        user_confirmed=False  # Approval missing
    )

    assert result.allowed is False
    assert result.status == "user_approval_required"
    assert result.requires_user_approval is True


# ── TEST C: Authentication Invalid -> DENY ──────────────────────────────────
def test_precedence_invalid_authentication(auth_service):
    """Proves that invalid, malformed, or wrong-secret tokens are rejected."""
    # Empty token
    assert auth_service.verify_token("") is None
    assert auth_service.verify_token(None) is None

    # Garbage token
    assert auth_service.verify_token("Bearer invalid.garbage.token") is None

    # Token with wrong secret
    import jwt
    foreign_token = jwt.encode({"sub": "attacker"}, "wrong_secret_1234567890", algorithm="HS256")
    assert auth_service.verify_token(foreign_token) is None


# ── TEST D: Device Revoked -> DENY ──────────────────────────────────────────
def test_precedence_revoked_device_rejected(auth_service):
    """Proves that a revoked device cannot authenticate or authorize actions."""
    dev_id = "test-device-revocation-001"
    token = auth_service.create_jwt_token(dev_id, "Test Phone")

    # Before revocation: valid
    payload = auth_service.verify_token(token)
    assert payload is not None
    assert payload.get("sub") == dev_id

    # Revoke device
    auth_service.revoke_device(dev_id)

    # After revocation: rejected immediately
    assert auth_service.verify_token(token) is None


# ── TEST E: Approval for Action A used for Action B -> DENY ─────────────────
def test_precedence_approval_bound_to_exact_action(gateway_service, auth_service):
    """Proves that an approval challenge issued for Action A cannot authorize Action B."""
    approval_id = "appr_test_action_mismatch"
    challenge = secrets.token_hex(32)
    device_id = "trusted_phone_001"

    # Register trusted client with Ed25519 keypair
    client_priv = ed25519.Ed25519PrivateKey.generate()
    client_pub_bytes = client_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    client_pub_b64 = base64.b64encode(client_pub_bytes).decode("utf-8")
    auth_service._trusted_devices[device_id] = {
        "device_id": device_id,
        "public_key": client_pub_b64,
        "trusted": True
    }

    # Register pending approval for "file_delete"
    gateway_service.pending_approvals[approval_id] = {
        "approval_id": approval_id,
        "action_type": "file_delete",
        "dangerous_target": "C:\\safe\\data.csv",
        "challenge": challenge,
        "timestamp": time.time(),
        "expires_at": time.time() + 60.0,
        "event": MagicMock()
    }

    # Client signs for a DIFFERENT action ("system_shutdown")
    attacker_signed_msg = f"JARVIS_APPROVAL_CHALLENGE:{approval_id}:system_shutdown:C:\\safe\\data.csv:{challenge}"
    sig = base64.b64encode(client_priv.sign(attacker_signed_msg.encode("utf-8"))).decode("utf-8")

    with patch("backend.services.manager.ServiceManager.get_instance", return_value=auth_service):
        success, reason = gateway_service.submit_approval_decision_with_biometrics(
            approval_id=approval_id,
            decision="approve",
            challenge=challenge,
            device_id=device_id,
            biometric_signature=sig
        )

    assert success is False
    assert "Cryptographic biometric signature verification failed" in reason


# ── TEST F: Valid Approval + Modified Parameters / Target -> DENY ───────────
def test_precedence_approval_bound_to_exact_target(gateway_service, auth_service):
    """Proves that altering the target path or payload invalidates the signature."""
    approval_id = "appr_test_target_tamper"
    challenge = secrets.token_hex(32)
    device_id = "trusted_phone_002"

    client_priv = ed25519.Ed25519PrivateKey.generate()
    client_pub_bytes = client_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    auth_service._trusted_devices[device_id] = {
        "device_id": device_id,
        "public_key": base64.b64encode(client_pub_bytes).decode("utf-8"),
        "trusted": True
    }

    gateway_service.pending_approvals[approval_id] = {
        "approval_id": approval_id,
        "action_type": "terminal_command",
        "dangerous_target": "npm install package-a",
        "challenge": challenge,
        "timestamp": time.time(),
        "expires_at": time.time() + 60.0,
        "event": MagicMock()
    }

    # Client signs tampered target ("npm install malicious-package")
    tampered_msg = f"JARVIS_APPROVAL_CHALLENGE:{approval_id}:terminal_command:npm install malicious-package:{challenge}"
    sig = base64.b64encode(client_priv.sign(tampered_msg.encode("utf-8"))).decode("utf-8")

    with patch("backend.services.manager.ServiceManager.get_instance", return_value=auth_service):
        success, reason = gateway_service.submit_approval_decision_with_biometrics(
            approval_id=approval_id,
            decision="approve",
            challenge=challenge,
            device_id=device_id,
            biometric_signature=sig
        )

    assert success is False
    assert "verification failed" in reason.lower()


# ── TEST G: Replay Consumed Approval Challenge -> DENY ───────────────────────
def test_precedence_replay_attack_prevention(gateway_service, auth_service):
    """Proves that a single-use challenge nonce cannot be replayed."""
    approval_id = "appr_test_replay_001"
    challenge = secrets.token_hex(32)
    device_id = "trusted_phone_003"

    client_priv = ed25519.Ed25519PrivateKey.generate()
    client_pub_bytes = client_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    auth_service._trusted_devices[device_id] = {
        "device_id": device_id,
        "public_key": base64.b64encode(client_pub_bytes).decode("utf-8"),
        "trusted": True
    }

    gateway_service.pending_approvals[approval_id] = {
        "approval_id": approval_id,
        "action_type": "terminal_command",
        "dangerous_target": "clean-build",
        "challenge": challenge,
        "timestamp": time.time(),
        "expires_at": time.time() + 60.0,
        "event": MagicMock()
    }

    valid_msg = f"JARVIS_APPROVAL_CHALLENGE:{approval_id}:terminal_command:clean-build:{challenge}"
    sig = base64.b64encode(client_priv.sign(valid_msg.encode("utf-8"))).decode("utf-8")

    with patch("backend.services.manager.ServiceManager.get_instance", return_value=auth_service):
        # First attempt: succeeds
        ok1, _ = gateway_service.submit_approval_decision_with_biometrics(
            approval_id=approval_id,
            decision="approve",
            challenge=challenge,
            device_id=device_id,
            biometric_signature=sig
        )
        assert ok1 is True

        # Re-inject same challenge to simulate replay attack on new approval
        gateway_service.pending_approvals["appr_replay_attempt"] = {
            "approval_id": "appr_replay_attempt",
            "action_type": "terminal_command",
            "dangerous_target": "clean-build",
            "challenge": challenge,  # Same challenge nonce
            "timestamp": time.time(),
            "expires_at": time.time() + 60.0,
            "event": MagicMock()
        }

        # Second attempt: fails because nonce was consumed
        ok2, reason2 = gateway_service.submit_approval_decision_with_biometrics(
            approval_id="appr_replay_attempt",
            decision="approve",
            challenge=challenge,
            device_id=device_id,
            biometric_signature=sig
        )
        assert ok2 is False
        assert "replay attack detected" in reason2.lower()


# ── TEST H: Security Component Throws Exception -> FAIL CLOSED ───────────────
def test_precedence_security_exception_fails_closed(gatekeeper):
    """Proves that unhandled internal exceptions inside security evaluation fail closed."""
    with patch.object(gatekeeper, "risk_mapping", None):  # Force internal error
        decision = gatekeeper.evaluate_tool_call("any_tool", {})
        assert decision.allowed is False
        assert decision.decision == SecurityDecisionType.DENY
        assert "Fail-Closed" in decision.reason


# ── TEST I: Direct Executor Invocation Missing Parameters -> Blocked ─────────
@pytest.mark.asyncio
async def test_precedence_tool_registry_parameter_enforcement(tool_registry):
    """Proves that ToolRegistry strictly validates required parameters and returns structured errors."""
    res = await tool_registry.execute_tool("read_file", {})  # Missing file_path
    assert res.get("status") == "error"
    assert "Missing required parameter" in res.get("error", "")


# ── TEST J: Path Traversal Attack -> Blocked by Policy ────────────────────────
def test_precedence_protected_path_traversal_blocked(gatekeeper):
    """Proves that path traversal targeting protected system files requires confirmation/is gated."""
    traversal_path = "../../Windows/System32/config/SAM"
    dec = gatekeeper.evaluate_tool_call("write_file", {"file_path": traversal_path, "content": "hack"})
    assert dec.allowed is False
    assert dec.decision == SecurityDecisionType.REQUIRE_APPROVAL
    assert "protected system files" in dec.reason


# ── TEST K: Client Boolean Without Cryptographic Proof -> Rejected ───────────
def test_precedence_client_boolean_rejected_for_high_risk(gateway_service):
    """Proves that client-side boolean (biometric_authenticated=True) alone cannot authorize high-risk actions."""
    approval_id = "appr_test_boolean_trust"
    challenge = secrets.token_hex(32)

    gateway_service.pending_approvals[approval_id] = {
        "approval_id": approval_id,
        "action_type": "system_shutdown",
        "dangerous_target": "host_pc",
        "challenge": challenge,
        "timestamp": time.time(),
        "expires_at": time.time() + 60.0,
        "event": MagicMock()
    }

    # Device has no registered cryptographic key, only sends boolean True
    ok, reason = gateway_service.submit_approval_decision_with_biometrics(
        approval_id=approval_id,
        decision="approve",
        challenge=challenge,
        device_id="unregistered_phone",
        biometric_authenticated=True,  # Raw boolean
        biometric_signature=None        # No cryptographic signature
    )

    assert ok is False
    assert "Cryptographic device keypair required" in reason
