import React, { useState, useRef, useEffect } from 'react'
import {
  Mic,
  MicOff,
  Send,
  Paperclip,
  Activity,
  Sparkles
} from 'lucide-react'
import { useAppStore } from '../stores/appStore'

interface FloatingCommandBarProps {
  onSendMessage: (text: string) => void
  onToggleListening: () => void
  isListening: boolean
}

export const FloatingCommandBar: React.FC<FloatingCommandBarProps> = ({
  onSendMessage,
  onToggleListening,
  isListening
}) => {
  const [inputText, setInputText] = useState('')
  const audioLevel = useAppStore((s) => s.audioLevel)
  const isSpeaking = useAppStore((s) => s.isSpeaking)
  const currentTranscript = useAppStore((s) => s.currentTranscript)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Sync real-time speech transcript into input if currently listening
  useEffect(() => {
    if (isListening && currentTranscript) {
      setInputText(currentTranscript)
    }
  }, [isListening, currentTranscript])

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const trimmed = inputText.trim()
    if (!trimmed) return
    onSendMessage(trimmed)
    setInputText('')
  }

  const handleSuggestionClick = (prompt: string) => {
    onSendMessage(prompt)
  }

  const handleAttachment = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click()
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setInputText(`Analyze file: ${file.name}`)
    }
  }

  const suggestions = [
    'Summarize this document',
    'Plan my day',
    'Search on web',
    'Help me code',
    'Control my PC'
  ]

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col items-center gap-3 px-4 z-40 select-none">
      {/* 5 Suggestion Chips */}
      <div className="flex items-center justify-center gap-2 flex-wrap">
        {suggestions.map((suggestion, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleSuggestionClick(suggestion)}
            className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-900/60 hover:bg-blue-900/30 border border-blue-500/20 hover:border-cyan-400/50 backdrop-blur-md text-xs text-slate-300 hover:text-cyan-200 transition-all duration-200 shadow-sm cursor-pointer hover:shadow-[0_0_12px_rgba(0,229,255,0.2)]"
          >
            <Sparkles className="w-3 h-3 text-cyan-400/70 group-hover:text-cyan-300 transition-colors" />
            <span className="font-sans font-medium">{suggestion}</span>
          </button>
        ))}
      </div>

      {/* Glowing Floating Input Pill */}
      <form
        onSubmit={handleSubmit}
        className="w-full relative flex items-center bg-slate-950/70 backdrop-blur-2xl border border-blue-500/30 hover:border-cyan-400/40 rounded-full px-3 py-2 shadow-[0_12px_36px_rgba(0,0,0,0.6),0_0_20px_rgba(0,180,255,0.15)] transition-all duration-300 focus-within:border-cyan-400 focus-within:shadow-[0_12px_36px_rgba(0,0,0,0.7),0_0_25px_rgba(0,229,255,0.25)]"
      >
        {/* Left Audio Waveform Visualizer Button */}
        <button
          type="button"
          onClick={onToggleListening}
          className={`p-2 rounded-full transition-all shrink-0 cursor-pointer ${
            isListening || isSpeaking
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/40 shadow-[0_0_10px_#00e5ff]'
              : 'text-slate-400 hover:text-cyan-400 hover:bg-slate-800/50'
          }`}
          title={isListening ? 'Listening (Click to stop)' : 'Click to start voice'}
        >
          <Activity
            className={`w-5 h-5 ${isListening ? 'animate-pulse' : ''}`}
            style={{
              transform: isListening ? `scale(${1 + audioLevel * 0.3})` : 'none'
            }}
          />
        </button>

        {/* Input Text Box */}
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Ask me anything..."
          className="flex-1 bg-transparent border-none outline-none px-3 text-sm text-slate-100 placeholder-slate-400/70 font-sans tracking-wide"
        />

        {/* Hidden File Input */}
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Attachment Button */}
        <button
          type="button"
          onClick={handleAttachment}
          className="p-2 text-slate-400 hover:text-cyan-300 hover:bg-slate-800/50 rounded-full transition-colors shrink-0 cursor-pointer"
          title="Attach document or file"
        >
          <Paperclip className="w-4 h-4" />
        </button>

        {/* Microphone Toggle Button */}
        <button
          type="button"
          onClick={onToggleListening}
          className={`p-2 rounded-full transition-all shrink-0 ml-0.5 cursor-pointer ${
            isListening
              ? 'bg-cyan-500/25 text-cyan-300 border border-cyan-400 shadow-[0_0_12px_#00e5ff]'
              : 'text-slate-400 hover:text-cyan-300 hover:bg-slate-800/50'
          }`}
          title={isListening ? 'Mute microphone' : 'Activate voice input'}
        >
          {isListening ? (
            <Mic className="w-4 h-4 animate-bounce text-cyan-300" />
          ) : (
            <Mic className="w-4 h-4" />
          )}
        </button>

        {/* Blue Circular Send Button */}
        <button
          type="submit"
          disabled={!inputText.trim()}
          className={`ml-1.5 p-2.5 rounded-full transition-all shrink-0 cursor-pointer flex items-center justify-center ${
            inputText.trim()
              ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-[0_0_14px_rgba(0,229,255,0.6)] hover:brightness-110 active:scale-95'
              : 'bg-slate-800/60 text-slate-500 cursor-not-allowed'
          }`}
          title="Send command"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  )
}
