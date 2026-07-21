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
import WorkflowManagerCard from './WorkflowManagerCard'
import MemoryGraphCard from './MemoryGraphCard'
import KnowledgeHubCard from './KnowledgeHubCard'
import MCPServersCard from './MCPServersCard'
import CommandPalette from './CommandPalette'
import SettingsPanel from './SettingsPanel'
import { Command, Mic, RefreshCw, Shield, Sliders, Play, Trash2, Power } from 'lucide-react'

interface DashboardLayoutProps {
  onSendMessage: (text: string) => void
  onOrbClick: () => void
}

export default function DashboardLayout({ onSendMessage, onOrbClick }: DashboardLayoutProps) {
  const { assistantState, showSettings, toggleSettings, clearMessages } = useAppStore()
  const [isPaletteOpen, setIsPaletteOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'all' | 'chat' | 'telemetry' | 'tools'>('all')

  const handlePaletteAction = (actionId: string) => {
    if (actionId === 'open_palette') {
      setIsPaletteOpen(true)
    } else if (actionId === 'inspect_screen') {
      onSendMessage('Inspect my screen and show the active window hierarchy')
    } else if (actionId === 'run_benchmarks') {
      onSendMessage('Run system benchmarks')
    } else if (actionId === 'trigger_backup') {
      onSendMessage('Trigger local backup')
    } else if (actionId === 'check_status') {
      onSendMessage('Show system status')
    } else if (actionId === 'discover_mcp') {
      onSendMessage('Discover MCP tools')
    }
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden select-none relative bg-[#070b13] text-[#e1f5fe]">
      {/* Animated background grid & radial glow */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden z-0">
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage: 'radial-gradient(circle at 1px 1px, #00e5ff 1px, transparent 0)',
            backgroundSize: '32px 32px',
          }}
        />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full opacity-20 blur-[140px] bg-[radial-gradient(circle,#00e5ff_0%,transparent_70%)]" />
      </div>

      {/* Top Title Bar */}
      <TitleBar />

      {/* Docked Control & Quick Actions Header */}
      <div className="relative z-20 px-4 py-2 bg-[rgba(10,20,38,0.8)] border-b border-[rgba(0,229,255,0.15)] backdrop-blur-lg flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {/* View Filter Pills */}
          <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-2.5 py-1 rounded-md text-xs font-mono font-semibold transition-all ${
                activeTab === 'all'
                  ? 'bg-[#00e5ff] text-slate-950 shadow-[0_0_10px_rgba(0,229,255,0.4)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Unified View
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-2.5 py-1 rounded-md text-xs font-mono font-semibold transition-all ${
                activeTab === 'chat'
                  ? 'bg-[#00e5ff] text-slate-950 shadow-[0_0_10px_rgba(0,229,255,0.4)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Chat Focus
            </button>
            <button
              onClick={() => setActiveTab('telemetry')}
              className={`px-2.5 py-1 rounded-md text-xs font-mono font-semibold transition-all ${
                activeTab === 'telemetry'
                  ? 'bg-[#00e5ff] text-slate-950 shadow-[0_0_10px_rgba(0,229,255,0.4)]'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Telemetry
            </button>
          </div>
        </div>

        {/* Quick Action Dock Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPaletteOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.2 rounded-lg bg-[rgba(0,229,255,0.12)] hover:bg-[rgba(0,229,255,0.25)] border border-[rgba(0,229,255,0.35)] text-[#00e5ff] text-xs font-mono transition-all shadow-[0_0_10px_rgba(0,229,255,0.15)]"
          >
            <Command className="w-3.5 h-3.5" />
            <span>Command Palette</span>
            <kbd className="text-[10px] bg-slate-950/60 px-1 py-0.2 rounded border border-slate-700 text-slate-300">Ctrl+K</kbd>
          </button>

          <button
            onClick={() => onSendMessage('Run system benchmarks')}
            title="Run System Benchmarks"
            className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-[#00e5ff] transition-all"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          <button
            onClick={() => onSendMessage('Trigger local backup')}
            title="Create Local ZIP Backup"
            className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-[#00e676] transition-all"
          >
            <Shield className="w-4 h-4" />
          </button>

          <button
            onClick={clearMessages}
            title="Clear Conversation History"
            className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-red-400 transition-all"
          >
            <Trash2 className="w-4 h-4" />
          </button>

          <button
            onClick={toggleSettings}
            title="Toggle Settings Drawer"
            className="p-1.5 rounded-lg bg-[rgba(0,229,255,0.1)] hover:bg-[rgba(0,229,255,0.2)] border border-[rgba(0,229,255,0.3)] text-[#00e5ff] transition-all"
          >
            <Sliders className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Single-Page Unified Dashboard Content */}
      <div className="flex-1 relative z-10 p-3 overflow-y-auto overflow-x-hidden space-y-3 custom-scrollbar">
        
        {/* TELEMETRY OR UNIFIED VIEW DECK */}
        {(activeTab === 'all' || activeTab === 'telemetry') && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
            <div className="lg:col-span-2">
              <HardwareGauges />
            </div>
            <div>
              <LLMProvidersCard />
            </div>
            <div>
              <MCPServersCard />
            </div>
          </div>
        )}

        {/* CHAT FOCUS MODE VIEW */}
        {activeTab === 'chat' ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 h-[calc(100vh-140px)]">
            <div className="lg:col-span-7 h-full">
              <ChatPanel onSendMessage={(text) => onSendMessage(text)} />
            </div>
            <div className="lg:col-span-5 flex flex-col items-center justify-between p-6 rounded-xl bg-[rgba(10,20,38,0.5)] border border-[rgba(0,229,255,0.2)] backdrop-blur-md relative overflow-hidden h-full">
              <div className="w-full mb-2">
                <TranscriptView />
              </div>
              <div className="my-auto flex flex-col items-center">
                <Orb onOrbClick={onOrbClick} />
                <div className="mt-6">
                  <VoiceWave />
                </div>
              </div>
              <div className="w-full pt-3 border-t border-[rgba(0,229,255,0.15)] flex items-center justify-between text-xs font-mono">
                <span className="text-[#b0bec5]">Assistant State: <strong className="text-[#00e5ff] uppercase">{assistantState}</strong></span>
                <span className="text-slate-400"><kbd className="bg-slate-800 text-slate-200 px-1 py-0.5 rounded border border-slate-700">Ctrl+Space</kbd> to Speak</span>
              </div>
            </div>
          </div>
        ) : (
          /* UNIFIED OR TELEMETRY 3-COLUMN GRID */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-[580px]">
            {/* Left Wing */}
            <div className="lg:col-span-4 flex flex-col gap-3">
              {activeTab === 'all' && (
                <div className="h-[380px]">
                  <ChatPanel onSendMessage={(text) => onSendMessage(text)} />
                </div>
              )}
              <ComputerUseCard />
              {activeTab === 'all' && <BrowserAutomationCard />}
              {activeTab === 'all' && <WorkflowManagerCard />}
            </div>

            {/* Center Hero Unit */}
            <div className="lg:col-span-4 flex flex-col items-center justify-between p-4 rounded-xl bg-[rgba(10,20,38,0.5)] border border-[rgba(0,229,255,0.15)] backdrop-blur-md relative overflow-hidden">
              <div className="w-full mb-2">
                <TranscriptView />
              </div>
              <div className="my-auto py-4 flex flex-col items-center">
                <Orb onOrbClick={onOrbClick} />
                <div className="mt-4">
                  <VoiceWave />
                </div>
              </div>
              <div className="w-full pt-3 border-t border-[rgba(0,229,255,0.1)] flex items-center justify-between text-xs font-mono">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#00e5ff] animate-ping" />
                  <span className="text-[#b0bec5]">State: <strong className="text-[#00e5ff] uppercase">{assistantState}</strong></span>
                </div>
                <span className="text-slate-400"><kbd className="bg-slate-800 text-slate-200 px-1 py-0.5 rounded border border-slate-700">Ctrl+Space</kbd></span>
              </div>
            </div>

            {/* Right Wing */}
            <div className="lg:col-span-4 flex flex-col gap-3">
              <TaskProgress />
              {activeTab === 'all' && <AgentOrchestratorCard />}
              {activeTab === 'all' && <MemoryGraphCard />}
              {activeTab === 'all' && <KnowledgeHubCard />}
            </div>
          </div>
        )}

        {/* Command History Drawer */}
        {activeTab === 'all' && <CommandHistory />}
      </div>


      {/* Floating Command Palette Modal */}
      <CommandPalette
        isOpen={isPaletteOpen}
        onClose={() => setIsPaletteOpen(false)}
        onSelectAction={handlePaletteAction}
      />

      {/* Slide-out Settings Panel */}
      {showSettings && <SettingsPanel />}
    </div>
  )
}
