import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useAppStore } from '../stores/appStore'
import { createOrbScene, type OrbSceneApi } from '../lib/orbScene'
import { HandTracker, type TrackerStatus } from '../lib/handTracker'

type CameraState = 'off' | 'starting' | 'on' | 'error'

interface OrbProps {
  onOrbClick?: () => void
}

const MODE_LABEL: Record<string, string> = {
  idle: 'STANDBY',
  spin: 'SPIN',
  zoom: 'ZOOM'
}

const Orb: React.FC<OrbProps> = ({ onOrbClick }) => {
  const assistantState = useAppStore((s) => s.assistantState)
  const audioLevel = useAppStore((s) => s.audioLevel)
  const pushToTalkActive = useAppStore((s) => s.pushToTalkActive)
  const isConnected = useAppStore((s) => s.isConnected)

  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  const sceneRef = useRef<OrbSceneApi | null>(null)
  const trackerRef = useRef<HandTracker | null>(null)

  const [camera, setCamera] = useState<CameraState>('off')
  const [status, setStatus] = useState<TrackerStatus>({ hands: 0, mode: 'idle' })
  const [error, setError] = useState<string | null>(null)

  // Initialize Three.js scene
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const scene = createOrbScene(container)
    sceneRef.current = scene

    // Sync initial state
    scene.setAssistantState(assistantState, audioLevel)

    return () => {
      trackerRef.current?.stop()
      trackerRef.current = null
      scene.dispose()
      sceneRef.current = null
    }
  }, [])

  // Update scene state when store state changes
  useEffect(() => {
    if (sceneRef.current) {
      sceneRef.current.setAssistantState(assistantState, audioLevel)
    }
  }, [assistantState, audioLevel])

  const stopGestures = useCallback(() => {
    trackerRef.current?.stop()
    trackerRef.current = null
    setCamera('off')
    setStatus({ hands: 0, mode: 'idle' })
  }, [])

  const startGestures = useCallback(async () => {
    const video = videoRef.current
    const overlay = overlayRef.current
    if (!video || !overlay || trackerRef.current) return

    setCamera('starting')
    setError(null)

    const tracker = new HandTracker(video, overlay, {
      onRotate: (dt, dp) => sceneRef.current?.rotateBy(dt, dp),
      onZoom: (factor) => sceneRef.current?.zoomBy(factor),
      onStatus: setStatus
    })
    trackerRef.current = tracker

    try {
      await tracker.start()
      setCamera('on')
    } catch (err) {
      trackerRef.current = null;
      tracker.stop()
      setCamera('error')
      setError(
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? 'CAMERA ACCESS DENIED'
          : 'TRACKING INIT FAILED'
      )
    }
  }, [])

  const toggleGestures = useCallback(() => {
    if (trackerRef.current) stopGestures()
    else void startGestures()
  }, [startGestures, stopGestures])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const activeEl = document.activeElement?.tagName
      if (activeEl === 'INPUT' || activeEl === 'TEXTAREA') return

      switch (e.key) {
        case '+':
        case '=':
          sceneRef.current?.zoomIn()
          break;
        case '-':
        case '_':
          sceneRef.current?.zoomOut()
          break;
        case 'r':
        case 'R':
          sceneRef.current?.resetView()
          break;
        case 'g':
        case 'G':
          toggleGestures()
          break;
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggleGestures])

  const mouseDownTimeRef = useRef(0)
  const mouseDownPosRef = useRef({ x: 0, y: 0 })

  const handleMouseDown = (e: React.MouseEvent) => {
    mouseDownTimeRef.current = Date.now()
    mouseDownPosRef.current = { x: e.clientX, y: e.clientY }
  }

  const handleMouseUp = (e: React.MouseEvent) => {
    const elapsed = Date.now() - mouseDownTimeRef.current
    const dx = e.clientX - mouseDownPosRef.current.x
    const dy = e.clientY - mouseDownPosRef.current.y
    const dist = Math.hypot(dx, dy)

    if (elapsed < 300 && dist < 5) {
      onOrbClick?.()
    }
  }

  const cameraOn = camera === 'on'

  return (
    <div className="relative flex flex-col items-center justify-center select-none w-full max-w-[500px]">
      {/* 3D Container box - holographic projection window (fully transparent, borderless) */}
      <div
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        className="relative w-[450px] h-[450px] overflow-hidden transition-all duration-500"
      >
        {/* WebGL Canvas target */}
        <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

        {/* Central J.A.R.V.I.S. text overlay (matches Arc Reactor core layout from the reference image) */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none select-none z-10">
          <div 
            className="text-3xl font-black tracking-[0.25em] text-[#e1f5fe] text-glow font-sans uppercase"
            style={{
              textShadow: '0 0 15px rgba(0, 229, 255, 0.7)',
              letterSpacing: '0.25em'
            }}
          >
            J.A.R.V.I.S.
          </div>
          <span 
            className="text-[9px] tracking-[0.2em] font-black font-mono mt-2 uppercase transition-all duration-300"
            style={{
              color: assistantState === 'idle' ? 'var(--jarvis-text-dim)' : 'var(--jarvis-accent)',
              textShadow: assistantState !== 'idle' ? '0 0 8px var(--jarvis-accent)' : 'none'
            }}
          >
            {assistantState === 'sleeping' && 'STANDBY (SLEEPING)'}
            {assistantState === 'idle' && 'SYSTEM READY'}
            {assistantState === 'wake_word_detected' && 'WAKE DETECTED'}
            {assistantState === 'listening' && 'LISTENING...'}
            {assistantState === 'processing' && 'THINKING...'}
            {assistantState === 'speaking' && 'SPEAKING...'}
            {assistantState === 'executing' && 'EXECUTING...'}
            {assistantState === 'interrupted' && 'INTERRUPTED'}
            {assistantState === 'error' && 'PIPELINE ERROR'}
          </span>
        </div>

        {/* Retro visual scans overlays */}
        <div className="absolute inset-0 pointer-events-none overlay-vignette opacity-70" />
        <div className="absolute inset-0 pointer-events-none overlay-scanlines opacity-20" />
        <div className="absolute inset-0 pointer-events-none overlay-grain opacity-5" />

        {/* Mirrored webcam floating preview panel */}
        <div
          className={`camera-panel absolute bottom-3 right-3 w-[110px] h-[82px] border border-jarvis-border/60 rounded overflow-hidden bg-[#070b13]/90 shadow-md transition-all duration-300 ${cameraOn ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none'}`}
        >
          <video
            ref={videoRef}
            muted
            playsInline
            className="absolute inset-0 w-full h-full object-cover scale-x-[-1] opacity-75 filter sepia(1) hue-rotate-[170deg] saturate(2) brightness(0.85)"
          />
          <canvas ref={overlayRef} width={110} height={82} className="absolute inset-0 w-full h-full" />
          <div className="absolute bottom-0 left-0 right-0 py-0.5 px-1 bg-black/60 text-[8px] font-mono text-jarvis-accent tracking-wider leading-none">
            {status.hands > 0 ? `${status.hands}H · ${MODE_LABEL[status.mode]}` : 'SHOW HANDS'}
          </div>
        </div>



        {error && (
          <div className="absolute bottom-3 left-3 px-2 py-0.5 bg-black/75 border border-jarvis-danger rounded text-[9px] font-mono text-jarvis-danger tracking-wide animate-pulse">
            {error}
          </div>
        )}
      </div>

      {/* Under-HUD State Label and Action Buttons */}
      <div className="mt-4 flex flex-col items-center gap-3.5 z-10 w-full">
        {/* Sleek gesture controls bar */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            className={`px-3 py-1 border rounded text-[10px] font-mono font-bold tracking-wider cursor-pointer backdrop-blur transition-all duration-200 select-none ${
              cameraOn
                ? 'bg-jarvis-accent-dim/30 border-jarvis-accent text-jarvis-accent shadow-[0_0_10px_rgba(0,229,255,0.15)]'
                : 'bg-jarvis-surface-hover/20 border-jarvis-border/40 text-jarvis-text-dim hover:border-jarvis-accent-dim hover:text-jarvis-accent'
            }`}
            onClick={(e) => {
              e.stopPropagation()
              toggleGestures()
            }}
            disabled={camera === 'starting'}
          >
            {camera === 'starting' ? 'INITIALIZING...' : cameraOn ? 'GESTURES ON' : 'GESTURES OFF'}
          </button>
          <button
            type="button"
            className="px-2.5 py-1 border border-jarvis-border/40 rounded bg-jarvis-surface-hover/20 text-[10px] font-mono font-bold tracking-wider hover:border-jarvis-accent hover:text-jarvis-accent transition-all duration-200 select-none cursor-pointer"
            onClick={(e) => {
              e.stopPropagation()
              sceneRef.current?.resetView()
            }}
          >
            RESET
          </button>
        </div>

        {pushToTalkActive && (
          <span className="text-[9px] text-jarvis-accent-2 animate-pulse-soft font-mono tracking-widest uppercase">
            PTT HOTKEY ACTIVE (CTRL+SPACE)
          </span>
        )}
        {!isConnected && (
          <span className="text-[9px] text-jarvis-danger animate-pulse-soft font-mono tracking-widest uppercase">
            CONNECTION LOST
          </span>
        )}
      </div>
    </div>
  )
}

export default Orb
