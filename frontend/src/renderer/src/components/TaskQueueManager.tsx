import React, { useState, useEffect, useCallback } from 'react'
import {
  Play,
  Pause,
  XCircle,
  Clock,
  CheckCircle2,
  AlertCircle,
  Plus,
  ChevronUp,
  ChevronDown,
  Activity,
  Layers,
  RefreshCw,
  RotateCcw
} from 'lucide-react'

export interface QueuedTaskItem {
  id: string
  title: string
  command: string
  priority: number
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
  progress: number
  logs?: string[]
  result?: string
  error?: string
  peak_memory_mb?: number
  cpu_time_seconds?: number
  created_at?: number
  updated_at?: number
}

interface TaskQueueManagerProps {
  tasks?: QueuedTaskItem[]
  onReorder?: (order: string[]) => void
  onPause?: (id: string) => void
  onResume?: (id: string) => void
  onCancel?: (id: string) => void
  onAddTask?: (title: string, command: string) => void
}

const DEFAULT_TASKS: QueuedTaskItem[] = [
  {
    id: 't-1',
    title: 'System Diagnostics & Telemetry',
    command: 'Check system status and hardware gauges',
    priority: 2,
    status: 'completed',
    progress: 1.0,
    result: 'Hardware nominal: CPU 34%, RAM 41%',
    logs: ['Diagnostics started', 'Metrics aggregated', 'Nominal']
  },
  {
    id: 't-2',
    title: 'Local Knowledge Base Indexing',
    command: 'Index project codebase & ChromaDB vector embeddings',
    priority: 1,
    status: 'running',
    progress: 0.68,
    logs: ['Scanning project tree...', 'Vectorizing chunks in ChromaDB...']
  },
  {
    id: 't-3',
    title: 'Automated Repository Backup',
    command: 'Generate local ZIP archive of development workspace',
    priority: 1,
    status: 'pending',
    progress: 0.0,
    logs: ['Queued for background worker']
  }
]

function getBackendUrl(): string {
  const host = typeof window !== 'undefined' && window.location && window.location.hostname ? window.location.hostname : '127.0.0.1'
  return `http://${host}:8000`
}

export default function TaskQueueManager({
  tasks = DEFAULT_TASKS,
  onReorder,
  onPause,
  onResume,
  onCancel,
  onAddTask
}: TaskQueueManagerProps) {
  const [items, setItems] = useState<QueuedTaskItem[]>(tasks)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isRecovering, setIsRecovering] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newCommand, setNewCommand] = useState('')

  // ── Fetch Authoritative Tasks from SQLite Backend ───────────────────────────
  const fetchTasks = useCallback(async (isSilent = false) => {
    if (!isSilent) setIsRefreshing(true)
    try {
      const res = await fetch(`${getBackendUrl()}/api/v1/tasks`)
      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`)
      }
      const data = await res.json()
      if (data.status === 'success' && Array.isArray(data.tasks)) {
        setItems(data.tasks)
        setErrorMsg(null)
      }
    } catch (err: any) {
      console.warn('[TaskQueueManager] Failed to load persisted tasks from backend:', err)
      if (items.length === 0) {
        setItems(tasks)
      }
      setErrorMsg('Offline mode: Using cached task snapshot')
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }, [items.length, tasks])

  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  // ── WebSocket Task Update Listener ──────────────────────────────────────────
  useEffect(() => {
    const handleTaskEvent = (e: CustomEvent) => {
      const payload = e.detail
      if (!payload || !payload.task) return
      const updatedTask: QueuedTaskItem = payload.task

      setItems(prev => {
        const existingIdx = prev.findIndex(t => t.id === updatedTask.id)
        if (existingIdx >= 0) {
          const next = [...prev]
          next[existingIdx] = { ...next[existingIdx], ...updatedTask }
          return next
        }
        return [updatedTask, ...prev]
      })
    }

    window.addEventListener('jarvis:task_update' as any, handleTaskEvent as any)
    return () => {
      window.removeEventListener('jarvis:task_update' as any, handleTaskEvent as any)
    }
  }, [])

  // ── Reorder Tasks ───────────────────────────────────────────────────────────
  const handleMove = async (index: number, direction: 'up' | 'down') => {
    const targetIdx = direction === 'up' ? index - 1 : index + 1
    if (targetIdx < 0 || targetIdx >= items.length) return
    const updated = [...items]
    const temp = updated[index]
    updated[index] = updated[targetIdx]
    updated[targetIdx] = temp
    setItems(updated)
    onReorder?.(updated.map(t => t.id))

    try {
      await fetch(`${getBackendUrl()}/api/v1/tasks/reorder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: updated.map(t => t.id) })
      })
    } catch (err) {
      console.warn('[TaskQueueManager] Failed to persist task reorder:', err)
    }
  }

  // ── Toggle Pause / Resume ───────────────────────────────────────────────────
  const handleTogglePause = async (task: QueuedTaskItem) => {
    const isPaused = task.status === 'paused'
    const endpoint = isPaused ? 'resume' : 'pause'
    const newStatus = isPaused ? 'pending' : 'paused'

    // Optimistic UI update
    setItems(prev => prev.map(t => (t.id === task.id ? { ...t, status: newStatus as any } : t)))
    if (isPaused) {
      onResume?.(task.id)
    } else {
      onPause?.(task.id)
    }

    try {
      const res = await fetch(`${getBackendUrl()}/api/v1/tasks/${task.id}/${endpoint}`, {
        method: 'POST'
      })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      const data = await res.json()
      if (data.task) {
        setItems(prev => prev.map(t => (t.id === task.id ? { ...t, ...data.task } : t)))
      }
    } catch (err) {
      console.error(`[TaskQueueManager] Failed to ${endpoint} task:`, err)
      fetchTasks(true)
    }
  }

  // ── Cancel Task ─────────────────────────────────────────────────────────────
  const handleCancelTask = async (id: string) => {
    // Optimistic UI update
    setItems(prev => prev.map(t => (t.id === id ? { ...t, status: 'cancelled' } : t)))
    onCancel?.(id)

    try {
      await fetch(`${getBackendUrl()}/api/v1/tasks/${id}`, {
        method: 'DELETE'
      })
    } catch (err) {
      console.error('[TaskQueueManager] Failed to cancel task:', err)
      fetchTasks(true)
    }
  }

  // ── Add Task ────────────────────────────────────────────────────────────────
  const handleAdd = async () => {
    if (!newTitle.trim()) return
    const titleVal = newTitle.trim()
    const commandVal = newCommand.trim() || titleVal

    setNewTitle('')
    setNewCommand('')
    setShowAdd(false)

    try {
      const res = await fetch(`${getBackendUrl()}/api/v1/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: titleVal,
          command: commandVal,
          priority: 1
        })
      })
      if (res.ok) {
        const data = await res.json()
        if (data.task) {
          setItems(prev => [data.task, ...prev])
          onAddTask?.(data.task.title, data.task.command)
          return
        }
      }
    } catch (err) {
      console.warn('[TaskQueueManager] Backend create task unavailable, using local ID:', err)
    }

    // Local fallback if backend is unavailable
    const newTask: QueuedTaskItem = {
      id: `t-${Date.now().toString(36)}`,
      title: titleVal,
      command: commandVal,
      priority: 1,
      status: 'pending',
      progress: 0.0,
      logs: ['Task added by user']
    }
    setItems(prev => [newTask, ...prev])
    onAddTask?.(newTask.title, newTask.command)
  }

  // ── Self-Recovery Trigger ───────────────────────────────────────────────────
  const handleRecoverInterrupted = async () => {
    setIsRecovering(true)
    try {
      const res = await fetch(`${getBackendUrl()}/api/v1/developer/recover_interrupted_goals`, {
        method: 'POST'
      })
      if (res.ok) {
        await fetchTasks(true)
      }
    } catch (err) {
      console.error('[TaskQueueManager] Recovery error:', err)
    } finally {
      setIsRecovering(false)
    }
  }

  return (
    <div className="flex flex-col h-full w-full bg-slate-950/40 backdrop-blur-2xl rounded-2xl border border-blue-500/20 overflow-hidden shadow-[0_8px_32px_0_rgba(0,0,0,0.37)]">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 bg-slate-950/30 border-b border-white/5">
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#00e5ff] animate-pulse" />
          <div>
            <div className="text-xs font-bold text-slate-200 tracking-[0.2em] uppercase font-mono">
              Task Queue & Scheduler
            </div>
            <div className="text-[10px] font-mono text-slate-400">
              Persistent SQLite Storage & Live Multitasking
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Recovery Button */}
          <button
            onClick={handleRecoverInterrupted}
            disabled={isRecovering}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-[10px] font-mono text-indigo-300 transition-all cursor-pointer"
            title="Scan SQLite WAL checkpoints and self-recover any interrupted goals"
          >
            <RotateCcw className={`w-3 h-3 ${isRecovering ? 'animate-spin' : ''}`} />
            <span>{isRecovering ? 'Recovering...' : 'Self-Recover'}</span>
          </button>

          {/* Refresh Button */}
          <button
            onClick={() => fetchTasks()}
            disabled={isRefreshing}
            className="p-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-800 text-slate-400 hover:text-cyan-400 border border-white/5 transition-all cursor-pointer"
            title="Refresh Tasks"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
          </button>

          {/* Add Task Button */}
          <button
            onClick={() => setShowAdd(!showAdd)}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-xs font-mono text-cyan-300 transition-all cursor-pointer shadow-[0_0_10px_rgba(0,229,255,0.15)]"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Task</span>
          </button>
        </div>
      </div>

      {/* Optional Error/Offline Notice */}
      {errorMsg && (
        <div className="px-5 py-1.5 bg-amber-500/10 border-b border-amber-500/20 text-[11px] font-mono text-amber-300 flex items-center justify-between">
          <span>⚠️ {errorMsg}</span>
          <button onClick={() => fetchTasks()} className="underline hover:text-amber-200 cursor-pointer">
            Retry Sync
          </button>
        </div>
      )}

      {/* Add Task Form Popdown */}
      {showAdd && (
        <div className="p-4 bg-slate-900/50 border-b border-white/5 space-y-3 transition-all animate-fadeIn">
          <div>
            <label className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
              Task Title
            </label>
            <input
              type="text"
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              placeholder="e.g. Clean Temporary System Logs"
              className="w-full bg-slate-950/80 border border-cyan-500/30 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-400"
            />
          </div>
          <div>
            <label className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
              Instruction / Command (Optional)
            </label>
            <input
              type="text"
              value={newCommand}
              onChange={e => setNewCommand(e.target.value)}
              placeholder="e.g. Execute safe temp file pruning in AppData"
              className="w-full bg-slate-950/80 border border-cyan-500/30 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-400"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={() => setShowAdd(false)}
              className="px-3 py-1 rounded-lg bg-slate-800 text-xs font-mono text-slate-400 hover:text-slate-200 cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={handleAdd}
              disabled={!newTitle.trim()}
              className="px-3 py-1 rounded-lg bg-cyan-500/30 hover:bg-cyan-500/40 border border-cyan-500/50 text-xs font-mono text-cyan-200 disabled:opacity-40 cursor-pointer"
            >
              Enqueue Task
            </button>
          </div>
        </div>
      )}

      {/* Task List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
        {isLoading && items.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-slate-400 font-mono text-xs gap-3">
            <RefreshCw className="w-5 h-5 animate-spin text-cyan-400" />
            <span>Loading persistent task queue...</span>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-slate-500 font-mono text-xs gap-2">
            <Layers className="w-8 h-8 opacity-40" />
            <span>No tasks currently queued.</span>
          </div>
        ) : (
          items.map((task, idx) => {
            const isRunning = task.status === 'running'
            const isPaused = task.status === 'paused'
            const isCompleted = task.status === 'completed'
            const isCancelled = task.status === 'cancelled'
            const isFailed = task.status === 'failed'

            return (
              <div
                key={task.id}
                className={`p-3.5 rounded-xl border transition-all duration-300 space-y-2.5 ${
                  isRunning
                    ? 'bg-cyan-950/20 border-cyan-500/40 shadow-[0_0_15px_rgba(0,229,255,0.08)]'
                    : isPaused
                    ? 'bg-amber-950/10 border-amber-500/30'
                    : isCompleted
                    ? 'bg-slate-900/30 border-white/5 opacity-80'
                    : isCancelled || isFailed
                    ? 'bg-rose-950/10 border-rose-500/20 opacity-70'
                    : 'bg-slate-900/40 border-white/5'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    {/* Status Badge */}
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono tracking-wider uppercase border ${
                        isRunning
                          ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 animate-pulse'
                          : isPaused
                          ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                          : isCompleted
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                          : isCancelled
                          ? 'bg-slate-500/20 text-slate-400 border-slate-500/30'
                          : isFailed
                          ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                          : 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                      }`}
                    >
                      {isRunning && <Activity className="w-2.5 h-2.5 animate-spin" />}
                      {isPaused && <Clock className="w-2.5 h-2.5" />}
                      {isCompleted && <CheckCircle2 className="w-2.5 h-2.5" />}
                      {isFailed && <AlertCircle className="w-2.5 h-2.5" />}
                      {task.status}
                    </span>

                    <span className="text-xs font-bold text-slate-200 truncate font-mono">
                      {task.title}
                    </span>
                  </div>

                  {/* Action Controls */}
                  <div className="flex items-center gap-1">
                    {/* Move Up / Down */}
                    <button
                      onClick={() => handleMove(idx, 'up')}
                      disabled={idx === 0}
                      className="p-1 rounded bg-slate-900/60 hover:bg-slate-800 disabled:opacity-20 text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
                      title="Move Up"
                    >
                      <ChevronUp className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => handleMove(idx, 'down')}
                      disabled={idx === items.length - 1}
                      className="p-1 rounded bg-slate-900/60 hover:bg-slate-800 disabled:opacity-20 text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
                      title="Move Down"
                    >
                      <ChevronDown className="w-3 h-3" />
                    </button>

                    {/* Pause / Resume */}
                    {!isCompleted && !isCancelled && !isFailed && (
                      <button
                        onClick={() => handleTogglePause(task)}
                        className={`p-1.5 rounded-lg border transition-all cursor-pointer ${
                          isPaused
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/40 hover:bg-amber-500/30'
                        }`}
                        title={isPaused ? 'Resume Task' : 'Pause Task'}
                      >
                        {isPaused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
                      </button>
                    )}

                    {/* Cancel */}
                    {!isCompleted && !isCancelled && (
                      <button
                        onClick={() => handleCancelTask(task.id)}
                        className="p-1.5 rounded-lg bg-slate-900/60 hover:bg-slate-800 text-slate-300 hover:text-rose-400 border border-white/5 transition-all cursor-pointer"
                        title="Cancel Task"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-slate-950/80 rounded-full h-1.5 overflow-hidden border border-white/5">
                  <div
                    className={`h-full transition-all duration-500 ${
                      isRunning
                        ? 'bg-gradient-to-r from-cyan-400 to-blue-500 shadow-[0_0_8px_#00e5ff]'
                        : isCompleted
                        ? 'bg-emerald-400'
                        : isPaused
                        ? 'bg-amber-400'
                        : isFailed
                        ? 'bg-rose-500'
                        : 'bg-blue-400'
                    }`}
                    style={{ width: `${Math.round(task.progress * 100)}%` }}
                  />
                </div>

                {/* Instruction / Command */}
                {task.command && (
                  <div className="text-[11px] font-mono text-slate-400 truncate">
                    {task.command}
                  </div>
                )}

                {/* Result or Error */}
                {task.result && (
                  <div className="text-[10px] font-mono text-emerald-300 bg-emerald-950/20 p-2 rounded-lg border border-emerald-500/20">
                    {task.result}
                  </div>
                )}
                {task.error && (
                  <div className="text-[10px] font-mono text-rose-300 bg-rose-950/20 p-2 rounded-lg border border-rose-500/20">
                    Error: {task.error}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
