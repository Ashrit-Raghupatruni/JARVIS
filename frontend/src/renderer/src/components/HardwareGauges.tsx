import React, { useEffect, useState } from 'react'
import { Cpu, HardDrive, Activity, Wifi, ShieldCheck, QrCode, Smartphone } from 'lucide-react'
import { QRPairingModal } from './QRPairingModal'

export interface HardwareMetrics {
  cpuUsage: number
  ramUsage: number
  ramUsedGb: number
  ramTotalGb: number
  gpuVramUsedGb: number
  gpuVramTotalGb: number
  gpuUsage: number
  networkLatencyMs: number
  status: string
}

export default function HardwareGauges() {
  const [metrics, setMetrics] = useState<HardwareMetrics>({
    cpuUsage: 0,
    ramUsage: 0,
    ramUsedGb: 0,
    ramTotalGb: 0,
    gpuVramUsedGb: 0,
    gpuVramTotalGb: 1,
    gpuUsage: 0,
    networkLatencyMs: 0,
    status: 'CONNECTING'
  })
  const [showQRModal, setShowQRModal] = useState<boolean>(false)

  const getHost = () => typeof window !== 'undefined' && window.location.hostname && window.location.hostname !== 'localhost' ? window.location.hostname : '127.0.0.1'

  // Poll real hardware metrics from API
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch(`http://${getHost()}:8000/api/ui/performance`)
        if (res.ok) {
          const data = await res.json()
          setMetrics({
            cpuUsage: data.cpu_usage_percent ?? 0,
            ramUsage: data.ram_usage_percent ?? 0,
            ramUsedGb: data.ram_used_gb ?? 0,
            ramTotalGb: data.ram_total_gb ?? 0,
            gpuVramUsedGb: data.gpu_vram_used_gb ?? 0,
            gpuVramTotalGb: data.gpu_vram_total_gb ?? 1,
            gpuUsage: data.gpu_usage_percent ?? 0,
            networkLatencyMs: data.network_latency_ms ?? 0,
            status: 'ONLINE'
          })
        } else {
          setMetrics(prev => ({ ...prev, status: 'OFFLINE' }))
        }
      } catch {
        // Genuine offline state indication, zero fake random animations
        setMetrics(prev => ({ ...prev, status: 'OFFLINE' }))
      }
    }

    fetchMetrics()
    const interval = setInterval(fetchMetrics, 3000)
    return () => clearInterval(interval)
  }, [])

  return (
    <>
      <div className="bg-[rgba(10,20,38,0.75)] backdrop-blur-md border border-[rgba(0,229,255,0.18)] rounded-xl p-3 shadow-lg hover:border-[rgba(0,229,255,0.35)] transition-all">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-[#00e5ff] animate-pulse" />
            <span className="text-xs font-semibold text-[#00e5ff] tracking-wider uppercase">System Telemetry</span>
          </div>
          
          <div className="flex items-center gap-2">
            {/* 1-Click Connect Mobile QR Button */}
            <button
              onClick={() => setShowQRModal(true)}
              className="flex items-center gap-1 bg-[rgba(0,229,255,0.12)] border border-[rgba(0,229,255,0.35)] hover:bg-[rgba(0,229,255,0.25)] text-[#00e5ff] px-2 py-0.5 rounded-lg transition-all text-[10px] font-mono font-semibold"
              title="Open QR Code to Pair Mobile Companion"
            >
              <QrCode className="w-3 h-3" />
              <Smartphone className="w-3 h-3" />
              <span>PAIR PHONE</span>
            </button>

            <div className="flex items-center gap-1.5 bg-[rgba(0,230,118,0.12)] border border-[rgba(0,230,118,0.3)] px-2 py-0.5 rounded-full">
              <ShieldCheck className="w-3 h-3 text-[#00e676]" />
              <span className="text-[10px] font-mono font-semibold text-[#00e676]">{metrics.status}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {/* CPU Usage */}
          <div className="bg-[rgba(15,30,56,0.5)] p-2 rounded-lg border border-[rgba(0,229,255,0.1)]">
            <div className="flex items-center justify-between text-[11px] text-[#b0bec5] mb-1">
              <span className="flex items-center gap-1"><Cpu className="w-3 h-3 text-[#00e5ff]" /> CPU</span>
              <span className="font-mono text-[#00e5ff] font-bold">{metrics.cpuUsage.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-gradient-to-r from-[#00aeff] to-[#00e5ff] h-full transition-all duration-500 rounded-full"
                style={{ width: `${metrics.cpuUsage}%` }}
              />
            </div>
          </div>

          {/* RAM Usage */}
          <div className="bg-[rgba(15,30,56,0.5)] p-2 rounded-lg border border-[rgba(0,229,255,0.1)]">
            <div className="flex items-center justify-between text-[11px] text-[#b0bec5] mb-1">
              <span className="flex items-center gap-1"><HardDrive className="w-3 h-3 text-[#00aeff]" /> RAM</span>
              <span className="font-mono text-[#00aeff] font-bold">{metrics.ramUsedGb.toFixed(1)}GB</span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-gradient-to-r from-[#00aeff] to-[#00e5ff] h-full transition-all duration-500 rounded-full"
                style={{ width: `${metrics.ramUsage}%` }}
              />
            </div>
          </div>

          {/* GPU VRAM */}
          <div className="bg-[rgba(15,30,56,0.5)] p-2 rounded-lg border border-[rgba(0,229,255,0.1)]">
            <div className="flex items-center justify-between text-[11px] text-[#b0bec5] mb-1">
              <span className="flex items-center gap-1"><Activity className="w-3 h-3 text-[#ffaa00]" /> VRAM</span>
              <span className="font-mono text-[#ffaa00] font-bold">{metrics.gpuVramUsedGb.toFixed(1)}GB</span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-gradient-to-r from-[#ffaa00] to-[#00e5ff] h-full transition-all duration-500 rounded-full"
                style={{ width: `${(metrics.gpuVramUsedGb / metrics.gpuVramTotalGb) * 100}%` }}
              />
            </div>
          </div>

          {/* Network Latency */}
          <div className="bg-[rgba(15,30,56,0.5)] p-2 rounded-lg border border-[rgba(0,229,255,0.1)]">
            <div className="flex items-center justify-between text-[11px] text-[#b0bec5] mb-1">
              <span className="flex items-center gap-1"><Wifi className="w-3 h-3 text-[#00e676]" /> Latency</span>
              <span className="font-mono text-[#00e676] font-bold">{Math.round(metrics.networkLatencyMs)}ms</span>
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-gradient-to-r from-[#00e676] to-[#00e5ff] h-full transition-all duration-500 rounded-full"
                style={{ width: `${Math.min(100, (metrics.networkLatencyMs / 100) * 100)}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* QR Pairing Modal */}
      <QRPairingModal isOpen={showQRModal} onClose={() => setShowQRModal(false)} />
    </>
  )
}
