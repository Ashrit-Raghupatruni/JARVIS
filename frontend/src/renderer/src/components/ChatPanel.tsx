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
        isDragging ? 'border border-jarvis-accent bg-jarvis-bg/85' : ''
      } ${
        isMinimized ? 'h-12' : 'h-full'
      }`}
      style={{
        boxShadow: '0 0 30px rgba(0, 0, 0, 0.3), 0 0 15px rgba(0, 229, 255, 0.05)'
      }}
    >
      {isDragging && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-black/80 border border-jarvis-accent rounded-xl animate-fade-in pointer-events-none">
          <svg className="w-12 h-12 text-jarvis-accent animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
          </svg>
          <span className="text-sm font-medium text-jarvis-accent mt-3">Drop file to attach</span>
          <span className="text-xs text-jarvis-text-dim mt-1">Supports source code, logs, text, markdown</span>
        </div>
      )}
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 h-12 border-b border-jarvis-border cursor-pointer shrink-0"
        onClick={() => setIsMinimized(!isMinimized)}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full bg-jarvis-accent"
            style={{ boxShadow: '0 0 6px rgba(0, 229, 255, 0.6)' }}
          />
          <span className="text-sm font-semibold tracking-wider text-jarvis-text text-glow">
            JARVIS
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

      {/* Messages */}
      {!isMinimized && (
        <>
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full gap-3 opacity-40">
                <svg className="w-10 h-10 text-jarvis-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <span className="text-xs text-jarvis-text-muted">
                  Say "Hey JARVIS" or press Ctrl+Space
                </span>
              </div>
            )}

            {messages.map((msg, index) => (
              <MessageBubble key={msg.id || index} message={msg} formatTime={formatTime} />
            ))}

            {/* Live transcript */}
            {currentTranscript && (
              <div className="animate-fade-in flex justify-end">
                <div className="max-w-[85%] px-3 py-2 rounded-lg bg-white/5 border border-white/10">
                  <p className="text-sm text-jarvis-text-dim italic animate-pulse-soft">
                    {currentTranscript}
                  </p>
                </div>
              </div>
            )}

            {/* Thinking indicator */}
            {assistantState === 'processing' && (
              <div className="animate-fade-in-up flex justify-start">
                <div className="max-w-[85%] px-3 py-2 rounded-lg bg-jarvis-accent-dim border border-jarvis-border">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-jarvis-accent"
                        style={{ animation: 'thinking-dot 1.4s infinite ease-in-out', animationDelay: '0s' }}
                      />
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-jarvis-accent"
                        style={{ animation: 'thinking-dot 1.4s infinite ease-in-out', animationDelay: '0.2s' }}
                      />
                      <span
                        className="w-1.5 h-1.5 rounded-full bg-jarvis-accent"
                        style={{ animation: 'thinking-dot 1.4s infinite ease-in-out', animationDelay: '0.4s' }}
                      />
                    </div>
                    {thinkingText && (
                      <span className="text-xs text-jarvis-text-dim">{thinkingText}</span>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="px-3 pb-3 pt-1 border-t border-jarvis-border shrink-0">
            {attachedFile && (
              <div className="flex items-center justify-between mx-1 mb-2 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-xs text-jarvis-text animate-fade-in">
                <span className="truncate max-w-[85%]">📄 {attachedFile.name}</span>
                <button
                  onClick={() => setAttachedFile(null)}
                  className="text-jarvis-text-dim hover:text-jarvis-accent transition-fast"
                >
                  ✕
                </button>
              </div>
            )}
            <div className="flex items-center gap-2 glass rounded-lg px-3 py-1.5">
              <input
                ref={inputRef}
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message..."
                className="flex-1 bg-transparent text-sm text-jarvis-text placeholder-jarvis-text-muted outline-none"
              />
              <button
                onClick={handleSend}
                disabled={!inputText.trim() && !attachedFile}
                className="w-7 h-7 flex items-center justify-center rounded-md bg-jarvis-accent/20 hover:bg-jarvis-accent/30 disabled:opacity-30 disabled:cursor-not-allowed transition-fast"
              >
                <svg
                  className="w-3.5 h-3.5 text-jarvis-accent"
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

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, formatTime }) => {
  if (message.role === 'system') {
    return (
      <div className="animate-fade-in flex justify-center">
        <div className="px-3 py-1 rounded-full bg-white/5">
          <span className="text-xs text-jarvis-text-muted">{message.content}</span>
        </div>
      </div>
    )
  }

  const isUser = message.role === 'user'

  return (
    <div
      className={`animate-fade-in-up flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`max-w-[85%] flex gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
      >
        {/* Avatar */}
        <div
          className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
            isUser
              ? 'bg-jarvis-accent/20'
              : 'bg-gradient-to-br from-jarvis-accent/30 to-jarvis-accent-2/30'
          }`}
          style={{
            boxShadow: isUser
              ? 'none'
              : '0 0 8px rgba(0, 229, 255, 0.2)'
          }}
        >
          {isUser ? (
            <svg className="w-3 h-3 text-jarvis-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          ) : (
            <svg className="w-3 h-3 text-jarvis-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          )}
        </div>

        {/* Content */}
        <div
          className={`px-3 py-2 rounded-lg ${
            isUser
              ? 'bg-white/5 border border-white/10'
              : 'bg-jarvis-accent-dim border border-jarvis-border'
          }`}
        >
          <p className="text-sm text-jarvis-text leading-relaxed whitespace-pre-wrap break-words">
            {message.content}
          </p>
          <span
            className={`text-[10px] mt-1 block ${
              isUser ? 'text-jarvis-text-muted text-right' : 'text-jarvis-text-muted'
            }`}
          >
            {formatTime(message.timestamp)}
          </span>
        </div>
      </div>
    </div>
  )
}

export default ChatPanel
