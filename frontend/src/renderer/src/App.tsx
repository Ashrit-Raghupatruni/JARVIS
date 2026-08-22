import { useEffect, useCallback, useState, useRef } from 'react'
import { useAppStore } from './stores/appStore'
import { useWebSocket } from './hooks/useWebSocket'
import { useAudio } from './hooks/useAudio'
import DashboardLayout from './components/DashboardLayout'
import SiriWidget from './components/SiriWidget'
import { FaceLockScreen } from './components/FaceLockScreen'
import { WindowSpotlightOverlay } from './components/WindowSpotlightOverlay'
import type { HandTracker } from './lib/handTracker'

export default function App() {
  const {
    assistantState,
    isConnected,
    currentTask,
    showSettings,
    audioLevel,
    settings,
    liveModeStatus,
  } = useAppStore()

  // Detect if this is the Siri widget overlay window
  const isSiriWidget = window.location.hash === '#siri'

  const sendAudioRef = useRef<(data: ArrayBuffer) => void>(() => {})
  const { playAudioChunk, startMicCapture, stopMicCapture, stopPlayback, isCapturing } = useAudio((data) => sendAudioRef.current(data))
  const { sendMessage, sendAudio } = useWebSocket(playAudioChunk)

  useEffect(() => {
    sendAudioRef.current = sendAudio
  }, [sendAudio])

  const [showChat, setShowChat] = useState(true)
  const [showHistory, setShowHistory] = useState(false)

  // Sync state with Electron main process (so SiriWidget gets updates)
  useEffect(() => {
    if (isSiriWidget) return // Don't loop state updates back

    const api = (window as any).electronAPI
    if (api?.sendStateUpdate) {
      api.sendStateUpdate(assistantState, audioLevel)
    }
  }, [assistantState, audioLevel, isSiriWidget])

  // Stop TTS playback when assistant transitions away from speaking state
  useEffect(() => {
    if (assistantState !== 'speaking') {
      stopPlayback()
    }
  }, [assistantState, stopPlayback])

  // Handle push-to-talk from Electron
  useEffect(() => {
    const api = (window as any).electronAPI
    if (api?.onPushToTalk) {
      const unsubscribe = api.onPushToTalk(async () => {
        // Toggle listening state on Ctrl+Space shortcut
        const store = useAppStore.getState()
        if (store.assistantState === 'idle') {
          try {
            await startMicCapture()
            sendMessage('push_to_talk_start', {})
          } catch (err) {
            console.error('[App] Mic capture failed on PTT:', err)
          }
        } else {
          stopMicCapture()
          sendMessage('push_to_talk_stop', {})
        }
      })
      return unsubscribe
    }
    return undefined
  }, [sendMessage, startMicCapture, stopMicCapture])

  // Start mic capture when listening or if wake word detection is enabled
  useEffect(() => {
    const wakeWordEnabled = settings?.voice?.wakeWordEnabled ?? true
    if (assistantState === 'listening' || assistantState === 'wake_word_detected' || wakeWordEnabled) {
      if (!isCapturing) {
        startMicCapture().catch((err) => {
          console.error('[App] Failed to start mic for listening/wake word:', err)
        })
      }
    } else {
      if (isCapturing) {
        stopMicCapture()
      }
    }
  }, [assistantState, isCapturing, startMicCapture, stopMicCapture, settings?.voice?.wakeWordEnabled])

  const handleOrbClick = useCallback(async () => {
    if (assistantState === 'idle' || assistantState === 'sleeping' || assistantState === 'error') {
      try {
        await startMicCapture()
        sendMessage('push_to_talk_start', {})
      } catch (err) {
        console.error('[App] Microphone access failed:', err)
      }
    } else if (assistantState === 'listening') {
      stopMicCapture()
      sendMessage('push_to_talk_stop', {})
    } else if (assistantState === 'speaking') {
      sendMessage('interrupt', {})
    }
  }, [assistantState, sendMessage, startMicCapture, stopMicCapture])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+Space: Toggle mic / voice command trigger
      if ((e.ctrlKey && e.code === 'Space') || (e.ctrlKey && e.key === ' ')) {
        e.preventDefault()
        handleOrbClick()
      }
      // Ctrl+Shift+H: Toggle chat panel
      if (e.ctrlKey && e.shiftKey && e.key === 'H') {
        e.preventDefault()
        setShowChat((prev) => !prev)
      }
      // Ctrl+Shift+L: Toggle command history
      if (e.ctrlKey && e.shiftKey && e.key === 'L') {
        e.preventDefault()
        setShowHistory((prev) => !prev)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleOrbClick])

  const isActive =
    assistantState === 'listening' ||
    assistantState === 'processing' ||
    assistantState === 'speaking'

  const isSerious = Boolean(settings?.voice?.seriousMode)

  const [isLocked, setIsLocked] = useState(true)

  // ── Laptop-Wide Global Hand Gesture Tracking Runner ───────────────
  const globalVideoRef = useRef<HTMLVideoElement>(null)
  const globalCanvasRef = useRef<HTMLCanvasElement>(null)
  const globalTrackerRef = useRef<HandTracker | null>(null)
  const handControlEnabled = Boolean(settings?.handControl?.enabled)

  useEffect(() => {
    if (isSiriWidget || isLocked || !handControlEnabled) {
      if (globalTrackerRef.current) {
        globalTrackerRef.current.stop()
        globalTrackerRef.current = null
      }
      return
    }

    const video = globalVideoRef.current
    const canvas = globalCanvasRef.current
    if (!video || !canvas) return

    import('./lib/handTracker').then(({ HandTracker }) => {
      const tracker = new HandTracker(video, canvas, {
        onHandAction: (action, params) => {
          if (action === 'click') {
            sendMessage('hand_action', {
              action: 'click',
              click_action: params.action || 'click',
              button: params.button || 'left'
            })
          } else {
            sendMessage('hand_action', { action, ...params })
          }
        }
      })

      tracker.updateConfigs(settings.handControl)
      tracker.start().then(() => {
        globalTrackerRef.current = tracker
        console.log('[App] Laptop-Wide Global Hand Control Active')
      }).catch((err) => {
        console.error('[App] Global Hand Tracker notice:', err)
      })
    })

    return () => {
      if (globalTrackerRef.current) {
        globalTrackerRef.current.stop()
        globalTrackerRef.current = null
      }
    }
  }, [handControlEnabled, isLocked, isSiriWidget, sendMessage, settings?.handControl])

  // If this window is the Siri widget overlay, render ONLY the Siri visualizer
  if (isSiriWidget) {
    return (
      <div className={`h-screen w-screen bg-transparent overflow-hidden ${isSerious ? 'serious-mode' : ''}`}>
        <SiriWidget />
      </div>
    )
  }

  // Intercept application mount with Cybernetic Face Identity Lock Screen
  if (isLocked) {
    return <FaceLockScreen onUnlock={() => setIsLocked(false)} />
  }

  const isLiveActive = Boolean(liveModeStatus?.isActive)

  return (
    <div
      className={`h-screen w-screen relative overflow-hidden transition-all duration-300 ${
        isLiveActive ? 'bg-slate-950/75 backdrop-blur-md' : ''
      } ${isSerious ? 'serious-mode' : ''}`}
    >
      {/* Live Mode Focused Window High-Contrast Spotlight Overlay */}
      <WindowSpotlightOverlay />

      {/* Background hidden video & canvas elements for laptop-wide hand gesture tracking */}
      <video ref={globalVideoRef} playsInline muted autoPlay className="fixed top-0 left-0 w-1 h-1 opacity-0 pointer-events-none -z-50" />
      <canvas ref={globalCanvasRef} width={320} height={240} className="fixed top-0 left-0 w-1 h-1 opacity-0 pointer-events-none -z-50" />

      {isSerious && <div className="absolute inset-0 serious-scanlines z-50 pointer-events-none" />}
      <DashboardLayout
        onSendMessage={(text) => {
          const activeId = useAppStore.getState().activeConversationId
          sendMessage('text_command', { text, conversation_id: activeId })
        }}
        onOrbClick={handleOrbClick}
      />
    </div>
  )
}
