import React, { useEffect, useRef, useState } from 'react'
import { Shield, ShieldAlert, ShieldCheck, Key, Scan, RefreshCw, UserCheck, AlertTriangle } from 'lucide-react'

interface FaceLockScreenProps {
  onUnlock: () => void
}

export const FaceLockScreen: React.FC<FaceLockScreenProps> = ({ onUnlock }) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  
  const [status, setStatus] = useState<'initializing' | 'scanning' | 'verifying' | 'granted' | 'denied' | 'lockout' | 'unenrolled'>('initializing')
  const [statusText, setStatusText] = useState('INITIALIZING BIOMETRIC SENSORS...')
  const [ownerName, setOwnerName] = useState('Primary Owner')
  const [failedAttempts, setFailedAttempts] = useState(0)
  const [lockoutSeconds, setLockoutSeconds] = useState(0)
  const [similarity, setSimilarity] = useState<number | null>(null)

  // PIN Backup Modal State
  const [showPinModal, setShowPinModal] = useState(false)
  const [pinInput, setPinInput] = useState('')
  const [pinError, setPinError] = useState<string | null>(null)

  // Enrollment Wizard Modal State
  const [showEnrollModal, setShowEnrollModal] = useState(false)
  const [enrollNameInput, setEnrollNameInput] = useState('Primary Owner')
  const [enrollPinInput, setEnrollPinInput] = useState('1234')
  const [enrollProgress, setEnrollProgress] = useState(0)
  const [enrollStatusText, setEnrollStatusText] = useState('Position face in center frame...')
  const [isEnrolling, setIsEnrolling] = useState(false)

  // 1. Query initial face biometrics status
  const checkStatus = async () => {
    try:
      const res = await fetch('/api/biometrics/face/status')
      const data = await res.json()
      if (data.status === 'success') {
        if (!data.enrolled) {
          setStatus('unenrolled')
          setStatusText('NO OWNER PROFILE ENROLLED — ENROLLMENT REQUIRED')
        } else if (data.lockout_active) {
          setStatus('lockout')
          setLockoutSeconds(data.lockout_seconds_remaining)
          setStatusText(`SECURITY LOCKOUT ACTIVE — RETRY IN ${data.lockout_seconds_remaining}s`)
        } else {
          setOwnerName(data.owner_name)
          setStatus('scanning')
          setStatusText('SCANNING FACE BIOMETRICS...')
        }
      }
    catch (e) {
      console.error('Failed to query face biometrics status:', e)
    }
  }

  // 2. Initialize Camera Feed
  useEffect(() => {
    checkStatus()

    let stream: MediaStream | null = null
    navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480, facingMode: 'user' } })
      .then((s) => {
        stream = s
        if (videoRef.current) {
          videoRef.current.srcObject = s
        }
      })
      .catch((err) => {
        console.error('Camera access denied or unattached:', err)
        setStatusText('CAMERA HARDWARE UNAVAILABLE — USE BACKUP MASTER PIN')
      })

    return () => {
      if (stream) {
        stream.getTracks().forEach((t) => t.stop())
      }
    }
  }, [])

  // 3. Lockout Countdown Timer
  useEffect(() => {
    if (lockoutSeconds <= 0) return
    const timer = setInterval(() => {
      setLockoutSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          setStatus('scanning')
          setStatusText('SCANNING FACE BIOMETRICS...')
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(timer)
  }, [lockoutSeconds])

  // 4. Verification Loop
  useEffect(() => {
    if (status !== 'scanning' || showPinModal || showEnrollModal) return

    const interval = setInterval(async () => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || video.readyState !== 4) return

      const ctx = canvas.getContext('2d')
      if (!ctx) return

      canvas.width = 320
      canvas.height = 240
      ctx.drawImage(video, 0, 0, 320, 240)
      const frameBase64 = canvas.toDataURL('image/jpeg', 0.8)

      try {
        setStatus('verifying')
        setStatusText('VERIFYING 128-D BIOMETRIC EMBEDDING...')

        const res = await fetch('/api/biometrics/face/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ frame_base64: frameBase64 })
        })
        const data = await res.json()

        if (data.status === 'success' && data.verified) {
          setStatus('granted')
          setStatusText(`ACCESS GRANTED — WELCOME BACK, ${data.owner_name.toUpperCase()}`)
          setSimilarity(data.similarity_score || 0.92)
          setTimeout(() => {
            onUnlock()
          }, 1200)
        } else {
          if (data.lockout_active) {
            setStatus('lockout')
            setLockoutSeconds(data.lockout_seconds_remaining || 30)
            setStatusText(`SECURITY LOCKOUT ACTIVE — RETRY IN ${data.lockout_seconds_remaining}s`)
          } else {
            setFailedAttempts(data.failed_attempts || failedAttempts + 1)
            setSimilarity(data.similarity_score || null)
            setStatus('denied')
            setStatusText(data.reason ? data.reason.toUpperCase() : 'BIOMETRIC IDENTITY MISMATCH — ACCESS DENIED')
            setTimeout(() => {
              if (status !== 'lockout') setStatus('scanning')
            }, 1800)
          }
        }
      } catch (e) {
        console.error('Verification request failed:', e)
        setStatus('scanning')
      }
    }, 2500)

    return () => clearInterval(interval)
  }, [status, showPinModal, showEnrollModal])

  // Handle Backup PIN Verification
  const handlePinSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setPinError(null)
    try {
      const res = await fetch('/api/biometrics/face/verify_pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: pinInput })
      })
      const data = await res.json()
      if (data.status === 'success' && data.verified) {
        setStatus('granted')
        setStatusText('MASTER SECURITY PIN VERIFIED — ACCESS GRANTED')
        setShowPinModal(false)
        setTimeout(() => {
          onUnlock()
        }, 1000)
      } else {
        setPinError('Invalid Security PIN.')
      }
    } catch (err) {
      setPinError('PIN verification failed.')
    }
  }

  // Handle Owner Face Enrollment Wizard
  const handleStartEnrollment = async () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || video.readyState !== 4) {
      setEnrollStatusText('Camera feed required. Position face in frame.')
      return
    }

    setIsEnrolling(true)
    setEnrollProgress(10)
    setEnrollStatusText('Capturing Sample 1 / 3...')

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = 320
    canvas.height = 240

    const frames: string[] = []

    for (let i = 1; i <= 3; i++) {
      setEnrollProgress(i * 30)
      setEnrollStatusText(`Capturing Face Sample ${i} / 3... Hold still`)
      ctx.drawImage(video, 0, 0, 320, 240)
      frames.push(canvas.toDataURL('image/jpeg', 0.85))
      await new Promise((r) => setTimeout(r, 600))
    }

    setEnrollStatusText('Processing 128-D embedding & master PIN...')
    try {
      const res = await fetch('/api/biometrics/face/enroll', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          frames_base64: frames,
          owner_name: enrollNameInput || 'Primary Owner',
          pin: enrollPinInput || '1234'
        })
      })
      const data = await res.json()
      if (data.status === 'success' && data.success) {
        setEnrollProgress(100)
        setEnrollStatusText('✓ Owner Face Biometrics Enrolled Successfully!')
        setTimeout(() => {
          setShowEnrollModal(false)
          setIsEnrolling(false)
          checkStatus()
        }, 1200)
      } else {
        setIsEnrolling(false)
        setEnrollStatusText(`Enrollment failed: ${data.error || 'Face not detected'}`)
      }
    } catch (e) {
      setIsEnrolling(false)
      setEnrollStatusText('Enrollment failed. Camera error.')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#050d08] text-emerald-300 font-mono select-none overflow-hidden">
      {/* Hidden processing canvas */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Cybernetic Background Glow Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,255,102,0.08)_0,transparent_70%)] pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#00ff6608_1px,transparent_1px),linear-gradient(to_bottom,#00ff6608_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />

      {/* Main Lock Screen Window Panel */}
      <div className="relative z-10 flex flex-col items-center max-w-md w-full p-6 bg-slate-950/90 border border-emerald-500/40 rounded-xl shadow-[0_0_40px_rgba(0,255,102,0.25)] backdrop-blur-md">
        {/* Header Title Bar */}
        <div className="flex items-center justify-between w-full pb-4 mb-4 border-b border-emerald-500/30">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-400 animate-pulse" />
            <span className="font-bold tracking-widest text-sm text-emerald-200">JARVIS // BIOMETRIC LOCK SCREEN</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-400/30 text-[10px]">
            <Scan className="w-3 h-3 text-emerald-400" />
            <span>FACE ID 2.0</span>
          </div>
        </div>

        {/* WebRTC Video Scanner Viewport */}
        <div className="relative w-64 h-64 my-2 rounded-full overflow-hidden border-2 border-emerald-400/60 shadow-[0_0_25px_rgba(0,255,102,0.4)] flex items-center justify-center bg-slate-900">
          <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover scale-x-[-1]" />

          {/* Scanner Overlay Graphics */}
          <div className="absolute inset-0 border-4 border-emerald-500/20 rounded-full pointer-events-none" />
          {status === 'scanning' && (
            <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-emerald-400 to-transparent shadow-[0_0_15px_#00ff66] animate-bounce top-1/2" />
          )}

          {/* Biometric Status Center Icon Badge */}
          {status === 'granted' && (
            <div className="absolute inset-0 flex items-center justify-center bg-emerald-950/80 backdrop-blur-sm">
              <ShieldCheck className="w-20 h-20 text-emerald-400 animate-bounce" />
            </div>
          )}
          {status === 'denied' && (
            <div className="absolute inset-0 flex items-center justify-center bg-red-950/80 backdrop-blur-sm">
              <ShieldAlert className="w-20 h-20 text-red-500 animate-pulse" />
            </div>
          )}
          {status === 'lockout' && (
            <div className="absolute inset-0 flex items-center justify-center bg-red-950/90 backdrop-blur-sm flex-col">
              <AlertTriangle className="w-16 h-16 text-amber-400 animate-bounce mb-2" />
              <span className="text-xl font-bold text-amber-300">{lockoutSeconds}s</span>
            </div>
          )}
        </div>

        {/* Status Telemetry Banner */}
        <div className="w-full mt-4 p-3 rounded bg-slate-900/90 border border-emerald-500/30 text-center">
          <p className={`text-xs font-bold tracking-wider ${status === 'granted' ? 'text-emerald-300' : status === 'denied' || status === 'lockout' ? 'text-red-400' : 'text-emerald-400'}`}>
            {statusText}
          </p>
          {similarity !== null && (
            <p className="text-[10px] text-emerald-400/80 mt-1">
              Biometric Cosine Similarity: <span className="font-bold text-emerald-200">{(similarity * 100).toFixed(1)}%</span> (Threshold: 70.0%)
            </p>
          )}
        </div>

        {/* Security Actions Bar */}
        <div className="flex items-center justify-between w-full mt-6 gap-3">
          <button
            type="button"
            onClick={() => setShowPinModal(true)}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-bold border border-emerald-500/40 rounded bg-emerald-950/40 hover:bg-emerald-500/20 text-emerald-200 transition-all cursor-pointer"
          >
            <Key className="w-3.5 h-3.5 text-emerald-400" />
            <span>MASTER PIN</span>
          </button>

          <button
            type="button"
            onClick={() => setShowEnrollModal(true)}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-bold border border-emerald-500/40 rounded bg-emerald-950/40 hover:bg-emerald-500/20 text-emerald-200 transition-all cursor-pointer"
          >
            <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>ENROLL FACE</span>
          </button>
        </div>
      </div>

      {/* ── MASTER PIN FALLBACK MODAL ───────────────────────────────────────── */}
      {showPinModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
          <form onSubmit={handlePinSubmit} className="w-full max-w-sm p-6 bg-slate-950 border border-emerald-500/50 rounded-xl shadow-2xl flex flex-col gap-4">
            <div className="flex items-center justify-between pb-2 border-b border-emerald-500/30">
              <div className="flex items-center gap-2">
                <Key className="w-4 h-4 text-emerald-400" />
                <span className="font-bold text-xs tracking-wider text-emerald-200">ENTER MASTER SECURITY PIN</span>
              </div>
              <button type="button" onClick={() => setShowPinModal(false)} className="text-slate-400 hover:text-white text-xs">✕</button>
            </div>

            <input
              type="password"
              value={pinInput}
              onChange={(e) => setPinInput(e.target.value)}
              placeholder="Enter PIN (Default: 1234)"
              className="w-full px-4 py-2 bg-slate-900 border border-emerald-500/40 rounded text-center text-lg font-mono text-emerald-300 focus:outline-none focus:border-emerald-400"
              autoFocus
            />

            {pinError && <p className="text-xs text-red-400 text-center font-bold">{pinError}</p>}

            <div className="flex items-center justify-end gap-2 mt-2">
              <button type="button" onClick={() => setShowPinModal(false)} className="px-3 py-1.5 text-xs text-slate-400 hover:text-white">Cancel</button>
              <button type="submit" className="px-4 py-1.5 text-xs font-bold bg-emerald-500/20 border border-emerald-400 text-emerald-200 rounded hover:bg-emerald-500/40">VERIFY PIN</button>
            </div>
          </form>
        </div>
      )}

      {/* ── OWNER FACE ENROLLMENT WIZARD MODAL ─────────────────────────────── */}
      {showEnrollModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
          <div className="w-full max-w-md p-6 bg-slate-950 border border-emerald-500/50 rounded-xl shadow-2xl flex flex-col gap-4">
            <div className="flex items-center justify-between pb-2 border-b border-emerald-500/30">
              <div className="flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-emerald-400" />
                <span className="font-bold text-xs tracking-wider text-emerald-200">OWNER FACE BIOMETRIC ENROLLMENT</span>
              </div>
              {!isEnrolling && <button type="button" onClick={() => setShowEnrollModal(false)} className="text-slate-400 hover:text-white text-xs">✕</button>}
            </div>

            <div className="flex flex-col gap-3">
              <label className="text-xs text-emerald-400">Owner Name</label>
              <input
                type="text"
                value={enrollNameInput}
                onChange={(e) => setEnrollNameInput(e.target.value)}
                className="w-full px-3 py-1.5 bg-slate-900 border border-emerald-500/40 rounded text-xs text-emerald-300 focus:outline-none"
                disabled={isEnrolling}
              />

              <label className="text-xs text-emerald-400">Backup Master PIN</label>
              <input
                type="password"
                value={enrollPinInput}
                onChange={(e) => setEnrollPinInput(e.target.value)}
                placeholder="1234"
                className="w-full px-3 py-1.5 bg-slate-900 border border-emerald-500/40 rounded text-xs text-emerald-300 focus:outline-none"
                disabled={isEnrolling}
              />
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-slate-900 h-2 rounded overflow-hidden mt-2">
              <div className="bg-emerald-400 h-full transition-all duration-300" style={{ width: `${enrollProgress}%` }} />
            </div>

            <p className="text-xs text-center text-emerald-300/90 font-bold">{enrollStatusText}</p>

            <div className="flex items-center justify-end gap-2 mt-2">
              {!isEnrolling && <button type="button" onClick={() => setShowEnrollModal(false)} className="px-3 py-1.5 text-xs text-slate-400 hover:text-white">Cancel</button>}
              <button
                type="button"
                onClick={handleStartEnrollment}
                disabled={isEnrolling}
                className="px-4 py-1.5 text-xs font-bold bg-emerald-500/20 border border-emerald-400 text-emerald-200 rounded hover:bg-emerald-500/40 disabled:opacity-50"
              >
                {isEnrolling ? 'ENROLLING...' : 'START ENROLLMENT SCAN'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
