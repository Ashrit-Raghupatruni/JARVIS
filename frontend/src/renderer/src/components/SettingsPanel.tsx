import { useState, useEffect, useCallback } from 'react'
import { useAppStore } from '../stores/appStore'
import { useWebSocket } from '../hooks/useWebSocket'
import type { Settings } from '../types'

const VOICE_OPTIONS = [
  { value: 'en-US-GuyNeural', label: 'Guy (US Male)' },
  { value: 'en-GB-RyanNeural', label: 'Ryan (UK Male)' },
  { value: 'en-AU-WilliamNeural', label: 'William (AU Male)' },
  { value: 'en-IN-PrabhatNeural', label: 'Prabhat (IN Male)' },
]

const MODEL_OPTIONS = [
  { value: 'qwen2.5-coder:3b', label: 'Qwen 2.5 Coder 3B (Ollama / Local)' },
  { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash (Cloud)' },
  { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (Cloud)' },
  { value: 'gpt-4o', label: 'GPT-4o (OpenAI)' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini (OpenAI)' },
  { value: 'meta-llama/llama-3.3-70b-instruct:free', label: 'Llama 3.3 70B (OpenRouter Free)' },
  { value: 'qwen/qwen-2.5-coder-32b-instruct:free', label: 'Qwen 2.5 Coder 32B (OpenRouter Free)' },
  { value: 'deepseek/deepseek-chat', label: 'DeepSeek V3 (OpenRouter)' },
]


export default function SettingsPanel() {
  const { showSettings, setShowSettings, settings, updateVoiceSettings, updateAISettings, updateDisplaySettings, updateHandControlSettings } = useAppStore()
  const { sendMessage } = useWebSocket()
  const [localSettings, setLocalSettings] = useState<Settings>(settings)
  const [monitors, setMonitors] = useState<any[]>([])
  const [cameras, setCameras] = useState<MediaDeviceInfo[]>([])
  
  // Tab and Analytics State
  const [activeTab, setActiveTab] = useState<'general' | 'orchestrator' | 'brain'>('general')
  const [rankings, setRankings] = useState<any[]>([])
  const [routerMetrics, setRouterMetrics] = useState<any[]>([])
  const [brainData, setBrainData] = useState<{ memories: any[], lessons: any[], workflows: any[] }>({ memories: [], lessons: [], workflows: [] })
  const [consolidating, setConsolidating] = useState(false)

  // Load monitors
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

      navigator.mediaDevices.enumerateDevices().then((devices) => {
        const videoDevices = devices.filter((d) => d.kind === 'videoinput')
        setCameras(videoDevices)
      }).catch((err) => {
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
  }, [localSettings, updateVoiceSettings, updateAISettings, updateDisplaySettings, updateHandControlSettings, sendMessage, setShowSettings])

  // Load and poll Orchestrator & Brain data
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
    if (showSettings) {
      fetchDashboardData()
      const interval = setInterval(fetchDashboardData, 5000)
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
          <h2 className="text-lg font-semibold" style={{ color: 'var(--jarvis-text)' }}>JARVIS System Settings</h2>
          <button onClick={handleClose} className="p-1.5 rounded-lg hover:bg-white/10 transition-colors" style={{ color: 'var(--jarvis-text-dim)' }}>
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-white/10 text-xs">
          <button
            className={`flex-1 py-3 text-center border-b-2 font-medium transition-all ${activeTab === 'general' ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]' : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'}`}
            onClick={() => setActiveTab('general')}
          >
            General
          </button>
          <button
            className={`flex-1 py-3 text-center border-b-2 font-medium transition-all ${activeTab === 'orchestrator' ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]' : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'}`}
            onClick={() => setActiveTab('orchestrator')}
          >
            Orchestrator
          </button>
          <button
            className={`flex-1 py-3 text-center border-b-2 font-medium transition-all ${activeTab === 'brain' ? 'border-[var(--jarvis-accent)] text-[var(--jarvis-text)]' : 'border-transparent text-[var(--jarvis-text-dim)] hover:text-white'}`}
            onClick={() => setActiveTab('brain')}
          >
            Brain & Memory
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-6 max-h-[60vh] overflow-y-auto custom-scrollbar">
          {activeTab === 'general' && (
            <>
              {/* Voice & Serious Mode Section */}
              <section>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3 flex items-center justify-between" style={{ color: 'var(--jarvis-accent)' }}>
                  <span>Voice & Serious Mode</span>
                  {localSettings.voice.seriousMode && (
                    <span className="text-[10px] bg-rose-950 border border-rose-500 text-rose-300 px-2 py-0.5 rounded font-mono font-bold tracking-widest animate-pulse">
                      SERIOUS MODE ACTIVE
                    </span>
                  )}
                </h3>
                <div className="space-y-4">
                  {/* Serious Mode Toggle */}
                  <div className="flex items-center justify-between p-2.5 rounded-lg border border-rose-500/30 bg-rose-950/20">
                    <div>
                      <div className="text-sm font-bold text-rose-200">Serious Mode</div>
                      <div className="text-xs text-slate-400">Tactical HUD, authoritative voice, & mission-focused direct responses</div>
                    </div>
                    <button
                      onClick={() => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, seriousMode: !localSettings.voice.seriousMode } })}
                      className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${localSettings.voice.seriousMode ? 'bg-rose-600' : 'bg-white/20'}`}
                    >
                      <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300"
                        style={{ transform: localSettings.voice.seriousMode ? 'translateX(22px)' : 'translateX(2px)' }}
                      />
                    </button>
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>TTS Voice</label>
                    <select
                      value={localSettings.voice.ttsVoice || 'en-GB-RyanNeural'}
                      onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, ttsVoice: e.target.value } })}
                      className="w-full px-3 py-2 rounded-lg text-sm border border-white/10 focus:border-[var(--jarvis-accent)] focus:outline-none transition-colors"
                      style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--jarvis-text)' }}
                    >
                      {VOICE_OPTIONS.map((v) => <option key={v.value} value={v.value} style={{ backgroundColor: '#0c101d', color: '#fff' }}>{v.label}</option>)}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>
                      Speech Rate: {(localSettings.voice.speechRate || 1.0).toFixed(1)}x
                    </label>
                    <input
                      type="range" min="0.5" max="2.0" step="0.1"
                      value={localSettings.voice.speechRate || 1.0}
                      onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, speechRate: parseFloat(e.target.value) } })}
                      className="w-full accent-[var(--jarvis-accent)]"
                    />
                  </div>

                  {/* Wake Word Controls */}
                  <div className="pt-2 border-t border-white/10">
                    <div className="flex items-center justify-between mb-3">
                      <label className="text-sm font-semibold" style={{ color: 'var(--jarvis-text)' }}>Wake Word Detection</label>
                      <button
                        onClick={() => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, wakeWordEnabled: !localSettings.voice.wakeWordEnabled } })}
                        className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${localSettings.voice.wakeWordEnabled ? 'bg-[var(--jarvis-accent)]' : 'bg-white/20'}`}
                      >
                        <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300"
                          style={{ transform: localSettings.voice.wakeWordEnabled ? 'translateX(22px)' : 'translateX(2px)' }}
                        />
                      </button>
                    </div>

                    {localSettings.voice.wakeWordEnabled && (
                      <div className="space-y-3 pl-2 border-l-2 border-[var(--jarvis-accent)]/40">
                        <div>
                          <label className="block text-xs mb-1" style={{ color: 'var(--jarvis-text-dim)' }}>Wake Word Model</label>
                          <select
                            value={localSettings.voice.wakeWord || 'hey_jarvis'}
                            onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, wakeWord: e.target.value } })}
                            className="w-full px-2.5 py-1.5 rounded text-xs border border-white/10 focus:border-[var(--jarvis-accent)] focus:outline-none"
                            style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--jarvis-text)' }}
                          >
                            <option value="hey_jarvis" style={{ backgroundColor: '#0c101d' }}>Hey Jarvis (Default)</option>
                            <option value="jarvis" style={{ backgroundColor: '#0c101d' }}>Jarvis</option>
                            <option value="alexa" style={{ backgroundColor: '#0c101d' }}>Alexa</option>
                            <option value="hey_siri" style={{ backgroundColor: '#0c101d' }}>Hey Siri</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs mb-1" style={{ color: 'var(--jarvis-text-dim)' }}>
                            Wake Sensitivity: {(localSettings.voice.wakeWordSensitivity || 0.5).toFixed(2)}
                          </label>
                          <input
                            type="range" min="0.1" max="0.9" step="0.05"
                            value={localSettings.voice.wakeWordSensitivity || 0.5}
                            onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, wakeWordSensitivity: parseFloat(e.target.value) } })}
                            className="w-full accent-[var(--jarvis-accent)]"
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Clap Trigger Controls */}
                  <div className="pt-2 border-t border-white/10">
                    <div className="flex items-center justify-between mb-3">
                      <label className="text-sm font-semibold" style={{ color: 'var(--jarvis-text)' }}>Clap Wake Trigger</label>
                      <button
                        onClick={() => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, clapEnabled: !localSettings.voice.clapEnabled } })}
                        className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${localSettings.voice.clapEnabled ? 'bg-[var(--jarvis-accent)]' : 'bg-white/20'}`}
                      >
                        <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300"
                          style={{ transform: localSettings.voice.clapEnabled ? 'translateX(22px)' : 'translateX(2px)' }}
                        />
                      </button>
                    </div>

                    {localSettings.voice.clapEnabled && (
                      <div className="space-y-3 pl-2 border-l-2 border-amber-500/40">
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-xs mb-1" style={{ color: 'var(--jarvis-text-dim)' }}>Trigger Mode</label>
                            <select
                              value={localSettings.voice.clapMode || 'double'}
                              onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, clapMode: e.target.value as 'single' | 'double' } })}
                              className="w-full px-2.5 py-1.5 rounded text-xs border border-white/10 focus:border-[var(--jarvis-accent)] focus:outline-none"
                              style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--jarvis-text)' }}
                            >
                              <option value="single" style={{ backgroundColor: '#0c101d' }}>Single Clap</option>
                              <option value="double" style={{ backgroundColor: '#0c101d' }}>Double Clap</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs mb-1" style={{ color: 'var(--jarvis-text-dim)' }}>
                              Sensitivity: {(localSettings.voice.clapSensitivity || 0.7).toFixed(2)}
                            </label>
                            <input
                              type="range" min="0.1" max="1.0" step="0.05"
                              value={localSettings.voice.clapSensitivity || 0.7}
                              onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, clapSensitivity: parseFloat(e.target.value) } })}
                              className="w-full accent-amber-500"
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Microphone & Self-Voice Barge-In Controls */}
                  <div className="pt-2 border-t border-white/10 space-y-3">
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--jarvis-text-dim)' }}>
                        Microphone Sensitivity: {(localSettings.voice.micSensitivity || 0.8).toFixed(2)}
                      </label>
                      <input
                        type="range" min="0.1" max="1.0" step="0.05"
                        value={localSettings.voice.micSensitivity || 0.8}
                        onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, micSensitivity: parseFloat(e.target.value) } })}
                        className="w-full accent-[var(--jarvis-accent)]"
                      />
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <div>
                        <div className="text-xs font-semibold" style={{ color: 'var(--jarvis-text)' }}>Self-Voice Barge-In Interrupt</div>
                        <div className="text-[11px]" style={{ color: 'var(--jarvis-text-dim)' }}>Ignores speaker audio & only interrupts when user speaks over TTS</div>
                      </div>
                      <button
                        onClick={() => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, bargeInEnabled: !localSettings.voice.bargeInEnabled } })}
                        className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${localSettings.voice.bargeInEnabled ? 'bg-[var(--jarvis-accent)]' : 'bg-white/20'}`}
                      >
                        <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300"
                          style={{ transform: localSettings.voice.bargeInEnabled ? 'translateX(22px)' : 'translateX(2px)' }}
                        />
                      </button>
                    </div>

                    {localSettings.voice.bargeInEnabled && (
                      <div>
                        <label className="block text-xs mb-1" style={{ color: 'var(--jarvis-text-dim)' }}>
                          Barge-In Sensitivity: {(localSettings.voice.bargeInSensitivity || 0.7).toFixed(2)}
                        </label>
                        <input
                          type="range" min="0.1" max="1.0" step="0.05"
                          value={localSettings.voice.bargeInSensitivity || 0.7}
                          onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, bargeInSensitivity: parseFloat(e.target.value) } })}
                          className="w-full accent-[var(--jarvis-accent)]"
                        />
                      </div>
                    )}
                  </div>
                </div>
              </section>

              {/* AI Section */}
              <section>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>AI Model</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Model</label>
                    <select
                      value={localSettings.ai.model}
                      onChange={(e) => setLocalSettings({ ...localSettings, ai: { ...localSettings.ai, model: e.target.value } })}
                      className="w-full px-3 py-2 rounded-lg text-sm border border-white/10 focus:border-[var(--jarvis-accent)] focus:outline-none transition-colors"
                      style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--jarvis-text)' }}
                    >
                      {MODEL_OPTIONS.map((m) => <option key={m.value} value={m.value} style={{ backgroundColor: '#0c101d', color: '#fff' }}>{m.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>
                      Temperature: {localSettings.ai.temperature.toFixed(1)}
                    </label>
                    <input
                      type="range" min="0" max="1" step="0.1"
                      value={localSettings.ai.temperature}
                      onChange={(e) => setLocalSettings({ ...localSettings, ai: { ...localSettings.ai, temperature: parseFloat(e.target.value) } })}
                      className="w-full accent-[var(--jarvis-accent)]"
                    />
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>OpenRouter API Key (optional)</label>
                    <input
                      type="password"
                      value={localSettings.ai.openrouterApiKey || ''}
                      onChange={(e) => setLocalSettings({ ...localSettings, ai: { ...localSettings.ai, openrouterApiKey: e.target.value } })}
                      placeholder="sk-or-v1-..."
                      className="w-full px-3 py-2 rounded-lg text-sm border border-white/10 focus:border-[var(--jarvis-accent)] focus:outline-none transition-colors"
                      style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--jarvis-text)' }}
                    />
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>OpenAI API Key (optional)</label>
                    <input
                      type="password"
                      value={localSettings.ai.openaiApiKey || ''}
                      onChange={(e) => setLocalSettings({ ...localSettings, ai: { ...localSettings.ai, openaiApiKey: e.target.value } })}
                      placeholder="sk-..."
                      className="w-full px-3 py-2 rounded-lg text-sm border border-white/10 focus:border-[var(--jarvis-accent)] focus:outline-none transition-colors"
                      style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--jarvis-text)' }}
                    />
                  </div>
                </div>
              </section>

              {/* Display Section */}
              <section>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Display</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm" style={{ color: 'var(--jarvis-text)' }}>Always on Top</label>
                    <button
                      onClick={() => setLocalSettings({ ...localSettings, display: { ...localSettings.display, alwaysOnTop: !localSettings.display.alwaysOnTop } })}
                      className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${localSettings.display.alwaysOnTop ? 'bg-[var(--jarvis-accent)]' : 'bg-white/20'}`}
                    >
                      <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300"
                        style={{ transform: localSettings.display.alwaysOnTop ? 'translateX(22px)' : 'translateX(2px)' }}
                      />
                    </button>
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Screenshot Monitor</label>
                    <select
                      value={localSettings.display.selectedMonitor ?? 'all'}
                      onChange={(e) => {
                        const val = e.target.value
                        setLocalSettings({
                          ...localSettings,
                          display: {
                            ...localSettings.display,
                            selectedMonitor: val === 'all' ? 'all' : parseInt(val, 10)
                          }
                        })
                      }}
                      className="w-full px-3 py-2 rounded-lg text-sm border border-white/10 focus:border-[var(--jarvis-accent)] focus:outline-none transition-colors"
                      style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--jarvis-text)' }}
                    >
                      <option value="all" style={{ backgroundColor: '#0c101d', color: '#fff' }}>All Monitors (Combined)</option>
                      {monitors.map((m) => (
                        <option key={m.index} value={String(m.index)} style={{ backgroundColor: '#0c101d', color: '#fff' }}>
                          Monitor {m.index + 1} ({m.width}x{m.height}){m.primary ? ' [Primary]' : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </section>

              {/* Hand Control Section */}
              <section>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Hand Gesture Control</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm" style={{ color: 'var(--jarvis-text)' }}>Enable Cursor Control</label>
                    <button
                      onClick={() => setLocalSettings({
                        ...localSettings,
                        handControl: { ...localSettings.handControl, enabled: !localSettings.handControl.enabled }
                      })}
                      className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${localSettings.handControl?.enabled ? 'bg-[var(--jarvis-accent)]' : 'bg-white/20'}`}
                    >
                      <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300"
                        style={{ transform: localSettings.handControl?.enabled ? 'translateX(22px)' : 'translateX(2px)' }}
                      />
                    </button>
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Sensitivity ({localSettings.handControl?.sensitivity.toFixed(1)})</label>
                    <input
                      type="range"
                      min="0.5"
                      max="3.0"
                      step="0.1"
                      value={localSettings.handControl?.sensitivity ?? 1.5}
                      onChange={(e) => setLocalSettings({
                        ...localSettings,
                        handControl: { ...localSettings.handControl, sensitivity: parseFloat(e.target.value) }
                      })}
                      className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[var(--jarvis-accent)]"
                    />
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Cursor Smoothing ({localSettings.handControl?.smoothing.toFixed(2)})</label>
                    <input
                      type="range"
                      min="0.05"
                      max="0.95"
                      step="0.05"
                      value={localSettings.handControl?.smoothing ?? 0.5}
                      onChange={(e) => setLocalSettings({
                        ...localSettings,
                        handControl: { ...localSettings.handControl, smoothing: parseFloat(e.target.value) }
                      })}
                      className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[var(--jarvis-accent)]"
                    />
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Pinch Threshold ({localSettings.handControl?.pinchThreshold.toFixed(2)})</label>
                    <input
                      type="range"
                      min="0.15"
                      max="0.55"
                      step="0.01"
                      value={localSettings.handControl?.pinchThreshold ?? 0.32}
                      onChange={(e) => setLocalSettings({
                        ...localSettings,
                        handControl: { ...localSettings.handControl, pinchThreshold: parseFloat(e.target.value) }
                      })}
                      className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[var(--jarvis-accent)]"
                    />
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Scroll Speed ({localSettings.handControl?.scrollSpeed.toFixed(0)})</label>
                    <input
                      type="range"
                      min="10"
                      max="100"
                      step="5"
                      value={localSettings.handControl?.scrollSpeed ?? 40}
                      onChange={(e) => setLocalSettings({
                        ...localSettings,
                        handControl: { ...localSettings.handControl, scrollSpeed: parseInt(e.target.value, 10) }
                      })}
                      className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[var(--jarvis-accent)]"
                    />
                  </div>

                  <div>
                    <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Select Active Camera</label>
                    <select
                      value={localSettings.handControl?.cameraDevice ?? ''}
                      onChange={(e) => setLocalSettings({
                        ...localSettings,
                        handControl: { ...localSettings.handControl, cameraDevice: e.target.value }
                      })}
                      className="w-full px-3 py-2 rounded-lg text-sm border border-white/10 focus:border-[var(--jarvis-accent)] focus:outline-none transition-colors"
                      style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--jarvis-text)' }}
                    >
                      <option value="" style={{ backgroundColor: '#0c101d', color: '#fff' }}>Default Camera Device</option>
                      {cameras.map((c, idx) => (
                        <option key={c.deviceId} value={c.deviceId} style={{ backgroundColor: '#0c101d', color: '#fff' }}>
                          {c.label || `Camera ${idx + 1}`}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </section>

              {/* About */}
              <section>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>About</h3>
                <div className="space-y-1.5 text-xs" style={{ color: 'var(--jarvis-text-dim)' }}>
                  <p><span className="font-medium" style={{ color: 'var(--jarvis-text)' }}>JARVIS</span> v1.0.0</p>
                  <p>AI Orchestration System</p>
                  <p>Built with Electron, React, FastAPI, SQLAlchemy, and ChromaDB</p>
                </div>
              </section>
            </>
          )}

          {activeTab === 'orchestrator' && (
            <div className="space-y-6 animate-fade-in">
              <section>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Live Provider Rankings</h3>
                <div className="space-y-3">
                  {rankings.length === 0 ? (
                    <p className="text-sm text-center py-4" style={{ color: 'var(--jarvis-text-dim)' }}>Loading provider rankings...</p>
                  ) : (
                    rankings.map((r, index) => (
                      <div key={r.provider} className="p-3.5 rounded-xl border border-white/5 bg-white/5 flex flex-col gap-2">
                        <div className="flex justify-between items-start">
                          <div>
                            <span className="text-sm font-semibold uppercase tracking-wide mr-2" style={{ color: index === 0 ? 'var(--jarvis-accent)' : 'var(--jarvis-text)' }}>
                              #{index + 1} {r.provider}
                            </span>
                            <span className="text-xs" style={{ color: 'var(--jarvis-text-dim)' }}>({r.model})</span>
                          </div>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${r.circuit === 'CLOSED' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'}`}>
                            {r.circuit === 'CLOSED' ? 'HEALTHY' : 'TRIPPED'}
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 mt-1 text-xs">
                          <div>
                            <p style={{ color: 'var(--jarvis-text-dim)' }}>Latency</p>
                            <p className="font-semibold text-sm" style={{ color: 'var(--jarvis-text)' }}>{r.latency} ms</p>
                          </div>
                          <div>
                            <p style={{ color: 'var(--jarvis-text-dim)' }}>Throughput</p>
                            <p className="font-semibold text-sm" style={{ color: 'var(--jarvis-text)' }}>{r.throughput} t/s</p>
                          </div>
                          <div>
                            <p style={{ color: 'var(--jarvis-text-dim)' }}>Success Rate</p>
                            <p className="font-semibold text-sm" style={{ color: 'var(--jarvis-text)' }}>{r.success_rate}%</p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>

              <section>
                <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Routing Log</h3>
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1 custom-scrollbar text-xs">
                  {routerMetrics.length === 0 ? (
                    <p className="text-center py-4" style={{ color: 'var(--jarvis-text-dim)' }}>No routing events recorded.</p>
                  ) : (
                    routerMetrics.map((m) => (
                      <div key={m.id} className="p-2.5 rounded-lg border border-white/5 bg-white/[0.02] flex justify-between items-center">
                        <div>
                          <p className="font-medium" style={{ color: 'var(--jarvis-text)' }}>
                            Routed to {m.selected_provider}
                          </p>
                          <p className="text-[10px]" style={{ color: 'var(--jarvis-text-dim)' }}>
                            {m.selected_model}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="font-semibold" style={{ color: m.success ? 'var(--jarvis-accent)' : '#f87171' }}>
                            {m.latency} ms
                          </p>
                          {m.fallback_count > 0 && (
                            <p className="text-[9px] text-amber-400">
                              Failovers: {m.fallback_count}
                            </p>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>
            </div>
          )}

          {activeTab === 'brain' && (
            <div className="space-y-6 animate-fade-in">
              <div className="flex justify-between items-center">
                <div>
                  <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--jarvis-accent)' }}>Memory Management</h3>
                  <p className="text-[11px]" style={{ color: 'var(--jarvis-text-dim)' }}>Locally stored concepts, corrections, and solutions.</p>
                </div>
                <button
                  onClick={async () => {
                    setConsolidating(true);
                    let port = 8000;
                    const api = (window as any).electronAPI;
                    if (api?.getSystemInfo) {
                      try {
                        const info = await api.getSystemInfo();
                        if (info && typeof info.backendPort === 'number') port = info.backendPort;
                      } catch(e) {}
                    }
                    try {
                      await fetch(`http://127.0.0.1:${port}/brain/consolidate`, { method: 'POST' });
                      setTimeout(() => {
                        setConsolidating(false);
                        fetchDashboardData();
                      }, 2000);
                    } catch(e) {
                      setConsolidating(false);
                    }
                  }}
                  disabled={consolidating}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all disabled:opacity-50"
                  style={{ color: 'var(--jarvis-accent)', borderColor: 'var(--jarvis-accent)', backgroundColor: 'transparent' }}
                >
                  {consolidating ? 'Consolidating...' : 'Consolidate Memories'}
                </button>
              </div>

              {/* Stored facts */}
              <section>
                <h4 className="text-xs font-semibold mb-2.5" style={{ color: 'var(--jarvis-text)' }}>Learned Preferences & Facts ({brainData.memories.length})</h4>
                <div className="max-h-36 overflow-y-auto space-y-2 pr-1 custom-scrollbar text-xs">
                  {brainData.memories.length === 0 ? (
                    <p style={{ color: 'var(--jarvis-text-dim)' }}>No memories stored yet.</p>
                  ) : (
                    brainData.memories.map((m) => (
                      <div key={m.id} className="p-2.5 rounded-lg border border-white/5 bg-white/[0.02] flex justify-between items-center">
                        <span style={{ color: 'var(--jarvis-text)' }}>{m.content}</span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${
                          m.importance === 'critical' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                          m.importance === 'high' ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30' :
                          m.importance === 'medium' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' :
                          'bg-white/10 text-white/50'
                        }`}>
                          {m.importance}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </section>

              {/* Lessons Learned */}
              <section>
                <h4 className="text-xs font-semibold mb-2.5" style={{ color: 'var(--jarvis-text)' }}>Corrections History / Lessons ({brainData.lessons.length})</h4>
                <div className="max-h-36 overflow-y-auto space-y-2 pr-1 custom-scrollbar text-xs">
                  {brainData.lessons.length === 0 ? (
                    <p style={{ color: 'var(--jarvis-text-dim)' }}>No corrections recorded.</p>
                  ) : (
                    brainData.lessons.map((l) => (
                      <div key={l.id} className="p-2.5 rounded-lg border border-rose-500/10 bg-rose-500/5 space-y-1">
                        <div className="flex justify-between text-[10px]" style={{ color: 'var(--jarvis-accent)' }}>
                          <span className="font-semibold">Trigger: "{l.trigger_keywords}"</span>
                        </div>
                        <p style={{ color: 'var(--jarvis-text-dim)' }}>
                          <span className="text-rose-400 font-medium">Error:</span> {l.error_description}
                        </p>
                        <p style={{ color: 'var(--jarvis-text)' }}>
                          <span className="text-emerald-400 font-medium">Correction:</span> {l.correction}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </section>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-white/10">
          <button onClick={handleClose} className="px-4 py-2 rounded-lg text-sm border border-white/10 hover:bg-white/10 transition-colors" style={{ color: 'var(--jarvis-text)' }}>Cancel</button>
          <button onClick={handleSave} className="px-4 py-2 rounded-lg text-sm font-medium transition-colors" style={{ backgroundColor: 'var(--jarvis-accent)', color: '#0a0e1a' }}>Save Changes</button>
        </div>
      </div>
    </div>
  )
}
