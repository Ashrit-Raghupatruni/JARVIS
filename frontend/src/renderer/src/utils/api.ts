/**
 * Dynamic API Base URL resolution for local Electron, local browser, and LAN / multi-desktop connections.
 */
let cachedBackendPort: number | null = null

export async function resolveBackendPort(): Promise<number> {
  if (cachedBackendPort) return cachedBackendPort
  if (typeof window !== 'undefined') {
    const api = (window as any).electronAPI
    if (api?.getSystemInfo) {
      try {
        const info = await api.getSystemInfo()
        if (info && typeof info.backendPort === 'number') {
          cachedBackendPort = info.backendPort
          return cachedBackendPort
        }
      } catch {
        // Fallback to default
      }
    }
    const envPort = (import.meta as any)?.env?.VITE_BACKEND_PORT
    if (envPort) {
      const parsed = parseInt(String(envPort), 10)
      if (!isNaN(parsed)) {
        cachedBackendPort = parsed
        return cachedBackendPort
      }
    }
  }
  cachedBackendPort = 8000
  return cachedBackendPort
}

// Proactively initialize
if (typeof window !== 'undefined') {
  resolveBackendPort().catch(() => {})
}

export function getApiBaseUrl(): string {
  const port = cachedBackendPort || 8000
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    // If running in browser / dev server on LAN or local machine
    if (host && host !== 'localhost' && host !== '127.0.0.1') {
      return `http://${host}:${port}`
    }
  }
  return `http://127.0.0.1:${port}`
}
