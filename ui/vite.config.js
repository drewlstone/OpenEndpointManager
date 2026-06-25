import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // dev: proxy API calls to the admin-api so there's no CORS friction
      '/api': { target: 'http://localhost:8000', changeOrigin: true }
    }
  },
  build: { outDir: 'dist' }
})
