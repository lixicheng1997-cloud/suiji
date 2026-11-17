/**
 * 网络环境快照：缓存当前网络类型与连接状态，供请求日志 / 调试页读取。
 *
 * uni.getNetworkType 是异步接口：启动瞬间快照为 unknown，回调成功后回填；
 * onNetworkStatusChange 在网络切换（WiFi ↔ 移动数据 / 断网）时持续更新。
 * 三端兼容：H5 / 小程序无对应能力时静默保留 unknown，不阻断业务。
 */

let snapshot = { type: 'unknown', connected: true, effectiveType: '' }

function apply(info) {
  if (!info) return
  snapshot = {
    type: info.networkType || info.type || 'unknown',
    connected: info.isConnected !== false,
    effectiveType: info.effectiveType || ''
  }
}

/** 启动时调用一次：拉取当前网络并注册变化监听（重复调用幂等） */
export function initNetWatch() {
  try {
    if (typeof uni !== 'undefined' && uni.getNetworkType) {
      uni.getNetworkType({ success: apply, fail: () => {} })
    }
    if (typeof uni !== 'undefined' && uni.onNetworkStatusChange) {
      uni.onNetworkStatusChange(apply)
    }
  } catch (e) { /* 平台不支持：保留 unknown 快照 */ }
}

/** 当前网络快照副本：{ type, connected, effectiveType } */
export function netInfo() {
  return { ...snapshot }
}

/** 短标签：无网络 / wifi / 4g / 5g / unknown，便于直接写进日志消息 */
export function netLabel() {
  const n = snapshot
  if (!n.connected) return '无网络'
  return n.type || 'unknown'
}
