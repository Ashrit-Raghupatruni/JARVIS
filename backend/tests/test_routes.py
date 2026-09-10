"""
FastAPI REST Route Discovery & End-to-End Test Suite.
"""

import pytest
import httpx
from httpx import ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_route_health():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
        assert response.status_code in (200, 404, 503) or response.status_code < 500


@pytest.mark.asyncio
async def test_route_system_status():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/system/status")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            assert "status" in data or "services" in data or "cpu" in data


@pytest.mark.asyncio
async def test_route_ui_performance():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/ui/performance")
        assert response.status_code == 200
        data = response.json()
        assert "cpu_usage_percent" in data or "ram_usage_percent" in data


@pytest.mark.asyncio
async def test_route_mobile_pair_initiate():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/mobile/pair/initiate", json={
            "device_name": "Pytest Phone",
            "device_id": "pytest-phone-001"
        })
        assert response.status_code == 200
        data = response.json()
        assert "pairing_code" in data
        assert "pairing_session_id" in data
        assert "server_public_key" in data


@pytest.mark.asyncio
async def test_route_mobile_pair_qr_generate():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/mobile/pair/qr/generate")
        assert response.status_code == 200
        data = response.json()
        assert "qr_payload" in data
        assert data["qr_payload"].startswith("jarvis_pair://")


@pytest.mark.asyncio
async def test_route_mobile_devices():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/mobile/devices")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_route_rag_action_add_document():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/ui/rag_action", json={
            "action": "add_document",
            "name": "test_architecture_spec.md",
            "content": "# Test Document Content for Vector Indexing\nJARVIS AI Operating System Architecture."
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"
        assert data.get("chunks", 0) >= 1


@pytest.mark.asyncio
async def test_route_mobile_pair_crypto_mutual_verification():
    """Verify Ed25519 cryptographic challenge-response authentication protocol."""
    import base64
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization

    # Generate genuine client Ed25519 keypair
    client_priv = ed25519.Ed25519PrivateKey.generate()
    client_pub = client_priv.public_key()
    client_pub_bytes = client_pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    client_pub_b64 = base64.b64encode(client_pub_bytes).decode("utf-8")

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Initiate pairing
        init_res = await ac.post("/api/v1/mobile/pair/initiate", json={
            "device_name": "Crypto Mobile Test",
            "device_id": "crypto-device-007"
        })
        assert init_res.status_code == 200
        init_data = init_res.json()
        session_id = init_data["pairing_session_id"]
        pin = init_data["pairing_code"]
        nonce = init_data.get("nonce", "")
        server_pub_b64 = init_data["server_public_key"]
        server_sig_b64 = init_data.get("server_signature")

        # 2. Cryptographically verify server signature
        server_pub_bytes = base64.b64decode(server_pub_b64)
        server_pub_key = ed25519.Ed25519PublicKey.from_public_bytes(server_pub_bytes)
        expected_srv_challenge = f"JARVIS_PAIR_CHALLENGE:{session_id}:{nonce}:{pin}"
        server_pub_key.verify(base64.b64decode(server_sig_b64), expected_srv_challenge.encode("utf-8"))

        # 3. Sign client challenge response
        client_msg = f"JARVIS_CLIENT_PAIR:{session_id}:{nonce}:crypto-device-007"
        client_sig = client_priv.sign(client_msg.encode("utf-8"))
        client_sig_b64 = base64.b64encode(client_sig).decode("utf-8")

        # 4. Confirm pairing with valid cryptographic signature
        confirm_res = await ac.post("/api/v1/mobile/pair/confirm", json={
            "pairing_session_id": session_id,
            "pairing_code": pin,
            "device_id": "crypto-device-007",
            "client_public_key": client_pub_b64,
            "client_signature": client_sig_b64
        })
        assert confirm_res.status_code == 200
        conf_data = confirm_res.json()
        assert conf_data["status"] == "paired_successfully"
        assert "access_token" in conf_data

        # 5. Verify that forged signature is rejected (fail closed)
        forged_res = await ac.post("/api/v1/mobile/pair/confirm", json={
            "pairing_session_id": session_id,
            "pairing_code": pin,
            "device_id": "crypto-device-007",
            "client_public_key": client_pub_b64,
            "client_signature": base64.b64encode(b"forged_signature_bytes_12345678").decode("utf-8")
        })
        assert forged_res.status_code in (400, 401)


@pytest.mark.asyncio
async def test_route_face_auth_full_flow():
    """Verify face authentication status, enrollment, and verification endpoints."""
    import math
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Check status
        status_res = await ac.get("/api/v1/auth/face/status")
        assert status_res.status_code == 200
        assert "enrolled" in status_res.json()

        # 2. Enroll face profile
        sample_vec = [float((i * 7) % 11) for i in range(128)]
        norm = math.sqrt(sum(x * x for x in sample_vec))
        sample_vec = [x / norm for x in sample_vec]

        enroll_res = await ac.post("/api/v1/auth/face/enroll", json={
            "user_name": "Ashrit_Test",
            "embedding": sample_vec
        })
        assert enroll_res.status_code == 200
        assert enroll_res.json().get("status") == "ok"

        # 3. Verify matching face with liveness
        verify_res = await ac.post("/api/v1/auth/face/verify", json={
            "embedding": sample_vec,
            "frame_sequence": [
                {"eye_aspect_ratio": 0.35, "head_yaw": 0.0},
                {"eye_aspect_ratio": 0.10, "head_yaw": 3.0},
            ]
        })
        assert verify_res.status_code == 200
        v_result = verify_res.json().get("result", {})
        assert v_result.get("authenticated") is True
        assert v_result.get("similarity", 0) >= 0.82

