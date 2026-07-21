import React, { useState } from 'react'
import { Server, CheckCircle2, AlertTriangle, Zap, Check } from 'lucide-react'

export interface ProviderItem {
  id: string
  name: string
  model: string
  status: 'PRIMARY' | 'SECONDARY' | 'OPTIONAL' | 'OFFLINE'
  latency: string
  type: 'local' | 'cloud'
}

export default function LLMProvidersCard() {
  const [activeProvider, setActiveProvider] = useState<string>('ollama')
  const [providers, setProviders] = useState<ProviderItem[]>([
    { id: 'ollama', name: 'Ollama Local', model: 'qwen2.5-coder:3b', status: 'PRIMARY', latency: '0.08s', type: 'local' },
    { id: 'groq', name: 'Groq Cloud', model: 'llama-3.3-70b', status: 'SECONDARY', latency: '0.31s', type: 'cloud' },
    { id: 'openai', name: 'OpenAI (Optional)', model: 'gpt-4o', status: 'OPTIONAL', latency: '--', type: 'cloud' },
    { id: 'gemini', name: 'Google Gemini', model: 'gemini-2.0-flash', status: 'OPTIONAL', latency: '0.45s', type: 'cloud' },
    { id: 'openrouter', name: 'OpenRouter', model: 'meta-llama-3.3', status: 'OPTIONAL', latency: '0.62s', type: 'cloud' },
  ])

  const handleSwitchProvider = async (providerId: string) => {
    setActiveProvider(providerId)
    try {
      await fetch('/api/ui/set_provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: providerId })
      })
    } catch (e) {
      console.warn('Provider switched')
    }
  }

  return (
    <div className="bg-[rgba(10,20,38,0.75)] backdrop-blur-md border border-[rgba(0,229,255,0.18)] rounded-xl p-3 shadow-lg hover:border-[rgba(0,229,255,0.35)] transition-all">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Server className="w-4 h-4 text-[#00e5ff]" />
          <span className="text-xs font-semibold text-[#00e5ff] tracking-wider uppercase">Connected LLM Providers</span>
        </div>
        <span className="text-[10px] font-mono text-[#b0bec5]">
          Active: <strong className="text-[#00e676] uppercase">{activeProvider}</strong>
        </span>
      </div>

      <div className="space-y-1.5">
        {providers.map((p) => {
          const isActive = activeProvider === p.id
          return (
            <div
              key={p.id}
              onClick={() => handleSwitchProvider(p.id)}
              className={`flex items-center justify-between p-1.5 rounded-lg border text-xs cursor-pointer transition-all ${
                isActive
                  ? 'bg-[rgba(0,229,255,0.15)] border-[rgba(0,229,255,0.4)] text-[#e1f5fe] shadow-[0_0_10px_rgba(0,229,255,0.15)]'
                  : 'bg-[rgba(15,30,56,0.4)] border-[rgba(0,229,255,0.08)] text-[#b0bec5] hover:border-slate-700'
              }`}
            >
              <div className="flex items-center gap-2">
                {isActive ? (
                  <Zap className="w-3.5 h-3.5 text-[#00e5ff] fill-[#00e5ff]" />
                ) : p.status === 'SECONDARY' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#00e676]" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5 text-[#78909c]" />
                )}
                <div>
                  <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                    <span>{p.name}</span>
                    <span className="text-[9px] font-mono px-1 rounded bg-slate-800 text-slate-400">{p.type}</span>
                  </div>
                  <div className="text-[10px] font-mono text-slate-400">{p.model}</div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-[#00e5ff]">{p.latency}</span>
                {isActive && (
                  <span className="text-[9px] font-mono font-bold bg-[#00e676] text-slate-950 px-1.5 py-0.5 rounded flex items-center gap-0.5">
                    <Check className="w-2.5 h-2.5" /> ACTIVE
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
