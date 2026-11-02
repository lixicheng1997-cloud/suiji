import App from './App'
import { createSSRApp } from 'vue'
import uviewPlus from 'uview-plus'
import useTheme from './theme/useTheme.js'

export function createApp() {
  const app = createSSRApp(App)
  app.use(uviewPlus)
  // 全局主题混入：注入 themeName / themeVars / setTheme，支撑 bear/duck 实时换肤
  app.mixin(useTheme)
  return { app }
}
