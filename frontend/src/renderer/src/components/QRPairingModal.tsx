import React, { useState, useEffect, useRef } from 'react'
import { QrCode, RefreshCw, CheckCircle, ShieldCheck, X, AlertCircle } from 'lucide-react'
import QRCode from 'react-qr-code'

interface QRPairingModalProps {
  isOpen: boolean
  onClose: () => void
}

export const QRPairingModal: React.FC<QRPairingModalProps> = ({ isOpen, onClose }) => {
  const [pairingData, setPairingData] = useState<{ session_id: string; code: string; payload: string } | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [isPaired, setIsPaired] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)

  const getHost = () =>
    typeof window !== 'undefined' && window.location.hostname && window.location.hostname !== 'localhost'
      ? window.location.hostname
      : '127.0.0.1'

  const fetchQRPayload = async () => {
    setIsLoading(true)
    setErrorMessage(null)
    setIsPaired(false)
    try {
      const res = await fetch(`http://${getHost()}:8000/api/v1/mobile/pair/qr/generate`)
      if (res.ok) {
        const data = await res.json()
        setPairingData({
          session_id: data.pairing_session_id,
          code: data.pairing_code,
          payload: data.qr_payload || `jarvis_pair://${data.pairing_session_id}:${data.pairing_code}`
        })
      } else {
        setErrorMessage('Backend refused QR generation. Ensure JARVIS Python backend is running.')
      }
    } catch {
      setErrorMessage('Failed to connect to backend on port 8000.')
    } finally {
      setIsLoading(false)
    }
  }

  // Poll pairing status to detect real pairing success
  useEffect(() => {
    if (!isOpen || !pairingData?.session_id || isPaired) {
      if (pollingRef.current) clearInterval(pollingRef.current)
      return
    }

    const checkStatus = async () => {
      try {
        const res = await fetch(`http://${getHost()}:8000/api/v1/mobile/pair/status/${pairingData.session_id}`)
        if (res.ok) {
          const data = await res.json()
          if (data.paired) {
            setIsPaired(true)
            if (pollingRef.current) clearInterval(pollingRef.current)
          }
        }
      } catch {
        // Continue polling silently
      }
    }

    pollingRef.current = setInterval(checkStatus, 2000)
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current)
    }
  }, [isOpen, pairingData?.session_id, isPaired])

  useEffect(() => {
    if (isOpen) {
      fetchQRPayload()
    } else {
      if (pollingRef.current) clearInterval(pollingRef.current)
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
            <h3 className="text-base font-bold text-slate-100 font-mono">Mobile Companion Pairing</h3>
            <p className="text-xs text-slate-400">Scan QR Code or enter PIN to establish authenticated bridge</p>
          </div>
        </div>

        {/* QR Code Canvas Box */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-6 flex flex-col items-center justify-center relative overflow-hidden min-h-[260px]">
          {isLoading ? (
            <div className="w-48 h-48 flex items-center justify-center text-cyan-400 animate-spin">
              <RefreshCw className="w-8 h-8" />
            </div>
          ) : isPaired ? (
            <div className="w-48 h-48 flex flex-col items-center justify-center text-emerald-400 space-y-3">
              <CheckCircle className="w-16 h-16 animate-bounce" />
              <div className="text-center font-mono">
                <span className="text-sm font-bold text-emerald-400 block">Device Paired!</span>
                <span className="text-[11px] text-slate-400">Encrypted token issued to companion</span>
              </div>
            </div>
          ) : errorMessage ? (
            <div className="w-48 h-48 flex flex-col items-center justify-center text-rose-400 space-y-2 p-2 text-center">
              <AlertCircle className="w-10 h-10" />
              <span className="text-xs font-mono">{errorMessage}</span>
            </div>
          ) : (
            <div className="flex flex-col items-center space-y-3">
              {/* Real Standard QR Code Matrix SVG */}
              {pairingData?.payload && (
                <div className="p-3 bg-white rounded-xl shadow-lg flex items-center justify-center">
                  <QRCode
                    value={pairingData.payload}
                    size={160}
                    bgColor="#ffffff"
                    fgColor="#090d16"
                    level="M"
                  />
                </div>
              )}

              <div className="text-center font-mono mt-1">
                <span className="text-[11px] text-slate-400 block uppercase tracking-wider">Pairing PIN</span>
                <span className="text-xl text-cyan-300 font-extrabold tracking-widest">{pairingData?.code}</span>
              </div>
            </div>
          )}
        </div>

        {/* Footer & Security Note */}
        <div className="mt-5 flex items-center justify-between pt-4 border-t border-slate-800">
          <div className="flex items-center space-x-1.5 text-xs text-emerald-400 font-mono">
            <ShieldCheck className="w-4 h-4" />
            <span>Ed25519 & JWT Protected</span>
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
