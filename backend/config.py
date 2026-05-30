"""
JARVIS AI Desktop Assistant - Configuration Module.

Loads application settings from environment variables and .env file
using Pydantic Settings. All configuration values are centralized here
with sensible defaults for development and production use.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Project Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_LOG_DIR = BACKEND_DIR / "logs"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.

    All settings have sensible defaults except OPENAI_API_KEY, which is
    required for the LLM service to function. Settings are loaded in the
    following priority order:
        1. Environment variables
        2. .env file in the project root
        3. Default values defined here
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Settings ─────────────────────────────────────────────────────
    LLM_PROVIDER: str = Field(
        default="gemini",
        description="Primary LLM provider to use: gemini or openai.",
    )
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for Flash/Pro model access.",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model identifier (e.g. gemini-2.0-flash).",
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key for GPT and Vision API access.",
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o",
        description="OpenAI model identifier for chat completions.",
    )


    # ── Whisper / STT Settings ───────────────────────────────────────────
    WHISPER_MODEL: str = Field(
        default="small",
        description="Faster-whisper model size: tiny, base, small, medium, large-v2, large-v3.",
    )
    WHISPER_DEVICE: str = Field(
        default="auto",
        description="Device for Whisper inference: auto, cpu, cuda.",
    )
    WHISPER_COMPUTE_TYPE: str = Field(
        default="int8",
        description="Compute type for Whisper: int8, float16, float32.",
    )

    # ── TTS Settings ─────────────────────────────────────────────────────
    TTS_ENGINE: str = Field(
        default="edge-tts",
        description="TTS engine to use: edge-tts or elevenlabs.",
    )
    TTS_VOICE: str = Field(
        default="en-US-GuyNeural",
        description="Voice identifier for the TTS engine.",
    )
    TTS_RATE: str = Field(
        default="+0%",
        description="Speech rate adjustment for edge-tts (e.g., '+10%', '-5%').",
    )

    # ── ElevenLabs (Optional) ────────────────────────────────────────────
    ELEVENLABS_API_KEY: Optional[str] = Field(
        default=None,
        description="ElevenLabs API key for premium TTS (optional).",
    )

    # ── Wake Word Settings ───────────────────────────────────────────────
    WAKE_WORD_THRESHOLD: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for wake word detection (0.0-1.0).",
    )

    # ── Server Settings ──────────────────────────────────────────────────
    SERVER_HOST: str = Field(
        default="127.0.0.1",
        description="Host address for the FastAPI server.",
    )
    SERVER_PORT: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port for the FastAPI server.",
    )

    # ── Safety Settings ──────────────────────────────────────────────────
    SAFETY_CONFIRM_DANGEROUS: bool = Field(
        default=True,
        description="Require user confirmation before executing dangerous actions.",
    )
    SAFETY_ALLOW_TERMINAL: bool = Field(
        default=True,
        description="Allow execution of terminal/shell commands.",
    )

    # ── OCR / Tesseract ──────────────────────────────────────────────────
    TESSERACT_PATH: Optional[str] = Field(
        default=None,
        description="Path to the Tesseract OCR executable (optional, auto-detected if on PATH).",
    )

    # ── Data Storage ─────────────────────────────────────────────────────
    DATA_DIR: str = Field(
        default=str(DEFAULT_DATA_DIR),
        description="Directory for persistent data storage (ChromaDB, SQLite).",
    )

    # ── Derived Properties ───────────────────────────────────────────────

    @field_validator("DATA_DIR", mode="before")
    @classmethod
    def _ensure_data_dir_exists(cls, v: str) -> str:
        """Create the data directory if it does not exist."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.resolve())

    @property
    def data_path(self) -> Path:
        """Return DATA_DIR as a resolved Path object."""
        return Path(self.DATA_DIR).resolve()

    @property
    def chromadb_path(self) -> Path:
        """Return the path for ChromaDB persistent storage."""
        p = self.data_path / "chromadb"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def sqlite_url(self) -> str:
        """Return the async SQLite connection URL."""
        db_path = self.data_path / "jarvis.db"
        return f"sqlite+aiosqlite:///{db_path}"

    @property
    def log_dir(self) -> Path:
        """Return the log directory path, creating it if needed."""
        log_path = DEFAULT_LOG_DIR
        log_path.mkdir(parents=True, exist_ok=True)
        return log_path


def get_settings() -> Settings:
    """
    Factory function to create a Settings instance.

    Returns:
        Settings: Validated application settings loaded from
                  environment variables and .env file.

    Raises:
        pydantic.ValidationError: If required settings are missing
                                   or values are invalid.
    """
    return Settings()
