import React from 'react'
import type { Settings } from '../../types'

interface HandControlSettingsTabProps {
  localSettings: Settings
  setLocalSettings: React.Dispatch<React.SetStateAction<Settings>>
  updateHandControlSettings: (settings: any) => void
  cameras: MediaDeviceInfo[]
}

export const HandControlSettingsTab: React.FC<HandControlSettingsTabProps> = ({
  localSettings,
  setLocalSettings,
  updateHandControlSettings,
  cameras
}) => {
  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Hand Gesture Control</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="text-sm" style={{ color: 'var(--jarvis-text)' }}>Enable Cursor Control</label>
            <button
              onClick={() => {
                const updated = { ...localSettings.handControl, enabled: !localSettings.handControl?.enabled }
                setLocalSettings({ ...localSettings, handControl: updated })
                updateHandControlSettings(updated)
              }}
              className={`relative w-11 h-6 rounded-full transition-colors duration-300 ${localSettings.handControl?.enabled ? 'bg-[var(--jarvis-accent)]' : 'bg-white/20'}`}
            >
              <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-300"
                style={{ transform: localSettings.handControl?.enabled ? 'translateX(22px)' : 'translateX(2px)' }}
              />
            </button>
          </div>

          <div>
            <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Sensitivity ({(localSettings.handControl?.sensitivity ?? 1.6).toFixed(1)}x)</label>
            <input
              type="range"
              min="0.5"
              max="3.0"
              step="0.1"
              value={localSettings.handControl?.sensitivity ?? 1.6}
              onChange={(e) => {
                const val = parseFloat(e.target.value)
                const updated = { ...localSettings.handControl, sensitivity: val }
                setLocalSettings({ ...localSettings, handControl: updated })
                updateHandControlSettings(updated)
              }}
              className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[var(--jarvis-accent)]"
            />
          </div>

          <div>
            <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Cursor Smoothing ({(localSettings.handControl?.smoothing ?? 0.45).toFixed(2)})</label>
            <input
              type="range"
              min="0.05"
              max="0.95"
              step="0.05"
              value={localSettings.handControl?.smoothing ?? 0.45}
              onChange={(e) => {
                const val = parseFloat(e.target.value)
                const updated = { ...localSettings.handControl, smoothing: val }
                setLocalSettings({ ...localSettings, handControl: updated })
                updateHandControlSettings(updated)
              }}
              className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[var(--jarvis-accent)]"
            />
          </div>

          <div>
            <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Pinch Threshold ({(localSettings.handControl?.pinchThreshold ?? 0.32).toFixed(2)})</label>
            <input
              type="range"
              min="0.15"
              max="0.55"
              step="0.01"
              value={localSettings.handControl?.pinchThreshold ?? 0.32}
              onChange={(e) => {
                const val = parseFloat(e.target.value)
                const updated = { ...localSettings.handControl, pinchThreshold: val }
                setLocalSettings({ ...localSettings, handControl: updated })
                updateHandControlSettings(updated)
              }}
              className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[var(--jarvis-accent)]"
            />
          </div>

          <div>
            <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Scroll Speed ({(localSettings.handControl?.scrollSpeed ?? 40).toFixed(0)} px/frame)</label>
            <input
              type="range"
              min="10"
              max="100"
              step="5"
              value={localSettings.handControl?.scrollSpeed ?? 40}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10)
                const updated = { ...localSettings.handControl, scrollSpeed: val }
                setLocalSettings({ ...localSettings, handControl: updated })
                updateHandControlSettings(updated)
              }}
              className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[var(--jarvis-accent)]"
            />
          </div>

          <div>
            <label className="block text-xs mb-1.5" style={{ color: 'var(--jarvis-text-dim)' }}>Select Active Camera</label>
            <select
              value={localSettings.handControl?.cameraDevice ?? ''}
              onChange={(e) => {
                const updated = { ...localSettings.handControl, cameraDevice: e.target.value }
                setLocalSettings({ ...localSettings, handControl: updated })
                updateHandControlSettings(updated)
              }}
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
    </div>
  )
}
export default HandControlSettingsTab
