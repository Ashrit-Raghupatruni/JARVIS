"""
JARVIS AI Desktop Assistant - Pydantic Schemas.

Defines every WebSocket / API message type used throughout the application.
All messages flowing between the frontend and backend conform to one of
these schemas, enabling strong validation and IDE auto-completion.
"""

from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Enums
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AssistantState(str, Enum):
    """All possible states of the JARVIS voice assistant."""

    SLEEPING = "sleeping"
    IDLE = "idle"
    WAKE_WORD_DETECTED = "wake_word_detected"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    EXECUTING = "executing"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class AgentStepStatus(str, Enum):
    """Status of an individual step within an agent task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageRole(str, Enum):
    """Role of a participant in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Base Message
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class WSMessage(BaseModel):
    """
    Base WebSocket message envelope (Protocol Version 1).

    Every message sent through the WebSocket connection conforms to this
    structure. The ``type`` field acts as a discriminator so the receiver
    can deserialise the ``data`` payload into the correct schema.
    """

    version: str = Field(default="1", description="Protocol version (e.g. '1').")
    type: str = Field(..., description="Message type discriminator.")
    success: bool = Field(default=True, description="Whether the operation/event succeeded.")
    request_id: Optional[str] = Field(default=None, description="Request ID for client correlation.")
    correlation_id: Optional[str] = Field(default=None, description="Correlation identifier linking requests and responses.")
    session_id: Optional[str] = Field(default=None, description="Client session or device identifier.")
    msg_id: Optional[int] = Field(default=None, description="Sequence ID for ACK tracking.")
    data: Dict[str, Any] = Field(default_factory=dict, description="Payload data.")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Structured error details if success is False.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of when the message was created.",
    )
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique message identifier.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Canonical Command, Response & Tool Result Envelopes (V1 Unified Protocol)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CommandSource(str, Enum):
    """Origin of a command entering the JARVIS core."""

    DESKTOP = "desktop"
    ANDROID = "android"
    TELEGRAM = "telegram"
    REST = "rest"
    VOICE = "voice"
    INTERNAL = "internal"


class CommandEnvelope(BaseModel):
    """
    Canonical Command Envelope across all ingress channels (Desktop, Mobile, Telegram, REST).
    Guarantees strict runtime validation before reaching FastIntentRouter and Planner.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = Field(default="1")
    source: CommandSource = Field(default=CommandSource.INTERNAL)
    type: str = Field(..., description="Action or command discriminator (e.g. 'command', 'action', 'voice_start').")
    text: Optional[str] = Field(default=None, description="Natural language prompt or typed text.")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Command arguments or payload data.")
    timestamp: float = Field(default_factory=time.time)
    client_id: Optional[str] = Field(default=None)
    correlation_id: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)


class ResponseEnvelope(BaseModel):
    """
    Canonical Response Envelope across all egress channels.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = Field(default="1")
    type: str = Field(..., description="Response discriminator: 'response', 'error', 'event', 'status', 'approval_required'.")
    success: bool = Field(default=True)
    data: Any = Field(default=None)
    error: Optional[Dict[str, Any]] = Field(default=None)
    correlation_id: Optional[str] = Field(default=None)
    request_id: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)
    timestamp: float = Field(default_factory=time.time)


class ToolResultContract(BaseModel):
    """
    Canonical Tool Result Contract returned by ToolRegistry and all executed tools.
    Guarantees consistent 'success' and 'status' fields so no consumer misinterprets outcomes.
    """

    success: bool
    status: str
    tool_name: str
    data: Optional[Any] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Audio & Speech Messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AudioData(BaseModel):
    """Raw audio data sent from client for processing."""

    audio_bytes: bytes = Field(..., description="Raw PCM audio bytes (16-bit, 16 kHz, mono).")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz.")
    channels: int = Field(default=1, description="Number of audio channels.")
    format: str = Field(default="pcm_s16le", description="Audio format identifier.")


class TranscriptMessage(BaseModel):
    """Speech-to-text transcription result."""

    text: str = Field(..., description="Transcribed text from user speech.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Transcription confidence.")
    is_partial: bool = Field(default=False, description="Whether this is a partial/interim result.")
    language: Optional[str] = Field(default=None, description="Detected language code.")


class TTSAudioMessage(BaseModel):
    """Text-to-speech audio chunk for playback."""

    audio_bytes: bytes = Field(..., description="MP3 audio chunk bytes.")
    format: str = Field(default="mp3", description="Audio format (mp3).")
    is_final: bool = Field(default=False, description="Whether this is the last chunk.")
    text_segment: Optional[str] = Field(default=None, description="The text segment this audio represents.")


class WakeWordMessage(BaseModel):
    """Wake word detection event."""

    detected: bool = Field(default=True, description="Whether the wake word was detected.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Detection confidence.")
    acknowledgement: Optional[str] = Field(
        default=None,
        description="Acknowledgement phrase, e.g. 'Yes sir?'.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Response Messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ResponseMessage(BaseModel):
    """Assistant's text response to a user query."""

    text: str = Field(..., description="Response text from the assistant.")
    is_partial: bool = Field(default=False, description="Whether this is a streamed partial response.")
    conversation_id: Optional[str] = Field(default=None, description="ID of the conversation.")
    token_usage: Optional[Dict[str, int]] = Field(
        default=None,
        description="Token usage stats: prompt_tokens, completion_tokens, total_tokens.",
    )

    @field_validator("conversation_id", mode="before")
    @classmethod
    def coerce_conversation_id(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class ThinkingMessage(BaseModel):
    """Emitted while the assistant is reasoning / planning."""

    text: str = Field(..., description="Current thinking/reasoning text.")
    step: Optional[int] = Field(default=None, description="Step number in reasoning chain.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Status & Error Messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class StatusMessage(BaseModel):
    """Current state of the voice assistant pipeline."""

    state: AssistantState = Field(..., description="Current assistant state.")
    message: Optional[str] = Field(default=None, description="Human-readable status description.")


class ErrorMessage(BaseModel):
    """Error details sent to the client."""

    error: str = Field(..., description="Error message.")
    code: Optional[str] = Field(default=None, description="Machine-readable error code.")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error context.")
    recoverable: bool = Field(default=True, description="Whether the client can recover from this error.")


class SystemStatus(BaseModel):
    """Overall system health and status information."""

    services: Dict[str, bool] = Field(
        default_factory=dict,
        description="Map of service name → healthy (True/False).",
    )
    uptime: float = Field(default=0.0, description="Server uptime in seconds.")
    active_connections: int = Field(default=0, description="Number of active WebSocket connections.")
    version: str = Field(default="1.0.0", description="Application version.")
    state: AssistantState = Field(default=AssistantState.IDLE, description="Current assistant state.")


class RuntimeDiagnostics(BaseModel):
    """
    Authoritative runtime configuration and diagnostic model.
    Derives actual active provider and model; never exposes API keys or secrets.
    """

    provider: str = Field(default="unknown", description="Active LLM provider (e.g. gemini, ollama, openai, openrouter, groq, nvidia).")
    model: str = Field(default="unknown", description="Active model identifier.")
    stt_status: str = Field(default="offline", description="Speech-to-text service status.")
    stt_model: Optional[str] = Field(default=None, description="STT model name if loaded.")
    tts_status: str = Field(default="offline", description="Text-to-speech service status.")
    tts_voice: Optional[str] = Field(default=None, description="TTS voice name.")
    wake_word_status: str = Field(default="offline", description="Wake-word service status.")
    wake_word_engine: Optional[str] = Field(default=None, description="Wake-word engine name.")
    automation_status: str = Field(default="offline", description="Desktop automation service status.")
    browser_status: str = Field(default="offline", description="Browser automation service status.")
    screen_status: str = Field(default="offline", description="Screen capture and perception status.")
    memory_status: str = Field(default="offline", description="Long-term memory service status.")
    backend_version: str = Field(default="1.0.0", description="Backend semantic version.")
    uptime: float = Field(default=0.0, description="Uptime in seconds.")
    active_connections: int = Field(default=0, description="Active WebSocket client connections.")
    platform: str = Field(default=sys.platform, description="Host operating system.")
    services: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-service status dictionary without credentials."
    )


RuntimeDiagnosticsModel = RuntimeDiagnostics



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Command Messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class UserCommand(BaseModel):
    """Text command submitted by the user (non-voice input)."""

    text: str = Field(..., min_length=1, description="The command text.")
    conversation_id: Optional[str] = Field(default=None, description="Conversation context ID.")

    @field_validator("conversation_id", mode="before")
    @classmethod
    def coerce_conversation_id(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class CommandResult(BaseModel):
    """Result of executing a system command or tool call."""

    command: str = Field(..., description="The command that was executed.")
    result: str = Field(..., description="Execution result or output.")
    status: str = Field(default="success", description="Outcome: success | error | blocked.")
    execution_time_ms: Optional[float] = Field(default=None, description="Execution time in milliseconds.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Agent / Task Messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgentStep(BaseModel):
    """A single step in an agent's task plan."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Step ID.")
    description: str = Field(..., description="Human-readable description of the step.")
    tool_name: Optional[str] = Field(default=None, description="Tool to be invoked.")
    tool_args: Optional[Dict[str, Any]] = Field(default=None, description="Arguments for the tool.")
    status: AgentStepStatus = Field(default=AgentStepStatus.PENDING, description="Step status.")
    result: Optional[str] = Field(default=None, description="Step execution result.")
    error: Optional[str] = Field(default=None, description="Error message if step failed.")
    started_at: Optional[datetime] = Field(default=None, description="When step execution began.")
    completed_at: Optional[datetime] = Field(default=None, description="When step execution ended.")


class AgentTask(BaseModel):
    """A multi-step task being executed by the planner agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Task ID.")
    description: str = Field(..., description="High-level task description.")
    steps: List[AgentStep] = Field(default_factory=list, description="Ordered list of steps.")
    status: AgentStepStatus = Field(default=AgentStepStatus.PENDING, description="Overall task status.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Task creation timestamp.",
    )
    completed_at: Optional[datetime] = Field(default=None, description="Task completion timestamp.")


class AgentProgressMessage(BaseModel):
    """Progress update emitted while the agent executes a task."""

    task_id: str = Field(..., description="ID of the parent task.")
    step_index: int = Field(..., description="Index of the current step (0-based).")
    total_steps: int = Field(..., description="Total number of steps in the task.")
    step_description: str = Field(..., description="Description of the current step.")
    step_status: AgentStepStatus = Field(..., description="Status of the current step.")
    result: Optional[str] = Field(default=None, description="Step result, if completed.")
    error: Optional[str] = Field(default=None, description="Error details, if failed.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Conversation Messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ConversationMessage(BaseModel):
    """A single message in a conversation history."""

    role: MessageRole = Field(..., description="Message author role.")
    content: str = Field(..., description="Message content.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the message was created.",
    )
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Tool calls made in this message (assistant role only).",
    )
    tool_call_id: Optional[str] = Field(
        default=None,
        description="ID of the tool call this message responds to (tool role only).",
    )
    name: Optional[str] = Field(
        default=None,
        description="Name of the tool function (tool role only).",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Live Mode Perception & Visual Synchronizer Messages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class LiveModeStatusMessage(BaseModel):
    """Real-time status and active window perception frame for Live Mode visual synchronization."""

    is_active: bool = Field(..., description="Whether Live Mode is active.")
    active_app: str = Field(default="Desktop", description="Currently focused application.")
    window_title: str = Field(default="Desktop Workspace", description="Title of the active foreground window.")
    window_bounds: Optional[Dict[str, int]] = Field(default=None, description="Screen coordinates and dimensions {x, y, w, h}.")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of status update.")

