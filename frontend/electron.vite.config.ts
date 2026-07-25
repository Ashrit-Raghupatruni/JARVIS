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
        // Proxy REST API calls to FastAPI backend
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true
        },
        // Proxy WebSocket connections to FastAPI backend with clean reconnect handling
        '/ws': {
          target: 'ws://127.0.0.1:8000',
          ws: true,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('error', (err) => {
              // Suppress noisy ECONNREFUSED logs while backend is starting
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
