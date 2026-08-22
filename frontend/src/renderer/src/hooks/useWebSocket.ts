import { useEffect, useCallback } from 'react'
import { useAppStore } from '../stores/appStore'
import type {
  WSMessage,
  TranscriptMessage,
  ResponseMessage,
  StatusMessage,
  ErrorMessage,
  ThinkingMessage,
  AgentProgressMessage,
  CommandResultMessage,
  WakeWordMessage,
  ConversationMessage,
  AgentStep
} from '../types'

const HEARTBEAT_INTERVAL = 30000
const MAX_RECONNECT_DELAY = 30000
const INITIAL_RECONNECT_DELAY = 1000

function playWakeChime() {
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
    if (!AudioCtx) return
    const ctx = new AudioCtx()
    
    // Tone 1: 880Hz (A5)
    const osc1 = ctx.createOscillator()
    const gain1 = ctx.createGain()
    osc1.type = 'sine'
    osc1.frequency.setValueAtTime(880, ctx.currentTime)
    gain1.gain.setValueAtTime(0.12, ctx.currentTime)
    gain1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1)
    osc1.connect(gain1)
    gain1.connect(ctx.destination)
    osc1.start(ctx.currentTime)
    osc1.stop(ctx.currentTime + 0.1)

    // Tone 2: 1320Hz (E6) - 50ms offset
    const osc2 = ctx.createOscillator()
    const gain2 = ctx.createGain()
    osc2.type = 'sine'
    osc2.frequency.setValueAtTime(1320, ctx.currentTime + 0.05)
    gain2.gain.setValueAtTime(0.15, ctx.currentTime + 0.05)
    gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.18)
    osc2.connect(gain2)
    gain2.connect(ctx.destination)
    osc2.start(ctx.currentTime + 0.05)
    osc2.stop(ctx.currentTime + 0.18)
  } catch {
    // Audio Context blocked or unavailable
  }
}

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 9)
}

interface UseWebSocketReturn {
  sendMessage: (type: string, data: Record<string, unknown>) => void
  sendAudio: (audioData: ArrayBuffer) => void
  reconnect: () => void
  disconnect: () => void
}

// Outbound message queue for delivering messages during disconnect / reconnect windows
let outgoingQueue: Array<{ type: string; data: Record<string, unknown>; timestamp: string }> = []

// Shared global WebSocket connection singletons
let globalWs: WebSocket | null = null
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
let heartbeatInterval: ReturnType<typeof setInterval> | null = null
let reconnectDelay = INITIAL_RECONNECT_DELAY
let isIntentionalClose = false
let activeHookCount = 0
let globalOnTtsAudio: ((data: ArrayBuffer) => void) | null = null

async function waitForBackendHealth(httpUrl: string, maxAttempts = 12): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const res = await fetch(`${httpUrl}/health`, { signal: AbortSignal.timeout(1000) })
      if (res.ok) return true
    } catch {
      // Backend is starting up, wait before creating WebSocket connection
    }
    await new Promise((r) => setTimeout(r, 400))
  }
  return false
}

export function useWebSocket(onTtsAudio?: (data: ArrayBuffer) => void): UseWebSocketReturn {
  // Track the most recent ttsAudio listener callback
  useEffect(() => {
    if (onTtsAudio) {
      globalOnTtsAudio = onTtsAudio
    }
    return () => {
      if (onTtsAudio && globalOnTtsAudio === onTtsAudio) {
        globalOnTtsAudio = null
      }
    }
  }, [onTtsAudio])

  const clearHeartbeat = useCallback(() => {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
      heartbeatInterval = null
    }
  }, [])

  const startHeartbeat = useCallback(() => {
    clearHeartbeat()
    heartbeatInterval = setInterval(() => {
      if (globalWs?.readyState === WebSocket.OPEN) {
        globalWs.send(
          JSON.stringify({
            type: 'heartbeat',
            data: {},
            timestamp: new Date().toISOString()
          })
        )
      }
    }, HEARTBEAT_INTERVAL)
  }, [clearHeartbeat])

  const handleMessage = useCallback((event: MessageEvent) => {
    // Handle binary audio data
    if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
      return
    }

    try {
      const message = JSON.parse(event.data as string) as WSMessage

      switch (message.type) {
        case 'transcript': {
          const transcript = message as TranscriptMessage
          useAppStore.getState().setCurrentTranscript(transcript.data.text)
          if (transcript.data.is_final) {
            const userMsg: ConversationMessage = {
              id: generateId(),
              role: 'user',
              content: transcript.data.text,
              timestamp: message.timestamp
            }
            useAppStore.getState().addMessage(userMsg)
            useAppStore.getState().setCurrentTranscript('')
          }
          break
        }

        case 'response': {
          const response = message as ResponseMessage
          const assistantMsg: ConversationMessage = {
            id: generateId(),
            role: 'assistant',
            content: response.data.text,
            timestamp: message.timestamp
          }
          const store = useAppStore.getState()
          store.addMessage(assistantMsg)
          if (response.data.conversation_id) {
            store.setActiveConversationId(response.data.conversation_id)
          }
          store.setThinkingText('')
          break
        }

        case 'serious_mode_changed': {
          const enabled = Boolean((message.data as any)?.enabled)
          const store = useAppStore.getState()
          store.updateVoiceSettings({ seriousMode: enabled })
          break
        }

        case 'hand_control_changed': {
          const enabled = Boolean((message.data as any)?.enabled)
          const store = useAppStore.getState()
          store.updateHandControlSettings({ enabled })
          break
        }

        case 'live_mode_status': {
          const data = message.data as any
          const store = useAppStore.getState()
          store.setLiveModeStatus({
            isActive: Boolean(data?.is_active),
            activeApp: data?.active_app,
            windowTitle: data?.window_title,
            windowBounds: data?.window_bounds ?? null
          })
          break
        }

        case 'clap_detected': {
          const store = useAppStore.getState()
          store.setAssistantState('wake_word_detected')
          setTimeout(() => {
            if (store.assistantState === 'wake_word_detected') {
              store.setAssistantState('listening')
            }
          }, 1000)
          break
        }

        case 'status': {
          const status = message as StatusMessage
          useAppStore.getState().setAssistantState(status.data.state)

          if (status.data.state === 'listening') {
            useAppStore.getState().setListening(true)
            useAppStore.getState().setSpeaking(false)
          } else if (status.data.state === 'speaking') {
            useAppStore.getState().setListening(false)
            useAppStore.getState().setSpeaking(true)
          } else if (status.data.state === 'sleeping' || status.data.state === 'idle') {
            useAppStore.getState().setListening(false)
            useAppStore.getState().setSpeaking(false)
            useAppStore.getState().setCurrentTranscript('')
            useAppStore.getState().setThinkingText('')
          } else if (status.data.state === 'processing') {
            useAppStore.getState().setListening(false)
          } else if (status.data.state === 'interrupted') {
            useAppStore.getState().setSpeaking(false)
            useAppStore.getState().setListening(true)
          }

          if (status.data.message) {
            const sysMsg: ConversationMessage = {
              id: generateId(),
              role: 'system',
              content: status.data.message,
              timestamp: message.timestamp
            }
            useAppStore.getState().addMessage(sysMsg)
          }
          break
        }

        case 'error': {
          const error = message as ErrorMessage
          useAppStore.getState().setAssistantState('error')
          const errorMsg: ConversationMessage = {
            id: generateId(),
            role: 'system',
            content: `Error: ${error.data.message}`,
            timestamp: message.timestamp
          }
          useAppStore.getState().addMessage(errorMsg)
          break
        }

        case 'thinking': {
          const thinking = message as ThinkingMessage
          useAppStore.getState().setThinkingText(thinking.data.text)
          break
        }

        case 'wake_word': {
          playWakeChime()
          useAppStore.getState().setAssistantState('wake_word_detected')
          setTimeout(() => {
            const store = useAppStore.getState()
            if (store.assistantState === 'wake_word_detected') {
              store.setAssistantState('listening')
            }
          }, 1200)
          break
        }

        case 'agent_progress': {
          const progress = message as AgentProgressMessage
          if (progress.data.steps) {
            useAppStore.getState().setCurrentTask({
              description: progress.data.task,
              steps: progress.data.steps,
              progress: progress.data.progress ?? 0
            })
          } else {
            const stepUpdate: AgentStep = {
              id: generateId(),
              description: progress.data.step,
              status: progress.data.status
            }
            const currentTask = useAppStore.getState().currentTask
            if (currentTask) {
              useAppStore.getState().updateTaskStep(
                stepUpdate.id,
                stepUpdate.status,
                stepUpdate.result
              )
            } else {
              useAppStore.getState().setCurrentTask({
                description: progress.data.task,
                steps: [stepUpdate],
                progress: progress.data.progress ?? 0
              })
            }
          }
          break
        }

        case 'command_result': {
          const cmdResult = message as CommandResultMessage
          useAppStore.getState().addCommandEntry({
            id: generateId(),
            command: cmdResult.data.command,
            result: cmdResult.data.result,
            success: cmdResult.data.success,
            timestamp: cmdResult.data.timestamp
          })
          break
        }

        case 'tts_audio': {
          const ttsMsg = message as any
          if (globalOnTtsAudio && ttsMsg.data?.audio) {
            try {
              const binaryString = window.atob(ttsMsg.data.audio)
              const len = binaryString.length
              const bytes = new Uint8Array(len)
              for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i)
              }
              globalOnTtsAudio(bytes.buffer)
            } catch (err) {
              console.error('[WS] Failed to decode base64 tts_audio:', err)
            }
          }
          break
        }

        case 'pong':
        case 'heartbeat': {
          break
        }

        default:
          console.log('[WS] Unknown message type:', message.type)
      }
    } catch (err) {
      console.error('[WS] Failed to parse message:', err)
    }
  }, [])

  const connect = useCallback(async () => {
    if (globalWs && (globalWs.readyState === WebSocket.OPEN || globalWs.readyState === WebSocket.CONNECTING)) {
      return
    }

    const store = useAppStore.getState()
    store.setConnectionState('connecting')

    try {
      let wsUrl: string
      let httpUrl: string
      const api = (window as any).electronAPI

      if (api?.getSystemInfo) {
        // Running inside Electron — connect directly to backend port
        let port = 8000
        try {
          const info = await api.getSystemInfo()
          if (info && typeof info.backendPort === 'number') {
            port = info.backendPort
          }
        } catch (err) {
          console.error('[WS] Failed to get system info for backend port:', err)
        }
        wsUrl = `ws://127.0.0.1:${port}/ws`
        httpUrl = `http://127.0.0.1:${port}`
      } else {
        // Running in browser — proxy /ws → backend
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const httpProto = window.location.protocol === 'https:' ? 'https:' : 'http:'
        wsUrl = `${proto}//${window.location.host}/ws`
        httpUrl = `${httpProto}//${window.location.host}`
      }

      // Poll backend health check to avoid cold-start race conditions
      await waitForBackendHealth(httpUrl, 10)

      console.log(`[WS] Connecting to ${wsUrl}`)
      const ws = new WebSocket(wsUrl)
      globalWs = ws

      ws.onopen = () => {
        console.log('[WS] Connected successfully')
        const currentStore = useAppStore.getState()
        currentStore.setConnectionState('connected')
        reconnectDelay = INITIAL_RECONNECT_DELAY
        startHeartbeat()

        // Flush outbound message queue upon connection
        if (outgoingQueue.length > 0) {
          console.log(`[WS] Connection established — flushing ${outgoingQueue.length} queued outbound message(s)...`)
          const itemsToSend = [...outgoingQueue]
          outgoingQueue = []
          currentStore.setQueuedMessageCount(0)

          for (const item of itemsToSend) {
            try {
              ws.send(JSON.stringify(item))
            } catch (err) {
              console.error('[WS] Error flushing queued message:', err)
            }
          }
        }

        const api = (window as any).electronAPI
        if (api?.websocketConnected) {
          api.websocketConnected()
        }
      }

      ws.onmessage = handleMessage

      ws.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason)
        const currentStore = useAppStore.getState()
        
        if (!isIntentionalClose) {
          currentStore.setConnectionState('reconnecting')
          clearHeartbeat()

          const delay = reconnectDelay
          console.log(`[WS] Reconnecting in ${delay}ms...`)
          reconnectTimeout = setTimeout(() => {
            reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY)
            connect()
          }, delay)
        } else {
          currentStore.setConnectionState('disconnected')
          clearHeartbeat()
        }
      }

      ws.onerror = (error) => {
        console.error('[WS] Error:', error)
      }
    } catch (err) {
      console.error('[WS] Connection failed:', err)
      const currentStore = useAppStore.getState()
      currentStore.setConnectionState('disconnected')
    }
  }, [handleMessage, startHeartbeat, clearHeartbeat])

  const disconnect = useCallback(() => {
    isIntentionalClose = true
    clearHeartbeat()
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    if (globalWs) {
      globalWs.close()
      globalWs = null
    }
    useAppStore.getState().setConnectionState('disconnected')
  }, [clearHeartbeat])

  const reconnect = useCallback(() => {
    disconnect()
    isIntentionalClose = false
    reconnectDelay = INITIAL_RECONNECT_DELAY
    connect()
  }, [connect, disconnect])

  const sendMessage = useCallback((type: string, data: Record<string, unknown>) => {
    const payload = {
      type,
      data,
      timestamp: new Date().toISOString()
    }

    if (globalWs?.readyState === WebSocket.OPEN) {
      globalWs.send(JSON.stringify(payload))
    } else {
      outgoingQueue.push(payload)
      const store = useAppStore.getState()
      store.setQueuedMessageCount(outgoingQueue.length)
      console.log(`[WS] WebSocket not OPEN. Message queued (${outgoingQueue.length} pending):`, payload)

      if (type === 'text_command' && data.text) {
        const queueNotice: ConversationMessage = {
          id: generateId(),
          role: 'system',
          content: `[WS Queue] Connection re-establishing — your message "${data.text}" is queued and will send automatically upon connection.`,
          timestamp: payload.timestamp
        }
        store.addMessage(queueNotice)
      }
    }
  }, [])

  const sendAudio = useCallback((audioData: ArrayBuffer) => {
    if (globalWs?.readyState === WebSocket.OPEN) {
      globalWs.send(audioData)
    }
  }, [])

  // Connect on mount, disconnect on unmount (via reference counting)
  useEffect(() => {
    activeHookCount++
    if (activeHookCount === 1) {
      isIntentionalClose = false
      connect()
    }

    return () => {
      activeHookCount--
      if (activeHookCount === 0) {
        disconnect()
      }
    }
  }, [connect, disconnect])

  return { sendMessage, sendAudio, reconnect, disconnect }
}
