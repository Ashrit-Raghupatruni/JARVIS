import React from 'react'
import type { Settings } from '../../types'

export const VOICE_OPTIONS = [
  { value: 'piper:en_US-lessac-low', label: 'Piper Lessac (Local Neural / Offline 0ms Latency)' },
  { value: 'en-GB-RyanNeural', label: 'Ryan (Edge-TTS / UK Male)' },
  { value: 'en-US-GuyNeural', label: 'Guy (Edge-TTS / US Male)' },
  { value: 'en-AU-WilliamNeural', label: 'William (Edge-TTS / AU Male)' },
  { value: 'en-IN-PrabhatNeural', label: 'Prabhat (Edge-TTS / IN Male)' },
]

export const MODEL_OPTIONS = [
  { value: 'qwen2.5-coder:3b', label: 'Qwen 2.5 Coder 3B (Ollama / Local)' },
  { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (Google Cloud)' },
  { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash (Cloud)' },
  { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (Cloud)' },
  { value: 'gpt-4o', label: 'GPT-4o (OpenAI)' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini (OpenAI)' },
  { value: 'llama-3.3-70b-versatile', label: 'Llama 3.3 70B (Groq Fast)' },
  { value: 'meta-llama/llama-3.3-70b-instruct:free', label: 'Llama 3.3 70B (OpenRouter Free)' },
  { value: 'deepseek/deepseek-chat', label: 'DeepSeek V3 (OpenRouter)' },
]

interface GeneralSettingsTabProps {
  localSettings: Settings
  setLocalSettings: React.Dispatch<React.SetStateAction<Settings>>
}

export const GeneralSettingsTab: React.FC<GeneralSettingsTabProps> = ({
  localSettings,
  setLocalSettings
}) => {
  return (
    <div className="space-y-6">
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

      {/* About */}
      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>About</h3>
        <div className="space-y-1.5 text-xs" style={{ color: 'var(--jarvis-text-dim)' }}>
          <p><span className="font-medium" style={{ color: 'var(--jarvis-text)' }}>JARVIS</span> v1.0.0</p>
          <p>AI Orchestration System</p>
          <p>Built with Electron, React, FastAPI, SQLAlchemy, and ChromaDB</p>
        </div>
      </section>
    </div>
  )
}
export default GeneralSettingsTab
