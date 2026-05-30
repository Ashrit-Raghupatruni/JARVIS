import { useState, useEffect, useCallback } from 'react'
import { useAppStore } from '../stores/appStore'
import type { Settings } from '../types'

const VOICE_OPTIONS = [
  { value: 'en-US-GuyNeural', label: 'Guy (US Male)' },
  { value: 'en-US-AriaNeural', label: 'Aria (US Female)' },
  { value: 'en-US-JennyNeural', label: 'Jenny (US Female)' },
  { value: 'en-GB-RyanNeural', label: 'Ryan (UK Male)' },
  { value: 'en-GB-SoniaNeural', label: 'Sonia (UK Female)' },
  { value: 'en-AU-WilliamNeural', label: 'William (AU Male)' },
  { value: 'en-IN-PrabhatNeural', label: 'Prabhat (IN Male)' },
]

const MODEL_OPTIONS = [
  { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash (Primary)' },
  { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (Capable)' },
  { value: 'gpt-4o', label: 'GPT-4o (Fallback / OpenAI)' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini (OpenAI)' },
]


export default function SettingsPanel() {
  const { showSettings, setShowSettings, settings, updateVoiceSettings, updateAISettings, updateDisplaySettings } = useAppStore()
  const [localSettings, setLocalSettings] = useState<Settings>(settings)

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
    setShowSettings(false)
  }, [localSettings, updateVoiceSettings, updateAISettings, updateDisplaySettings, setShowSettings])

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
          <h2 className="text-lg font-semibold" style={{ color: 'var(--jarvis-text)' }}>Settings</h2>
          <button onClick={handleClose} className="p-1.5 rounded-lg hover:bg-white/10 transition-colors" style={{ color: 'var(--jarvis-text-dim)' }}>
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-6 max-h-[60vh] overflow-y-auto custom-scrollbar">
          {/* Voice Section */}
          <section>
            <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Voice</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>TTS Voice</label>
                <select
                  value={localSettings.voice.ttsVoice}
                  onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, ttsVoice: e.target.value } })}
                  className="w-full px-3 py-2 rounded-lg text-sm border border-white/10 focus:border-[var(--jarvis-accent)] focus:outline-none transition-colors"
                  style={{ backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--jarvis-text)' }}
                >
                  {VOICE_OPTIONS.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>
                  Speech Rate: {localSettings.voice.speechRate.toFixed(1)}x
                </label>
                <input
                  type="range" min="0.5" max="2.0" step="0.1"
                  value={localSettings.voice.speechRate}
                  onChange={(e) => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, speechRate: parseFloat(e.target.value) } })}
                  className="w-full accent-[var(--jarvis-accent)]"
                />
              </div>

              <div className="flex items-center justify-between">
                <label className="text-sm" style={{ color: 'var(--jarvis-text)' }}>Wake Word Detection</label>
                <button
                  onClick={() => setLocalSettings({ ...localSettings, voice: { ...localSettings.voice, wakeWordEnabled: !localSettings.voice.wakeWordEnabled } })}
                  className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${localSettings.voice.wakeWordEnabled ? 'bg-[var(--jarvis-accent)]' : 'bg-white/20'}`}
                >
                  <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300"
                    style={{ transform: localSettings.voice.wakeWordEnabled ? 'translateX(22px)' : 'translateX(2px)' }}
                  />
                </button>
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
                  {MODEL_OPTIONS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
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
            </div>
          </section>

          {/* Display Section */}
          <section>
            <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Display</h3>
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
          </section>

          {/* About */}
          <section>
            <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>About</h3>
            <div className="space-y-1.5 text-xs" style={{ color: 'var(--jarvis-text-dim)' }}>
              <p><span className="font-medium" style={{ color: 'var(--jarvis-text)' }}>JARVIS</span> v1.0.0</p>
              <p>AI Desktop Assistant</p>
              <p>Built with React, Electron, FastAPI, and OpenAI</p>
            </div>
          </section>
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
