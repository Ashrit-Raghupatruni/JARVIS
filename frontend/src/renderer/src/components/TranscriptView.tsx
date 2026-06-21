import React, { useEffect, useState } from 'react'
import { useAppStore } from '../stores/appStore'

const TranscriptView: React.FC = () => {
  const currentTranscript = useAppStore((s) => s.currentTranscript)
  const assistantState = useAppStore((s) => s.assistantState)
  const [displayText, setDisplayText] = useState('')
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (currentTranscript) {
      setDisplayText(currentTranscript)
      setIsVisible(true)
    } else if (assistantState !== 'listening') {
      // Fade out when not listening and no transcript
      const timer = setTimeout(() => {
        setIsVisible(false)
        // Clear text after fade-out
        const clearTimer = setTimeout(() => setDisplayText(''), 300)
        return () => clearTimeout(clearTimer)
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [currentTranscript, assistantState])

  if (!displayText && !isVisible) return null

  return (
    <div
      className="flex items-center justify-center px-8 transition-all duration-500"
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(8px)'
      }}
    >
      <div className="max-w-lg text-center">
        {/* Label */}
        <div className="flex items-center justify-center gap-2 mb-2">
          <div className="w-6 h-px bg-gradient-to-r from-transparent to-jarvis-accent/30" />
          <span className="text-[10px] uppercase tracking-[0.2em] text-jarvis-accent/60 font-medium">
            Transcript
          </span>
          <div className="w-6 h-px bg-gradient-to-l from-transparent to-jarvis-accent/30" />
        </div>

        {/* Transcript text */}
        <p
          className="text-2xl font-normal text-jarvis-text leading-relaxed"
          style={{
            textShadow: '0 0 20px rgba(255, 59, 48, 0.15)'
          }}
        >
          {displayText}
          {assistantState === 'listening' && (
            <span className="inline-block w-0.5 h-5 ml-1 bg-jarvis-accent animate-pulse-soft align-middle" />
          )}
        </p>
      </div>
    </div>
  )
}

export default TranscriptView
