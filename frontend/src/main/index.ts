import {
  app,
  net,
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
let siriWindow: BrowserWindow | null = null
let siriHideTimeout: NodeJS.Timeout | null = null
let omniWindow: BrowserWindow | null = null
let tray: Tray | null = null
let backendProcess: ChildProcess | null = null
let isQuitting = false
let isLiveModeActive = false


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

function getLogPath(): string {
  const logDir = join(__dirname, '..', '..', '..', 'logs')
  if (!existsSync(logDir)) {
    try { mkdirSync(logDir, { recursive: true }) } catch (e) { /* ignore */ }
  }
  return join(logDir, 'backend_startup.log')
}

function writeBackendLog(message: string): void {
  const timestamp = new Date().toISOString()
  const line = `[${timestamp}] ${message}\n`
  try {
    appendFileSync(getLogPath(), line, 'utf8')
  } catch (err) {
    // Ignore logging write failures
  }
}

function startBackendProcess(): void {
  const backendPath = join(__dirname, '..', '..', '..', 'backend')
  const port = getBackendPort()

  writeBackendLog(`[Backend] Initializing backend process on port ${port}...`)
  console.log(`[Backend] Checking and freeing port ${port}...`)
  killPortOwner(port)

  // Use the venv Python so all pip-installed deps are available
  const venvPython = process.platform === 'win32'
    ? join(backendPath, 'venv', 'Scripts', 'python.exe')
    : join(backendPath, 'venv', 'bin', 'python')

  if (!existsSync(venvPython)) {
    const errorMsg = `[Backend Error] Virtual environment Python not found at: ${venvPython}. Run setup.bat to create venv.`
    console.error(errorMsg)
    writeBackendLog(errorMsg)
    return
  }

  writeBackendLog(`[Backend] Spawning Python venv interpreter: ${venvPython}`)

  try {
    backendProcess = spawn(venvPython, ['-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', String(port)], {
      cwd: backendPath,
      stdio: 'pipe',
      env: { ...process.env, SPAWNED_BY_ELECTRON: 'true' }
    })

    backendProcess.stdout?.on('data', (data: Buffer) => {
      const text = data.toString().trim()
      console.log(`[Backend] ${text}`)
      writeBackendLog(`[STDOUT] ${text}`)
    })

    backendProcess.stderr?.on('data', (data: Buffer) => {
      const text = data.toString().trim()
      console.error(`[Backend Error] ${text}`)
      writeBackendLog(`[STDERR] ${text}`)
    })

    backendProcess.on('close', (code: number | null) => {
      const exitMsg = `[Backend] Process exited with code ${code}`
      console.log(exitMsg)
      writeBackendLog(exitMsg)
      if (!isQuitting) {
        console.log('[Backend] Restarting in 3 seconds...')
        setTimeout(startBackendProcess, 3000)
      }
    })

    backendProcess.on('error', (err: Error) => {
      const errStr = `[Backend Error] Failed to start process: ${err.message}`
      console.error(errStr)
      writeBackendLog(errStr)
    })

    console.log('[Backend] Started with PID:', backendProcess.pid)
    writeBackendLog(`[Backend] Spawned successfully with PID: ${backendProcess.pid}`)
  } catch (err) {
    const catchErr = `[Backend Exception] Failed to spawn process: ${err}`
    console.error(catchErr)
    writeBackendLog(catchErr)
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
    minWidth: 420,
    minHeight: 420,
    show: false,
    frame: false,
    transparent: false,
    backgroundColor: '#070b13',
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
    const isHiddenLaunch = process.argv.includes('--autostart') || process.argv.includes('--hidden') || process.argv.includes('--minimized')
    if (!isHiddenLaunch) {
      mainWindow?.show()
      mainWindow?.focus()
      showSiriWindowTemporarily(3000)
    } else {
      console.log('[Main] Started in background / minimized-to-tray mode.')
    }
  })


  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

let isQuittingApproved = false

async function requestMobileShutdownApproval(): Promise<boolean> {
  try {
    const response = await net.fetch('http://127.0.0.1:8000/api/v1/mobile/shutdown_approval/request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    if (response.ok) {
      const data = await response.json()
      console.log('[Security Gatekeeper] Backend shutdown approval result:', data)
      return data.approved === true
    }
  } catch (err) {
    console.error('[Security Gatekeeper] Shutdown approval check error:', err)
  }
  // Default to FALSE so JARVIS stays open if mobile approval was denied, timed out, or unavailable!
  return false
}

  // Handle window close -> Minimize to system tray instead of terminating
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      mainWindow?.hide()
      console.log('[Tray] Window minimized to system tray.')
    }
  })


  // When main window is focused, hide the Siri widget popup
  mainWindow.on('focus', () => {
    if (siriWindow && !siriWindow.isDestroyed() && siriWindow.isVisible()) {
      siriWindow.hide()
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

function createSiriWindow(): void {
  siriWindow = new BrowserWindow({
    width: 320,
    height: 120,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    show: false,
    focusable: false, // Prevent focus stealing
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true
    }
  })

  // Position at top center of primary monitor (directly below webcam)
  const { screen } = require('electron')
  const primaryDisplay = screen.getPrimaryDisplay()
  const { width: screenWidth } = primaryDisplay.workAreaSize
  siriWindow.setBounds({
    x: Math.round((screenWidth - 320) / 2),
    y: 10,
    width: 320,
    height: 120
  })

  // Let mouse events click through
  siriWindow.setIgnoreMouseEvents(true, { forward: true })

  if (!app.isPackaged && process.env['ELECTRON_RENDERER_URL']) {
    siriWindow.loadURL(`${process.env['ELECTRON_RENDERER_URL']}#siri`)
  } else {
    siriWindow.loadURL(`file://${join(__dirname, '../renderer/index.html')}#siri`)
  }

  siriWindow.on('closed', () => {
    siriWindow = null
  })
}

function handleSiriWindowVisibility(state: string): void {
  if (!siriWindow || siriWindow.isDestroyed()) return

  // If the main window is visible and currently focused, keep Siri hidden!
  if (mainWindow && mainWindow.isVisible() && mainWindow.isFocused()) {
    if (siriWindow.isVisible()) {
      siriWindow.hide()
    }
    return
  }

  if (state !== 'idle') {
    if (siriHideTimeout) {
      clearTimeout(siriHideTimeout)
      siriHideTimeout = null
    }
    if (!siriWindow.isVisible()) {
      siriWindow.showInactive()
    }
  } else {
    // If state is idle, wait 4 seconds before hiding so user sees it finish speaking/listening
    if (!siriHideTimeout) {
      siriHideTimeout = setTimeout(() => {
        if (siriWindow && !siriWindow.isDestroyed()) {
          siriWindow.hide()
        }
        siriHideTimeout = null
      }, 4000)
    }
  }
}

function showSiriWindowTemporarily(durationMs: number): void {
  if (!siriWindow || siriWindow.isDestroyed()) return

  // If the main window is visible and currently focused, keep Siri hidden!
  if (mainWindow && mainWindow.isVisible() && mainWindow.isFocused()) {
    return
  }

  if (siriHideTimeout) {
    clearTimeout(siriHideTimeout)
  }

  siriWindow.showInactive()
  siriWindow.webContents.send('status-update', { state: 'wake_word_detected', audioLevel: 0 })

  // Transition to idle after 2s, which will trigger hiding after another 3s
  setTimeout(() => {
    if (siriWindow && !siriWindow.isDestroyed()) {
      siriWindow.webContents.send('status-update', { state: 'idle', audioLevel: 0 })
      siriHideTimeout = setTimeout(() => {
        if (siriWindow && !siriWindow.isDestroyed()) {
          siriWindow.hide()
        }
        siriHideTimeout = null
      }, 3000)
    }
  }, 2000)
}

function createTray(): void {
  const icon = createTrayIcon()
  tray = new Tray(icon)

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open JARVIS',
      click: (): void => {
        if (mainWindow) {
          if (mainWindow.isMinimized()) mainWindow.restore()
          mainWindow.show()
          mainWindow.focus()
        }
      }
    },
    {
      label: 'Toggle Live Mode',
      click: async (): Promise<void> => {
        try {
          const port = getBackendPort()
          isLiveModeActive = !isLiveModeActive
          await net.fetch(`http://127.0.0.1:${port}/api/v1/mobile/live_mode/toggle?enable=${isLiveModeActive}`, { method: 'POST' })
          if (Notification.isSupported()) {
            new Notification({
              title: '👁️ JARVIS Live Mode',
              body: `Live Mode ${isLiveModeActive ? 'Activated' : 'Deactivated'}`,
              silent: false
            }).show()
          }
        } catch (e) {
          console.error('[Tray] Failed to toggle live mode:', e)
        }
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
      label: 'Quit JARVIS',
      click: (): void => {
        isQuitting = true
        app.quit()
      }
    }
  ])

  tray.setToolTip('JARVIS AI Assistant')
  tray.setContextMenu(contextMenu)

  tray.on('double-click', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })

  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide()
      } else {
        mainWindow.show()
        mainWindow.focus()
      }
    }
  })
}


function createOmniWindow(): void {
  const { screen } = require('electron')
  const primaryDisplay = screen.getPrimaryDisplay()
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize

  const width = 640
  const height = 64

  omniWindow = new BrowserWindow({
    width,
    height,
    x: Math.round((screenWidth - width) / 2),
    y: Math.round(screenHeight * 0.25),
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    show: false,
    focusable: true,
    webPreferences: {
      sandbox: false,
      contextIsolation: false,
      nodeIntegration: true
    }
  })

  const omniHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        html, body { background: transparent; width: 100%; height: 100%; overflow: hidden; display: flex; align-items: center; justify-content: center; }
        .omni-bar {
          width: 100%; height: 100%;
          background: rgba(3, 7, 18, 0.96);
          border: 1.5px solid #00e5ff;
          border-radius: 14px;
          box-shadow: 0 10px 30px rgba(0, 229, 255, 0.25), 0 0 20px rgba(0, 0, 0, 0.9);
          display: flex; align-items: center; padding: 0 16px; gap: 12px;
        }
        .icon { font-size: 18px; color: #00e5ff; text-shadow: 0 0 8px #00e5ff; }
        input {
          flex: 1; background: transparent; border: none; outline: none;
          color: #f8fafc; font-size: 15px; font-weight: 500;
        }
        input::placeholder { color: #475569; font-size: 13px; }
        .badge {
          font-size: 10px; font-weight: bold; color: #64748b;
          border: 1px solid #334155; padding: 3px 6px; border-radius: 4px;
        }
        .status-pill {
          display: none; font-size: 11px; color: #10b981; font-weight: 600;
        }
      </style>
    </head>
    <body>
      <div class="omni-bar">
        <span class="icon">⚡</span>
        <input id="promptInput" type="text" placeholder="Ask JARVIS or type a command... (Esc to dismiss)" autofocus />
        <span id="statusPill" class="status-pill">Routing...</span>
        <span class="badge">ESC</span>
      </div>
      <script>
        const { ipcRenderer } = require('electron');
        const input = document.getElementById('promptInput');
        const status = document.getElementById('statusPill');

        window.addEventListener('keydown', (e) => {
          if (e.key === 'Escape') {
            ipcRenderer.send('omni-hide');
          } else if (e.key === 'Enter') {
            const val = input.value.trim();
            if (val) {
              status.style.display = 'inline';
              status.innerText = 'Routing to Planner...';
              ipcRenderer.send('omni-submit', val);
              input.value = '';
            }
          }
        });

        ipcRenderer.on('omni-focus', () => {
          input.value = '';
          status.style.display = 'none';
          input.focus();
        });
      </script>
    </body>
    </html>
  `

  omniWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(omniHtml)}`)

  omniWindow.on('blur', () => {
    omniWindow?.hide()
  })

  omniWindow.on('closed', () => {
    omniWindow = null
  })
}

function registerGlobalShortcuts(): void {
  // Push-to-talk: Ctrl+Space
  globalShortcut.register('CommandOrControl+Space', () => {
    mainWindow?.webContents.send('push-to-talk-toggle')
  })

  // Global Omni-Bar: Alt+Shift+Space (Conflict-free in Windows, avoids Alt+Space Win32 menu)
  const omniShortcut = 'Alt+Shift+Space'
  const ok = globalShortcut.register(omniShortcut, () => {
    if (omniWindow) {
      if (omniWindow.isVisible()) {
        omniWindow.hide()
      } else {
        omniWindow.show()
        omniWindow.focus()
        omniWindow.webContents.send('omni-focus')
      }
    }
  })
  console.log(`[Main] Registered global Omni-Bar shortcut (${omniShortcut}):`, ok)
}


// IPC Handlers
function setupIPC(): void {
  ipcMain.handle('window-minimize', () => {
    mainWindow?.minimize()
  })

  ipcMain.handle('window-maximize', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize()
      } else {
        mainWindow.maximize()
      }
      return mainWindow.isMaximized()
    }
    return false
  })

  ipcMain.handle('window-close', async () => {
    try {
      const port = getBackendPort()
      const http = require('http')
      
      // Query mobile gatekeeper for approval
      const req = http.request({
        hostname: '127.0.0.1',
        port: port,
        path: '/api/v1/mobile/shutdown_approval/request',
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        timeout: 4000
      }, (res: any) => {
        let body = ''
        res.on('data', (chunk: any) => body += chunk)
        res.on('end', () => {
          try {
            const data = JSON.parse(body)
            if (data.approved === false) {
              if (Notification.isSupported()) {
                new Notification({
                  title: '🛡️ Security Gatekeeper Interlock',
                  body: 'Desktop exit denied by Mobile Companion approval gate.'
                }).show()
              }
              return
            }
          } catch (e) {
            // Ignore parse errors
          }
          mainWindow?.close()
        })
      })
      req.on('error', () => {
        mainWindow?.close()
      })
      req.end()
    } catch (err) {
      mainWindow?.close()
    }
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

  // Live Mode System-Wide Screen-Dimming Spotlight Overlay IPC Handlers
  ipcMain.handle('live-mode:toggle-overlay', (_event, enable: boolean) => {
    if (enable) {
      createOverlayWindow()
    } else {
      destroyOverlayWindow()
    }
  })

  ipcMain.handle('live-mode:update-spotlight', (_event, bounds: { x: number; y: number; w: number; h: number }) => {
    if (overlayWindow && !overlayWindow.isDestroyed()) {
      overlayWindow.webContents.executeJavaScript(`window.updateSpotlight && window.updateSpotlight(${JSON.stringify(bounds)})`)
    }
  })

  // Sync state between renderer and Siri overlay window
  ipcMain.on('renderer-state-update', (_event, data: { state: string; audioLevel: number }) => {
    if (siriWindow && !siriWindow.isDestroyed()) {
      siriWindow.webContents.send('status-update', data)
    }
    handleSiriWindowVisibility(data.state)
  })

  // Show and fullscreen main window when websocket is connected
  ipcMain.on('websocket-connected', () => {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
    }
  })

  // Omni-Bar IPC Handlers
  ipcMain.on('omni-hide', () => {
    omniWindow?.hide()
  })

  ipcMain.on('omni-submit', async (_event, prompt: string) => {
    console.log('[OmniBar] Dispatched command:', prompt)
    omniWindow?.hide()

    try {
      const port = getBackendPort()
      const res = await net.fetch(`http://127.0.0.1:${port}/api/v1/mobile/system/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'natural_language', params: { prompt } })
      })
      const data = await res.json()
      console.log('[OmniBar] Result:', data)
      if (Notification.isSupported()) {
        new Notification({
          title: '⚡ JARVIS Omni-Bar',
          body: data.message || data.response || `Executed: ${prompt.slice(0, 50)}`,
          silent: false
        }).show()
      }
    } catch (err) {
      console.error('[OmniBar] Execution error:', err)
      if (Notification.isSupported()) {
        new Notification({
          title: '⚠️ JARVIS Omni-Bar Error',
          body: String(err),
          silent: false
        }).show()
      }
    }
  })
}

function handleContextCommandLine(args: string[]): void {
  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith('--context-action=')) {
      const action = args[i].split('=')[1]
      const targetPath = args[i + 1] || ''
      if (targetPath) {
        dispatchContextAction(action, targetPath)
      }
    }
  }
}

async function dispatchContextAction(action: string, targetPath: string): Promise<void> {
  try {
    const port = getBackendPort()
    console.log(`[Explorer Context] Dispatching action '${action}' on: ${targetPath}`)
    await net.fetch(`http://127.0.0.1:${port}/api/v1/desktop/context_action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, target_path: targetPath })
    })
    if (Notification.isSupported()) {
      new Notification({
        title: '📁 Windows Explorer Action',
        body: `Processing ${action} for ${targetPath}`,
        silent: false
      }).show()
    }
  } catch (err) {
    console.error('[Main] Failed to dispatch context action:', err)
  }
}


let overlayWindow: BrowserWindow | null = null

function createOverlayWindow(): void {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.showInactive()
    return
  }

  const { screen } = require('electron')
  const displays = screen.getAllDisplays()

  let minX = 0, minY = 0, maxX = 0, maxY = 0
  for (const d of displays) {
    minX = Math.min(minX, d.bounds.x)
    minY = Math.min(minY, d.bounds.y)
    maxX = Math.max(maxX, d.bounds.x + d.bounds.width)
    maxY = Math.max(maxY, d.bounds.y + d.bounds.height)
  }

  overlayWindow = new BrowserWindow({
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    resizable: false,
    focusable: false,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false
    }
  })

  overlayWindow.setAlwaysOnTop(true, 'screen-saver')
  overlayWindow.setIgnoreMouseEvents(true, { forward: true })

  const overlayHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body, html { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: transparent; }
        canvas { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
      </style>
    </head>
    <body>
      <canvas id="spotlightCanvas"></canvas>
      <script>
        const canvas = document.getElementById('spotlightCanvas');
        const ctx = canvas.getContext('2d');
        let currentSpotlight = null;

        function resize() {
          canvas.width = window.innerWidth;
          canvas.height = window.innerHeight;
          draw();
        }
        window.addEventListener('resize', resize);

        function draw() {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.fillStyle = 'rgba(0, 0, 0, 0.65)';
          ctx.fillRect(0, 0, canvas.width, canvas.height);

          if (currentSpotlight && currentSpotlight.w > 0 && currentSpotlight.h > 0) {
            ctx.globalCompositeOperation = 'destination-out';
            ctx.fillStyle = 'rgba(0, 0, 0, 1)';

            const r = 12;
            const x = currentSpotlight.x;
            const y = currentSpotlight.y;
            const w = currentSpotlight.w;
            const h = currentSpotlight.h;

            ctx.beginPath();
            if (ctx.roundRect) {
              ctx.roundRect(x, y, w, h, r);
            } else {
              ctx.rect(x, y, w, h);
            }
            ctx.fill();

            ctx.globalCompositeOperation = 'source-over';

            ctx.strokeStyle = '#00e5ff';
            ctx.lineWidth = 3;
            ctx.shadowColor = '#00e5ff';
            ctx.shadowBlur = 12;
            ctx.beginPath();
            if (ctx.roundRect) {
              ctx.roundRect(x, y, w, h, r);
            } else {
              ctx.rect(x, y, w, h);
            }
            ctx.stroke();
            ctx.shadowBlur = 0;
          }
        }

        resize();

        window.updateSpotlight = (bounds) => {
          currentSpotlight = bounds;
          draw();
        };
      </script>
    </body>
    </html>
  `

  overlayWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(overlayHtml)}`)
  overlayWindow.showInactive()

  overlayWindow.on('closed', () => {
    overlayWindow = null
  })
}

function destroyOverlayWindow(): void {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.destroy()
    overlayWindow = null
  }
}

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', (_event, commandLine) => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
    handleContextCommandLine(commandLine)
  })

  app.whenReady().then(() => {
    // Auto-grant microphone and camera permissions for getUserMedia
    session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
      const allowedPermissions = ['media', 'microphone', 'camera', 'audioCapture']
      callback(allowedPermissions.includes(permission))
    })

    setupIPC()
    createWindow()
    createSiriWindow()
    createOmniWindow()
    createTray()
    registerGlobalShortcuts()
    startBackendProcess()
    handleContextCommandLine(process.argv)

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
