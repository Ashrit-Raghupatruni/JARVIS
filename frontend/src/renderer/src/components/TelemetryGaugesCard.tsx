import React, { useEffect, useState } from 'react'
import { Activity } from 'lucide-react'

interface TelemetryData {
  cpuUsage: number
  ramUsage: number
  ramUsedGb: number
  ramTotalGb: number
  diskUsage: number
  diskUsedGb: number
  diskTotalGb: number
  batteryPercent: number
  batteryPlugged: boolean
  isOnline: boolean
}

export const TelemetryGaugesCard: React.FC = () => {
  const [data, setData] = useState<TelemetryData>({
    cpuUsage: 18,
    ramUsage: 54,
    ramUsedGb: 8.6,
    ramTotalGb: 16.0,
    diskUsage: 41,
    diskUsedGb: 210,
    diskTotalGb: 512,
    batteryPercent: 92,
    batteryPlugged: true,
    isOnline: true
  })

  const getHost = () =>
    typeof window !== 'undefined' && window.location.hostname && window.location.hostname !== 'localhost'
      ? window.location.hostname
      : '127.0.0.1'

  useEffect(() => {
    let isMounted = true

    const fetchTelemetry = async () => {
      try {
        const res = await fetch(`http://${getHost()}:8000/api/ui/performance`)
        if (res.ok && isMounted) {
          const json = await res.json()
          setData({
            cpuUsage: Math.round(json.cpu_usage_percent ?? 0),
            ramUsage: Math.round(json.ram_usage_percent ?? 0),
            ramUsedGb: json.ram_used_gb ?? 8.6,
            ramTotalGb: json.ram_total_gb ?? 16.0,
            diskUsage: Math.round(json.disk_usage_percent ?? 42),
            diskUsedGb: json.disk_used_gb ?? 212,
            diskTotalGb: json.disk_total_gb ?? 512,
            batteryPercent: Math.round(json.battery_percent ?? 90),
            batteryPlugged: json.battery_plugged ?? true,
            isOnline: true
          })
        }
      } catch {
        if (isMounted) {
          setData((prev) => ({ ...prev, isOnline: false }))
        }
      }
    }

    fetchTelemetry()
    const interval = setInterval(fetchTelemetry, 3000)
    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

  const renderGauge = (
    label: string,
    percent: number,
    subtext: string,
    strokeColor = '#00e5ff',
    secondaryColor = '#1e3a8a'
  ) => {
    const radius = 24
    const circumference = 2 * Math.PI * radius
    const strokeDashoffset = circumference - (Math.min(100, Math.max(0, percent)) / 100) * circumference

    return (
      <div className="flex flex-col items-center bg-slate-900/40 rounded-xl p-2.5 border border-white/5 shadow-inner">
        <div className="relative w-16 h-16 flex items-center justify-center">
          <svg className="w-full h-full -rotate-90 transform" viewBox="0 0 60 60">
            {/* Background track ring */}
            <circle
              cx="30"
              cy="30"
              r={radius}
              stroke="rgba(255, 255, 255, 0.08)"
              strokeWidth="5"
              fill="transparent"
            />
            {/* Animated Progress ring */}
            <circle
              cx="30"
              cy="30"
              r={radius}
              stroke={strokeColor}
              strokeWidth="5"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              fill="transparent"
              className="transition-all duration-700 ease-out"
              style={{
                filter: `drop-shadow(0 0 4px ${strokeColor})`
              }}
            />
          </svg>
          {/* Centered Percentage */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xs font-bold font-mono text-white tracking-tight">
              {percent}%
            </span>
          </div>
        </div>

        {/* Gauge Label */}
        <span className="mt-1 text-[11px] font-semibold text-slate-200 tracking-wider">
          {label}
        </span>

        {/* Subtext info */}
        <span className="text-[10px] text-slate-400 font-mono mt-0.5 truncate max-w-[80px]">
          {subtext}
        </span>

        {/* Mini linear progress bar */}
        <div className="w-full bg-slate-800/80 h-1 rounded-full mt-1.5 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${Math.min(100, Math.max(0, percent))}%`,
              background: `linear-gradient(90deg, ${secondaryColor}, ${strokeColor})`
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="w-full bg-slate-950/40 backdrop-blur-2xl border border-blue-500/20 rounded-2xl p-4 shadow-[0_8px_32px_0_rgba(0,0,0,0.37)]">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-bold tracking-[0.2em] text-slate-200 uppercase font-mono">
            TELEMETRY
          </h3>
        </div>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20">
          <span className={`w-1.5 h-1.5 rounded-full ${data.isOnline ? 'bg-cyan-400 shadow-[0_0_6px_#00e5ff]' : 'bg-rose-400'}`} />
          <span className="text-[10px] font-mono text-cyan-300">
            {data.isOnline ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* 2x2 Circular Gauges Grid */}
      <div className="grid grid-cols-2 gap-3 mt-3">
        {renderGauge('CPU', data.cpuUsage, '3.2 GHz', '#00e5ff', '#0284c7')}
        {renderGauge('RAM', data.ramUsage, `${data.ramUsedGb} / ${data.ramTotalGb} GB`, '#38bdf8', '#1e40af')}
        {renderGauge('DISK C:', data.diskUsage, `${data.diskUsedGb} / ${data.diskTotalGb} GB`, '#60a5fa', '#2563eb')}
        {renderGauge('BATTERY', data.batteryPercent, data.batteryPlugged ? 'Charging' : 'On Battery', '#34d399', '#059669')}
      </div>
    </div>
  )
}
