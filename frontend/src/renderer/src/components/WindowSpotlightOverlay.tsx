import React, { useEffect, useState } from 'react'
import { useAppStore } from '../stores/appStore'

export const WindowSpotlightOverlay: React.FC = () => {
  const { liveModeStatus } = useAppStore()
  const { isActive, activeApp, windowTitle, windowBounds } = liveModeStatus

  const [coords, setCoords] = useState<{ x: number; y: number; w: number; h: number } | null>(null)

  useEffect(() => {
    if (isActive && windowBounds && windowBounds.w > 0 && windowBounds.h > 0) {
      setCoords(windowBounds)
    } else {
      setCoords(null)
    }
  }, [isActive, windowBounds])

  if (!isActive || !coords) {
    return null
  }

  return (
    <div className="fixed inset-0 pointer-events-none z-[9999] overflow-hidden">
      {/* High-Contrast Focused Window Spotlight Frame */}
      <div
        className="absolute rounded-lg transition-all duration-150 ease-out"
        style={{
          left: `${coords.x}px`,
          top: `${coords.y}px`,
          width: `${coords.w}px`,
          height: `${coords.h}px`,
          border: '2px solid rgba(0, 229, 255, 0.85)',
          boxShadow: '0 0 25px rgba(0, 229, 255, 0.45), inset 0 0 15px rgba(0, 229, 255, 0.15)',
        }}
      >
        {/* HUD Corner Accents */}
        <div className="absolute -top-1 -left-1 w-3.5 h-3.5 border-t-2 border-l-2 border-cyan-300" />
        <div className="absolute -top-1 -right-1 w-3.5 h-3.5 border-t-2 border-r-2 border-cyan-300" />
        <div className="absolute -bottom-1 -left-1 w-3.5 h-3.5 border-b-2 border-l-2 border-cyan-300" />
        <div className="absolute -bottom-1 -right-1 w-3.5 h-3.5 border-b-2 border-r-2 border-cyan-300" />

        {/* Floating Active Application Tag Badge */}
        <div className="absolute -top-7 left-2 flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-slate-950/90 border border-cyan-400/50 text-[10px] font-mono text-cyan-300 shadow-lg backdrop-blur-md">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          <span className="font-bold uppercase tracking-wider">{activeApp || 'App'}</span>
          <span className="text-slate-400 truncate max-w-[200px]">| {windowTitle || 'Active'}</span>
        </div>
      </div>
    </div>
  )
}

export default WindowSpotlightOverlay
