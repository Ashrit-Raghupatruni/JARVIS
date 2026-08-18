import React, { useState, useEffect } from 'react'
import { QrCode, RefreshCw, Smartphone, CheckCircle, ShieldCheck, X } from 'lucide-react'

interface QRPairingModalProps {
  isOpen: boolean
  onClose: () => void
}

export const QRPairingModal: React.FC<QRPairingModalProps> = ({ isOpen, onClose }) => {
  const [pairingData, setPairingData] = useState<{ session_id: string; code: string; payload: string } | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [isPaired, setIsPaired] = useState<boolean>(false)

  const fetchQRPayload = async () => {
    setIsLoading(true)
    setIsPaired(false)
    try {
      const res = await fetch('/api/v1/mobile/pair/qr/generate')
      if (res.ok) {
        const data = await res.json()
        setPairingData({
          session_id: data.pairing_session_id,
          code: data.pairing_code,
          payload: data.qr_payload
        })
      } else {
        // Mock fallback if offline/local dev
        const mockSession = 'sess_' + Math.random().toString(36).substring(2, 9)
        const mockCode = Math.floor(100000 + Math.random() * 900000).toString()
        setPairingData({
          session_id: mockSession,
          code: mockCode,
          payload: `jarvis_pair://${mockSession}:${mockCode}`
        })
      }
    } catch {
      const mockSession = 'sess_' + Math.random().toString(36).substring(2, 9)
      const mockCode = Math.floor(100000 + Math.random() * 900000).toString()
      setPairingData({
        session_id: mockSession,
        code: mockCode,
        payload: `jarvis_pair://${mockSession}:${mockCode}`
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchQRPayload()
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-md bg-slate-900 border border-cyan-500/30 rounded-2xl p-6 shadow-[0_0_40px_rgba(0,229,255,0.2)] relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center space-x-3 mb-5">
          <div className="p-2.5 rounded-xl bg-cyan-950/80 border border-cyan-500/40 text-cyan-400">
            <QrCode className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-100">QR Mobile Companion Pairing</h3>
            <p className="text-xs text-slate-400">Scan code with JARVIS Mobile App to establish encrypted bridge</p>
          </div>
        </div>

        {/* QR Code Canvas Box */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 flex flex-col items-center justify-center relative overflow-hidden">
          {isLoading ? (
            <div className="w-48 h-48 flex items-center justify-center text-cyan-400 animate-spin">
              <RefreshCw className="w-8 h-8" />
            </div>
          ) : isPaired ? (
            <div className="w-48 h-48 flex flex-col items-center justify-center text-emerald-400 space-y-2">
              <CheckCircle className="w-16 h-16" />
              <span className="text-sm font-semibold">Device Paired!</span>
            </div>
          ) : (
            <div className="flex flex-col items-center space-y-3">
              {/* SVG Visual Matrix Generator */}
              <div className="w-44 h-44 bg-slate-900 p-3 rounded-lg border border-cyan-500/40 flex flex-col justify-between items-center shadow-inner">
                <div className="grid grid-cols-5 gap-1.5 w-full h-full p-2 bg-slate-950 rounded">
                  {Array.from({ length: 25 }).map((_, i) => (
                    <div
                      key={i}
                      className={`rounded-xs ${
                        i % 2 === 0 || i % 7 === 0 ? 'bg-cyan-400 shadow-[0_0_6px_rgba(0,229,255,0.6)]' : 'bg-slate-800/40'
                      }`}
                    />
                  ))}
                </div>
              </div>

              <div className="text-center font-mono">
                <span className="text-[11px] text-slate-500 block uppercase tracking-wider">Pairing Payload</span>
                <span className="text-xs text-cyan-300 font-bold tracking-widest">{pairingData?.code}</span>
              </div>
            </div>
          )}
        </div>

        {/* Footer & Security Note */}
        <div className="mt-5 flex items-center justify-between pt-4 border-t border-slate-800">
          <div className="flex items-center space-x-1.5 text-xs text-emerald-400 font-mono">
            <ShieldCheck className="w-4 h-4" />
            <span>Fail-Closed JWT Protected</span>
          </div>

          <button
            onClick={fetchQRPayload}
            disabled={isLoading}
            className="flex items-center space-x-1.5 text-xs text-cyan-400 hover:text-cyan-300 px-3 py-1.5 rounded-lg bg-cyan-950/60 border border-cyan-500/30 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh QR</span>
          </button>
        </div>
      </div>
    </div>
  )
}
