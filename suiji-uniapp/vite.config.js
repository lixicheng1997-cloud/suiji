import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
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
