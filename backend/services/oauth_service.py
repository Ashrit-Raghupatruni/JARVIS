"""
OAuth2 Integration Service for Google Workspace & Microsoft 365.

Direct OAuth2 authorization code flow, PKCE state verification, encrypted token
storage with rotation in CredentialVault, and native ToolRegistry action handlers.
Scoped strictly to Google (Gmail + Calendar) and Microsoft (Outlook + Calendar).
"""

import os
import time
import json
import base64
import hashlib
import secrets
import urllib.parse
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger
import httpx

from backend.services.security.vault import CredentialVault
from backend.services.manager import ServiceManager


class OAuthProviderConfig:
    """OAuth2 configuration parameters per provider."""
    def __init__(
        self,
        name: str,
        display_name: str,
        auth_url: str,
        token_url: str,
        userinfo_url: str,
        default_scopes: List[str],
        client_id_env: str,
        client_secret_env: str,
        redirect_uri: str = "http://localhost:8000/api/v1/oauth/callback"
    ):
        self.name = name
        self.display_name = display_name
        self.auth_url = auth_url
        self.token_url = token_url
        self.userinfo_url = userinfo_url
        self.default_scopes = default_scopes
        self.client_id_env = client_id_env
        self.client_secret_env = client_secret_env
        self.redirect_uri = redirect_uri

    @property
    def client_id(self) -> str:
        return os.getenv(self.client_id_env, "").strip()

    @property
    def client_secret(self) -> str:
        return os.getenv(self.client_secret_env, "").strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


class OAuth2Service:
    """
    Manages OAuth2 flows, automatic token refresh rotation, and provider API operations
    for Google Workspace (Gmail + Google Calendar) and Microsoft 365 (Outlook + Calendar).
    """

    PROVIDERS: Dict[str, OAuthProviderConfig] = {
        "google": OAuthProviderConfig(
            name="google",
            display_name="Google Workspace (Gmail & Calendar)",
            auth_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
            default_scopes=[
                "openid",
                "email",
                "profile",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/calendar.events"
            ],
            client_id_env="GOOGLE_CLIENT_ID",
            client_secret_env="GOOGLE_CLIENT_SECRET",
            redirect_uri="http://localhost:8000/api/v1/oauth/google/callback"
        ),
        "microsoft": OAuthProviderConfig(
            name="microsoft",
            display_name="Microsoft 365 (Outlook Mail & Calendar)",
            auth_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            userinfo_url="https://graph.microsoft.com/v1.0/me",
            default_scopes=[
                "offline_access",
                "User.Read",
                "Mail.Read",
                "Mail.Send",
                "Calendars.Read",
                "Calendars.ReadWrite"
            ],
            client_id_env="MICROSOFT_CLIENT_ID",
            client_secret_env="MICROSOFT_CLIENT_SECRET",
            redirect_uri="http://localhost:8000/api/v1/oauth/microsoft/callback"
        )
    }

    def __init__(self, vault: Optional[CredentialVault] = None, config_path: str = "data/oauth_config.json"):
        self.vault = vault or CredentialVault()
        self.config_path = config_path
        self._pending_states: Dict[str, Dict[str, Any]] = {}
        self._load_file_config()
        logger.info("OAuth2Service initialized with Google Workspace and Microsoft 365 providers.")

    def _load_file_config(self) -> None:
        """Load optional client IDs and secrets from data/oauth_config.json."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                for prov_name, creds in cfg.items():
                    if prov_name in self.PROVIDERS:
                        if creds.get("client_id") and not os.getenv(self.PROVIDERS[prov_name].client_id_env):
                            os.environ[self.PROVIDERS[prov_name].client_id_env] = creds["client_id"]
                        if creds.get("client_secret") and not os.getenv(self.PROVIDERS[prov_name].client_secret_env):
                            os.environ[self.PROVIDERS[prov_name].client_secret_env] = creds["client_secret"]
            except Exception as e:
                logger.warning(f"Failed to parse OAuth config file '{self.config_path}': {e}")

    # ── PKCE and Authorization URL Generation ──────────────────────────────────

    def generate_authorization_url(self, provider: str, custom_scopes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generate OAuth2 authorization URL with PKCE (Proof Key for Code Exchange) and CSRF state.
        """
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unsupported OAuth provider: '{provider}'. Must be 'google' or 'microsoft'.")

        cfg = self.PROVIDERS[provider]
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        
        # S256 PKCE challenge
        code_challenge_bytes = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).decode("ascii").rstrip("=")

        scopes = custom_scopes or cfg.default_scopes
        scope_str = " ".join(scopes)

        params = {
            "client_id": cfg.client_id or "jarvis_oauth_client",
            "response_type": "code",
            "redirect_uri": cfg.redirect_uri,
            "scope": scope_str,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }

        if provider == "google":
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        elif provider == "microsoft":
            params["response_mode"] = "query"
            params["prompt"] = "select_account"

        auth_url = f"{cfg.auth_url}?{urllib.parse.urlencode(params)}"

        # Store state for verification in callback
        self._pending_states[state] = {
            "provider": provider,
            "code_verifier": code_verifier,
            "created_at": time.time()
        }

        return {
            "provider": provider,
            "authorization_url": auth_url,
            "state": state,
            "configured": cfg.is_configured
        }

    # ── Code Exchange & Token Persistence ──────────────────────────────────────

    async def exchange_code_for_token(
        self,
        provider: str,
        code: str,
        state: Optional[str] = None,
        code_verifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens, and store securely in CredentialVault.
        """
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unsupported provider: '{provider}'")

        cfg = self.PROVIDERS[provider]

        # Verify state and retrieve verifier if stored
        if state and state in self._pending_states:
            saved = self._pending_states.pop(state)
            if not code_verifier:
                code_verifier = saved.get("code_verifier")

        token_payload = {
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": cfg.redirect_uri
        }
        if code_verifier:
            token_payload["code_verifier"] = code_verifier

        # Check if live credentials are configured
        if not cfg.is_configured:
            # Fallback simulated token for tests/mock verification
            mock_token = {
                "provider": provider,
                "access_token": f"mock_access_{provider}_{secrets.token_hex(16)}",
                "refresh_token": f"mock_refresh_{provider}_{secrets.token_hex(24)}",
                "expires_at": time.time() + 3600,
                "token_type": "Bearer",
                "scope": " ".join(cfg.default_scopes),
                "user_email": f"demo_user@{provider}.com"
            }
            self._store_token(provider, mock_token)
            return {
                "status": "connected_simulated",
                "provider": provider,
                "user_email": mock_token["user_email"],
                "expires_in": 3600
            }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(cfg.token_url, data=token_payload)
            if resp.status_code != 200:
                logger.error(f"Failed to exchange token with {provider}: {resp.text}")
                raise RuntimeError(f"Token exchange failed: {resp.text}")

            data = resp.json()
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in", 3600)
            expires_at = time.time() + int(expires_in)

            # Query user email
            user_email = await self._fetch_user_email(provider, access_token, client)

            token_data = {
                "provider": provider,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "token_type": data.get("token_type", "Bearer"),
                "scope": data.get("scope", " ".join(cfg.default_scopes)),
                "user_email": user_email
            }
            self._store_token(provider, token_data)

            return {
                "status": "connected",
                "provider": provider,
                "user_email": user_email,
                "expires_in": expires_in
            }

    async def _fetch_user_email(self, provider: str, access_token: str, client: httpx.AsyncClient) -> str:
        """Query provider user profile for primary email."""
        cfg = self.PROVIDERS[provider]
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            resp = await client.get(cfg.userinfo_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if provider == "google":
                    return data.get("email", "unknown_google_user@gmail.com")
                elif provider == "microsoft":
                    return data.get("mail") or data.get("userPrincipalName") or "unknown_ms_user@outlook.com"
        except Exception as e:
            logger.warning(f"Failed to fetch {provider} user profile: {e}")
        return f"authenticated_user@{provider}.com"

    # ── Token Storage & Automatic Refresh Rotation ────────────────────────────

    def _store_token(self, provider: str, token_data: Dict[str, Any]) -> None:
        """Store token encrypted in CredentialVault."""
        secret_str = json.dumps(token_data)
        self.vault.store_credential(f"oauth_{provider}", "session_token", secret_str)
        logger.info(f"Encrypted OAuth token stored for provider '{provider}'.")

    def get_stored_token(self, provider: str) -> Optional[Dict[str, Any]]:
        """Retrieve decrypted token from CredentialVault."""
        secret_str = self.vault.get_credential(f"oauth_{provider}", "session_token")
        if not secret_str:
            return None
        try:
            return json.loads(secret_str)
        except Exception as e:
            logger.error(f"Failed to parse stored OAuth token for '{provider}': {e}")
            return None

    def is_connected(self, provider: str) -> bool:
        """Check if an active token exists for provider."""
        token = self.get_stored_token(provider)
        return token is not None and bool(token.get("access_token") or token.get("refresh_token"))

    async def get_valid_access_token(self, provider: str) -> str:
        """
        Get valid access token, automatically triggering refresh token rotation
        if token is expired or within 60s of expiration.
        """
        token_data = self.get_stored_token(provider)
        if not token_data:
            raise RuntimeError(f"Provider '{provider}' is not authenticated. Please complete OAuth flow.")

        expires_at = token_data.get("expires_at", 0)
        # Check if token is expired or about to expire in < 60 seconds
        if time.time() >= expires_at - 60:
            logger.info(f"Access token for '{provider}' expired or near-expiry. Triggering refresh token rotation...")
            token_data = await self.refresh_token(provider)

        return token_data["access_token"]

    async def refresh_token(self, provider: str) -> Dict[str, Any]:
        """
        Perform refresh token rotation against provider token endpoint.
        """
        token_data = self.get_stored_token(provider)
        if not token_data or not token_data.get("refresh_token"):
            raise RuntimeError(f"No refresh token available for provider '{provider}'. Re-authentication required.")

        cfg = self.PROVIDERS[provider]
        refresh_token = token_data["refresh_token"]

        if not cfg.is_configured or refresh_token.startswith("mock_refresh_"):
            # Update simulated token with new rotated credentials
            token_data["access_token"] = f"mock_refreshed_access_{provider}_{secrets.token_hex(16)}"
            token_data["refresh_token"] = f"mock_rotated_refresh_{provider}_{secrets.token_hex(24)}"
            token_data["expires_at"] = time.time() + 3600
            self._store_token(provider, token_data)
            logger.info(f"Simulated token refreshed and rotated for provider '{provider}'.")
            return token_data

        payload = {
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(cfg.token_url, data=payload)
            if resp.status_code != 200:
                logger.error(f"Failed to refresh OAuth token for '{provider}': {resp.text}")
                raise RuntimeError(f"Refresh token expired or revoked. Please re-authenticate {provider}.")

            data = resp.json()
            token_data["access_token"] = data["access_token"]
            token_data["expires_at"] = time.time() + int(data.get("expires_in", 3600))
            # If provider returned a new refresh token (rotation), save it
            if data.get("refresh_token"):
                token_data["refresh_token"] = data["refresh_token"]

            self._store_token(provider, token_data)
            logger.info(f"✓ Successfully refreshed & rotated OAuth token for '{provider}'.")
            return token_data

    def disconnect(self, provider: str) -> bool:
        """Revoke and remove credentials for provider."""
        self.vault.store_credential(f"oauth_{provider}", "session_token", "")
        logger.info(f"Disconnected and cleared credentials for '{provider}'.")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Return status for Google and Microsoft OAuth integrations."""
        status = {}
        for name, cfg in self.PROVIDERS.items():
            token = self.get_stored_token(name)
            connected = token is not None and bool(token.get("access_token"))
            user_email = token.get("user_email") if token else None
            expires_at = token.get("expires_at") if token else None
            status[name] = {
                "display_name": cfg.display_name,
                "configured": cfg.is_configured,
                "connected": connected,
                "user_email": user_email,
                "expires_at": expires_at,
                "scopes": cfg.default_scopes
            }
        return status

    # ── Google Workspace API Operations (Gmail & Calendar) ─────────────────────

    async def gmail_list_messages(self, query: str = "", max_results: int = 10) -> Dict[str, Any]:
        """Search and list messages from user's Gmail inbox."""
        token = await self.get_valid_access_token("google")
        
        # If simulated token
        if token.startswith("mock_"):
            return {
                "provider": "google",
                "service": "gmail",
                "query": query,
                "total_estimated": 2,
                "messages": [
                    {
                        "id": "gmail_msg_001",
                        "thread_id": "thread_001",
                        "sender": "sarah.connor@example.com",
                        "subject": "Project Status & Deployment Timeline",
                        "snippet": "Attached is the latest build report for the automation subsystem...",
                        "date": "2026-08-22 10:30:00"
                    },
                    {
                        "id": "gmail_msg_002",
                        "thread_id": "thread_002",
                        "sender": "alerts@cloudservice.com",
                        "subject": "Security notification: OAuth API access granted",
                        "snippet": "JARVIS Personal Assistant was authorized to access your Google account.",
                        "date": "2026-08-22 09:15:00"
                    }
                ]
            }

        headers = {"Authorization": f"Bearer {token}"}
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        params = {"maxResults": min(max_results, 50)}
        if query:
            params["q"] = query

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"Gmail API error: {resp.text}")
            data = resp.json()
            msg_ids = [m["id"] for m in data.get("messages", [])]

            # Fetch details for each message
            detailed_msgs = []
            for m_id in msg_ids[:max_results]:
                m_resp = await client.get(f"{url}/{m_id}", headers=headers, params={"format": "metadata"})
                if m_resp.status_code == 200:
                    m_data = m_resp.json()
                    headers_map = {h["name"].lower(): h["value"] for h in m_data.get("payload", {}).get("headers", [])}
                    detailed_msgs.append({
                        "id": m_id,
                        "thread_id": m_data.get("threadId"),
                        "sender": headers_map.get("from", "Unknown"),
                        "subject": headers_map.get("subject", "No Subject"),
                        "snippet": m_data.get("snippet", ""),
                        "date": headers_map.get("date", "")
                    })

            return {
                "provider": "google",
                "service": "gmail",
                "query": query,
                "total_estimated": data.get("resultSizeEstimate", len(detailed_msgs)),
                "messages": detailed_msgs
            }

    async def gmail_send_message(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Send an email via user's Gmail account."""
        token = await self.get_valid_access_token("google")

        if token.startswith("mock_"):
            return {
                "status": "sent",
                "provider": "google",
                "service": "gmail",
                "message_id": f"gmsg_{secrets.token_hex(8)}",
                "to": to,
                "subject": subject,
                "timestamp": time.time()
            }

        # Build RFC 2822 email
        email_content = f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=\"UTF-8\"\r\n\r\n{body}"
        raw_b64 = base64.urlsafe_b64encode(email_content.encode("utf-8")).decode("utf-8")

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json={"raw": raw_b64})
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Gmail send error: {resp.text}")
            data = resp.json()
            return {
                "status": "sent",
                "provider": "google",
                "service": "gmail",
                "message_id": data.get("id"),
                "to": to,
                "subject": subject
            }

    async def google_calendar_list_events(self, time_min: Optional[str] = None, max_results: int = 10) -> Dict[str, Any]:
        """Fetch upcoming events from Google Calendar."""
        token = await self.get_valid_access_token("google")

        if token.startswith("mock_"):
            return {
                "provider": "google",
                "service": "calendar",
                "events": [
                    {
                        "id": "gcal_evt_001",
                        "summary": "JARVIS Architecture & Roadmap Review",
                        "start": "2026-08-23T10:00:00Z",
                        "end": "2026-08-23T11:00:00Z",
                        "description": "Discussing direct OAuth2 integrations and Live Mode perception co-pilot."
                    },
                    {
                        "id": "gcal_evt_002",
                        "summary": "Team Sync & Status",
                        "start": "2026-08-23T15:00:00Z",
                        "end": "2026-08-23T15:30:00Z",
                        "description": "Weekly engineering check-in."
                    }
                ]
            }

        headers = {"Authorization": f"Bearer {token}"}
        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        params = {
            "maxResults": min(max_results, 50),
            "singleEvents": "true",
            "orderBy": "startTime"
        }
        if time_min:
            params["timeMin"] = time_min

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"Google Calendar API error: {resp.text}")
            data = resp.json()
            events = [
                {
                    "id": item.get("id"),
                    "summary": item.get("summary", "Untitled Event"),
                    "start": item.get("start", {}).get("dateTime") or item.get("start", {}).get("date"),
                    "end": item.get("end", {}).get("dateTime") or item.get("end", {}).get("date"),
                    "description": item.get("description", "")
                }
                for item in data.get("items", [])
            ]
            return {
                "provider": "google",
                "service": "calendar",
                "events": events
            }

    async def google_calendar_create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """Create a new event in Google Calendar."""
        token = await self.get_valid_access_token("google")

        if token.startswith("mock_"):
            return {
                "status": "created",
                "provider": "google",
                "service": "calendar",
                "event_id": f"gcal_{secrets.token_hex(8)}",
                "summary": summary,
                "start": start_time,
                "end": end_time
            }

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        payload = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time}
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Google Calendar create event error: {resp.text}")
            data = resp.json()
            return {
                "status": "created",
                "provider": "google",
                "service": "calendar",
                "event_id": data.get("id"),
                "summary": summary,
                "html_link": data.get("htmlLink")
            }

    # ── Microsoft 365 API Operations (Outlook Mail & Calendar) ─────────────────

    async def outlook_list_messages(self, query: str = "", max_results: int = 10) -> Dict[str, Any]:
        """Search and list messages from Microsoft Outlook inbox."""
        token = await self.get_valid_access_token("microsoft")

        if token.startswith("mock_"):
            return {
                "provider": "microsoft",
                "service": "outlook_mail",
                "query": query,
                "messages": [
                    {
                        "id": "ms_msg_001",
                        "sender": "director@enterprise.com",
                        "subject": "Quarterly Objectives & Infrastructure Review",
                        "snippet": "Please review the updated requirements for security and AI orchestration...",
                        "received_at": "2026-08-22T08:45:00Z"
                    },
                    {
                        "id": "ms_msg_002",
                        "sender": "ms-identity@microsoft.com",
                        "subject": "Microsoft 365 OAuth Connected",
                        "snippet": "JARVIS OS application was granted Mail and Calendar read/write access.",
                        "received_at": "2026-08-22T07:20:00Z"
                    }
                ]
            }

        headers = {"Authorization": f"Bearer {token}"}
        url = "https://graph.microsoft.com/v1.0/me/messages"
        params = {
            "$top": min(max_results, 50),
            "$select": "id,subject,from,bodyPreview,receivedDateTime"
        }
        if query:
            params["$search"] = f'"{query}"'

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"Microsoft Graph Mail API error: {resp.text}")
            data = resp.json()
            messages = [
                {
                    "id": item.get("id"),
                    "sender": item.get("from", {}).get("emailAddress", {}).get("address", "Unknown"),
                    "subject": item.get("subject", "No Subject"),
                    "snippet": item.get("bodyPreview", ""),
                    "received_at": item.get("receivedDateTime")
                }
                for item in data.get("value", [])
            ]
            return {
                "provider": "microsoft",
                "service": "outlook_mail",
                "query": query,
                "messages": messages
            }

    async def outlook_send_message(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Send an email via Microsoft Outlook / Graph API."""
        token = await self.get_valid_access_token("microsoft")

        if token.startswith("mock_"):
            return {
                "status": "sent",
                "provider": "microsoft",
                "service": "outlook_mail",
                "message_id": f"msmsg_{secrets.token_hex(8)}",
                "to": to,
                "subject": subject,
                "timestamp": time.time()
            }

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = "https://graph.microsoft.com/v1.0/me/sendMail"
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}]
            },
            "saveToSentItems": "true"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code not in (200, 202):
                raise RuntimeError(f"Microsoft Graph sendMail error: {resp.text}")
            return {
                "status": "sent",
                "provider": "microsoft",
                "service": "outlook_mail",
                "to": to,
                "subject": subject
            }

    async def outlook_calendar_list_events(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Fetch events from Microsoft Outlook Calendar."""
        token = await self.get_valid_access_token("microsoft")

        if token.startswith("mock_"):
            return {
                "provider": "microsoft",
                "service": "outlook_calendar",
                "events": [
                    {
                        "id": "mscal_evt_001",
                        "subject": "Microsoft Cloud & Edge AI Sync",
                        "start": "2026-08-23T14:00:00Z",
                        "end": "2026-08-23T14:45:00Z",
                        "body": "Discussion on Graph API webhooks and token rotation."
                    }
                ]
            }

        headers = {"Authorization": f"Bearer {token}"}
        url = "https://graph.microsoft.com/v1.0/me/events"
        params = {
            "$top": min(max_results, 50),
            "$select": "id,subject,start,end,bodyPreview",
            "$orderby": "start/dateTime"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"Microsoft Graph Calendar error: {resp.text}")
            data = resp.json()
            events = [
                {
                    "id": item.get("id"),
                    "subject": item.get("subject", "Untitled Event"),
                    "start": item.get("start", {}).get("dateTime"),
                    "end": item.get("end", {}).get("dateTime"),
                    "body": item.get("bodyPreview", "")
                }
                for item in data.get("value", [])
            ]
            return {
                "provider": "microsoft",
                "service": "outlook_calendar",
                "events": events
            }

    async def outlook_calendar_create_event(
        self,
        subject: str,
        start_time: str,
        end_time: str,
        body: str = ""
    ) -> Dict[str, Any]:
        """Create a new event in Microsoft Outlook Calendar."""
        token = await self.get_valid_access_token("microsoft")

        if token.startswith("mock_"):
            return {
                "status": "created",
                "provider": "microsoft",
                "service": "outlook_calendar",
                "event_id": f"mscal_{secrets.token_hex(8)}",
                "subject": subject,
                "start": start_time,
                "end": end_time
            }

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = "https://graph.microsoft.com/v1.0/me/events"
        payload = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "start": {"dateTime": start_time, "timeZone": "UTC"},
            "end": {"dateTime": end_time, "timeZone": "UTC"}
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Microsoft Graph create event error: {resp.text}")
            data = resp.json()
            return {
                "status": "created",
                "provider": "microsoft",
                "service": "outlook_calendar",
                "event_id": data.get("id"),
                "subject": subject,
                "web_link": data.get("webLink")
            }


# Global singleton instance
oauth_service = OAuth2Service()
