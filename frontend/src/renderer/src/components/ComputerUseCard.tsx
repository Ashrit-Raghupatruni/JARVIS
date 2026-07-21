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
    <div className="bg-[rgba(10,20,38,0.75)] backdrop-blur-md border border-[rgba(0,229,255,0.18)] rounded-xl p-3 shadow-lg hover:border-[rgba(0,229,255,0.35)] transition-all">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Monitor className="w-4 h-4 text-[#00e5ff]" />
          <span className="text-xs font-semibold text-[#00e5ff] tracking-wider uppercase">Computer Use & Inspector</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleTakeScreenshot}
            className="flex items-center gap-1 text-[10px] font-mono bg-[rgba(0,230,118,0.1)] hover:bg-[rgba(0,230,118,0.2)] text-[#00e676] border border-[rgba(0,230,118,0.3)] px-2 py-0.5 rounded-md transition-all"
            title="Capture Screenshot"
          >
            <Camera className="w-3 h-3" />
            <span>Capture</span>
          </button>
          <button
            onClick={fetchActiveWindow}
            disabled={inspecting}
            className="flex items-center gap-1 text-[10px] font-mono bg-[rgba(0,229,255,0.1)] hover:bg-[rgba(0,229,255,0.2)] text-[#00e5ff] border border-[rgba(0,229,255,0.3)] px-2 py-0.5 rounded-md transition-all"
          >
            <RefreshCw className={`w-3 h-3 ${inspecting ? 'animate-spin' : ''}`} />
            {inspecting ? 'Scanning...' : 'Inspect'}
          </button>
        </div>
      </div>

      <div className="space-y-1.5 text-xs">
        <div className="flex items-center justify-between p-1.5 rounded-md bg-[rgba(15,30,56,0.4)] border border-[rgba(0,229,255,0.08)]">
          <span className="text-[#b0bec5]">Primary Monitor:</span>
          <span className="font-mono text-[#00e5ff] font-semibold">{hierarchy.primaryResolution}</span>
        </div>

        <div className="flex items-center justify-between p-1.5 rounded-md bg-[rgba(15,30,56,0.4)] border border-[rgba(0,229,255,0.08)]">
          <span className="text-[#b0bec5]">Focused Window:</span>
          <span className="font-mono text-[#00e676] font-semibold truncate max-w-[170px]" title={hierarchy.foregroundWindow}>
            {hierarchy.foregroundWindow}
          </span>
        </div>

        <div className="flex items-center justify-between p-1.5 rounded-md bg-[rgba(15,30,56,0.4)] border border-[rgba(0,229,255,0.08)]">
          <span className="text-[#b0bec5]">Process / HWND:</span>
          <span className="font-mono text-[#ffaa00] font-semibold">
            {hierarchy.processName} (0x{hierarchy.hwnd.toString(16).toUpperCase()})
          </span>
        </div>

        <div className="flex items-center justify-between p-1.5 rounded-md bg-[rgba(15,30,56,0.4)] border border-[rgba(0,229,255,0.08)]">
          <span className="text-[#b0bec5]">Accessibility Nodes:</span>
          <span className="font-mono text-[#d500f9] font-semibold">{hierarchy.accessibilityElements} UI elements</span>
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
