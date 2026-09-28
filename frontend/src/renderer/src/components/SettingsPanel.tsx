import { useState, useEffect, useCallback } from 'react'
import { useAppStore } from '../stores/appStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { getApiBaseUrl } from '../utils/api'
import type { Settings } from '../types'
import { GeneralSettingsTab } from './settings/GeneralSettingsTab'
import { DisplaySettingsTab } from './settings/DisplaySettingsTab'
import { HandControlSettingsTab } from './settings/HandControlSettingsTab'
import { IntegrationsSettingsTab } from './settings/IntegrationsSettingsTab'
import { SystemDiagnosticsTab } from './settings/SystemDiagnosticsTab'
import { 
  Sliders, 
  Monitor, 
  Hand, 
  Send, 
  Key, 
  Bluetooth, 
  Cpu, 
  Brain, 
  Check, 
  RotateCcw 
} from 'lucide-react'

export default function SettingsPanel() {
  const {
    settings,
    updateVoiceSettings,
    updateAISettings,
    updateDisplaySettings,
    updateHandControlSettings
  } = useAppStore()
  const { sendMessage } = useWebSocket()
  const [localSettings, setLocalSettings] = useState<Settings>(settings)
  const [monitors, setMonitors] = useState<any[]>([])
  const [cameras, setCameras] = useState<MediaDeviceInfo[]>([])
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false)

  // Tab Selection
  const [activeTab, setActiveTab] = useState<
    'general' | 'display' | 'hand' | 'telegram' | 'integrations' | 'proximity' | 'orchestrator' | 'brain'
  >('general')

  const [rankings, setRankings] = useState<any[]>([])
  const [routerMetrics, setRouterMetrics] = useState<any[]>([])
  const [brainData, setBrainData] = useState<{
    memories: any[]
    lessons: any[]
    workflows: any[]
  }>({ memories: [], lessons: [], workflows: [] })
  const [consolidating, setConsolidating] = useState(false)

  // Load monitors & cameras on mount
  useEffect(() => {
    const loadHardware = async () => {
      try {
        const baseUrl = getApiBaseUrl()
        const res = await fetch(`${baseUrl}/monitors`)
        if (res.ok) {
          const data = await res.json()
          if (Array.isArray(data)) {
            setMonitors(data)
          }
        }
      } catch (err) {
        console.error('[Settings] Failed to fetch monitors:', err)
      }

      try {
        if (navigator.mediaDevices?.enumerateDevices) {
          const devices = await navigator.mediaDevices.enumerateDevices()
          const videoDevices = devices.filter((d) => d.kind === 'videoinput')
          setCameras(videoDevices)
        }
      } catch (err) {
        console.error('[Settings] Failed to enumerate camera devices:', err)
      }
    }

    loadHardware()
  }, [])

  // Sync settings locally when store updates
  useEffect(() => {
    setLocalSettings(settings)
  }, [settings])

  const handleSave = useCallback(() => {
    updateVoiceSettings(localSettings.voice)
    updateAISettings(localSettings.ai)
    updateDisplaySettings(localSettings.display)
    updateHandControlSettings(localSettings.handControl)
    sendMessage('settings', {
      voice: localSettings.voice,
      ai: localSettings.ai,
      display: localSettings.display,
      handControl: localSettings.handControl
    })
    setSaveSuccess(true)
    setTimeout(() => setSaveSuccess(false), 2500)
  }, [
    localSettings,
    updateVoiceSettings,
    updateAISettings,
    updateDisplaySettings,
    updateHandControlSettings,
    sendMessage
  ])

  // Consolidate memory action
  const handleConsolidateMemories = useCallback(async () => {
    setConsolidating(true)
    try {
      const baseUrl = getApiBaseUrl()
      await fetch(`${baseUrl}/brain/consolidate`, { method: 'POST' })
      const resBrain = await fetch(`${baseUrl}/brain/memories`)
      if (resBrain.ok) {
        const dataBrain = await resBrain.json()
        if (dataBrain.status === 'ok') {
          setBrainData({
            memories: dataBrain.memories || [],
            lessons: dataBrain.lessons || [],
            workflows: dataBrain.workflows || []
          })
        }
      }
    } catch (err) {
      console.error('[Settings] Failed to consolidate memories:', err)
    } finally {
      setConsolidating(false)
    }
  }, [])

  // Load and poll Orchestrator & Brain data when tab is active
  const fetchDashboardData = useCallback(async () => {
    try {
      const baseUrl = getApiBaseUrl()
      if (activeTab === 'orchestrator') {
        const resRank = await fetch(`${baseUrl}/router/rankings`)
        if (resRank.ok) {
          const dataRank = await resRank.json()
          if (dataRank.status === 'ok') setRankings(dataRank.rankings || [])
        }

        const resMetrics = await fetch(`${baseUrl}/router/metrics`)
        if (resMetrics.ok) {
          const dataMetrics = await resMetrics.json()
          if (dataMetrics.status === 'ok') setRouterMetrics(dataMetrics.metrics || [])
        }
      } else if (activeTab === 'brain') {
        const resBrain = await fetch(`${baseUrl}/brain/memories`)
        if (resBrain.ok) {
          const dataBrain = await resBrain.json()
          if (dataBrain.status === 'ok') {
            setBrainData({
              memories: dataBrain.memories || [],
              lessons: dataBrain.lessons || [],
              workflows: dataBrain.workflows || []
            })
          }
        }
      }
    } catch (err) {
      console.error('[Settings] Error fetching dashboard data:', err)
    }
  }, [activeTab])

  useEffect(() => {
    if (activeTab === 'orchestrator' || activeTab === 'brain') {
      fetchDashboardData()
      const interval = setInterval(fetchDashboardData, 8000)
      return () => clearInterval(interval)
    }
  }, [activeTab, fetchDashboardData])

  const tabItems = [
    { id: 'general' as const, label: 'General & Voice', icon: Sliders },
    { id: 'display' as const, label: 'Display & UI', icon: Monitor },
    { id: 'hand' as const, label: 'Vision & Gestures', icon: Hand },
    { id: 'telegram' as const, label: 'Telegram Bot', icon: Send },
    { id: 'integrations' as const, label: 'OAuth & Apps', icon: Key },
    { id: 'proximity' as const, label: 'BLE Proximity', icon: Bluetooth },
    { id: 'orchestrator' as const, label: 'LLM Orchestrator', icon: Cpu },
    { id: 'brain' as const, label: 'Brain & Memory', icon: Brain },
  ]

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col bg-slate-950/70 backdrop-blur-2xl rounded-2xl border border-blue-500/20 overflow-hidden shadow-[0_16px_48px_rgba(0,0,0,0.5)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-slate-900/50">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_#00e5ff] animate-pulse" />
          <div>
            <h2 className="text-sm font-bold tracking-[0.2em] text-white uppercase font-mono">
              JARVIS System Configuration
            </h2>
            <p className="text-[11px] text-slate-400 font-mono mt-0.5">
              Neural audio, vision tracking, cloud services, and hardware preferences
            </p>
          </div>
        </div>

        {saveSuccess && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-mono animate-fade-in shadow-[0_0_12px_rgba(16,185,129,0.3)]">
            <Check className="w-3.5 h-3.5" />
            <span>Settings Applied</span>
          </div>
        )}
      </div>

      {/* Tab Selection */}
      <div className="flex border-b border-white/10 text-xs overflow-x-auto custom-scrollbar bg-slate-950/40 px-2">
        {tabItems.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-3 px-4 border-b-2 font-mono font-medium whitespace-nowrap transition-all cursor-pointer ${
                isActive
                  ? 'border-cyan-400 text-cyan-200 font-bold bg-blue-600/15 shadow-[inset_0_-2px_6px_rgba(0,229,255,0.2)]'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div className="p-6 space-y-6 max-h-[calc(100vh-270px)] overflow-y-auto custom-scrollbar bg-slate-950/30">
        {activeTab === 'general' && (
          <GeneralSettingsTab
            localSettings={localSettings}
            setLocalSettings={setLocalSettings}
          />
        )}

        {activeTab === 'display' && (
          <DisplaySettingsTab
            localSettings={localSettings}
            setLocalSettings={setLocalSettings}
            monitors={monitors}
          />
        )}

        {activeTab === 'hand' && (
          <HandControlSettingsTab
            localSettings={localSettings}
            setLocalSettings={setLocalSettings}
            updateHandControlSettings={updateHandControlSettings}
            cameras={cameras}
          />
        )}

        {activeTab === 'telegram' && (
          <IntegrationsSettingsTab viewMode="telegram" />
        )}

        {activeTab === 'integrations' && (
          <IntegrationsSettingsTab viewMode="oauth" />
        )}

        {activeTab === 'proximity' && (
          <IntegrationsSettingsTab viewMode="proximity" />
        )}

        {activeTab === 'orchestrator' && (
          <SystemDiagnosticsTab
            rankings={rankings}
            routerMetrics={routerMetrics}
            brainData={brainData}
            consolidating={consolidating}
            onConsolidate={handleConsolidateMemories}
            activeSubSection="orchestrator"
          />
        )}

        {activeTab === 'brain' && (
          <SystemDiagnosticsTab
            rankings={rankings}
            routerMetrics={routerMetrics}
            brainData={brainData}
            consolidating={consolidating}
            onConsolidate={handleConsolidateMemories}
            activeSubSection="brain"
          />
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-6 py-4 border-t border-white/10 bg-slate-950/80">
        <div className="text-xs text-slate-400 font-mono hidden sm:block">
          Changes take effect immediately across active background pipelines.
        </div>
        <div className="flex items-center gap-3 ml-auto">
          <button
            type="button"
            onClick={() => setLocalSettings(settings)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-mono font-medium text-slate-400 hover:text-white border border-white/10 hover:bg-white/5 transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Revert</span>
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="flex items-center gap-2 px-6 py-2 rounded-xl text-xs font-mono font-bold bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-[0_0_15px_rgba(0,229,255,0.4)] hover:brightness-110 active:scale-95 transition-all cursor-pointer"
          >
            <Check className="w-3.5 h-3.5" />
            <span>Save Changes</span>
          </button>
        </div>
      </div>
    </div>
  )
}