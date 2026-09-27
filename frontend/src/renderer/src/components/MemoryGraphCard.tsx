import React from 'react'
import { Database, Network, Brain, HardDrive } from 'lucide-react'

export default function MemoryGraphCard() {
  const memoryScopes = [
    { name: 'Working Memory', count: '12 active vars', color: '#00e5ff' },
    { name: 'Conversational', count: '48 message pairs', color: '#00aeff' },
    { name: 'Semantic (ChromaDB)', count: '1,420 vectors', color: '#00e676' },
    { name: 'Knowledge Graph', count: '86 nodes / 142 edges', color: '#d500f9' },
  ]

  return (
    <div className="bg-slate-950/40 backdrop-blur-2xl border border-blue-500/20 rounded-2xl p-5 shadow-[0_8px_32px_0_rgba(0,0,0,0.37)] hover:border-cyan-500/30 transition-all">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#00e5ff] animate-pulse" />
          <span className="text-xs font-bold text-slate-200 tracking-[0.2em] uppercase font-mono">Memory & Knowledge Graph</span>
        </div>
        <span className="text-[10px] font-mono text-purple-300 bg-purple-950/30 border border-purple-500/30 px-2.5 py-0.5 rounded-full shadow-[0_0_10px_rgba(213,0,249,0.2)]">
          6-Scope Memory Active
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2.5 mb-3">
        {memoryScopes.map((m, idx) => (
          <div key={idx} className="p-2.5 rounded-xl bg-slate-900/40 border border-white/5 hover:border-cyan-500/20 transition-all">
            <div className="text-[10px] text-slate-400 font-mono font-medium truncate">{m.name}</div>
            <div className="text-xs font-mono font-bold mt-1" style={{ color: m.color }}>
              {m.count}
            </div>
          </div>
        ))}
      </div>

      <div className="p-2.5 rounded-xl bg-slate-950/50 border border-white/5 flex items-center justify-between text-[11px] font-mono">
        <span className="flex items-center gap-2 text-slate-300">
          <Network className="w-3.5 h-3.5 text-purple-400" /> Knowledge Graph State:
        </span>
        <span className="text-emerald-400 font-bold tracking-wider">SYNCHRONIZED</span>
      </div>
    </div>
  )
}
