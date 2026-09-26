"""
JARVIS AI Operating System - Phase 7: Browser Automation Reliability & Security Hardening Tests.
================================================================================================
Adversarial test suite validating:
- URL scheme and SSRF protection (blocking javascript:, data:, file:, localhost, private IPs, AWS metadata)
- Domain trust verification and cross-domain redirect blocking
- Substring domain bypass rejection (attacker-example.com vs example.com)
- Credential masking for passwords/tokens in form inputs
- Target element ambiguity rejection for sensitive actions
- CAPTCHA / Cloudflare Turnstile challenge detection and safe pause
- Browser context session isolation
- Fail-closed security boundaries and invariants for web automation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.automation.browser_executor import (
    BrowserExecutor,
    validate_browser_url,
    is_matching_domain,
)


# ── 1. URL Scheme & SSRF Protection ──────────────────────────────────────────

def test_url_validation_blocks_dangerous_schemes():
    """
    javascript:, data:, file:, and vbscript: URL schemes must be blocked.
    """
    bad_urls = [
        "javascript:alert(document.cookie)",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        "file:///C:/Windows/System32/drivers/etc/hosts",
        "vbscript:msgbox(1)",
    ]
    for url in bad_urls:
        is_valid, msg = validate_browser_url(url)
        assert not is_valid
        assert "Disallowed URL scheme" in msg or "Security Policy Blocked" in msg


def test_url_validation_blocks_ssrf_and_private_ips():
    """
    Loopback, internal private subnets, and cloud metadata endpoints must be blocked.
    """
    private_targets = [
        "http://localhost:8080/admin",
        "http://127.0.0.1:8000/internal",
        "http://10.0.0.5/api",
        "http://192.168.1.100/router",
        "http://172.16.0.1/dashboard",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/internal",
    ]
    for url in private_targets:
        is_valid, msg = validate_browser_url(url, allow_local=False)
        assert not is_valid
        assert "SSRF protection blocked" in msg or "metadata" in msg or "Security Policy Blocked" in msg


def test_url_validation_allows_valid_public_urls():
    """
    Standard public HTTPS/HTTP domains must be validated successfully.
    """
    valid_urls = [
        "https://github.com",
        "https://en.wikipedia.org/wiki/Main_Page",
        "http://example.com/test?q=hello",
        "google.com",
    ]
    for url in valid_urls:
        is_valid, clean_url = validate_browser_url(url)
        assert is_valid
        assert clean_url.startswith("http")


# ── 2. Domain Trust Model & Subdomain Matching ───────────────────────────────

def test_domain_matching_rejects_substring_exploits():
    """
    Domain matching must use canonical hostname parsing, rejecting substring spoofing.
    """
    expected = "example.com"

    # Valid matches
    assert is_matching_domain("https://example.com/path", expected)
    assert is_matching_domain("https://sub.example.com/path", expected)
    assert is_matching_domain("https://login.api.example.com", expected)

    # Malicious substring attempts (MUST BE REJECTED)
    assert not is_matching_domain("https://attacker-example.com/login", expected)
    assert not is_matching_domain("https://example.com.attacker.com/login", expected)
    assert not is_matching_domain("https://notexample.com", expected)
    assert not is_matching_domain("https://fakeexample.com", expected)


# ── 3. Cross-Domain Redirect & Navigation Hardening ──────────────────────────

@pytest.mark.asyncio
async def test_unexpected_cross_domain_redirect_blocked():
    """
    If a navigation redirects away from the expected domain, open_url must report a redirect block.
    """
    executor = BrowserExecutor()
    mock_page = AsyncMock()
    mock_page.url = "https://evil-phishing.com/login"
    mock_page.title = AsyncMock(return_value="Phishing Page")
    executor._page = mock_page
    executor._started = True

    with patch.object(executor, "_ensure_started", new_callable=AsyncMock):
        res = await executor.open_url("https://trusted-service.com", expected_domain="trusted-service.com")
        assert "Redirect Blocked" in res
        assert "evil-phishing.com" in res


# ── 4. Credential Masking in Form Inputs ─────────────────────────────────────

@pytest.mark.asyncio
async def test_credential_masking_in_fill_input():
    """
    Passwords, API keys, tokens, and sensitive inputs must be masked in logs and returned messages.
    """
    executor = BrowserExecutor()
    mock_page = AsyncMock()
    mock_page.url = "https://accounts.google.com"
    executor._page = mock_page
    executor._started = True

    with patch.object(executor, "_ensure_started", new_callable=AsyncMock):
        # 1. Password field
        res = await executor.fill_input("input#password", "SuperSecretPassword123!", expected_domain="google.com")
        assert "SuperSecretPassword123!" not in res
        assert "******" in res
        assert "masked" in res

        # 2. Domain mismatch on sensitive form
        res_mismatch = await executor.fill_input("input#password", "Secret123", expected_domain="paypal.com")
        assert "Domain Mismatch Blocked" in res_mismatch


# ── 5. Target Ambiguity Rejection for Sensitive Actions ──────────────────────

@pytest.mark.asyncio
async def test_ambiguous_selector_blocked_for_sensitive_actions():
    """
    If multiple elements match a sensitive selector (e.g. 3 'Submit Payment' buttons),
    the action must be blocked rather than clicking an arbitrary element.
    """
    executor = BrowserExecutor()
    mock_page = MagicMock()
    mock_page.url = "https://bank.com/transfer"
    
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=3)  # 3 matching buttons
    mock_page.locator.return_value = mock_locator

    executor._page = mock_page
    executor._started = True

    with patch.object(executor, "_ensure_started", new_callable=AsyncMock):
        res = await executor.click_element("button.confirm-transfer", expected_domain="bank.com", is_sensitive=True)
        assert "Target Ambiguity Blocked" in res
        assert "Multiple elements (3)" in res


# ── 6. CAPTCHA / Cloudflare Challenge Detection ──────────────────────────────

@pytest.mark.asyncio
async def test_captcha_detection_triggers_safe_pause():
    """
    When CAPTCHA or Cloudflare challenge is present, BrowserExecutor must detect it and safely pause.
    """
    executor = BrowserExecutor()
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=True)  # Simulates challenge detection in DOM
    executor._page = mock_page

    has_challenge, msg = await executor.detect_captcha_or_challenge()
    assert has_challenge is True
    assert "CAPTCHA / Security Challenge detected" in msg


# ── 7. Browser Session & Context Isolation ───────────────────────────────────

@pytest.mark.asyncio
async def test_session_isolation_creates_distinct_contexts():
    """
    create_isolated_context must spawn independent browser contexts to avoid cross-tenant session leaks.
    """
    executor = BrowserExecutor()
    mock_browser = AsyncMock()
    mock_context_a = MagicMock()
    mock_context_b = MagicMock()
    mock_browser.new_context.side_effect = [mock_context_a, mock_context_b]
    
    executor._browser = mock_browser
    executor._started = True

    with patch.object(executor, "_ensure_started", new_callable=AsyncMock):
        ctx1 = await executor.create_isolated_context()
        ctx2 = await executor.create_isolated_context()
        assert ctx1 is not ctx2
        assert mock_browser.new_context.call_count == 2
