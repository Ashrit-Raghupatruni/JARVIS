import React from 'react'
import { Server, ShieldCheck, Wrench, Layers } from 'lucide-react'

export default function MCPServersCard() {
  const mcpServers = [
    { name: 'FastMCP Skill Registry', toolsCount: 55, status: 'CONNECTED', riskScore: 'LOW' },
    { name: 'Desktop Automation MCP', toolsCount: 12, status: 'CONNECTED', riskScore: 'SAFE' },
    { name: 'Research & Web MCP', toolsCount: 8, status: 'CONNECTED', riskScore: 'SAFE' },
  ]

  return (
    <div className="bg-[rgba(10,20,38,0.75)] backdrop-blur-md border border-[rgba(0,229,255,0.18)] rounded-xl p-3 shadow-lg hover:border-[rgba(0,229,255,0.35)] transition-all">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Server className="w-4 h-4 text-[#00e5ff]" />
          <span className="text-xs font-semibold text-[#00e5ff] tracking-wider uppercase">MCP Servers & Tool Registry</span>
        </div>
        <span className="text-[10px] font-mono text-[#00e676] bg-[rgba(0,230,118,0.1)] border border-[rgba(0,230,118,0.25)] px-2 py-0.5 rounded-full">
          75 Discovered Tools
        </span>
      </div>

      <div className="space-y-1.5">
        {mcpServers.map((s, idx) => (
          <div key={idx} className="flex items-center justify-between p-1.5 rounded-lg bg-[rgba(15,30,56,0.4)] border border-[rgba(0,229,255,0.08)] text-xs">
            <div className="flex items-center gap-2">
              <Wrench className="w-3.5 h-3.5 text-[#00e5ff]" />
              <div>
                <div className="font-semibold text-[#e1f5fe]">{s.name}</div>
                <div className="text-[10px] text-[#b0bec5] font-mono">{s.toolsCount} registered tool handlers</div>
              </div>
            </div>

            <div className="text-right">
              <span className="text-[10px] font-mono font-bold text-[#00e676] bg-[rgba(0,230,118,0.12)] px-1.5 py-0.5 rounded">
                {s.status}
              </span>
              <div className="text-[9px] font-mono text-slate-400 mt-0.5">Risk: {s.riskScore}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
