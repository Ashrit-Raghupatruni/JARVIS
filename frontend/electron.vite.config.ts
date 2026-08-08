import { resolve } from 'path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        external: ['electron']
      }
    }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        external: ['electron']
      }
    }
  },
  renderer: {
    resolve: {
      alias: {
        '@': resolve('src/renderer/src'),
        '@components': resolve('src/renderer/src/components'),
        '@hooks': resolve('src/renderer/src/hooks'),
        '@stores': resolve('src/renderer/src/stores'),
        '@types': resolve('src/renderer/src/types')
      }
    },
    plugins: [react(), tailwindcss()],
    server: {
      host: true, // Expose dev server to LAN / other desktops (0.0.0.0)
      port: 5173,
      proxy: {
        // Proxy REST API calls to FastAPI backend with clean cold-start error suppression
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('error', (_err, _req, res: any) => {
              if (res && typeof res.writeHead === 'function' && !res.headersSent) {
                res.writeHead(503, { 'Content-Type': 'application/json' })
                res.end(JSON.stringify({ status: 'backend_booting', message: 'FastAPI backend starting up...' }))
              }
            })
          }
        },
        // Proxy WebSocket connections to FastAPI backend with clean reconnect handling
        '/ws': {
          target: 'ws://127.0.0.1:8000',
          ws: true,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('error', (_err, req: any, res: any) => {
              if (req.headers && req.headers.upgrade === 'websocket') {
                if (req.socket && !req.socket.destroyed) {
                  req.socket.destroy()
                }
                return
              }
              if (res && typeof res.writeHead === 'function' && !res.headersSent) {
                res.writeHead(503, { 'Content-Type': 'application/json' })
                res.end(JSON.stringify({ status: 'backend_booting' }))
              }
            })
          }
        }
      }
    },
    build: {
      rollupOptions: {
        input: resolve(__dirname, 'src/renderer/index.html')
      }
    }
  }
})
