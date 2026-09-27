/**
 * JARVIS AI Operating System - Strict V1 WebSocket Protocol Specification.
 *
 * Defines versioned, strictly-typed message envelopes and discriminated unions
 * for real-time bidirectional communication between JARVIS Core and clients
 * (Desktop Electron and Mobile Companion).
 *
 * Strictly typed with zero `any` usage.
 */

export type ProtocolVersion = '1';

export type AssistantState =
  | 'sleeping'
  | 'idle'
  | 'wake_word_detected'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'executing'
  | 'interrupted'
  | 'error';

export type AgentStepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface BaseProtocolEnvelope {
  version: ProtocolVersion;
  id?: string;
  msg_id?: number;
  request_id?: string;
  session_id?: string;
  timestamp: string;
}

/* ─────────────────────────────────────────────────────────────────────────────
   Server -> Client Discriminated Union Messages
───────────────────────────────────────────────────────────────────────────── */

export interface StatusServerMessage extends BaseProtocolEnvelope {
  type: 'status';
  data: {
    state: AssistantState;
    message?: string;
    client_id?: string;
    task_queue?: Record<string, unknown>;
  };
}

export interface ResponseServerMessage extends BaseProtocolEnvelope {
  type: 'response';
  data: {
    text: string;
    is_partial?: boolean;
    conversation_id?: string;
    action?: string;
    token_usage?: {
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
    };
  };
}

export interface ThinkingServerMessage extends BaseProtocolEnvelope {
  type: 'thinking';
  data: {
    text: string;
    step?: number;
  };
}

export interface AgentProgressServerMessage extends BaseProtocolEnvelope {
  type: 'agent_progress';
  data: {
    task_id: string;
    step_index: number;
    total_steps: number;
    step_description: string;
    step_status: AgentStepStatus;
    result?: string;
    error?: string;
  };
}

export interface TranscriptServerMessage extends BaseProtocolEnvelope {
  type: 'transcript';
  data: {
    text: string;
    confidence?: number;
    is_partial?: boolean;
    language?: string;
  };
}

export interface TTSAudioServerMessage extends BaseProtocolEnvelope {
  type: 'tts_audio';
  data: {
    audio?: string;
    audio_bytes?: string;
    format: string;
    is_final: boolean;
    text_segment?: string;
  };
}

export interface WakeWordServerMessage extends BaseProtocolEnvelope {
  type: 'wake_word';
  data: {
    detected: boolean;
    confidence: number;
    acknowledgement?: string;
  };
}

export interface ErrorServerMessage extends BaseProtocolEnvelope {
  type: 'error';
  data: {
    error?: string;
    message?: string;
    code?: string;
    details?: Record<string, unknown>;
    recoverable?: boolean;
  };
}

export interface AckServerMessage extends BaseProtocolEnvelope {
  type: 'ack';
  data: {
    received?: string;
    msg_id?: number;
  };
}

export interface PongServerMessage extends BaseProtocolEnvelope {
  type: 'pong';
  data: {
    timestamp: number;
  };
}

export interface LiveModeServerMessage extends BaseProtocolEnvelope {
  type: 'live_mode_status';
  data: {
    is_active: boolean;
    active_app: string;
    window_title: string;
    window_bounds?: {
      x: number;
      y: number;
      w: number;
      h: number;
    } | null;
    timestamp: number;
  };
}

export interface TelemetryServerMessage extends BaseProtocolEnvelope {
  type: 'telemetry';
  data: {
    timestamp: number;
    cpu_percent: number;
    ram_percent: number;
    ram_used_gb: number;
    ram_total_gb: number;
    gpu_percent: number;
    gpu_memory_used_mb?: number;
    disk_percent?: number;
    temperature?: number | null;
    battery_percent?: number | null;
    battery_plugged?: boolean | null;
    active_task: string;
    active_workflow: string;
    active_llm_provider: string;
    assistant_state: string;
    internet_connected: boolean;
    current_app?: string;
    current_window?: string;
    last_command?: string;
    planner_status?: string;
    voice_status?: string;
    memory_usage_mb?: number;
    active_agents_count?: number;
  };
}

export interface ApprovalRequestServerMessage extends BaseProtocolEnvelope {
  type: 'approval_request';
  data: {
    approval_id: string;
    action_type: string;
    description: string;
    dangerous_target: string;
    timestamp: number;
    timeout_seconds: number;
    challenge: string;
  };
}

export type ServerMessage =
  | StatusServerMessage
  | ResponseServerMessage
  | ThinkingServerMessage
  | AgentProgressServerMessage
  | TranscriptServerMessage
  | TTSAudioServerMessage
  | WakeWordServerMessage
  | ErrorServerMessage
  | AckServerMessage
  | PongServerMessage
  | LiveModeServerMessage
  | TelemetryServerMessage
  | ApprovalRequestServerMessage;

/* ─────────────────────────────────────────────────────────────────────────────
   Client -> Server Discriminated Union Messages
───────────────────────────────────────────────────────────────────────────── */

export interface ClientCommandMessage {
  version: ProtocolVersion;
  type: 'command' | 'text_command';
  request_id: string;
  session_id?: string;
  data: {
    text: string;
    conversation_id?: string | number | null;
  };
}

export interface ClientPushToTalkStartMessage {
  version: ProtocolVersion;
  type: 'push_to_talk_start';
  request_id: string;
  session_id?: string;
  data?: Record<string, unknown>;
}

export interface ClientPushToTalkStopMessage {
  version: ProtocolVersion;
  type: 'push_to_talk_stop';
  request_id: string;
  session_id?: string;
  data?: Record<string, unknown>;
}

export interface ClientInterruptMessage {
  version: ProtocolVersion;
  type: 'interrupt';
  request_id: string;
  session_id?: string;
  data?: Record<string, unknown>;
}

export interface ClientPingMessage {
  version: ProtocolVersion;
  type: 'ping' | 'heartbeat';
  request_id: string;
  session_id?: string;
  data?: {
    timestamp: number;
  };
}

export interface ClientAckMessage {
  version: ProtocolVersion;
  type: 'ack';
  request_id?: string;
  session_id?: string;
  msg_id: number;
  data?: Record<string, unknown>;
}

export interface ClientAudioDataMessage {
  version: ProtocolVersion;
  type: 'audio_data';
  request_id: string;
  session_id?: string;
  data: {
    audio: string; // base64 encoded audio
    format?: string;
  };
}

export interface ClientHandActionMessage {
  version: ProtocolVersion;
  type: 'hand_action';
  request_id: string;
  session_id?: string;
  data: {
    action: 'move' | 'click' | 'mouse_click' | 'scroll' | 'keyboard';
    x?: number;
    y?: number;
    norm_x?: number;
    norm_y?: number;
    button?: 'left' | 'right' | 'middle';
    click_action?: 'click' | 'down' | 'up' | 'double';
    direction?: 'up' | 'down';
    amount?: number;
    keyboard_action?: string;
    target_monitor?: string | number;
  };
}

export type ClientMessage =
  | ClientCommandMessage
  | ClientPushToTalkStartMessage
  | ClientPushToTalkStopMessage
  | ClientInterruptMessage
  | ClientPingMessage
  | ClientAckMessage
  | ClientAudioDataMessage
  | ClientHandActionMessage;

/* ─────────────────────────────────────────────────────────────────────────────
   Authoritative Runtime Diagnostics Interface
───────────────────────────────────────────────────────────────────────────── */

export interface RuntimeDiagnostics {
  status: 'ok' | 'error' | 'degraded';
  provider: string;
  model: string;
  stt_status: string;
  stt_model?: string | null;
  tts_status: string;
  tts_voice?: string | null;
  wake_word_status: string;
  wake_word_engine?: string | null;
  automation_status: string;
  browser_status: string;
  screen_status: string;
  memory_status: string;
  backend_version: string;
  uptime: number;
  active_connections: number;
  platform: string;
  services?: Record<string, { status: string; model?: string; provider?: string }>;
}
