import React, { useState, useEffect, useCallback } from 'react'
import { Send, Shield, RefreshCw, Key, CheckCircle2, AlertCircle, Smartphone, ExternalLink, Lock } from 'lucide-react'

interface TelegramStatus {
  enabled: boolean
  connected: boolean
  bot_username: string | null
  bot_id: number | null
  authorized_chat_id: string | null
  is_paired: boolean
  pairing_active: boolean
  pending_approvals: number
  last_activity_time: number
  total_commands_executed: number
  total_unauthorized_attempts: number
}

interface PairingData {
  pin: string
  expires_at: number
  timeout_seconds: number
  instructions: string
}

export const TelegramIntegrationCard: React.FC = () => {
  const [status, setStatus] = useState<TelegramStatus | null>(null)
  const [pairingData, setPairingData] = useState<PairingData | null>(null)
  const [loading, setLoading] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  const getBackendPort = () => 8000
  const getHost = () => {
    if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      return window.location.hostname
    }
    return '127.0.0.1'
  }

  const BASE_URL = `http://${getHost()}:${getBackendPort()}/api/v1/telegram`

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}/status`)
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      }
    } catch (e) {
      console.error('[TelegramCard] Failed to fetch status:', e)
    }
  }, [BASE_URL])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 4000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const handleInitiatePairing = async () => {
    setLoading(true)
    setFeedback('Generating secure pairing PIN...')
    try {
      const res = await fetch(`${BASE_URL}/pair/initiate`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        setPairingData(data)
        setFeedback('✓ Pairing PIN generated. Send this code to your bot in Telegram.')
      } else {
        const err = await res.json()
        setFeedback(`Failed to initiate pairing: ${err.detail || 'Unknown error'}`)
      }
    } catch (e) {
      setFeedback(`Network error: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const handleUnpair = async () => {
    if (!confirm('Are you sure you want to revoke Telegram access for this workstation?')) return
    setLoading(true)
    try {
      const res = await fetch(`${BASE_URL}/unpair`, { method: 'POST' })
      if (res.ok) {
        setFeedback('✓ Telegram account un-paired successfully.')
        setPairingData(null)
        fetchStatus()
      }
    } catch (e) {
      setFeedback(`Error unpairing: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  const handleSendTestNotification = async () => {
    setLoading(true)
    setFeedback('Sending test push notification to Telegram...')
    try {
      const res = await fetch(`${BASE_URL}/test_notification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: 'JARVIS Remote Test Alert',
          message: 'Secure link operational! Remote command and 1-click approvals ready.'
        })
      })
      if (res.ok) {
        setFeedback('✓ Test alert delivered to your Telegram!')
      } else {
        const err = await res.json()
        setFeedback(`Failed: ${err.detail || 'Check connection'}`)
      }
    } catch (e) {
      setFeedback(`Error sending alert: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 backdrop-blur shadow-xl relative overflow-hidden">
      {/* Background Glow */}
      <div className="absolute -top-12 -right-12 w-48 h-48 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
            <Send className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-100 flex items-center space-x-2">
              <span>Telegram Remote Gateway</span>
              <span className="text-xs px-2 py-0.5 rounded-full font-mono bg-cyan-950 text-cyan-400 border border-cyan-800">
                Fail-Closed
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Encrypted remote control, mobile notifications, and 1-click action approvals via Telegram.
            </p>
          </div>
        </div>

        {/* Status Badge */}
        <div className="flex items-center space-x-2">
          {status?.is_paired ? (
            <div className="flex items-center space-x-1.5 px-3 py-1 bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 rounded-full text-xs font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Paired & Active</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1.5 px-3 py-1 bg-amber-950/60 border border-amber-500/30 text-amber-400 rounded-full text-xs font-medium">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>Awaiting Pairing</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Grid Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700/60">
          <div className="text-xs text-slate-400 mb-1 flex items-center space-x-1">
            <Smartphone className="w-3.5 h-3.5 text-slate-400" />
            <span>Bot Identity</span>
          </div>
          <div className="font-mono text-sm text-cyan-300">
            {status?.bot_username ? `@${status.bot_username}` : '@playingwdbot_bot'}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Status: {status?.connected ? 'Online (Polling)' : 'Offline'}
          </div>
        </div>

        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700/60">
          <div className="text-xs text-slate-400 mb-1 flex items-center space-x-1">
            <Shield className="w-3.5 h-3.5 text-slate-400" />
            <span>Authorized Administrator</span>
          </div>
          <div className="font-mono text-sm text-emerald-300">
            {status?.authorized_chat_id || 'Not Paired'}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Unknown users: Rejected & Logged
          </div>
        </div>

        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700/60">
          <div className="text-xs text-slate-400 mb-1 flex items-center space-x-1">
            <Lock className="w-3.5 h-3.5 text-slate-400" />
            <span>Remote Activity</span>
          </div>
          <div className="text-sm font-semibold text-slate-200">
            {status?.total_commands_executed || 0} Commands Executed
          </div>
          <div className="text-xs text-slate-500 mt-1">
            Pending Approvals: {status?.pending_approvals || 0}
          </div>
        </div>
      </div>

      {/* Pairing Flow Panel (When Unpaired or Initiated) */}
      {pairingData && (
        <div className="mb-6 p-4 rounded-lg bg-cyan-950/40 border border-cyan-500/40 animate-pulse-subtle">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs font-semibold text-cyan-400 uppercase tracking-wider mb-1">
                Active Pairing PIN
              </div>
              <div className="text-3xl font-mono font-bold tracking-widest text-cyan-200 mb-2">
                {pairingData.pin}
              </div>
              <p className="text-xs text-slate-300">
                {pairingData.instructions}
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-cyan-400 font-mono">
                Valid for 5 mins
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Feedback Alert */}
      {feedback && (
        <div className="mb-4 p-3 rounded-lg bg-slate-800 border border-slate-700 text-xs text-slate-300 flex items-center justify-between">
          <span>{feedback}</span>
          <button
            onClick={() => setFeedback(null)}
            className="text-slate-500 hover:text-slate-400 ml-2"
          >
            ×
          </button>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-slate-800">
        {!status?.is_paired ? (
          <button
            onClick={handleInitiatePairing}
            disabled={loading}
            className="flex items-center space-x-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold shadow-md transition disabled:opacity-50"
          >
            <Key className="w-4 h-4" />
            <span>Generate Pairing PIN</span>
          </button>
        ) : (
          <>
            <button
              onClick={handleSendTestNotification}
              disabled={loading}
              className="flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-800/40 rounded-lg text-xs font-semibold transition disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Send Test Ping</span>
            </button>

            <button
              onClick={handleUnpair}
              disabled={loading}
              className="flex items-center space-x-2 px-3 py-2 bg-red-950/40 hover:bg-red-900/60 text-red-400 border border-red-800/40 rounded-lg text-xs font-medium transition disabled:opacity-50"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Revoke Pairing</span>
            </button>
          </>
        )}

        <button
          onClick={fetchStatus}
          disabled={loading}
          className="flex items-center space-x-1.5 px-3 py-2 bg-slate-800/60 hover:bg-slate-800 text-slate-400 rounded-lg text-xs transition"
          title="Refresh Telegram Status"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>

        {status?.bot_username && (
          <a
            href={`https://t.me/${status.bot_username}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center space-x-1 px-3 py-2 text-slate-400 hover:text-cyan-400 text-xs ml-auto transition"
          >
            <span>Open @{status.bot_username}</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    </div>
  )
}

export default TelegramIntegrationCard
