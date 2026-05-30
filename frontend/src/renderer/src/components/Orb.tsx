import React, { useMemo } from 'react'
import { useAppStore } from '../stores/appStore'

interface Particle {
  id: number
  size: number
  orbitRadius: number
  duration: number
  delay: number
  opacity: number
  reverse: boolean
}

const Orb: React.FC = () => {
  const assistantState = useAppStore((s) => s.assistantState)
  const audioLevel = useAppStore((s) => s.audioLevel)
  const pushToTalkActive = useAppStore((s) => s.pushToTalkActive)
  const isConnected = useAppStore((s) => s.isConnected)

  const particles: Particle[] = useMemo(() => {
    return Array.from({ length: 12 }, (_, i) => ({
      id: i,
      size: 2 + Math.random() * 3,
      orbitRadius: 90 + Math.random() * 50,
      duration: 8 + Math.random() * 12,
      delay: Math.random() * -20,
      opacity: 0.3 + Math.random() * 0.5,
      reverse: i % 3 === 0
    }))
  }, [])

  const stateLabel = useMemo(() => {
    const labels: Record<string, string> = {
      idle: 'Ready',
      wake_word_detected: 'Wake Word Detected',
      listening: 'Listening...',
      processing: 'Processing...',
      speaking: 'Speaking...',
      executing: 'Executing...'
    }
    return labels[assistantState] || 'Ready'
  }, [assistantState])

  const stateColor = useMemo(() => {
    const colors: Record<string, string> = {
      idle: 'text-jarvis-text-dim',
      wake_word_detected: 'text-jarvis-accent',
      listening: 'text-jarvis-accent',
      processing: 'text-jarvis-accent-2',
      speaking: 'text-jarvis-accent-3',
      executing: 'text-jarvis-warning'
    }
    return colors[assistantState] || 'text-jarvis-text-dim'
  }, [assistantState])

  // Dynamic glow scale based on audio level for speaking state
  const glowScale = assistantState === 'speaking' ? 1 + audioLevel * 0.3 : 1
  const glowOpacity = assistantState === 'speaking' ? 0.5 + audioLevel * 0.5 : 1

  const getOrbClasses = (): string => {
    const base = 'relative w-[200px] h-[200px] rounded-full cursor-pointer transition-all duration-500 '

    switch (assistantState) {
      case 'idle':
        return base + 'animate-orb-pulse'
      case 'wake_word_detected':
        return base + 'animate-orb-glow-intense'
      case 'listening':
        return base + 'animate-orb-breathe'
      case 'processing':
        return base + 'animate-orb-glow'
      case 'speaking':
        return base
      case 'executing':
        return base + 'animate-orb-glow'
      default:
        return base + 'animate-orb-pulse'
    }
  }

  const handleClick = (): void => {
    const store = useAppStore.getState()
    if (store.pushToTalkActive) {
      store.setPushToTalkActive(false)
      store.setAssistantState('processing')
    } else {
      store.setPushToTalkActive(true)
      store.setAssistantState('listening')
    }
  }

  return (
    <div className="relative flex flex-col items-center justify-center select-none">
      {/* Ambient glow behind orb */}
      <div
        className="absolute w-[340px] h-[340px] rounded-full pointer-events-none"
        style={{
          background: `radial-gradient(circle, rgba(0, 212, 255, ${0.06 + audioLevel * 0.08}) 0%, rgba(14, 165, 233, 0.03) 40%, transparent 70%)`,
          transform: `scale(${glowScale * 1.1})`,
          transition: 'transform 0.15s ease-out, background 0.15s ease-out'
        }}
      />

      {/* Outer ring particles */}
      <div className="absolute w-[200px] h-[200px] pointer-events-none">
        {particles.map((p) => (
          <div
            key={p.id}
            className="absolute rounded-full"
            style={{
              width: p.size,
              height: p.size,
              background: `rgba(0, 212, 255, ${p.opacity})`,
              boxShadow: `0 0 ${p.size * 2}px rgba(0, 212, 255, ${p.opacity * 0.5})`,
              top: '50%',
              left: '50%',
              marginTop: -p.size / 2,
              marginLeft: -p.size / 2,
              animation: `${p.reverse ? 'particle-orbit-reverse' : 'particle-orbit'} ${p.duration}s linear infinite`,
              animationDelay: `${p.delay}s`,
              animationPlayState:
                assistantState === 'idle' ? 'running' : 'running'
            }}
          />
        ))}
      </div>

      {/* Ripple rings - shown on wake word detection and listening */}
      {(assistantState === 'wake_word_detected' || assistantState === 'listening') && (
        <>
          <div
            className="absolute w-[200px] h-[200px] rounded-full border border-jarvis-accent pointer-events-none animate-ripple"
            style={{ opacity: 0.6 }}
          />
          <div
            className="absolute w-[200px] h-[200px] rounded-full border border-jarvis-accent-2 pointer-events-none animate-ripple-delayed"
            style={{ opacity: 0.4 }}
          />
          {assistantState === 'wake_word_detected' && (
            <div
              className="absolute w-[200px] h-[200px] rounded-full border-2 border-jarvis-accent pointer-events-none animate-ring-expand"
            />
          )}
        </>
      )}

      {/* Processing orbital ring */}
      {assistantState === 'processing' && (
        <div className="absolute w-[230px] h-[230px] rounded-full pointer-events-none animate-orb-spin">
          <div
            className="absolute w-3 h-3 rounded-full bg-jarvis-accent top-0 left-1/2 -ml-1.5"
            style={{ boxShadow: '0 0 10px rgba(0, 212, 255, 0.8), 0 0 20px rgba(0, 212, 255, 0.4)' }}
          />
          <div
            className="absolute w-2 h-2 rounded-full bg-jarvis-accent-2 bottom-0 left-1/2 -ml-1"
            style={{
              boxShadow: '0 0 8px rgba(14, 165, 233, 0.8)',
              opacity: 0.7
            }}
          />
        </div>
      )}

      {/* Executing accent ring */}
      {assistantState === 'executing' && (
        <div
          className="absolute w-[220px] h-[220px] rounded-full pointer-events-none"
          style={{
            border: '2px solid rgba(0, 212, 255, 0.3)',
            animation: 'orb-spin 8s linear infinite'
          }}
        >
          <div
            className="absolute w-2.5 h-2.5 rounded-full bg-jarvis-warning -top-1 left-1/2 -ml-1"
            style={{ boxShadow: '0 0 10px rgba(245, 158, 11, 0.8)' }}
          />
        </div>
      )}

      {/* Main orb */}
      <div
        className={getOrbClasses()}
        onClick={handleClick}
        style={{
          transform: assistantState === 'speaking' ? `scale(${glowScale})` : undefined,
          transition: 'transform 0.1s ease-out',
          background: `
            radial-gradient(circle at 40% 35%, rgba(0, 212, 255, 0.25) 0%, transparent 50%),
            radial-gradient(circle at 60% 65%, rgba(14, 165, 233, 0.15) 0%, transparent 50%),
            radial-gradient(circle at 50% 50%, rgba(6, 182, 212, 0.2) 0%, rgba(0, 212, 255, 0.05) 40%, rgba(10, 14, 26, 0.8) 70%)
          `,
          boxShadow: assistantState === 'speaking'
            ? `0 0 ${30 + audioLevel * 50}px rgba(0, 212, 255, ${0.3 + audioLevel * 0.4}), 0 0 ${60 + audioLevel * 80}px rgba(0, 212, 255, ${0.15 + audioLevel * 0.2}), inset 0 0 ${30 + audioLevel * 30}px rgba(0, 212, 255, ${0.1 + audioLevel * 0.15})`
            : '0 0 30px rgba(0, 212, 255, 0.2), 0 0 60px rgba(0, 212, 255, 0.1), inset 0 0 30px rgba(0, 212, 255, 0.08)'
        }}
      >
        {/* Inner bright core */}
        <div
          className="absolute inset-[30%] rounded-full pointer-events-none"
          style={{
            background: `radial-gradient(circle, rgba(0, 212, 255, ${0.3 + audioLevel * 0.3}) 0%, rgba(14, 165, 233, 0.1) 50%, transparent 70%)`,
            opacity: glowOpacity,
            transition: 'opacity 0.1s ease-out'
          }}
        />

        {/* Surface highlight */}
        <div
          className="absolute inset-[10%] rounded-full pointer-events-none"
          style={{
            background:
              'radial-gradient(ellipse at 35% 25%, rgba(255, 255, 255, 0.08) 0%, transparent 60%)'
          }}
        />

        {/* Edge ring */}
        <div
          className="absolute inset-0 rounded-full pointer-events-none"
          style={{
            border: `1px solid rgba(0, 212, 255, ${0.15 + audioLevel * 0.2})`,
            transition: 'border-color 0.1s ease-out'
          }}
        />
      </div>

      {/* State label */}
      <div className="mt-6 flex flex-col items-center gap-1">
        <span
          className={`text-sm font-medium tracking-wider uppercase ${stateColor} transition-all duration-300`}
          style={{
            textShadow:
              assistantState !== 'idle'
                ? '0 0 10px rgba(0, 212, 255, 0.3)'
                : 'none'
          }}
        >
          {stateLabel}
        </span>
        {pushToTalkActive && (
          <span className="text-xs text-jarvis-accent animate-pulse-soft tracking-wide">
            Push-to-Talk Active
          </span>
        )}
        {!isConnected && (
          <span className="text-xs text-jarvis-danger animate-pulse-soft tracking-wide">
            Disconnected
          </span>
        )}
      </div>
    </div>
  )
}

export default Orb
