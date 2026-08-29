import React, { useState } from 'react'
import {
  ListOrdered,
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
  Layers
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
  peak_memory_mb?: number
  cpu_time_seconds?: number
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

export default function TaskQueueManager({
  tasks = DEFAULT_TASKS,
  onReorder,
  onPause,
  onResume,
  onCancel,
  onAddTask
}: TaskQueueManagerProps) {
  const [items, setItems] = useState<QueuedTaskItem[]>(tasks)
  const [showAdd, setShowAdd] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newCommand, setNewCommand] = useState('')

  const handleMove = (index: number, direction: 'up' | 'down') => {
    const targetIdx = direction === 'up' ? index - 1 : index + 1
    if (targetIdx < 0 || targetIdx >= items.length) return
    const updated = [...items]
    const temp = updated[index]
    updated[index] = updated[targetIdx]
    updated[targetIdx] = temp
    setItems(updated)
    onReorder?.(updated.map(t => t.id))
  }

  const handleTogglePause = (task: QueuedTaskItem) => {
    if (task.status === 'running' || task.status === 'pending') {
      setItems(prev => prev.map(t => (t.id === task.id ? { ...t, status: 'paused' } : t)))
      onPause?.(task.id)
    } else if (task.status === 'paused') {
      setItems(prev => prev.map(t => (t.id === task.id ? { ...t, status: 'pending' } : t)))
      onResume?.(task.id)
    }
  }

  const handleCancelTask = (id: string) => {
    setItems(prev => prev.map(t => (t.id === id ? { ...t, status: 'cancelled' } : t)))
    onCancel?.(id)
  }

  const handleAdd = () => {
    if (!newTitle.trim()) return
    const newTask: QueuedTaskItem = {
      id: `t-${Date.now().toString(36)}`,
      title: newTitle.trim(),
      command: newCommand.trim() || newTitle.trim(),
      priority: 1,
      status: 'pending',
      progress: 0.0,
      logs: ['Task added by user']
    }
    setItems(prev => [newTask, ...prev])
    onAddTask?.(newTask.title, newTask.command)
    setNewTitle('')
    setNewCommand('')
    setShowAdd(false)
  }

  return (
    <div className="flex flex-col h-full w-full bg-slate-950/90 rounded-xl border border-cyan-500/20 overflow-hidden shadow-2xl backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/80 border-b border-cyan-500/20">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <ListOrdered className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-100 uppercase tracking-wider">Task Queue & Scheduler</div>
            <div className="text-[10px] font-mono text-slate-400">Multi-Task Execution & Priority Reordering</div>
          </div>
        </div>

        <button
          onClick={() => setShowAdd(prev => !prev)}
          className="flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-xs font-mono transition-all cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Task</span>
        </button>
      </div>

      {/* Sub-Agent Quota & Long-Horizon Checkpoint Status Bar */}
      <div className="px-4 py-2 bg-slate-950/90 border-b border-cyan-500/10 flex items-center justify-between text-[10px] font-mono text-slate-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block animate-pulse" />
            <span>Sandbox Quota: <strong className="text-slate-200">512 MB RSS</strong> | <strong className="text-slate-200">30s CPU</strong></span>
          </span>
          <span className="text-slate-700">|</span>
          <span className="flex items-center gap-1">
            <span>Recovery Interlock: <strong className="text-cyan-300">Active Checkpoint</strong></span>
          </span>
        </div>
        <button
          onClick={async () => {
            try {
              const res = await fetch('http://127.0.0.1:8000/api/v1/developer/recover_interrupted_goals', { method: 'POST' });
              if (res.ok) {
                alert('✓ Scanned and recovered interrupted goal checkpoints.');
              }
            } catch (e) {
              console.log('Recovery trigger notice:', e);
            }
          }}
          className="px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-900/50 transition cursor-pointer"
        >
          Scan & Resume Goals
        </button>
      </div>

      {/* Add Task Drawer */}

      {showAdd && (
        <div className="p-3 bg-slate-900 border-b border-slate-800 flex flex-col gap-2">
          <input
            type="text"
            placeholder="Task Title (e.g. Daily Briefing)"
            value={newTitle}
            onChange={e => setNewTitle(e.target.value)}
            className="px-2.5 py-1.5 rounded text-xs bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-400"
          />
          <input
            type="text"
            placeholder="Instruction Command (e.g. Summarize news and open Chrome)"
            value={newCommand}
            onChange={e => setNewCommand(e.target.value)}
            className="px-2.5 py-1.5 rounded text-xs bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-400"
          />
          <div className="flex justify-end gap-2 mt-1">
            <button onClick={() => setShowAdd(false)} className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200">
              Cancel
            </button>
            <button onClick={handleAdd} className="px-3 py-1 rounded text-xs font-bold bg-cyan-500 text-slate-950 hover:bg-cyan-400">
              Queue Task
            </button>
          </div>
        </div>
      )}

      {/* Task Queue List */}
      <div className="flex-1 p-3 overflow-y-auto space-y-2.5 custom-scrollbar">
        {items.map((task, idx) => {
          const isRunning = task.status === 'running'
          const isCompleted = task.status === 'completed'
          const isPaused = task.status === 'paused'
          const isCancelled = task.status === 'cancelled'

          return (
            <div
              key={task.id}
              className={`p-3 rounded-lg border backdrop-blur-md transition-all flex flex-col gap-2 ${
                isRunning
                  ? 'bg-cyan-950/40 border-cyan-500/60 shadow-[0_0_15px_rgba(0,229,255,0.15)]'
                  : isCompleted
                  ? 'bg-slate-900/40 border-emerald-500/30'
                  : isPaused
                  ? 'bg-amber-950/20 border-amber-500/30'
                  : isCancelled
                  ? 'bg-slate-900/20 border-slate-800 opacity-60'
                  : 'bg-slate-900/60 border-slate-800'
              }`}
            >
              {/* Task Row Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="flex flex-col gap-0.5 select-none">
                    <button
                      onClick={() => handleMove(idx, 'up')}
                      disabled={idx === 0}
                      className="text-slate-500 hover:text-cyan-400 disabled:opacity-20 cursor-pointer"
                    >
                      <ChevronUp className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleMove(idx, 'down')}
                      disabled={idx === items.length - 1}
                      className="text-slate-500 hover:text-cyan-400 disabled:opacity-20 cursor-pointer"
                    >
                      <ChevronDown className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-100">{task.title}</span>
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.2 rounded font-bold uppercase ${
                          isRunning
                            ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 animate-pulse'
                            : isCompleted
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : isPaused
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                            : isCancelled
                            ? 'bg-slate-800 text-slate-400'
                            : 'bg-slate-800 text-slate-300'
                        }`}
                      >
                        {task.status}
                      </span>
                    </div>
                    <div className="text-[10px] font-mono text-slate-400 mt-0.5">{task.command}</div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1.5">
                  {!isCompleted && !isCancelled && (
                    <button
                      onClick={() => handleTogglePause(task)}
                      className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-400 transition-all cursor-pointer"
                      title={isPaused ? 'Resume Task' : 'Pause Task'}
                    >
                      {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                    </button>
                  )}
                  {!isCompleted && !isCancelled && (
                    <button
                      onClick={() => handleCancelTask(task.id)}
                      className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-rose-400 transition-all cursor-pointer"
                      title="Cancel Task"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden border border-slate-800">
                <div
                  className={`h-full transition-all duration-500 ${
                    isRunning ? 'bg-cyan-400 shadow-[0_0_8px_#00e5ff]' : isCompleted ? 'bg-emerald-400' : 'bg-amber-400'
                  }`}
                  style={{ width: `${Math.round(task.progress * 100)}%` }}
                />
              </div>

              {/* Logs / Result */}
              {task.result && <div className="text-[10px] font-mono text-emerald-300 bg-emerald-950/30 p-1.5 rounded border border-emerald-500/20">{task.result}</div>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
