/**
 * 岁记 · 主题全局混入（Options API）
 * 在 main.js 通过 app.mixin() 注册，向每个组件注入：
 *   data.__theme        当前主题名（响应式，随 'sj:theme' 更新）
 *   computed.themeName  当前主题名
 *   computed.themeVars  可直接绑到页面根节点 :style 的 CSS 变量映射（实现运行时换肤）
 *   methods.setTheme / toggleTheme
 * 用法：页面最外层 <view :style="themeVars"> 包裹内容，切主题即整页换肤。
 */
import { getTheme, setTheme, toggleTheme } from './store.js'
import { buildCssVars } from './theme.js'

export default {
  data() {
    return { __theme: getTheme() }
  },
  computed: {
    themeName() {
      return this.__theme
    },
    themeVars() {
      return buildCssVars(this.__theme)
    }
  },
  created() {
    this.__themeHandler = (name) => { this.__theme = name }
    uni.$on('sj:theme', this.__themeHandler)
  },
  beforeUnmount() {
    if (this.__themeHandler) uni.$off('sj:theme', this.__themeHandler)
  },
  methods: {
    setTheme(name) { setTheme(name) },
    toggleTheme() { toggleTheme() }
  }
}
