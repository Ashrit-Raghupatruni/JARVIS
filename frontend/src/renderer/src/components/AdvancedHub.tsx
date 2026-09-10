import React, { useState, Suspense, lazy } from 'react'
import {
  Cpu,
  Terminal,
  LayoutGrid,
  Activity,
  Layers,
  Share2,
  Bug,
  Sparkles
} from 'lucide-react'

// Lazy load heavy advanced components
const AutonomousAgentStudio = lazy(() =>
  import('./AutonomousAgentStudio').then((m) => ({ default: m.AutonomousAgentStudio }))
)
const DeveloperDashboard = lazy(() => import('./DeveloperDashboard'))
const VisualWorkflowBuilder = lazy(() => import('./VisualWorkflowBuilder'))
const HardwareGauges = lazy(() => import('./HardwareGauges'))
const LLMProvidersCard = lazy(() => import('./LLMProvidersCard'))
const AgentOrchestratorCard = lazy(() => import('./AgentOrchestratorCard'))
const MCPServersCard = lazy(() => import('./MCPServersCard'))
const MobileCompanionCard = lazy(() =>
  import('./MobileCompanionCard').then((m) => ({ default: m.MobileCompanionCard }))
)
const OAuthIntegrationsCard = lazy(() => import('./OAuthIntegrationsCard'))
const MemoryGraphCard = lazy(() => import('./MemoryGraphCard'))
const LiveDebugInspector = lazy(() =>
  import('./LiveDebugInspector').then((m) => ({ default: m.LiveDebugInspector }))
)

export type AdvancedSubTab =
  | 'agents'
  | 'developer'
  | 'workflows'
  | 'telemetry'
  | 'integrations'
  | 'memory_graph'
  | 'debug'

interface AdvancedSubItem {
  id: AdvancedSubTab
  label: string
  description: string
  icon: React.ReactNode
}

const ADVANCED_TABS: AdvancedSubItem[] = [
  {
    id: 'agents',
    label: 'Agent Studio',
    description: 'Multi-agent orchestration, IPC audit bus, and SQLite checkpointing',
    icon: <Cpu className="w-4 h-4 text-cyan-400" />
  },
  {
    id: 'developer',
    label: 'Developer Portal',
    description: 'Capability map, self-repair healing logs, and Level 2/3 gateways',
    icon: <Terminal className="w-4 h-4 text-cyan-400" />
  },
  {
    id: 'workflows',
    label: 'Workflow Studio',
    description: 'Visual drag-and-drop workflow macro builder and executor',
    icon: <LayoutGrid className="w-4 h-4 text-cyan-400" />
  },
  {
    id: 'telemetry',
    label: 'Telemetry & Gauges',
    description: 'Real-time CPU/RAM/VRAM hardware telemetry, LLM provider matrix & Mobile sync',
    icon: <Activity className="w-4 h-4 text-cyan-400" />
  },
  {
    id: 'integrations',
    label: 'MCP & Integrations',
    description: 'Model Context Protocol servers, OAuth integrations and BLE proximity',
    icon: <Share2 className="w-4 h-4 text-cyan-400" />
  },
  {
    id: 'memory_graph',
    label: 'Memory Graph',
    description: 'Entity relationship visualizer and persistent knowledge graph',
    icon: <Layers className="w-4 h-4 text-cyan-400" />
  },
  {
    id: 'debug',
    label: 'Debug Inspector',
    description: 'Live event stream, error traces, and low-level diagnostic logs',
    icon: <Bug className="w-4 h-4 text-cyan-400" />
  }
]

const LoadingFallback: React.FC<{ label: string }> = ({ label }) => (
  <div className="flex flex-col items-center justify-center h-64 rounded-xl border border-cyan-500/20 bg-slate-900/40 backdrop-blur-md p-8 text-center animate-pulse">
    <Sparkles className="w-8 h-8 text-cyan-400 mb-2 animate-spin" />
    <span className="text-xs font-mono text-cyan-300 font-bold tracking-wider uppercase">
      Loading {label}...
    </span>
    <span className="text-[10px] font-mono text-slate-500 mt-1">Initializing module on demand</span>
  </div>
)

export const AdvancedHub: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AdvancedSubTab>('agents')
  const currentTab = ADVANCED_TABS.find((t) => t.id === activeTab) || ADVANCED_TABS[0]

  return (
    <div className="h-full flex flex-col gap-3 overflow-hidden select-none">
      {/* Sub-Navigation Header Bar */}
      <div className="flex items-center justify-between p-2 rounded-xl bg-slate-950/80 border border-cyan-500/20 backdrop-blur-md overflow-x-auto custom-scrollbar shrink-0">
        <div className="flex items-center gap-1.5 min-w-max">
          {ADVANCED_TABS.map((tab) => {
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono transition-all cursor-pointer ${
                  isActive
                    ? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/40 shadow-[0_0_10px_rgba(0,229,255,0.2)]'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Main Sub-View Content */}
      <div className="flex-1 overflow-hidden min-h-0">
        <Suspense fallback={<LoadingFallback label={currentTab.label} />}>
          {activeTab === 'agents' && <AutonomousAgentStudio />}

          {activeTab === 'developer' && <DeveloperDashboard />}

          {activeTab === 'workflows' && <VisualWorkflowBuilder />}

          {activeTab === 'telemetry' && (
            <div className="h-full overflow-y-auto space-y-3 custom-scrollbar pr-1">
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

          {activeTab === 'integrations' && (
            <div className="h-full overflow-y-auto space-y-3 custom-scrollbar pr-1">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <MCPServersCard />
                <OAuthIntegrationsCard />
              </div>
            </div>
          )}

          {activeTab === 'memory_graph' && (
            <div className="h-full overflow-y-auto custom-scrollbar pr-1">
              <MemoryGraphCard />
            </div>
          )}

          {activeTab === 'debug' && <LiveDebugInspector />}
        </Suspense>
      </div>
    </div>
  )
}
export default AdvancedHub
