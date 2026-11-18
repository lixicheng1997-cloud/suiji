import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// base 必须是 /admin/：产物部署在 nginx /admin/ 子路径下，漏配会白屏（资源落 H5 兜底）
export default defineConfig({
  base: '/admin/',
  plugins: [vue()],
  server: {
    port: 5175,
    proxy: {
      // 本地联调：/api → 本机后端（与生产 nginx 同形态，前端代码零 baseUrl 配置）
      '/api': { target: 'http://127.0.0.1:30080', changeOrigin: true }
    }
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1200
  }
})
