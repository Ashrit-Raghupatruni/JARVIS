import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '../stores/appStore'
import { createOrbScene, type OrbSceneApi } from '../lib/orbScene'
import { IdleHUD } from './IdleHUD'
import { RotateCw, Pause } from 'lucide-react'

type CameraState = 'off' | 'starting' | 'on' | 'error'

interface OrbProps {
  onOrbClick?: () => void
}

const Orb: React.FC<OrbProps> = ({ onOrbClick }) => {
  const assistantState = useAppStore((s) => s.assistantState)
  const audioLevel = useAppStore((s) => s.audioLevel)
  const pushToTalkActive = useAppStore((s) => s.pushToTalkActive)
  const isConnected = useAppStore((s) => s.isConnected)
  const is3DRotationEnabled = useAppStore((s) => s.is3DRotationEnabled)
  const toggle3DRotation = useAppStore((s) => s.toggle3DRotation)

  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<OrbSceneApi | null>(null)

  const [camera, setCamera] = useState<CameraState>('off')
  const [status, setStatus] = useState<TrackerStatus>({ hands: 0, mode: 'idle' })
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'auto' | 'hud' | 'reactor'>('auto')

  // Determine active visual component
  const isSpeaking = assistantState === 'speaking' || assistantState === 'listening' || assistantState === 'processing'
  const activeVisual =
    viewMode === 'auto'
      ? (isSpeaking ? 'reactor' : 'hud')
      : viewMode === 'reactor'
      ? 'reactor'
      : 'hud'

  // Initialize Three.js Arc Reactor scene if in reactor mode
  useEffect(() => {
    if (activeVisual !== 'reactor') return
    const container = containerRef.current
    if (!container) return
    const scene = createOrbScene(container)
    sceneRef.current = scene

    scene.setAssistantState(assistantState, audioLevel)

    return () => {
      trackerRef.current?.stop()
      trackerRef.current = null
      scene.dispose()
      sceneRef.current = null
    }
  }, [activeVisual])

  useEffect(() => {
    if (sceneRef.current && activeVisual === 'reactor') {
      sceneRef.current.setAssistantState(assistantState, audioLevel)
    }
  }, [assistantState, audioLevel, activeVisual])

  return (
    <div className="w-full h-full flex flex-col items-center justify-between relative overflow-hidden select-none p-2">
      {/* ── Active Visual Container (Fills Hero Area) ────────────────────────── */}
      <div className="w-full flex-1 flex items-center justify-center relative overflow-hidden">
        {/* State 1: Idle Circular Tech HUD (Ambient / Passive Display) */}
        {activeVisual === 'hud' && (
          <IdleHUD onOrbClick={onOrbClick} />
        )}

        {/* State 2: Classic 3D Arc Reactor Orb */}
        {activeVisual === 'reactor' && (
          <div
            onClick={onOrbClick}
            className="relative w-full h-full max-w-[480px] max-h-[480px] overflow-hidden transition-all duration-500 rounded-full border border-emerald-500/20"
          >
            <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
          </div>
        )}
      </div>

      {/* Sleek Green Hacker Mode Switcher & 3D Rotation Bar */}
      <div className="mt-2 flex items-center gap-2 z-30">
        <button
          type="button"
          onClick={() => setViewMode('auto')}
          className={`px-3 py-1 border rounded text-[10px] font-mono font-bold tracking-wider cursor-pointer transition-all ${
            viewMode === 'auto'
              ? 'bg-emerald-500/20 border-emerald-400 text-emerald-200 shadow-[0_0_10px_rgba(0,255,102,0.3)]'
              : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          title="Auto-switch between Idle HUD and 3D Arc Reactor during speech"
        >
          AUTO DISPLAY
        </button>

        <button
          type="button"
          onClick={() => setViewMode('hud')}
          className={`px-3 py-1 border rounded text-[10px] font-mono font-bold tracking-wider cursor-pointer transition-all ${
            viewMode === 'hud'
              ? 'bg-emerald-500/20 border-emerald-400 text-emerald-200 shadow-[0_0_10px_rgba(0,255,102,0.3)]'
              : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          title="Lock display to Idle HUD"
        >
          HUD
        </button>

        <button
          type="button"
          onClick={() => setViewMode('reactor')}
          className={`px-3 py-1 border rounded text-[10px] font-mono font-bold tracking-wider cursor-pointer transition-all ${
            viewMode === 'reactor'
              ? 'bg-emerald-500/20 border-emerald-400 text-emerald-200 shadow-[0_0_10px_rgba(0,255,102,0.3)]'
              : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          title="Lock display to 3D Arc Reactor"
        >
          ARC REACTOR
        </button>

        {/* 3D ROTATION TOGGLE BUTTON */}
        <button
          type="button"
          onClick={toggle3DRotation}
          className={`flex items-center gap-1.5 px-3 py-1 border rounded text-[10px] font-mono font-bold tracking-wider cursor-pointer transition-all ${
            is3DRotationEnabled
              ? 'bg-emerald-500/20 border-emerald-400 text-emerald-200 shadow-[0_0_10px_rgba(0,255,102,0.4)]'
              : 'bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200'
          }`}
          title="Toggle Arc Reactor 3D 360-Degree Rotation ON / OFF"
        >
          {is3DRotationEnabled ? (
            <>
              <RotateCw className="w-3 h-3 animate-spin text-emerald-400" style={{ animationDuration: '4s' }} />
              <span>ROTATE: ON</span>
            </>
          ) : (
            <>
              <Pause className="w-3 h-3 text-slate-400" />
              <span>ROTATE: OFF</span>
            </>
          )}
        </button>
      </div>

      {pushToTalkActive && (
        <span className="mt-1 text-[9px] text-emerald-300 animate-pulse font-mono tracking-widest uppercase z-20">
          PTT HOTKEY ACTIVE (CTRL+SPACE)
        </span>
      )}
      {!isConnected && (
        <span className="mt-1 text-[9px] text-rose-400 animate-pulse font-mono tracking-widest uppercase z-20">
          CONNECTION LOST
        </span>
      )}
    </div>
  )
}

export default Orb
