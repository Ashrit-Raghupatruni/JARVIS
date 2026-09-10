"""
JARVIS AI OS — Working Memory.

Manages lightweight, bounded short-term conversation context, active session state,
message turn buffers, and silent language tracking without unbounded memory growth.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger
from sqlalchemy import select

from backend.config import get_settings
from backend.models.database import Conversation, Message as DbMessage


class SilentLanguageTracker:
    """Tracks and persists silent user language preferences in user_habits.json."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        settings = get_settings()
        self.data_dir = data_dir or settings.data_path
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.habits_file = self.data_dir / "user_habits.json"
        
        self.preferred_language: str = "en"
        self.language_name: str = "English"
        self._load_memory()

    def _load_memory(self) -> None:
        if self.habits_file.exists():
            try:
                with open(self.habits_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.preferred_language = data.get("preferred_language", "en")
                    self.language_name = data.get("language_name", "English")
                    logger.debug("Loaded Silent Language: {} ({})", self.language_name, self.preferred_language)
            except Exception as e:
                logger.error("Failed to load user habits: {}", e)

    def _save_memory(self) -> None:
        try:
            existing = {}
            if self.habits_file.exists():
                try:
                    with open(self.habits_file, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}

            existing["preferred_language"] = self.preferred_language
            existing["language_name"] = self.language_name

            with open(self.habits_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            logger.error("Failed to save language habits: {}", e)

    def detect_and_update(self, text: str) -> str:
        if not text or len(text.strip()) < 3:
            return self.preferred_language

        if re.search(r'\b(hola|por favor|gracias|buenos dias|como estas|que|para)\b', text, re.I):
            self.preferred_language = "es"
            self.language_name = "Spanish"
            self._save_memory()
        elif re.search(r'\b(bonjour|merci|s\'il vous plait|comment|avec|pour)\b', text, re.I):
            self.preferred_language = "fr"
            self.language_name = "French"
            self._save_memory()
        elif re.search(r'\b(hallo|danke|bitte|guten tag|wie gehts|und|mit)\b', text, re.I):
            self.preferred_language = "de"
            self.language_name = "German"
            self._save_memory()
        elif re.search(r'[\u0900-\u097F]', text):
            self.preferred_language = "hi"
            self.language_name = "Hindi"
            self._save_memory()
        elif re.search(r'[\u0C00-\u0C7F]', text):
            self.preferred_language = "te"
            self.language_name = "Telugu"
            self._save_memory()

        return self.preferred_language

    def get_system_prompt_instruction(self) -> str:
        if self.preferred_language == "en":
            return ""
        return f"[LANGUAGE MEMORY ENFORCEMENT]: User preferred language is set to {self.language_name} ({self.preferred_language}). You MUST respond in {self.language_name} unless explicitly commanded otherwise."


class WorkingMemory:
    """
    Working Memory maintains:
    1. Bounded conversation turn window (sliding-window buffer).
    2. Ephemeral session state key-values.
    3. SQLite conversation history & message persistence.
    4. Silent user language detection & prompting.
    """

    def __init__(self, session_factory=None, max_turns: int = 10, max_tokens: int = 2048):
        self.session_factory = session_factory
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        
        self.turns: List[Dict[str, str]] = []
        self.state: Dict[str, Any] = {}
        self.language = SilentLanguageTracker()
        logger.info("WorkingMemory initialized (max_turns={}, max_tokens={})", max_turns, max_tokens)

    def set_session_factory(self, session_factory):
        self.session_factory = session_factory

    # ── Sliding Window Turn Buffer ────────────────────────────────────────

    def add_turn(self, role: str, content: str) -> None:
        """Add turn with automatic eviction of oldest turn when exceeding max_turns."""
        if role not in ("user", "assistant", "system"):
            role = "user"
        content = content.strip()
        if not content:
            return

        # Check silent language preference
        if role == "user":
            self.language.detect_and_update(content)

        if len(self.turns) >= self.max_turns:
            self.turns.pop(0)

        self.turns.append({"role": role, "content": content, "timestamp": time.time()})

    def get_turns(self) -> List[Dict[str, str]]:
        """Return shallow copy of current active turns."""
        return [{"role": t["role"], "content": t["content"]} for t in self.turns]

    def clear_turns(self) -> None:
        self.turns.clear()

    # ── Ephemeral State ───────────────────────────────────────────────────

    def set(self, key: str, value: Any) -> None:
        self.state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def clear_ephemeral(self) -> None:
        self.state.clear()

    # ── SQLite Conversation Database Persistence ─────────────────────────

    async def create_conversation(self, title: str = "New Session") -> Optional[int]:
        if not self.session_factory:
            return None
        try:
            async with self.session_factory() as session:
                conv = Conversation(title=title)
                session.add(conv)
                await session.commit()
                await session.refresh(conv)
                return conv.id
        except Exception as e:
            logger.error("Failed to create conversation: {}", e)
            return None

    async def add_message_to_conversation(self, conv_id: int, role: str, content: str) -> Optional[int]:
        # Track in turn buffer
        self.add_turn(role, content)

        if not self.session_factory:
            return None
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conv_id)
                )
                conv = result.scalar_one_or_none()
                if not conv:
                    conv = Conversation(id=conv_id, title="New Conversation")
                    session.add(conv)
                    await session.flush()
                
                conv.updated_at = datetime.now(timezone.utc)
                msg = DbMessage(
                    conversation_id=conv.id,
                    role=role,
                    content=content,
                )
                session.add(msg)
                await session.commit()
                await session.refresh(msg)
                return conv.id
        except Exception as e:
            logger.error("Failed to append message to conversation {}: {}", conv_id, e)
            return None

    save_message = add_message_to_conversation
    add_message = add_message_to_conversation

    async def get_recent_conversations(self, limit: int = 30) -> list[dict]:
        if not self.session_factory:
            return []
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Conversation)
                    .order_by(Conversation.updated_at.desc())
                    .limit(limit)
                )
                conversations = result.scalars().all()
                return [
                    {
                        "id": c.id,
                        "title": c.title,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                        "message_count": len(c.messages) if c.messages else 0
                    }
                    for c in conversations
                ]
        except Exception as e:
            logger.error("Failed to get recent conversations: {}", e)
            return []

    async def get_conversation(self, conv_id: int) -> Optional[dict]:
        if not self.session_factory:
            return None
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conv_id)
                )
                c = result.scalar_one_or_none()
                if not c:
                    return None
                return {
                    "id": c.id,
                    "title": c.title,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                    "messages": [
                        {
                            "id": m.id,
                            "role": m.role,
                            "content": m.content,
                            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                        }
                        for m in (c.messages or [])
                    ]
                }
        except Exception as e:
            logger.error("Failed to get conversation {}: {}", conv_id, e)
            return None

    async def rename_conversation(self, conv_id: int, new_title: str) -> bool:
        if not self.session_factory:
            return False
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conv_id)
                )
                c = result.scalar_one_or_none()
                if not c:
                    return False
                c.title = new_title.strip()
                await session.commit()
                return True
        except Exception as e:
            logger.error("Failed to rename conversation {}: {}", conv_id, e)
            return False

    async def delete_conversation(self, conv_id: int) -> bool:
        if not self.session_factory:
            return False
        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conv_id)
                )
                c = result.scalar_one_or_none()
                if not c:
                    return False
                await session.delete(c)
                await session.commit()
                return True
        except Exception as e:
            logger.error("Failed to delete conversation {}: {}", conv_id, e)
            return False

    @staticmethod
    def auto_generate_title(first_msg: str) -> str:
        clean = first_msg.strip()
        if not clean:
            return "New Conversation"
        words = clean.split()
        if len(words) <= 6:
            return clean.capitalize()
        return " ".join(words[:6]).capitalize() + "..."

    async def generate_auto_title(self, conv_id: int, user_prompt: str, assistant_reply: str = "") -> str:
        fallback_title = self.auto_generate_title(user_prompt)
        title = fallback_title
        try:
            from backend.services.manager import ServiceManager
            llm_svc = ServiceManager.get_instance("llm_service")
            if llm_svc and hasattr(llm_svc, "simple_completion"):
                sys_prompt = "You are a concise title generator. Generate a short 3-6 word title summarizing the user prompt. Output ONLY the plain text title. No quotes, no markdown, no punctuation."
                llm_response = await llm_svc.simple_completion(f"User Prompt: {user_prompt[:200]}", system_prompt=sys_prompt)
                if llm_response and isinstance(llm_response, str):
                    clean_t = llm_response.strip().strip('"\'`')
                    if 2 <= len(clean_t) <= 60:
                        title = clean_t
        except Exception as e:
            logger.debug("LLM title notice for conv {}: {}", conv_id, e)

        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    result = await session.execute(
                        select(Conversation).where(Conversation.id == conv_id)
                    )
                    conv = result.scalar_one_or_none()
                    if conv:
                        conv.title = title
                        conv.updated_at = datetime.now(timezone.utc)
                        await session.commit()
            except Exception as db_err:
                logger.error("Failed to save title to DB: {}", db_err)

        return title
