import React, { useState, useEffect } from 'react'
import { Shield, ShieldAlert, Cpu, Bot, Zap, Play, Square, AlertTriangle, CheckCircle2, RotateCcw } from 'lucide-react'
import { useWebSocket } from '../hooks/useWebSocket'

export interface SupervisorState {
  authority_state: 'IDLE' | 'PRIMARY_ACTIVE' | 'FAILOVER_PENDING' | 'HERMES_ACTIVE' | 'RECOVERY' | 'COMPLETED' | 'FAILED' | 'CANCELLED'
  active_agent: string
  handoff_count: number
  goal?: string
  current_step?: string
  failover_reason?: string
  summary?: string
}

export default function LiveModeFailoverHUD() {
  const { lastMessage, sendMessage } = useWebSocket()
  const [state, setState] = useState<SupervisorState>({
    authority_state: 'IDLE',
    active_agent: 'JARVIS Desktop (Primary)',
    handoff_count: 0
  })
  const [goalInput, setGoalInput] = useState('')
  const [isExecuting, setIsExecuting] = useState(false)
  const [notification, setNotification] = useState<string | null>(null)

  // Listen for real-time WebSocket telemetry updates
  useEffect(() => {
    if (lastMessage?.type === 'live_mode_supervisor_update') {
      const payload = lastMessage.data
      setState(prev => ({
        ...prev,
        authority_state: payload.authority_state || prev.authority_state,
        active_agent: payload.active_agent || prev.active_agent,
        current_step: payload.data?.description || payload.data?.current_step || prev.current_step,
        failover_reason: payload.data?.reason || prev.failover_reason,
        summary: payload.data?.summary || prev.summary
      }))

      if (payload.type === 'failover_triggered') {
        setNotification(`🚨 Failover: Hermes Desktop took over. Reason: ${payload.data?.reason || 'Primary step failed'}`)
      } else if (payload.type === 'emergency_stop') {
        setNotification('🛑 Manual override: AI agent control revoked.')
      } else if (payload.type === 'goal_completed' || payload.type === 'recovery_success') {
        setIsExecuting(false)
      }
    }
  }, [lastMessage])

  const handleStartTask = async () => {
    if (!goalInput.trim()) return
    setIsExecuting(true)
    setNotification(null)

    try {
      const res = await fetch('http://localhost:8000/api/v1/live_mode/supervisor/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal: goalInput.trim() })
      })
      const data = await res.json()
      if (data.status === 'success') {
        setNotification(`✓ Completed: ${data.summary}`)
      } else if (data.status === 'failed') {
        setNotification(`✗ Execution Failed: ${data.summary}`)
      }
    } catch (err) {
      setNotification(`Error: ${err}`)
    } finally {
      setIsExecuting(false)
    }
  }

  const handleEmergencyStop = async () => {
    try {
      await fetch('http://localhost:8000/api/v1/live_mode/supervisor/emergency_stop', { method: 'POST' })
      setNotification('🛑 Control lock revoked. Full manual control restored.')
    } catch (err) {
      console.error(err)
    }
  }

  const isHermesActive = state.authority_state === 'HERMES_ACTIVE' || state.active_agent.includes('Hermes')
  const isPrimaryActive = state.authority_state === 'PRIMARY_ACTIVE'

  return (
    <div className="bg-slate-900/80 border border-slate-700/60 backdrop-blur-md rounded-xl p-4 shadow-xl text-slate-100 mb-4 transition-all">
      {/* Header Bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isHermesActive ? 'bg-amber-400' : isPrimaryActive ? 'bg-cyan-400' : 'bg-emerald-400'}`} />
            <span className={`relative inline-flex rounded-full h-3 w-3 ${isHermesActive ? 'bg-amber-500' : isPrimaryActive ? 'bg-cyan-500' : 'bg-emerald-500'}`} />
          </span>
          <div>
            <h3 className="text-sm font-semibold tracking-wide uppercase flex items-center gap-1.5 text-cyan-400">
              <Shield className="w-4 h-4 text-cyan-400" />
              Live Mode Failover Supervisor
            </h3>
            <p className="text-xs text-slate-400">
              Primary: <strong className="text-cyan-300">JARVIS Desktop</strong> | Fallback: <strong className="text-amber-300">Hermes Desktop</strong>
            </p>
          </div>
        </div>

        {/* Emergency Stop / Take Control Button */}
        <button
          onClick={handleEmergencyStop}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 rounded-lg text-xs font-medium transition-all shadow-sm active:scale-95"
          title="Instantly stop all AI agents and take manual control"
        >
          <Square className="w-3.5 h-3.5 fill-rose-400" />
          Take Control (Emergency Stop)
        </button>
      </div>

      {/* Status Badges Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 mb-3 text-xs">
        <div className="bg-slate-800/60 p-2.5 rounded-lg border border-slate-700/50">
          <span className="text-slate-400 block mb-0.5">Active Agent Authority</span>
          <span className="font-medium flex items-center gap-1.5">
            {isHermesActive ? (
              <span className="text-amber-300 flex items-center gap-1">
                <Bot className="w-3.5 h-3.5 text-amber-400" /> Hermes Desktop (Fallback)
              </span>
            ) : isPrimaryActive ? (
              <span className="text-cyan-300 flex items-center gap-1">
                <Cpu className="w-3.5 h-3.5 text-cyan-400" /> JARVIS Desktop (Primary)
              </span>
            ) : (
              <span className="text-slate-300">Idle / Ready</span>
            )}
          </span>
        </div>

        <div className="bg-slate-800/60 p-2.5 rounded-lg border border-slate-700/50">
          <span className="text-slate-400 block mb-0.5">Authority State</span>
          <span className="font-mono font-semibold text-slate-200 uppercase">
            {state.authority_state}
          </span>
        </div>

        <div className="bg-slate-800/60 p-2.5 rounded-lg border border-slate-700/50">
          <span className="text-slate-400 block mb-0.5">Control Lock</span>
          <span className="font-semibold text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" /> Single-Agent Enforced
          </span>
        </div>
      </div>

      {/* Notification / Failover Banner */}
      {notification && (
        <div className={`p-2.5 mb-3 rounded-lg text-xs border flex items-center gap-2 ${notification.includes('Failover') ? 'bg-amber-950/40 border-amber-600/50 text-amber-200' : 'bg-cyan-950/40 border-cyan-700/50 text-cyan-200'}`}>
          <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
          <span>{notification}</span>
        </div>
      )}

      {/* Goal Input & Execute Trigger */}
      <div className="flex gap-2">
        <input
          type="text"
          value={goalInput}
          onChange={(e) => setGoalInput(e.target.value)}
          placeholder="e.g. Open Chrome, navigate to GitHub, open repository, and inspect issue..."
          disabled={isExecuting}
          className="flex-1 bg-slate-800/90 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
          onKeyDown={(e) => e.key === 'Enter' && handleStartTask()}
        />
        <button
          onClick={handleStartTask}
          disabled={isExecuting || !goalInput.trim()}
          className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all shadow-md active:scale-95"
        >
          {isExecuting ? (
            <>
              <RotateCcw className="w-3.5 h-3.5 animate-spin" />
              Executing...
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              Run Goal
            </>
          )}
        </button>
      </div>
    </div>
  )
}
