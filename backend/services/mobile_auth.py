"""
JARVIS AI Operating System - Mobile Authentication & Pairing Service.

Manages one-time pairing PINs, real Ed25519 keypair generation, trusted device whitelists,
and JWT token generation for secure mobile app authorization.
Fails closed on unauthenticated / invalid PIN pairing requests.
"""

import os
import json
import time
import uuid
import secrets
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

# Cryptography Ed25519 support
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# PyJWT for token generation
try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

from backend.config import get_settings
from backend.models.mobile_schemas import (
    PairingInitiateResponse,
    PairingConfirmResponse,
    DeviceInfo
)


class MobileAuthService:
    """Device pairing, trusted device store, and JWT token validator."""

    def __init__(self, data_dir: str = "data") -> None:
        self.settings = get_settings()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trusted_devices_file = self.data_dir / "trusted_devices.json"
        
        self._jwt_secret = getattr(self.settings, "JWT_SECRET_KEY", "jarvis_personal_mobile_secret_987654321")
        is_prod = str(getattr(self.settings, "ENVIRONMENT", "development")).lower() in ("production", "prod")
        default_secret = "jarvis_personal_mobile_secret_987654321"
        if is_prod and (not self._jwt_secret or self._jwt_secret == default_secret):
            raise RuntimeError("CRITICAL SECURITY: Default or empty JWT_SECRET_KEY detected in production environment! Set a strong JWT_SECRET_KEY in production.")

        self._active_sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> metadata
        self._completed_sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> device_entry
        self._trusted_devices: Dict[str, Dict[str, Any]] = self._load_trusted_devices()

        # Initialize real Ed25519 asymmetric cryptographic keypair
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        raw_pub = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        self._server_public_key_b64 = base64.b64encode(raw_pub).decode("utf-8")

        logger.info("MobileAuthService initialized (Loaded {} trusted devices, Ed25519 PubKey={})",
                    len(self._trusted_devices), self._server_public_key_b64[:12] + "...")

    def _load_trusted_devices(self) -> Dict[str, Dict[str, Any]]:
        """Load registered paired devices from local trusted_devices.json."""
        if self.trusted_devices_file.exists():
            try:
                with open(self.trusted_devices_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading trusted_devices.json: {e}")
        return {}

    def _save_trusted_devices(self) -> None:
        """Persist registered paired devices to disk."""
        try:
            with open(self.trusted_devices_file, "w", encoding="utf-8") as f:
                json.dump(self._trusted_devices, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving trusted_devices.json: {e}")

    def initiate_pairing(self, device_name: str, device_id: str) -> PairingInitiateResponse:
        """Generate a random 6-digit numeric pairing code and session ID for desktop UI with real Ed25519 public key and signed challenge."""
        session_id = str(uuid.uuid4())
        pairing_code = f"{secrets.randbelow(900000) + 100000}"  # 6-digit PIN
        nonce = secrets.token_hex(16)
        challenge_msg = f"JARVIS_PAIR_CHALLENGE:{session_id}:{nonce}:{pairing_code}"
        server_sig_bytes = self._private_key.sign(challenge_msg.encode("utf-8"))
        server_sig_b64 = base64.b64encode(server_sig_bytes).decode("utf-8")
        
        self._active_sessions[session_id] = {
            "session_id": session_id,
            "pairing_code": pairing_code,
            "nonce": nonce,
            "server_signature": server_sig_b64,
            "device_name": device_name,
            "device_id": device_id,
            "created_at": time.time(),
            "expires_at": time.time() + 300  # 5 minutes
        }
        
        logger.info("Generated pairing code {} for device '{}' (Session: {})", pairing_code, device_name, session_id)
        return PairingInitiateResponse(
            pairing_session_id=session_id,
            pairing_code=pairing_code,
            server_public_key=self._server_public_key_b64,
            nonce=nonce,
            server_signature=server_sig_b64,
            expires_in_seconds=300
        )

    def sign_challenge(self, message: str) -> str:
        """Sign a string challenge using the server's Ed25519 private key."""
        sig = self._private_key.sign(message.encode("utf-8"))
        return base64.b64encode(sig).decode("utf-8")

    def verify_client_signature(
        self,
        client_public_key_b64: str,
        challenge_message: str,
        signature_b64: str
    ) -> bool:
        """
        Cryptographically verify an Ed25519 digital signature from a client device.
        Fails closed on any corruption, invalid key, or invalid signature.
        """
        try:
            raw_pub = base64.b64decode(client_public_key_b64)
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(raw_pub)
            sig_bytes = base64.b64decode(signature_b64)
            pub_key.verify(sig_bytes, challenge_message.encode("utf-8"))
            return True
        except Exception as e:
            logger.warning("Cryptographic signature verification failed: {}", e)
            return False

    def confirm_pairing(
        self,
        session_id: str,
        pairing_code: str,
        device_id: str,
        client_public_key: Optional[str] = None,
        client_signature: Optional[str] = None
    ) -> Optional[PairingConfirmResponse]:
        """
        Validate pairing code and issue JWT access token.
        If client provides Ed25519 public key and signature, cryptographically verifies the challenge signature.
        Fails closed on any mismatch or invalid signature.
        """
        session = self._active_sessions.get(session_id)
        if not session:
            logger.warning("Pairing failed: Session ID {} not found", session_id)
            return None

        if time.time() > session["expires_at"]:
            logger.warning("Pairing failed: Session ID {} expired", session_id)
            del self._active_sessions[session_id]
            return None

        if session["pairing_code"] != pairing_code:
            logger.warning("Pairing failed: Incorrect pairing code for session {}", session_id)
            return None

        # If cryptographic challenge response was provided, verify client's signature
        if client_public_key and client_signature:
            nonce = session.get("nonce", "")
            expected_msg = f"JARVIS_CLIENT_PAIR:{session_id}:{nonce}:{device_id}"
            if not self.verify_client_signature(client_public_key, expected_msg, client_signature):
                logger.warning("Pairing failed: Invalid cryptographic signature from client {}", device_id)
                return None

        # Pairing successful — register device as trusted
        friendly_name = session["device_name"]
        device_entry = {
            "device_id": device_id,
            "friendly_name": friendly_name,
            "public_key": client_public_key or "",
            "pairing_session_id": session_id,
            "registered_at": time.time(),
            "last_active": time.time(),
            "trusted": True
        }
        self._trusted_devices[device_id] = device_entry
        self._completed_sessions[session_id] = device_entry
        self._save_trusted_devices()
        del self._active_sessions[session_id]

        # Generate JWT token
        token = self.create_jwt_token(device_id, friendly_name)

        logger.info("✓ Successfully paired device '{}' ({}) [CryptoVerified={}]",
                    friendly_name, device_id, bool(client_public_key and client_signature))
        return PairingConfirmResponse(
            status="paired_successfully",
            access_token=token,
            token_type="bearer",
            device_id=device_id,
            friendly_name=friendly_name
        )

    def is_session_paired(self, session_id: str) -> bool:
        """Check if a specific session ID completed pairing successfully."""
        if session_id in self._completed_sessions:
            return True
        return any(d.get("pairing_session_id") == session_id for d in self._trusted_devices.values())

    def easy_pair(self, pin: str, device_name: str = "Android Phone", device_id: str = "android-companion-1") -> Optional[Dict[str, Any]]:
        """
        Secure pairing for mobile companion app.
        Validates PIN strictly against active, non-expired pairing sessions.
        Fails closed with no bypass if PIN is invalid.
        """
        now = time.time()
        matching_session_id = None
        for sess_id, sess in list(self._active_sessions.items()):
            if sess["expires_at"] < now:
                del self._active_sessions[sess_id]
                continue
            if sess["pairing_code"] == str(pin).strip():
                matching_session_id = sess_id
                break
        
        if matching_session_id:
            res = self.confirm_pairing(matching_session_id, str(pin).strip(), device_id)
            if res:
                return {"status": "paired", "token": res.access_token, "device_id": device_id}

        logger.warning("❌ Mobile pairing rejected: Invalid or expired pairing PIN '{}' for device '{}'", pin, device_name)
        return None

    def create_jwt_token(self, device_id: str, friendly_name: str) -> str:
        """Create signed JWT access token for mobile authentication."""
        payload = {
            "sub": device_id,
            "friendly_name": friendly_name,
            "iat": int(time.time()),
            "exp": int(time.time()) + (86400 * 365)  # 1 year token for personal device
        }
        if HAS_JWT:
            return jwt.encode(payload, self._jwt_secret, algorithm="HS256")
        return f"DEV_TOKEN_{device_id}_{int(time.time())}"

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return authenticated payload. Fails closed on any decode error."""
        if not token:
            return None

        clean_token = token.replace("Bearer ", "").strip()
        if not clean_token:
            return None

        settings = get_settings()

        # Development token prefix is strictly disabled in production (requires settings.DEBUG == True)
        if clean_token.startswith("DEV_TOKEN_"):
            if not getattr(settings, "DEBUG", False):
                logger.warning("DEV_TOKEN_ rejected because settings.DEBUG is False")
                return None
            dev_id = clean_token.replace("DEV_TOKEN_", "").strip() or "dev-device"
            return {"sub": dev_id, "friendly_name": f"Dev Device ({dev_id})", "is_dev": True}

        if HAS_JWT:
            try:
                payload = jwt.decode(clean_token, self._jwt_secret, algorithms=["HS256"])
                dev_id = payload.get("sub")
                if not dev_id:
                    logger.warning("JWT decode succeeded but missing 'sub' claim")
                    return None
                if dev_id in self._trusted_devices:
                    self._trusted_devices[dev_id]["last_active"] = time.time()
                return payload
            except Exception as e:
                logger.warning(f"JWT decode failed: {e}. Token rejected.")
                return None

        logger.warning("JWT library unavailable and DEV_TOKEN_ rejected. Token verification failed.")
        return None

    def get_trusted_devices(self) -> List[DeviceInfo]:
        """Return list of all registered trusted mobile devices."""
        return [
            DeviceInfo(**data) for data in self._trusted_devices.values()
        ]
