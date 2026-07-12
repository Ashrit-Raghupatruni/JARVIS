import { useEffect, useRef, useCallback } from 'react'
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

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 9)
}

interface UseWebSocketReturn {
  sendMessage: (type: string, data: Record<string, unknown>) => void
  sendAudio: (audioData: ArrayBuffer) => void
  reconnect: () => void
  disconnect: () => void
}

// Shared global WebSocket connection state
let globalWs: WebSocket | null = null
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
let heartbeatInterval: ReturnType<typeof setInterval> | null = null
let reconnectDelay = INITIAL_RECONNECT_DELAY
let isIntentionalClose = false
let activeHookCount = 0
let globalOnTtsAudio: ((data: ArrayBuffer) => void) | null = null

export function useWebSocket(onTtsAudio?: (data: ArrayBuffer) => void): UseWebSocketReturn {
  const {
    setConnected,
    setAssistantState,
    addMessage,
    setCurrentTranscript,
    setListening,
    setSpeaking,
    setCurrentTask,
    updateTaskStep,
    addCommandEntry,
    setThinkingText
  } = useAppStore.getState()

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
          useAppStore.getState().addMessage(assistantMsg)
          useAppStore.getState().setThinkingText('')
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
          } else if (status.data.state === 'idle') {
            useAppStore.getState().setListening(false)
            useAppStore.getState().setSpeaking(false)
            useAppStore.getState().setCurrentTranscript('')
            useAppStore.getState().setThinkingText('')
          } else if (status.data.state === 'processing') {
            useAppStore.getState().setListening(false)
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
          const _wakeWord = message as WakeWordMessage
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

        case 'heartbeat': {
          // Server heartbeat response, no action needed
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

    try {
      let port = 8000
      const api = (window as any).electronAPI
      if (api?.getSystemInfo) {
        try {
          const info = await api.getSystemInfo()
          if (info && typeof info.backendPort === 'number') {
            port = info.backendPort
          }
        } catch (err) {
          console.error('[WS] Failed to get system info for backend port:', err)
        }
      }
      const wsUrl = `ws://127.0.0.1:${port}/ws`
      console.log(`[WS] Connecting to ${wsUrl}`)
      const ws = new WebSocket(wsUrl)
      globalWs = ws

      ws.onopen = () => {
        console.log('[WS] Connected')
        useAppStore.getState().setConnected(true)
        reconnectDelay = INITIAL_RECONNECT_DELAY
        startHeartbeat()

        const api = (window as any).electronAPI
        if (api?.websocketConnected) {
          api.websocketConnected()
        }
      }

      ws.onmessage = handleMessage

      ws.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason)
        useAppStore.getState().setConnected(false)
        clearHeartbeat()

        if (!isIntentionalClose) {
          const delay = reconnectDelay
          console.log(`[WS] Reconnecting in ${delay}ms...`)
          reconnectTimeout = setTimeout(() => {
            reconnectDelay = Math.min(
              reconnectDelay * 2,
              MAX_RECONNECT_DELAY
            )
            connect()
          }, delay)
        }
      }

      ws.onerror = (error) => {
        console.error('[WS] Error:', error)
      }
    } catch (err) {
      console.error('[WS] Connection failed:', err)
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
  }, [clearHeartbeat])

  const reconnect = useCallback(() => {
    disconnect()
    isIntentionalClose = false
    reconnectDelay = INITIAL_RECONNECT_DELAY
    connect()
  }, [connect, disconnect])

  const sendMessage = useCallback((type: string, data: Record<string, unknown>) => {
    if (globalWs?.readyState === WebSocket.OPEN) {
      globalWs.send(
        JSON.stringify({
          type,
          data,
          timestamp: new Date().toISOString()
        })
      )
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
