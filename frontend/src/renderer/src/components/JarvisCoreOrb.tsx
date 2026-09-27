import React from 'react'
import { useAppStore } from '../stores/appStore'

interface JarvisCoreOrbProps {
  onToggleListening?: () => void
}

export const JarvisCoreOrb: React.FC<JarvisCoreOrbProps> = ({ onToggleListening }) => {
  const assistantState = useAppStore((s) => s.assistantState)
  const isListening = useAppStore((s) => s.isListening)
  const isSpeaking = useAppStore((s) => s.isSpeaking)
  const audioLevel = useAppStore((s) => s.audioLevel)
  const isConnected = useAppStore((s) => s.isConnected)

  const isActive = isListening || isSpeaking || assistantState === 'listening' || assistantState === 'speaking' || assistantState === 'processing'
  
  // Scale dynamically with audio reactivity (1.0 to 1.15)
  const reactiveScale = 1 + (audioLevel * 0.15)
  const auraGlow = isActive 
    ? 'rgba(0, 229, 255, 0.55)' 
    : 'rgba(59, 130, 246, 0.25)'

  const getStatusText = () => {
    if (!isConnected) return 'Offline - Connecting...'
    if (isListening || assistantState === 'listening') return 'Listening...'
    if (assistantState === 'processing') return 'Processing query...'
    if (isSpeaking || assistantState === 'speaking') return 'Responding...'
    return 'Ready for instructions'
  }

  const getStatusColor = () => {
    if (!isConnected) return 'text-amber-400 bg-amber-400'
    if (isListening || assistantState === 'listening') return 'text-cyan-300 bg-cyan-400'
    if (assistantState === 'processing') return 'text-blue-400 bg-blue-500'
    if (isSpeaking || assistantState === 'speaking') return 'text-emerald-400 bg-emerald-400'
    return 'text-cyan-400 bg-cyan-400'
  }

  return (
    <div className="flex flex-col items-center justify-center select-none relative group">
      {/* Outer Glow Halo */}
      <div 
        className="absolute w-72 h-72 rounded-full blur-3xl opacity-60 pointer-events-none transition-all duration-700"
        style={{
          background: `radial-gradient(circle, ${auraGlow} 0%, rgba(30, 58, 138, 0.2) 50%, transparent 75%)`,
          transform: `scale(${reactiveScale * 1.1})`
        }}
      />

      {/* Main Interactive Orb Container */}
      <div 
        onClick={onToggleListening}
        className="relative w-56 h-56 flex items-center justify-center cursor-pointer transition-transform duration-300 active:scale-95"
        style={{ transform: `scale(${reactiveScale})` }}
        title="Click to activate voice command"
      >
        {/* Orbital Ring 1 - Outer dashed counter-clockwise */}
        <div 
          className="absolute inset-0 rounded-full border border-cyan-400/20 border-dashed animate-spin"
          style={{ animationDuration: '24s', animationDirection: 'reverse' }}
        />

        {/* Orbital Ring 2 - Subtle tilt ring with accent dots */}
        <div 
          className="absolute inset-2 rounded-full border border-blue-500/25 animate-spin"
          style={{ animationDuration: '36s' }}
        >
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#00e5ff]" />
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_8px_#3b82f6]" />
        </div>

        {/* Orbital Ring 3 - Fast inner orbital ring */}
        <div 
          className="absolute inset-6 rounded-full border border-cyan-300/30 animate-spin"
          style={{ animationDuration: '16s' }}
        />

        {/* Dynamic Pulse Wave when active */}
        {isActive && (
          <div 
            className="absolute inset-3 rounded-full border-2 border-cyan-400/40 animate-ping pointer-events-none"
            style={{ animationDuration: '2.5s' }}
          />
        )}

        {/* Core Spherical Body with Realistic Specular Highlight */}
        <div className="relative w-40 h-40 rounded-full bg-gradient-to-br from-slate-900 via-[#071328] to-[#020617] border border-cyan-500/30 shadow-[inset_0_0_35px_rgba(0,229,255,0.35),0_0_25px_rgba(0,140,255,0.3)] flex flex-col items-center justify-center overflow-hidden">
          {/* Internal Swirling Plasma Cloud */}
          <div 
            className="absolute inset-0 opacity-40 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-400 via-blue-600 to-transparent blur-md animate-pulse"
            style={{ animationDuration: '4s' }}
          />

          {/* Top Specular Sheen */}
          <div className="absolute top-1 left-4 right-4 h-12 rounded-full bg-gradient-to-b from-white/20 to-transparent blur-[1px] pointer-events-none" />

          {/* JARVIS Typography */}
          <div className="relative z-10 flex flex-col items-center">
            <span className="text-xl font-bold tracking-[0.35em] text-white drop-shadow-[0_0_12px_rgba(0,229,255,0.8)] pl-1.5 select-none">
              JARVIS
            </span>
            <div className="w-8 h-0.5 mt-1.5 bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-80" />
          </div>

          {/* Reactive Waveform Line inside core */}
          <div className="absolute bottom-6 flex items-center justify-center gap-1 z-10">
            {[0.4, 0.7, 1.0, 0.8, 0.5].map((h, i) => (
              <span
                key={i}
                className="w-1 bg-cyan-400/80 rounded-full transition-all duration-150"
                style={{
                  height: isActive ? `${Math.max(4, 18 * h * (audioLevel + 0.3))}px` : '4px',
                  boxShadow: isActive ? '0 0 6px #00e5ff' : 'none'
                }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Status Label & Micro Copy */}
      <div className="mt-5 flex flex-col items-center text-center">
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/60 border border-white/10 backdrop-blur-md shadow-sm">
          <span className={`w-2 h-2 rounded-full animate-pulse ${getStatusColor().split(' ')[1]}`} />
          <span className={`text-xs font-medium tracking-wide ${getStatusColor().split(' ')[0]}`}>
            {getStatusText()}
          </span>
        </div>
        <p className="mt-1.5 text-[11px] text-slate-400/80 font-normal tracking-wide">
          Click or say <span className="text-cyan-400/90 font-medium">"Hey Jarvis"</span> to activate
        </p>
      </div>
    </div>
  )
}
