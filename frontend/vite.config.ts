import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            if ('writeHead' in res) {
              if (!res.headersSent) {
                res.writeHead(503, {
                  'Content-Type': 'application/json',
                })
              }
              res.end(
                JSON.stringify({
                  success: false,
                  error: 'Backend API unavailable',
                  message:
                    'Backend server is not responding at http://127.0.0.1:8000. Please ensure FastAPI is running.',
                  detail: err.message,
                })
              )
            }
          })
        },
      },
    },
  },
})
