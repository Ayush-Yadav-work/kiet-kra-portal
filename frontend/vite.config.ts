import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev server proxies the API so cookies/CSRF stay same-origin (D-020).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    // KRA_API_TARGET lets the isolated browser-test run point at its own Django (e2e/run_isolated.py).
    proxy: { '/api': process.env.KRA_API_TARGET ?? 'http://127.0.0.1:8000' },
  },
})
