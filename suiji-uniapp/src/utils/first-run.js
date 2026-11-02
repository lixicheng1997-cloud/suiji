/**
 * 首次安装（本机标记）与登录门控（TDD v3.0 启动链路）
 *
 * 启动顺序：splash → 登录 → 宝宝档案判定
 *  1) 未登录 → 直接进登录（首次安装引导 pages/onboard 的入口逻辑已移除，页面暂保留）；
 *  2) 登录后：无关联家庭 → 进 pages/family-setup 强制创建/加入家庭；
 *     有家庭但无宝宝档案 → 进 pages/baby?new=1 新建档案；
 *     有档案但未留痕隐私同意 → 进 pages/consent；否则进首页。
 *
 * 「是否安装过」只写本机 Storage（uni storage，不随账号同步）：
 * 卸载重装或清除应用数据后标记丢失 → 再次进入引导流程。
 */

import * as http from '@/api/http.js'
import * as api from '@/utils/api.js'

const INSTALL_KEY = 'sj_installed'

/** 本机是否安装（运行）过本软件：无标记视为首次安装 */
export function isInstalled() {
  try { return !!uni.getStorageSync(INSTALL_KEY) } catch (e) { return false }
}

/** 落本机安装标记（值为首次进入日期，便于排查） */
export function markInstalled() {
  try {
    uni.setStorageSync(INSTALL_KEY, new Date().toISOString().slice(0, 10))
  } catch (e) { /* 存储不可用时退化为每次都走引导 */ }
}

/** 调试/演示用：清掉标记，下次启动重走引导 */
export function resetInstalled() {
  try { uni.removeStorageSync(INSTALL_KEY) } catch (e) { /* ignore */ }
}

/** 引导流程结束（看完或跳过）：落标记并进登录页 */
export function finishGuide() {
  markInstalled()
  uni.reLaunch({ url: '/pages/login/login' })
}

/** 家庭引导页路径：未关联家庭时唯一允许停留的业务入口 */
export const FAMILY_SETUP = '/pages/family-setup/family-setup'

/** 家庭门控期间允许停留的页面：引导页自身 + 未登录期的登录/启动/首次安装引导 */
const GUARD_WHITE = [FAMILY_SETUP, '/pages/login/login', '/pages/splash/splash', '/pages/onboard/onboard']

/** 是否处于「已登录但未关联家庭」状态：此时禁止进入任何业务页面（管理员放行） */
export function needFamilySetup() {
  return api.isLoggedIn() && !api.hasFamily() && !api.isAdmin()
}

/**
 * 安装家庭路由守卫：已登录但未关联家庭的账号，任何跳转业务页面的动作都会被改写到引导页。
 * 配合后端 409 need_family（http 层处理）形成双重强制——
 * 用户只能①输入家庭名称创建 ②输入邀请码加入，二者之一完成才能继续。
 */
export function redirectToFamilySetup() {
  uni.reLaunch({ url: FAMILY_SETUP })
}

export function installFamilyGuard() {
  // 后端 409 need_family 到达时由 http 层转交：先清缓存再跳引导页，保证门控判定一致
  http.setNeedFamilyHandler(() => {
    api.resetFamilyCache()
    redirectToFamilySetup()
  })
  // 401 刷新失败被踢下线时由 http 层转交：清内存缓存并停轮询，防止旧会话数据残留在页面
  http.setExpireHandler(() => api.resetAccountSession())
  const guard = args => {
    const target = String((args && args.url) || '').split('?')[0]
    if (GUARD_WHITE.indexOf(target) >= 0) return args
    if (!needFamilySetup()) return args
    redirectToFamilySetup()
    return false          // 中断原跳转
  }
  ;['navigateTo', 'redirectTo', 'switchTab', 'reLaunch'].forEach(m => {
    try { uni.addInterceptor(m, { invoke: guard }) } catch (e) { /* 端能力缺失时忽略 */ }
  })
}

/**
 * 登录后去向判定（缓存已由 bootstrap 灌满后调用）。
 * 无家庭 → 创建/加入引导页；无宝宝 → 新建档案页；有宝宝但未同意 → 隐私同意页；否则进首页。
 */
export function goAfterLogin() {
  if (!api.hasFamily()) {
    redirectToFamilySetup()
    return
  }
  /* 管理员：不强制建档/隐私同意，直接进首页（专属入口在「我的」页） */
  if (api.isAdmin()) {
    uni.switchTab({ url: '/pages/index/index' })
    return
  }
  if (!api.getBaby()) {
    uni.reLaunch({ url: '/pages/baby/baby?new=1' })
    return
  }
  if (!api.getConsent()) {
    uni.reLaunch({ url: '/pages/consent/consent' })
    return
  }
  uni.switchTab({ url: '/pages/index/index' })
}
