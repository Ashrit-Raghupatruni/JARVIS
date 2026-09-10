import React from 'react'

interface SystemDiagnosticsTabProps {
  rankings: any[]
  routerMetrics: any[]
  brainData: { memories: any[], lessons: any[], workflows: any[] }
  consolidating: boolean
  onConsolidate: () => void
  activeSubSection?: 'orchestrator' | 'brain'
}

export const SystemDiagnosticsTab: React.FC<SystemDiagnosticsTabProps> = ({
  rankings,
  routerMetrics,
  brainData,
  consolidating,
  onConsolidate,
  activeSubSection = 'orchestrator'
}) => {
  if (activeSubSection === 'orchestrator') {
    return (
      <div className="space-y-6 animate-fade-in">
        <section>
          <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Live Provider Rankings</h3>
          <div className="space-y-3">
            {rankings.length === 0 ? (
              <p className="text-sm text-center py-4" style={{ color: 'var(--jarvis-text-dim)' }}>Loading provider rankings...</p>
            ) : (
              rankings.map((r, index) => (
                <div key={r.provider} className="p-3.5 rounded-xl border border-white/5 bg-white/5 flex flex-col gap-2">
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="text-sm font-semibold uppercase tracking-wide mr-2" style={{ color: index === 0 ? 'var(--jarvis-accent)' : 'var(--jarvis-text)' }}>
                        #{index + 1} {r.provider}
                      </span>
                      <span className="text-xs" style={{ color: 'var(--jarvis-text-dim)' }}>({r.model})</span>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${r.circuit === 'CLOSED' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'}`}>
                      {r.circuit === 'CLOSED' ? 'HEALTHY' : 'TRIPPED'}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-1 text-xs">
                    <div>
                      <p style={{ color: 'var(--jarvis-text-dim)' }}>Latency</p>
                      <p className="font-semibold text-sm" style={{ color: 'var(--jarvis-text)' }}>{r.latency} ms</p>
                    </div>
                    <div>
                      <p style={{ color: 'var(--jarvis-text-dim)' }}>Throughput</p>
                      <p className="font-semibold text-sm" style={{ color: 'var(--jarvis-text)' }}>{r.throughput} t/s</p>
                    </div>
                    <div>
                      <p style={{ color: 'var(--jarvis-text-dim)' }}>Success Rate</p>
                      <p className="font-semibold text-sm" style={{ color: 'var(--jarvis-text)' }}>{r.success_rate}%</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section>
          <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Routing Log</h3>
          <div className="max-h-48 overflow-y-auto space-y-2 pr-1 custom-scrollbar text-xs">
            {routerMetrics.length === 0 ? (
              <p className="text-center py-4" style={{ color: 'var(--jarvis-text-dim)' }}>No routing events recorded.</p>
            ) : (
              routerMetrics.map((m) => (
                <div key={m.id} className="p-2.5 rounded-lg border border-white/5 bg-white/[0.02] flex justify-between items-center">
                  <div>
                    <p className="font-medium" style={{ color: 'var(--jarvis-text)' }}>
                      Routed to {m.selected_provider}
                    </p>
                    <p className="text-[10px]" style={{ color: 'var(--jarvis-text-dim)' }}>
                      {m.selected_model}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold" style={{ color: m.success ? 'var(--jarvis-accent)' : '#f87171' }}>
                      {m.latency} ms
                    </p>
                    {m.fallback_count > 0 && (
                      <p className="text-[9px] text-amber-400">
                        Failovers: {m.fallback_count}
                      </p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--jarvis-accent)' }}>Memory Management</h3>
          <p className="text-[11px]" style={{ color: 'var(--jarvis-text-dim)' }}>Locally stored concepts, corrections, and solutions.</p>
        </div>
        <button
          onClick={onConsolidate}
          disabled={consolidating}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all disabled:opacity-50"
          style={{ color: 'var(--jarvis-accent)', borderColor: 'var(--jarvis-accent)', backgroundColor: 'transparent' }}
        >
          {consolidating ? 'Consolidating...' : 'Consolidate Memories'}
        </button>
      </div>

      {/* Stored facts */}
      <section>
        <h4 className="text-xs font-semibold mb-2.5" style={{ color: 'var(--jarvis-text)' }}>Learned Preferences & Facts ({brainData.memories.length})</h4>
        <div className="max-h-36 overflow-y-auto space-y-2 pr-1 custom-scrollbar text-xs">
          {brainData.memories.length === 0 ? (
            <p style={{ color: 'var(--jarvis-text-dim)' }}>No memories stored yet.</p>
          ) : (
            brainData.memories.map((m) => (
              <div key={m.id} className="p-2.5 rounded-lg border border-white/5 bg-white/[0.02] flex justify-between items-center">
                <span style={{ color: 'var(--jarvis-text)' }}>{m.content}</span>
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${
                  m.importance === 'critical' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                  m.importance === 'high' ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30' :
                  m.importance === 'medium' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' :
                  'bg-white/10 text-white/50'
                }`}>
                  {m.importance}
                </span>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Lessons Learned */}
      <section>
        <h4 className="text-xs font-semibold mb-2.5" style={{ color: 'var(--jarvis-text)' }}>Corrections History / Lessons ({brainData.lessons.length})</h4>
        <div className="max-h-36 overflow-y-auto space-y-2 pr-1 custom-scrollbar text-xs">
          {brainData.lessons.length === 0 ? (
            <p style={{ color: 'var(--jarvis-text-dim)' }}>No corrections recorded.</p>
          ) : (
            brainData.lessons.map((l) => (
              <div key={l.id} className="p-2.5 rounded-lg border border-rose-500/10 bg-rose-500/5 space-y-1">
                <div className="flex justify-between text-[10px]" style={{ color: 'var(--jarvis-accent)' }}>
                  <span className="font-semibold">Trigger: "{l.trigger_keywords}"</span>
                </div>
                <p style={{ color: 'var(--jarvis-text-dim)' }}>
                  <span className="text-rose-400 font-medium">Error:</span> {l.error_description}
                </p>
                <p style={{ color: 'var(--jarvis-text)' }}>
                  <span className="text-emerald-400 font-medium">Correction:</span> {l.correction}
                </p>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  )
}
export default SystemDiagnosticsTab
