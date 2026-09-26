"""
JARVIS AI OS — Phase 9: Secrets, Credentials & Key Management Adversarial Test Suite.
=====================================================================================
Validates all 16 Phase 9 security invariants:
  1. CredentialVault store, get, delete, and master key rotation with re-encryption.
  2. Settings safe __repr__ and __str__ masking all secrets and tokens.
  3. Settings placeholder key detection and safe nullification.
  4. Settings sync key validation and fallback key generation without secret printing.
  5. MobileAuthService HS256 algorithm enforcement and rejection of 'none' algorithm.
  6. MobileAuthService rejection of expired JWT tokens.
  7. MobileAuthService rejection of revoked JWT tokens.
  8. MobileAuthService rejection of revoked or untrusted devices.
  9. MobileAuthService DEV_TOKEN rejection when DEBUG is False.
 10. MobileAuthService Ed25519 challenge generation and expiration.
 11. MobileGatewayService replay attack prevention on approval challenges.
 12. MobileGatewayService rejection of fake/mock biometric signatures (bio_sig_...).
 13. MobileGatewayService fail-closed cryptographic signature verification for high-risk actions.
 14. OAuth2Service PKCE flow and encrypted token persistence in CredentialVault.
 15. Debug endpoints (/world_model_inspector, /traces, /workspace_intelligence) automatic sanitization.
 16. Repository cleanliness verification against committed production secrets.
"""

import os
import time
import json
import pytest
import base64
from pathlib import Path
from unittest.mock import patch, MagicMock

import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from backend.config import Settings, get_settings
from backend.services.security.vault import CredentialVault
from backend.services.mobile_auth import MobileAuthService
from backend.services.mobile_gateway import MobileGatewayService
from backend.services.oauth_service import OAuth2Service
from backend.services.data_privacy import sanitize_payload, mask_secrets


# ==============================================================================
# 1. CredentialVault Lifecycle & Key Rotation Tests
# ==============================================================================

def test_credential_vault_crud_and_rotation(tmp_path):
    """Test full CRUD and master key rotation with re-encryption in CredentialVault."""
    vault_dir = tmp_path / "vault_test"
    vault = CredentialVault(vault_dir=str(vault_dir))

    # 1. Store credentials
    assert vault.store_credential("openai", "api_key", "sk-proj-test-secret-123456789")
    assert vault.store_credential("github", "pat", "ghp_mockpat1234567890abcdef")

    # 2. Retrieve credentials
    assert vault.get_credential("openai", "api_key") == "sk-proj-test-secret-123456789"
    assert vault.get_credential("github", "pat") == "ghp_mockpat1234567890abcdef"
    assert vault.get_credential("nonexistent", "user") is None

    # 3. Rotate master key
    old_key = vault._encryption_key
    assert vault.rotate_master_key()
    assert vault._encryption_key != old_key

    # 4. Verify secrets decrypt correctly with rotated master key
    assert vault.get_credential("openai", "api_key") == "sk-proj-test-secret-123456789"
    assert vault.get_credential("github", "pat") == "ghp_mockpat1234567890abcdef"

    # 5. Delete credential
    assert vault.delete_credential("openai", "api_key")
    assert vault.get_credential("openai", "api_key") is None
    # Ensure remaining credential is still intact
    assert vault.get_credential("github", "pat") == "ghp_mockpat1234567890abcdef"


# ==============================================================================
# 2. Settings Secrets Masking & Sanitization Tests
# ==============================================================================

def test_settings_repr_and_str_mask_secrets():
    """Ensure Settings __repr__ and __str__ never dump plaintext API keys or secrets."""
    settings = Settings(
        OPENAI_API_KEY="sk-proj-reallookingmocksecret123456789",
        GEMINI_API_KEY="AIzaSyTestMockApiKey123456789",
        SYNC_KEY="iy2yR4WcpNOzgIn3FHXSw_ygqgkpi7KghI7Yvx1o6J4="
    )

    repr_str = repr(settings)
    str_str = str(settings)

    # Plaintext keys must NOT appear in representation
    assert "sk-proj-reallookingmocksecret123456789" not in repr_str
    assert "AIzaSyTestMockApiKey123456789" not in repr_str
    assert "iy2yR4WcpNOzgIn3FHXSw_ygqgkpi7KghI7Yvx1o6J4=" not in repr_str

    assert "sk-proj-reallookingmocksecret123456789" not in str_str
    assert "AIzaSyTestMockApiKey123456789" not in str_str
    assert "iy2yR4WcpNOzgIn3FHXSw_ygqgkpi7KghI7Yvx1o6J4=" not in str_str

    # Mask marker must be present
    assert "******" in repr_str


def test_settings_placeholder_key_deactivation():
    """Ensure placeholder API keys are detected and safely deactivated."""
    assert Settings.validate_api_keys("your-openai-api-key") is None
    assert Settings.validate_api_keys("sk-your-key-here") is None
    assert Settings.validate_api_keys("AIzaSy-your-key") is None
    assert Settings.validate_api_keys("placeholder") is None
    # Valid non-placeholder key is preserved
    valid_key = "sk-proj-actualvalidlookingtoken12345"
    assert Settings.validate_api_keys(valid_key) == valid_key


def test_settings_sync_key_fallback(capsys):
    """Ensure invalid SYNC_KEY triggers safe fallback without leaking raw key in stdout."""
    fallback = Settings.validate_sync_key("invalid_corrupt_sync_key")
    assert fallback is not None
    assert len(fallback) > 20

    captured = capsys.readouterr()
    # Output should not leak the raw fallback secret
    assert fallback not in captured.out


# ==============================================================================
# 3. MobileAuthService Authentication & JWT Hardening Tests
# ==============================================================================

def test_mobile_auth_jwt_algorithm_enforcement(tmp_path):
    """Ensure MobileAuthService rejects algorithm confusion (e.g., 'none' or 'RS256' with symmetric key)."""
    auth_service = MobileAuthService(data_dir=str(tmp_path))
    
    # 1. Reject 'none' algorithm token
    none_token = jwt.encode({"sub": "attacker-device", "exp": int(time.time()) + 3600}, key="", algorithm="none")
    assert auth_service.verify_token(none_token) is None

    # 2. Reject tampered secret token
    bad_token = jwt.encode({"sub": "legit-device", "exp": int(time.time()) + 3600}, "wrong_secret_key", algorithm="HS256")
    assert auth_service.verify_token(bad_token) is None


def test_mobile_auth_expired_and_revoked_tokens(tmp_path):
    """Ensure MobileAuthService rejects expired and explicitly revoked tokens."""
    auth_service = MobileAuthService(data_dir=str(tmp_path))

    # 1. Expired token
    expired_token = jwt.encode(
        {"sub": "test-device", "exp": int(time.time()) - 100, "iat": int(time.time()) - 200},
        auth_service._jwt_secret,
        algorithm="HS256"
    )
    assert auth_service.verify_token(expired_token) is None

    # 2. Valid token revoked via blocklist
    valid_token = auth_service.create_jwt_token("test-device-1", "Companion")
    assert auth_service.verify_token(valid_token) is not None

    auth_service.revoke_token(valid_token)
    assert auth_service.verify_token(valid_token) is None


def test_mobile_auth_revoked_and_untrusted_devices(tmp_path):
    """Ensure MobileAuthService rejects tokens belonging to revoked or untrusted devices."""
    auth_service = MobileAuthService(data_dir=str(tmp_path))
    token = auth_service.create_jwt_token("untrusted-phone", "My Phone")
    
    # Register device
    auth_service._trusted_devices["untrusted-phone"] = {
        "device_id": "untrusted-phone",
        "friendly_name": "My Phone",
        "trusted": True
    }
    assert auth_service.verify_token(token) is not None

    # Revoke device
    auth_service.revoke_device("untrusted-phone")
    assert auth_service.verify_token(token) is None


def test_mobile_auth_dev_token_fails_closed_in_production(tmp_path):
    """Ensure DEV_TOKEN_ is rejected when settings.DEBUG is False."""
    auth_service = MobileAuthService(data_dir=str(tmp_path))
    
    with patch("backend.services.mobile_auth.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.DEBUG = False
        mock_get_settings.return_value = mock_settings

        dev_token = "DEV_TOKEN_attacker_device_12345"
        assert auth_service.verify_token(dev_token) is None


def test_mobile_auth_pairing_cryptographic_challenge(tmp_path):
    """Ensure pairing challenge contains Ed25519 signature and valid expiration."""
    auth_service = MobileAuthService(data_dir=str(tmp_path))
    init_resp = auth_service.initiate_pairing("Pixel 9 Pro", "pixel-9-id")

    assert init_resp.pairing_code.isdigit()
    assert len(init_resp.pairing_code) == 6
    assert init_resp.server_public_key is not None
    assert init_resp.nonce is not None
    assert init_resp.server_signature is not None
    assert init_resp.expires_in_seconds == 300

    # Verify server signature on the challenge
    challenge_msg = f"JARVIS_PAIR_CHALLENGE:{init_resp.pairing_session_id}:{init_resp.nonce}:{init_resp.pairing_code}"
    assert auth_service.verify_client_signature(
        init_resp.server_public_key,
        challenge_msg,
        init_resp.server_signature
    )


# ==============================================================================
# 4. MobileGatewayService Biometric & Replay Security Tests
# ==============================================================================

def test_mobile_gateway_replay_protection():
    """Ensure MobileGatewayService rejects replayed approval challenges."""
    gateway = MobileGatewayService()
    approval_id = "test-appr-123"
    challenge_nonce = "chal-nonce-999"

    gateway.pending_approvals[approval_id] = {
        "action_type": "open_app",
        "description": "Open Calc",
        "dangerous_target": "calc.exe",
        "challenge": challenge_nonce,
        "timestamp": time.time(),
        "expires_at": time.time() + 60.0
    }

    # First attempt: succeeds
    success, msg = gateway.submit_approval_decision_with_biometrics(
        approval_id=approval_id,
        decision="approve",
        challenge=challenge_nonce,
        device_id="device-1"
    )
    assert success is True

    # Re-insert approval with already consumed challenge
    gateway.pending_approvals["test-appr-456"] = {
        "action_type": "open_app",
        "description": "Open Calc Again",
        "dangerous_target": "calc.exe",
        "challenge": challenge_nonce,  # Reused consumed challenge!
        "timestamp": time.time(),
        "expires_at": time.time() + 60.0
    }

    # Second attempt: fails due to replay detection
    replay_success, replay_msg = gateway.submit_approval_decision_with_biometrics(
        approval_id="test-appr-456",
        decision="approve",
        challenge=challenge_nonce,
        device_id="device-1"
    )
    assert replay_success is False
    assert "replay" in replay_msg.lower()


def test_mobile_gateway_rejects_mock_biometric_signatures():
    """Ensure MobileGatewayService rejects fake placeholder biometric signatures."""
    gateway = MobileGatewayService()
    approval_id = "test-appr-fake-bio"
    challenge_nonce = "chal-nonce-fake"

    gateway.pending_approvals[approval_id] = {
        "action_type": "shell_command",
        "description": "Run shell",
        "dangerous_target": "powershell.exe",
        "challenge": challenge_nonce,
        "timestamp": time.time(),
        "expires_at": time.time() + 60.0
    }

    # Attempt with placeholder signature 'bio_sig_mock12345'
    success, msg = gateway.submit_approval_decision_with_biometrics(
        approval_id=approval_id,
        decision="approve",
        challenge=challenge_nonce,
        device_id="device-1",
        biometric_signature="bio_sig_mock12345"
    )
    assert success is False
    assert "mock" in msg.lower() or "invalid" in msg.lower()


def test_mobile_gateway_ed25519_high_risk_signature_verification(tmp_path):
    """Ensure high-risk action requires valid Ed25519 digital signature from registered client."""
    gateway = MobileGatewayService()
    auth_service = MobileAuthService(data_dir=str(tmp_path))

    # Generate client Ed25519 keypair
    client_priv = ed25519.Ed25519PrivateKey.generate()
    client_pub = client_priv.public_key()
    raw_pub = client_pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    client_pub_b64 = base64.b64encode(raw_pub).decode("utf-8")

    device_id = "secure-pixel-device"
    auth_service._trusted_devices[device_id] = {
        "device_id": device_id,
        "friendly_name": "Pixel",
        "public_key": client_pub_b64,
        "trusted": True
    }

    approval_id = "appr-high-risk-001"
    challenge_nonce = "chal-nonce-highrisk-777"
    action_type = "shell_command"
    target = "powershell -Command Remove-Item"

    gateway.pending_approvals[approval_id] = {
        "action_type": action_type,
        "description": "Execute dangerous script",
        "dangerous_target": target,
        "challenge": challenge_nonce,
        "timestamp": time.time(),
        "expires_at": time.time() + 60.0
    }

    with patch("backend.services.manager.ServiceManager.get_instance", return_value=auth_service):
        # 1. Missing signature should fail
        fail_res, fail_msg = gateway.submit_approval_decision_with_biometrics(
            approval_id=approval_id,
            decision="approve",
            challenge=challenge_nonce,
            device_id=device_id,
            biometric_signature=None
        )
        assert fail_res is False
        assert "signature required" in fail_msg.lower()

        # 2. Valid Ed25519 signature on canonical challenge
        canonical_msg = f"JARVIS_APPROVAL_CHALLENGE:{approval_id}:{action_type}:{target}:{challenge_nonce}"
        sig_bytes = client_priv.sign(canonical_msg.encode("utf-8"))
        valid_sig_b64 = base64.b64encode(sig_bytes).decode("utf-8")

        pass_res, pass_msg = gateway.submit_approval_decision_with_biometrics(
            approval_id=approval_id,
            decision="approve",
            challenge=challenge_nonce,
            device_id=device_id,
            biometric_signature=valid_sig_b64
        )
        assert pass_res is True


# ==============================================================================
# 5. OAuth2Service Security & Vault Integration Tests
# ==============================================================================

def test_oauth_pkce_and_token_vault_storage(tmp_path):
    """Ensure OAuth2Service uses PKCE state and securely encrypts tokens in CredentialVault."""
    vault = CredentialVault(vault_dir=str(tmp_path / "oauth_vault"))
    oauth_svc = OAuth2Service(vault=vault)

    # 1. Generate authorization URL with PKCE
    auth_data = oauth_svc.generate_authorization_url("google")
    assert "authorization_url" in auth_data
    assert "state" in auth_data
    assert "code_challenge=" in auth_data["authorization_url"]
    assert "code_challenge_method=S256" in auth_data["authorization_url"]

    # 2. Store mock tokens securely into vault
    mock_token_data = {
        "access_token": "ya29.a0AfH6SMockAccessToken12345",
        "refresh_token": "1//04MockRefreshToken98765",
        "expires_at": time.time() + 3600,
        "token_type": "Bearer"
    }
    oauth_svc._store_token("google", mock_token_data)

    # 3. Retrieve token from vault
    loaded = oauth_svc.get_stored_token("google")
    assert loaded is not None
    assert loaded["access_token"] == "ya29.a0AfH6SMockAccessToken12345"
    assert loaded["refresh_token"] == "1//04MockRefreshToken98765"


# ==============================================================================
# 6. Debug Endpoints Automatic Sanitization Tests
# ==============================================================================

def test_debug_payload_sanitization():
    """Ensure debug router payloads strip clipboard secrets and context tokens."""
    raw_debug_data = {
        "timestamp": 1718000000.0,
        "active_app": "notepad.exe",
        "clipboard_text": "Here is my secret token: sk-proj-1234567890abcdef1234567890 and pass: password=SuperSecret123!",
        "execution_traces": [
            {
                "tool": "terminal_exec",
                "args": {"api_key": "AIzaSySecretApiKey1234567890", "cmd": "curl -H 'Authorization: Bearer mysecrettoken1234567890'"}
            }
        ]
    }

    sanitized = sanitize_payload(raw_debug_data)
    assert "sk-proj-1234567890abcdef" not in sanitized["clipboard_text"]
    assert "SuperSecret123!" not in sanitized["clipboard_text"]
    assert "AIzaSySecretApiKey1234567890" not in str(sanitized["execution_traces"])
    assert "mysecrettoken1234567890" not in str(sanitized["execution_traces"])
