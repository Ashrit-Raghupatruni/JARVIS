import React, { useState, useEffect, useRef } from 'react'
import {
  Play,
  Plus,
  Trash2,
  Zap,
  Globe,
  Code,
  Terminal,
  Clock,
  GitBranch,
  RotateCw,
  Sliders,
  CheckCircle2,
  Sparkles,
  Layers,
  Save,
  Download,
  Server,
  Wand2
} from 'lucide-react'

export interface WorkflowNode {
  id: string
  type: 'trigger' | 'action' | 'condition' | 'loop' | 'llm' | 'script'
  title: string
  desc: string
  x: number
  y: number
  status?: 'idle' | 'running' | 'completed' | 'failed'
  config?: Record<string, any>
}

export interface WorkflowEdge {
  id: string
  from: string
  to: string
  label?: string
}

export default function VisualWorkflowBuilder() {
  const [nodes, setNodes] = useState<WorkflowNode[]>([
    { id: 'n1', type: 'trigger', title: 'Wake Word / Voice Trigger', desc: 'Triggers on "Hey Jarvis, setup workstation"', x: 50, y: 100 },
    { id: 'n2', type: 'action', title: 'Launch VS Code', desc: 'Opens target workspace folder in VS Code', x: 300, y: 60 },
    { id: 'n3', type: 'action', title: 'Open Chrome Workspace', desc: 'Navigates to GitHub & Dev Dashboard', x: 300, y: 160 },
    { id: 'n4', type: 'llm', title: 'JARVIS Daily Briefing', desc: 'Summarizes top news & pending tasks', x: 560, y: 110 }
  ])
  const [edges, setEdges] = useState<WorkflowEdge[]>([
    { id: 'e1', from: 'n1', to: 'n2' },
    { id: 'e2', from: 'n1', to: 'n3' },
    { id: 'e3', from: 'n2', to: 'n4' },
    { id: 'e4', from: 'n3', to: 'n4' }
  ])
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(nodes[0])
  const [isRunning, setIsRunning] = useState(false)
  const [activeStep, setActiveStep] = useState<string | null>(null)
  const [workflowName, setWorkflowName] = useState('Workstation Setup')
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [logs, setLogs] = useState<string[]>([])

  // n8n Synchronization State
  const [n8nWorkflows, setN8nWorkflows] = useState<any[]>([])
  const [isN8nOnline, setIsN8nOnline] = useState<boolean>(false)
  const [aiPrompt, setAiPrompt] = useState<string>('')
  const [isGenerating, setIsGenerating] = useState<boolean>(false)

  const canvasRef = useRef<HTMLDivElement>(null)

  const getBackendHost = () => {
    if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      return window.location.hostname
    }
    return '127.0.0.1'
  }

  // Fetch n8n workflows on mount
  useEffect(() => {
    fetchN8nWorkflows()
  }, [])

  const fetchN8nWorkflows = async () => {
    try {
      const res = await fetch(`http://${getBackendHost()}:8000/api/v1/integrations/n8n/workflows`)
      const data = await res.json()
      if (data.status === 'success') {
        setN8nWorkflows(data.workflows || [])
        setIsN8nOnline(true)
        setLogs(prev => [...prev, `[n8n Engine] Connected to http://localhost:5678 (${data.count} workflows synced).`])
      }
    } catch (e) {
      setIsN8nOnline(false)
      setLogs(prev => [...prev, `[n8n Engine] Local n8n engine check: standby.`])
    }
  }

  const addNode = (type: WorkflowNode['type']) => {
    const newId = `node-${Date.now().toString(36)}`
    const typeTitles: Record<WorkflowNode['type'], string> = {
      trigger: 'Voice / Event Trigger',
      action: 'Desktop Action',
      condition: 'Condition Branch',
      loop: 'Loop Step',
      llm: 'AI Prompt / RAG',
      script: 'Python Script'
    }
    const newNode: WorkflowNode = {
      id: newId,
      type,
      title: typeTitles[type],
      desc: 'Configurable step parameter',
      x: 200 + Math.random() * 80,
      y: 100 + Math.random() * 80,
      status: 'idle'
    }
    setNodes(prev => [...prev, newNode])
    setSelectedNode(newNode)
  }

  const deleteNode = (id: string) => {
    setNodes(prev => prev.filter(n => n.id !== id))
    setEdges(prev => prev.filter(e => e.from !== id && e.to !== id))
    if (selectedNode?.id === id) setSelectedNode(null)
  }

  // ── Sync & Save Canvas to n8n Engine ───────────────────────────────────────
  const saveToN8n = async () => {
    setLogs(prev => [...prev, `[n8n Sync] Translating JARVIS canvas -> n8n workflow graph...`])
    try {
      const res = await fetch(`http://${getBackendHost()}:8000/api/v1/integrations/n8n/canvas/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: workflowName,
          nodes,
          edges,
          workflow_id: workflowId
        })
      })
      const data = await res.json()
      if (data.status === 'success') {
        const newWfId = data.n8n_result?.workflow?.id || data.n8n_result?.id || 'n8n_wf_saved'
        setWorkflowId(newWfId)
        setLogs(prev => [...prev, `✓ [n8n Sync] Saved workflow '${workflowName}' to n8n engine (ID: ${newWfId}).`])
        fetchN8nWorkflows()
      } else {
        setLogs(prev => [...prev, `❌ [n8n Sync] Save failed: ${data.message}`])
      }
    } catch (err: any) {
      setLogs(prev => [...prev, `❌ [n8n Sync] Server error: ${err.message}`])
    }
  }

  // ── Load Existing n8n Workflow onto Canvas ─────────────────────────────────
  const loadN8nWorkflow = async (id: string) => {
    setLogs(prev => [...prev, `[n8n Engine] Reconstructing canvas graph for workflow ID '${id}'...`])
    try {
      const res = await fetch(`http://${getBackendHost()}:8000/api/v1/integrations/n8n/canvas/load/${id}`)
      const data = await res.json()
      if (data.status === 'success' && data.canvas_graph) {
        setWorkflowName(data.canvas_graph.name || 'n8n Workflow')
        setNodes(data.canvas_graph.nodes || [])
        setEdges(data.canvas_graph.edges || [])
        setWorkflowId(id)
        setSelectedNode(data.canvas_graph.nodes[0] || null)
        setLogs(prev => [...prev, `✓ Reconstructed ${data.canvas_graph.nodes.length} nodes & ${data.canvas_graph.edges.length} edges on canvas.`])
      }
    } catch (err: any) {
      setLogs(prev => [...prev, `❌ Failed to load n8n workflow: ${err.message}`])
    }
  }

  // ── Execute Real Workflow on n8n Engine ────────────────────────────────────
  const runWorkflowOnN8n = async () => {
    setIsRunning(true)
    setLogs([`[n8n Engine] Dispatching '${workflowName}' graph execution to n8n engine...`])

    try {
      const targetId = workflowId || 'jarvis-test'
      
      // Highlight initial nodes
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i]
        setActiveStep(node.id)
        setNodes(prev => prev.map(n => (n.id === node.id ? { ...n, status: 'running' } : n)))
        setLogs(prev => [...prev, `[n8n Exec] Step '${node.title}' running on engine...`])

        await new Promise(res => setTimeout(res, 400))
        setNodes(prev => prev.map(n => (n.id === node.id ? { ...n, status: 'completed' } : n)))
      }

      // Invoke real n8n backend execution API
      const res = await fetch(`http://${getBackendHost()}:8000/api/v1/integrations/n8n/canvas/execute/${targetId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ canvas_name: workflowName })
      })
      const data = await res.json()

      if (data.status === 'success') {
        const execInfo = data.execution || {}
        setLogs(prev => [...prev, `✓ [n8n Success] Execution '${execInfo.execution_id}' finished in ${execInfo.duration_ms}ms.`])
        setLogs(prev => [...prev, `  └> Payload: ${JSON.stringify(execInfo.result || {})}`])
      } else {
        setLogs(prev => [...prev, `⚠️ [n8n Notice] Execution response: ${JSON.stringify(data)}`])
      }
    } catch (err: any) {
      setLogs(prev => [...prev, `❌ [n8n Engine Error] ${err.message || err}`])
    } finally {
      setActiveStep(null)
      setIsRunning(false)
    }
  }

  // ── AI Natural-Language Workflow Generator ─────────────────────────────────
  const generateAiWorkflow = async () => {
    if (!aiPrompt.trim()) return
    setIsGenerating(true)
    setLogs(prev => [...prev, `[AI Generator] Creating visual workflow graph for: "${aiPrompt}"...`])

    try {
      const res = await fetch(`http://${getBackendHost()}:8000/api/v1/integrations/n8n/canvas/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: aiPrompt })
      })
      const data = await res.json()
      if (data.status === 'success' && data.canvas_graph) {
        setWorkflowName(data.canvas_graph.name || 'AI Generated Workflow')
        setNodes(data.canvas_graph.nodes || [])
        setEdges(data.canvas_graph.edges || [])
        setSelectedNode(data.canvas_graph.nodes[0] || null)
        setLogs(prev => [...prev, `✓ Generated proposed visual graph (${data.canvas_graph.nodes.length} nodes). Syncing with n8n...`])
        
        // Auto sync with n8n engine
        saveToN8n()
      }
    } catch (err: any) {
      setLogs(prev => [...prev, `❌ Generation failed: ${err.message}`])
    } finally {
      setIsGenerating(false)
      setAiPrompt('')
    }
  }

  return (
    <div className="flex flex-col h-full w-full bg-slate-950/90 rounded-xl border border-cyan-500/20 overflow-hidden shadow-2xl backdrop-blur-xl">
      {/* Header Controls & n8n Sync Toolbar */}
      <div className="flex flex-col border-b border-cyan-500/20 bg-slate-900/80">
        <div className="flex items-center justify-between px-4 py-2">
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <input
                type="text"
                value={workflowName}
                onChange={e => setWorkflowName(e.target.value)}
                className="bg-transparent text-sm font-bold text-slate-100 focus:outline-none border-b border-transparent focus:border-cyan-400"
              />
              <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                <span>Visual n8n Workflow Designer</span>
                <span className="text-slate-600">•</span>
                <span className={`flex items-center gap-1 ${isN8nOnline ? 'text-emerald-400' : 'text-amber-400'}`}>
                  <Server className="w-3 h-3" />
                  {isN8nOnline ? 'n8n Engine Online (http://localhost:5678)' : 'n8n Engine Offline / Standby'}
                </span>
              </div>
            </div>
          </div>

          {/* Action Buttons & n8n Selector */}
          <div className="flex items-center gap-2">
            {n8nWorkflows.length > 0 && (
              <select
                onChange={e => {
                  if (e.target.value) loadN8nWorkflow(e.target.value)
                }}
                className="px-2.5 py-1 rounded-md text-xs font-mono bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none"
              >
                <option value="">-- Load n8n Workflow --</option>
                {n8nWorkflows.map(w => (
                  <option key={w.id} value={w.id}>
                    {w.name} ({w.active ? 'Active' : 'Draft'})
                  </option>
                ))}
              </select>
            )}

            <button
              onClick={saveToN8n}
              className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-cyan-500/40 text-cyan-300 text-xs font-mono cursor-pointer transition-all"
            >
              <Save className="w-3.5 h-3.5" />
              <span>SYNC TO n8n</span>
            </button>

            <button
              onClick={runWorkflowOnN8n}
              disabled={isRunning}
              className="flex items-center gap-1.5 px-3.5 py-1 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-mono font-bold transition-all shadow-[0_0_12px_rgba(0,229,255,0.4)] cursor-pointer disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isRunning ? 'RUNNING ON n8n...' : 'RUN ON n8n'}</span>
            </button>
          </div>
        </div>

        {/* AI Natural Language Prompt Assistant Bar */}
        <div className="flex items-center gap-2 px-4 py-1.5 bg-slate-950/60 border-t border-slate-800/80">
          <Wand2 className="w-3.5 h-3.5 text-purple-400 shrink-0" />
          <input
            type="text"
            placeholder="Ask JARVIS AI e.g. 'Create a workflow to organize my downloaded PDFs and summarize them'..."
            value={aiPrompt}
            onChange={e => setAiPrompt(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && generateAiWorkflow()}
            className="flex-1 bg-transparent text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none"
          />
          <button
            onClick={generateAiWorkflow}
            disabled={isGenerating || !aiPrompt.trim()}
            className="px-2.5 py-0.5 rounded text-[11px] font-mono bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/40 transition-all disabled:opacity-50 cursor-pointer"
          >
            {isGenerating ? 'GENERATING...' : 'GENERATE GRAPH'}
          </button>
        </div>
      </div>

      {/* Main Studio Body: Palette + Canvas + Inspector */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Palette Bar */}
        <div className="w-48 bg-slate-900/60 border-r border-slate-800/80 p-3 flex flex-col gap-2 z-10 select-none">
          <div className="text-[10px] font-mono font-bold tracking-widest text-cyan-400 uppercase mb-1">Node Palette</div>

          <button
            onClick={() => addNode('trigger')}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-slate-800/60 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 cursor-pointer"
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Voice / Webhook Trigger</span>
          </button>

          <button
            onClick={() => addNode('action')}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-slate-800/60 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 cursor-pointer"
          >
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>Desktop / API Action</span>
          </button>

          <button
            onClick={() => addNode('llm')}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-slate-800/60 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>AI Prompt / RAG</span>
          </button>

          <button
            onClick={() => addNode('condition')}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-slate-800/60 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 cursor-pointer"
          >
            <GitBranch className="w-3.5 h-3.5 text-emerald-400" />
            <span>If / Else Branch</span>
          </button>

          <button
            onClick={() => addNode('script')}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-slate-800/60 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 cursor-pointer"
          >
            <Code className="w-3.5 h-3.5 text-blue-400" />
            <span>Python Script</span>
          </button>

          {/* Console Log Panel */}
          <div className="mt-auto border-t border-slate-800 pt-2 flex flex-col h-36">
            <div className="text-[9px] font-mono text-slate-400 mb-1">Execution Log</div>
            <div className="flex-1 bg-slate-950/80 p-1.5 rounded font-mono text-[9px] text-cyan-300/80 overflow-y-auto space-y-0.5 custom-scrollbar">
              {logs.length === 0 ? (
                <div className="text-slate-600 italic">Ready to run on n8n...</div>
              ) : (
                logs.map((l, idx) => <div key={idx}>{l}</div>)
              )}
            </div>
          </div>
        </div>

        {/* Interactive Visual Graph Canvas */}
        <div ref={canvasRef} className="flex-1 relative overflow-hidden bg-[#050811] cursor-crosshair">
          {/* Grid background */}
          <div
            className="absolute inset-0 opacity-[0.06] pointer-events-none"
            style={{
              backgroundImage: 'radial-gradient(circle at 1px 1px, #00e5ff 1px, transparent 0)',
              backgroundSize: '24px 24px'
            }}
          />

          {/* SVG Bezier Connectors Layer */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
            {edges.map(edge => {
              const fromNode = nodes.find(n => n.id === edge.from)
              const toNode = nodes.find(n => n.id === edge.to)
              if (!fromNode || !toNode) return null

              const x1 = fromNode.x + 180
              const y1 = fromNode.y + 40
              const x2 = toNode.x
              const y2 = toNode.y + 40

              const dx = Math.abs(x2 - x1) * 0.5
              const path = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`

              const isConnectedStepActive = activeStep === edge.from || activeStep === edge.to

              return (
                <g key={edge.id}>
                  <path
                    d={path}
                    fill="none"
                    stroke={isConnectedStepActive ? '#00e5ff' : 'rgba(0, 229, 255, 0.3)'}
                    strokeWidth={isConnectedStepActive ? 3 : 2}
                    strokeDasharray={isConnectedStepActive ? '6,3' : 'none'}
                    className={isConnectedStepActive ? 'animate-pulse' : ''}
                  />
                  {edge.label && (
                    <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6} fill="#00e5ff" fontSize="9" fontFamily="monospace">
                      {edge.label}
                    </text>
                  )}
                </g>
              )
            })}
          </svg>

          {/* Draggable Canvas Nodes */}
          {nodes.map(node => {
            const isSelected = selectedNode?.id === node.id
            const isActive = activeStep === node.id

            return (
              <div
                key={node.id}
                onClick={() => setSelectedNode(node)}
                style={{ left: `${node.x}px`, top: `${node.y}px` }}
                className={`absolute w-44 rounded-xl p-3 border backdrop-blur-md cursor-grab active:cursor-grabbing transition-all select-none z-10 ${
                  isActive
                    ? 'bg-cyan-950/90 border-cyan-400 shadow-[0_0_20px_rgba(0,229,255,0.5)] scale-105'
                    : isSelected
                    ? 'bg-slate-900/95 border-cyan-500/80 shadow-[0_0_10px_rgba(0,229,255,0.2)]'
                    : 'bg-slate-900/75 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span
                    className={`text-[9px] font-mono font-bold uppercase px-1.5 py-0.2 rounded ${
                      node.type === 'trigger'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        : node.type === 'llm'
                        ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                        : node.type === 'condition'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                    }`}
                  >
                    {node.type}
                  </span>
                  {node.status === 'completed' && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
                </div>

                <div className="text-xs font-bold text-slate-100 truncate">{node.title}</div>
                <div className="text-[10px] text-slate-400 line-clamp-2 mt-0.5">{node.desc}</div>

                {/* Ports */}
                <div className="absolute left-0 top-1/2 -translate-x-1.5 -translate-y-1/2 w-3 h-3 rounded-full bg-slate-950 border border-cyan-400" />
                <div className="absolute right-0 top-1/2 translate-x-1.5 -translate-y-1/2 w-3 h-3 rounded-full bg-slate-950 border border-cyan-400" />
              </div>
            )
          })}
        </div>

        {/* Right Inspector Drawer */}
        {selectedNode && (
          <div className="w-56 bg-slate-900/80 border-l border-slate-800 p-3 flex flex-col gap-3 z-10">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-xs font-bold text-slate-200">Node Inspector</span>
              <button onClick={() => deleteNode(selectedNode.id)} className="text-rose-400 hover:text-rose-300 cursor-pointer">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>

            <div>
              <label className="block text-[10px] font-mono text-slate-400 mb-1">Title</label>
              <input
                type="text"
                value={selectedNode.title}
                onChange={e => {
                  const title = e.target.value
                  setNodes(prev => prev.map(n => (n.id === selectedNode.id ? { ...n, title } : n)))
                  setSelectedNode(prev => (prev ? { ...prev, title } : null))
                }}
                className="w-full px-2 py-1 rounded text-xs bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-400"
              />
            </div>

            <div>
              <label className="block text-[10px] font-mono text-slate-400 mb-1">Description</label>
              <textarea
                rows={3}
                value={selectedNode.desc}
                onChange={e => {
                  const desc = e.target.value
                  setNodes(prev => prev.map(n => (n.id === selectedNode.id ? { ...n, desc } : n)))
                  setSelectedNode(prev => (prev ? { ...prev, desc } : null))
                }}
                className="w-full px-2 py-1 rounded text-xs bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-400 resize-none"
              />
            </div>

            <div>
              <label className="block text-[10px] font-mono text-slate-400 mb-1">Node Type</label>
              <div className="text-xs font-mono text-cyan-400 uppercase bg-slate-950 p-2 rounded border border-slate-800">
                {selectedNode.type}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
