import { useAppStore } from '../stores/appStore'
import type { AssistantState } from '../types'

interface StatusBarProps {
  onToggleChat?: () => void
  onToggleHistory?: () => void
}

const stateConfig: Record<AssistantState, { label: string; icon: string; color: string }> = {
  idle: { label: 'Ready', icon: '○', color: 'var(--jarvis-text-dim)' },
  wake_word_detected: { label: 'Activated', icon: '◉', color: 'var(--jarvis-accent)' },
  listening: { label: 'Listening', icon: '◉', color: 'var(--jarvis-accent)' },
  processing: { label: 'Processing', icon: '◎', color: 'var(--jarvis-accent-2)' },
  speaking: { label: 'Speaking', icon: '◉', color: 'var(--jarvis-accent)' },
  executing: { label: 'Executing', icon: '⟡', color: 'var(--jarvis-warning)' },
}

export default function StatusBar({ onToggleChat, onToggleHistory }: StatusBarProps) {
  const isConnected = useAppStore((s) => s.isConnected)
  const assistantState = useAppStore((s) => s.assistantState)
  const audioLevel = useAppStore((s) => s.audioLevel)
  const toggleSettings = useAppStore((s) => s.toggleSettings)

  const currentState = stateConfig[assistantState]

  return (
    <div
      className="h-8 flex items-center justify-between px-4 glass border-t border-white/5 z-40 shrink-0"
    >
      {/* Left section */}
      <div className="flex items-center gap-4">
        {/* Connection indicator */}
        <div className="flex items-center gap-1.5">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{
              backgroundColor: isConnected ? 'var(--jarvis-success)' : 'var(--jarvis-danger)',
              boxShadow: isConnected
                ? '0 0 4px rgba(16, 185, 129, 0.6)'
                : '0 0 4px rgba(239, 68, 68, 0.6)',
            }}
          />
          <span
            className="text-[10px] font-medium uppercase tracking-wider"
            style={{ color: 'var(--jarvis-text-dim)' }}
          >
            {isConnected ? 'Connected' : 'Offline'}
          </span>
        </div>

        {/* State */}
        <div className="flex items-center gap-1.5">
          <span className="text-[11px]" style={{ color: currentState.color }}>
            {currentState.icon}
          </span>
          <span
            className="text-[10px] font-medium uppercase tracking-wider"
            style={{ color: currentState.color }}
          >
            {currentState.label}
          </span>
        </div>

        {/* Mic level */}
        <div className="flex items-center gap-1.5">
          <svg
            className="w-3 h-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            style={{ color: 'var(--jarvis-text-dim)' }}
          >
            <path strokeLinecap="round" d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
            <path strokeLinecap="round" d="M19 10v2a7 7 0 01-14 0v-2M12 19v4M8 23h8" />
          </svg>
          <div className="w-16 h-1.5 rounded-full bg-white/5 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-100"
              style={{
                width: `${audioLevel * 100}%`,
                background:
                  audioLevel > 0.7
                    ? 'linear-gradient(90deg, #00d4ff, #ef4444)'
                    : audioLevel > 0.3
                    ? 'linear-gradient(90deg, #00d4ff, #0ea5e9)'
                    : '#00d4ff',
                boxShadow:
                  audioLevel > 0.1
                    ? `0 0 ${4 + audioLevel * 8}px rgba(0, 212, 255, ${audioLevel * 0.5})`
                    : 'none',
              }}
            />
          </div>
        </div>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-1">
        {/* Toggle Command History */}
        <button
          onClick={onToggleHistory}
          className="w-7 h-6 flex items-center justify-center rounded hover:bg-white/10 transition-colors"
          style={{ color: 'var(--jarvis-text-dim)' }}
          title="Command History"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </button>

        {/* Toggle Chat */}
        <button
          onClick={onToggleChat}
          className="w-7 h-6 flex items-center justify-center rounded hover:bg-white/10 transition-colors"
          style={{ color: 'var(--jarvis-text-dim)' }}
          title="Chat Panel"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>

        {/* Settings */}
        <button
          onClick={toggleSettings}
          className="w-7 h-6 flex items-center justify-center rounded hover:bg-white/10 transition-colors"
          style={{ color: 'var(--jarvis-text-dim)' }}
          title="Settings"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>
    </div>
  )
}
