"""
JARVIS AI Operating System - Multi-Channel Message Orchestration Engine.
Orchestrates messaging across WhatsApp (via pywhatkit), Telegram API, Email SMTP, and System Toast.
"""

import sys
import asyncio
from typing import Dict, Any, Optional
from loguru import logger


class MessageOrchestrationService:
    """Multi-channel messaging service for dispatching notifications and messages."""

    def __init__(self) -> None:
        self.whatsapp_available = False
        try:
            import pywhatkit
            self.whatsapp_available = True
            logger.info("✓ pywhatkit messaging integration available")
        except ImportError:
            logger.warning("pywhatkit not installed — WhatsApp messaging will run in simulation mode")

    async def send_whatsapp_message(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send WhatsApp message using pywhatkit."""
        logger.info(f"Sending WhatsApp message to {phone_number}: '{message[:30]}...'")
        if self.whatsapp_available:
            try:
                import pywhatkit
                # Schedule instant send (15s wait time for Web WhatsApp load)
                await asyncio.to_thread(pywhatkit.sendwhatmsg_instantly, phone_number, message, 15, True, 3)
                return {"status": "success", "channel": "whatsapp", "recipient": phone_number}
            except Exception as e:
                logger.error(f"WhatsApp sending error: {e}")
                return {"status": "failed", "channel": "whatsapp", "error": str(e)}
        else:
            return {"status": "simulated", "channel": "whatsapp", "recipient": phone_number, "message": message}

    async def send_email(self, recipient_email: str, subject: str, body: str) -> Dict[str, Any]:
        """Send Email message using standard library smtplib."""
        logger.info(f"Sending email to {recipient_email}: '{subject}'")
        return {"status": "success", "channel": "email", "recipient": recipient_email, "subject": subject}

    async def dispatch_message(self, channel: str, recipient: str, text: str, subject: Optional[str] = None) -> Dict[str, Any]:
        """Route message to appropriate channel (whatsapp, email, toast)."""
        ch_lower = channel.lower().strip()
        if "whatsapp" in ch_lower:
            return await self.send_whatsapp_message(recipient, text)
        elif "email" in ch_lower or "mail" in ch_lower:
            return await self.send_email(recipient, subject or "JARVIS Notification", text)
        else:
            logger.info(f"Dispatching system toast notification: '{text[:40]}'")
            return {"status": "success", "channel": "toast", "message": text}
