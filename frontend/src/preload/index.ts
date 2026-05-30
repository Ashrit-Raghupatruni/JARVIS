import { contextBridge, ipcRenderer } from 'electron'

export interface ElectronAPI {
  minimize: () => Promise<void>
  maximize: () => Promise<void>
  close: () => Promise<void>
  isMaximized: () => Promise<boolean>
  getSystemInfo: () => Promise<{
    platform: string
    arch: string
    version: string
    electron: string
    node: string
    chrome: string
    backendPort?: number
  }>
  showNotification: (title: string, body: string) => Promise<void>
  onPushToTalk: (callback: () => void) => () => void
  onWindowStateChanged: (callback: (state: { isMaximized: boolean }) => void) => () => void
  onOpenSettings: (callback: () => void) => () => void
  platform: string
}

const api: ElectronAPI = {
  minimize: () => ipcRenderer.invoke('window-minimize'),
  maximize: () => ipcRenderer.invoke('window-maximize'),
  close: () => ipcRenderer.invoke('window-close'),
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  getSystemInfo: () => ipcRenderer.invoke('get-system-info'),
  showNotification: (title: string, body: string) =>
    ipcRenderer.invoke('show-notification', title, body),

  onPushToTalk: (callback: () => void) => {
    const handler = (): void => callback()
    ipcRenderer.on('push-to-talk-toggle', handler)
    return () => {
      ipcRenderer.removeListener('push-to-talk-toggle', handler)
    }
  },

  onWindowStateChanged: (callback: (state: { isMaximized: boolean }) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, state: { isMaximized: boolean }): void =>
      callback(state)
    ipcRenderer.on('window-state-changed', handler)
    return () => {
      ipcRenderer.removeListener('window-state-changed', handler)
    }
  },

  onOpenSettings: (callback: () => void) => {
    const handler = (): void => callback()
    ipcRenderer.on('open-settings', handler)
    return () => {
      ipcRenderer.removeListener('open-settings', handler)
    }
  },

  platform: process.platform
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electronAPI', api)
  } catch (error) {
    console.error('Failed to expose electron API:', error)
  }
} else {
  // @ts-ignore - fallback for non-isolated context
  window.electronAPI = api
}
