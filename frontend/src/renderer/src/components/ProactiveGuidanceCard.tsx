import React from 'react'
import { Lightbulb, ArrowRight, X, Sparkles, Clock, Compass } from 'lucide-react'

export interface ProactiveGuidanceItem {
  guidance_type: 'active_project' | 'topic_digest' | 'agenda_recap' | 'suggestion' | 'error_alert'
  title: string
  message: str
  action_suggestion?: string
}

interface ProactiveGuidanceCardProps {
  item: ProactiveGuidanceItem
  onActionClick?: (suggestion: string) => void
  onDismiss?: () => void
}

export const ProactiveGuidanceCard: React.FC<ProactiveGuidanceCardProps> = ({
  item,
  onActionClick,
  onDismiss,
}) => {
  const getIcon = () => {
    switch (item.guidance_type) {
      case 'active_project':
        return <Sparkles className="w-4 h-4 text-cyan-400" />
      case 'topic_digest':
        return <Compass className="w-4 h-4 text-amber-400" />
      case 'agenda_recap':
        return <Clock className="w-4 h-4 text-emerald-400" />
      default:
        return <Lightbulb className="w-4 h-4 text-cyan-400" />
    }
  }

  return (
    <div className="w-full bg-slate-900/90 backdrop-blur-md border border-cyan-500/30 rounded-xl p-3.5 my-2 shadow-[0_4px_16px_rgba(0,0,0,0.5)] animate-in fade-in slide-in-from-top-2 duration-300">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-cyan-950/60 border border-cyan-500/30">
            {getIcon()}
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-100 font-mono tracking-wide uppercase">
              {item.title}
            </h4>
            <span className="text-[10px] text-cyan-400/80 font-mono">Proactive 2.0 Engine</span>
          </div>
        </div>

        {onDismiss && (
          <button
            onClick={onDismiss}
            className="p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 transition-all cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      <p className="text-xs text-slate-300 mt-2 font-mono leading-relaxed">
        {item.message}
      </p>

      {item.action_suggestion && (
        <div className="mt-3 pt-2.5 border-t border-slate-800 flex items-center justify-between">
          <span className="text-[11px] text-slate-400 font-mono italic">
            "{item.action_suggestion}"
          </span>
          <button
            onClick={() => onActionClick?.(item.action_suggestion!)}
            className="flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 text-xs font-mono font-semibold transition-all cursor-pointer shadow-[0_0_10px_rgba(0,229,255,0.2)]"
          >
            <span>Execute Action</span>
            <ArrowRight className="w-3 h-3 text-cyan-300" />
          </button>
        </div>
      )}
    </div>
  )
}
