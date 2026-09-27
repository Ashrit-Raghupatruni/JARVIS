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
      <div className="h-full w-full rounded-2xl border border-blue-500/20 bg-slate-950/40 backdrop-blur-2xl p-4 shadow-[0_8px_32px_0_rgba(0,0,0,0.37)] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-cyan-400/60 shadow-[0_0_8px_#00e5ff]" />
          <span className="text-xs font-mono text-slate-300">Execution Pipeline Standing By</span>
        </div>
        <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-blue-950/30 border border-blue-500/20 text-cyan-300">
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
    <div className="h-full w-full rounded-2xl border border-blue-500/20 bg-slate-950/40 backdrop-blur-2xl p-4 shadow-[0_8px_32px_0_rgba(0,0,0,0.37)] flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#00e5ff] animate-pulse" />
          <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-[0.2em]">
            Live Execution Timeline
          </h3>
        </div>
        <button
          onClick={() => {
            setCurrentTask(null)
            setAssistantState('idle' as any)
          }}
          className="px-2.5 py-1 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border border-rose-800/40 text-[10px] font-mono cursor-pointer transition"
        >
          Stop Task
        </button>
      </div>

      {/* Task Description */}
      {currentTask && (
        <div className="text-xs font-mono text-cyan-300 bg-blue-950/20 px-3 py-1.5 rounded-xl border border-cyan-500/20 truncate mb-3">
          {currentTask.description}
        </div>
      )}

      {/* 9-Stage Pipeline Indicators */}
      <div className="grid grid-cols-3 gap-2 flex-1 items-center">
        {STAGES.map((stage, idx) => {
          const Icon = stage.icon
          const isDone = idx < activeStageIdx
          const isActive = idx === activeStageIdx

          return (
            <div
              key={stage.id}
              className={`flex items-center gap-2 px-2.5 py-1.5 rounded-xl border text-[10px] font-mono transition-all ${
                isActive
                  ? 'bg-blue-600/30 border-cyan-400/60 text-cyan-200 shadow-[0_0_15px_rgba(0,229,255,0.25)] animate-pulse'
                  : isDone
                  ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                  : 'bg-slate-900/30 border-white/5 text-slate-500 opacity-60'
              }`}
            >
              <Icon className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{stage.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
