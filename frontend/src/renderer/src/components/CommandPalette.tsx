import React, { useState, useEffect } from 'react'
import { Search, Command, Zap, Play, Terminal, Shield, X } from 'lucide-react'

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
  onSelectAction: (action: string) => void
}

export default function CommandPalette({ isOpen, onClose, onSelectAction }: CommandPaletteProps) {
  const [query, setQuery] = useState('')

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        if (isOpen) onClose()
        else onSelectAction('open_palette')
      }
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose, onSelectAction])

  if (!isOpen) return null

  const actions = [
    { label: 'Inspect Screen & Active Window Hierarchy', icon: Terminal, category: 'Vision & Computer Use', id: 'inspect_screen' },
    { label: 'Run System Hardware & LLM Latency Benchmarks', icon: Zap, category: 'Diagnostics', id: 'run_benchmarks' },
    { label: 'Trigger Local Compressed ZIP Backup', icon: Shield, category: 'Data Backup', id: 'trigger_backup' },
    { label: 'Execute Workstation Setup Macro', icon: Play, category: 'Workflows', id: 'macro_workstation' },
    { label: 'Check Active Backend Services Status', icon: Zap, category: 'System Status', id: 'check_status' },
    { label: 'Discover FastMCP Skill Tool Registry', icon: Command, category: 'MCP Tools', id: 'discover_mcp' },
  ]

  const filtered = actions.filter(
    (a) =>
      a.label.toLowerCase().includes(query.toLowerCase()) ||
      a.category.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-slate-950/70 backdrop-blur-md animate-fade-in">
      <div className="w-full max-w-xl bg-[rgba(10,20,38,0.92)] border border-[rgba(0,229,255,0.35)] rounded-2xl shadow-2xl overflow-hidden backdrop-blur-xl">
        {/* Input header */}
        <div className="flex items-center gap-3 p-4 border-b border-[rgba(0,229,255,0.15)] bg-[rgba(15,30,56,0.6)]">
          <Search className="w-5 h-5 text-[#00e5ff]" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search action (e.g. Inspect Screen, Backup)..."
            className="w-full bg-transparent font-mono text-sm text-[#e1f5fe] placeholder-slate-500 focus:outline-none"
          />
          <button onClick={onClose} className="text-slate-400 hover:text-[#00e5ff]">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length > 0 ? (
            filtered.map((item) => {
              const Icon = item.icon
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    onSelectAction(item.id)
                    onClose()
                  }}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-[rgba(15,30,56,0.3)] hover:bg-[rgba(0,229,255,0.15)] border border-transparent hover:border-[rgba(0,229,255,0.3)] text-xs cursor-pointer transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-[rgba(0,229,255,0.1)] text-[#00e5ff]">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="font-semibold text-[#e1f5fe]">{item.label}</div>
                      <div className="text-[10px] font-mono text-[#b0bec5]">{item.category}</div>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-[#00e5ff] opacity-0 group-hover:opacity-100">
                    Execute ↵
                  </span>
                </div>
              )
            })
          ) : (
            <div className="p-6 text-center text-xs font-mono text-slate-400">
              No matching commands found.
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="p-2.5 bg-slate-900/60 border-t border-[rgba(0,229,255,0.1)] flex items-center justify-between text-[10px] font-mono text-slate-400 px-4">
          <span>Use <strong>↑</strong> <strong>↓</strong> to navigate</span>
          <span><strong>Esc</strong> to close</span>
        </div>
      </div>
    </div>
  )
}
