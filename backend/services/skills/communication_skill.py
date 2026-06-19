"""
Communication Hub Skill for JARVIS.
Handles sending/receiving emails (IMAP/SMTP), WhatsApp messaging,
Slack/Discord webhook notifications, local calendar events (SQLite), and ADB-based Android commands.
"""

import os
import sqlite3
import subprocess
import urllib.request
import json
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.header import decode_header
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pywhatkit

from backend.services.skills.base import BaseSkill, skill_tool
from backend.utils.logger import logger
from backend.config import get_settings


class CommunicationSkill(BaseSkill):
    """Enables JARVIS to interface with email, chat apps, calendars, and mobile devices."""

    def __init__(self, browser_service=None, memory_service=None) -> None:
        self.browser = browser_service
        self.memory = memory_service
        self._settings = get_settings()
        self._db_path = self._settings.data_path / "calendar.db"
        self._init_calendar_db()

    def _init_calendar_db(self) -> None:
        """Ensure calendar reminders SQLite database and tables exist."""
        try:
            self._settings.data_path.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    completed INTEGER DEFAULT 0
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to initialize calendar db: {}", e)

    # ── Email Client ───────────────────────────────────────────────────────

    @skill_tool(
        name="send_email",
        description="Sends an email using SMTP. Requires SMTP credentials configured in settings/env.",
        parameters={
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Recipient email address (e.g. 'user@example.com')"},
                "subject": {"type": "string", "description": "Subject of the email"},
                "body": {"type": "string", "description": "Body text of the email"}
            },
            "required": ["recipient", "subject", "body"]
        }
    )
    def send_email(self, recipient: str, subject: str, body: str) -> str:
        # Load SMTP configs from environment
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        sender_email = os.environ.get("EMAIL_USER")
        sender_pwd = os.environ.get("EMAIL_PASSWORD")

        if not sender_email or not sender_pwd:
            return "Email credentials are not configured. Please define EMAIL_USER and EMAIL_PASSWORD in .env."

        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = sender_email
            msg["To"] = recipient

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_pwd)
                server.send_message(msg)
                
            logger.info("Email sent successfully to {}", recipient)
            return f"✓ Email sent successfully to {recipient}."
        except Exception as e:
            logger.error("Failed to send email: {}", e)
            return f"Failed to send email: {e}"

    @skill_tool(
        name="read_latest_emails",
        description="Checks the inbox and retrieves details of the latest emails via IMAP.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of emails to retrieve. Default is 5."}
            },
            "required": []
        }
    )
    def read_latest_emails(self, limit: int = 5) -> str:
        imap_server = os.environ.get("IMAP_SERVER", "imap.gmail.com")
        imap_port = int(os.environ.get("IMAP_PORT", "993"))
        email_user = os.environ.get("EMAIL_USER")
        email_pwd = os.environ.get("EMAIL_PASSWORD")

        if not email_user or not email_pwd:
            return "Email credentials are not configured. Please define EMAIL_USER and EMAIL_PASSWORD in .env."

        try:
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(email_user, email_pwd)
            mail.select("inbox")

            status, messages = mail.search(None, "ALL")
            if status != "OK":
                return "Failed to search inbox."

            mail_ids = messages[0].split()
            if not mail_ids:
                return "Your inbox is empty."

            # Fetch last N emails
            mail_ids = mail_ids[-limit:]
            results = []

            for m_id in reversed(mail_ids):
                status, data = mail.fetch(m_id, "(RFC822)")
                if status != "OK":
                    continue
                
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode subject
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="ignore")

                # Decode sender
                sender, encoding = decode_header(msg["From"])[0]
                if isinstance(sender, bytes):
                    sender = sender.decode(encoding or "utf-8", errors="ignore")

                results.append(f"- **From**: {sender}\n  **Subject**: {subject}")

            mail.logout()
            return f"Latest {len(results)} emails:\n" + "\n".join(results)
        except Exception as e:
            logger.error("Failed to read emails: {}", e)
            return f"Failed to read emails: {e}"

    # ── WhatsApp Client ───────────────────────────────────────────────────

    @skill_tool(
        name="send_whatsapp_message",
        description="Sends an instant WhatsApp message to a phone number (include country code, e.g. +919876543210).",
        parameters={
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Target phone number with country code"},
                "message": {"type": "string", "description": "Message text"}
            },
            "required": ["phone_number", "message"]
        }
    )
    def send_whatsapp_message(self, phone_number: str, message: str) -> str:
        clean_num = phone_number.replace(" ", "").strip()
        try:
            logger.info("Sending WhatsApp message to {}", clean_num)
            # sendwhatmsg_instantly opens a browser page. WaitTime defines loading buffer.
            pywhatkit.sendwhatmsg_instantly(clean_num, message, wait_time=15, tab_close=True, close_time=3)
            return f"✓ WhatsApp message sent to {clean_num} (opened in browser)."
        except Exception as e:
            logger.error("WhatsApp message failed: {}", e)
            return f"Failed to send WhatsApp message: {e}"

    # ── Slack / Discord Webhooks ──────────────────────────────────────────

    @skill_tool(
        name="send_slack_message",
        description="Sends a text notification to a Slack Channel via an Incoming Webhook URL.",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Text message to post"},
                "webhook_url": {"type": "string", "description": "Webhook URL (optional, defaults to SLACK_WEBHOOK_URL env)"}
            },
            "required": ["message"]
        }
    )
    def send_slack_message(self, message: str, webhook_url: Optional[str] = None) -> str:
        url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        if not url:
            return "Slack Webhook URL is not configured. Add SLACK_WEBHOOK_URL to env or pass it as an argument."

        try:
            data = json.dumps({"text": message}).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as resp:
                resp.read()
            return "✓ Posted message to Slack successfully."
        except Exception as e:
            return f"Failed to send Slack message: {e}"

    @skill_tool(
        name="send_discord_message",
        description="Sends a message to a Discord channel via Webhook.",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message string"},
                "webhook_url": {"type": "string", "description": "Discord webhook URL (optional, defaults to DISCORD_WEBHOOK_URL env)"}
            },
            "required": ["message"]
        }
    )
    def send_discord_message(self, message: str, webhook_url: Optional[str] = None) -> str:
        url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
        if not url:
            return "Discord Webhook URL is not configured. Add DISCORD_WEBHOOK_URL to env or pass it as an argument."

        try:
            data = json.dumps({"content": message}).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json", "User-Agent": "JARVIS-Assistant"}
            )
            with urllib.request.urlopen(req) as resp:
                resp.read()
            return "✓ Posted message to Discord successfully."
        except Exception as e:
            return f"Failed to send Discord message: {e}"

    # ── Local SQLite Calendar ──────────────────────────────────────────────

    @skill_tool(
        name="add_calendar_event",
        description="Saves a new calendar event / reminder to the local SQLite database.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event name"},
                "start_time": {"type": "string", "description": "Start time (YYYY-MM-DD HH:MM)"},
                "description": {"type": "string", "description": "Details about the event"},
                "end_time": {"type": "string", "description": "End time (optional, YYYY-MM-DD HH:MM)"}
            },
            "required": ["title", "start_time"]
        }
    )
    def add_calendar_event(self, title: str, start_time: str, description: Optional[str] = None, end_time: Optional[str] = None) -> str:
        try:
            # Validate start_time format
            datetime.strptime(start_time, "%Y-%m-%d %H:%M")
            if end_time:
                datetime.strptime(end_time, "%Y-%m-%d %H:%M")
        except ValueError:
            return "Invalid time format. Please use YYYY-MM-DD HH:MM (e.g. '2026-06-25 14:00')."

        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO events (title, description, start_time, end_time) VALUES (?, ?, ?, ?)",
                (title, description, start_time, end_time)
            )
            conn.commit()
            conn.close()
            return f"✓ Event '{title}' scheduled for {start_time}."
        except Exception as e:
            return f"Failed to schedule event: {e}"

    @skill_tool(
        name="list_calendar_events",
        description="Lists all upcoming local calendar events and reminders.",
        parameters={"type": "object", "properties": {}, "required": []}
    )
    def list_calendar_events(self) -> str:
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, description, start_time, end_time, completed FROM events ORDER BY start_time ASC")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return "Your calendar is empty."

            lines = ["📅 Scheduled Events:"]
            for row in rows:
                evt_id, title, desc, start, end, done = row
                status = "✅ Done" if done else "⏳ Pending"
                desc_str = f" - {desc}" if desc else ""
                lines.append(f"[{evt_id}] {start} : **{title}**{desc_str} ({status})")
            return "\n".join(lines)
        except Exception as e:
            return f"Failed to list events: {e}"

    # ── SMS / Phone via ADB ────────────────────────────────────────────────

    @skill_tool(
        name="adb_make_call",
        description="Triggers a dialer phone call on a connected Android phone via ADB commands.",
        parameters={
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Target number to call"}
            },
            "required": ["phone_number"]
        }
    )
    def adb_make_call(self, phone_number: str) -> str:
        clean_num = phone_number.replace(" ", "").strip()
        try:
            # Check devices first
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=True)
            lines = res.stdout.strip().split("\n")
            if len(lines) < 2 or not lines[1].strip():
                return "No Android device connected via ADB. Run 'adb devices' and ensure USB debugging is on."

            cmd = ["adb", "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{clean_num}"]
            subprocess.run(cmd, check=True, capture_output=True)
            return f"✓ Dialed {clean_num} on your Android device."
        except Exception as e:
            logger.error("ADB call failed: {}", e)
            return f"ADB action failed: {e}. Ensure ADB is installed and phone is connected."
            
    @skill_tool(
        name="adb_send_sms",
        description="Sends an SMS to a recipient phone number on a connected Android phone using ADB.",
        parameters={
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Target phone number"},
                "message": {"type": "string", "description": "Text message body"}
            },
            "required": ["phone_number", "message"]
        }
    )
    def adb_send_sms(self, phone_number: str, message: str) -> str:
        clean_num = phone_number.replace(" ", "").strip()
        try:
            # Check devices
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=True)
            if "device" not in res.stdout.split("\n")[1]:
                return "No Android device found connected via ADB."

            # Launch SMS activity
            launch_cmd = [
                "adb", "shell", "am", "start", "-a", "android.intent.action.SENDTO",
                "-d", f"sms:{clean_num}", "--es", "sms_body", message
            ]
            subprocess.run(launch_cmd, check=True, capture_output=True)
            
            # Wait a moment for UI to load
            import time
            time.sleep(1.5)
            
            # Send keys to trigger send (Usually keyevent 22 to focus send, keyevent 66 to press send)
            # Note: This is Android UI dependent, but works for most default SMS apps.
            # Send keyevent 22 (RIGHT), keyevent 22 (RIGHT), keyevent 66 (ENTER)
            subprocess.run(["adb", "shell", "input", "keyevent", "22"], capture_output=True)
            subprocess.run(["adb", "shell", "input", "keyevent", "66"], capture_output=True)

            return f"✓ Triggered SMS send to {clean_num} via ADB."
        except Exception as e:
            logger.error("ADB SMS failed: {}", e)
            return f"ADB SMS failed: {e}"
