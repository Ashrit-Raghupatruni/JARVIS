import React, { useState, useEffect, useCallback } from 'react'
import { Bluetooth, Lock, Shield, RefreshCw, Search, Sliders, Activity, CheckCircle2, AlertCircle } from 'lucide-react'

interface ProximityTelemetry {
  is_scanning: boolean
  auto_lock_enabled: boolean
  paired_device_address: string | null
  paired_device_name: string | null
  current_smoothed_rssi: number | null
  lock_threshold_dbm: number
  return_threshold_dbm: number
  departure_debounce_seconds: number
  state: 'IN_RANGE' | 'DEPARTED' | 'LOCKED' | 'BIOMETRIC_ARMED'
  distance_category: 'IMMEDIATE' | 'NEAR' | 'FAR' | 'OUT_OF_RANGE'
}

interface ScannedDevice {
  name: string
  address: string
  rssi: number
}

export const BluetoothProximityCard: React.FC = () => {
  const [telemetry, setTelemetry] = useState<ProximityTelemetry | null>(null)
  const [scannedDevices, setScannedDevices] = useState<ScannedDevice[]>([])
  const [isScanning, setIsScanning] = useState(false)
  const [showScanModal, setShowScanModal] = useState(false)
  const [lockThreshold, setLockThreshold] = useState(-82)
  const [returnThreshold, setReturnThreshold] = useState(-65)
  const [debounceSec, setDebounceSec] = useState(7.0)
  const [autoLockEnabled, setAutoLockEnabled] = useState(true)
  const [statusMsg, setStatusMsg] = useState<string | null>(null)

  const getBackendPort = () => 8000
  const getHost = () => {
    if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      return window.location.hostname
    }
    return '127.0.0.1'
  }

  const BASE_URL = `http://${getHost()}:${getBackendPort()}/api/v1/mobile/proximity`

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}/status`)
      if (res.ok) {
        const data = await res.json()
        if (data.status === 'ok' && data.telemetry) {
          setTelemetry(data.telemetry)
          setLockThreshold(data.telemetry.lock_threshold_dbm)
          setReturnThreshold(data.telemetry.return_threshold_dbm)
          setDebounceSec(data.telemetry.departure_debounce_seconds)
          setAutoLockEnabled(data.telemetry.auto_lock_enabled)
        }
      }
    } catch (e) {
      console.error('[BluetoothCard] Failed to fetch proximity status:', e)
    }
  }, [BASE_URL])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 3000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const handleSaveConfig = async () => {
    try {
      setStatusMsg('Saving configuration...')
      const res = await fetch(`${BASE_URL}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          auto_lock_enabled: autoLockEnabled,
          lock_threshold_dbm: lockThreshold,
          return_threshold_dbm: returnThreshold,
          departure_debounce_seconds: debounceSec
        })
      })
      if (res.ok) {
        setStatusMsg('✓ Proximity auto-lock thresholds saved.')
        fetchStatus()
      }
    } catch (e) {
      setStatusMsg(`Error saving config: ${e}`)
    }
  }

  const handleScanDevices = async () => {
    try {
      setIsScanning(true)
      setShowScanModal(true)
      setStatusMsg('Scanning for nearby BLE devices (4.0s)...')
      const res = await fetch(`${BASE_URL}/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timeout_seconds: 4.0 })
      })
      if (res.ok) {
        const data = await res.json()
        setScannedDevices(data.devices || [])
        setStatusMsg(`Discovered ${data.count || 0} nearby BLE device(s).`)
      }
    } catch (e) {
      setStatusMsg(`Scan failed: ${e}`)
    } finally {
      setIsScanning(false)
    }
  }

  const handlePairDevice = async (device: ScannedDevice) => {
    try {
      const res = await fetch(`${BASE_URL}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_address: device.address,
          device_name: device.name || 'Bluetooth Device'
        })
      })
      if (res.ok) {
        setStatusMsg(`✓ Paired with ${device.name || device.address}`)
        setShowScanModal(false)
        fetchStatus()
      }
    } catch (e) {
      setStatusMsg(`Pairing failed: ${e}`)
    }
  }

  const handleLockNow = async () => {
    try {
      setStatusMsg('Triggering immediate workstation lock...')
      await fetch(`${BASE_URL}/lock_now`, { method: 'POST' })
    } catch (e) {
      setStatusMsg(`Lock trigger error: ${e}`)
    }
  }

  const rssi = telemetry?.current_smoothed_rssi ?? -90
  const rssiPercent = Math.min(100, Math.max(0, ((rssi + 100) / 60) * 100))

  return (
    <div className="flex flex-col gap-4 p-4 rounded-xl bg-slate-900/60 border border-cyan-500/20 backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-500/10 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-400">
            <Bluetooth className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold tracking-wider text-cyan-100 uppercase">Bluetooth RSSI Proximity Auto-Lock</h3>
            <p className="text-[11px] text-slate-400">Hardware-Gated Departure Lock & Biometric Wake Interlock</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleScanDevices}
            disabled={isScanning}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 border border-cyan-500/30 text-cyan-300 hover:bg-slate-700 text-xs transition"
          >
            <Search className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} /> Scan BLE
          </button>
          <button
            onClick={handleLockNow}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-950/60 border border-red-500/40 text-red-300 hover:bg-red-900/60 text-xs transition"
            title="Lock PC immediately"
          >
            <Lock className="w-3.5 h-3.5" /> Lock PC
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="px-3 py-2 rounded-lg bg-cyan-950/60 border border-cyan-500/30 text-xs text-cyan-300">
          {statusMsg}
        </div>
      )}

      {/* Telemetry Gauge & Status Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="flex flex-col gap-2 p-3 rounded-xl bg-slate-950/80 border border-slate-800">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-cyan-400" /> Paired Device
            </span>
            <span className="font-mono text-cyan-300 font-semibold">
              {telemetry?.paired_device_name || 'No Device Paired'}
            </span>
          </div>

          {/* RSSI Meter Bar */}
          <div className="flex flex-col gap-1 mt-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-400">Signal Strength (RSSI)</span>
              <span className="font-mono text-slate-200">
                {telemetry?.current_smoothed_rssi ? `${telemetry.current_smoothed_rssi.toFixed(1)} dBm` : 'No Signal'}
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  rssi >= -65 ? 'bg-emerald-400' : rssi >= -82 ? 'bg-amber-400' : 'bg-red-400'
                }`}
                style={{ width: `${rssiPercent}%` }}
              />
            </div>
          </div>

          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800/80 text-[11px]">
            <span className="text-slate-400">Proximity Zone:</span>
            <span className="px-2 py-0.5 rounded bg-cyan-950 border border-cyan-500/30 text-cyan-300 font-mono text-[10px] uppercase">
              {telemetry?.distance_category || 'UNKNOWN'}
            </span>
          </div>
        </div>

        {/* Sliders and Configuration */}
        <div className="flex flex-col gap-2.5 p-3 rounded-xl bg-slate-950/80 border border-slate-800">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium">Auto-Lock on Departure</span>
            <input
              type="checkbox"
              checked={autoLockEnabled}
              onChange={(e) => setAutoLockEnabled(e.target.checked)}
              className="accent-cyan-400 cursor-pointer"
            />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-[11px] text-slate-400">
              <span>Lock Threshold:</span>
              <span className="font-mono text-cyan-300">{lockThreshold} dBm</span>
            </div>
            <input
              type="range"
              min="-95"
              max="-60"
              step="1"
              value={lockThreshold}
              onChange={(e) => setLockThreshold(parseInt(e.target.value))}
              className="accent-cyan-400 h-1 bg-slate-800 rounded-lg cursor-pointer"
            />
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex justify-between text-[11px] text-slate-400">
              <span>Departure Debounce:</span>
              <span className="font-mono text-cyan-300">{debounceSec.toFixed(1)}s</span>
            </div>
            <input
              type="range"
              min="2.0"
              max="20.0"
              step="0.5"
              value={debounceSec}
              onChange={(e) => setDebounceSec(parseFloat(e.target.value))}
              className="accent-cyan-400 h-1 bg-slate-800 rounded-lg cursor-pointer"
            />
          </div>

          <button
            onClick={handleSaveConfig}
            className="mt-1 w-full py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-semibold text-xs transition"
          >
            Save Proximity Settings
          </button>
        </div>
      </div>

      {/* BLE Device Scan Modal */}
      {showScanModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md p-4 rounded-xl bg-slate-900 border border-cyan-500/30 flex flex-col gap-3 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <h4 className="text-sm font-bold text-cyan-100 flex items-center gap-2">
                <Search className="w-4 h-4 text-cyan-400" /> Discovered BLE Devices
              </h4>
              <button
                onClick={() => setShowScanModal(false)}
                className="text-slate-400 hover:text-slate-200 text-xs"
              >
                Close
              </button>
            </div>

            <div className="max-h-60 overflow-y-auto flex flex-col gap-2">
              {scannedDevices.length === 0 ? (
                <div className="py-6 text-center text-xs text-slate-400">
                  {isScanning ? 'Scanning for nearby Bluetooth devices...' : 'No devices discovered. Ensure Bluetooth is active on your phone.'}
                </div>
              ) : (
                scannedDevices.map((dev, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-cyan-500/40 transition"
                  >
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold text-slate-200">{dev.name || 'Unnamed BLE Beacon'}</span>
                      <span className="text-[10px] font-mono text-slate-400">{dev.address} | RSSI: {dev.rssi} dBm</span>
                    </div>
                    <button
                      onClick={() => handlePairDevice(dev)}
                      className="px-2.5 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-[11px] transition"
                    >
                      Pair
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default BluetoothProximityCard
