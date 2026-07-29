import React, { useEffect, useRef, useState } from 'react'
import { useAppStore } from '../stores/appStore'
import { createIdleHudScene, type IdleHudSceneApi } from '../lib/idleHudScene'

interface IdleHUDProps {
  onOrbClick?: () => void
}

export const IdleHUD: React.FC<IdleHUDProps> = ({ onOrbClick }) => {
  const assistantState = useAppStore((s) => s.assistantState)
  const audioLevel = useAppStore((s) => s.audioLevel)
  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<IdleHudSceneApi | null>(null)

  // Live time & date state
  const [now, setNow] = useState<Date>(new Date())

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(new Date())
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Initialize Three.js circular HUD scene
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const scene = createIdleHudScene(container)
    sceneRef.current = scene
    scene.setAssistantState(assistantState, audioLevel)

    return () => {
      scene.dispose()
      sceneRef.current = null
    }
  }, [])

  useEffect(() => {
    if (sceneRef.current) {
      sceneRef.current.setAssistantState(assistantState, audioLevel)
    }
  }, [assistantState, audioLevel])

  // Format Time & Date matching reference
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  const seconds = String(now.getSeconds()).padStart(2, '0')

  const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
  const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

  const dayName = days[now.getDay()]
  const dateNum = String(now.getDate()).padStart(2, '0')
  const monthName = months[now.getMonth()]
  const year = now.getFullYear()
  const dateStr = `${dayName} · ${dateNum} ${monthName} ${year}`

  const stateText =
    assistantState === 'listening'
      ? 'LISTENING • VOICE INPUT ACTIVE'
      : assistantState === 'thinking' || assistantState === 'processing'
      ? 'PROCESSING • ANALYZING INTENT'
      : 'STANDBY • SYSTEMS NOMINAL • SYS 1104057 F8-8468'

  return (
    <div
      onClick={onOrbClick}
      className="relative w-[380px] h-[380px] md:w-[450px] md:h-[450px] flex flex-col items-center justify-center cursor-pointer select-none group"
      title="Click to activate voice input"
    >
      {/* Three.js Canvas Container */}
      <div ref={containerRef} className="absolute inset-0 z-0 pointer-events-none" />

      {/* Central HUD Typography overlay */}
      <div className="relative z-10 flex flex-col items-center justify-center text-center p-6 space-y-1 bg-slate-950/30 rounded-full backdrop-blur-[2px] border border-cyan-500/10 shadow-[0_0_50px_rgba(0,229,255,0.15)] group-hover:shadow-[0_0_70px_rgba(0,229,255,0.3)] transition-all duration-500">
        {/* Digital Time: HH:MM with superscript SS */}
        <div className="flex items-baseline justify-center font-mono font-bold text-cyan-200 tracking-wider text-2xl md:text-3xl drop-shadow-[0_0_12px_rgba(0,229,255,0.8)]">
          <span>{hours}:{minutes}</span>
          <span className="text-[11px] md:text-[13px] ml-1 text-cyan-400 font-normal">{seconds}</span>
        </div>

        {/* J.A.R.V.I.S. Wordmark */}
        <h1 className="font-serif font-extrabold text-cyan-100 tracking-[0.3em] text-xl md:text-2xl drop-shadow-[0_0_16px_rgba(0,229,255,0.9)] my-0.5">
          J.A.R.V.I.S.
        </h1>

        {/* Tagline */}
        <p className="text-[8px] md:text-[9.5px] font-mono tracking-[0.25em] text-cyan-300/80 uppercase">
          JUST A RATHER VERY INTELLIGENT SYSTEM
        </p>

        {/* Live Date */}
        <div className="text-[9px] md:text-[10.5px] font-mono tracking-[0.2em] text-cyan-400/90 pt-0.5">
          {dateStr}
        </div>
      </div>

      {/* Bottom Glowing JARVIS Pill Badge */}
      <div className="absolute bottom-2 z-20 flex flex-col items-center">
        <div className="px-6 py-1.5 rounded-full bg-cyan-500/20 border border-cyan-400/60 shadow-[0_0_20px_rgba(0,229,255,0.6)] backdrop-blur-md">
          <span className="font-serif font-black tracking-[0.25em] text-xs md:text-sm text-cyan-100 drop-shadow-[0_0_10px_rgba(0,229,255,1)]">
            JARVIS
          </span>
        </div>
        <div className="mt-1 text-[8px] font-mono tracking-widest text-cyan-400/70 uppercase">
          {stateText}
        </div>
      </div>
    </div>
  )
}
