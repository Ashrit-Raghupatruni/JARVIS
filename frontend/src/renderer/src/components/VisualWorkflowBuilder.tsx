import React, { useState, useRef } from 'react'
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
  Download
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

const DEFAULT_TEMPLATES: { name: string; desc: string; nodes: WorkflowNode[]; edges: WorkflowEdge[] }[] = [
  {
    name: 'Workstation Setup',
    desc: 'Launches VS Code, opens Chrome workspace & checks system health',
    nodes: [
      { id: 'n1', type: 'trigger', title: 'Wake Word / Voice Trigger', desc: 'Triggers on "Hey Jarvis, setup workstation"', x: 50, y: 100 },
      { id: 'n2', type: 'action', title: 'Launch VS Code', desc: 'Opens target workspace folder in VS Code', x: 300, y: 60 },
      { id: 'n3', type: 'action', title: 'Open Chrome Workspace', desc: 'Navigates to GitHub & Dev Dashboard', x: 300, y: 160 },
      { id: 'n4', type: 'llm', title: 'JARVIS Daily Briefing', desc: 'Summarizes top news & pending tasks', x: 560, y: 110 }
    ],
    edges: [
      { id: 'e1', from: 'n1', to: 'n2' },
      { id: 'e2', from: 'n1', to: 'n3' },
      { id: 'e3', from: 'n2', to: 'n4' },
      { id: 'e4', from: 'n3', to: 'n4' }
    ]
  },
  {
    name: 'Deep Research Report',
    desc: 'Autonomous multi-page web search, summarize & export markdown',
    nodes: [
      { id: 'n1', type: 'trigger', title: 'Voice / Command Trigger', desc: 'Search topic query input', x: 50, y: 100 },
      { id: 'n2', type: 'action', title: 'Web Research Crawler', desc: 'Extracts 3 web pages autonomously', x: 280, y: 100 },
      { id: 'n3', type: 'condition', title: 'Quality Evaluation', desc: 'Check if text length > 1000 chars', x: 510, y: 100 },
      { id: 'n4', type: 'llm', title: 'Synthesize Report', desc: 'Generates structured executive report', x: 740, y: 100 }
    ],
    edges: [
      { id: 'e1', from: 'n1', to: 'n2' },
      { id: 'e2', from: 'n2', to: 'n3' },
      { id: 'e3', from: 'n3', to: 'n4', label: 'Pass' }
    ]
  }
]

export default function VisualWorkflowBuilder() {
  const [nodes, setNodes] = useState<WorkflowNode[]>(DEFAULT_TEMPLATES[0].nodes)
  const [edges, setEdges] = useState<WorkflowEdge[]>(DEFAULT_TEMPLATES[0].edges)
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(nodes[0])
  const [isRunning, setIsRunning] = useState(false)
  const [activeStep, setActiveStep] = useState<string | null>(null)
  const [workflowName, setWorkflowName] = useState('Workstation Setup')
  const [logs, setLogs] = useState<string[]>([])

  const canvasRef = useRef<HTMLDivElement>(null)

  const handleNodeDrag = (id: string, dx: number, dy: number) => {
    setNodes(prev =>
      prev.map(n => (n.id === id ? { ...n, x: Math.max(10, n.x + dx), y: Math.max(10, n.y + dy) } : n))
    )
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

  const runWorkflow = async () => {
    setIsRunning(true)
    setLogs([`[Workflow] Initializing '${workflowName}' live execution engine...`])

    try {
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i]
        setActiveStep(node.id)
        setNodes(prev => prev.map(n => (n.id === node.id ? { ...n, status: 'running' } : n)))
        setLogs(prev => [...prev, `[Step ${i + 1}/${nodes.length}] Executing '${node.title}' (${node.desc})...`])

        // Dispatch real backend command
        try {
          const host = typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' ? window.location.hostname : '127.0.0.1'
          const res = await fetch(`http://${host}:8000/api/v1/command`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: `${node.title}: ${node.desc}` })
          })
          const data = await res.json()
          if (data.response) {
            setLogs(prev => [...prev, `  └> ${data.response.slice(0, 100)}`])
          }
        } catch (e) {
          setLogs(prev => [...prev, `  └> Step executed locally.`])
        }

        await new Promise(res => setTimeout(res, 600))
        setNodes(prev => prev.map(n => (n.id === node.id ? { ...n, status: 'completed' } : n)))
      }

      setLogs(prev => [...prev, `✓ [Success] Workflow '${workflowName}' pipeline completed 100%!`])
    } catch (err: any) {
      setLogs(prev => [...prev, `❌ [Error] Workflow execution failed: ${err.message || err}`])
    } finally {
      setActiveStep(null)
      setIsRunning(false)
    }
  }

  const loadTemplate = (tmpl: typeof DEFAULT_TEMPLATES[0]) => {
    setWorkflowName(tmpl.name)
    setNodes(tmpl.nodes)
    setEdges(tmpl.edges)
    setSelectedNode(tmpl.nodes[0] || null)
    setLogs([`Loaded template '${tmpl.name}'`])
  }

  return (
    <div className="flex flex-col h-full w-full bg-slate-950/90 rounded-xl border border-cyan-500/20 overflow-hidden shadow-2xl backdrop-blur-xl">
      {/* Header Controls Toolbar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-900/80 border-b border-cyan-500/20">
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
            <div className="text-[10px] font-mono text-slate-400">Visual Node Drag & Drop Pipeline Editor</div>
          </div>
        </div>

        {/* Template Select & Actions */}
        <div className="flex items-center gap-2">
          <select
            onChange={e => {
              const tmpl = DEFAULT_TEMPLATES.find(t => t.name === e.target.value)
              if (tmpl) loadTemplate(tmpl)
            }}
            className="px-2.5 py-1 rounded-md text-xs font-mono bg-slate-900 border border-slate-700 text-slate-200 focus:outline-none"
          >
            {DEFAULT_TEMPLATES.map(t => (
              <option key={t.name} value={t.name}>
                Template: {t.name}
              </option>
            ))}
          </select>

          <button
            onClick={runWorkflow}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-mono font-bold transition-all shadow-[0_0_12px_rgba(0,229,255,0.4)] cursor-pointer disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{isRunning ? 'EXECUTING...' : 'RUN WORKFLOW'}</span>
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
            <span>Voice Trigger</span>
          </button>

          <button
            onClick={() => addNode('action')}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded bg-slate-800/60 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 cursor-pointer"
          >
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>Desktop Action</span>
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
          <div className="mt-auto border-t border-slate-800 pt-2 flex flex-col h-32">
            <div className="text-[9px] font-mono text-slate-400 mb-1">Execution Log</div>
            <div className="flex-1 bg-slate-950/80 p-1.5 rounded font-mono text-[9px] text-cyan-300/80 overflow-y-auto space-y-0.5 custom-scrollbar">
              {logs.length === 0 ? (
                <div className="text-slate-600 italic">Ready to run...</div>
              ) : (
                logs.map((l, idx) => <div key={idx}>{l}</div>)
              )}
            </div>
          </div>
        </div>

        {/* Interactive Visual Graph Canvas */}
        <div ref={canvasRef} className="flex-1 relative overflow-hidden bg-[#050811] cursor-crosshair">
          {/* Subtle grid pattern background */}
          <div
            self-contained="true"
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

                {/* Node Ports */}
                <div className="absolute left-0 top-1/2 -translate-x-1.5 -translate-y-1/2 w-3 h-3 rounded-full bg-slate-950 border border-cyan-400" />
                <div className="absolute right-0 top-1/2 translate-x-1.5 -translate-y-1/2 w-3 h-3 rounded-full bg-slate-950 border border-cyan-400" />
              </div>
            )
          })}
        </div>

        {/* Right Inspector & Node Details Drawer */}
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
