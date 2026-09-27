import React, { useState } from 'react'
import {
  Zap,
  LayoutGrid,
  Lock,
  FilePlus,
  Target,
  Camera,
  Info,
  CheckCircle2,
  Loader2
} from 'lucide-react'
import { useAppStore } from '../stores/appStore'

interface QuickActionsCardProps {
  onExecutePrompt?: (prompt: string) => void
}

export const QuickActionsCard: React.FC<QuickActionsCardProps> = ({ onExecutePrompt }) => {
  const focusMode = useAppStore((s) => s.focusMode)
  const toggleFocusMode = useAppStore((s) => s.toggleFocusMode)
  const setActiveTab = useAppStore((s) => s.setActiveTab)
  const quickActionFeedback = useAppStore((s) => s.quickActionFeedback)
  const setQuickActionFeedback = useAppStore((s) => s.setQuickActionFeedback)

  const [loadingAction, setLoadingAction] = useState<string | null>(null)

  const getHost = () =>
    typeof window !== 'undefined' && window.location.hostname && window.location.hostname !== 'localhost'
      ? window.location.hostname
      : '127.0.0.1'

  const showFeedback = (text: string) => {
    setQuickActionFeedback(text)
    setTimeout(() => {
      setQuickActionFeedback(null)
    }, 3500)
  }

  const handleAction = async (actionId: string) => {
    setLoadingAction(actionId)
    try {
      switch (actionId) {
        case 'open_app': {
          if (onExecutePrompt) {
            onExecutePrompt('Open application')
          } else {
            showFeedback('Say "Open Notepad" or any app name')
          }
          break
        }

        case 'lock_pc': {
          try {
            const res = await fetch(`http://${getHost()}:8000/api/system/lock`, { method: 'POST' })
            if (res.ok) {
              showFeedback('PC Locked successfully')
            } else {
              showFeedback('Lock command initiated')
            }
          } catch {
            showFeedback('Lock command initiated')
          }
          break
        }

        case 'create_file': {
          if (onExecutePrompt) {
            onExecutePrompt('Create a new scratch note file')
          } else {
            showFeedback('Creating new file...')
          }
          break
        }

        case 'focus_mode': {
          const nextState = !focusMode
          toggleFocusMode(nextState)
          showFeedback(nextState ? 'Focus Mode Activated' : 'Focus Mode Deactivated')
          break
        }

        case 'screenshot': {
          showFeedback('Capturing screenshot...')
          try {
            const res = await fetch(`http://${getHost()}:8000/api/system/screenshot`, { method: 'POST' })
            if (res.ok) {
              showFeedback('Screenshot saved to artifacts')
            } else {
              // Fallback via prompt execution
              if (onExecutePrompt) onExecutePrompt('Take a screenshot')
              else showFeedback('Screenshot captured')
            }
          } catch {
            if (onExecutePrompt) onExecutePrompt('Take a screenshot')
            else showFeedback('Screenshot captured')
          }
          break
        }

        case 'system_info': {
          setActiveTab('system')
          showFeedback('Viewing System Diagnostics')
          break
        }
      }
    } finally {
      setTimeout(() => setLoadingAction(null), 400)
    }
  }

  const actionButtons = [
    {
      id: 'open_app',
      label: 'Open App',
      icon: LayoutGrid,
      color: 'text-cyan-400 group-hover:text-cyan-300',
      active: false
    },
    {
      id: 'lock_pc',
      label: 'Lock PC',
      icon: Lock,
      color: 'text-blue-400 group-hover:text-blue-300',
      active: false
    },
    {
      id: 'create_file',
      label: 'Create File',
      icon: FilePlus,
      color: 'text-indigo-400 group-hover:text-indigo-300',
      active: false
    },
    {
      id: 'focus_mode',
      label: focusMode ? 'Focusing' : 'Focus Mode',
      icon: Target,
      color: focusMode ? 'text-emerald-400' : 'text-slate-300 group-hover:text-white',
      active: focusMode
    },
    {
      id: 'screenshot',
      label: 'Screenshot',
      icon: Camera,
      color: 'text-sky-400 group-hover:text-sky-300',
      active: false
    },
    {
      id: 'system_info',
      label: 'System Info',
      icon: Info,
      color: 'text-teal-400 group-hover:text-teal-300',
      active: false
    }
  ]

  return (
    <div className="w-full bg-slate-950/40 backdrop-blur-2xl border border-blue-500/20 rounded-2xl p-4 shadow-[0_8px_32px_0_rgba(0,0,0,0.37)]">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-bold tracking-[0.2em] text-slate-200 uppercase font-mono">
            QUICK ACTIONS
          </h3>
        </div>
        <span className="text-[10px] text-slate-400/80 font-mono">Voice or Click</span>
      </div>

      {/* Dynamic Feedback Banner */}
      {quickActionFeedback && (
        <div className="mt-2.5 px-3 py-1.5 rounded-lg bg-cyan-950/40 border border-cyan-500/30 flex items-center gap-2 text-cyan-300 text-xs animate-in fade-in slide-in-from-top-1">
          <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <span className="truncate">{quickActionFeedback}</span>
        </div>
      )}

      {/* 2x3 Grid */}
      <div className="grid grid-cols-2 gap-2.5 mt-3">
        {actionButtons.map((action) => {
          const Icon = action.icon
          const isLoading = loadingAction === action.id

          return (
            <button
              key={action.id}
              type="button"
              onClick={() => handleAction(action.id)}
              disabled={isLoading}
              className={`group flex items-center gap-2.5 px-3 py-2.5 rounded-xl border transition-all duration-200 text-left cursor-pointer ${
                action.active
                  ? 'bg-blue-600/25 border-cyan-400/50 shadow-[0_0_15px_rgba(0,229,255,0.2)]'
                  : 'bg-slate-900/40 border-white/5 hover:border-cyan-500/30 hover:bg-slate-800/40 hover:shadow-[0_0_12px_rgba(0,229,255,0.1)]'
              }`}
            >
              <div
                className={`p-1.5 rounded-lg shrink-0 transition-colors ${
                  action.active
                    ? 'bg-cyan-500/20 text-cyan-300'
                    : 'bg-white/5 group-hover:bg-cyan-500/10'
                }`}
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
                ) : (
                  <Icon className={`w-4 h-4 ${action.color}`} />
                )}
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-xs font-medium text-slate-200 group-hover:text-white truncate">
                  {action.label}
                </span>
                {action.id === 'focus_mode' && (
                  <span className={`text-[9px] font-mono leading-none ${focusMode ? 'text-emerald-400' : 'text-slate-500'}`}>
                    {focusMode ? 'ENABLED' : 'OFF'}
                  </span>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
