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
        default="groq",
        description="Primary LLM provider to use: gemini, openai, or ollama.",
    )
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for Flash/Pro model access.",
    )
    GEMINI_API_KEY_ALT: Optional[str] = Field(
        default=None,
        description="Alternative Google Gemini API key for fallback rotation.",
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
    OPENROUTER_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenRouter API key for LLM completions.",
    )
    OPENROUTER_MODEL: str = Field(
        default="meta-llama/llama-3.3-70b-instruct:free",
        description="OpenRouter model identifier.",
    )
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="Groq API key for high-speed LLM completions.",
    )
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model identifier.",
    )
    NVIDIA_API_KEY: Optional[str] = Field(
        default=None,
        description="NVIDIA NIM API key.",
    )
    NIM_MODEL: str = Field(
        default="meta/llama-3.1-8b-instruct",
        description="NVIDIA NIM model identifier.",
    )


    # ── Ollama Settings ──────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL for the Ollama API server.",
    )
    OLLAMA_MODEL: str = Field(
        default="qwen2.5-coder:3b",
        description="Ollama model identifier for local chat completions.",
    )
    OLLAMA_MODEL_ALT: Optional[str] = Field(
        default="qwen3:8b",
        description="Alternative local Ollama model for fallback rotation.",
    )


    # ── Whisper / STT Settings ───────────────────────────────────────────
    WHISPER_MODEL: str = Field(
        default="base",
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
        default="en-GB-RyanNeural",
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
    ELEVENLABS_VOICE_ID: Optional[str] = Field(
        default=None,
        description="ElevenLabs voice ID for premium TTS.",
    )
    ELEVENLABS_MODEL_ID: str = Field(
        default="eleven_multilingual_v2",
        description="ElevenLabs TTS model ID.",
    )
    ELEVENLABS_OUTPUT_FORMAT: str = Field(
        default="pcm_24000",
        description="ElevenLabs output audio format.",
    )
    ELEVENLABS_PCM_SAMPLE_RATE: Optional[int] = Field(
        default=None,
        description="ElevenLabs sample rate override (defaults to parsing format).",
    )

    # ── Clap Listener Settings ───────────────────────────────────────────
    CLAP_ENABLED: bool = Field(
        default=True,
        description="Whether to enable the background clap listener.",
    )
    CLAP_SAMPLE_RATE: int = Field(
        default=44100,
        description="Sample rate for microphone audio capture.",
    )
    CLAP_BLOCK_MS: int = Field(
        default=40,
        description="Analysis block size in milliseconds.",
    )
    CLAP_SPIKE_RATIO: float = Field(
        default=7.0,
        description="Spike ratio relative to noise floor to detect a clap.",
    )
    CLAP_COOLDOWN_S: float = Field(
        default=0.45,
        description="Cooldown period in seconds between detections.",
    )
    CLAP_MIN_DOUBLE_GAP_S: float = Field(
        default=0.05,
        description="Minimum gap between double claps.",
    )
    CLAP_MAX_DOUBLE_GAP_S: float = Field(
        default=0.35,
        description="Maximum gap between double claps.",
    )
    CLAP_RETRIGGER_RATIO: float = Field(
        default=0.55,
        description="Retrigger ratio to arm next detection.",
    )
    CLAP_NOISE_FLOOR_ALPHA: float = Field(
        default=0.992,
        description="Adaptive noise floor tracking alpha coefficient.",
    )
    CLAP_MIN_RMS: float = Field(
        default=0.012,
        description="Absolute minimum RMS amplitude to consider.",
    )
    CLAP_QUIET_GATE_MULT: float = Field(
        default=2.2,
        description="Gate multiplier below which noise floor is updated.",
    )

    # ── Double Clap Welcome Flow Actions ─────────────────────────────────
    CLAP_SONG_URI: str = Field(
        default="",
        description="Spotify or YouTube URL/URI to open on double clap.",
    )
    CLAP_FOCUS_EXISTING_CURSOR: bool = Field(
        default=True,
        description="Foreground existing Cursor window on double clap.",
    )
    CLAP_OPEN_NEW_CURSOR: bool = Field(
        default=False,
        description="Launch a new Cursor window (-n) on double clap.",
    )
    CLAP_CURSOR_FULLSCREEN: bool = Field(
        default=True,
        description="Send F11 to Cursor window to toggle fullscreen (Windows).",
    )
    CLAP_OPEN_CLAUDE_CHROME: bool = Field(
        default=False,
        description="Open Claude.ai in Google Chrome on double clap.",
    )
    CLAP_OPEN_BINANCE_CHROME: bool = Field(
        default=False,
        description="Open Binance BTC in Google Chrome on double clap.",
    )
    CLAP_CHROME_FULLSCREEN: bool = Field(
        default=True,
        description="Open Chrome windows in fullscreen.",
    )
    CLAP_CHROME_SEPARATE_PROFILES: bool = Field(
        default=False,
        description="Use separate profile temp directories for Chrome.",
    )
    CLAP_CLAUDE_MONITOR: int = Field(
        default=1,
        description="Display monitor index to open Claude Chrome (1-based).",
    )
    CLAP_BINANCE_MONITOR: int = Field(
        default=3,
        description="Display monitor index to open Binance Chrome (1-based).",
    )
    CLAP_WELCOME_ENABLED: bool = Field(
        default=True,
        description="Enable speech synthesis welcome sequence.",
    )
    CLAP_WELCOME_PHRASE: str = Field(
        default="Welcome home sir. Congratulations on the new client for your SaaS app—make sure to follow up. If it helps: a short, specific note while the deal is still fresh usually anchors trust better than a polished deck sent cold a few days later.",
        description="Phrase spoken on double clap.",
    )
    CLAP_WELCOME_DELAY_S: float = Field(
        default=1.0,
        description="Seconds to wait after opening song before starting TTS speech.",
    )
    CLAP_WELCOME_CACHE_ENABLED: bool = Field(
        default=True,
        description="Cache TTS generated welcome WAV locally.",
    )
    CLAP_WELCOME_CACHE_DIR: Optional[str] = Field(
        default=None,
        description="Directory for cached welcome audio files.",
    )

    # ── Cross-Device Sync Settings ───────────────────────────────────────
    SYNC_ENABLED: bool = Field(
        default=True,
        description="Whether to enable cross-device synchronization.",
    )
    SYNC_KEY: str = Field(
        default="iy2yR4WcpNOzgIn3FHXSw_ygqgkpi7KghI7Yvx1o6J4=",  # A valid 32-byte Fernet key base64
        description="Symmetric encryption key for sync data.",
    )
    SYNC_PORT: int = Field(
        default=18270,
        description="Port for peer-to-peer connection discovery.",
    )
    FRIENDLY_DEVICE_NAME: str = Field(
        default="JARVIS Windows",
        description="Friendly name for identifying this device.",
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

    @field_validator(
        "GEMINI_API_KEY",
        "GEMINI_API_KEY_ALT",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "NVIDIA_API_KEY",
        mode="before"
    )
    @classmethod
    def validate_api_keys(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v_str = str(v).strip()
        placeholders = [
            "your-gemini-api-key",
            "your-openai-api-key",
            "your-openrouter-api-key",
            "your-groq-api-key",
            "your-nvidia-api-key",
            "placeholder",
            "sk-your",
            "AIzaSy-your",
            "your_key",
        ]
        for p in placeholders:
            if p.lower() in v_str.lower():
                print(f"[Config Warning] Placeholder API key detected and deactivated: {v_str[:15]}...")
                return None
        return v_str

    @field_validator("SYNC_KEY", mode="before")
    @classmethod
    def validate_sync_key(cls, v: Optional[str]) -> str:
        default_key = "iy2yR4WcpNOzgIn3FHXSw_ygqgkpi7KghI7Yvx1o6J4="
        if not v:
            return default_key
        v_str = str(v).strip()
        try:
            from cryptography.fernet import Fernet
            Fernet(v_str.encode("utf-8"))
            return v_str
        except Exception:
            try:
                from cryptography.fernet import Fernet
                fallback_key = Fernet.generate_key().decode("utf-8")
                print(f"[Config Warning] Invalid SYNC_KEY provided. Auto-generated secure fallback key: {fallback_key[:10]}...")
                return fallback_key
            except Exception:
                return default_key

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
