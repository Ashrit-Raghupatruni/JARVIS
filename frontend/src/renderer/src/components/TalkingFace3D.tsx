import React, { useEffect, useRef } from 'react'
import { useAppStore } from '../stores/appStore'
import { createTalkingFaceScene, type TalkingFaceSceneApi } from '../lib/talkingFaceScene'
import { RotateCw, Pause } from 'lucide-react'

interface TalkingFace3DProps {
  onOrbClick?: () => void
}

export const TalkingFace3D: React.FC<TalkingFace3DProps> = ({ onOrbClick }) => {
  const assistantState = useAppStore((s) => s.assistantState)
  const audioLevel = useAppStore((s) => s.audioLevel)
  const is3DRotationEnabled = useAppStore((s) => s.is3DRotationEnabled)
  const toggle3DRotation = useAppStore((s) => s.toggle3DRotation)

  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<TalkingFaceSceneApi | null>(null)

  // Initialize 3D Talking Face Scene
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const scene = createTalkingFaceScene(container)
    sceneRef.current = scene
    scene.setAssistantState(assistantState, audioLevel)

    return () => {
      scene.dispose()
      sceneRef.current = null
    }
  }, [])

  // Sync assistant state and Web Audio playback level into 3D scene
  useEffect(() => {
    if (sceneRef.current) {
      sceneRef.current.setAssistantState(assistantState, audioLevel)
    }
  }, [assistantState, audioLevel])

  return (
    <div
      onClick={onOrbClick}
      className="relative w-full h-full min-h-[400px] flex flex-col items-center justify-center cursor-pointer select-none group"
      title="Click to interrupt speech"
    >
      {/* Three.js Canvas Container */}
      <div ref={containerRef} className="absolute inset-0 z-0 pointer-events-none" />

      {/* Cybernetic Header HUD Bracket */}
      <div className="absolute top-2 left-4 right-4 z-10 flex items-center justify-between px-3 py-1 text-[10px] font-mono text-emerald-300/90 bg-slate-950/60 border border-emerald-500/30 rounded backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="font-bold tracking-widest text-emerald-200">JARVIS // FACECAP 3D NODE</span>
        </div>

        {/* 3D ROTATION TOGGLE BUTTON */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            toggle3DRotation()
          }}
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded border text-[10px] font-mono font-bold transition-all cursor-pointer ${
            is3DRotationEnabled
              ? 'bg-emerald-500/20 border-emerald-400 text-emerald-200 shadow-[0_0_10px_rgba(0,255,102,0.4)]'
              : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-slate-200'
          }`}
          title="Toggle 3D Head 360 Rotation ON / OFF"
        >
          {is3DRotationEnabled ? (
            <>
              <RotateCw className="w-3 h-3 animate-spin text-emerald-400" style={{ animationDuration: '4s' }} />
              <span>3D ROTATION: ON</span>
            </>
          ) : (
            <>
              <Pause className="w-3 h-3 text-slate-400" />
              <span>3D ROTATION: OFF</span>
            </>
          )}
        </button>
      </div>

      {/* Bottom Status Pill */}
      <div className="absolute bottom-2 z-20 flex flex-col items-center pointer-events-none">
        <div className="px-5 py-1 rounded-full bg-emerald-500/20 border border-emerald-400/50 shadow-[0_0_20px_rgba(0,255,102,0.6)] backdrop-blur-md">
          <span className="font-serif font-black tracking-[0.25em] text-xs md:text-sm text-emerald-100 drop-shadow-[0_0_8px_rgba(0,255,102,1)]">
            JARVIS SPEAKING...
          </span>
        </div>
      </div>
    </div>
  )
}
