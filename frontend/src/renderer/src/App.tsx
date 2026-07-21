import { useEffect, useCallback, useState, useRef } from 'react'
import { useAppStore } from './stores/appStore'
import { useWebSocket } from './hooks/useWebSocket'
import { useAudio } from './hooks/useAudio'
import DashboardLayout from './components/DashboardLayout'
import SiriWidget from './components/SiriWidget'

export default function App() {
  const {
    assistantState,
    isConnected,
    currentTask,
    showSettings,
    audioLevel,
    settings,
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


  const handleOrbClick = useCallback(async () => {
    if (assistantState === 'idle') {
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

  const isActive =
    assistantState === 'listening' ||
    assistantState === 'processing' ||
    assistantState === 'speaking'

  // If this window is the Siri widget overlay, render ONLY the Siri visualizer
  if (isSiriWidget) {
    return (
      <div className="h-screen w-screen bg-transparent overflow-hidden">
        <SiriWidget />
      </div>
    )
  }

  return (
    <DashboardLayout
      onSendMessage={(text) => sendMessage('text_command', { text })}
      onOrbClick={handleOrbClick}
    />
  )
}
