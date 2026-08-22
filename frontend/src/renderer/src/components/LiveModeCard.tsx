import React, { useState, useEffect, useRef } from 'react'
import { Eye, Play, Square, RefreshCw, Layout, Layers, CheckCircle, ShieldAlert, Cpu } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { HandTracker, type TrackerTelemetry } from '../lib/handTracker'

export interface LiveFrame {
  is_live_mode_enabled: boolean
  active_app: string
  window_title: string
  active_workflow: string
  current_step: string
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
  const { settings, updateHandControlSettings } = useAppStore()
  const { sendMessage } = useWebSocket()
  const handControlEnabled = settings.handControl?.enabled ?? false

  const [isEnabled, setIsEnabled] = useState(false)
  const [frame, setFrame] = useState<LiveFrame | null>(null)
  const [loading, setLoading] = useState(false)
  const [statusMsg, setStatusMsg] = useState('Live Mode Standing By')

  // Webcam & Hand landmarker refs
  const videoRef = useRef<HTMLVideoElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  const trackerRef = useRef<HandTracker | null>(null)

  const [telemetry, setTelemetry] = useState<TrackerTelemetry>({
    hands: 0,
    fps: 0,
    activeGesture: 'NONE',
    confidence: 0,
    handControlActive: false
  })

  // Real Monitored Topics State & Safety Guardrails
  const [monitoredTopics, setMonitoredTopics] = useState<string[]>([
    'quantum computing advances',
    'ai os integration'
  ])
  const [newTopicInput, setNewTopicInput] = useState('')
  const [topicStatusMsg, setTopicStatusMsg] = useState<string | null>(null)

  useEffect(() => {
    fetchMonitoredTopics()
  }, [])

  const fetchMonitoredTopics = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/monitored_topics')
      if (res.ok) {
        const data = await res.json()
        if (data.monitored_topics) {
          setMonitoredTopics(data.monitored_topics)
        }
      }
    } catch {
      // Fallback
    }
  }

  const handleAddTopic = async (topicToAdd: string) => {
    const clean = topicToAdd.trim()
    if (!clean) return
    const blocked = ['crypto', 'bitcoin', 'ethereum', 'forex', 'daytrading', 'gambling', 'casino']
    if (blocked.some((b) => clean.toLowerCase().includes(b))) {
      setTopicStatusMsg('⚠️ Safety Policy Alert: Financial, crypto, day-trading, and gambling topics are blocked by content safety policy.')
      return
    }

    try {
      const res = await fetch('http://localhost:8000/api/v1/monitored_topics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: clean })
      })
      const data = await res.json()
      if (data.status === 'blocked') {
        setTopicStatusMsg(`⚠️ Safety Policy Alert: ${data.reason}`)
        return
      }
      if (data.monitored_topics) {
        setMonitoredTopics(data.monitored_topics)
        setTopicStatusMsg(`✓ Added monitored topic: '${clean}'`)
        setNewTopicInput('')
        return
      }
    } catch {
      if (!monitoredTopics.includes(clean)) {
        setMonitoredTopics([...monitoredTopics, clean])
        setTopicStatusMsg(`✓ Added monitored topic: '${clean}' (Local)`)
        setNewTopicInput('')
      }
    }
  }

  const handleRemoveTopic = async (topicToRemove: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/monitored_topics/${encodeURIComponent(topicToRemove)}`, {
        method: 'DELETE'
      })
      const data = await res.json()
      if (data.monitored_topics) {
        setMonitoredTopics(data.monitored_topics)
        setTopicStatusMsg(`✓ Removed monitored topic: '${topicToRemove}'`)
        return
      }
    } catch {
      // Fallback
    }
    setMonitoredTopics(monitoredTopics.filter((t) => t !== topicToRemove))
    setTopicStatusMsg(`✓ Removed monitored topic: '${topicToRemove}'`)
  }

  // Start/Stop Hand Tracker reactively (Gated strictly to Live Mode active + Hand Control enabled)
  useEffect(() => {
    if (!isEnabled || !handControlEnabled) {
      if (trackerRef.current) {
        trackerRef.current.stop()
        trackerRef.current = null
      }
      return
    }

    const video = videoRef.current
    const overlay = overlayRef.current
    if (!video || !overlay) return

    const tracker = new HandTracker(video, overlay, {
      onHandAction: (action, params) => {
        if (action === 'click') {
          sendMessage('hand_action', {
            action: 'click',
            click_action: params.action || 'click',
            button: params.button || 'left'
          })
        } else {
          sendMessage('hand_action', { action, ...params })
        }
      },
      onTelemetry: (tel) => {
        setTelemetry(tel)
      }
    })

    tracker.updateConfigs(settings.handControl)
    tracker.start().then(() => {
      trackerRef.current = tracker
    }).catch((err) => {
      console.error('[LiveModeCard] Failed to start hand landmarker:', err)
    })

    return () => {
      tracker.stop()
      trackerRef.current = null
    }
  }, [isEnabled, handControlEnabled])

  // Watch for setting changes (sensitivity, smoothing, camera, etc.)
  useEffect(() => {
    if (trackerRef.current) {
      trackerRef.current.updateConfigs(settings.handControl)
    }
  }, [settings.handControl])

  const fetchStatus = async () => {
    try {
      const host = typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' ? window.location.hostname : '127.0.0.1'
      const res = await fetch(`http://${host}:8000/api/live_mode/status`)
      const data = await res.json()
      if (data.status === 'active' && data.frame) {
        setIsEnabled(true)
        setFrame(data.frame)
        setStatusMsg(`Active in ${data.frame.window_title || data.frame.active_app}`)
        
        // Notify Electron to update spotlight cutout bounds
        if (typeof window !== 'undefined' && (window as any).electron?.ipcRenderer) {
          const bounds = data.frame.window_bounds || { x: 100, y: 80, w: 1000, h: 700 }
          ;(window as any).electron.ipcRenderer.invoke('live-mode:update-spotlight', bounds)
        }
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
      const host = typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' ? window.location.hostname : '127.0.0.1'
      const res = await fetch(`http://${host}:8000/api/live_mode/toggle?enable=${enable}`, {
        method: 'POST'
      })
      const data = await res.json()
      setIsEnabled(data.live_mode_enabled)

      if (data.live_mode_enabled) {
        useAppStore.getState().setAssistantState('listening')
        setStatusMsg('🎤 Hands-Free Voice Control Active')
      } else {
        useAppStore.getState().setAssistantState('idle')
        setStatusMsg('Live Mode Standing By')
      }

      // Toggle Electron system-wide spotlight overlay
      if (typeof window !== 'undefined' && (window as any).electron?.ipcRenderer) {
        ;(window as any).electron.ipcRenderer.invoke('live-mode:toggle-overlay', data.live_mode_enabled)
      }

      fetchStatus()
    } catch (err) {
      console.error('[LiveMode] Toggle error:', err)
    } finally {
      setLoading(false)
    }
  }

  const restoreWorkspace = async (preset: string) => {
    try {
      const host = typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' ? window.location.hostname : '127.0.0.1'
      const res = await fetch(`http://${host}:8000/api/v1/mobile/workspaces/restore?preset=${preset}`, {
        method: 'POST'
      })
      const data = await res.json()
      alert(data.result || `Workspace preset '${preset}' restored!`)
    } catch (err) {
      console.error('[Workspace] Restore error:', err)
    }
  }

  return (
    <div className={`flex flex-col h-full w-full bg-slate-950/90 rounded-xl border transition-all duration-300 overflow-hidden backdrop-blur-xl p-4 gap-4 ${
      isEnabled
        ? 'border-cyan-400 shadow-[0_0_30px_rgba(0,229,255,0.35)] ring-1 ring-cyan-400/50'
        : 'border-cyan-500/20 shadow-2xl'
    }`}>
      {/* Background Dimming Backdrop when Live Mode is active */}
      {isEnabled && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-[2px] pointer-events-none z-30 transition-opacity duration-300" />
      )}

      {/* Active Spotlight Highlight Banner */}
      {isEnabled && (
        <div className="relative z-40 flex items-center justify-between px-3.5 py-2 bg-cyan-950/90 border border-cyan-400 rounded-lg shadow-[0_0_20px_rgba(0,229,255,0.4)] animate-pulse">
          <div className="flex items-center gap-2.5 text-xs font-mono font-bold text-cyan-300">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_10px_#00e5ff] animate-ping" />
            <span>⚡ LIVE PERCEPTION & SPOTLIGHT ACTIVE ── HIGHLIGHTING:</span>
            <span className="text-white px-2 py-0.5 rounded bg-cyan-500/20 border border-cyan-400/40">
              {frame?.window_title || frame?.active_app || 'Desktop Workspace'}
            </span>
          </div>
          <span className="text-[10px] font-mono text-cyan-400 font-bold">1.0 FPS UIA PERCEPTION SCANNING</span>
        </div>
      )}

      {/* Header */}
      <div className="relative z-40 flex items-center justify-between border-b border-cyan-500/20 pb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Eye className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="text-base font-bold text-slate-100 flex items-center gap-2">
              <span>Dedicated Live Mode & Hand Gesture HUD</span>
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
              Desktop observation, Win32 UIA Scene Graph analysis & low-latency gesture cursor controls
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

          {/* Toggle Hand Gesture Control */}
          <button
            onClick={() => updateHandControlSettings({ enabled: !handControlEnabled })}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono font-bold text-xs transition-all cursor-pointer ${
              handControlEnabled
                ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-[0_0_14px_rgba(0,229,255,0.4)]'
                : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>HAND CONTROL: {handControlEnabled ? 'ON' : 'OFF'}</span>
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchStatus}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700 cursor-pointer"
              title="Refresh Perception Status"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Grid: Scene Graph Context + Proactive Guidance + Workspaces + Telemetry Preview */}
      <div className="relative z-40 grid grid-cols-1 md:grid-cols-4 gap-4 flex-1 overflow-hidden">
        {/* Panel 1: Hand Gesture Control Telemetry */}
        <div className="col-span-1 bg-slate-900/60 rounded-lg border border-slate-800 p-3 flex flex-col gap-3">
          <div className="text-xs font-mono font-bold text-cyan-400 uppercase flex items-center gap-1.5 border-b border-slate-800 pb-2">
            <Cpu className="w-3.5 h-3.5" />
            <span>Hand Telemetry HUD</span>
          </div>

          {handControlEnabled ? (
            <div className="flex flex-col gap-3 flex-1">
              <div className="relative w-full h-[140px] rounded-lg overflow-hidden bg-slate-950 border border-cyan-500/20 flex items-center justify-center">
                <video
                  ref={videoRef}
                  playsInline
                  muted
                  autoPlay
                  className="absolute inset-0 w-full h-full object-cover scale-x-[-1] opacity-70"
                />
                <canvas
                  ref={overlayRef}
                  width={320}
                  height={240}
                  className="absolute inset-0 w-full h-full object-cover pointer-events-none z-10"
                />
                <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-950/80 text-[9px] font-mono text-cyan-400 border border-cyan-500/20 z-20 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                  LIVE PREVIEW
                </div>
              </div>

              <div className="space-y-1.5 text-[11px] font-mono">
                <div className="flex justify-between items-center border-b border-slate-800/60 pb-1">
                  <span className="text-slate-400">Camera Device</span>
                  <span className="text-cyan-400 font-bold">● ON</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-800/60 pb-1">
                  <span className="text-slate-400">Hand Detection</span>
                  <span className={telemetry.hands > 0 ? 'text-cyan-400 font-bold' : 'text-slate-500'}>
                    {telemetry.hands > 0 ? '● TRACKED' : '○ NONE'}
                  </span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-800/60 pb-1">
                  <span className="text-slate-400">Active Gesture</span>
                  <span className={telemetry.activeGesture !== 'NONE' ? 'text-cyan-400 font-bold' : 'text-slate-500'}>
                    {telemetry.activeGesture}
                  </span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-800/60 pb-1">
                  <span className="text-slate-400">Processor FPS</span>
                  <span className="text-slate-200 font-bold">{telemetry.fps} FPS</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-800/60 pb-1">
                  <span className="text-slate-400">Confidence Score</span>
                  <span className="text-cyan-400 font-bold">{telemetry.confidence}%</span>
                </div>
              </div>

              {/* Live Gesture Sensitivity & Smoothing Tuning Sliders */}
              <div className="mt-2 pt-2 border-t border-slate-800/80 space-y-2 font-mono text-[10px]">
                <div>
                  <div className="flex justify-between text-slate-400 mb-1">
                    <span>Sensitivity</span>
                    <span className="text-cyan-300 font-bold">{(settings.handControl?.sensitivity ?? 1.6).toFixed(1)}x</span>
                  </div>
                  <input
                    type="range"
                    min="0.5"
                    max="3.0"
                    step="0.1"
                    value={settings.handControl?.sensitivity ?? 1.6}
                    onChange={(e) => updateHandControlSettings({ sensitivity: parseFloat(e.target.value) })}
                    className="w-full h-1 bg-slate-800 rounded appearance-none cursor-pointer accent-cyan-400"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-slate-400 mb-1">
                    <span>Smoothing</span>
                    <span className="text-cyan-300 font-bold">{(settings.handControl?.smoothing ?? 0.45).toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0.05"
                    max="0.95"
                    step="0.05"
                    value={settings.handControl?.smoothing ?? 0.45}
                    onChange={(e) => updateHandControlSettings({ smoothing: parseFloat(e.target.value) })}
                    className="w-full h-1 bg-slate-800 rounded appearance-none cursor-pointer accent-cyan-400"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-slate-400 mb-1">
                    <span>Pinch Threshold</span>
                    <span className="text-cyan-300 font-bold">{(settings.handControl?.pinchThreshold ?? 0.32).toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0.15"
                    max="0.55"
                    step="0.01"
                    value={settings.handControl?.pinchThreshold ?? 0.32}
                    onChange={(e) => updateHandControlSettings({ pinchThreshold: parseFloat(e.target.value) })}
                    className="w-full h-1 bg-slate-800 rounded appearance-none cursor-pointer accent-cyan-400"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center flex-1 text-center p-4 border border-dashed border-slate-800 rounded-lg">
              <span className="text-xs text-slate-500 mb-2 font-mono">Hand Gesture Control is disabled.</span>
              <span className="text-[10px] text-slate-600 font-mono">Toggle hand control above or use voice: "Jarvis, enable hand control"</span>
            </div>
          )}
        </div>

        {/* Panel 2: Active App & Scene Graph */}
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
              <span className="text-slate-400">Active App:</span>
              <div className="text-cyan-300 truncate">{frame?.active_app || 'None'}</div>
            </div>

            <div>
              <span className="text-slate-400">Control Nodes:</span>
              <div className="text-cyan-400 font-bold">{frame?.scene_graph?.total_elements || 0} Elements</div>
            </div>

            <div>
              <span className="text-slate-400">Focused Item:</span>
              <div className="text-slate-200 truncate">
                {frame?.scene_graph?.focused_element
                  ? `${frame.scene_graph.focused_element.name} (${frame.scene_graph.focused_element.control_type})`
                  : 'None'}
              </div>
            </div>
          </div>
        </div>

        {/* Panel 3: Proactive Guidance & Next Step */}
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

            <div className="p-2.5 rounded-lg bg-cyan-500/5 border border-cyan-500/20 text-xs">
              <div className="text-[10px] font-mono text-cyan-400 font-bold uppercase mb-1">Current Step</div>
              <div className="text-slate-200">{frame?.current_step || 'Observing active window context...'}</div>
            </div>

            {frame?.next_logical_step && (
              <div className="p-2.5 rounded-lg bg-cyan-500/10 border border-cyan-400/40 text-xs">
                <div className="text-[10px] font-mono text-cyan-300 font-bold uppercase mb-1 flex items-center gap-1">
                  <span>⚡ Predicted Next Action</span>
                </div>
                <div className="text-cyan-200 font-semibold">{frame.next_logical_step}</div>
              </div>
            )}
          </div>
        </div>

        {/* Panel 4: Quick Workspace Intelligence Actions */}
        <div className="col-span-1 bg-slate-900/60 rounded-lg border border-slate-800 p-3 flex flex-col gap-3">
          <div className="text-xs font-mono font-bold text-cyan-400 uppercase flex items-center gap-1.5 border-b border-slate-800 pb-2">
            <Layout className="w-3.5 h-3.5" />
            <span>Workspace Layout Presets</span>
          </div>

          <div className="flex flex-col gap-2">
            <button
              onClick={() => restoreWorkspace('coding')}
              className="w-full text-left p-2.5 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-cyan-500/30 transition-all text-xs font-mono flex items-center justify-between cursor-pointer"
            >
              <span className="text-slate-200">👨‍💻 Coding Layout</span>
              <span className="text-[10px] text-cyan-400">Restore</span>
            </button>

            <button
              onClick={() => restoreWorkspace('research')}
              className="w-full text-left p-2.5 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-cyan-500/30 transition-all text-xs font-mono flex items-center justify-between cursor-pointer"
            >
              <span className="text-slate-200">🔍 Research Layout</span>
              <span className="text-[10px] text-cyan-400">Restore</span>
            </button>

            <button
              onClick={() => restoreWorkspace('writer')}
              className="w-full text-left p-2.5 rounded-lg bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-cyan-500/30 transition-all text-xs font-mono flex items-center justify-between cursor-pointer"
            >
              <span className="text-slate-200">📝 Writer Layout</span>
              <span className="text-[10px] text-cyan-400">Restore</span>
            </button>
          </div>
        </div>

        {/* Panel 5: Background Topic Monitor Manager & Content Safety Guardrails */}
        <div className="col-span-1 md:col-span-3 bg-slate-900/60 rounded-lg border border-slate-800 p-3 flex flex-col gap-3">
          <div className="text-xs font-mono font-bold text-amber-400 uppercase flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
              <span>📡 Background Topic Monitor Manager</span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">Deduplicated & Content-Safe</span>
          </div>

          {topicStatusMsg && (
            <div className={`p-2 rounded text-xs font-mono border transition-all ${
              topicStatusMsg.includes('Alert') || topicStatusMsg.includes('blocked')
                ? 'bg-rose-950/60 border-rose-500/40 text-rose-300'
                : 'bg-cyan-950/60 border-cyan-500/40 text-cyan-300'
            }`}>
              {topicStatusMsg}
            </div>
          )}

          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newTopicInput}
              onChange={(e) => setNewTopicInput(e.target.value)}
              placeholder="e.g. Quantum Computing, AI Breakthroughs..."
              className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-100 placeholder-slate-500 outline-none focus:border-cyan-500/50"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleAddTopic(newTopicInput)
                }
              }}
            />
            <button
              onClick={() => handleAddTopic(newTopicInput)}
              className="px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 text-xs font-mono font-bold transition-all cursor-pointer"
            >
              + ADD TOPIC
            </button>
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            {monitoredTopics.map((topic, idx) => (
              <span
                key={idx}
                className="text-[11px] px-2.5 py-1 rounded-full bg-cyan-950/60 border border-cyan-500/40 text-cyan-300 font-mono flex items-center gap-2"
              >
                <span>● {topic}</span>
                <button
                  onClick={() => handleRemoveTopic(topic)}
                  className="text-cyan-400/60 hover:text-rose-400 font-bold transition-colors cursor-pointer"
                  title={`Remove ${topic}`}
                >
                  ✕
                </button>
              </span>
            ))}

            <span
              className="text-[11px] px-2.5 py-1 rounded-full bg-slate-950 border border-rose-500/30 text-rose-300/70 font-mono line-through flex items-center gap-1.5"
              title="Financial & crypto topics blocked by safety policy"
            >
              <span>✕ Crypto & Daytrading</span>
              <span className="text-[9px] text-rose-400/80">BLOCKED</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
