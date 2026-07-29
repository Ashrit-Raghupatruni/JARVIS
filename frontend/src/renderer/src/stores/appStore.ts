import { create } from 'zustand'
import type {
  AssistantState,
  ConversationMessage,
  CurrentTask,
  AgentStep,
  CommandEntry,
  Settings
} from '../types'

interface AppState {
  /* ----- Core State ----- */
  assistantState: AssistantState
  isConnected: boolean
  messages: ConversationMessage[]
  currentTranscript: string
  isListening: boolean
  isSpeaking: boolean
  audioLevel: number
  currentTask: CurrentTask | null
  commandHistory: CommandEntry[]
  screenPreview: string | null
  pushToTalkActive: boolean
  is3DRotationEnabled: boolean

  /* ----- UI State ----- */
  showSettings: boolean
  showChat: boolean
  showCommandHistory: boolean
  isWindowMaximized: boolean
  thinkingText: string

  /* ----- Settings ----- */
  settings: Settings

  /* ----- Core Actions ----- */
  setAssistantState: (state: AssistantState) => void
  setConnected: (connected: boolean) => void
  addMessage: (message: ConversationMessage) => void
  clearMessages: () => void
  setCurrentTranscript: (transcript: string) => void
  setListening: (listening: boolean) => void
  setSpeaking: (speaking: boolean) => void
  setAudioLevel: (level: number) => void
  setCurrentTask: (task: CurrentTask | null) => void
  updateTaskStep: (stepId: string, status: AgentStep['status'], result?: string) => void
  addCommandEntry: (entry: CommandEntry) => void
  setScreenPreview: (preview: string | null) => void
  setPushToTalkActive: (active: boolean) => void
  setThinkingText: (text: string) => void

  /* ----- UI Actions ----- */
  toggle3DRotation: () => void
  toggleSettings: () => void
  setShowSettings: (show: boolean) => void
  toggleChat: () => void
  toggleCommandHistory: () => void
  setWindowMaximized: (maximized: boolean) => void

  /* ----- Settings Actions ----- */
  updateSettings: (settings: Partial<Settings>) => void
  updateVoiceSettings: (voice: Partial<Settings['voice']>) => void
  updateAISettings: (ai: Partial<Settings['ai']>) => void
  updateDisplaySettings: (display: Partial<Settings['display']>) => void
}

const defaultSettings: Settings = {
  voice: {
    ttsVoice: 'en-GB-RyanNeural',
    speechRate: 1.0,
    wakeWordEnabled: true,
    wakeWord: 'hey_jarvis',
    wakeWordSensitivity: 0.5,
    clapEnabled: true,
    clapMode: 'double',
    clapSensitivity: 0.7,
    micSensitivity: 0.8,
    bargeInEnabled: true,
    bargeInSensitivity: 0.7,
    seriousMode: false,
  },
  ai: {
    model: 'qwen2.5-coder:3b',
    temperature: 0.7,
    openrouterApiKey: '',
    openaiApiKey: ''
  },
  display: {
    alwaysOnTop: false,
    theme: 'dark',
    selectedMonitor: 'all'
  }
}

export const useAppStore = create<AppState>((set) => ({
  /* ----- Initial State ----- */
  assistantState: 'idle',
  isConnected: false,
  messages: [],
  currentTranscript: '',
  isListening: false,
  isSpeaking: false,
  audioLevel: 0,
  currentTask: null,
  commandHistory: [],
  screenPreview: null,
  pushToTalkActive: false,
  is3DRotationEnabled: true,
  showSettings: false,
  showChat: true,
  showCommandHistory: false,
  isWindowMaximized: false,
  thinkingText: '',
  settings: defaultSettings,

  /* ----- Core Actions ----- */
  setAssistantState: (assistantState) => set({ assistantState }),

  setConnected: (isConnected) => set({ isConnected }),

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message]
    })),

  clearMessages: () => set({ messages: [] }),

  setCurrentTranscript: (currentTranscript) => set({ currentTranscript }),

  setListening: (isListening) => set({ isListening }),

  setSpeaking: (isSpeaking) => set({ isSpeaking }),

  setAudioLevel: (audioLevel) => set({ audioLevel: Math.max(0, Math.min(1, audioLevel)) }),

  setCurrentTask: (currentTask) => set({ currentTask }),

  updateTaskStep: (stepId, status, result) =>
    set((state) => {
      if (!state.currentTask) return {}
      const updatedSteps = state.currentTask.steps.map((step) =>
        step.id === stepId ? { ...step, status, result: result ?? step.result } : step
      )
      const completedCount = updatedSteps.filter(
        (s) => s.status === 'completed' || s.status === 'failed'
      ).length
      const progress = updatedSteps.length > 0 ? completedCount / updatedSteps.length : 0
      return {
        currentTask: {
          ...state.currentTask,
          steps: updatedSteps,
          progress
        }
      }
    }),

  addCommandEntry: (entry) =>
    set((state) => ({
      commandHistory: [entry, ...state.commandHistory].slice(0, 50) // Keep last 50
    })),

  setScreenPreview: (screenPreview) => set({ screenPreview }),

  setPushToTalkActive: (pushToTalkActive) => set({ pushToTalkActive }),

  setThinkingText: (thinkingText) => set({ thinkingText }),

  /* ----- UI Actions ----- */
  toggle3DRotation: () => set((state) => ({ is3DRotationEnabled: !state.is3DRotationEnabled })),
  toggleSettings: () => set((state) => ({ showSettings: !state.showSettings })),

  setShowSettings: (showSettings) => set({ showSettings }),

  toggleChat: () => set((state) => ({ showChat: !state.showChat })),

  toggleCommandHistory: () =>
    set((state) => ({ showCommandHistory: !state.showCommandHistory })),

  setWindowMaximized: (isWindowMaximized) => set({ isWindowMaximized }),

  /* ----- Settings Actions ----- */
  updateSettings: (newSettings) =>
    set((state) => ({
      settings: { ...state.settings, ...newSettings }
    })),

  updateVoiceSettings: (voice) =>
    set((state) => ({
      settings: {
        ...state.settings,
        voice: { ...state.settings.voice, ...voice }
      }
    })),

  updateAISettings: (ai) =>
    set((state) => ({
      settings: {
        ...state.settings,
        ai: { ...state.settings.ai, ...ai }
      }
    })),

  updateDisplaySettings: (display) =>
    set((state) => ({
      settings: {
        ...state.settings,
        display: { ...state.settings.display, ...display }
      }
    }))
}))
