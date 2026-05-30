import {
  app,
  shell,
  BrowserWindow,
  globalShortcut,
  Tray,
  Menu,
  nativeImage,
  ipcMain,
  Notification,
  session
} from 'electron'
import { join } from 'path'
import { ChildProcess, spawn, execSync } from 'child_process'
import { readFileSync, existsSync } from 'fs'

function getBackendPort(): number {
  const envPath = join(__dirname, '..', '..', '..', '.env')
  if (existsSync(envPath)) {
    try {
      const content = readFileSync(envPath, 'utf8')
      const match = content.match(/^SERVER_PORT\s*=\s*(\d+)/m)
      if (match && match[1]) {
        return parseInt(match[1], 10)
      }
    } catch (err) {
      console.error('[Main] Failed to read .env file for port:', err)
    }
  }
  return 8000
}

function killPortOwner(port: number): void {
  try {
    if (process.platform === 'win32') {
      const cmd = `powershell -Command "Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"`
      execSync(cmd, { stdio: 'ignore' })
    } else {
      execSync(`lsof -t -i:${port} | xargs kill -9 2>/dev/null || true`, { stdio: 'ignore' })
    }
  } catch (err) {
    // Ignore errors
  }
}

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let backendProcess: ChildProcess | null = null
let isQuitting = false

function createTrayIcon(): nativeImage {
  // Create a simple 16x16 cyan circle icon programmatically
  const size = 16
  const canvas = Buffer.alloc(size * size * 4)
  const cx = size / 2
  const cy = size / 2
  const r = 6
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4
      const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
      if (dist <= r) {
        const alpha = Math.max(0, Math.min(255, (r - dist) * 80))
        canvas[idx] = 0 // R
        canvas[idx + 1] = 212 // G
        canvas[idx + 2] = 255 // B
        canvas[idx + 3] = Math.min(255, alpha + 180) // A
      }
    }
  }
  return nativeImage.createFromBuffer(canvas, { width: size, height: size })
}

function startBackendProcess(): void {
  const backendPath = join(__dirname, '..', '..', '..', 'backend')
  const port = getBackendPort()

  // Clean up any orphan processes holding the port before starting uvicorn
  console.log(`[Backend] Checking and freeing port ${port}...`)
  killPortOwner(port)

  // Use the venv Python so all pip-installed deps are available
  const venvPython = process.platform === 'win32'
    ? join(backendPath, 'venv', 'Scripts', 'python.exe')
    : join(backendPath, 'venv', 'bin', 'python')

  try {
    backendProcess = spawn(venvPython, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(port)], {
      cwd: backendPath,
      stdio: 'pipe',
      shell: true
    })

    backendProcess.stdout?.on('data', (data: Buffer) => {
      console.log(`[Backend] ${data.toString().trim()}`)
    })

    backendProcess.stderr?.on('data', (data: Buffer) => {
      console.error(`[Backend Error] ${data.toString().trim()}`)
    })

    backendProcess.on('close', (code: number | null) => {
      console.log(`[Backend] Process exited with code ${code}`)
      if (!isQuitting) {
        console.log('[Backend] Restarting in 3 seconds...')
        setTimeout(startBackendProcess, 3000)
      }
    })

    backendProcess.on('error', (err: Error) => {
      console.error('[Backend] Failed to start:', err.message)
    })

    console.log('[Backend] Started with PID:', backendProcess.pid)
  } catch (err) {
    console.error('[Backend] Failed to spawn process:', err)
  }
}

function killBackendProcess(): void {
  if (backendProcess && !backendProcess.killed) {
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t'], { shell: true })
      } else {
        backendProcess.kill('SIGTERM')
      }
    } catch (err) {
      console.error('[Backend] Failed to kill process:', err)
    }
    backendProcess = null
  }
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    frame: false,
    transparent: false,
    backgroundColor: '#0a0e1a',
    titleBarStyle: 'hidden',
    titleBarOverlay: false,
    icon: createTrayIcon(),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // Handle window close -> minimize to tray
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      mainWindow?.hide()
    }
  })

  mainWindow.on('maximize', () => {
    mainWindow?.webContents.send('window-state-changed', { isMaximized: true })
  })

  mainWindow.on('unmaximize', () => {
    mainWindow?.webContents.send('window-state-changed', { isMaximized: false })
  })

  // Load renderer
  if (!app.isPackaged && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

function createTray(): void {
  const icon = createTrayIcon()
  tray = new Tray(icon)

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show JARVIS',
      click: (): void => {
        mainWindow?.show()
        mainWindow?.focus()
      }
    },
    {
      label: 'Settings',
      click: (): void => {
        mainWindow?.show()
        mainWindow?.focus()
        mainWindow?.webContents.send('open-settings')
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: (): void => {
        isQuitting = true
        app.quit()
      }
    }
  ])

  tray.setToolTip('JARVIS AI Assistant')
  tray.setContextMenu(contextMenu)

  tray.on('double-click', () => {
    mainWindow?.show()
    mainWindow?.focus()
  })
}

function registerGlobalShortcuts(): void {
  // Push-to-talk: Ctrl+Space
  globalShortcut.register('CommandOrControl+Space', () => {
    mainWindow?.webContents.send('push-to-talk-toggle')
  })
}

// IPC Handlers
function setupIPC(): void {
  ipcMain.handle('window-minimize', () => {
    mainWindow?.minimize()
  })

  ipcMain.handle('window-maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow?.maximize()
    }
  })

  ipcMain.handle('window-close', () => {
    mainWindow?.close()
  })

  ipcMain.handle('window-is-maximized', () => {
    return mainWindow?.isMaximized() ?? false
  })

  ipcMain.handle('get-system-info', () => {
    return {
      platform: process.platform,
      arch: process.arch,
      version: app.getVersion(),
      electron: process.versions.electron,
      node: process.versions.node,
      chrome: process.versions.chrome,
      backendPort: getBackendPort()
    }
  })

  ipcMain.handle('show-notification', (_event, title: string, body: string) => {
    if (Notification.isSupported()) {
      new Notification({ title, body, icon: createTrayIcon() }).show()
    }
  })
}

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })

  app.whenReady().then(() => {
    // Auto-grant microphone and camera permissions for getUserMedia
    session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
      const allowedPermissions = ['media', 'microphone', 'camera', 'audioCapture']
      callback(allowedPermissions.includes(permission))
    })

    setupIPC()
    createWindow()
    createTray()
    registerGlobalShortcuts()
    startBackendProcess()

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow()
      }
    })
  })
}

app.on('before-quit', () => {
  isQuitting = true
  killBackendProcess()
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
  killBackendProcess()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    // Don't quit on window close, stay in tray
  }
})
