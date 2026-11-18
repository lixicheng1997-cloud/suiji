import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from '../stores/session'
import * as http from '../api/http'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('../layouts/AdminLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '数据概览' } },
      { path: 'users', name: 'users', component: () => import('../views/Users.vue'), meta: { title: '用户管理' } },
      { path: 'families', name: 'families', component: () => import('../views/Families.vue'), meta: { title: '家庭管理' } },
      { path: 'media', name: 'media', component: () => import('../views/Media.vue'), meta: { title: '媒体中心' } },
      { path: 'audit', name: 'audit', component: () => import('../views/AuditLogs.vue'), meta: { title: '审计日志' } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHistory('/admin/'),
  routes
})

router.beforeEach(async to => {
  if (to.meta && to.meta.public) return true
  if (!http.getAccessToken()) return { path: '/login' }
  const session = useSession()
  if (!session.isAdmin) {
    try {
      await session.verify()
    } catch (e) {
      return { path: '/login' }
    }
  }
  return true
})

export default router
