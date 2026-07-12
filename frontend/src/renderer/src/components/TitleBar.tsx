import React, { useEffect, useState } from 'react'
import { useAppStore } from '../stores/appStore'

const TitleBar: React.FC = () => {
  const [isMaximized, setIsMaximized] = useState(false)
  const isConnected = useAppStore((s) => s.isConnected)

  useEffect(() => {
    const api = window.electronAPI
    if (!api) return

    api.isMaximized().then(setIsMaximized).catch(() => {})

    const unsubscribe = api.onWindowStateChanged((state) => {
      setIsMaximized(state.isMaximized)
    })

    return () => {
      unsubscribe()
    }
  }, [])

  const handleMinimize = (): void => {
    window.electronAPI?.minimize()
  }

  const handleMaximize = async (): Promise<void> => {
    const api = window.electronAPI
    if (api) {
      const state = await api.maximize()
      setIsMaximized(state)
    }
  }

  const handleClose = (): void => {
    window.electronAPI?.close()
  }

  return (
    <div className="titlebar-drag h-9 flex items-center justify-between px-4 glass-light border-b border-jarvis-border z-50 relative shrink-0">
      {/* Left: Logo + Title */}
      <div className="flex items-center gap-2.5 titlebar-no-drag">
        {/* JARVIS Logo - Hexagonal Icon */}
        <div className="relative w-5 h-5 flex items-center justify-center">
          <div
            className="w-4 h-4 rounded-sm rotate-45"
            style={{
              background: 'linear-gradient(135deg, var(--jarvis-accent) 0%, var(--jarvis-accent-2) 100%)',
              boxShadow: '0 0 8px rgba(0, 229, 255, 0.4)'
            }}
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              className="w-1.5 h-1.5 rounded-full bg-jarvis-bg"
            />
          </div>
        </div>

        <span className="text-xs font-semibold tracking-[0.25em] text-jarvis-text uppercase">
          JARVIS
        </span>

        {/* Connection dot */}
        <div
          className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-jarvis-success' : 'bg-jarvis-danger'}`}
          style={{
            boxShadow: isConnected
              ? '0 0 6px rgba(16, 185, 129, 0.6)'
              : '0 0 6px rgba(239, 68, 68, 0.6)'
          }}
        />
      </div>

      {/* Right: Window Controls */}
      <div className="flex items-center gap-0.5 titlebar-no-drag">
        {/* Minimize */}
        <button
          onClick={handleMinimize}
          className="w-8 h-7 flex items-center justify-center rounded-sm hover:bg-white/10 transition-fast group"
          aria-label="Minimize"
        >
          <svg
            className="w-3.5 h-3.5 text-jarvis-text-dim group-hover:text-jarvis-text transition-colors"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" d="M5 12h14" />
          </svg>
        </button>

        {/* Maximize/Restore */}
        <button
          onClick={handleMaximize}
          className="w-8 h-7 flex items-center justify-center rounded-sm hover:bg-white/10 transition-fast group"
          aria-label={isMaximized ? 'Restore' : 'Maximize'}
        >
          {isMaximized ? (
            <svg
              className="w-3 h-3 text-jarvis-text-dim group-hover:text-jarvis-text transition-colors"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <rect x="5" y="8" width="11" height="11" rx="1" />
              <path d="M8 8V5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-3" />
            </svg>
          ) : (
            <svg
              className="w-3 h-3 text-jarvis-text-dim group-hover:text-jarvis-text transition-colors"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <rect x="4" y="4" width="16" height="16" rx="1" />
            </svg>
          )}
        </button>

        {/* Close */}
        <button
          onClick={handleClose}
          className="w-8 h-7 flex items-center justify-center rounded-sm hover:bg-red-500/80 transition-fast group"
          aria-label="Close"
        >
          <svg
            className="w-3.5 h-3.5 text-jarvis-text-dim group-hover:text-white transition-colors"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" d="M6 6l12 12M6 18L18 6" />
          </svg>
        </button>
      </div>
    </div>
  )
}

export default TitleBar
