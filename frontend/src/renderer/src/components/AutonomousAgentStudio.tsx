import React, { useState, useEffect } from 'react'
import {
  Bot,
  Cpu,
  Shield,
  Search,
  Code2,
  Play,
  Pause,
  RotateCcw,
  Zap,
  Radio,
  CheckCircle2,
  AlertCircle,
  PlusCircle,
  Database
} from 'lucide-react'
import { useAppStore } from '../stores/appStore'

export const AutonomousAgentStudio: React.FC = () => {
  const activeSubAgents = useAppStore((s) => s.activeSubAgents)
  const ipcMessages = useAppStore((s) => s.ipcMessages)
  const goalQueue = useAppStore((s) => s.goalQueue)
  const kvCacheMetrics = useAppStore((s) => s.kvCacheMetrics)

  const setActiveSubAgents = useAppStore((s) => s.setActiveSubAgents)
  const setGoalQueue = useAppStore((s) => s.setGoalQueue)
  const setKVCacheMetrics = useAppStore((s) => s.setKVCacheMetrics)

  const [spawnRole, setSpawnRole] = useState<'CodeAgent' | 'ResearchAgent' | 'SecurityAgent'>('CodeAgent')
  const [spawnGoal, setSpawnGoal] = useState('')
  const [isSpawning, setIsSpawning] = useState(false)
  const [activeTab, setActiveTab] = useState<'agents' | 'ipc' | 'goals' | 'kv'>('agents')

  // Fetch initial telemetry data
  useEffect(() => {
    fetchActiveAgents()
    fetchGoalQueue()
    fetchKVCacheMetrics()
    const interval = setInterval(() => {
      fetchActiveAgents()
      fetchGoalQueue()
      fetchKVCacheMetrics()
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  const fetchActiveAgents = async () => {
    try {
      const res = await fetch('/api/v1/agents/active')
      const data = await res.json()
      if (data.status === 'success' && data.agents) {
        setActiveSubAgents(data.agents)
      }
    } catch (e) {
      console.warn('Failed to fetch active agents:', e)
    }
  }

  const fetchGoalQueue = async () => {
    try {
      const res = await fetch('/api/v1/agents/goals')
      const data = await res.json()
      if (data.status === 'success' && data.goals) {
        setGoalQueue(data.goals)
      }
    } catch (e) {
      console.warn('Failed to fetch goal queue:', e)
    }
  }

  const fetchKVCacheMetrics = async () => {
    try {
      const res = await fetch('/api/v1/agents/kv_cache')
      const data = await res.json()
      if (data.status === 'success' && data.metrics) {
        setKVCacheMetrics(data.metrics)
      }
    } catch (e) {
      console.warn('Failed to fetch KV cache metrics:', e)
    }
  }

  const handleSpawnAgent = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!spawnGoal.trim()) return

    setIsSpawning(true)
    try {
      await fetch('/api/v1/agents/spawn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: spawnRole, task_goal: spawnGoal })
      })
      setSpawnGoal('')
      await fetchActiveAgents()
    } catch (err) {
      console.error('Spawn sub-agent error:', err)
    } finally {
      setIsSpawning(false)
    }
  }

  const handleCreateGoal = async () => {
    const title = prompt('Enter Long-Horizon Goal Title:')
    if (!title) return
    try {
      await fetch('/api/v1/agents/goals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description: 'Multi-day persistent task', total_steps: 5 })
      })
      await fetchGoalQueue()
    } catch (e) {
      console.error('Create goal error:', e)
    }
  }

  const handleGoalStatusToggle = async (goalId: string, currentStatus: string) => {
    const nextStatus = currentStatus === 'paused' ? 'running' : 'paused'
    try {
      await fetch('/api/v1/agents/goals/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal_id: goalId, status: nextStatus })
      })
      await fetchGoalQueue()
    } catch (e) {
      console.error('Goal status update error:', e)
    }
  }

  const getRoleIcon = (role: string) => {
    if (role === 'CodeAgent') return <Code2 className="w-4 h-4 text-cyan-400" />
    if (role === 'ResearchAgent') return <Search className="w-4 h-4 text-blue-400" />
    if (role === 'SecurityAgent') return <Shield className="w-4 h-4 text-amber-400" />
    return <Bot className="w-4 h-4 text-purple-400" />
  }

  return (
    <div className="w-full h-full flex flex-col bg-slate-950/90 text-slate-100 font-sans p-4 overflow-y-auto">
      {/* ── Studio Header & Navigation ────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-cyan-500/30 pb-3 mb-4">
        <div className="flex items-center gap-2.5">
          <Cpu className="w-5 h-5 text-cyan-400 animate-pulse" />
          <h2 className="text-sm md:text-base font-mono font-bold text-cyan-200 tracking-wider">
            AUTONOMOUS AGENT ECOSYSTEM
          </h2>
        </div>

        {/* Tab Buttons */}
        <div className="flex items-center gap-1.5 bg-slate-900/80 p-1 rounded-lg border border-slate-800 text-[11px] font-mono">
          <button
            type="button"
            onClick={() => setActiveTab('agents')}
            className={`px-3 py-1 rounded transition-all cursor-pointer ${
              activeTab === 'agents'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(0,229,255,0.3)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            SUB-AGENTS ({activeSubAgents.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('ipc')}
            className={`px-3 py-1 rounded transition-all cursor-pointer ${
              activeTab === 'ipc'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(0,229,255,0.3)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            IPC BUS ({ipcMessages.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('goals')}
            className={`px-3 py-1 rounded transition-all cursor-pointer ${
              activeTab === 'goals'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(0,229,255,0.3)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            GOAL QUEUE ({goalQueue.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('kv')}
            className={`px-3 py-1 rounded transition-all cursor-pointer ${
              activeTab === 'kv'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(0,229,255,0.3)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            KV-CACHE PRUNER
          </button>
        </div>
      </div>

      {/* ── TAB 1: Sub-Agent Hierarchy & Spawning ─────────────────────────── */}
      {activeTab === 'agents' && (
        <div className="flex flex-col gap-4">
          {/* Sub-Agent Spawn Form */}
          <form
            onSubmit={handleSpawnAgent}
            className="flex flex-wrap items-center gap-3 p-3 bg-slate-900/60 border border-cyan-500/20 rounded-xl backdrop-blur-md"
          >
            <div className="flex items-center gap-2 text-xs font-mono text-cyan-300">
              <PlusCircle className="w-4 h-4 text-cyan-400" />
              <span>SPAWN SUB-AGENT:</span>
            </div>

            <select
              value={spawnRole}
              onChange={(e) => setSpawnRole(e.target.value as any)}
              className="bg-slate-950 text-slate-200 border border-slate-700 text-xs font-mono rounded px-2.5 py-1.5 focus:border-cyan-400 outline-none"
            >
              <option value="CodeAgent">CodeAgent (AST & Refactor)</option>
              <option value="ResearchAgent">ResearchAgent (RAG & Web)</option>
              <option value="SecurityAgent">SecurityAgent (Sandbox Audit)</option>
            </select>

            <input
              type="text"
              placeholder="Task goal (e.g. Audit security sandbox & build user dashboard)"
              value={spawnGoal}
              onChange={(e) => setSpawnGoal(e.target.value)}
              className="flex-1 bg-slate-950 text-slate-100 border border-slate-700 text-xs rounded px-3 py-1.5 focus:border-cyan-400 outline-none min-w-[200px]"
            />

            <button
              type="submit"
              disabled={isSpawning || !spawnGoal.trim()}
              className="px-4 py-1.5 bg-cyan-500/20 border border-cyan-400 text-cyan-200 hover:bg-cyan-500/30 text-xs font-mono font-bold rounded transition-all disabled:opacity-50 cursor-pointer shadow-[0_0_10px_rgba(0,229,255,0.2)]"
            >
              {isSpawning ? 'SPAWNING...' : 'LAUNCH THREAD'}
            </button>
          </form>

          {/* Active Sub-Agent Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {activeSubAgents.map((ag) => (
              <div
                key={ag.agent_id}
                className="p-3.5 bg-slate-900/80 border border-slate-800 hover:border-cyan-500/40 rounded-xl transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {getRoleIcon(ag.role)}
                      <span className="font-mono text-xs font-bold text-slate-200">{ag.role}</span>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold ${
                        ag.status === 'completed'
                          ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                          : ag.status === 'running'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {ag.status}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 line-clamp-2 mb-2 font-mono">{ag.task_goal}</p>

                  <div className="text-[11px] font-mono text-slate-400 mb-2">
                    Step: <span className="text-cyan-300">{ag.current_step}</span>
                  </div>
                </div>

                {/* Progress Bar */}
                <div>
                  <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden mb-1">
                    <div
                      className="h-full bg-cyan-400 transition-all duration-300"
                      style={{ width: `${Math.round((ag.progress || 0) * 100)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                    <span>Tokens: {ag.tokens_used || 0}</span>
                    <span>{Math.round((ag.progress || 0) * 100)}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── TAB 2: IPC Message Bus Stream ─────────────────────────────────── */}
      {activeTab === 'ipc' && (
        <div className="flex flex-col gap-2 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-300 mb-1">
            <Radio className="w-4 h-4 text-cyan-400 animate-pulse" />
            <span>REAL-TIME AGENT-TO-AGENT IPC STREAM</span>
          </div>

          <div className="flex flex-col gap-1.5 max-h-[400px] overflow-y-auto pr-1">
            {ipcMessages.length === 0 ? (
              <span className="text-xs font-mono text-slate-500 italic p-4 text-center">
                No IPC messages recorded yet. Spawn sub-agents to observe inter-process bus communication.
              </span>
            ) : (
              ipcMessages.map((m) => (
                <div
                  key={m.id}
                  className="p-2.5 bg-slate-950/80 border border-slate-800/80 rounded-lg flex items-start justify-between gap-3 text-xs font-mono"
                >
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-cyan-400 font-bold">{m.sender}</span>
                      <span className="text-slate-500">➔</span>
                      <span className="text-blue-400 font-bold">{m.recipient}</span>
                      <span className="px-1.5 py-0.2 rounded text-[9px] bg-slate-800 text-slate-300 uppercase">
                        {m.message_type}
                      </span>
                    </div>
                    <span className="text-slate-300">{m.content}</span>
                  </div>
                  <span className="text-[10px] text-slate-500 whitespace-nowrap">{m.formatted_time}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ── TAB 3: Long-Horizon Goal Queue ────────────────────────────────── */}
      {activeTab === 'goals' && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-cyan-300">PERSISTENT MULTI-DAY GOAL QUEUE (SQLITE WAL)</span>
            <button
              type="button"
              onClick={handleCreateGoal}
              className="px-3 py-1 bg-cyan-500/20 border border-cyan-400 text-cyan-200 text-xs font-mono rounded hover:bg-cyan-500/30 transition-all cursor-pointer"
            >
              + NEW LONG-HORIZON GOAL
            </button>
          </div>

          <div className="flex flex-col gap-2.5">
            {goalQueue.map((g) => (
              <div
                key={g.goal_id}
                className="p-3.5 bg-slate-900/80 border border-slate-800 rounded-xl flex items-center justify-between gap-4"
              >
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-cyan-400" />
                    <span className="font-mono text-sm font-bold text-slate-100">{g.title}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase ${
                        g.status === 'running'
                          ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                          : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      }`}
                    >
                      {g.status}
                    </span>
                  </div>
                  <span className="text-xs text-slate-400">{g.description || 'Persistent agent goal checkpointing'}</span>
                </div>

                <div className="flex items-center gap-3 font-mono text-xs">
                  <span className="text-slate-400">
                    Step <strong className="text-cyan-300">{g.current_step_index}</strong> / {g.total_steps}
                  </span>

                  <button
                    type="button"
                    onClick={() => handleGoalStatusToggle(g.goal_id, g.status)}
                    className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 cursor-pointer"
                    title={g.status === 'paused' ? 'Resume Goal' : 'Pause Goal'}
                  >
                    {g.status === 'paused' ? <Play className="w-3.5 h-3.5 text-cyan-400" /> : <Pause className="w-3.5 h-3.5 text-amber-400" />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── TAB 4: KV-Cache Pruner Metrics ────────────────────────────────── */}
      {activeTab === 'kv' && (
        <div className="flex flex-col gap-4 p-4 bg-slate-900/60 rounded-xl border border-slate-800 font-mono">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-cyan-300">
              <Zap className="w-4 h-4 text-cyan-400" />
              <span>CONTEXT WINDOW KV-CACHE COMPRESSION METRICS</span>
            </div>
            <button
              type="button"
              onClick={fetchKVCacheMetrics}
              className="px-3 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs rounded transition-all cursor-pointer"
            >
              REFRESH METRICS
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center">
            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
              <div className="text-[10px] text-slate-500 mb-1">MAX TOKEN BUDGET</div>
              <div className="text-lg font-bold text-slate-200">{kvCacheMetrics?.max_context_tokens || 8192}</div>
            </div>
            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
              <div className="text-[10px] text-slate-500 mb-1">RAW PROCESSED</div>
              <div className="text-lg font-bold text-slate-200">{kvCacheMetrics?.raw_tokens_processed || 0}</div>
            </div>
            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
              <div className="text-[10px] text-slate-500 mb-1">PRUNED SAVINGS</div>
              <div className="text-lg font-bold text-cyan-400">+{kvCacheMetrics?.pruned_tokens_saved || 0}</div>
            </div>
            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
              <div className="text-[10px] text-slate-500 mb-1">SAVINGS %</div>
              <div className="text-lg font-bold text-amber-400">{kvCacheMetrics?.savings_percent || 0}%</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
