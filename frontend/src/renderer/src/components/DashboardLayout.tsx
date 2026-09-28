import React, { useState, useEffect, Suspense, lazy } from 'react'
import { useAppStore } from '../stores/appStore'
import TitleBar from './TitleBar'
import { JarvisCoreOrb } from './JarvisCoreOrb'
import { TelemetryGaugesCard } from './TelemetryGaugesCard'
import { QuickActionsCard } from './QuickActionsCard'
import { FloatingCommandBar } from './FloatingCommandBar'
import {
  LayoutDashboard,
  MessageSquare,
  Mic,
  CheckSquare,
  Monitor,
  Folder,
  Cpu,
  Activity,
  Settings as SettingsIcon,
  Sparkles,
  Command,
  Trash2
} from 'lucide-react'

// Lazy load tab views for optimal performance
const ChatPanel = lazy(() => import('./ChatPanel'))
const ConversationSidebar = lazy(() =>
  import('./ConversationSidebar').then((m) => ({ default: m.ConversationSidebar }))
)
const TaskQueueManager = lazy(() => import('./TaskQueueManager'))
const TaskProgress = lazy(() => import('./TaskProgress'))
const LiveModeCard = lazy(() => import('./LiveModeCard'))
const LivePerceptionVisualizer = lazy(() =>
  import('./LivePerceptionVisualizer').then((m) => ({ default: m.LivePerceptionVisualizer }))
)
const ComputerUseCard = lazy(() => import('./ComputerUseCard'))
const BrowserAutomationCard = lazy(() => import('./BrowserAutomationCard'))
const KnowledgeHubCard = lazy(() => import('./KnowledgeHubCard'))
const MemoryGraphCard = lazy(() => import('./MemoryGraphCard'))
const HardwareGauges = lazy(() => import('./HardwareGauges'))
const LiveDebugInspector = lazy(() =>
  import('./LiveDebugInspector').then((m) => ({ default: m.LiveDebugInspector }))
)
const SettingsPanel = lazy(() => import('./SettingsPanel'))
const CommandPalette = lazy(() => import('./CommandPalette'))
const Orb = lazy(() => import('./Orb'))
const VoiceWave = lazy(() => import('./VoiceWave'))

interface DashboardLayoutProps {
  onSendMessage: (text: string) => void
  onOrbClick: () => void
}

type TabKey =
  | 'home'
  | 'chat'
  | 'voice'
  | 'tasks'
  | 'pc_control'
  | 'files'
  | 'automation'
  | 'system'
  | 'settings'

interface SidebarItem {
  id: TabKey
  label: string
  icon: React.ElementType
}

const SIDEBAR_ITEMS: SidebarItem[] = [
  { id: 'home', label: 'Home', icon: LayoutDashboard },
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'voice', label: 'Voice', icon: Mic },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare },
  { id: 'pc_control', label: 'PC Control', icon: Monitor },
  { id: 'files', label: 'Files', icon: Folder },
  { id: 'automation', label: 'Automation', icon: Cpu },
  { id: 'system', label: 'System', icon: Activity },
  { id: 'settings', label: 'Settings', icon: SettingsIcon }
]

const TAB_METADATA: Record<string, { title: string; subtitle: string; tag: string }> = {
  chat: { title: 'Conversational Intelligence', subtitle: 'Multi-turn dialog & contextual reasoning', tag: 'SESSION ACTIVE' },
  voice: { title: 'Voice Interaction Core', subtitle: 'Real-time neural audio & wake-word engine', tag: 'LISTENING ENGINE' },
  tasks: { title: 'Autonomous Task Queue', subtitle: 'Multi-step action sequencing & execution timeline', tag: 'SCHEDULER READY' },
  pc_control: { title: 'Computer Control & Perception', subtitle: 'Live screen graph, Win32 UIA tree & failover co-pilot', tag: 'PERCEPTION ONLINE' },
  files: { title: 'Knowledge Hub & Semantic Memory', subtitle: 'ChromaDB vector store & cross-session memory graph', tag: 'SYNCHRONIZED' },
  automation: { title: 'Browser & System Automation', subtitle: 'Autonomous web navigation & workflow macros', tag: 'WORKFLOW ENGINE' },
  system: { title: 'System Diagnostics & Telemetry', subtitle: 'Hardware gauges, process limits & runtime inspector', tag: 'NOMINAL 1.0 HZ' },
  settings: { title: 'System Configuration', subtitle: 'Voice models, API endpoints & telemetry preferences', tag: 'CONFIGURATION' },
}

const LoadingFallback: React.FC<{ label: string }> = ({ label }) => (
  <div className="flex flex-col items-center justify-center h-full min-h-[350px] rounded-2xl border border-cyan-500/20 bg-slate-950/40 backdrop-blur-2xl p-8 text-center animate-pulse">
    <Sparkles className="w-8 h-8 text-cyan-400 mb-2 animate-spin" />
    <span className="text-xs font-mono text-cyan-300 font-bold tracking-wider uppercase">
      Loading {label}...
    </span>
    <span className="text-[10px] font-mono text-slate-500 mt-1">Initializing module</span>
  </div>
)

export default function DashboardLayout({ onSendMessage, onOrbClick }: DashboardLayoutProps) {
  const activeTab = useAppStore((s) => s.activeTab)
  const setActiveTab = useAppStore((s) => s.setActiveTab)
  const isListening = useAppStore((s) => s.isListening)
  const setListening = useAppStore((s) => s.setListening)
  const userName = useAppStore((s) => s.userName) || 'Ashrit'
  const clearMessages = useAppStore((s) => s.clearMessages)
  const activeConversationId = useAppStore((s) => s.activeConversationId)
  const setActiveConversationId = useAppStore((s) => s.setActiveConversationId)
  const setMessages = useAppStore((s) => s.setMessages)

  const [isPaletteOpen, setIsPaletteOpen] = useState(false)
  const [currentDateStr, setCurrentDateStr] = useState('')
  const [timeGreeting, setTimeGreeting] = useState('Good Morning,')

  // Date and Time calculation
  useEffect(() => {
    const updateDateTime = () => {
      const now = new Date()
      const hour = now.getHours()
      if (hour < 12) setTimeGreeting('Good Morning,')
      else if (hour < 17) setTimeGreeting('Good Afternoon,')
      else setTimeGreeting('Good Evening,')

      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      setCurrentDateStr(`☼ ${days[now.getDay()]}, ${months[now.getMonth()]} ${now.getDate()}, ${now.getFullYear()}`)
    }

    updateDateTime()
    const timer = setInterval(updateDateTime, 60000)
    return () => clearInterval(timer)
  }, [])

  // Keyboard shortcut Ctrl+K for Palette
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setIsPaletteOpen((prev) => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleToggleListening = () => {
    onOrbClick()
    setListening(!isListening)
  }

  const handleSelectConversation = async (convId: string | number) => {
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
  }

  const handleNewChat = () => {
    setActiveConversationId(null)
    setMessages([])
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden select-none relative bg-slate-950 text-slate-100 font-sans">
      {/* ── Atmospheric Cybernetic Landscape Backdrop (Clean Vector Horizon, No Phantom UI) ── */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden z-0 bg-gradient-to-b from-[#020510] via-[#050b1a] to-[#02040a]">
        {/* Central Luminous Nebula Glow behind the Jarvis Core Orb */}
        <div className="absolute top-[20%] left-1/2 -translate-x-1/2 w-[700px] h-[500px] rounded-full bg-[radial-gradient(ellipse_at_center,_rgba(0,229,255,0.12)_0%,_rgba(30,58,138,0.18)_40%,_transparent_75%)] blur-2xl pointer-events-none" />

        {/* Subtle Ambient Horizon Aurora */}
        <div className="absolute bottom-[18%] left-0 right-0 h-48 bg-gradient-to-t from-cyan-950/20 via-blue-900/10 to-transparent pointer-events-none" />

        {/* Crisp Vector Mountain Landscape Silhouette */}
        <svg
          className="absolute bottom-0 left-0 right-0 w-full h-[32%] min-h-[160px] opacity-75"
          viewBox="0 0 1440 320"
          preserveAspectRatio="none"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Back Distant Peaks */}
          <path
            d="M0,220 L120,180 L240,210 L380,150 L520,200 L680,130 L840,190 L980,140 L1120,180 L1260,130 L1380,170 L1440,160 L1440,320 L0,320 Z"
            fill="url(#distantMountainGrad)"
          />
          {/* Mid Ridge Peaks */}
          <path
            d="M0,250 L160,200 L320,240 L460,180 L620,230 L760,170 L920,220 L1080,165 L1240,210 L1380,185 L1440,200 L1440,320 L0,320 Z"
            fill="url(#midMountainGrad)"
          />
          {/* Front Foreground Ridge */}
          <path
            d="M0,280 L180,240 L360,270 L540,230 L720,265 L900,225 L1080,260 L1260,235 L1440,265 L1440,320 L0,320 Z"
            fill="url(#frontMountainGrad)"
          />
          <defs>
            <linearGradient id="distantMountainGrad" x1="720" y1="130" x2="720" y2="320" gradientUnits="userSpaceOnUse">
              <stop stopColor="#0d1b2a" stopOpacity="0.8" />
              <stop offset="0.6" stopColor="#08101e" stopOpacity="0.95" />
              <stop offset="1" stopColor="#02040a" />
            </linearGradient>
            <linearGradient id="midMountainGrad" x1="720" y1="165" x2="720" y2="320" gradientUnits="userSpaceOnUse">
              <stop stopColor="#0b1728" stopOpacity="0.9" />
              <stop offset="0.7" stopColor="#060c18" />
              <stop offset="1" stopColor="#02040a" />
            </linearGradient>
            <linearGradient id="frontMountainGrad" x1="720" y1="225" x2="720" y2="320" gradientUnits="userSpaceOnUse">
              <stop stopColor="#070e1b" />
              <stop offset="1" stopColor="#010307" />
            </linearGradient>
          </defs>
        </svg>

        {/* Ambient Lake / Surface Reflection Line */}
        <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent" />

        {/* Cinematic Vignette */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_transparent_45%,_rgba(2,6,23,0.85)_100%)] pointer-events-none" />
      </div>

      {/* ── Top Bar ── */}
      <TitleBar />

      {/* ── Main Application Body ── */}
      <div className="flex-1 flex overflow-hidden relative z-10">
        {/* ── Left Translucent Glass Sidebar Navigation ── */}
        <aside className="w-56 shrink-0 h-full bg-slate-950/40 backdrop-blur-2xl border-r border-blue-500/20 flex flex-col justify-between py-4 px-3 shadow-[4px_0_24px_rgba(0,0,0,0.4)] z-20">
          <nav className="flex flex-col gap-1.5">
            {SIDEBAR_ITEMS.map((item) => {
              const Icon = item.icon
              const isActive = activeTab === item.id

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={`group relative flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-medium text-xs tracking-wide transition-all duration-200 cursor-pointer text-left ${
                    isActive
                      ? 'bg-blue-600/30 text-white border border-cyan-400/50 shadow-[0_0_18px_rgba(0,229,255,0.3)]'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800/40 hover:border-cyan-500/20 border border-transparent'
                  }`}
                >
                  {/* Left luminous accent bar when active */}
                  {isActive && (
                    <div className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-cyan-400 shadow-[0_0_8px_#00e5ff]" />
                  )}

                  <Icon
                    className={`w-4 h-4 shrink-0 transition-colors ${
                      isActive ? 'text-cyan-300' : 'text-slate-400 group-hover:text-cyan-400'
                    }`}
                  />
                  <span className="truncate">{item.label}</span>
                </button>
              )
            })}
          </nav>

          {/* Sidebar Footer Controls */}
          <div className="pt-3 border-t border-white/5 flex items-center justify-between px-1">
            <button
              type="button"
              onClick={() => setIsPaletteOpen(true)}
              className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-900/60 hover:bg-slate-800 border border-blue-500/20 text-slate-300 hover:text-cyan-300 text-[11px] font-mono transition-colors cursor-pointer"
              title="Command Palette (Ctrl+K)"
            >
              <Command className="w-3.5 h-3.5 text-cyan-400" />
              <span>Ctrl+K</span>
            </button>

            <button
              type="button"
              onClick={clearMessages}
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-900/60 transition-colors cursor-pointer"
              title="Clear Active Chat"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </aside>

        {/* ── Main View Content Area ── */}
        <main className="flex-1 h-full overflow-hidden flex flex-col relative">
          {/* Sub-Page Persistent Glass Header Bar */}
          {activeTab !== 'home' && (
            <div className="px-6 pt-4 pb-2 shrink-0 flex items-center justify-between border-b border-white/5 bg-slate-950/20 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_10px_#00e5ff] animate-pulse" />
                <div>
                  <h1 className="text-xs font-bold font-mono text-slate-200 tracking-[0.2em] uppercase">
                    {TAB_METADATA[activeTab]?.title || activeTab}
                  </h1>
                  <p className="text-[11px] font-mono text-slate-400">
                    {TAB_METADATA[activeTab]?.subtitle}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-3 py-1 rounded-full bg-blue-950/40 border border-cyan-500/30 text-cyan-300 shadow-[0_0_15px_rgba(0,229,255,0.15)] uppercase">
                  {TAB_METADATA[activeTab]?.tag}
                </span>
              </div>
            </div>
          )}

          {/* TAB 1: HOME (Exact match to reference aesthetic) */}
          {activeTab === 'home' && (
            <div className="flex-1 flex flex-col justify-between p-6 overflow-hidden relative">
              {/* Upper Main Workspace Section */}
              <div className="flex-1 grid grid-cols-12 gap-6 items-center min-h-0">
                {/* Hero Left: Date, Time Greeting, Name, Quote */}
                <div className="col-span-12 lg:col-span-4 flex flex-col justify-center select-none pl-2">
                  {/* Dynamic Date Badge */}
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/60 border border-blue-500/20 backdrop-blur-md w-fit mb-3">
                    <span className="text-[11px] font-mono font-medium text-cyan-300 tracking-wider">
                      {currentDateStr}
                    </span>
                  </div>

                  {/* Greeting & Name */}
                  <h1 className="text-3xl lg:text-4xl font-light text-white tracking-tight leading-tight">
                    {timeGreeting}
                  </h1>
                  <h2 className="text-4xl lg:text-5xl font-extrabold tracking-tight text-white drop-shadow-[0_0_20px_rgba(0,229,255,0.4)] mt-1">
                    <span className="bg-gradient-to-r from-white via-cyan-100 to-cyan-300 bg-clip-text text-transparent">
                      {userName}.
                    </span>
                  </h2>

                  {/* Cyan Glowing Accent Underline */}
                  <div className="w-20 h-1 bg-gradient-to-r from-cyan-400 via-blue-500 to-transparent rounded-full my-4 shadow-[0_0_10px_#00e5ff]" />

                  {/* Quote / Subtitle */}
                  <p className="text-sm lg:text-base text-slate-300/90 font-normal italic tracking-wide">
                    "Let's make today productive."
                  </p>
                </div>

                {/* Hero Center: Central Floating Luminous JARVIS Core Orb */}
                <div className="col-span-12 lg:col-span-4 flex items-center justify-center">
                  <JarvisCoreOrb onToggleListening={handleToggleListening} />
                </div>

                {/* Hero Right: Telemetry & Quick Actions Cards */}
                <div className="col-span-12 lg:col-span-4 flex flex-col gap-4 max-h-[82vh] overflow-y-auto custom-scrollbar pr-1">
                  <TelemetryGaugesCard />
                  <QuickActionsCard onExecutePrompt={(prompt) => onSendMessage(prompt)} />
                </div>
              </div>

              {/* Bottom Floating Command Bar Dock */}
              <div className="pt-3 pb-1 shrink-0">
                <FloatingCommandBar
                  onSendMessage={onSendMessage}
                  onToggleListening={handleToggleListening}
                  isListening={isListening}
                />
              </div>
            </div>
          )}

          {/* TAB 2: CHAT */}
          {activeTab === 'chat' && (
            <Suspense fallback={<LoadingFallback label="Chat" />}>
              <div className="flex-1 flex h-full overflow-hidden p-4 gap-4">
                <ConversationSidebar
                  activeId={activeConversationId}
                  onSelectConversation={handleSelectConversation}
                  onNewChat={handleNewChat}
                />
                <div className="flex-1 h-full min-w-0 bg-slate-950/40 backdrop-blur-2xl border border-blue-500/20 rounded-2xl overflow-hidden shadow-2xl">
                  <ChatPanel onSendMessage={onSendMessage} />
                </div>
              </div>
            </Suspense>
          )}

          {/* TAB 3: VOICE */}
          {activeTab === 'voice' && (
            <Suspense fallback={<LoadingFallback label="Voice Interface" />}>
              <div className="flex-1 flex flex-col items-center justify-center p-6 gap-6">
                {/* Legacy Three.js Arc Reactor Orb commented out as requested */}
                {/*
                <div className="relative w-80 h-80 rounded-full border border-cyan-500/30 bg-slate-950/60 backdrop-blur-2xl shadow-[0_0_50px_rgba(0,229,255,0.25)] flex items-center justify-center overflow-hidden">
                  <Orb onOrbClick={onOrbClick} />
                </div>
                */}
                <div className="flex items-center justify-center">
                  <JarvisCoreOrb onToggleListening={handleToggleListening} />
                </div>
                <div className="w-full max-w-md">
                  <VoiceWave />
                </div>
                <p className="text-xs font-mono text-cyan-300">
                  Voice recognition active. Speak naturally or click the orb.
                </p>
              </div>
            </Suspense>
          )}

          {/* TAB 4: TASKS */}
          {activeTab === 'tasks' && (
            <Suspense fallback={<LoadingFallback label="Task Queue" />}>
              <div className="flex-1 p-4 overflow-y-auto space-y-4 custom-scrollbar">
                <TaskQueueManager />
                <div className="max-w-4xl mx-auto">
                  <TaskProgress />
                </div>
              </div>
            </Suspense>
          )}

          {/* TAB 5: PC CONTROL */}
          {activeTab === 'pc_control' && (
            <Suspense fallback={<LoadingFallback label="PC Control & Perception" />}>
              <div className="flex-1 p-4 overflow-y-auto space-y-4 custom-scrollbar">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <ComputerUseCard />
                  <LivePerceptionVisualizer />
                </div>
                <LiveModeCard />
              </div>
            </Suspense>
          )}

          {/* TAB 6: FILES */}
          {activeTab === 'files' && (
            <Suspense fallback={<LoadingFallback label="File System & Knowledge" />}>
              <div className="flex-1 p-4 overflow-y-auto space-y-4 custom-scrollbar">
                <KnowledgeHubCard />
                <MemoryGraphCard />
              </div>
            </Suspense>
          )}

          {/* TAB 7: AUTOMATION */}
          {activeTab === 'automation' && (
            <Suspense fallback={<LoadingFallback label="Automation Workflows" />}>
              <div className="flex-1 p-4 overflow-y-auto space-y-4 custom-scrollbar">
                <BrowserAutomationCard />
                <ComputerUseCard />
              </div>
            </Suspense>
          )}

          {/* TAB 8: SYSTEM */}
          {activeTab === 'system' && (
            <Suspense fallback={<LoadingFallback label="System Diagnostics" />}>
              <div className="flex-1 p-4 overflow-y-auto space-y-4 custom-scrollbar">
                <HardwareGauges />
                <LiveDebugInspector />
              </div>
            </Suspense>
          )}

          {/* TAB 9: SETTINGS */}
          {activeTab === 'settings' && (
            <Suspense fallback={<LoadingFallback label="Settings" />}>
              <div className="flex-1 p-4 md:p-6 overflow-y-auto custom-scrollbar flex justify-center">
                <SettingsPanel />
              </div>
            </Suspense>
          )}
        </main>
      </div>

      {/* Global Command Palette Modal */}
      {isPaletteOpen && (
        <Suspense fallback={null}>
          <CommandPalette
            isOpen={isPaletteOpen}
            onClose={() => setIsPaletteOpen(false)}
            onSelectAction={(actionId) => {
              if (actionId === 'screenshot') onSendMessage('Take a screenshot')
              else if (actionId === 'lock_pc') onSendMessage('Lock PC')
              else if (actionId === 'focus_mode') onSendMessage('Toggle focus mode')
            }}
          />
        </Suspense>
      )}
    </div>
  )
}