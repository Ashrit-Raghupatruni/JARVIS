import React, { useState, useEffect } from 'react'
import { Terminal, Shield, Cpu, RefreshCw, Check, X, Database, List, AlertTriangle, CheckCircle } from 'lucide-react'

interface Capability {
  name: string
  status: 'IMPLEMENTED' | 'PARTIALLY_IMPLEMENTED' | 'EXPERIMENTAL' | 'BROKEN' | 'UNUSED' | 'PLACEHOLDER' | 'MISSING'
  description: string
  implementation_files: string[]
  test_files: string[]
  dependencies: string[]
}

interface CapabilityRegistry {
  project_name: string
  version: string
  capabilities: Record<string, Capability>
}

interface DiagnosticReport {
  diagnostic_status: 'HEALTHY' | 'DEGRADED'
  timestamp: number
  metrics: {
    cpu_percent: number
    ram_percent: number
    disk_percent: number
    rag_database: string
    vector_memory: string
    speech_to_text_model: string
    wake_word_model: string
    camera_perception: string
    display_screen: string
    hand_gesture_control: string
    capability_registry: string
  }
  discovered_issues: string[]
  recommendations: string[]
}

interface ModificationProposal {
  action_type: string
  file_path: string
  proposed_code: string
  description: string
  timestamp: number
}

interface DeveloperMemory {
  bugs_fixed: number
  lessons_learned: string[]
  repair_history: Array<{
    file: string
    error: string
    resolved: boolean
    timestamp: number
  }>
}

export function DeveloperDashboard() {
  const [registry, setRegistry] = useState<CapabilityRegistry | null>(null)
  const [diagnostic, setDiagnostic] = useState<DiagnosticReport | null>(null)
  const [memory, setMemory] = useState<DeveloperMemory | null>(null)
  const [approvals, setApprovals] = useState<Record<string, ModificationProposal>>({})
  const [loading, setLoading] = useState(false)
  const [activeSubTab, setActiveSubTab] = useState<'capabilities' | 'diagnostics' | 'approvals' | 'memory'>('capabilities')

  const getBackendPort = () => {
    // In dev, usually 8000
    return 8000
  }

  const host = typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' ? window.location.hostname : '127.0.0.1'
  const BASE_URL = `http://${host}:${getBackendPort()}/api/v1`

  const fetchRegistry = async () => {
    try {
      const res = await fetch(`${BASE_URL}/developer/capabilities`)
      if (res.ok) setRegistry(await res.json())
    } catch (e) {
      console.error('Failed to load capability map:', e)
    }
  }

  const fetchDiagnostic = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${BASE_URL}/developer/diagnostic`)
      if (res.ok) setDiagnostic(await res.json())
    } catch (e) {
      console.error('Failed to run diagnostics:', e)
    } finally {
      setLoading(false)
    }
  }

  const fetchMemory = async () => {
    try {
      const res = await fetch(`${BASE_URL}/developer/memory`)
      if (res.ok) setMemory(await res.json())
    } catch (e) {
      console.error('Failed to load developer memory:', e)
    }
  }

  const fetchApprovals = async () => {
    try {
      const res = await fetch(`${BASE_URL}/developer/approvals`)
      if (res.ok) setApprovals(await res.json())
    } catch (e) {
      console.error('Failed to load approvals:', e)
    }
  }

  useEffect(() => {
    fetchRegistry()
    fetchDiagnostic()
    fetchMemory()
    fetchApprovals()

    // Poll for approvals & diagnostics every 4 seconds
    const interval = setInterval(() => {
      fetchApprovals()
      fetchMemory()
    }, 4000)
    return () => clearInterval(interval)
  }, [])

  const handleApprove = async (approvalId: string) => {
    try {
      const res = await fetch(`${BASE_URL}/developer/approve/${approvalId}`, { method: 'POST' })
      const data = await res.json()
      alert(data.message)
      fetchApprovals()
    } catch (e) {
      alert(`Approval execution failed: ${e}`)
    }
  }

  const handleReject = async (approvalId: string) => {
    try {
      const res = await fetch(`${BASE_URL}/developer/reject/${approvalId}`, { method: 'POST' })
      const data = await res.json()
      alert(data.message)
      fetchApprovals()
    } catch (e) {
      alert(`Rejection execution failed: ${e}`)
    }
  }

  return (
    <div className="flex flex-col h-full w-full bg-slate-950/80 rounded-xl border border-cyan-500/20 shadow-2xl backdrop-blur-xl p-4 gap-4 select-none">
      {/* Portal Header */}
      <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Terminal className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h2 className="text-base font-extrabold tracking-widest text-cyan-100 uppercase">
              JARVIS Developer Hub & System Integrity Portal
            </h2>
            <p className="text-xs text-slate-400">
              Core capability registration status, self-repair logs, and Level 2/3 modification gateways
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {diagnostic && (
            <span
              className={`px-3 py-1 rounded font-mono font-bold text-xs border ${
                diagnostic.diagnostic_status === 'HEALTHY'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                  : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
              }`}
            >
              SYSTEM STATUS: {diagnostic.diagnostic_status}
            </span>
          )}

          <button
            onClick={fetchDiagnostic}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs transition-all disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>RUN DIAGNOSTIC</span>
          </button>
        </div>
      </div>

      {/* Sub Tabs */}
      <div className="flex gap-2 border-b border-slate-900 pb-2">
        {(['capabilities', 'diagnostics', 'approvals', 'memory'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveSubTab(tab)}
            className={`px-4 py-1.5 rounded-lg font-mono text-xs font-bold transition-all cursor-pointer ${
              activeSubTab === tab
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(0,229,255,0.2)]'
                : 'text-slate-400 hover:bg-slate-900 hover:text-slate-300'
            }`}
          >
            {tab.toUpperCase()} {tab === 'approvals' && Object.keys(approvals).length > 0 && (
              <span className="ml-1.5 px-1.5 py-0.2 rounded-full bg-rose-500 text-white font-bold text-[9px] animate-pulse">
                {Object.keys(approvals).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tabs Content */}
      <div className="flex-1 overflow-hidden min-h-0">
        
        {/* SUBTAB 1: CAPABILITY MAP */}
        {activeSubTab === 'capabilities' && (
          <div className="h-full overflow-y-auto pr-1 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 custom-scrollbar">
            {registry?.capabilities && Object.entries(registry.capabilities).map(([key, cap]) => (
              <div key={key} className="bg-slate-900/40 border border-slate-800 hover:border-cyan-500/30 rounded-xl p-3.5 flex flex-col gap-2.5 transition-all">
                <div className="flex justify-between items-start">
                  <span className="text-xs font-mono font-bold text-slate-100">{cap.name}</span>
                  <span className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold border ${
                    cap.status === 'IMPLEMENTED' 
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                  }`}>
                    {cap.status}
                  </span>
                </div>

                <p className="text-[11px] text-slate-400 font-mono leading-relaxed flex-1">
                  {cap.description}
                </p>

                <div className="text-[10px] font-mono border-t border-slate-900 pt-2 space-y-1">
                  <div>
                    <span className="text-slate-500 block">Implementation:</span>
                    {cap.implementation_files.map(f => (
                      <span key={f} className="text-cyan-400/90 block truncate">{f}</span>
                    ))}
                  </div>
                  <div>
                    <span className="text-slate-500 block">Dependencies:</span>
                    <span className="text-slate-300 block">{cap.dependencies.join(', ') || 'None'}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* SUBTAB 2: INTEGRITY DIAGNOSTIC */}
        {activeSubTab === 'diagnostics' && (
          <div className="h-full overflow-y-auto pr-1 space-y-4 custom-scrollbar">
            {diagnostic ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                
                {/* Metrics */}
                <div className="lg:col-span-1 bg-slate-900/40 border border-slate-800 rounded-xl p-4 space-y-3.5">
                  <h3 className="text-xs font-mono font-bold text-cyan-400 border-b border-slate-800 pb-2 flex items-center gap-1.5">
                    <Cpu className="w-4 h-4" /> HARDWARE & CORE LOAD
                  </h3>
                  <div className="space-y-2 text-xs font-mono">
                    <div className="flex justify-between">
                      <span className="text-slate-400">CPU Load</span>
                      <span className="text-slate-200 font-bold">{diagnostic.metrics.cpu_percent}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">RAM Load</span>
                      <span className="text-slate-200 font-bold">{diagnostic.metrics.ram_percent}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Disk Space</span>
                      <span className="text-slate-200 font-bold">{diagnostic.metrics.disk_percent}%</span>
                    </div>
                  </div>

                  <h3 className="text-xs font-mono font-bold text-cyan-400 border-b border-slate-800 pb-2 pt-2 flex items-center gap-1.5">
                    <Database className="w-4 h-4" /> INTEGRATED SERVICES
                  </h3>
                  <div className="space-y-2 text-xs font-mono">
                    <div className="flex justify-between">
                      <span className="text-slate-400">RAG SQL DB</span>
                      <span className="text-emerald-400 font-bold">{diagnostic.metrics.rag_database}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">ChromaDB store</span>
                      <span className="text-emerald-400 font-bold">{diagnostic.metrics.vector_memory}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Whisper STT</span>
                      <span className="text-emerald-400 font-bold">{diagnostic.metrics.speech_to_text_model}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Wake Word</span>
                      <span className="text-emerald-400 font-bold">{diagnostic.metrics.wake_word_model}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Camera Perception</span>
                      <span className="text-emerald-400 font-bold">{diagnostic.metrics.camera_perception}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Hand Gestures</span>
                      <span className="text-emerald-400 font-bold">{diagnostic.metrics.hand_gesture_control}</span>
                    </div>
                  </div>
                </div>

                {/* Recommendations */}
                <div className="lg:col-span-2 bg-slate-900/40 border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
                  <h3 className="text-xs font-mono font-bold text-cyan-400 border-b border-slate-800 pb-2 flex items-center gap-1.5">
                    <List className="w-4 h-4" /> ISSUES & CORRECTION TASKS
                  </h3>

                  {diagnostic.discovered_issues.length > 0 ? (
                    <div className="space-y-3 flex-1 overflow-y-auto custom-scrollbar">
                      {diagnostic.discovered_issues.map((issue, idx) => (
                        <div key={idx} className="p-3 bg-amber-500/10 border border-amber-500/20 text-amber-300 rounded-lg flex items-start gap-2.5 text-xs font-mono">
                          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                          <div>
                            <div className="font-bold">Detected Fault:</div>
                            <div className="text-[11px] text-amber-200/90 mt-0.5">{issue}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center flex-1 text-center p-8">
                      <CheckCircle className="w-12 h-12 text-emerald-400/80 mb-2 animate-bounce" />
                      <span className="text-xs font-mono text-emerald-400 font-bold uppercase tracking-wider">ALL SYSTEMS NOMINAL</span>
                      <span className="text-[10px] font-mono text-slate-500 mt-1">No integrity faults or degraded modules detected.</span>
                    </div>
                  )}

                  <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 mt-auto">
                    <span className="text-[10px] font-mono text-slate-500 block uppercase font-bold">AI Diagnostic Action Recommendation:</span>
                    <span className="text-xs font-mono text-slate-300 mt-1 block">
                      {diagnostic.recommendations[0] || 'Maintain system operational state.'}
                    </span>
                  </div>
                </div>

              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 font-mono">Run integrity checks to aggregate data.</div>
            )}
          </div>
        )}

        {/* SUBTAB 3: MODIFICATION GATEWAY */}
        {activeSubTab === 'approvals' && (
          <div className="h-full overflow-y-auto pr-1 space-y-4 custom-scrollbar">
            {Object.keys(approvals).length > 0 ? (
              Object.entries(approvals).map(([id, app]) => (
                <div key={id} className="bg-slate-900/60 border border-slate-850 rounded-xl p-4 space-y-3 flex flex-col">
                  <div className="flex justify-between items-start border-b border-slate-900 pb-2">
                    <div>
                      <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[9px] font-mono font-bold uppercase">
                        PENDING CORE MODIFICATION
                      </span>
                      <h4 className="text-xs font-mono font-bold text-slate-100 mt-1">Proposed File: {app.file_path}</h4>
                    </div>
                    
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleReject(id)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-slate-850 hover:bg-slate-800 border border-slate-750 text-slate-300 hover:text-rose-400 rounded-lg font-mono font-bold text-xs cursor-pointer transition-colors"
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>REJECT</span>
                      </button>
                      <button
                        onClick={() => handleApprove(id)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 rounded-lg font-mono font-bold text-xs cursor-pointer transition-colors shadow-[0_0_12px_rgba(16,185,129,0.3)]"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>APPROVE & MERGE</span>
                      </button>
                    </div>
                  </div>

                  <div className="text-xs font-mono bg-slate-950 p-2.5 rounded border border-slate-900 text-slate-400">
                    <strong className="text-cyan-400 block mb-1">Agent Action Motivation:</strong>
                    {app.description}
                  </div>

                  <div className="flex-1 overflow-hidden flex flex-col bg-slate-950 rounded border border-slate-900 max-h-80">
                    <div className="px-3 py-1 bg-slate-900/70 border-b border-slate-900 text-[10px] font-mono text-slate-500 uppercase font-bold flex justify-between">
                      <span>File Contents Preview</span>
                      <span>Action: {app.action_type}</span>
                    </div>
                    <pre className="p-3 overflow-auto text-[11px] font-mono text-slate-300 leading-tight flex-1 custom-scrollbar">
                      <code>{app.proposed_code}</code>
                    </pre>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center p-8 border border-dashed border-slate-900 rounded-xl">
                <Shield className="w-12 h-12 text-slate-700 mb-2" />
                <span className="text-xs font-mono text-slate-400 font-bold uppercase tracking-wider">GATEWAY SECURED</span>
                <span className="text-[10px] font-mono text-slate-600 mt-1">No pending Level 2 or Level 3 system modifications awaiting approval.</span>
              </div>
            )}
          </div>
        )}

        {/* SUBTAB 4: DEVELOPER HEALING MEMORY */}
        {activeSubTab === 'memory' && (
          <div className="h-full overflow-y-auto pr-1 grid grid-cols-3 gap-4 custom-scrollbar">
            
            {/* General Stats */}
            <div className="col-span-1 bg-slate-900/40 border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
              <h3 className="text-xs font-mono font-bold text-cyan-400 border-b border-slate-800 pb-2">
                HEALING INDEX METRICS
              </h3>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-900 flex flex-col items-center justify-center text-center">
                <span className="text-3xl font-extrabold text-cyan-400 font-mono">
                  {memory?.bugs_fixed ?? 0}
                </span>
                <span className="text-[10px] font-mono text-slate-400 uppercase mt-1">AUTOMATED REPAIRS MADE</span>
              </div>

              <div className="space-y-1 mt-2 text-xs font-mono">
                <span className="text-slate-500 block uppercase font-bold">Lessons Registry:</span>
                {memory?.lessons_learned && memory.lessons_learned.length > 0 ? (
                  memory.lessons_learned.map((lesson, i) => (
                    <div key={i} className="p-2 rounded bg-slate-950 border border-slate-900 text-slate-300">
                      • {lesson}
                    </div>
                  ))
                ) : (
                  <span className="text-slate-600 italic block p-1">[No healing logs indexed]</span>
                )}
              </div>
            </div>

            {/* Repair history */}
            <div className="col-span-2 bg-slate-900/40 border border-slate-800 rounded-xl p-4 flex flex-col gap-3">
              <h3 className="text-xs font-mono font-bold text-cyan-400 border-b border-slate-800 pb-2">
                REPAIR EXPERIENCE HISTORY
              </h3>

              <div className="space-y-2 flex-1 overflow-y-auto custom-scrollbar text-xs font-mono">
                {memory?.repair_history && memory.repair_history.length > 0 ? (
                  memory.repair_history.map((log, i) => (
                    <div key={i} className="p-3 bg-slate-950 rounded-lg border border-slate-900 flex flex-col gap-1.5">
                      <div className="flex justify-between font-bold">
                        <span className="text-slate-200 truncate max-w-sm">{log.file}</span>
                        <span className="text-emerald-400">RESOLVED</span>
                      </div>
                      <div className="text-slate-500 text-[11px]">
                        Fault Context: <span className="text-slate-400 font-normal">{log.error}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-slate-500 py-12">No repair events recorded.</div>
                )}
              </div>
            </div>

          </div>
        )}

      </div>
    </div>
  )
}
export default DeveloperDashboard
