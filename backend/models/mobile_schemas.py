"""
JARVIS AI Operating System - Mobile Companion Pydantic Schemas.

Defines request and response data models for device pairing, authentication,
telemetry streaming, remote desktop commands, security approvals, file operations, and screen previews.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class PairingInitiateRequest(BaseModel):
    device_name: str = Field(..., description="Friendly device name (e.g., Ashrit's Android Phone)")
    device_id: str = Field(..., description="Unique client hardware UUID")
    client_public_key: Optional[str] = Field(None, description="Client Ed25519/RSA public key")


class PairingInitiateResponse(BaseModel):
    pairing_session_id: str
    pairing_code: str
    server_public_key: str
    nonce: Optional[str] = None
    server_signature: Optional[str] = None
    expires_in_seconds: int = 300


class PairingConfirmRequest(BaseModel):
    pairing_session_id: str
    pairing_code: str
    device_id: str
    client_public_key: Optional[str] = None
    client_signature: Optional[str] = None


class PairingConfirmResponse(BaseModel):
    status: str
    access_token: str
    token_type: str = "bearer"
    device_id: str
    friendly_name: str


class DeviceInfo(BaseModel):
    device_id: str
    friendly_name: str
    registered_at: float
    last_active: float
    trusted: bool = True
    is_online: bool = False


class SystemTelemetry(BaseModel):
    timestamp: float
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    gpu_percent: float
    gpu_memory_used_mb: float = 0.0
    disk_percent: float = 0.0
    temperature: Optional[float] = None
    battery_percent: Optional[float] = None
    battery_plugged: Optional[bool] = None
    active_task: str = "System Idle"
    active_workflow: str = "None"
    active_llm_provider: str = "Ollama Local"
    assistant_state: str = "idle"
    internet_connected: bool = True
    current_app: str = "Desktop"
    current_window: str = "General Workspace"
    last_command: str = "None"
    planner_status: str = "Idle"
    voice_status: str = "Listening"
    memory_usage_mb: float = 0.0
    active_agents_count: int = 0


class RemoteCommandRequest(BaseModel):
    command: str = Field(..., description="Command type: shutdown, restart, sleep, lock, open_app, cancel_task, restart_backend")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)


class MobileApprovalRequest(BaseModel):
    approval_id: str
    action_type: str
    description: str
    dangerous_target: str
    timestamp: float
    timeout_seconds: float = 30.0


class MobileApprovalDecision(BaseModel):
    approval_id: str
    decision: str = Field(..., description="approve, deny, always_allow, always_deny")
    biometric_authenticated: bool = Field(False, description="Whether device biometric hardware (fingerprint/Face ID) verified the user")
    biometric_signature: Optional[str] = Field(None, description="Optional cryptographic biometric proof or hardware token")



class ScreenPreviewResponse(BaseModel):
    timestamp: float
    width: int
    height: int
    image_base64: str
    active_window_title: str
