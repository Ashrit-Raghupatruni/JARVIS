import React, { useState } from 'react'
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
import {
  Command,
  Mic,
  RefreshCw,
  Shield,
  Sliders,
  Play,
  Trash2,
  Power,
  Zap,
  ListOrdered,
  Activity,
  Globe,
  SlidersHorizontal,
  Bot,
  LayoutGrid,
  X
} from 'lucide-react'

interface DashboardLayoutProps {
  onSendMessage: (text: string) => void
  onOrbClick: () => void
}

export default function DashboardLayout({ onSendMessage, onOrbClick }: DashboardLayoutProps) {
  const { assistantState, showSettings, toggleSettings, clearMessages } = useAppStore()
  const [isPaletteOpen, setIsPaletteOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'command' | 'workflows' | 'queue' | 'telemetry' | 'automation'>('command')

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

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden select-none relative bg-[#050811] text-[#e1f5fe]">
      {/* Background radial atmosphere */}
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
      <div className="relative z-20 px-4 py-2 bg-slate-950/80 border-b border-cyan-500/20 backdrop-blur-xl flex items-center justify-between gap-2 shadow-lg">
        {/* Navigation Mode Selector Tabs */}
        <div className="flex items-center gap-1.5 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('command')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
              activeTab === 'command'
                ? 'bg-cyan-500 text-slate-950 shadow-[0_0_12px_rgba(0,229,255,0.4)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Bot className="w-3.5 h-3.5" />
            <span>Command Center</span>
          </button>

          <button
            onClick={() => setActiveTab('workflows')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
              activeTab === 'workflows'
                ? 'bg-cyan-500 text-slate-950 shadow-[0_0_12px_rgba(0,229,255,0.4)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Workflow Studio</span>
          </button>

          <button
            onClick={() => setActiveTab('queue')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
              activeTab === 'queue'
                ? 'bg-cyan-500 text-slate-950 shadow-[0_0_12px_rgba(0,229,255,0.4)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ListOrdered className="w-3.5 h-3.5 text-cyan-300" />
            <span>Task Queue</span>
          </button>

          <button
            onClick={() => setActiveTab('telemetry')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
              activeTab === 'telemetry'
                ? 'bg-cyan-500 text-slate-950 shadow-[0_0_12px_rgba(0,229,255,0.4)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span>Telemetry</span>
          </button>

          <button
            onClick={() => setActiveTab('automation')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer ${
              activeTab === 'automation'
                ? 'bg-cyan-500 text-slate-950 shadow-[0_0_12px_rgba(0,229,255,0.4)]'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Globe className="w-3.5 h-3.5 text-purple-400" />
            <span>Automation</span>
          </button>
        </div>

        {/* Header Right Action Dock */}
        <div className="flex items-center gap-2">
          {/* Voice State Badge */}
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg border border-cyan-500/30 bg-slate-900/80 text-[11px] font-mono font-bold uppercase transition-all shadow-sm">
            <span
              className={`w-2 h-2 rounded-full ${
                assistantState === 'listening'
                  ? 'bg-cyan-400 animate-ping'
                  : assistantState === 'speaking'
                  ? 'bg-purple-400 animate-ping'
                  : assistantState === 'processing'
                  ? 'bg-amber-400 animate-pulse'
                  : assistantState === 'interrupted'
                  ? 'bg-orange-400 animate-ping'
                  : assistantState === 'error'
                  ? 'bg-rose-500 animate-ping'
                  : 'bg-slate-500'
              }`}
            />
            <span className="text-slate-200">{assistantState}</span>
          </div>

          {/* Serious Mode Quick Toggle */}
          <button
            onClick={() => {
              const cur = Boolean(useAppStore.getState().settings?.voice?.seriousMode)
              useAppStore.getState().updateVoiceSettings({ seriousMode: !cur })
            }}
            title="Toggle Serious Mode"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all border cursor-pointer ${
              useAppStore((s) => s.settings?.voice?.seriousMode)
                ? 'bg-rose-950/80 border-rose-500 text-rose-200 shadow-[0_0_12px_rgba(255,0,51,0.5)] animate-pulse'
                : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Shield className="w-3.5 h-3.5" />
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
        {/* VIEW 1: COMMAND CENTER (Clean Hero Orb + Live Workspace) */}
        {activeTab === 'command' && (
          <div className="h-full grid grid-cols-1 lg:grid-cols-12 gap-3 items-stretch">
            {/* Left AI Central Hero Orb Visualizer */}
            <div className="lg:col-span-5 flex flex-col items-center justify-center p-4 rounded-xl border border-cyan-500/20 bg-slate-900/40 backdrop-blur-xl shadow-2xl relative overflow-hidden">
              <Orb onOrbClick={onOrbClick} />
              <div className="mt-2 w-full max-w-[360px]">
                <VoiceWave />
              </div>
            </div>

            {/* Right Live Conversational Workspace */}
            <div className="lg:col-span-7 flex flex-col h-full overflow-hidden gap-3">
              <div className="flex-1 min-h-0">
                <ChatPanel onSendMessage={onSendMessage} />
              </div>
              <div className="h-44">
                <TaskProgress />
              </div>
            </div>
          </div>
        )}

        {/* VIEW 2: VISUAL WORKFLOW STUDIO */}
        {activeTab === 'workflows' && <VisualWorkflowBuilder />}

        {/* VIEW 3: TASK QUEUE & SCHEDULER */}
        {activeTab === 'queue' && <TaskQueueManager />}

        {/* VIEW 4: TELEMETRY & SYSTEM GAUGES */}
        {activeTab === 'telemetry' && (
          <div className="h-full overflow-y-auto space-y-3 custom-scrollbar">
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

        {/* VIEW 5: DESKTOP & BROWSER AUTOMATION */}
        {activeTab === 'automation' && (
          <div className="h-full overflow-y-auto space-y-3 custom-scrollbar">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <ComputerUseCard />
              <BrowserAutomationCard />
            </div>
            <KnowledgeHubCard />
          </div>
        )}
      </div>

      {/* Floating Modals & Drawers */}
      <CommandPalette isOpen={isPaletteOpen} onClose={() => setIsPaletteOpen(false)} onSelectAction={handlePaletteAction} />
      <SettingsPanel isOpen={showSettings} onClose={toggleSettings} />
    </div>
  )
}
