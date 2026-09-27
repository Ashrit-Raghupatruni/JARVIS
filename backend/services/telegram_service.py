"""
JARVIS AI Operating System - Telegram Remote Control & Push Notification Service.

Provides an authenticated, fail-closed remote control channel and real-time push notification
bridge via Telegram Bot API. Integrates directly into the existing JARVIS execution pipeline
(PlannerAgent, ToolRegistry, SafetyGatekeeper, TaskQueue, ExperienceEngine) with zero duplicate architecture.
"""

import os
import io
import re
import time
import json
import base64
import asyncio
import secrets
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from backend.config import get_settings


class TelegramRemoteService:
    """Secure Telegram Remote Control, Approval Gatekeeper, and Notification Gateway."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        poll_interval_s: int = 20
    ) -> None:
        settings = get_settings()
        self.bot_token = bot_token or getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        self.chat_id = str(chat_id or getattr(settings, "TELEGRAM_CHAT_ID", "") or "").strip()
        self.enabled = getattr(settings, "TELEGRAM_ENABLED", True) and bool(self.bot_token)
        self.poll_interval_s = poll_interval_s or getattr(settings, "TELEGRAM_POLL_INTERVAL_S", 20)

        self._is_running: bool = False
        self._polling_task: Optional[asyncio.Task] = None
        self._last_update_id: int = 0
        self._bot_username: Optional[str] = None
        self._bot_id: Optional[int] = None

        # Pairing Mode State (when chat_id is not yet set)
        self.pairing_pin: Optional[str] = None
        self.pairing_pin_expires_at: float = 0.0

        # Debounce and Rate Limiting
        self._last_notification_time: float = 0.0
        self._last_sent_hash: Optional[str] = None
        self._last_sent_hash_time: float = 0.0
        self._min_send_interval_s: float = 2.0
        self._send_lock = asyncio.Lock()

        # Telemetry & Status
        self.last_activity_time: float = 0.0
        self.total_commands_executed: int = 0
        self.total_unauthorized_attempts: int = 0

        logger.info(
            "TelegramRemoteService initialized (Enabled={}, ChatIDConfigured={})",
            self.enabled,
            bool(self.chat_id)
        )

    # ── LIFECYCLE MANAGEMENT ───────────────────────────────────────────────

    async def start(self) -> bool:
        """Start the background polling loop and fetch bot identity."""
        if not self.enabled or not self.bot_token:
            logger.info("TelegramRemoteService disabled or token missing; skipping startup.")
            return False

        if self._is_running:
            return True

        # Fetch bot identity via getMe
        bot_info = await self._call_api_async("getMe")
        if not bot_info or not bot_info.get("ok"):
            logger.warning("[SECURITY] Failed to verify Telegram Bot token via getMe. Remote listener disabled.")
            return False

        res = bot_info.get("result", {})
        self._bot_id = res.get("id")
        self._bot_username = res.get("username")
        logger.info("✓ Telegram Bot verified: @{} (ID: {})", self._bot_username, self._bot_id)

        # Clear any dangling webhook to avoid getUpdates conflicts
        await self._call_api_async("deleteWebhook", {"drop_pending_updates": False})

        self._is_running = True
        self._polling_task = asyncio.create_task(self._polling_loop())
        logger.info("✓ Telegram remote control background polling loop online.")
        return True

    async def stop(self) -> None:
        """Stop background polling listener."""
        self._is_running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
        logger.info("TelegramRemoteService stopped.")

    # ── POLLING LOOP & DISPATCH ────────────────────────────────────────────

    async def _polling_loop(self) -> None:
        """Continuous long-polling loop with exponential backoff on network failure."""
        backoff_delay = 1.0

        while self._is_running:
            try:
                params = {
                    "offset": self._last_update_id + 1 if self._last_update_id > 0 else 0,
                    "timeout": self.poll_interval_s,
                    "allowed_updates": ["message", "callback_query"]
                }
                
                resp = await self._call_api_async("getUpdates", params, timeout=self.poll_interval_s + 5)
                if not resp or not resp.get("ok"):
                    backoff_delay = min(backoff_delay * 1.5, 30.0)
                    await asyncio.sleep(backoff_delay)
                    continue

                backoff_delay = 1.0  # Reset on successful network request
                updates = resp.get("result", [])

                for update in updates:
                    update_id = update.get("update_id", 0)
                    if update_id > self._last_update_id:
                        self._last_update_id = update_id

                    try:
                        await self._process_update(update)
                    except Exception as upd_err:
                        logger.error("Error processing Telegram update {}: {}", update_id, upd_err)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Telegram polling network notice: {}. Retrying in {:.1f}s...", e, backoff_delay)
                await asyncio.sleep(backoff_delay)
                backoff_delay = min(backoff_delay * 2.0, 30.0)

    async def _process_update(self, update: Dict[str, Any]) -> None:
        """Process an individual update (message or callback_query)."""
        if "callback_query" in update:
            await self._handle_callback_query(update["callback_query"])
            return

        if "message" in update:
            await self._handle_message(update["message"])

    # ── AUTHENTICATION & PAIRING GATE ──────────────────────────────────────

    def _is_user_authorized(self, user_id: str) -> bool:
        """Constant-time comparison check for authorized Telegram user."""
        if not self.chat_id:
            return False
        return secrets.compare_digest(str(user_id).strip(), self.chat_id)

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Process incoming user text message with strict authentication gate."""
        from_user = message.get("from", {})
        user_id = str(from_user.get("id", ""))
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = str(message.get("text", "")).strip()

        if not user_id or not text:
            return

        self.last_activity_time = time.time()

        # 1. Pairing Mode Flow (when chat_id is not yet set)
        if not self.chat_id:
            if text.startswith(("/pair", "/start")):
                parts = text.split(maxsplit=1)
                pin_attempt = parts[1].strip() if len(parts) > 1 else ""
                
                if (
                    self.pairing_pin
                    and pin_attempt
                    and time.time() < self.pairing_pin_expires_at
                    and secrets.compare_digest(pin_attempt, self.pairing_pin)
                ):
                    self.chat_id = user_id
                    self._persist_chat_id(user_id)
                    self.pairing_pin = None
                    self.pairing_pin_expires_at = 0.0
                    logger.info("✓ [SECURITY] Successfully paired Telegram user {} (@{}) to JARVIS!", user_id, from_user.get("username"))
                    await self._send_message(
                        chat_id,
                        f"✅ *Workstation Successfully Paired!*\n\n"
                        f"Welcome, {from_user.get('first_name', 'Sir')}. You are now the authorized administrator of JARVIS.\n\n"
                        f"Type /help to see all available remote capabilities."
                    )
                    return
                else:
                    await self._send_message(
                        chat_id,
                        "❌ *Invalid or Expired Pairing PIN*\n\n"
                        "Please check the pairing PIN displayed on your JARVIS desktop settings and send:\n`/pair <6-digit-pin>`"
                    )
                    return
            else:
                await self._send_message(
                    chat_id,
                    "🔒 *JARVIS Workstation Unpaired*\n\n"
                    "This JARVIS instance is currently awaiting pairing. Generate a pairing PIN on your desktop HUD and send:\n`/pair <PIN>`"
                )
                return

        # 2. Strict Authentication Gate for Configured Chat ID
        if not self._is_user_authorized(user_id):
            self.total_unauthorized_attempts += 1
            logger.warning(
                "⛔ [SECURITY ALERT] Unauthorized Telegram command attempt from user_id: {} (@{}) | Content: '{}'",
                user_id,
                from_user.get("username", "unknown"),
                text[:30]
            )
            await self._send_message(
                chat_id,
                "⛔ *Unauthorized Access Denied*\n\n"
                "This JARVIS instance is private and restricted strictly to its authorized owner."
            )
            return

        # 3. Authorized Execution
        self.total_commands_executed += 1
        await self._dispatch_authorized_command(chat_id, text)

    def _persist_chat_id(self, chat_id: str) -> None:
        """Persist newly paired Telegram chat ID to .env file safely."""
        env_path = Path(".env")
        if not env_path.exists():
            return

        try:
            content = env_path.read_text(encoding="utf-8")
            if "TELEGRAM_CHAT_ID=" in content:
                content = re.sub(r"TELEGRAM_CHAT_ID=.*", f"TELEGRAM_CHAT_ID={chat_id}", content)
            else:
                content += f"\nTELEGRAM_CHAT_ID={chat_id}\n"
            env_path.write_text(content, encoding="utf-8")
            logger.info("✓ Updated .env with TELEGRAM_CHAT_ID={}", chat_id)
        except Exception as e:
            logger.warning("Failed to persist TELEGRAM_CHAT_ID to .env: {}", e)

    def generate_pairing_pin(self, timeout_seconds: float = 300.0) -> str:
        """Generate a 6-digit numeric pairing PIN valid for 5 minutes."""
        pin = f"{secrets.randbelow(900000) + 100000}"
        self.pairing_pin = pin
        self.pairing_pin_expires_at = time.time() + timeout_seconds
        logger.info("Generated new Telegram pairing PIN: {} (expires in {:.0f}s)", pin, timeout_seconds)
        return pin

    # ── APPROVAL CALLBACK HANDLING ─────────────────────────────────────────

    async def _handle_callback_query(self, query: Dict[str, Any]) -> None:
        """Process inline button tap from user ([Approve], [Deny], [Retry], [Cancel])."""
        query_id = query.get("id")
        from_user = query.get("from", {})
        user_id = str(from_user.get("id", ""))
        data = str(query.get("data", ""))
        message = query.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        message_id = message.get("message_id")

        # Strict auth check
        if not self._is_user_authorized(user_id):
            logger.warning("⛔ [SECURITY ALERT] Unauthorized callback query from user: {}", user_id)
            await self._answer_callback(query_id, "Unauthorized: Access Denied", show_alert=True)
            return

        # Acknowledge button press immediately so client UI stops spinning
        await self._answer_callback(query_id, "Decision received")

        logger.info("Processing Telegram approval callback: '{}'", data)

        decision_text = ""
        decision_applied = False

        if data.startswith("approve_"):
            action_id = data.replace("approve_", "")
            decision_applied = self._resolve_approval(action_id, "approve")
            decision_text = "✅ *Approved by Administrator via Telegram*"
        elif data.startswith("deny_"):
            action_id = data.replace("deny_", "")
            decision_applied = self._resolve_approval(action_id, "deny")
            decision_text = "❌ *Denied by Administrator via Telegram*"
        elif data.startswith("cancel_"):
            task_id = data.replace("cancel_", "")
            self._cancel_task(task_id)
            decision_text = "⏹️ *Task Cancelled via Telegram*"
            decision_applied = True
        elif data.startswith("retry_"):
            task_id = data.replace("retry_", "")
            decision_text = "🔄 *Retry requested via Telegram*"
            decision_applied = True

        if message_id and decision_text:
            orig_text = message.get("text", "")
            updated_text = f"{orig_text}\n\n━━━━━━━━━━━━━━━━━━━━\n{decision_text}"
            await self._edit_message_text(chat_id, message_id, updated_text)

    def _resolve_approval(self, action_id: str, decision: str) -> bool:
        """Resolve pending approval across MobileBridge and MobileGateway."""
        from backend.services.manager import ServiceManager
        resolved = False

        # 1. Resolve via MobileBridgeService
        bridge = ServiceManager.get_instance("mobile_bridge")
        if bridge and hasattr(bridge, "submit_telegram_decision"):
            bridge.submit_telegram_decision(action_id, decision)
            resolved = True

        # 2. Resolve via MobileGatewayService
        gateway = ServiceManager.get_instance("mobile_gateway_service")
        if gateway and hasattr(gateway, "submit_approval_decision"):
            gateway.submit_approval_decision(action_id, decision)
            resolved = True

        return resolved

    def _cancel_task(self, task_id: Optional[str] = None) -> bool:
        """Cancel running task in TaskQueue and interrupt VoiceManager."""
        from backend.services.manager import ServiceManager
        cancelled = False

        # 1. Interrupt VoiceManager / Planner
        vm = ServiceManager.get_instance("voice_manager")
        if vm and hasattr(vm, "handle_interrupt"):
            asyncio.create_task(vm.handle_interrupt().__anext__())
            cancelled = True

        # 2. TaskQueue cancellation
        tq = ServiceManager.get_instance("task_queue_service")
        if tq:
            if task_id and hasattr(tq, "cancel_task"):
                tq.cancel_task(task_id)
                cancelled = True
            elif hasattr(tq, "clear"):
                tq.clear()
                cancelled = True

        return cancelled

    # ── COMMAND DISPATCH & EXECUTION ───────────────────────────────────────

    async def _dispatch_authorized_command(self, chat_id: str, text: str) -> None:
        """Execute authorized command through the existing JARVIS pipeline."""
        clean_text = text.strip()
        lower_text = clean_text.lower()

        # 1. /status or "system status"
        if lower_text in ("/status", "/telemetry", "system status", "status", "diagnostics"):
            await self._handle_status_command(chat_id)
            return

        # 2. /tasks or "running tasks"
        if lower_text in ("/tasks", "running tasks", "tasks", "task list"):
            await self._handle_tasks_command(chat_id)
            return

        # 3. /progress or "task progress"
        if lower_text in ("/progress", "task progress", "progress"):
            await self._handle_progress_command(chat_id)
            return

        # 4. /lock or "lock workstation"
        if lower_text in ("/lock", "lock workstation", "lock screen", "lock"):
            await self._handle_lock_command(chat_id)
            return

        # 5. /screenshot or "screenshot"
        if lower_text in ("/screenshot", "/screen", "screenshot", "take a screenshot", "screen snapshot"):
            await self._handle_screenshot_command(chat_id)
            return

        # 6. /cancel or "cancel task"
        if lower_text.startswith(("/cancel", "cancel task", "stop task", "abort")):
            self._cancel_task()
            await self._send_message(chat_id, "⏹️ *Task Execution Cancelled*\n\nActive pipeline tasks halted and buffers reset.")
            return

        # 7. /app <name> (Approved application launch)
        if lower_text.startswith("/app "):
            app_name = clean_text[5:].strip()
            await self._handle_app_launch(chat_id, app_name)
            return

        # 8. /help
        if lower_text in ("/help", "/start", "help"):
            await self._handle_help_command(chat_id)
            return

        # 9. Natural Language Question or Workflow -> Route through existing Unified Pipeline
        await self._handle_natural_language_command(chat_id, clean_text)

    async def _handle_status_command(self, chat_id: str) -> None:
        """Fetch and return real-time workstation telemetry."""
        from backend.services.manager import ServiceManager
        gateway = ServiceManager.get_instance("mobile_gateway_service")
        
        if not gateway:
            from backend.services.mobile_gateway import MobileGatewayService
            gateway = MobileGatewayService()

        tel = gateway.get_system_telemetry()
        
        status_msg = (
            "🖥️ *JARVIS Workstation Status*\n\n"
            f"• *CPU Usage:* `{tel.cpu_percent:.1f}%`\n"
            f"• *RAM Usage:* `{tel.ram_percent:.1f}%` ({tel.ram_used_gb:.1f} GB / {tel.ram_total_gb:.1f} GB)\n"
            f"• *Active Model:* `{getattr(tel, 'active_llm_provider', 'Ollama Local')}`\n"
            f"• *Workstation State:* `Online & Monitored`\n"
            f"• *Telegram Bridge:* `Securely Connected`\n"
            f"• *Commands Processed:* `{self.total_commands_executed}`\n"
            f"• *Timestamp:* `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(tel.timestamp))}`"
        )
        await self._send_message(chat_id, status_msg)

    async def _handle_tasks_command(self, chat_id: str) -> None:
        """Fetch current TaskQueue status."""
        from backend.services.manager import ServiceManager
        tq = ServiceManager.get_instance("task_queue_service")
        
        tasks = getattr(tq, "tasks", []) if tq else []
        if not tasks:
            await self._send_message(chat_id, "📋 *Task Queue Status*\n\nNo pending or running tasks. Systems idle.")
            return

        lines = ["📋 *Active & Queued Tasks:*\n"]
        for idx, t in enumerate(tasks[:10], 1):
            name = t.get("name") or t.get("task_id") or f"Task #{idx}"
            status = t.get("status", "unknown").upper()
            progress = t.get("progress", 0)
            lines.append(f"{idx}. *{name}* — `{status}` ({progress}%)")

        await self._send_message(chat_id, "\n".join(lines))

    async def _handle_progress_command(self, chat_id: str) -> None:
        """Fetch current active task progress."""
        from backend.services.manager import ServiceManager
        tq = ServiceManager.get_instance("task_queue_service")
        tasks = getattr(tq, "tasks", []) if tq else []
        running = [t for t in tasks if t.get("status") == "running"]

        if not running:
            await self._send_message(chat_id, "⏱️ *Task Progress*\n\nNo long-running tasks are currently executing.")
            return

        current = running[0]
        name = current.get("name", "Active Workflow")
        pct = current.get("progress", 0)
        step = current.get("current_step", "Executing...")
        
        await self._send_message(
            chat_id,
            f"⏱️ *Task Progress: {name}*\n\n"
            f"• *Progress:* `{pct}%`\n"
            f"• *Current Step:* {step}\n"
            f"• *Status:* `RUNNING`"
        )

    async def _handle_lock_command(self, chat_id: str) -> None:
        """Lock the host Windows workstation immediately."""
        try:
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], shell=False)
            await self._send_message(chat_id, "🔒 *Workstation Locked*\n\nWindows workstation display locked successfully.")
        except Exception as e:
            logger.error("Failed to lock workstation: {}", e)
            await self._send_message(chat_id, f"❌ Failed to lock workstation: {e}")

    async def _handle_screenshot_command(self, chat_id: str) -> None:
        """Capture on-demand screen preview and send as a Telegram photo."""
        from backend.services.manager import ServiceManager
        gateway = ServiceManager.get_instance("mobile_gateway_service")
        if not gateway:
            from backend.services.mobile_gateway import MobileGatewayService
            gateway = MobileGatewayService()

        preview = gateway.capture_screen_preview()
        if not preview.image_base64:
            await self._send_message(chat_id, "⚠️ Desktop screenshot capture unavailable (missing display dependencies).")
            return

        try:
            raw_b64 = preview.image_base64.split(",", 1)[-1]
            img_bytes = base64.b64decode(raw_b64)
            await self._send_photo(
                chat_id,
                img_bytes,
                caption=f"📸 *Workstation Screen Snapshot*\nWindow: `{preview.active_window_title}`"
            )
        except Exception as e:
            logger.error("Failed to transmit screenshot photo via Telegram: {}", e)
            await self._send_message(chat_id, f"❌ Failed to transmit screenshot: {e}")

    async def _handle_app_launch(self, chat_id: str, app_name: str) -> None:
        """Launch whitelisted desktop application via AutomationService."""
        # Sanitize against shell operators
        if any(c in app_name for c in ["&", ";", "|", ">", "<", "`", "$", "\n", "\r"]):
            await self._send_message(chat_id, "❌ Invalid application name: shell operators are strictly prohibited.")
            return

        from backend.services.automation import AutomationService
        auto_svc = AutomationService()
        res = await auto_svc.open_application(app_name)
        if res.get("success", False):
            await self._send_message(chat_id, f"🚀 *Launched Application:* `{app_name}`")
        else:
            await self._send_message(chat_id, f"⚠️ Could not launch `{app_name}`: {res.get('error', 'Unknown error')}")

    async def _handle_help_command(self, chat_id: str) -> None:
        """Format and return command guide."""
        help_text = (
            "🤖 *JARVIS Telegram Remote Capabilities*\n\n"
            "• `/status` — System hardware metrics, active LLM, health\n"
            "• `/tasks` — View running and pending task queue items\n"
            "• `/progress` — Track progress of active workflows\n"
            "• `/screenshot` — Receive instant desktop screen capture\n"
            "• `/lock` — Lock the Windows workstation immediately\n"
            "• `/cancel` — Cancel active task execution & reset buffers\n"
            "• `/app <name>` — Launch approved desktop application\n"
            "• `/help` — Display this capabilities menu\n\n"
            "💬 *Natural Language Interaction:*\n"
            "Simply type any question or instruction (e.g. _'summarize today's meetings'_, _'check disk space'_) "
            "and JARVIS will execute it through the full planner & tool ecosystem."
        )
        await self._send_message(chat_id, help_text)

    async def _handle_natural_language_command(self, chat_id: str, prompt: str) -> None:
        """
        Execute natural language command through existing VoiceManager / PlannerAgent.
        Maintains shared memory context and records experience trace tagged with source="telegram".
        """
        await self._send_message(chat_id, f"⚡ *Processing command:* _{prompt[:80]}..._")

        from backend.services.manager import ServiceManager
        vm = ServiceManager.get_instance("voice_manager")

        response_text = ""
        start_time = time.time()

        try:
            if vm and hasattr(vm, "handle_text_command"):
                async for ws_msg in vm.handle_text_command(prompt):
                    msg_type = getattr(ws_msg, "type", "")
                    data = getattr(ws_msg, "data", {})
                    if msg_type == "response" and data.get("text"):
                        response_text = data["text"]
            else:
                planner = ServiceManager.get_instance("planner_agent")
                if planner and hasattr(planner, "plan_and_execute"):
                    async for p_msg in planner.plan_and_execute(prompt):
                        m_type = getattr(p_msg, "type", "")
                        d = getattr(p_msg, "data", {})
                        if m_type == "response" and d.get("text"):
                            response_text = d["text"]
                else:
                    response_text = f"Command received and acknowledged: '{prompt}'"

            if not response_text:
                response_text = "Action completed, sir."

            # Record experience trace with source='telegram'
            exp_engine = ServiceManager.get_instance("experience_engine")
            if exp_engine and hasattr(exp_engine, "record_experience"):
                try:
                    exp_engine.record_experience(
                        goal=f"[Telegram] {prompt}",
                        result=response_text[:200],
                        success=True,
                        execution_time_seconds=time.time() - start_time
                    )
                except Exception as exp_err:
                    logger.warning("Failed to record Telegram experience trace: {}", exp_err)

            # Send response back to Telegram (chunking if > 4000 chars)
            await self._send_message_chunked(chat_id, response_text)

        except Exception as e:
            logger.error("Error executing Telegram command '{}': {}", prompt, e)
            await self._send_message(chat_id, f"❌ *Error executing command:*\n`{e}`")

    # ── OUTBOUND NOTIFICATIONS & DEBOUNCE BUFFER ───────────────────────────

    async def send_notification(
        self,
        title: str,
        body: str,
        level: str = "info",
        inline_keyboard: Optional[List[List[Dict[str, str]]]] = None
    ) -> bool:
        """
        Send an outbound push alert to the authorized administrator with 2.0s rate limiting.
        Suppresses duplicate messages within a 10s window.
        """
        if not self.enabled or not self.chat_id or not self.bot_token:
            return False

        # Debounce duplicate messages
        msg_hash = f"{title}:{body}"
        now = time.time()
        if self._last_sent_hash == msg_hash and (now - self._last_sent_hash_time) < 10.0:
            logger.debug("Duplicate Telegram notification suppressed: '{}'", title)
            return True

        prefix_icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨",
            "security": "🛡️",
            "success": "✅"
        }
        icon = prefix_icons.get(level.lower(), "📱")
        formatted = f"{icon} *{title}*\n\n{body}"

        async with self._send_lock:
            # Enforce 2.0s gap
            time_since_last = now - self._last_notification_time
            if time_since_last < self._min_send_interval_s:
                await asyncio.sleep(self._min_send_interval_s - time_since_last)

            ok = await self._send_message(
                self.chat_id,
                formatted,
                inline_keyboard=inline_keyboard
            )
            if ok:
                self._last_notification_time = time.time()
                self._last_sent_hash = msg_hash
                self._last_sent_hash_time = time.time()
            return ok

    async def request_approval_notification(
        self,
        action_id: str,
        action_type: str,
        description: str,
        dangerous_target: str,
        timeout_seconds: float = 30.0
    ) -> bool:
        """Push an urgent 1-click [Approve] / [Deny] interactive card to Telegram."""
        if not self.enabled or not self.chat_id:
            return False

        message_text = (
            "🛡️ *JARVIS Security Authorization Required*\n\n"
            f"• *Action:* `{action_type}`\n"
            f"• *Target:* `{dangerous_target}`\n"
            f"• *Details:* {description}\n\n"
            f"⚠️ *Decision Timeout:* `{timeout_seconds:.0f}s`"
        )

        inline_keyboard = [
            [
                {"text": "✅ Approve Action", "callback_data": f"approve_{action_id}"},
                {"text": "❌ Deny Action", "callback_data": f"deny_{action_id}"}
            ]
        ]

        return await self.send_notification(
            title="SECURITY APPROVAL REQUIRED",
            body=message_text,
            level="security",
            inline_keyboard=inline_keyboard
        )

    # ── LOW-LEVEL TELEGRAM HTTP API CALLS ──────────────────────────────────

    async def _send_message(
        self,
        chat_id: str,
        text: str,
        inline_keyboard: Optional[List[List[Dict[str, str]]]] = None
    ) -> bool:
        """Deliver Markdown message via Telegram sendMessage."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if inline_keyboard:
            payload["reply_markup"] = {"inline_keyboard": inline_keyboard}

        resp = await self._call_api_async("sendMessage", payload)
        return bool(resp and resp.get("ok"))

    async def _send_message_chunked(self, chat_id: str, text: str) -> None:
        """Split text exceeding Telegram's 4096 character limit into multiple messages."""
        max_chunk = 3800
        if len(text) <= max_chunk:
            await self._send_message(chat_id, text)
            return

        for i in range(0, len(text), max_chunk):
            chunk = text[i:i + max_chunk]
            await self._send_message(chat_id, chunk)
            await asyncio.sleep(0.5)

    async def _edit_message_text(self, chat_id: str, message_id: int, text: str) -> bool:
        """Edit existing Telegram message to reflect decision outcome."""
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        resp = await self._call_api_async("editMessageText", payload)
        return bool(resp and resp.get("ok"))

    async def _answer_callback(self, query_id: str, text: str = "", show_alert: bool = False) -> bool:
        """Answer callback query to clear button loading spinner."""
        payload = {
            "callback_query_id": query_id,
            "text": text,
            "show_alert": show_alert
        }
        resp = await self._call_api_async("answerCallbackQuery", payload)
        return bool(resp and resp.get("ok"))

    async def _send_photo(self, chat_id: str, photo_bytes: bytes, caption: str = "") -> bool:
        """Upload and send JPEG photo via multipart/form-data."""
        if not self.bot_token:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        boundary = f"----WebKitFormBoundary{secrets.token_hex(16)}"

        body = bytearray()
        # chat_id field
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
        body.extend(f"{chat_id}\r\n".encode("utf-8"))

        # caption field
        if caption:
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
            body.extend(f"{caption}\r\n".encode("utf-8"))
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n')
            body.extend(b"Markdown\r\n")

        # photo file field
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="photo"; filename="screen.jpg"\r\n')
        body.extend(b"Content-Type: image/jpeg\r\n\r\n")
        body.extend(photo_bytes)
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode("utf-8"))

        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )

        def _do_upload():
            try:
                with urllib.request.urlopen(req, timeout=15.0) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception as e:
                logger.error("Failed to upload photo to Telegram: {}", e)
                return None

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, _do_upload)
        return bool(resp and resp.get("ok"))

    async def _call_api_async(
        self,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """Execute HTTP request against Telegram Bot API asynchronously."""
        if not self.bot_token:
            return None

        url = f"https://api.telegram.org/bot{self.bot_token}/{endpoint}"
        
        def _request_sync():
            try:
                if payload:
                    data_bytes = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        url,
                        data=data_bytes,
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    req = urllib.request.Request(url)

                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as http_err:
                logger.debug("Telegram API HTTP error {}: {}", http_err.code, http_err.reason)
                return None
            except Exception as e:
                logger.debug("Telegram API error {}: {}", endpoint, e)
                return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _request_sync)

    # ── STATUS & INTROSPECTION ─────────────────────────────────────────────

    def get_service_status(self) -> Dict[str, Any]:
        """Return safe status telemetry for UI dashboard and API."""
        masked_chat_id = (
            f"****{self.chat_id[-4:]}"
            if self.chat_id and len(self.chat_id) >= 4
            else ("Set" if self.chat_id else None)
        )
        return {
            "enabled": self.enabled,
            "connected": self._is_running,
            "bot_username": self._bot_username,
            "bot_id": self._bot_id,
            "authorized_chat_id": masked_chat_id,
            "is_paired": bool(self.chat_id),
            "pairing_active": bool(self.pairing_pin and time.time() < self.pairing_pin_expires_at),
            "last_activity_time": self.last_activity_time,
            "total_commands_executed": self.total_commands_executed,
            "total_unauthorized_attempts": self.total_unauthorized_attempts
        }


# Global singleton instance
telegram_service = TelegramRemoteService()
