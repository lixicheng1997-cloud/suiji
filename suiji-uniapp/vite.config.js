import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    // 固定 H5 开发端口：被占用时直接报错退出，不再静默漂移到 5174 等其他端口，
    // 避免浏览器仍访问旧端口、误以为连到了旧后端。
    port: 5173,
    strictPort: true
  },
  css: {
    preprocessorOptions: {
      scss: {
        // Dart Sass ≥1.80 弃用了 legacy JS API 与 @import，uni 编译链路与 uview-plus
        // 组件源码仍在使用且无法修改，静默这两类提示以免终端刷屏（不影响编译产物）
        silenceDeprecations: ['legacy-js-api', 'import']
      }
    }
  }
})
