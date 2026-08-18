import React, { useRef, useEffect, useState, useCallback } from 'react'
import { useAppStore } from '../stores/appStore'
import type { ConversationMessage } from '../types'

interface ChatPanelProps {
  onSendMessage?: (text: string) => void
}

const ChatPanel: React.FC<ChatPanelProps> = ({ onSendMessage }) => {
  const messages = useAppStore((s) => s.messages)
  const currentTranscript = useAppStore((s) => s.currentTranscript)
  const assistantState = useAppStore((s) => s.assistantState)
  const thinkingText = useAppStore((s) => s.thinkingText)
  const showChat = useAppStore((s) => s.showChat)
  const connectionState = useAppStore((s) => s.connectionState)
  const queuedMessageCount = useAppStore((s) => s.queuedMessageCount)

  const [inputText, setInputText] = useState('')
  const [isMinimized, setIsMinimized] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [attachedFile, setAttachedFile] = useState<{ name: string; content: string; type: string } | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentTranscript, thinkingText, scrollToBottom])

  const handleSend = useCallback(() => {
    const trimmed = inputText.trim()
    if (!trimmed && !attachedFile) return

    let finalContent = trimmed
    if (attachedFile) {
      finalContent = `[File Attachment: ${attachedFile.name}]\n\nContent:\n\`\`\`${attachedFile.type}\n${attachedFile.content}\n\`\`\`\n\n${trimmed}`
    }

    const msg: ConversationMessage = {
      id: Date.now().toString(36) + Math.random().toString(36).substring(2, 9),
      role: 'user',
      content: attachedFile ? `📄 Attached file: ${attachedFile.name}\n${trimmed}` : trimmed,
      timestamp: new Date().toISOString()
    }
    useAppStore.getState().addMessage(msg)
    onSendMessage?.(finalContent)
    setInputText('')
    setAttachedFile(null)
  }, [inputText, attachedFile, onSendMessage])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  const formatTime = (timestamp: string): string => {
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
      return ''
    }
  }

  if (!showChat) return null

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setIsDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) {
          const reader = new FileReader()
          reader.onload = (event) => {
            const content = event.target?.result as string
            setAttachedFile({
              name: file.name,
              content: content || '',
              type: file.type || file.name.split('.').pop() || 'unknown'
            })
          }
          reader.readAsText(file)
        }
      }}
      className={`flex flex-col glass-heavy rounded-xl overflow-hidden transition-all duration-500 relative w-full ${
        isDragging ? 'border border-cyan-500 bg-slate-950/85' : ''
      } ${isMinimized ? 'h-12' : 'h-full'}`}
      style={{
        boxShadow: '0 0 30px rgba(0, 0, 0, 0.3), 0 0 15px rgba(0, 229, 255, 0.05)'
      }}
    >
      {isDragging && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-black/80 border border-cyan-400 rounded-xl animate-fade-in pointer-events-none">
          <svg className="w-12 h-12 text-cyan-400 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
          </svg>
          <span className="text-sm font-medium text-cyan-300 mt-3">Drop file to attach</span>
          <span className="text-xs text-slate-400 mt-1">Supports source code, logs, text, markdown</span>
        </div>
      )}
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 h-12 border-b border-cyan-500/20 cursor-pointer shrink-0"
        onClick={() => setIsMinimized(!isMinimized)}
      >
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <h2 className="text-sm font-semibold text-slate-200 tracking-wide font-mono">AI CHAT</h2>
          
          {/* Connection Status Indicator Pill */}
          <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded tracking-wider border flex items-center gap-1.5 transition-all ${
            connectionState === 'connected'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : connectionState === 'reconnecting'
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-300 animate-pulse'
              : connectionState === 'connecting'
              ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300 animate-pulse'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${
              connectionState === 'connected'
                ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]'
                : connectionState === 'reconnecting'
                ? 'bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.8)]'
                : connectionState === 'connecting'
                ? 'bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.8)]'
                : 'bg-rose-400'
            }`} />
            {connectionState === 'connected' && 'CONNECTED'}
            {connectionState === 'reconnecting' && `RECONNECTING${queuedMessageCount > 0 ? ` (${queuedMessageCount} QUEUED)` : ''}`}
            {connectionState === 'connecting' && 'CONNECTING...'}
            {connectionState === 'disconnected' && 'OFFLINE'}
          </span>
        </div>

        <button
          className="w-6 h-6 flex items-center justify-center rounded hover:bg-white/10 transition-fast"
          onClick={(e) => {
            e.stopPropagation()
            setIsMinimized(!isMinimized)
          }}
        >
          <svg
            className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-300 ${
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

      {/* Messages */}
      {!isMinimized && (
        <>
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 custom-scrollbar">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full gap-3 opacity-40">
                <svg className="w-10 h-10 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <span className="text-xs text-slate-400 font-mono">
                  Say "Hey JARVIS" or type your command...
                </span>
              </div>
            )}

            {messages.map((msg, index) => (
              <MessageBubble key={msg.id || index} message={msg} formatTime={formatTime} />
            ))}

            {/* Live transcript */}
            {currentTranscript && (
              <div className="animate-fade-in flex justify-end">
                <div className="max-w-[85%] px-3 py-2 rounded-lg bg-cyan-950/40 border border-cyan-500/30">
                  <p className="text-xs text-cyan-300 italic animate-pulse">
                    {currentTranscript}
                  </p>
                </div>
              </div>
            )}

            {/* Thinking indicator */}
            {assistantState === 'processing' && (
              <div className="animate-fade-in-up flex justify-start">
                <div className="max-w-[85%] px-3 py-2 rounded-lg bg-slate-900 border border-cyan-500/30">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-cyan-400"
                        style={{ animation: 'thinking-dot 1.4s infinite ease-in-out', animationDelay: '0s' }}
                      />
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-cyan-400"
                        style={{ animation: 'thinking-dot 1.4s infinite ease-in-out', animationDelay: '0.2s' }}
                      />
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-cyan-400"
                        style={{ animation: 'thinking-dot 1.4s infinite ease-in-out', animationDelay: '0.4s' }}
                      />
                    </div>
                    {thinkingText && (
                      <span className="text-xs text-slate-400 font-mono">{thinkingText}</span>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="px-3 pb-3 pt-1 border-t border-slate-800 shrink-0">
            {attachedFile && (
              <div className="flex items-center justify-between mx-1 mb-2 px-3 py-1.5 rounded bg-slate-900 border border-cyan-500/30 text-xs text-slate-200 animate-fade-in">
                <span className="truncate max-w-[85%] font-mono">📄 {attachedFile.name}</span>
                <button
                  onClick={() => setAttachedFile(null)}
                  className="text-slate-400 hover:text-cyan-400 transition-fast"
                >
                  ✕
                </button>
              </div>
            )}
            <div className="flex items-center gap-2 bg-slate-950/80 rounded-lg px-3 py-1.5 border border-cyan-500/30">
              <input
                ref={inputRef}
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={assistantState === 'listening' ? "🎤 Listening to your voice..." : "Type a message or say 'Hey Jarvis'..."}
                className="flex-1 bg-transparent text-sm font-sans text-slate-100 placeholder-slate-500 outline-none caret-cyan-400"
              />

              {/* Mic Toggle Button inside Chat Box */}
              <button
                type="button"
                onClick={() => {
                  const store = useAppStore.getState()
                  if (store.assistantState === 'idle') {
                    store.setAssistantState('listening')
                  } else {
                    store.setAssistantState('idle')
                  }
                }}
                className={`w-7 h-7 flex items-center justify-center rounded-md transition-all ${
                  assistantState === 'listening'
                    ? 'bg-rose-500/30 text-rose-400 border border-rose-500/50 animate-pulse shadow-[0_0_10px_rgba(244,63,94,0.4)]'
                    : 'bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                }`}
                title={assistantState === 'listening' ? "Stop Mic (Click or Ctrl+Space)" : "Activate Mic (Click or Ctrl+Space)"}
              >
                <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                </svg>
              </button>

              <button
                onClick={handleSend}
                disabled={!inputText.trim() && !attachedFile}
                className="w-7 h-7 flex items-center justify-center rounded-md bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
                title="Send Message"
              >
                <svg
                  className="w-3.5 h-3.5 text-cyan-300"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

/* ===== Message Bubble ===== */
interface MessageBubbleProps {
  message: ConversationMessage
  formatTime: (ts: string) => string
}

function cleanChatMessageText(text: string): string {
  if (!text) return ''
  let cleaned = text
  cleaned = cleaned.replace(/<function=[\s\S]*?<\/function>/gi, '')
  cleaned = cleaned.replace(/<function=[\s\S]*?$/gi, '')
  cleaned = cleaned.replace(/\[SERIOUS MODE ACTIVE:[^\]]*\]/gi, '')
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n')
  return cleaned.trim()
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, formatTime }) => {
  const isUser = message.role === 'user'
  const isVisionAck = !isUser && message.content.includes('Looking at your screen now')
  const isSessionMem = message.content.includes('[PREVIOUS SESSION MEMORY]') || message.content.includes('PREVIOUS SESSION MEMORY')

  if (message.role === 'system') {
    return (
      <div className="animate-fade-in flex justify-center font-mono">
        <div className="px-3 py-1 rounded-full bg-slate-900 border border-slate-800">
          <span className="text-xs text-slate-400">{cleanChatMessageText(message.content)}</span>
        </div>
      </div>
    )
  }

  return (
    <div className={`animate-fade-in-up flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
      {/* Session Memory Continuity Chip */}
      {isSessionMem && (
        <div className="w-full my-1.5 p-2 rounded-lg bg-cyan-950/60 border border-cyan-500/30 flex items-center justify-between text-xs text-cyan-300 font-mono">
          <div className="flex items-center space-x-2">
            <span className="text-base">🧠</span>
            <span className="font-semibold">Session Context Restored</span>
          </div>
          <span className="text-[10px] text-cyan-400/70">Read-Once Active</span>
        </div>
      )}

      <div
        className={`max-w-[85%] px-3.5 py-2.5 rounded-xl transition-all duration-200 ${
          isUser
            ? 'bg-cyan-950/70 border border-cyan-500/30 text-cyan-100 rounded-tr-none shadow-[0_2px_10px_rgba(0,229,255,0.1)]'
            : isVisionAck
            ? 'bg-amber-950/60 border border-amber-500/40 text-amber-100 rounded-tl-none shadow-[0_2px_12px_rgba(245,158,11,0.2)]'
            : 'bg-slate-900/90 border border-slate-800 text-slate-100 rounded-tl-none shadow-[0_2px_10px_rgba(0,0,0,0.3)]'
        }`}
      >
        {/* Vision Live Pulse Badge */}
        {isVisionAck && (
          <div className="flex items-center space-x-1.5 mb-1.5 text-[11px] font-mono text-amber-400 font-bold">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            <span>👁️ INSTANT VISION ACKNOWLEDGMENT</span>
          </div>
        )}

        <div className="text-sm leading-relaxed whitespace-pre-wrap break-words font-sans">
          {cleanChatMessageText(message.content)}
        </div>

        <div
          className={`text-[9px] font-mono mt-1 ${
            isUser ? 'text-cyan-400/60 text-right' : 'text-slate-500 text-left'
          }`}
        >
          {formatTime(message.timestamp)}
        </div>
      </div>
    </div>
  )
}

export default ChatPanel
