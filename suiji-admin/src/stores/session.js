import { defineStore } from 'pinia'
import * as http from '../api/http'

const USER_KEY = 'sj_admin_user'

export const useSession = defineStore('session', {
  state: () => ({
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  }),
  getters: {
    isAdmin: s => !!(s.user && s.user.is_admin),
    displayName: s => (s.user ? (s.user.name || s.user.username) : '')
  },
  actions: {
    async login(username, password) {
      const d = await http.post('/auth/login', { username, password }, { silent: true })
      // 非管理员账号：令牌不落盘，直接拒登（路由守卫之外再挡一道）
      if (!d.user || !d.user.is_admin) {
        const e = new Error('该账号不是管理员，无法登录后台')
        e.friendly = e.message
        throw e
      }
      http.setTokens(d.access, d.refresh, d.media)
      this.setUser(d.user)
      return d.user
    },
    setUser(u) {
      this.user = u
      localStorage.setItem(USER_KEY, JSON.stringify(u))
    },
    /** 守卫用会话自检：刷新页面后确认令牌仍是管理员（被撤权/停用立即失效） */
    async verify() {
      const me = await http.get('/admin/me', { silent: true })
      this.setUser({ id: me.id, username: me.username, name: me.name, is_admin: 1 })
      return me
    },
    async logout() {
      const refresh = http.getRefreshToken()
      if (http.getAccessToken()) {
        try { await http.post('/auth/logout', { refresh }, { silent: true }) } catch (e) { /* 网络不通也要能退出 */ }
      }
      http.clearTokens()
      this.user = null
      localStorage.removeItem(USER_KEY)
    }
  }
})
