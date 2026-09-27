"""
JARVIS AI OS — Telegram Remote Service & Security Verification Suite.
=====================================================================
Validates all 17 security, operational, and integration requirements:
 1. Authentication & user restriction (authorized user allowed)
 2. Rejection of unknown / unauthorized users (fail-closed, 0 execution)
 3. Token masking and credential protection (zero exposure in logs/reprs)
 4. Pairing mode with 6-digit PIN validation and .env persistence
 5. System status command telemetry formatting
 6. Tasks and progress inspection
 7. Workstation locking command
 8. Approved application control & shell injection rejection
 9. Desktop screenshot capture & photo formatting
10. Task cancellation through TaskQueue and interrupt
11. Routing natural language questions through existing PlannerAgent
12. Security approval generation with inline [Approve] / [Deny] buttons
13. Approval callback handling unblocking execution
14. Denial callback handling halting execution fail-closed
15. Notification debouncing & duplicate message suppression
16. ExperienceEngine trace recording tagged with source="telegram"
17. Network resilience, retry backoff, and exception handling
"""

import time
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from backend.config import get_settings
from backend.services.telegram_service import TelegramRemoteService
from backend.services.mobile_bridge import MobileBridgeService, ApprovalState
from backend.services.mobile_gateway import MobileGatewayService
from backend.services.manager import ServiceManager
from backend.models.schemas import WSMessage


@pytest.fixture
def clean_telegram_service():
    """Create isolated TelegramRemoteService with mocked network calls."""
    svc = TelegramRemoteService(
        bot_token="test_token_123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        chat_id="999888777",
        poll_interval_s=1
    )
    # Mock network call
    svc._call_api_async = AsyncMock(return_value={"ok": True, "result": {}})
    svc._send_photo = AsyncMock(return_value=True)
    return svc


# ── TEST 1: AUTHORIZED USER ACCESS ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_auth_allow_authorized_user(clean_telegram_service):
    """Verify that commands from authorized user are allowed and dispatched."""
    svc = clean_telegram_service
    sent_messages = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return True

    svc._send_message = mock_send

    msg = {
        "from": {"id": 999888777, "username": "admin_user"},
        "chat": {"id": 999888777},
        "text": "/status"
    }

    await svc._handle_message(msg)
    assert svc.total_commands_executed == 1
    assert svc.total_unauthorized_attempts == 0
    assert len(sent_messages) == 1
    assert "JARVIS Workstation Status" in sent_messages[0]["text"]


# ── TEST 2: REJECTION OF UNKNOWN USERS ──────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_auth_reject_unknown_user(clean_telegram_service):
    """Verify that messages from unknown users are strictly rejected with zero side-effects."""
    svc = clean_telegram_service
    sent_messages = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return True

    svc._send_message = mock_send

    unknown_msg = {
        "from": {"id": 111222333, "username": "attacker"},
        "chat": {"id": 111222333},
        "text": "/status"
    }

    await svc._handle_message(unknown_msg)
    assert svc.total_commands_executed == 0
    assert svc.total_unauthorized_attempts == 1
    assert len(sent_messages) == 1
    assert "Unauthorized Access Denied" in sent_messages[0]["text"]


# ── TEST 3: TOKEN NEVER LOGGED OR EXPOSED ───────────────────────────────────

def test_telegram_token_never_logged_or_exposed():
    """Verify that TELEGRAM_BOT_TOKEN is masked in repr and status outputs."""
    settings = get_settings()
    settings_repr = repr(settings)
    assert settings.TELEGRAM_BOT_TOKEN not in settings_repr or settings.TELEGRAM_BOT_TOKEN is None
    assert "******" in settings_repr

    svc = TelegramRemoteService(bot_token="secret_bot_token_abc123", chat_id="12345678")
    status = svc.get_service_status()
    assert "secret_bot_token_abc123" not in json.dumps(status)
    assert status["authorized_chat_id"] == "****5678"


# ── TEST 4: PAIRING FLOW & PIN VERIFICATION ─────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_pairing_flow_pin_verification():
    """Verify pairing mode when chat_id is empty, PIN matching, and rejection of wrong PIN."""
    svc = TelegramRemoteService(bot_token="test_token", chat_id="")
    sent_messages = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return True

    svc._send_message = mock_send
    svc._persist_chat_id = MagicMock()

    # Attempt without PIN
    await svc._handle_message({
        "from": {"id": 555666777, "username": "new_user"},
        "chat": {"id": 555666777},
        "text": "Hello"
    })
    assert "Unpaired" in sent_messages[-1]["text"]
    assert svc.chat_id == ""

    # Generate PIN
    pin = svc.generate_pairing_pin(timeout_seconds=60)
    assert len(pin) == 6

    # Attempt with wrong PIN
    await svc._handle_message({
        "from": {"id": 555666777, "username": "new_user"},
        "chat": {"id": 555666777},
        "text": "/pair 000000"
    })
    assert "Invalid or Expired Pairing PIN" in sent_messages[-1]["text"]
    assert svc.chat_id == ""

    # Attempt with correct PIN
    await svc._handle_message({
        "from": {"id": 555666777, "username": "new_user", "first_name": "Ashrit"},
        "chat": {"id": 555666777},
        "text": f"/pair {pin}"
    })
    assert svc.chat_id == "555666777"
    assert "Successfully Paired" in sent_messages[-1]["text"]
    svc._persist_chat_id.assert_called_with("555666777")


# ── TEST 5: SYSTEM STATUS COMMAND ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_status_command(clean_telegram_service):
    """Verify /status command queries telemetry and formats markdown."""
    svc = clean_telegram_service
    sent_messages = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return True

    svc._send_message = mock_send
    await svc._handle_status_command("999888777")

    assert len(sent_messages) == 1
    assert "CPU Usage" in sent_messages[0]["text"]
    assert "RAM Usage" in sent_messages[0]["text"]
    assert "Active Model" in sent_messages[0]["text"]


# ── TEST 6: TASKS AND PROGRESS COMMAND ──────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_tasks_and_progress_command(clean_telegram_service):
    """Verify /tasks and /progress format queue items and percentages."""
    svc = clean_telegram_service
    sent_messages = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return True

    svc._send_message = mock_send

    # Test idle tasks
    await svc._handle_tasks_command("999888777")
    assert "No pending or running tasks" in sent_messages[-1]["text"]

    # Test running tasks
    mock_tq = MagicMock()
    mock_tq.tasks = [
        {"name": "Summarize codebase", "status": "running", "progress": 45, "current_step": "Analyzing AST"}
    ]
    ServiceManager.register_instance("task_queue_service", mock_tq)

    await svc._handle_tasks_command("999888777")
    assert "Summarize codebase" in sent_messages[-1]["text"]
    assert "45%" in sent_messages[-1]["text"]

    await svc._handle_progress_command("999888777")
    assert "Analyzing AST" in sent_messages[-1]["text"]


# ── TEST 7: LOCK WORKSTATION COMMAND ────────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_lock_workstation_command(clean_telegram_service):
    """Verify /lock command invokes workstation lock."""
    svc = clean_telegram_service
    sent_messages = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return True

    svc._send_message = mock_send

    with patch("subprocess.Popen") as mock_popen:
        await svc._handle_lock_command("999888777")
        mock_popen.assert_called_once_with(["rundll32.exe", "user32.dll,LockWorkStation"], shell=False)

    assert "Workstation Locked" in sent_messages[0]["text"]


# ── TEST 8: APPROVED APPLICATION CONTROL ────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_approved_app_control(clean_telegram_service):
    """Verify /app launches application and rejects shell injection attempts."""
    svc = clean_telegram_service
    sent_messages = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return True

    svc._send_message = mock_send

    # 1. Shell injection rejection
    await svc._handle_app_launch("999888777", "notepad; rm -rf /")
    assert "shell operators are strictly prohibited" in sent_messages[-1]["text"]

    # 2. Approved launch
    with patch("backend.services.automation.AutomationService.open_application", new_callable=AsyncMock) as mock_app:
        mock_app.return_value = {"success": True, "app": "notepad"}
        await svc._handle_app_launch("999888777", "notepad")
        assert "Launched Application" in sent_messages[-1]["text"]


# ── TEST 9: SCREENSHOT CAPTURE AND TRANSMISSION ─────────────────────────────

@pytest.mark.asyncio
async def test_telegram_screenshot_capture_and_send(clean_telegram_service):
    """Verify /screenshot triggers preview capture and dispatches photo."""
    svc = clean_telegram_service
    sent_photos = []

    async def mock_photo(chat_id, photo_bytes, caption=""):
        sent_photos.append({"chat_id": chat_id, "len": len(photo_bytes), "caption": caption})
        return True

    svc._send_photo = mock_photo

    mock_gw = MagicMock()
    mock_preview = MagicMock()
    mock_preview.image_base64 = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    mock_preview.active_window_title = "JARVIS Visual HUD"
    mock_gw.capture_screen_preview.return_value = mock_preview
    ServiceManager.register_instance("mobile_gateway_service", mock_gw)

    await svc._handle_screenshot_command("999888777")
    assert len(sent_photos) == 1
    assert sent_photos[0]["chat_id"] == "999888777"
    assert "Workstation Screen Snapshot" in sent_photos[0]["caption"]


# ── TEST 10: TASK CANCELLATION ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_task_cancellation(clean_telegram_service):
    """Verify /cancel command clears TaskQueue and interrupts voice/planner."""
    svc = clean_telegram_service
    sent_messages = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return True

    svc._send_message = mock_send

    mock_tq = MagicMock()
    ServiceManager.register_instance("task_queue_service", mock_tq)

    await svc._dispatch_authorized_command("999888777", "/cancel")
    assert mock_tq.clear.called
    assert "Task Execution Cancelled" in sent_messages[-1]["text"]


# ── TEST 11: NATURAL LANGUAGE ROUTED THROUGH PLANNER ────────────────────────

@pytest.mark.asyncio
async def test_telegram_question_routes_through_planner(clean_telegram_service):
    """Verify arbitrary questions route through existing VoiceManager/Planner."""
    svc = clean_telegram_service
    sent_messages = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        sent_messages.append({"chat_id": chat_id, "text": text})
        return True

    svc._send_message = mock_send

    async def mock_cmd_gen(text):
        yield WSMessage(type="response", data={"text": "Sir, all 11 OS capabilities are running at 100% capacity."})

    mock_vm = MagicMock()
    mock_vm.handle_text_command = mock_cmd_gen
    ServiceManager.register_instance("voice_manager", mock_vm)

    await svc._dispatch_authorized_command("999888777", "What is the system status?")
    assert any("all 11 OS capabilities" in m["text"] for m in sent_messages)


# ── TEST 12: APPROVAL INLINE KEYBOARD GENERATION ────────────────────────────

@pytest.mark.asyncio
async def test_telegram_approval_system_inline_keyboard(clean_telegram_service):
    """Verify request_approval_notification creates inline [Approve] / [Deny] buttons."""
    svc = clean_telegram_service
    captured = []

    async def mock_send(chat_id, text, inline_keyboard=None):
        captured.append({"text": text, "keyboard": inline_keyboard})
        return True

    svc._send_message = mock_send

    ok = await svc.request_approval_notification(
        action_id="act_4567",
        action_type="terminal_command",
        description="Run npm audit fix",
        dangerous_target="Host Terminal",
        timeout_seconds=30.0
    )

    assert ok is True
    assert len(captured) == 1
    kb = captured[0]["keyboard"]
    assert kb[0][0]["callback_data"] == "approve_act_4567"
    assert kb[0][1]["callback_data"] == "deny_act_4567"


# ── TEST 13: APPROVAL CALLBACK UNBLOCKS EXECUTION ───────────────────────────

@pytest.mark.asyncio
async def test_telegram_approval_callback_resolution(clean_telegram_service):
    """Verify tapping [Approve] in Telegram unblocks MobileBridge / MobileGateway."""
    svc = clean_telegram_service
    svc._answer_callback = AsyncMock()
    svc._edit_message_text = AsyncMock()

    bridge = MobileBridgeService()
    bridge.submit_telegram_decision = MagicMock(return_value=True)
    ServiceManager.register_instance("mobile_bridge", bridge)

    gateway = MobileGatewayService()
    gateway.submit_approval_decision = MagicMock(return_value=True)
    ServiceManager.register_instance("mobile_gateway_service", gateway)

    query = {
        "id": "query_999",
        "from": {"id": 999888777},
        "data": "approve_appr_1001",
        "message": {"chat": {"id": 999888777}, "message_id": 42, "text": "Authorize action?"}
    }

    await svc._handle_callback_query(query)
    bridge.submit_telegram_decision.assert_called_with("appr_1001", "approve")
    gateway.submit_approval_decision.assert_called_with("appr_1001", "approve")
    assert svc._edit_message_text.called


# ── TEST 14: DENIAL CALLBACK HALTS FAIL-CLOSED ──────────────────────────────

@pytest.mark.asyncio
async def test_telegram_approval_denial_fail_closed(clean_telegram_service):
    """Verify tapping [Deny] in Telegram marks action denied fail-closed."""
    svc = clean_telegram_service
    svc._answer_callback = AsyncMock()
    svc._edit_message_text = AsyncMock()

    bridge = MobileBridgeService()
    bridge.submit_telegram_decision = MagicMock(return_value=True)
    ServiceManager.register_instance("mobile_bridge", bridge)

    gateway = MobileGatewayService()
    gateway.submit_approval_decision = MagicMock(return_value=True)
    ServiceManager.register_instance("mobile_gateway_service", gateway)

    query = {
        "id": "query_1000",
        "from": {"id": 999888777},
        "data": "deny_appr_1002",
        "message": {"chat": {"id": 999888777}, "message_id": 43, "text": "Authorize action?"}
    }

    await svc._handle_callback_query(query)
    bridge.submit_telegram_decision.assert_called_with("appr_1002", "deny")
    gateway.submit_approval_decision.assert_called_with("appr_1002", "deny")


# ── TEST 15: NOTIFICATION DEBOUNCING & RATE LIMITING ────────────────────────

@pytest.mark.asyncio
async def test_telegram_notification_debouncing(clean_telegram_service):
    """Verify duplicate notification suppression and rate-limiting gap."""
    svc = clean_telegram_service
    sent_count = 0

    async def mock_send(chat_id, text, inline_keyboard=None):
        nonlocal sent_count
        sent_count += 1
        return True

    svc._send_message = mock_send
    svc._min_send_interval_s = 0.05  # Shorten for fast test

    # Send identical notification twice immediately
    ok1 = await svc.send_notification("Alert Title", "Same alert body", "info")
    ok2 = await svc.send_notification("Alert Title", "Same alert body", "info")

    assert ok1 is True
    assert ok2 is True
    # The duplicate should have been suppressed
    assert sent_count == 1


# ── TEST 16: EXPERIENCE & LEARNING TRACE TAGGING ────────────────────────────

@pytest.mark.asyncio
async def test_telegram_experience_and_learning_tagging(clean_telegram_service):
    """Verify that commands executed via Telegram record experience trace with [Telegram] tag."""
    svc = clean_telegram_service
    svc._send_message = AsyncMock(return_value=True)

    mock_exp = MagicMock()
    ServiceManager.register_instance("experience_engine", mock_exp)

    async def mock_cmd(text):
        yield WSMessage(type="response", data={"text": "Task finished."})

    mock_vm = MagicMock()
    mock_vm.handle_text_command = mock_cmd
    ServiceManager.register_instance("voice_manager", mock_vm)

    await svc._handle_natural_language_command("999888777", "Analyze log files")
    assert mock_exp.record_experience.called
    kwargs = mock_exp.record_experience.call_args[1]
    assert "[Telegram]" in kwargs["goal"]
    assert kwargs["success"] is True


# ── TEST 17: NETWORK RESILIENCE AND RECONNECT ───────────────────────────────

@pytest.mark.asyncio
async def test_telegram_network_resilience_and_reconnect(clean_telegram_service):
    """Verify polling loop handles network disconnects gracefully without crashing."""
    svc = clean_telegram_service
    attempts = 0

    async def mock_api(endpoint, payload=None, timeout=10.0):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionResetError("Connection dropped by peer")
        elif attempts == 2:
            return {"ok": False, "error_code": 502, "description": "Bad Gateway"}
        else:
            svc._is_running = False
            return {"ok": True, "result": []}

    svc._call_api_async = mock_api
    svc.poll_interval_s = 0.01
    svc._is_running = True

    # Run polling loop briefly
    await svc._polling_loop()
    assert attempts >= 3
    assert svc._is_running is False
