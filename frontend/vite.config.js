import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        'firebase-messaging-sw': fileURLToPath(new URL('./src/firebase-messaging-sw.js', import.meta.url)),
      },
      output: { entryFileNames: (chunk) => chunk.name === 'firebase-messaging-sw' ? 'firebase-messaging-sw.js' : 'assets/[name]-[hash].js' },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    headers: { 'Service-Worker-Allowed': '/' },
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
