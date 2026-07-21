import React, { useState } from 'react'
import { Bot, Cpu, Eye, Code2, Globe, Pause, Play, Send, Square } from 'lucide-react'

export interface AgentItem {
  id: string
  role: string
  status: 'ACTIVE' | 'RUNNING' | 'READY' | 'PAUSED' | 'STOPPED'
  icon: any
  description: string
}

export default function AgentOrchestratorCard() {
  const [agents, setAgents] = useState<AgentItem[]>([
    { id: 'ceo', role: 'CEO Agent', status: 'ACTIVE', icon: Bot, description: 'Goal Definition & Event Broker' },
    { id: 'planner', role: 'Planner Agent', status: 'RUNNING', icon: Cpu, description: 'LangGraph State Machine Engine' },
    { id: 'vision', role: 'Vision Agent', status: 'READY', icon: Eye, description: 'Accessibility Tree & Element Grounding' },
    { id: 'coding', role: 'Coding Agent', status: 'READY', icon: Code2, description: 'AST Bug Localization & Pytest Stubs' },
    { id: 'research', role: 'Research Agent', status: 'READY', icon: Globe, description: 'Persistent Browser Profiles & Citations' },
  ])

  const handleAction = async (agentId: string, action: 'pause' | 'resume' | 'trigger' | 'stop') => {
    try {
      let prompt = ''
      if (action === 'trigger') {
        prompt = window.prompt(`Enter task prompt to dispatch to ${agentId.toUpperCase()}:`) || ''
        if (!prompt) return
      }

      const res = await fetch('/api/ui/agent_action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId, action, task_prompt: prompt })
      })

      setAgents(prev => prev.map(a => {
        if (a.id === agentId) {
          if (action === 'pause') return { ...a, status: 'PAUSED' }
          if (action === 'resume') return { ...a, status: 'READY' }
          if (action === 'trigger') return { ...a, status: 'RUNNING' }
          if (action === 'stop') return { ...a, status: 'STOPPED' }
        }
        return a
      }))
    } catch (e) {
      console.warn('Agent action updated')
    }
  }


  return (
    <div className="bg-[rgba(10,20,38,0.75)] backdrop-blur-md border border-[rgba(0,229,255,0.18)] rounded-xl p-3 shadow-lg hover:border-[rgba(0,229,255,0.35)] transition-all">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-[#00e5ff]" />
          <span className="text-xs font-semibold text-[#00e5ff] tracking-wider uppercase">Multi-Agent Orchestrator</span>
        </div>
        <span className="text-[10px] font-mono text-[#00e676] bg-[rgba(0,230,118,0.1)] border border-[rgba(0,230,118,0.25)] px-2 py-0.5 rounded-full">
          {agents.filter(a => a.status !== 'PAUSED').length} / 5 Active
        </span>
      </div>

      <div className="space-y-1.5">
        {agents.map((a) => {
          const Icon = a.icon
          const isBusy = a.status === 'RUNNING' || a.status === 'ACTIVE'
          return (
            <div
              key={a.id}
              className="flex items-center justify-between p-1.5 rounded-lg bg-[rgba(15,30,56,0.4)] border border-[rgba(0,229,255,0.08)] text-xs hover:border-[rgba(0,229,255,0.25)] transition-all"
            >
              <div className="flex items-center gap-2">
                <div className={`p-1.5 rounded-md ${isBusy ? 'bg-[rgba(0,229,255,0.15)] text-[#00e5ff]' : 'bg-slate-800 text-slate-400'}`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <div>
                  <div className="font-semibold text-[#e1f5fe]">{a.role}</div>
                  <div className="text-[10px] text-[#b0bec5] truncate max-w-[150px]">{a.description}</div>
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                <span
                  className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                    a.status === 'RUNNING'
                      ? 'bg-[#ffaa00] text-slate-950 animate-pulse'
                      : a.status === 'ACTIVE'
                      ? 'bg-[#00e5ff] text-slate-950'
                      : a.status === 'PAUSED'
                      ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                      : a.status === 'STOPPED'
                      ? 'bg-slate-900 text-slate-500 border border-slate-800'
                      : 'bg-slate-800 text-slate-300'
                  }`}
                >
                  {a.status}
                </span>
                
                {a.status === 'PAUSED' || a.status === 'STOPPED' ? (
                  <button
                    onClick={() => handleAction(a.id, 'resume')}
                    className="p-1 rounded bg-emerald-950/60 hover:bg-emerald-900 text-emerald-400 border border-emerald-700/50"
                    title="Resume Agent"
                  >
                    <Play className="w-3 h-3" />
                  </button>
                ) : (
                  <button
                    onClick={() => handleAction(a.id, 'pause')}
                    className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
                    title="Pause Agent"
                  >
                    <Pause className="w-3 h-3" />
                  </button>
                )}

                <button
                  onClick={() => handleAction(a.id, 'stop')}
                  className="p-1 rounded bg-red-950/40 hover:bg-red-900/60 text-red-400 border border-red-800/40"
                  title="Stop Agent Action"
                >
                  <Square className="w-3 h-3 fill-current" />
                </button>

                <button
                  onClick={() => handleAction(a.id, 'trigger')}
                  className="p-1 rounded bg-[#00e5ff]/10 hover:bg-[#00e5ff]/20 text-[#00e5ff] border border-[#00e5ff]/30"
                  title="Dispatch Custom Sub-task"
                >
                  <Send className="w-3 h-3" />
                </button>

              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

