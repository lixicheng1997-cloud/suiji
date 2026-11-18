<template>
  <el-container class="admin-shell">
    <el-aside width="210px" class="admin-aside">
      <div class="brand">
        <img class="brand-ico" :src="bearFace" alt="" />岁记<span class="brand-sub">管理台</span>
      </div>
      <el-menu :default-active="route.path" router class="admin-menu">
        <el-menu-item index="/dashboard"><img class="menu-ico" :src="icoHome" alt="" /><span>数据概览</span></el-menu-item>
        <el-menu-item index="/users"><img class="menu-ico" :src="icoUser" alt="" /><span>用户管理</span></el-menu-item>
        <el-menu-item index="/families"><img class="menu-ico" :src="icoFamily" alt="" /><span>家庭管理</span></el-menu-item>
        <el-menu-item index="/media"><img class="menu-ico" :src="icoMedia" alt="" /><span>媒体中心</span></el-menu-item>
        <el-menu-item index="/audit"><img class="menu-ico" :src="icoAudit" alt="" /><span>审计日志</span></el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="admin-header">
        <div class="header-title">{{ route.meta.title || '' }}</div>
        <el-dropdown @command="onCommand">
          <span class="user-chip">
            <el-avatar :size="28" class="user-avatar">{{ (session.displayName || 'A').charAt(0) }}</el-avatar>
            {{ session.displayName }}<el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useSession } from '../stores/session'
import bearFace from '../assets/icons/bear-face.png'
import icoHome from '../assets/icons/10-tab-home.png'
import icoUser from '../assets/icons/13-tab-me.png'
import icoFamily from '../assets/icons/12-tab-family.png'
import icoMedia from '../assets/icons/04-photo.png'
import icoAudit from '../assets/icons/35-fn-audit.png'

const route = useRoute()
const router = useRouter()
const session = useSession()

async function onCommand(cmd) {
  if (cmd !== 'logout') return
  try {
    await ElMessageBox.confirm('退出后需要重新登录才能使用后台，确定退出吗？', '退出登录', {
      confirmButtonText: '退出', cancelButtonText: '再想想', type: 'warning'
    })
  } catch (e) { return }
  await session.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-shell { height: 100%; }
.admin-aside {
  background: var(--sj-card);
  border-right: 1px solid var(--sj-line);
  display: flex;
  flex-direction: column;
}
.brand {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 18px;
  font-size: 19px;
  font-weight: 700;
  font-family: var(--sj-font-title);
  color: var(--sj-honey-deep);
  border-bottom: 1px solid var(--sj-line);
}
.brand-ico { width: 26px; height: 26px; }
/* 菜单绘本图标 */
.menu-ico { width: 20px; height: 20px; margin-right: 8px; flex-shrink: 0; }
.brand-sub { font-size: 12px; font-weight: 400; color: var(--sj-ink-3); margin-left: 4px; }
.admin-menu {
  border-right: none;
  flex: 1;
  padding: 10px 12px;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: var(--sj-ink-2);
  --el-menu-hover-bg-color: var(--sj-honey-soft);
  --el-menu-active-color: var(--sj-honey-deep);
}
/* 菜单选中项：圆角胶囊 + 蜂蜜浅底深字 */
.admin-menu :deep(.el-menu-item) {
  height: 46px;
  border-radius: var(--sj-radius-pill);
  margin-bottom: 6px;
  font-family: var(--sj-font-title);
  transition: background .2s var(--sj-ease-pop), color .2s;
}
.admin-menu :deep(.el-menu-item:hover) { background: var(--sj-honey-soft); }
.admin-menu :deep(.el-menu-item.is-active) {
  background: var(--sj-honey-soft);
  color: var(--sj-honey-deep);
  font-weight: 700;
}
.admin-header {
  background: var(--sj-card);
  border-bottom: 1px solid var(--sj-line);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-title { font-size: 16px; font-weight: 600; font-family: var(--sj-font-title); color: var(--sj-ink); }
.user-chip {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
  color: var(--sj-ink); font-size: 14px;
  padding: 4px 12px 4px 4px; border-radius: var(--sj-radius-pill);
  transition: background .2s var(--sj-ease-pop);
}
.user-chip:hover { background: var(--sj-honey-soft); }
.user-avatar { background: var(--sj-honey); }
.admin-main { background: var(--sj-cream); padding: 0; }
</style>
