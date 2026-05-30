/* ===== Assistant State ===== */
export type AssistantState =
  | 'idle'
  | 'wake_word_detected'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'executing'

/* ===== WebSocket Message Types ===== */
export type WSMessageType =
  | 'audio_data'
  | 'transcript'
  | 'response'
  | 'tts_audio'
  | 'status'
  | 'command_result'
  | 'error'
  | 'wake_word'
  | 'thinking'
  | 'agent_progress'
  | 'heartbeat'
  | 'push_to_talk_start'
  | 'push_to_talk_stop'

export interface WSMessage {
  type: WSMessageType
  data: Record<string, unknown>
  timestamp: string
}

export interface TranscriptMessage {
  type: 'transcript'
  data: {
    text: string
    is_final: boolean
  }
  timestamp: string
}

export interface ResponseMessage {
  type: 'response'
  data: {
    text: string
    action?: string
    metadata?: Record<string, unknown>
  }
  timestamp: string
}

export interface StatusMessage {
  type: 'status'
  data: {
    state: AssistantState
    message?: string
  }
  timestamp: string
}

export interface TTSAudioMessage {
  type: 'tts_audio'
  data: {
    audio: string // base64 encoded audio chunk
    format: string
    is_final: boolean
  }
  timestamp: string
}

export interface ErrorMessage {
  type: 'error'
  data: {
    code: string
    message: string
    details?: string
  }
  timestamp: string
}

export interface ThinkingMessage {
  type: 'thinking'
  data: {
    text: string
  }
  timestamp: string
}

export interface AgentProgressMessage {
  type: 'agent_progress'
  data: {
    task: string
    step: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    progress?: number
    steps?: AgentStep[]
  }
  timestamp: string
}

export interface CommandResultMessage {
  type: 'command_result'
  data: {
    command: string
    result: string
    success: boolean
    timestamp: string
  }
  timestamp: string
}

export interface WakeWordMessage {
  type: 'wake_word'
  data: {
    confidence: number
  }
  timestamp: string
}

/* ===== Conversation ===== */
export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

/* ===== Agent / Task ===== */
export interface AgentStep {
  id: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  result?: string
}

export interface CurrentTask {
  description: string
  steps: AgentStep[]
  progress: number
}

/* ===== Command History ===== */
export interface CommandEntry {
  id: string
  command: string
  result: string
  success: boolean
  timestamp: string
}

/* ===== Settings ===== */
export interface Settings {
  voice: {
    ttsVoice: string
    speechRate: number
    wakeWordEnabled: boolean
  }
  ai: {
    model: string
    temperature: number
  }
  display: {
    alwaysOnTop: boolean
    theme: 'dark' | 'light'
  }
}

/* ===== Electron API (preload bridge) ===== */
export interface ElectronAPI {
  minimize: () => Promise<void>
  maximize: () => Promise<void>
  close: () => Promise<void>
  isMaximized: () => Promise<boolean>
  getSystemInfo: () => Promise<{
    platform: string
    arch: string
    version: string
    electron: string
    node: string
    chrome: string
  }>
  showNotification: (title: string, body: string) => Promise<void>
  onPushToTalk: (callback: () => void) => () => void
  onWindowStateChanged: (callback: (state: { isMaximized: boolean }) => void) => () => void
  onOpenSettings: (callback: () => void) => () => void
  platform: string
}

/* ===== Global Window Augmentation ===== */
declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}
