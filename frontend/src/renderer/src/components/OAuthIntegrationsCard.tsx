import React, { useState, useEffect, useCallback } from 'react'
import {
  Mail,
  Calendar,
  CheckCircle2,
  XCircle,
  RefreshCw,
  ShieldCheck,
  Key,
  LogOut,
  GitBranch,
  Hash,
  FileText
} from 'lucide-react'

interface OAuthProviderStatus {
  connected: boolean
  account_email?: string
  expires_in_seconds?: number
  scopes?: string[]
}

interface OAuthStatusResponse {
  status: string
  providers: {
    google?: OAuthProviderStatus
    microsoft?: OAuthProviderStatus
    github?: OAuthProviderStatus
    slack?: OAuthProviderStatus
    notion?: OAuthProviderStatus
  }
}

type ProviderId = 'google' | 'microsoft' | 'github' | 'slack' | 'notion'

interface ProviderMeta {
  id: ProviderId
  name: string
  description: string
  icon: React.ReactNode
  accentColor: string
}

const PROVIDER_METAS: ProviderMeta[] = [
  {
    id: 'google',
    name: 'Google Workspace',
    description: 'Gmail (Search, Send) & Google Calendar (Events, Scheduling).',
    icon: <Mail className="w-4 h-4 text-blue-400" />,
    accentColor: 'blue'
  },
  {
    id: 'microsoft',
    name: 'Microsoft 365',
    description: 'Outlook Mail (Sync, Send) & Outlook Calendar (Meeting Events).',
    icon: <Calendar className="w-4 h-4 text-cyan-400" />,
    accentColor: 'cyan'
  },
  {
    id: 'github',
    name: 'GitHub Enterprise',
    description: 'Repositories, pull requests, issue tracking, and user profile sync.',
    icon: <GitBranch className="w-4 h-4 text-purple-400" />,
    accentColor: 'purple'
  },
  {
    id: 'slack',
    name: 'Slack Workspace',
    description: 'Channel broadcasting, direct messaging, and notification dispatches.',
    icon: <Hash className="w-4 h-4 text-emerald-400" />,
    accentColor: 'emerald'
  },
  {
    id: 'notion',
    name: 'Notion Workspace',
    description: 'Pages, structured workspace databases, documentation, and notes.',
    icon: <FileText className="w-4 h-4 text-amber-400" />,
    accentColor: 'amber'
  }
]

export const OAuthIntegrationsCard: React.FC = () => {
  const [oauthStatus, setOauthStatus] = useState<OAuthStatusResponse['providers'] | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionMsg, setActionMsg] = useState<string | null>(null)

  const getBackendPort = () => 8000
  const getHost = () => {
    if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
      return window.location.hostname
    }
    return '127.0.0.1'
  }

  const BASE_URL = `http://${getHost()}:${getBackendPort()}/api/v1/oauth`

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true)
      const res = await fetch(`${BASE_URL}/status`)
      if (res.ok) {
        const data: OAuthStatusResponse = await res.json()
        if (data.status === 'ok' && data.providers) {
          setOauthStatus(data.providers)
        }
      }
    } catch (e) {
      console.error('[OAuthCard] Failed to fetch OAuth status:', e)
    } finally {
      setLoading(false)
    }
  }, [BASE_URL])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 8000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const handleConnect = async (provider: ProviderId) => {
    try {
      setActionMsg(`Initiating PKCE authorization for ${provider}...`)
      const res = await fetch(`${BASE_URL}/${provider}/authorize`)
      if (res.ok) {
        const data = await res.json()
        if (data.authorization_url) {
          window.open(data.authorization_url, '_blank')
          setActionMsg(`Opened ${provider} authentication in your default browser. Complete authorization and return here.`)
        } else {
          setActionMsg(`Error: ${data.message || 'No authorization URL returned'}`)
        }
      }
    } catch (e) {
      setActionMsg(`Failed to initiate ${provider} OAuth: ${e}`)
    }
  }

  const handleDisconnect = async (provider: ProviderId) => {
    try {
      setActionMsg(`Disconnecting ${provider}...`)
      const res = await fetch(`${BASE_URL}/${provider}/disconnect`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        setActionMsg(`✓ Disconnected ${provider}: ${data.message}`)
        fetchStatus()
      }
    } catch (e) {
      setActionMsg(`Failed to disconnect ${provider}: ${e}`)
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4 rounded-xl bg-slate-900/60 border border-cyan-500/20 backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cyan-500/10 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold tracking-wider text-cyan-100 uppercase">Direct OAuth2 Integrations (Native PKCE)</h3>
            <p className="text-[11px] text-slate-400">Google, Microsoft 365, GitHub, Slack, & Notion Ecosystems</p>
          </div>
        </div>
        <button
          onClick={fetchStatus}
          disabled={loading}
          className="p-1.5 rounded-lg bg-slate-800 border border-cyan-500/20 text-cyan-400 hover:bg-slate-700 transition"
          title="Refresh Status"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {actionMsg && (
        <div className="px-3 py-2 rounded-lg bg-cyan-950/60 border border-cyan-500/30 text-xs text-cyan-300">
          {actionMsg}
        </div>
      )}

      {/* Grid of All 5 Providers */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {PROVIDER_METAS.map((prov) => {
          const status = oauthStatus?.[prov.id]
          const isConnected = status?.connected ?? false

          return (
            <div
              key={prov.id}
              className="flex flex-col justify-between p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-cyan-500/30 transition"
            >
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
                      {prov.icon}
                    </div>
                    <span className="text-xs font-semibold text-slate-200">{prov.name}</span>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-medium flex items-center gap-1 ${
                      isConnected
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    }`}
                  >
                    {isConnected ? (
                      <>
                        <CheckCircle2 className="w-2.5 h-2.5" /> Connected
                      </>
                    ) : (
                      <>
                        <XCircle className="w-2.5 h-2.5" /> Disconnected
                      </>
                    )}
                  </span>
                </div>

                <p className="text-[11px] text-slate-400 leading-relaxed">
                  {prov.description}
                </p>

                {isConnected && status?.account_email && (
                  <div className="px-2 py-1 rounded bg-slate-900 border border-slate-800 text-[10px] font-mono text-cyan-300 truncate">
                    Account: {status.account_email}
                  </div>
                )}
              </div>

              <div className="mt-3 pt-3 border-t border-slate-800/60 flex items-center justify-between">
                {isConnected ? (
                  <button
                    onClick={() => handleDisconnect(prov.id)}
                    className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-red-950/50 border border-red-500/30 text-red-300 hover:bg-red-900/50 text-xs transition"
                  >
                    <LogOut className="w-3 h-3" /> Disconnect
                  </button>
                ) : (
                  <button
                    onClick={() => handleConnect(prov.id)}
                    className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-semibold text-xs transition"
                  >
                    <Key className="w-3 h-3" /> Connect {prov.name.split(' ')[0]}
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default OAuthIntegrationsCard

