import { useState, useEffect } from 'react'
import { useAppStore } from '../stores/appStore'

interface TaskProgressProps {
  className?: string
}

export default function TaskProgress({ className = '' }: TaskProgressProps) {
  const { currentTask } = useAppStore()
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    if (currentTask) {
      setIsVisible(true)
    } else {
      const timer = setTimeout(() => setIsVisible(false), 500)
      return () => clearTimeout(timer)
    }
  }, [currentTask])

  if (!isVisible || !currentTask) return null

  const completedSteps = currentTask.steps.filter(s => s.status === 'completed').length
  const totalSteps = currentTask.steps.length
  const progress = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0

  return (
    <div
      className={`glass rounded-xl border border-white/10 p-4 w-80 transition-all duration-500 ${
        currentTask ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
      } ${className}`}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2 h-2 rounded-full bg-[var(--jarvis-accent)] animate-pulse" />
        <h3
          className="text-sm font-semibold truncate"
          style={{ color: 'var(--jarvis-text)' }}
        >
          {currentTask.description || 'Executing Task'}
        </h3>
      </div>

      {/* Progress Bar */}
      <div className="w-full h-1.5 rounded-full bg-white/5 mb-3 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${progress}%`,
            background: 'linear-gradient(90deg, var(--jarvis-accent), var(--jarvis-accent-2))',
            boxShadow: '0 0 8px var(--jarvis-accent)',
          }}
        />
      </div>

      {/* Steps */}
      <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
        {currentTask.steps.map((step, index) => (
          <div
            key={index}
            className="flex items-start gap-2.5 text-xs transition-all duration-300"
            style={{
              opacity: step.status === 'pending' ? 0.4 : 1,
            }}
          >
            {/* Status Icon */}
            <div className="mt-0.5 flex-shrink-0">
              {step.status === 'pending' && (
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6" stroke="var(--jarvis-text-dim)" strokeWidth="1.5" />
                </svg>
              )}
              {step.status === 'running' && (
                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6" stroke="var(--jarvis-accent)" strokeWidth="1.5" strokeDasharray="20 10" />
                </svg>
              )}
              {step.status === 'completed' && (
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6" fill="var(--jarvis-success)" fillOpacity="0.2" stroke="var(--jarvis-success)" strokeWidth="1.5" />
                  <path d="M5 8l2 2 4-4" stroke="var(--jarvis-success)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              {step.status === 'failed' && (
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6" fill="var(--jarvis-danger)" fillOpacity="0.2" stroke="var(--jarvis-danger)" strokeWidth="1.5" />
                  <path d="M6 6l4 4M10 6l-4 4" stroke="var(--jarvis-danger)" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              )}
            </div>

            {/* Step Description */}
            <span
              className="leading-tight"
              style={{
                color:
                  step.status === 'running'
                    ? 'var(--jarvis-accent)'
                    : step.status === 'completed'
                    ? 'var(--jarvis-success)'
                    : step.status === 'failed'
                    ? 'var(--jarvis-danger)'
                    : 'var(--jarvis-text-dim)',
              }}
            >
              {step.description}
            </span>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div
        className="mt-3 pt-2 border-t border-white/5 text-xs flex justify-between"
        style={{ color: 'var(--jarvis-text-dim)' }}
      >
        <span>
          {completedSteps}/{totalSteps} steps
        </span>
        <span>{Math.round(progress)}%</span>
      </div>
    </div>
  )
}
