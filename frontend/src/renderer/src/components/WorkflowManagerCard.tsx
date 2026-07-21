import React, { useState } from 'react'
import { Play, Circle, Zap, Plus, Trash2, Loader2 } from 'lucide-react'

export default function WorkflowManagerCard() {
  const [runningMacro, setRunningMacro] = useState<string | null>(null)
  const [newMacroName, setNewMacroName] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [macros, setMacros] = useState([
    { id: 'm1', name: 'Workstation Setup', desc: 'Opens VS Code, Spotify & Chrome', duration: '2.4s' },
    { id: 'm2', name: 'Daily Briefing Macro', desc: 'Triggers calendar, tasks & news', duration: '1.8s' },
    { id: 'm3', name: 'Clean Desktop Layout', desc: 'Minimizes windows & centers HUD', duration: '0.9s' },
  ])

  const handlePlay = async (name: string) => {
    setRunningMacro(name)
    try {
      await fetch('/api/ui/workflow_action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'run', name })
      })
    } catch (e) {
      console.warn('Macro execution started')
    } finally {
      setTimeout(() => {
        setRunningMacro(null)
      }, 1500)
    }
  }

  const handleCreate = async () => {
    if (!newMacroName.trim()) return
    const name = newMacroName.trim()
    try {
      await fetch('/api/ui/workflow_action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'create', name })
      })
      setMacros(prev => [{ id: Date.now().toString(), name, desc: 'Custom recorded macro workflow', duration: '1.0s' }, ...prev])
      setNewMacroName('')
      setShowCreate(false)
    } catch (e) {
      setMacros(prev => [{ id: Date.now().toString(), name, desc: 'Custom recorded macro workflow', duration: '1.0s' }, ...prev])
      setNewMacroName('')
      setShowCreate(false)
    }
  }

  const handleDelete = async (id: string, name: string) => {
    try {
      await fetch('/api/ui/workflow_action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete', name })
      })
      setMacros(prev => prev.filter(m => m.id !== id))
    } catch (e) {
      setMacros(prev => prev.filter(m => m.id !== id))
    }
  }

  return (
    <div className="bg-[rgba(10,20,38,0.75)] backdrop-blur-md border border-[rgba(0,229,255,0.18)] rounded-xl p-3 shadow-lg hover:border-[rgba(0,229,255,0.35)] transition-all">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-[#00e5ff]" />
          <span className="text-xs font-semibold text-[#00e5ff] tracking-wider uppercase">Workflow & Macro Manager</span>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-1 text-[10px] font-mono bg-[rgba(0,229,255,0.12)] hover:bg-[rgba(0,229,255,0.25)] text-[#00e5ff] border border-[rgba(0,229,255,0.3)] px-2 py-0.5 rounded transition-all"
        >
          <Plus className="w-3 h-3" /> New Workflow
        </button>
      </div>

      {showCreate && (
        <div className="flex items-center gap-1.5 mb-2 p-1.5 rounded-lg bg-slate-900/90 border border-[#00e5ff]/30">
          <input
            type="text"
            value={newMacroName}
            onChange={(e) => setNewMacroName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="Workflow name (e.g. Build Project)..."
            className="flex-1 bg-transparent font-mono text-[10px] text-white focus:outline-none placeholder:text-slate-500 px-1"
          />
          <button
            onClick={handleCreate}
            className="px-2 py-0.5 text-[10px] font-mono bg-[#00e676]/20 text-[#00e676] rounded border border-[#00e676]/40 hover:bg-[#00e676]/30"
          >
            Save
          </button>
        </div>
      )}

      <div className="space-y-1.5">
        {macros.map((m) => {
          const isExec = runningMacro === m.name
          return (
            <div
              key={m.id}
              className="flex items-center justify-between p-1.5 rounded-lg bg-[rgba(15,30,56,0.4)] border border-[rgba(0,229,255,0.08)] text-xs hover:border-[rgba(0,229,255,0.25)] transition-all"
            >
              <div>
                <div className="font-semibold text-[#e1f5fe]">{m.name}</div>
                <div className="text-[10px] text-[#b0bec5]">{m.desc}</div>
              </div>

              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handlePlay(m.name)}
                  disabled={isExec}
                  className={`flex items-center gap-1 text-[10px] font-mono font-semibold px-2 py-1 rounded transition-all ${
                    isExec
                      ? 'bg-[#ffaa00] text-slate-950 animate-pulse'
                      : 'bg-[rgba(0,229,255,0.12)] hover:bg-[rgba(0,229,255,0.25)] text-[#00e5ff] border border-[rgba(0,229,255,0.3)]'
                  }`}
                >
                  {isExec ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                  <span>{isExec ? 'Running' : 'Run'}</span>
                </button>
                <button
                  onClick={() => handleDelete(m.id, m.name)}
                  className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                  title="Delete Workflow"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
