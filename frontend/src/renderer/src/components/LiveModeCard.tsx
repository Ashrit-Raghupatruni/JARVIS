import React, { useState, useEffect } from 'react'
import { Eye, Play, Square, RefreshCw, Layout, Layers, CheckCircle, ShieldAlert, Cpu } from 'lucide-react'

export interface LiveFrame {
  is_live_mode_enabled: boolean
  active_app: string
  window_title: str
  active_workflow: str
  current_step: str
  next_logical_step?: string
  proactive_suggestion?: string
  detected_form_fields: number
  confidence_score: number
  scene_graph?: {
    window_title: string
    total_elements: number
    focused_element?: { name: string; control_type: string }
    elements: Array<{ id: string; name: string; control_type: string }>
  }
}

export default function LiveModeCard() {
  const [isEnabled, setIsEnabled] = useState(false)
  const [frame, setFrame] = useState<LiveFrame | null>(null)
  const [loading, setLoading] = useState(false)
  const [statusMsg, setStatusMsg] = useState('Live Mode Standing By')

  const fetchStatus = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/mobile/live_mode/status')
      const data = await res.json()
      if (data.status === 'active' && data.frame) {
        setIsEnabled(true)
        setFrame(data.frame)
        setStatusMsg(`Active in ${data.frame.window_title || data.frame.active_app}`)
      } else {
        setIsEnabled(false)
        setStatusMsg('Live Mode Standing By')
      }
    } catch (err) {
      console.error('[LiveMode] Error fetching status:', err)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 1500)
    return () => clearInterval(interval)
  }, [])

  const toggleLiveMode = async (enable: boolean) => {
    setLoading(true)
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/mobile/live_mode/toggle?enable=${enable}`, {
        method: 'POST'
      })
      const data = await res.json()
      setIsEnabled(data.live_mode_enabled)
      fetchStatus()
    } catch (err) {
      console.error('[LiveMode] Toggle error:', err)
    } finally {
      setLoading(false)
    }
  }

  const restoreWorkspace = async (preset: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/mobile/workspaces/restore?preset=${preset}`, {
        method: 'POST'
      })
      const data = await res.json()
      alert(data.result || `Workspace preset '${preset}' restored!`)
    } catch (err) {
      console.error('[Workspace] Restore error:', err)
    }
  }

  return (
    <div className="flex flex-col h-full w-full bg-slate-950/90 rounded-xl border border-cyan-500/20 overflow-hidden shadow-2xl backdrop-blur-xl p-4 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Eye className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>Dedicated Live Mode (AI Screen Assistant)</span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-bold ${
                  isEnabled
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_10px_rgba(0,229,255,0.3)]'
                    : 'bg-slate-800 text-slate-400 border border-slate-700'
                }`}
              >
                {isEnabled ? '● LIVE SCANNING (1.0 FPS)' : 'OFFLINE'}
              </span>
            </div>
            <div className="text-xs text-slate-400">
              Continuous desktop observation, Win32 UIA Scene Graph analysis & proactive guidance
            </div>
          </div>
        </div>

        {/* Live Controls */}
        <div className="flex items-center gap-2">
          {!isEnabled ? (
            <button
              onClick={() => toggleLiveMode(true)}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs transition-all shadow-[0_0_14px_rgba(0,229,255,0.4)] cursor-pointer disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>START LIVE MODE</span>
            </button>
          ) : (
            <button
              onClick={() => toggleLiveMode(false)}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/40 font-mono font-bold text-xs transition-all cursor-pointer disabled:opacity-50"
            >
              <Square className="w-4 h-4 fill-current" />
              <span>STOP LIVE MODE</span>
            </button>
          )}

          <button
            onClick={fetchStatus}
            className="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 cursor-pointer"
            title="Refresh Live Context"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Grid: Scene Graph Context + Proactive Guidance + Workspaces */}
      <div className="grid grid-cols-3 gap-4 flex-1 overflow-hidden">
        {/* Panel 1: Active App & Scene Graph */}
        <div className="col-span-1 bg-slate-900/60 rounded-lg border border-slate-800 p-3 flex flex-col gap-3 overflow-y-auto">
          <div className="text-xs font-mono font-bold text-cyan-400 uppercase flex items-center gap-1.5 border-b border-slate-800 pb-2">
            <Cpu className="w-3.5 h-3.5" />
            <span>Active Scene Perception</span>
          </div>

          <div className="space-y-2 text-xs font-mono">
            <div>
              <span className="text-slate-400">Foreground Window:</span>
              <div className="text-slate-100 font-semibold truncate">{frame?.window_title || 'Desktop'}</div>
            </div>

            <div>
              <span className="text-slate-400">Active App / Process ID:</span>
              <div className="text-cyan-300">{frame?.active_app || 'None'}</div>
            </div>

            <div>
              <span className="text-slate-400">Detected Control Nodes:</span>
              <div className="text-emerald-400 font-bold">{frame?.scene_graph?.total_elements || 0} Controls Parsed</div>
            </div>

            <div>
              <span className="text-slate-400">Focused Control:</span>
              <div className="text-slate-200">
                {frame?.scene_graph?.focused_element
                  ? `${frame.scene_graph.focused_element.name} (${frame.scene_graph.focused_element.control_type})`
                  : 'None'}
              </div>
            </div>
          </div>
        </div>

        {/* Panel 2: Proactive Guidance & Next Step */}
        <div className="col-span-1 bg-slate-900/60 rounded-lg border border-slate-800 p-3 flex flex-col gap-3 overflow-y-auto">
          <div className="text-xs font-mono font-bold text-cyan-400 uppercase flex items-center gap-1.5 border-b border-slate-800 pb-2">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Proactive AI Guidance</span>
          </div>

          <div className="space-y-3">
            <div className="p-2.5 rounded-lg bg-cyan-500/5 border border-cyan-500/20 text-xs">
              <div className="text-[10px] font-mono text-cyan-400 font-bold uppercase mb-1">Current Workflow</div>
              <div className="text-slate-100 font-medium">{frame?.active_workflow || 'General Workspace Assistance'}</div>
            </div>

            <div className="p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20 text-xs">
              <div className="text-[10px] font-mono text-emerald-400 font-bold uppercase mb-1">Proactive Suggestion</div>
              <div className="text-slate-200">{frame?.proactive_suggestion || 'JARVIS is observing your active desktop context...'}</div>
            </div>

            {frame?.next_logical_step && (
              <div className="p-2.5 rounded-lg bg-indigo-500/5 border border-indigo-500/20 text-xs">
                <div className="text-[10px] font-mono text-indigo-400 font-bold uppercase mb-1">Next Logical Step</div>
                <div className="text-indigo-200">{frame.next_logical_step}</div>
              </div>
            )}
          </div>
        </div>

        {/* Panel 3: Workspace Presets & Form Assistant */}
        <div className="col-span-1 bg-slate-900/60 rounded-lg border border-slate-800 p-3 flex flex-col gap-3 overflow-y-auto">
          <div className="text-xs font-mono font-bold text-cyan-400 uppercase flex items-center gap-1.5 border-b border-slate-800 pb-2">
            <Layout className="w-3.5 h-3.5" />
            <span>Workspace Layout Presets</span>
          </div>

          <div className="flex flex-col gap-2">
            <button
              onClick={() => restoreWorkspace('coding')}
              className="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-xs text-slate-100 font-mono cursor-pointer transition-all"
            >
              <span>💻 Coding Workspace</span>
              <span className="text-[10px] text-cyan-400">VS Code + Chrome</span>
            </button>

            <button
              onClick={() => restoreWorkspace('research')}
              className="flex items-center justify-between p-2.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-xs text-slate-100 font-mono cursor-pointer transition-all"
            >
              <span>🔬 Research Workspace</span>
              <span className="text-[10px] text-cyan-400">Browser + PDF</span>
            </button>
          </div>

          <div className="mt-auto pt-2 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between font-mono">
            <span>Form Fields Detected:</span>
            <span className="text-cyan-400 font-bold">{frame?.detected_form_fields || 0}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
