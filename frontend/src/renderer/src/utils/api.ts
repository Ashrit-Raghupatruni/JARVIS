/**
 * Dynamic API Base URL resolution for local Electron, local browser, and LAN / multi-desktop connections.
 */
export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    // If running in browser / dev server on LAN or local machine
    if (host && host !== 'localhost' && host !== '127.0.0.1') {
      return `http://${host}:8000`
    }
  }
  return 'http://127.0.0.1:8000'
}
