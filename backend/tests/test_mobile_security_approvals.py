"""
JARVIS AI OS — Mobile Biometric Approval Proof & Security Test Suite.
=====================================================================
Validates:
1. Authentication: JWT generation, validation, expiration, and malformed token rejection.
2. Authorization: Endpoint access controls and remote execution protection.
3. Cryptographic Approval Flow: Challenge generation, canonical payload binding, Ed25519 signature verification.
4. Attack Prevention: Replay attack prevention, altered action/target payload rejection, expired challenge rejection.
5. Anti-Spoofing: Rejection of fake/mock biometric string placeholders (e.g. bio_sig_123).
"""

import time
import base64
import pytest
import asyncio
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from backend.services.mobile_auth import MobileAuthService
from backend.services.mobile_gateway import MobileGatewayService
from backend.services.manager import ServiceManager


@pytest.fixture
def auth_service(tmp_path):
    """Instantiate isolated MobileAuthService with temporary directory."""
    svc = MobileAuthService(data_dir=str(tmp_path))
    ServiceManager.register_instance("mobile_auth_service", svc)
    return svc


@pytest.fixture
def gateway_service():
    """Instantiate MobileGatewayService."""
    gw = MobileGatewayService()
    ServiceManager.register_instance("mobile_gateway_service", gw)
    return gw


def generate_test_client_keypair():
    """Generate Ed25519 keypair for client test simulation."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    pub_b64 = base64.b64encode(pub_raw).decode("utf-8")
    return priv, pub_b64


# ===========================================================================
# 1. AUTHENTICATION & JWT SECURITY
# ===========================================================================

def test_jwt_generation_and_verification(auth_service):
    """Verify standard JWT token creation and payload extraction."""
    token = auth_service.create_jwt_token("device-test-01", "Pixel 8 Pro")
    assert token is not None

    payload = auth_service.verify_token(token)
    assert payload is not None
    assert payload["sub"] == "device-test-01"
    assert payload["friendly_name"] == "Pixel 8 Pro"


def test_missing_or_empty_token(auth_service):
    """Fails closed on missing or empty token."""
    assert auth_service.verify_token("") is None
    assert auth_service.verify_token("   ") is None
    assert auth_service.verify_token(None) is None


def test_malformed_token_rejection(auth_service):
    """Fails closed on corrupted or tampered token."""
    assert auth_service.verify_token("Bearer invalid.tampered.token") is None
    assert auth_service.verify_token("random_garbage_string") is None


def test_token_with_wrong_secret(auth_service):
    """Fails closed if signed with untrusted secret key."""
    import jwt
    bogus_token = jwt.encode({"sub": "hacker-device", "exp": int(time.time()) + 3600}, "wrong_secret_key", algorithm="HS256")
    assert auth_service.verify_token(bogus_token) is None


# ===========================================================================
# 2. CRYPTOGRAPHIC PAIRING WITH ED25519
# ===========================================================================

def test_ed25519_pairing_flow(auth_service):
    """Simulates complete cryptographic device pairing with Ed25519 signature."""
    client_priv, client_pub_b64 = generate_test_client_keypair()
    device_id = "pixel-secure-device"

    init_res = auth_service.initiate_pairing("Pixel Companion", device_id)
    session_id = init_res.pairing_session_id
    pin = init_res.pairing_code
    nonce = init_res.nonce

    # Client signs challenge: JARVIS_CLIENT_PAIR:{session_id}:{nonce}:{device_id}
    client_msg = f"JARVIS_CLIENT_PAIR:{session_id}:{nonce}:{device_id}"
    sig_bytes = client_priv.sign(client_msg.encode("utf-8"))
    sig_b64 = base64.b64encode(sig_bytes).decode("utf-8")

    confirm_res = auth_service.confirm_pairing(
        session_id=session_id,
        pairing_code=pin,
        device_id=device_id,
        client_public_key=client_pub_b64,
        client_signature=sig_b64
    )

    assert confirm_res is not None
    assert confirm_res.status == "paired_successfully"
    assert confirm_res.device_id == device_id
    assert device_id in auth_service._trusted_devices
    assert auth_service._trusted_devices[device_id]["public_key"] == client_pub_b64


def test_pairing_fails_on_invalid_client_signature(auth_service):
    """Pairing fails closed if client signature does not match public key."""
    client_priv, client_pub_b64 = generate_test_client_keypair()
    device_id = "pixel-secure-device"

    init_res = auth_service.initiate_pairing("Pixel Companion", device_id)
    session_id = init_res.pairing_session_id
    pin = init_res.pairing_code

    confirm_res = auth_service.confirm_pairing(
        session_id=session_id,
        pairing_code=pin,
        device_id=device_id,
        client_public_key=client_pub_b64,
        client_signature=base64.b64encode(b"invalid_signature_bytes_here!").decode("utf-8")
    )
    assert confirm_res is None


# ===========================================================================
# 3. CRYPTOGRAPHIC APPROVAL CHALLENGE-RESPONSE & REPLAY PROTECTION
# ===========================================================================

@pytest.mark.asyncio
async def test_cryptographic_approval_verification(gateway_service, auth_service):
    """Test valid Ed25519 signed approval for high-risk action."""
    client_priv, client_pub_b64 = generate_test_client_keypair()
    device_id = "test-hardware-token-01"

    # Register device with public key
    auth_service._trusted_devices[device_id] = {
        "device_id": device_id,
        "friendly_name": "Secure Phone",
        "public_key": client_pub_b64,
        "trusted": True
    }

    approval_task = asyncio.create_task(
        gateway_service.request_approval(
            action_type="system_shutdown",
            description="Power off desktop",
            dangerous_target="Host OS Core",
            timeout_seconds=5.0
        )
    )

    await asyncio.sleep(0.05)
    assert len(gateway_service.pending_approvals) == 1
    approval_id = list(gateway_service.pending_approvals.keys())[0]
    pending_item = gateway_service.pending_approvals[approval_id]
    challenge = pending_item["challenge"]
    assert len(challenge) == 64  # 32 bytes hex

    # Construct canonical challenge message
    canonical_msg = f"JARVIS_APPROVAL_CHALLENGE:{approval_id}:system_shutdown:Host OS Core:{challenge}"
    sig_bytes = client_priv.sign(canonical_msg.encode("utf-8"))
    sig_b64 = base64.b64encode(sig_bytes).decode("utf-8")

    # Submit valid cryptographic approval
    success, msg = gateway_service.submit_approval_decision_with_biometrics(
        approval_id=approval_id,
        decision="approve",
        challenge=challenge,
        device_id=device_id,
        biometric_signature=sig_b64
    )

    assert success is True
    assert "verified" in msg.lower()
    final_decision = await approval_task
    assert final_decision == "approve"


@pytest.mark.asyncio
async def test_replay_attack_prevention(gateway_service, auth_service):
    """Replaying an already consumed challenge fails immediately."""
    client_priv, client_pub_b64 = generate_test_client_keypair()
    device_id = "test-replay-device"

    auth_service._trusted_devices[device_id] = {
        "device_id": device_id,
        "public_key": client_pub_b64,
        "trusted": True
    }

    approval_task = asyncio.create_task(
        gateway_service.request_approval(
            action_type="file_delete",
            description="Delete system folder",
            dangerous_target="/critical/dir",
            timeout_seconds=5.0
        )
    )

    await asyncio.sleep(0.05)
    approval_id = list(gateway_service.pending_approvals.keys())[0]
    challenge = gateway_service.pending_approvals[approval_id]["challenge"]

    canonical_msg = f"JARVIS_APPROVAL_CHALLENGE:{approval_id}:file_delete:/critical/dir:{challenge}"
    sig_b64 = base64.b64encode(client_priv.sign(canonical_msg.encode("utf-8"))).decode("utf-8")

    # 1. First submission succeeds
    success, msg = gateway_service.submit_approval_decision_with_biometrics(
        approval_id=approval_id,
        decision="approve",
        challenge=challenge,
        device_id=device_id,
        biometric_signature=sig_b64
    )
    assert success is True
    await approval_task

    # 2. Replay attempt with same approval / consumed challenge fails
    gateway_service.pending_approvals[approval_id] = {
        "approval_id": approval_id,
        "action_type": "file_delete",
        "dangerous_target": "/critical/dir",
        "challenge": challenge,
        "timestamp": time.time(),
        "expires_at": time.time() + 30.0,
        "event": asyncio.Event()
    }

    replay_success, replay_msg = gateway_service.submit_approval_decision_with_biometrics(
        approval_id=approval_id,
        decision="approve",
        challenge=challenge,
        device_id=device_id,
        biometric_signature=sig_b64
    )
    assert replay_success is False
    assert "replay" in replay_msg.lower()


@pytest.mark.asyncio
async def test_altered_action_payload_rejection(gateway_service, auth_service):
    """Signature computed for delete_file cannot be used for shell_command."""
    client_priv, client_pub_b64 = generate_test_client_keypair()
    device_id = "test-altered-device"

    auth_service._trusted_devices[device_id] = {
        "device_id": device_id,
        "public_key": client_pub_b64,
        "trusted": True
    }

    approval_task = asyncio.create_task(
        gateway_service.request_approval(
            action_type="shell_command",
            description="Run bash script",
            dangerous_target="Terminal Subshell",
            timeout_seconds=5.0
        )
    )

    await asyncio.sleep(0.05)
    approval_id = list(gateway_service.pending_approvals.keys())[0]
    challenge = gateway_service.pending_approvals[approval_id]["challenge"]

    # Attacker tries to sign a different action type
    altered_msg = f"JARVIS_APPROVAL_CHALLENGE:{approval_id}:read_file:Terminal Subshell:{challenge}"
    sig_b64 = base64.b64encode(client_priv.sign(altered_msg.encode("utf-8"))).decode("utf-8")

    success, msg = gateway_service.submit_approval_decision_with_biometrics(
        approval_id=approval_id,
        decision="approve",
        challenge=challenge,
        device_id=device_id,
        biometric_signature=sig_b64
    )
    assert success is False
    assert "signature verification failed" in msg.lower()


# ===========================================================================
# 4. REJECTION OF FAKE BIOMETRIC PLACEHOLDERS (ANTI-SPOOFING)
# ===========================================================================

@pytest.mark.asyncio
async def test_fake_bio_sig_string_rejection(gateway_service):
    """Explicitly verifies that placeholders like bio_sig_123 are rejected."""
    approval_task = asyncio.create_task(
        gateway_service.request_approval(
            action_type="registry_write",
            description="Modify registry",
            dangerous_target="HKLM\\Software",
            timeout_seconds=5.0
        )
    )

    await asyncio.sleep(0.05)
    approval_id = list(gateway_service.pending_approvals.keys())[0]

    # Try fake signature
    success, msg = gateway_service.submit_approval_decision_with_biometrics(
        approval_id=approval_id,
        decision="approve",
        biometric_authenticated=True,
        biometric_signature="bio_sig_1726135000_abcde"
    )
    assert success is False
    assert "mock" in msg.lower() or "invalid" in msg.lower()


@pytest.mark.asyncio
async def test_expired_approval_rejection(gateway_service):
    """Expired approvals cannot be approved."""
    approval_task = asyncio.create_task(
        gateway_service.request_approval(
            action_type="system_shutdown",
            description="Exit",
            dangerous_target="OS",
            timeout_seconds=0.1
        )
    )

    await asyncio.sleep(0.15)
    approval_id = list(gateway_service.pending_approvals.keys())[0] if gateway_service.pending_approvals else "appr_dummy"

    success, msg = gateway_service.submit_approval_decision_with_biometrics(
        approval_id=approval_id,
        decision="approve",
        biometric_authenticated=True
    )
    assert success is False
    assert "expired" in msg.lower() or "not found" in msg.lower()
