"""
JARVIS AI Operating System - Telegram Integration API Router.

Provides status monitoring, pairing management, and test push notification triggers
for the Telegram Remote Control bridge.
"""

import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from loguru import logger

from backend.services.telegram_service import telegram_service


async def require_admin_or_local(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> Dict[str, Any]:
    """Require loopback origin (desktop UI HUD) or valid administrative bearer token."""
    if request.client and request.client.host in ("127.0.0.1", "localhost", "::1", "testclient"):
        return {"sub": "localhost", "scope": "admin"}

    if authorization:
        from backend.services.manager import ServiceManager
        auth_svc = getattr(request.app.state, "mobile_auth_service", None) or ServiceManager.get_instance("mobile_auth_service")
        if auth_svc and hasattr(auth_svc, "verify_token"):
            payload = auth_svc.verify_token(authorization)
            if payload:
                return payload

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Localhost access or valid administrative authentication token required"
    )


telegram_router = APIRouter(
    prefix="/api/v1/telegram",
    tags=["Telegram Remote Integration"]
)


class TelegramStatusResponse(BaseModel):
    enabled: bool
    connected: bool
    bot_username: Optional[str] = None
    bot_id: Optional[int] = None
    authorized_chat_id: Optional[str] = None
    is_paired: bool
    pairing_active: bool
    pending_approvals: int = 0
    last_activity_time: float = 0.0
    total_commands_executed: int = 0
    total_unauthorized_attempts: int = 0


class TelegramPairingInitiateResponse(BaseModel):
    status: str
    pin: str
    expires_at: float
    timeout_seconds: float
    instructions: str


class TelegramNotificationTestRequest(BaseModel):
    title: Optional[str] = "JARVIS Remote Alert"
    message: Optional[str] = "This is a test notification from your JARVIS Workstation."


@telegram_router.get("/status", response_model=TelegramStatusResponse)
async def get_telegram_status():
    """Fetch current Telegram Bot status, connectivity, and authorized pairing state."""
    svc_status = telegram_service.get_service_status()

    # Query pending approvals count from MobileGateway if available
    pending_count = 0
    try:
        from backend.services.manager import ServiceManager
        gateway = ServiceManager.get_instance("mobile_gateway_service")
        if gateway and hasattr(gateway, "pending_approvals"):
            pending_count = len(gateway.pending_approvals)
    except Exception:
        pass

    return TelegramStatusResponse(
        enabled=svc_status["enabled"],
        connected=svc_status["connected"],
        bot_username=svc_status["bot_username"],
        bot_id=svc_status["bot_id"],
        authorized_chat_id=svc_status["authorized_chat_id"],
        is_paired=svc_status["is_paired"],
        pairing_active=svc_status["pairing_active"],
        pending_approvals=pending_count,
        last_activity_time=svc_status["last_activity_time"],
        total_commands_executed=svc_status["total_commands_executed"],
        total_unauthorized_attempts=svc_status["total_unauthorized_attempts"],
    )


@telegram_router.post("/pair/initiate", response_model=TelegramPairingInitiateResponse)
async def initiate_telegram_pairing(auth_ctx=Depends(require_admin_or_local)):
    """Generate a 6-digit numeric pairing PIN for desktop HUD display."""
    if not telegram_service.enabled:
        raise HTTPException(
            status_code=400,
            detail="Telegram service is disabled or bot token is missing"
        )

    timeout = 300.0  # 5 minutes
    pin = telegram_service.generate_pairing_pin(timeout_seconds=timeout)
    expires_at = time.time() + timeout
    bot_name = telegram_service._bot_username or "your bot"

    return TelegramPairingInitiateResponse(
        status="pairing_initiated",
        pin=pin,
        expires_at=expires_at,
        timeout_seconds=timeout,
        instructions=f"Open Telegram, search for @{bot_name}, and send: /pair {pin}"
    )


@telegram_router.post("/unpair")
async def unpair_telegram_account(auth_ctx=Depends(require_admin_or_local)):
    """Revoke authorized Telegram account pairing and reset to unpaired state."""
    telegram_service.chat_id = ""
    telegram_service._persist_chat_id("")
    logger.info("✓ [SECURITY] Telegram authorized account un-paired via API.")
    return {"status": "unpaired", "message": "Telegram account pairing revoked."}


@telegram_router.post("/test_notification")
async def send_test_notification(req: TelegramNotificationTestRequest, auth_ctx=Depends(require_admin_or_local)):
    """Trigger a test alert to the paired Telegram user."""
    if not telegram_service.chat_id:
        raise HTTPException(
            status_code=400,
            detail="No Telegram account currently paired. Pair an account first."
        )

    sent = await telegram_service.send_notification(
        title=req.title or "Test Alert",
        body=req.message or "JARVIS test ping",
        level="info"
    )

    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Failed to send notification via Telegram API"
        )

    return {"status": "sent", "message": "Test notification delivered successfully."}
