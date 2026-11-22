import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em desenvolvimento, o Vite (porta 5173) repassa /api para o Django (porta 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
