import { useEffect, useCallback, useState, useRef } from 'react'
import { useAppStore } from './stores/appStore'
import { useWebSocket } from './hooks/useWebSocket'
import { useAudio } from './hooks/useAudio'
import TitleBar from './components/TitleBar'
import Orb from './components/Orb'
import VoiceWave from './components/VoiceWave'
import TranscriptView from './components/TranscriptView'
import ChatPanel from './components/ChatPanel'
import CommandHistory from './components/CommandHistory'
import StatusBar from './components/StatusBar'
import TaskProgress from './components/TaskProgress'
import ScreenPreview from './components/ScreenPreview'
import SettingsPanel from './components/SettingsPanel'
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
  }, [])

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
    <div className="h-screen w-screen flex flex-col overflow-hidden select-none relative" style={{ backgroundColor: 'var(--jarvis-bg)' }}>
      {/* Animated background grid */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, var(--jarvis-accent) 1px, transparent 0)',
            backgroundSize: '40px 40px',
          }}
        />
        {/* Ambient glow */}
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full opacity-25 blur-[120px] transition-all duration-1000"
          style={{
            background: isActive
              ? 'radial-gradient(circle, var(--jarvis-accent) 0%, transparent 70%)'
              : 'radial-gradient(circle, var(--jarvis-accent-dim) 0%, transparent 70%)',
          }}
        />
      </div>

      {/* Title Bar */}
      <TitleBar />

      {/* Main Content */}
      <div className="flex-1 flex relative z-10 overflow-hidden">
        {/* Left: Chat Panel */}
        {showChat && (
          <div className="w-full max-w-[360px] md:max-w-[400px] h-full p-4 shrink-0 animate-slide-in-left">
            <ChatPanel onSendMessage={(text) => sendMessage('text_command', { text })} />
          </div>
        )}

        {/* Center: Orb + Wave + Transcript */}
        <div className="flex-1 flex flex-col items-center justify-center relative">
          {/* Transcript (above orb) */}
          <div className="mb-8">
            <TranscriptView />
          </div>

          {/* Orb */}
          <div className="cursor-pointer" onClick={handleOrbClick}>
            <Orb />
          </div>

          {/* Voice Wave (below orb) */}
          <div className="mt-6">
            <VoiceWave />
          </div>
        </div>

        {/* Right: Command History (overlay) */}
        {showHistory && (
          <div className="absolute right-4 top-4 z-20 animate-slide-in-right">
            <CommandHistory />
          </div>
        )}
      </div>

      {/* Bottom overlays */}
      <div className="absolute bottom-16 z-20 transition-all duration-500" style={{ left: showChat ? '400px' : '16px' }}>
        {currentTask && <TaskProgress />}
      </div>
      <div className="absolute bottom-16 right-4 z-20">
        <ScreenPreview />
      </div>

      {/* Status Bar */}
      <StatusBar
        onToggleChat={() => setShowChat((p) => !p)}
        onToggleHistory={() => setShowHistory((p) => !p)}
      />

      {/* Settings Modal */}
      <SettingsPanel />
    </div>
  )
}
