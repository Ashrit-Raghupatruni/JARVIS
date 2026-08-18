"""
JARVIS Personal AI OS — Silent Language Memory & Detection Service.
Detects user spoken/written language, persists preference in user context,
and enforces automated multi-turn responses in the user's preferred language.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

from backend.config import get_settings


class LanguageMemoryService:
    """Manages silent detection and multi-session persistence of user language."""

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
                    logger.info(f"✓ Loaded Silent Language Memory: {self.language_name} ({self.preferred_language})")
            except Exception as e:
                logger.error(f"Failed to load user habits file: {e}")

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
            logger.info(f"✓ Persisted Silent Language Memory: {self.language_name} ({self.preferred_language})")
        except Exception as e:
            logger.error(f"Failed to save language memory: {e}")

    def detect_and_update(self, text: str) -> str:
        """Detect language from input string and update memory if confident."""
        if not text or len(text.strip()) < 3:
            return self.preferred_language

        # Heuristic detection patterns for key languages
        # Spanish
        if re.search(r'\b(hola|por favor|gracias|buenos dias|como estas|que|para)\b', text, re.I):
            self.preferred_language = "es"
            self.language_name = "Spanish"
            self._save_memory()
        # French
        elif re.search(r'\b(bonjour|merci|s\'il vous plait|comment|avec|pour)\b', text, re.I):
            self.preferred_language = "fr"
            self.language_name = "French"
            self._save_memory()
        # German
        elif re.search(r'\b(hallo|danke|bitte|guten tag|wie gehts|und|mit)\b', text, re.I):
            self.preferred_language = "de"
            self.language_name = "German"
            self._save_memory()
        # Hindi / Telugu / Indian script patterns
        elif re.search(r'[\u0900-\u097F]', text):  # Devanagari script
            self.preferred_language = "hi"
            self.language_name = "Hindi"
            self._save_memory()
        elif re.search(r'[\u0C00-\u0C7F]', text):  # Telugu script
            self.preferred_language = "te"
            self.language_name = "Telugu"
            self._save_memory()

        return self.preferred_language

    def get_system_prompt_instruction(self) -> str:
        """Return system prompt instruction for enforcing response language."""
        if self.preferred_language == "en":
            return ""
        return f"[LANGUAGE MEMORY ENFORCEMENT]: User preferred language is set to {self.language_name} ({self.preferred_language}). You MUST respond in {self.language_name} unless explicitly commanded otherwise."
