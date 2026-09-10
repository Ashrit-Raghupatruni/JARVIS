import { useState, useEffect, useCallback } from 'react'
import { useAppStore } from '../stores/appStore'
import { useWebSocket } from '../hooks/useWebSocket'
import type { Settings } from '../types'
import { GeneralSettingsTab } from './settings/GeneralSettingsTab'
import { DisplaySettingsTab } from './settings/DisplaySettingsTab'
import { HandControlSettingsTab } from './settings/HandControlSettingsTab'
import { IntegrationsSettingsTab } from './settings/IntegrationsSettingsTab'
import { SystemDiagnosticsTab } from './settings/SystemDiagnosticsTab'

export default function SettingsPanel() {
  const {
    showSettings,
    setShowSettings,
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

  // Tab and Analytics State
  const [activeTab, setActiveTab] = useState<
    'general' | 'display' | 'hand' | 'orchestrator' | 'brain' | 'integrations' | 'proximity'
  >('general')
  const [rankings, setRankings] = useState<any[]>([])
  const [routerMetrics, setRouterMetrics] = useState<any[]>([])
  const [brainData, setBrainData] = useState<{
    memories: any[]
    lessons: any[]
    workflows: any[]
  }>({ memories: [], lessons: [], workflows: [] })
  const [consolidating, setConsolidating] = useState(false)

  // Load monitors & cameras on open
  useEffect(() => {
    if (showSettings) {
      const loadMonitors = async () => {
        let port = 8000
        const api = (window as any).electronAPI
        if (api?.getSystemInfo) {
          try {
            const info = await api.getSystemInfo()
            if (info && typeof info.backendPort === 'number') {
              port = info.backendPort
            }
          } catch (e) {
            console.error(e)
          }
        }
        try {
          const res = await fetch(`http://127.0.0.1:${port}/monitors`)
          const data = await res.json()
          if (Array.isArray(data)) {
            setMonitors(data)
          }
        } catch (err) {
          console.error('[Settings] Failed to fetch monitors:', err)
        }
      }
      loadMonitors()

      navigator.mediaDevices
        .enumerateDevices()
        .then((devices) => {
          const videoDevices = devices.filter((d) => d.kind === 'videoinput')
          setCameras(videoDevices)
        })
        .catch((err) => {
          console.error('[Settings] Failed to enumerate camera devices:', err)
        })
    }
  }, [showSettings])

  // Sync settings locally
  useEffect(() => {
    setLocalSettings(settings)
  }, [settings])

  const handleClose = useCallback(() => {
    setShowSettings(false)
  }, [setShowSettings])

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
    setShowSettings(false)
  }, [
    localSettings,
    updateVoiceSettings,
    updateAISettings,
    updateDisplaySettings,
    updateHandControlSettings,
    sendMessage,
    setShowSettings
  ])

  // Consolidate memory action
  const handleConsolidateMemories = useCallback(async () => {
    let port = 8000
    const api = (window as any).electronAPI
    if (api?.getSystemInfo) {
      try {
        const info = await api.getSystemInfo()
        if (info && typeof info.backendPort === 'number') port = info.backendPort
      } catch (e) {
        console.error(e)
      }
    }
    setConsolidating(true)
    try {
      await fetch(`http://127.0.0.1:${port}/brain/consolidate`, { method: 'POST' })
      const resBrain = await fetch(`http://127.0.0.1:${port}/brain/memories`)
      const dataBrain = await resBrain.json()
      if (dataBrain.status === 'ok') {
        setBrainData({
          memories: dataBrain.memories || [],
          lessons: dataBrain.lessons || [],
          workflows: dataBrain.workflows || []
        })
      }
    } catch (err) {
      console.error('[Settings] Failed to consolidate memories:', err)
    } finally {
      setConsolidating(false)
    }
  }, [])

  // Load and poll Orchestrator & Brain data when tab is active
  const fetchDashboardData = useCallback(async () => {
    let port = 8000
    const api = (window as any).electronAPI
    if (api?.getSystemInfo) {
      try {
        const info = await api.getSystemInfo()
        if (info && typeof info.backendPort === 'number') {
          port = info.backendPort
        }
      } catch (e) {
        console.error(e)
      }
    }

    try {
      if (activeTab === 'orchestrator') {
        const resRank = await fetch(`http://127.0.0.1:${port}/router/rankings`)
        const dataRank = await resRank.json()
        if (dataRank.status === 'ok') setRankings(dataRank.rankings)

        const resMetrics = await fetch(`http://127.0.0.1:${port}/router/metrics`)
        const dataMetrics = await resMetrics.json()
        if (dataMetrics.status === 'ok') setRouterMetrics(dataMetrics.metrics)
      } else if (activeTab === 'brain') {
        const resBrain = await fetch(`http://127.0.0.1:${port}/brain/memories`)
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
      console.error('[Dashboard] Error fetching dashboard data:', err)
    }
  }, [activeTab])

  useEffect(() => {
    if (showSettings && (activeTab === 'orchestrator' || activeTab === 'brain')) {
      fetchDashboardData()
      const interval = setInterval(fetchDashboardData, 8000)
      return () => clearInterval(interval)
    }
  }, [showSettings, activeTab, fetchDashboardData])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showSettings) handleClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [showSettings, handleClose])

  if (!showSettings) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)' }}
      onClick={handleClose}
    >
      <div
        className="glass-heavy rounded-2xl border border-white/10 w-full max-w-lg mx-4 overflow-hidden animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--jarvis-text)' }}>
            JARVIS System Settings
          </h2>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
            style={{ color: 'var(--jarvis-text-dim)' }}
          >
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-white/10 text-xs overflow-x-auto custom-scrollbar">
          <button
            className={`flex-1 py-3 px-3 text-center border-b-2 font-medium whitespace-nowrap transition-all ${
              activeTab === 'general'
                ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]'
                : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'
            }`}
            onClick={() => setActiveTab('general')}
          >
            General & Voice
          </button>
          <button
            className={`flex-1 py-3 px-3 text-center border-b-2 font-medium whitespace-nowrap transition-all ${
              activeTab === 'display'
                ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]'
                : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'
            }`}
            onClick={() => setActiveTab('display')}
          >
            Display
          </button>
          <button
            className={`flex-1 py-3 px-3 text-center border-b-2 font-medium whitespace-nowrap transition-all ${
              activeTab === 'hand'
                ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]'
                : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'
            }`}
            onClick={() => setActiveTab('hand')}
          >
            Gestures
          </button>
          <button
            className={`flex-1 py-3 px-3 text-center border-b-2 font-medium whitespace-nowrap transition-all ${
              activeTab === 'integrations'
                ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]'
                : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'
            }`}
            onClick={() => setActiveTab('integrations')}
          >
            OAuth
          </button>
          <button
            className={`flex-1 py-3 px-3 text-center border-b-2 font-medium whitespace-nowrap transition-all ${
              activeTab === 'proximity'
                ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]'
                : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'
            }`}
            onClick={() => setActiveTab('proximity')}
          >
            BLE
          </button>
          <button
            className={`flex-1 py-3 px-3 text-center border-b-2 font-medium whitespace-nowrap transition-all ${
              activeTab === 'orchestrator'
                ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]'
                : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'
            }`}
            onClick={() => setActiveTab('orchestrator')}
          >
            Orchestrator
          </button>
          <button
            className={`flex-1 py-3 px-3 text-center border-b-2 font-medium whitespace-nowrap transition-all ${
              activeTab === 'brain'
                ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]'
                : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'
            }`}
            onClick={() => setActiveTab('brain')}
          >
            Brain & Memory
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-6 max-h-[60vh] overflow-y-auto custom-scrollbar">
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
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-white/10">
          <button
            onClick={handleClose}
            className="px-4 py-2 rounded-lg text-sm border border-white/10 hover:bg-white/10 transition-colors"
            style={{ color: 'var(--jarvis-text)' }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{ backgroundColor: 'var(--jarvis-accent)', color: '#0a0e1a' }}
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  )
}