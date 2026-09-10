import React from 'react'
import type { Settings } from '../../types'

interface DisplaySettingsTabProps {
  localSettings: Settings
  setLocalSettings: React.Dispatch<React.SetStateAction<Settings>>
  monitors: any[]
}

export const DisplaySettingsTab: React.FC<DisplaySettingsTabProps> = ({
  localSettings,
  setLocalSettings,
  monitors
}) => {
  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--jarvis-accent)' }}>Display & Window Options</h3>
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
    </div>
  )
}
export default DisplaySettingsTab
