import React, { useState } from 'react'
import { useAppStore } from '../stores/appStore'
import type { CommandEntry } from '../types'

interface CommandHistoryProps {
  onRerun?: (command: string) => void
}

const CommandHistory: React.FC<CommandHistoryProps> = ({ onRerun }) => {
  const commandHistory = useAppStore((s) => s.commandHistory)
  const showCommandHistory = useAppStore((s) => s.showCommandHistory)
  const [isMinimized, setIsMinimized] = useState(false)

  if (!showCommandHistory) return null

  const formatTime = (timestamp: string): string => {
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
      return ''
    }
  }

  return (
    <div
      className={`flex flex-col glass-heavy rounded-xl overflow-hidden transition-all duration-500 ${
        isMinimized ? 'h-12' : 'h-full'
      }`}
      style={{
        width: 300,
        maxHeight: isMinimized ? 48 : 'calc(100vh - 120px)',
        boxShadow: '0 0 30px rgba(0, 0, 0, 0.3), 0 0 15px rgba(0, 212, 255, 0.05)'
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 h-12 border-b border-jarvis-border cursor-pointer shrink-0"
        onClick={() => setIsMinimized(!isMinimized)}
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-3.5 h-3.5 text-jarvis-accent"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-sm font-semibold tracking-wider text-jarvis-text">
            History
          </span>
          {commandHistory.length > 0 && (
            <span className="text-[10px] text-jarvis-text-muted bg-white/5 px-1.5 py-0.5 rounded-full">
              {commandHistory.length}
            </span>
          )}
        </div>

        <button
          className="w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 transition-fast"
          onClick={(e) => {
            e.stopPropagation()
            setIsMinimized(!isMinimized)
          }}
        >
          <svg
            className={`w-3 h-3 text-jarvis-text-dim transition-transform duration-300 ${
              isMinimized ? 'rotate-180' : ''
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Entries */}
      {!isMinimized && (
        <div className="flex-1 overflow-y-auto py-2">
          {commandHistory.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 opacity-40 px-4">
              <svg className="w-8 h-8 text-jarvis-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                <path strokeLinecap="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span className="text-xs text-jarvis-text-muted text-center">
                No commands yet
              </span>
            </div>
          ) : (
            commandHistory.map((entry, index) => (
              <CommandEntryItem
                key={entry.id || index}
                entry={entry}
                formatTime={formatTime}
                onRerun={onRerun}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

/* ===== Command Entry Item ===== */
interface CommandEntryItemProps {
  entry: CommandEntry
  formatTime: (ts: string) => string
  onRerun?: (command: string) => void
}

const CommandEntryItem: React.FC<CommandEntryItemProps> = ({ entry, formatTime, onRerun }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div
      className="px-3 py-2 mx-2 mb-1 rounded-lg hover:bg-white/5 cursor-pointer transition-fast animate-fade-in"
      onClick={() => setIsExpanded(!isExpanded)}
    >
      <div className="flex items-start gap-2">
        {/* Status icon */}
        <div className="mt-0.5 shrink-0">
          {entry.success ? (
            <svg className="w-3.5 h-3.5 text-jarvis-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5 text-jarvis-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="text-xs text-jarvis-text truncate font-mono">{entry.command}</p>
          <span className="text-[10px] text-jarvis-text-muted">{formatTime(entry.timestamp)}</span>
        </div>

        {/* Rerun button */}
        <button
          className="w-5 h-5 flex items-center justify-center rounded hover:bg-jarvis-accent/20 transition-fast opacity-0 group-hover:opacity-100 shrink-0"
          onClick={(e) => {
            e.stopPropagation()
            onRerun?.(entry.command)
          }}
          title="Re-run"
        >
          <svg className="w-3 h-3 text-jarvis-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      {/* Expanded result */}
      {isExpanded && entry.result && (
        <div className="mt-2 px-2 py-1.5 rounded bg-black/30 border border-jarvis-border animate-fade-in">
          <p className="text-[11px] text-jarvis-text-dim font-mono whitespace-pre-wrap break-all leading-relaxed">
            {entry.result}
          </p>
        </div>
      )}
    </div>
  )
}

export default CommandHistory
