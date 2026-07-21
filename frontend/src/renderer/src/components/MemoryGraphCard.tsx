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
    <div className="bg-[rgba(10,20,38,0.75)] backdrop-blur-md border border-[rgba(0,229,255,0.18)] rounded-xl p-3 shadow-lg hover:border-[rgba(0,229,255,0.35)] transition-all">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-[#00e5ff]" />
          <span className="text-xs font-semibold text-[#00e5ff] tracking-wider uppercase">Memory & Knowledge Graph Overview</span>
        </div>
        <span className="text-[10px] font-mono text-purple-400 bg-purple-950/40 border border-purple-800/40 px-2 py-0.5 rounded-full">
          6-Scope Memory Active
        </span>
      </div>

      <div className="grid grid-cols-2 gap-1.5 mb-2">
        {memoryScopes.map((m, idx) => (
          <div key={idx} className="p-1.5 rounded-lg bg-[rgba(15,30,56,0.4)] border border-[rgba(0,229,255,0.08)]">
            <div className="text-[10px] text-[#b0bec5] font-semibold truncate">{m.name}</div>
            <div className="text-[11px] font-mono font-bold mt-0.5" style={{ color: m.color }}>
              {m.count}
            </div>
          </div>
        ))}
      </div>

      <div className="p-2 rounded-lg bg-[rgba(0,0,0,0.3)] border border-[rgba(0,229,255,0.1)] flex items-center justify-between text-[11px] font-mono">
        <span className="flex items-center gap-1.5 text-slate-300">
          <Network className="w-3.5 h-3.5 text-[#d500f9]" /> Knowledge Graph State:
        </span>
        <span className="text-[#00e676] font-bold">SYNCHRONIZED</span>
      </div>
    </div>
  )
}
