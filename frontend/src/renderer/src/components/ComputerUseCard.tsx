import React, { useState, useEffect } from 'react'
import { Monitor, Layers, Eye, RefreshCw, Camera, X } from 'lucide-react'

export default function ComputerUseCard() {
  const [inspecting, setInspecting] = useState(false)
  const [screenshotModal, setScreenshotModal] = useState<string | null>(null)
  const [hierarchy, setHierarchy] = useState({
    primaryResolution: '1920x1080',
    foregroundWindow: 'JARVIS AI OS Terminal',
    processName: 'WindowsTerminal.exe',
    hwnd: 0x102E4,
    accessibilityElements: 42,
    topWindows: [
      'JARVIS Command Center (HWND: 65821)',
      'Visual Studio Code - JARVIS (HWND: 12894)',
      'Windows Terminal (HWND: 40912)',
      'Google Chrome (HWND: 98124)',
    ]
  })

  const fetchActiveWindow = async () => {
    setInspecting(true)
    try {
      const res = await fetch('/api/ui/screen_inspector', { method: 'POST' })
      const data = await res.json()
      if (data.status === 'success' && data.window) {
        setHierarchy(prev => ({
          ...prev,
          primaryResolution: data.window.resolution || '1920x1080',
          foregroundWindow: data.window.title || 'Active Window',
          processName: data.window.process_name || 'System',
          hwnd: data.window.hwnd || 0x102E4,
          accessibilityElements: data.window.accessibility_elements_count || 42
        }))
      }
    } catch (e) {
      console.warn('Screen inspector fallback', e)
    } finally {
      setInspecting(false)
    }
  }

  const handleTakeScreenshot = async () => {
    try {
      const res = await fetch('/api/ui/take_screenshot', { method: 'POST' })
      const data = await res.json()
      if (data.status === 'success' && data.image_base64) {
        setScreenshotModal(data.image_base64)
      }
    } catch (e) {
      alert('Failed to capture screenshot.')
    }
  }

  useEffect(() => {
    fetchActiveWindow()
    const interval = setInterval(fetchActiveWindow, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="bg-slate-950/40 backdrop-blur-2xl border border-blue-500/20 rounded-2xl p-4 shadow-[0_8px_32px_0_rgba(0,0,0,0.37)] hover:border-cyan-500/30 transition-all">
      <div className="flex items-center justify-between pb-3 border-b border-white/5 mb-3">
        <div className="flex items-center gap-2">
          <Monitor className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-bold text-slate-200 tracking-[0.2em] uppercase font-mono">Computer Use & Inspector</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleTakeScreenshot}
            className="flex items-center gap-1.5 text-[10px] font-mono font-semibold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2.5 py-1 rounded-full transition-all cursor-pointer shadow-sm"
            title="Capture Screenshot"
          >
            <Camera className="w-3.5 h-3.5" />
            <span>Capture</span>
          </button>
          <button
            onClick={fetchActiveWindow}
            disabled={inspecting}
            className="flex items-center gap-1.5 text-[10px] font-mono font-semibold bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-2.5 py-1 rounded-full transition-all cursor-pointer shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${inspecting ? 'animate-spin' : ''}`} />
            {inspecting ? 'Scanning...' : 'Inspect'}
          </button>
        </div>
      </div>

      <div className="space-y-2 text-xs">
        <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/40 border border-white/5 shadow-inner">
          <span className="text-slate-400 font-medium">Primary Monitor:</span>
          <span className="font-mono text-cyan-300 font-semibold">{hierarchy.primaryResolution}</span>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/40 border border-white/5 shadow-inner">
          <span className="text-slate-400 font-medium">Focused Window:</span>
          <span className="font-mono text-emerald-400 font-semibold truncate max-w-[220px]" title={hierarchy.foregroundWindow}>
            {hierarchy.foregroundWindow}
          </span>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/40 border border-white/5 shadow-inner">
          <span className="text-slate-400 font-medium">Process / HWND:</span>
          <span className="font-mono text-amber-300 font-semibold">
            {hierarchy.processName} (0x{hierarchy.hwnd.toString(16).toUpperCase()})
          </span>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/40 border border-white/5 shadow-inner">
          <span className="text-slate-400 font-medium">Accessibility Nodes:</span>
          <span className="font-mono text-indigo-300 font-semibold">{hierarchy.accessibilityElements} UI elements</span>
        </div>

        <div className="mt-2 pt-2 border-t border-[rgba(0,229,255,0.1)]">
          <div className="text-[10px] font-mono text-[#b0bec5] mb-1 flex items-center gap-1">
            <Layers className="w-3 h-3 text-[#00e5ff]" /> Top Active Desktop Windows:
          </div>
          <div className="space-y-1">
            {hierarchy.topWindows.map((win, i) => (
              <div key={i} className="text-[10px] font-mono text-slate-300 truncate bg-[rgba(0,0,0,0.2)] px-2 py-0.5 rounded border border-slate-800">
                • {win}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
