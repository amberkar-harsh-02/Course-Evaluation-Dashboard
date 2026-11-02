import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served at /course-eval-app/ behind Caddy; Caddy forwards /course-eval-app/api/* to the backend on :8010.
// In development the same forwarding is done by the proxy below.
export default defineConfig({
  plugins: [react()],
  base: '/course-eval-app/',
  server: {
    proxy: {
      '/course-eval-app/api': {
        target: 'http://127.0.0.1:8010',
        rewrite: (path) => path.replace(/^\/course-eval-app/, ''),
      },
    },
  },
})
