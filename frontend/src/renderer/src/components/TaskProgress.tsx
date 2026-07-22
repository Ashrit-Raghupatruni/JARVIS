import React from 'react'
import { useAppStore } from '../stores/appStore'
import {
  Target,
  GitBranch,
  Brain,
  Wrench,
  BookOpen,
  Globe,
  Sparkles,
  CheckCircle2,
  MessageSquare,
  Activity,
  X
} from 'lucide-react'

interface ExecutionStage {
  id: string
  label: string
  icon: React.ComponentType<{ className?: string }>
}

const STAGES: ExecutionStage[] = [
  { id: 'intent', label: 'Intent Detection', icon: Target },
  { id: 'planner', label: 'Planner', icon: GitBranch },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'tools', label: 'Tool Selection', icon: Wrench },
  { id: 'rag', label: 'RAG Knowledge', icon: BookOpen },
  { id: 'research', label: 'Web Research', icon: Globe },
  { id: 'llm', label: 'LLM Reasoning', icon: Sparkles },
  { id: 'validation', label: 'Validation', icon: CheckCircle2 },
  { id: 'response', label: 'Response', icon: MessageSquare }
]

export default function TaskProgress() {
  const { currentTask, assistantState, setAssistantState, setCurrentTask } = useAppStore()

  if (!currentTask && assistantState === 'idle') {
    return (
      <div className="h-full w-full rounded-xl border border-slate-800 bg-slate-950/60 p-3 backdrop-blur-md flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono text-slate-400">Execution Pipeline Standing By</span>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-cyan-300">
          IDLE
        </span>
      </div>
    )
  }

  // Calculate current stage index based on assistantState or task steps
  let activeStageIdx = 0
  if (assistantState === 'listening') activeStageIdx = 0
  else if (assistantState === 'processing') activeStageIdx = 3
  else if (assistantState === 'speaking') activeStageIdx = 8
  else if (assistantState === 'executing') activeStageIdx = 5

  return (
    <div className="h-full w-full rounded-xl border border-cyan-500/20 bg-slate-950/90 p-3.5 backdrop-blur-xl shadow-2xl flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
          <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider">
            Live Execution Timeline
          </h3>
        </div>
        <button
          onClick={() => {
            setCurrentTask(null)
            setAssistantState('idle' as any)
          }}
          className="p-1 rounded bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/40 text-[10px] font-mono cursor-pointer"
        >
          Stop Task
        </button>
      </div>

      {/* Task Description */}
      {currentTask && (
        <div className="text-xs font-mono text-cyan-300 bg-cyan-950/30 px-2.5 py-1 rounded border border-cyan-500/20 truncate mb-2">
          {currentTask.description}
        </div>
      )}

      {/* 9-Stage Pipeline Indicators */}
      <div className="grid grid-cols-3 gap-1.5 flex-1 items-center">
        {STAGES.map((stage, idx) => {
          const Icon = stage.icon
          const isDone = idx < activeStageIdx
          const isActive = idx === activeStageIdx
          const isPending = idx > activeStageIdx

          return (
            <div
              key={stage.id}
              className={`flex items-center gap-1.5 px-2 py-1 rounded border text-[10px] font-mono transition-all ${
                isActive
                  ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 shadow-[0_0_10px_rgba(0,229,255,0.3)] animate-pulse'
                  : isDone
                  ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
                  : 'bg-slate-900/40 border-slate-800 text-slate-500 opacity-60'
              }`}
            >
              <Icon className="w-3 h-3 shrink-0" />
              <span className="truncate">{stage.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
