import React, { useMemo, useState, useRef, useEffect } from 'react'
import { useAppStore } from '../stores/appStore'

const Orb: React.FC = () => {
  const assistantState = useAppStore((s) => s.assistantState)
  const audioLevel = useAppStore((s) => s.audioLevel)
  const pushToTalkActive = useAppStore((s) => s.pushToTalkActive)
  const isConnected = useAppStore((s) => s.isConnected)

  const containerRef = useRef<HTMLDivElement | null>(null)
  const [tilt, setTilt] = useState({ rx: 0, ry: 0 })

  // 3D Parallax Mouse Tracking
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    const dx = e.clientX - cx
    const dy = e.clientY - cy
    
    // Maximum tilt angle in degrees
    const maxTilt = 18
    const rx = -(dy / (rect.height / 2)) * maxTilt
    const ry = (dx / (rect.width / 2)) * maxTilt
    
    setTilt({ rx, ry })
  }

  const handleMouseLeave = () => {
    // Smooth return to center
    setTilt({ rx: 0, ry: 0 })
  }

  // Dynamic values depending on assistant state
  const stateSpeedMultiplier = useMemo(() => {
    switch (assistantState) {
      case 'idle': return 0.5
      case 'wake_word_detected': return 3.0
      case 'listening': return 1.2 + audioLevel * 1.5
      case 'processing': return 4.0
      case 'speaking': return 1.0 + audioLevel * 2.0
      case 'executing': return 2.0
      default: return 0.5
    }
  }, [assistantState, audioLevel])

  const statePulseScale = useMemo(() => {
    if (assistantState === 'listening' || assistantState === 'speaking') {
      return 1.0 + audioLevel * 0.15
    }
    if (assistantState === 'wake_word_detected') {
      return 1.1
    }
    return 1.0
  }, [assistantState, audioLevel])

  const stateGlowIntensity = useMemo(() => {
    if (assistantState === 'idle') return 10
    if (assistantState === 'processing') return 20
    if (assistantState === 'speaking' || assistantState === 'listening') {
      return 15 + audioLevel * 30
    }
    return 25
  }, [assistantState, audioLevel])

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
      {/* Ambient background blueprint/grid glow */}
      <div 
        className="absolute w-[440px] h-[440px] rounded-full pointer-events-none transition-all duration-500"
        style={{
          background: `radial-gradient(circle, rgba(0, 229, 255, ${0.05 + audioLevel * 0.08}) 0%, rgba(0, 174, 255, 0.02) 45%, transparent 70%)`,
          transform: `scale(${statePulseScale * 1.05})`,
          filter: `blur(${15 + audioLevel * 20}px)`
        }}
      />

      {/* Main interactive 3D container */}
      <div
        ref={containerRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
        className="relative cursor-pointer transition-all duration-300 ease-out"
        style={{
          width: '380px',
          height: '380px',
          transform: `perspective(1000px) rotateX(${tilt.rx}deg) rotateY(${tilt.ry}deg)`,
          transformStyle: 'preserve-3d',
          transition: tilt.rx === 0 && tilt.ry === 0 ? 'transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)' : 'none'
        }}
      >
        {/* Layer 1: Background circuit schematic blueprint grid (Translates back in Z for parallax depth) */}
        <div 
          className="absolute inset-0 pointer-events-none opacity-20"
          style={{ transform: 'translateZ(-40px) scale(0.95)' }}
        >
          <svg viewBox="0 0 400 400" className="w-full h-full">
            {/* Fine circuit schematic lines */}
            <circle cx="200" cy="200" r="195" fill="none" stroke="var(--jarvis-border)" strokeWidth="0.5" />
            <line x1="200" y1="5" x2="200" y2="395" stroke="var(--jarvis-border)" strokeWidth="0.5" strokeDasharray="4 8" />
            <line x1="5" y1="200" x2="395" y2="200" stroke="var(--jarvis-border)" strokeWidth="0.5" strokeDasharray="4 8" />
            <circle cx="200" cy="200" r="160" fill="none" stroke="var(--jarvis-border)" strokeWidth="0.5" strokeDasharray="2 12" />
            
            {/* Architectural diagonal ticks */}
            <line x1="60" y1="60" x2="100" y2="100" stroke="var(--jarvis-border)" strokeWidth="0.5" />
            <line x1="340" y1="60" x2="300" y2="100" stroke="var(--jarvis-border)" strokeWidth="0.5" />
            <line x1="60" y1="340" x2="100" y2="300" stroke="var(--jarvis-border)" strokeWidth="0.5" />
            <line x1="340" y1="340" x2="300" y2="300" stroke="var(--jarvis-border)" strokeWidth="0.5" />
            
            {/* Technical annotations */}
            <text x="205" y="25" fill="var(--jarvis-border)" fontSize="6" fontFamily="monospace" letterSpacing="1">SEC_CLEARANCE: TOP</text>
            <text x="205" y="380" fill="var(--jarvis-border)" fontSize="6" fontFamily="monospace" letterSpacing="1">SYS_STATUS: ACTIVE</text>
            <text x="25" y="208" fill="var(--jarvis-border)" fontSize="6" fontFamily="monospace" letterSpacing="1" transform="rotate(-90 25 208)">CORE_TEMP: NORMAL</text>
          </svg>
        </div>

        {/* Layer 2: Main outer HUD rings (Translates mid Z-level) */}
        <div 
          className="absolute inset-0 pointer-events-none"
          style={{ 
            transform: 'translateZ(10px)',
            filter: `drop-shadow(0 0 ${stateGlowIntensity * 0.4}px rgba(0, 229, 255, 0.4))`
          }}
        >
          <svg viewBox="0 0 400 400" className="w-full h-full">
            {/* Outer dotted scale ring */}
            <circle 
              cx="200" 
              cy="200" 
              r="175" 
              fill="none" 
              stroke="var(--jarvis-accent-dim)" 
              strokeWidth="2" 
              strokeDasharray="2 6"
              style={{
                transformOrigin: '200px 200px',
                animation: `orb-spin ${30 / stateSpeedMultiplier}s linear infinite`
              }} 
            />

            {/* Segmented scale bracket ring */}
            <path 
              d="M 50 200 A 150 150 0 0 1 350 200" 
              fill="none" 
              stroke="var(--jarvis-accent)" 
              strokeWidth="2" 
              strokeDasharray="40 10 15 10 5 10" 
              style={{
                transformOrigin: '200px 200px',
                animation: `orb-spin ${20 / stateSpeedMultiplier}s linear infinite`
              }}
            />
            <path 
              d="M 350 200 A 150 150 0 0 1 50 200" 
              fill="none" 
              stroke="var(--jarvis-accent)" 
              strokeWidth="2" 
              strokeDasharray="40 10 15 10 5 10" 
              style={{
                transformOrigin: '200px 200px',
                animation: `orb-spin ${20 / stateSpeedMultiplier}s linear infinite`
              }}
            />

            {/* Heavy outer scale indicators (ticks) */}
            <circle 
              cx="200" 
              cy="200" 
              r="145" 
              fill="none" 
              stroke="var(--jarvis-accent-dim)" 
              strokeWidth="6" 
              strokeDasharray="2 12"
              style={{
                transformOrigin: '200px 200px',
                animation: `orb-spin ${45 / stateSpeedMultiplier}s linear infinite reverse`
              }}
            />
          </svg>
        </div>

        {/* Layer 3: Dynamic middle ring, orange highlight arc, and yellow dots (Translates closer in Z) */}
        <div 
          className="absolute inset-0 pointer-events-none"
          style={{ 
            transform: `translateZ(40px) scale(${statePulseScale})`,
            transition: 'transform 0.1s ease-out'
          }}
        >
          <svg viewBox="0 0 400 400" className="w-full h-full">
            {/* The signature orange/yellow highlight arc from reference image */}
            <path 
              d="M 90 200 A 110 110 0 0 1 200 90" 
              fill="none" 
              stroke="var(--jarvis-accent-3)" 
              strokeWidth="5" 
              strokeLinecap="round" 
              style={{
                transformOrigin: '200px 200px',
                animation: `orb-spin ${12 / stateSpeedMultiplier}s linear infinite`
              }}
            />

            {/* Glowing cyan arc block */}
            <path 
              d="M 200 310 A 110 110 0 0 1 90 200" 
              fill="none" 
              stroke="var(--jarvis-accent-2)" 
              strokeWidth="3" 
              strokeDasharray="50 15 5 10"
              style={{
                transformOrigin: '200px 200px',
                animation: `orb-spin ${8 / stateSpeedMultiplier}s linear infinite reverse`
              }}
            />

            {/* Concentric solid cyan ring segment with brackets */}
            <path 
              d="M 290 200 A 90 90 0 1 1 200 110" 
              fill="none" 
              stroke="var(--jarvis-accent)" 
              strokeWidth="1.5" 
              strokeDasharray="180 40 20 40"
              style={{
                transformOrigin: '200px 200px',
                animation: `orb-spin ${15 / stateSpeedMultiplier}s linear infinite`
              }}
            />

            {/* Little yellow warning indicator dots on the inner ring */}
            <g style={{
              transformOrigin: '200px 200px',
              animation: `orb-spin ${25 / stateSpeedMultiplier}s linear infinite`
            }}>
              <circle cx="200" cy="115" r="2.5" fill="var(--jarvis-accent-3)" />
              <circle cx="220" cy="118" r="2.5" fill="var(--jarvis-accent-3)" />
              <circle cx="180" cy="118" r="2.5" fill="var(--jarvis-accent-3)" />
              <circle cx="240" cy="126" r="2.5" fill="var(--jarvis-accent-3)" />
              <circle cx="160" cy="126" r="2.5" fill="var(--jarvis-accent-3)" />
            </g>
          </svg>
        </div>

        {/* Layer 4: Central J.A.R.V.I.S. Core & Text (Highest Z projection) */}
        <div 
          className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
          style={{ 
            transform: 'translateZ(75px)',
            filter: `drop-shadow(0 0 ${stateGlowIntensity * 0.5}px rgba(0, 229, 255, 0.6))`
          }}
        >
          {/* Glowing gradient center circle core */}
          <div 
            className="w-[120px] h-[120px] rounded-full flex items-center justify-center relative border border-jarvis-border-bright"
            style={{
              background: `
                radial-gradient(circle, rgba(0, 229, 255, ${0.15 + audioLevel * 0.3}) 0%, rgba(0, 174, 255, 0.05) 50%, rgba(7, 11, 19, 0.9) 80%)
              `,
              boxShadow: `inset 0 0 ${15 + audioLevel * 20}px rgba(0, 229, 255, 0.3)`
            }}
          >
            {/* Hexagon tech overlay inside center */}
            <div 
              className="absolute inset-2 opacity-[0.07]"
              style={{
                backgroundImage: `
                  linear-gradient(90deg, rgba(0,229,255,0.4) 1px, transparent 1px),
                  linear-gradient(0deg, rgba(0,229,255,0.4) 1px, transparent 1px)
                `,
                backgroundSize: '10px 10px'
              }}
            />

            {/* Dynamic visual indicator arc rotating inside the core */}
            <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full">
              <circle 
                cx="50" 
                cy="50" 
                r="45" 
                fill="none" 
                stroke="rgba(0, 229, 255, 0.2)" 
                strokeWidth="1" 
              />
              <circle 
                cx="50" 
                cy="50" 
                r="42" 
                fill="none" 
                stroke="var(--jarvis-accent-2)" 
                strokeWidth="2.5" 
                strokeDasharray="90 200"
                style={{
                  transformOrigin: '50px 50px',
                  animation: `orb-spin ${4 / stateSpeedMultiplier}s linear infinite`
                }}
              />
            </svg>

            {/* Glowing J.A.R.V.I.S. Text */}
            <span 
              className="text-lg font-bold tracking-[0.2em] font-mono text-glow transition-all duration-300 text-jarvis-text"
              style={{
                textShadow: `0 0 ${stateGlowIntensity * 0.5}px rgba(0, 229, 255, 0.8)`
              }}
            >
              JARVIS
            </span>
          </div>
        </div>
      </div>

      {/* Under-HUD State Label and Stats */}
      <div className="mt-8 flex flex-col items-center gap-1.5 z-10">
        <div className="flex items-center gap-2">
          {/* Glowing pulse dot */}
          <span 
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              assistantState === 'idle' ? 'bg-jarvis-text-muted opacity-60' :
              assistantState === 'listening' ? 'bg-jarvis-accent animate-ping' :
              assistantState === 'speaking' ? 'bg-jarvis-accent-2 animate-pulse-soft' :
              assistantState === 'processing' ? 'bg-jarvis-accent-3 animate-spin-smooth' :
              'bg-jarvis-warning animate-pulse'
            }`}
          />
          <span
            className="text-sm font-semibold tracking-[0.25em] uppercase transition-all duration-300 text-glow"
            style={{
              color: assistantState === 'idle' ? 'var(--jarvis-text-dim)' : 'var(--jarvis-accent)',
              textShadow: assistantState !== 'idle' ? '0 0 10px var(--jarvis-accent)' : 'none'
            }}
          >
            {assistantState === 'idle' && 'SYSTEM READY'}
            {assistantState === 'wake_word_detected' && 'WAKE DETECTED'}
            {assistantState === 'listening' && 'LISTENING'}
            {assistantState === 'processing' && 'THINKING'}
            {assistantState === 'speaking' && 'SPEAKING'}
            {assistantState === 'executing' && 'EXECUTING'}
          </span>
        </div>

        {pushToTalkActive && (
          <span className="text-xs text-jarvis-accent-2 animate-pulse-soft font-mono tracking-wider uppercase">
            PTT HOTKEY ACTIVE (CTRL+SPACE)
          </span>
        )}
        {!isConnected && (
          <span className="text-xs text-jarvis-danger animate-pulse-soft font-mono tracking-wider uppercase">
            CONNECTION LOST
          </span>
        )}
      </div>
    </div>
  )
}

export default Orb
