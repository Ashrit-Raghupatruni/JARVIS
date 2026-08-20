import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useAppStore } from '../stores/appStore'
import TitleBar from './TitleBar'
import Orb from './Orb'
import VoiceWave from './VoiceWave'
import TranscriptView from './TranscriptView'
import ChatPanel from './ChatPanel'
import TaskProgress from './TaskProgress'
import CommandHistory from './CommandHistory'
import HardwareGauges from './HardwareGauges'
import LLMProvidersCard from './LLMProvidersCard'
import AgentOrchestratorCard from './AgentOrchestratorCard'
import ComputerUseCard from './ComputerUseCard'
import BrowserAutomationCard from './BrowserAutomationCard'
import KnowledgeHubCard from './KnowledgeHubCard'
import MCPServersCard from './MCPServersCard'
import CommandPalette from './CommandPalette'
import SettingsPanel from './SettingsPanel'
import VisualWorkflowBuilder from './VisualWorkflowBuilder'
import TaskQueueManager from './TaskQueueManager'
import LiveModeCard from './LiveModeCard'
import { DynamicContentPanel, SearchResultCard } from './DynamicContentPanel'
import { MobileCompanionCard } from './MobileCompanionCard'
import { LiveDebugInspector } from './LiveDebugInspector'
import { LivePerceptionVisualizer } from './LivePerceptionVisualizer'
import { AutonomousAgentStudio } from './AutonomousAgentStudio'
import { DeveloperDashboard } from './DeveloperDashboard'
import { ProactiveGuidanceCard } from './ProactiveGuidanceCard'
import { ConversationSidebar } from './ConversationSidebar'
import {
  Command,
  ChevronDown,
  Menu,
  MessageSquare,
  Sliders,
  Trash2,
  Zap,
  ListOrdered,
  Activity,
  Globe,
  Bot,
  LayoutGrid,
  Maximize2,
  X,
  Eye,
  Terminal,
  GripVertical,
  Cpu
} from 'lucide-react'

interface DashboardLayoutProps {
  onSendMessage: (text: string) => void
  onOrbClick: () => void
}

type NavTab = 'command' | 'agents' | 'history' | 'workflows' | 'queue' | 'telemetry' | 'live' | 'automation' | 'debug' | 'developer'

const NAV_ITEMS: { id: NavTab; label: string; icon: React.ReactNode }[] = [
  { id: 'command', label: 'Command Center', icon: <Bot className="w-4 h-4 text-cyan-400" /> },
  { id: 'agents', label: 'Agent Studio', icon: <Cpu className="w-4 h-4 text-cyan-400" /> },
  { id: 'history', label: 'Chat History', icon: <MessageSquare className="w-4 h-4 text-cyan-400" /> },
  { id: 'workflows', label: 'Workflow Studio', icon: <LayoutGrid className="w-4 h-4 text-cyan-400" /> },
  { id: 'queue', label: 'Task Queue', icon: <ListOrdered className="w-4 h-4 text-cyan-400" /> },
  { id: 'telemetry', label: 'Telemetry', icon: <Activity className="w-4 h-4 text-cyan-400" /> },
  { id: 'live', label: 'Live Mode', icon: <Eye className="w-4 h-4 text-cyan-400" /> },
  { id: 'automation', label: 'Automation', icon: <Globe className="w-4 h-4 text-cyan-400" /> },
  { id: 'developer', label: 'Developer Portal', icon: <Terminal className="w-4 h-4 text-cyan-400" /> },
  { id: 'debug', label: 'Debug Inspector', icon: <Terminal className="w-4 h-4 text-cyan-400" /> }
]

export default function DashboardLayout({ onSendMessage, onOrbClick }: DashboardLayoutProps) {
  const { assistantState, showSettings, toggleSettings, clearMessages, activeConversationId, setActiveConversationId, setMessages } = useAppStore()
  const [isPaletteOpen, setIsPaletteOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<NavTab>('command')
  const [isNavOpen, setIsNavOpen] = useState(false)

  const handleSelectConversation = useCallback(async (convId: string | number) => {
    setActiveConversationId(convId)
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/conversations/${convId}`)
      if (res.ok) {
        const data = await res.json()
        const conv = data.conversation || data
        if (conv && conv.messages) {
          const formatted = conv.messages.map((m: any) => ({
            id: String(m.id || Math.random()),
            role: m.role,
            content: m.content,
            timestamp: m.timestamp || new Date().toISOString()
          }))
          setMessages(formatted)
        }
      }
    } catch (e) {
      console.error('Failed to load conversation history:', e)
    }
  }, [setActiveConversationId, setMessages])

  const handleNewChat = useCallback(() => {
    setActiveConversationId(null)
    setMessages([])
  }, [setActiveConversationId, setMessages])

  // Resizable 70/30 panel split ratio (default 0.70, persisted in localStorage)
  const [splitRatio, setSplitRatio] = useState<number>(() => {
    const saved = localStorage.getItem('jarvis_split_ratio')
    return saved ? Math.min(0.8, Math.max(0.2, parseFloat(saved))) : 0.70
  })

  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Drag handler for panel resizing
  const handleMouseDown = useCallback(() => {
    setIsDragging(true)
  }, [])

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const offset = e.clientX - rect.left
      const newRatio = Math.min(0.85, Math.max(0.15, offset / rect.width))
      setSplitRatio(newRatio)
      localStorage.setItem('jarvis_split_ratio', newRatio.toString())
    },
    [isDragging]
  )

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
    } else {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  // Responsive compact view check
  const [isCompactView, setIsCompactView] = useState<boolean>(() => {
    return window.innerWidth < 900 || window.innerHeight < 600
  })

  useEffect(() => {
    const handleResize = () => {
      const isCompact = window.innerWidth < 900 || window.innerHeight < 600
      setIsCompactView(isCompact)
    }

    window.addEventListener('resize', handleResize)

    const api = (window as any).electronAPI
    if (api?.onWindowStateChanged) {
      const unsub = api.onWindowStateChanged((state: { isMaximized: boolean }) => {
        if (state.isMaximized) {
          setIsCompactView(false)
        } else {
          const isCompact = window.innerWidth < 900 || window.innerHeight < 600
          setIsCompactView(isCompact)
        }
      })
      return () => {
        window.removeEventListener('resize', handleResize)
        unsub()
      }
    }

    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const handlePaletteAction = (actionId: string) => {
    if (actionId === 'open_palette') {
      setIsPaletteOpen(true)
    } else if (actionId === 'inspect_screen') {
      onSendMessage('Inspect my screen and show active windows')
    } else if (actionId === 'run_benchmarks') {
      onSendMessage('Run system benchmarks')
    } else if (actionId === 'trigger_backup') {
      onSendMessage('Trigger local backup')
    }
  }

  const activeNavItem = NAV_ITEMS.find((item) => item.id === activeTab) || NAV_ITEMS[0]

  // ── COMPACT RESIZED MODE ────────────────────────────────────────────────
  if (isCompactView) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#050811] text-[#e1f5fe] relative overflow-hidden select-none">
        <div
          className="absolute top-0 left-0 right-0 h-9 z-50 flex items-center justify-between px-3 bg-slate-950/40 backdrop-blur-md border-b border-cyan-500/10"
          style={{ WebkitAppRegion: 'drag' } as any}
        >
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            <span className="text-[10px] font-mono font-bold tracking-widest text-cyan-300">
              JARVIS HUD
            </span>
          </div>

          <div className="flex items-center gap-1" style={{ WebkitAppRegion: 'no-drag' } as any}>
            <button
              onClick={() => (window as any).electronAPI?.maximize()}
              className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 transition-all cursor-pointer shadow-[0_0_8px_rgba(0,229,255,0.3)]"
            >
              <Maximize2 className="w-3 h-3" />
              <span>EXPAND</span>
            </button>
            <button
              onClick={() => (window as any).electronAPI?.close()}
              className="p-1 rounded text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 transition-all cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div className="relative z-10 flex flex-col items-center justify-center p-2">
          <Orb onOrbClick={onOrbClick} />
          <div className="mt-1 w-full max-w-[320px]">
            <VoiceWave />
          </div>
        </div>
      </div>
    )
  }

  // ── FULLSCREEN / MAXIMIZED DASHBOARD MODE ──────────────────────────────
  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden select-none relative bg-[#050811] text-[#e1f5fe]">
      {/* Background Radial Cyan Glow */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden z-0">
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: 'radial-gradient(circle at 1px 1px, #00e5ff 1px, transparent 0)',
            backgroundSize: '32px 32px'
          }}
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[850px] h-[850px] rounded-full opacity-15 blur-[160px] bg-[radial-gradient(circle,#00e5ff_0%,transparent_70%)]" />
      </div>

      {/* Top Title Bar */}
      <TitleBar />

      {/* OS Command Bar Header Dock */}
      <div className="relative z-30 px-4 py-2 bg-slate-950/80 border-b border-cyan-500/20 backdrop-blur-xl flex items-center justify-between gap-2 shadow-lg">
        {/* Consolidated Top Nav Dropdown Menu */}
        <div className="relative">
          <button
            onClick={() => setIsNavOpen((prev) => !prev)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-cyan-500/30 text-cyan-200 text-xs font-mono font-bold transition-all cursor-pointer shadow-[0_0_12px_rgba(0,229,255,0.2)]"
          >
            <Menu className="w-4 h-4 text-cyan-400" />
            <span>☰ {activeNavItem.label}</span>
            <ChevronDown className={`w-3.5 h-3.5 text-cyan-400 transition-transform duration-200 ${isNavOpen ? 'rotate-180' : ''}`} />
          </button>

          {/* Expanded Dropdown Menu items */}
          {isNavOpen && (
            <div className="absolute top-full left-0 mt-1.5 w-56 bg-slate-950/95 border border-cyan-500/40 rounded-xl shadow-[0_10px_30px_rgba(0,229,255,0.25)] backdrop-blur-2xl py-1.5 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    setActiveTab(item.id)
                    setIsNavOpen(false)
                  }}
                  className={`w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-mono text-left transition-colors cursor-pointer ${
                    activeTab === item.id
                      ? 'bg-cyan-500/20 text-cyan-300 font-bold border-l-2 border-cyan-400'
                      : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'
                  }`}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Global Right Action Tools */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const current = useAppStore.getState().seriousMode
              useAppStore.getState().setSeriousMode(!current)
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition-all cursor-pointer ${
              useAppStore((s) => s.seriousMode)
                ? 'bg-amber-500/20 border-amber-500/50 text-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.3)]'
                : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            <span>SERIOUS MODE</span>
          </button>

          <button
            onClick={() => setIsPaletteOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-xs font-mono transition-all cursor-pointer"
          >
            <Command className="w-3.5 h-3.5" />
            <span>Palette</span>
            <kbd className="text-[10px] bg-slate-950 px-1 py-0.2 rounded border border-slate-700 text-slate-300">Ctrl+K</kbd>
          </button>

          <button
            onClick={clearMessages}
            title="Clear Chat"
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-rose-400 transition-all cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
          </button>

          <button
            onClick={toggleSettings}
            title="Settings"
            className="p-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 transition-all cursor-pointer"
          >
            <Sliders className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main View Port */}
      <div className="flex-1 relative z-10 p-3 overflow-hidden">
        {/* VIEW 1: COMMAND CENTER (Default 70/30 Resizable Split) */}
        {activeTab === 'command' && (
          <div ref={containerRef} className="h-full flex items-stretch gap-0 relative overflow-hidden">
            {/* Left 3D Face / Orb Panel (Default ~70% width) */}
            <div
              style={{ width: `${splitRatio * 100}%` }}
              className="flex flex-col items-center justify-center p-4 rounded-xl border border-cyan-500/20 bg-slate-900/40 backdrop-blur-xl shadow-2xl relative overflow-hidden min-w-[250px]"
            >
              <Orb onOrbClick={onOrbClick} />
              <div className="mt-2 w-full max-w-[360px]">
                <VoiceWave />
              </div>
              <div className="w-full max-w-2xl mt-4 overflow-y-auto max-h-[340px] custom-scrollbar">
                <ProactiveGuidanceCard
                  item={{
                    guidance_type: 'active_project',
                    title: 'Proactive Check-In: JARVIS AI OS',
                    message: '[Morning Briefing] You have been working on JARVIS AI OS across the last 8 turns.',
                    action_suggestion: 'Run system integration tests'
                  }}
                  onActionClick={(suggestion) => onSendMessage(suggestion)}
                />
                <DynamicContentPanel />
              </div>
            </div>

            {/* Draggable Vertical Splitter Bar */}
            <div
              onMouseDown={handleMouseDown}
              className={`w-3 mx-1 flex items-center justify-center cursor-col-resize hover:bg-cyan-500/30 rounded transition-colors group ${
                isDragging ? 'bg-cyan-500/40' : 'bg-transparent'
              }`}
              title="Drag to resize panels"
            >
              <GripVertical className="w-3.5 h-3.5 text-cyan-400/60 group-hover:text-cyan-400" />
            </div>

            {/* Right Chat & Task Panel (Default ~30% width) */}
            <div
              style={{ width: `${(1 - splitRatio) * 100}%` }}
              className="flex flex-col h-full overflow-hidden gap-3 min-w-[250px]"
            >
              <div className="flex-1 min-h-0">
                <ChatPanel onSendMessage={onSendMessage} />
              </div>
              <div className="h-40">
                <TaskProgress />
              </div>
            </div>
          </div>
        )}

        {/* VIEW 2: AUTONOMOUS AGENT STUDIO */}
        {activeTab === 'agents' && <AutonomousAgentStudio />}

        {/* VIEW 3: CHAT HISTORY (Persistent Sidebar + Resumable Chat) */}
        {activeTab === 'history' && (
          <div className="h-full flex items-stretch gap-3 overflow-hidden rounded-xl border border-cyan-500/20 bg-slate-900/40 backdrop-blur-xl p-2">
            <ConversationSidebar
              activeId={activeConversationId}
              onSelectConversation={handleSelectConversation}
              onNewChat={handleNewChat}
            />
            <div className="flex-1 h-full min-w-0">
              <ChatPanel onSendMessage={onSendMessage} />
            </div>
          </div>
        )}

        {/* VIEW 3: VISUAL WORKFLOW STUDIO */}
        {activeTab === 'workflows' && <VisualWorkflowBuilder />}

        {/* VIEW 4: TASK QUEUE & SCHEDULER */}
        {activeTab === 'queue' && <TaskQueueManager />}

        {/* VIEW 5: LIVE MODE */}
        {activeTab === 'live' && (
          <div className="h-full overflow-y-auto space-y-4 custom-scrollbar">
            <LiveModeCard />
            <LivePerceptionVisualizer />
          </div>
        )}

        {/* VIEW 6: TELEMETRY & SYSTEM GAUGES */}
        {activeTab === 'telemetry' && (
          <div className="h-full overflow-y-auto space-y-3 custom-scrollbar">
            <MobileCompanionCard />
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div className="lg:col-span-2">
                <HardwareGauges />
              </div>
              <div>
                <LLMProvidersCard />
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <AgentOrchestratorCard />
              <MCPServersCard />
            </div>
          </div>
        )}

        {/* VIEW 7: DESKTOP & BROWSER AUTOMATION */}
        {activeTab === 'automation' && (
          <div className="h-full overflow-y-auto space-y-3 custom-scrollbar">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <ComputerUseCard />
              <BrowserAutomationCard />
            </div>
            <KnowledgeHubCard />
          </div>
        )}

        {/* VIEW 8: DEBUG INSPECTOR */}
        {activeTab === 'debug' && <LiveDebugInspector />}

        {/* VIEW 9: DEVELOPER PORTAL */}
        {activeTab === 'developer' && <DeveloperDashboard />}
      </div>

      {/* Global Command Palette Modal */}
      {isPaletteOpen && (
        <CommandPalette
          isOpen={isPaletteOpen}
          onClose={() => setIsPaletteOpen(false)}
          onSelectAction={handlePaletteAction}
        />
      )}

      {/* Global Settings Modal */}
      {showSettings && <SettingsPanel />}
    </div>
  )
}
