import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发模式：vite 起在 5173，/api 代理到后端 8000
// 生产模式：npm run build 产出 dist/，由 FastAPI 直接托管
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000'
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
})
