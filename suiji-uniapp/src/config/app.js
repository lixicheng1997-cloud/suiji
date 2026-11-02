/**
 * 岁记 · 前端公共配置
 *
 * 服务器地址等环境相关配置一律写死在本文件，不再从服务端 /servers
 * （server_endpoint 表）拉取；换环境 / 加地址只改这里，重新打包即可。
 */

/* 现役端口：nginx 统一入口 30080；旧版本直连 8000，读取本机历史地址时自动升级 */
export const CURRENT_PORT = 30080
export const LEGACY_PORT = 8000

/* 可选服务器列表（登录页 / 「我的」页共用）：
 * id 为本机「已选服务器」记录用的稳定标识；is_default 标记首次启动的默认地址。 */
export const SERVERS = [
  { id: 'cloud', name: '云服务', url: 'http://49.233.77.155:30080/api/v1', env: 'prod', is_default: 1 },
  { id: 'local', name: '本地调试', url: 'http://localhost:30080/api/v1', env: 'dev', is_default: 0 }
]

/* 兜底地址：本机没选过服务器时使用，默认取 SERVERS 中 is_default 的那条 */
const __default = SERVERS.find(s => s.is_default) || SERVERS[0]
export const DEFAULT_BASE = __default ? __default.url : ''

/* 消息（家人动态）获取周期，单位毫秒：App 在前台时每该间隔发一次
 * GET /events/count（一个请求同时带回未读通知，见 utils/api.js checkEvents）。
 * 改这里即可调整拉取频率：15000=15 秒，30000=30 秒，60000=60 秒。
 * 现值取 30 秒：单请求 + 只在真有新记录时才重拉快照后，这个节奏下前台通知延迟
 * 最多 30 秒，QPS/电量/流量都比旧实现低；越短实时性越好但同比上升。
 * 后台/被杀不轮询，靠下次冷启动 init() 补弹，本参数不影响后台可达性。 */
export const MESSAGE_POLL_INTERVAL = 30000
