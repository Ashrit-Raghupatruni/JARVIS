"""
FastAPI Endpoints for Direct OAuth2 Authentication and API operations
(Google Workspace & Microsoft 365).
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Query, Body, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from loguru import logger

from backend.services.oauth_service import oauth_service

router = APIRouter(prefix="/api/v1/oauth", tags=["OAuth2 Integrations"])


@router.get("/status")
async def get_oauth_status():
    """Get connection and configuration status for Google Workspace and Microsoft 365."""
    return {"status": "ok", "providers": oauth_service.get_status()}


@router.get("/{provider}/authorize")
async def oauth_authorize(provider: str):
    """
    Generate authorization URL for Google Workspace or Microsoft 365.
    Redirects user or returns auth URL payload.
    """
    try:
        data = oauth_service.generate_authorization_url(provider.lower())
        return {"status": "ok", **data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating OAuth URL for {provider}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: Optional[str] = Query(None, description="CSRF state parameter")
):
    """
    OAuth2 callback handler. Exchanges authorization code for tokens and persists encrypted credentials.
    """
    try:
        res = await oauth_service.exchange_code_for_token(provider.lower(), code, state=state)
        # Return HTML or JSON confirmation
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"Successfully connected to {provider.capitalize()}!",
                "data": res
            }
        )
    except Exception as e:
        logger.error(f"OAuth callback failed for {provider}: {e}")
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"OAuth callback failed: {str(e)}"}
        )


@router.post("/{provider}/refresh")
async def oauth_refresh_token(provider: str):
    """Manually force token refresh & rotation."""
    try:
        res = await oauth_service.refresh_token(provider.lower())
        return {
            "status": "refreshed",
            "provider": provider,
            "expires_at": res.get("expires_at"),
            "user_email": res.get("user_email")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{provider}/disconnect")
async def oauth_disconnect(provider: str):
    """Disconnect and revoke OAuth tokens."""
    try:
        success = oauth_service.disconnect(provider.lower())
        return {"status": "disconnected", "provider": provider, "success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Direct REST Endpoints for Google & Microsoft Actions ───────────────────────

@router.get("/google/gmail/messages")
async def list_gmail_messages(query: str = "", max_results: int = 10):
    try:
        return await oauth_service.gmail_list_messages(query=query, max_results=max_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google/gmail/send")
async def send_gmail_message(payload: Dict[str, Any] = Body(...)):
    to = payload.get("to")
    subject = payload.get("subject", "No Subject")
    body = payload.get("body", "")
    if not to:
        raise HTTPException(status_code=400, detail="Recipient 'to' field required.")
    try:
        return await oauth_service.gmail_send_message(to=to, subject=subject, body=body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/google/calendar/events")
async def list_google_calendar_events(time_min: Optional[str] = None, max_results: int = 10):
    try:
        return await oauth_service.google_calendar_list_events(time_min=time_min, max_results=max_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google/calendar/events")
async def create_google_calendar_event(payload: Dict[str, Any] = Body(...)):
    summary = payload.get("summary")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    description = payload.get("description", "")
    if not summary or not start_time or not end_time:
        raise HTTPException(status_code=400, detail="'summary', 'start_time', and 'end_time' are required.")
    try:
        return await oauth_service.google_calendar_create_event(
            summary=summary, start_time=start_time, end_time=end_time, description=description
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/microsoft/outlook/messages")
async def list_outlook_messages(query: str = "", max_results: int = 10):
    try:
        return await oauth_service.outlook_list_messages(query=query, max_results=max_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/microsoft/outlook/send")
async def send_outlook_message(payload: Dict[str, Any] = Body(...)):
    to = payload.get("to")
    subject = payload.get("subject", "No Subject")
    body = payload.get("body", "")
    if not to:
        raise HTTPException(status_code=400, detail="Recipient 'to' field required.")
    try:
        return await oauth_service.outlook_send_message(to=to, subject=subject, body=body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/microsoft/calendar/events")
async def list_outlook_calendar_events(start_time: Optional[str] = None, end_time: Optional[str] = None, max_results: int = 10):
    try:
        return await oauth_service.outlook_calendar_list_events(start_time=start_time, end_time=end_time, max_results=max_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/microsoft/calendar/events")
async def create_outlook_calendar_event(payload: Dict[str, Any] = Body(...)):
    subject = payload.get("subject")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    body = payload.get("body", "")
    if not subject or not start_time or not end_time:
        raise HTTPException(status_code=400, detail="'subject', 'start_time', and 'end_time' are required.")
    try:
        return await oauth_service.outlook_calendar_create_event(
            subject=subject, start_time=start_time, end_time=end_time, body=body
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
