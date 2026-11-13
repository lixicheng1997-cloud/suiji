/**
 * 岁记 · 前端公共配置（dev / prod 双环境）
 *
 * 服务器地址等环境相关配置一律写死在本文件，不再从服务端 /servers
 * （server_endpoint 表）拉取；换环境 / 加地址只改这里，重新打包即可。
 *
 * 环境判定：uni-app 编译链路注入 process.env.NODE_ENV ——
 *   `npm run dev:*`（uni 启动开发）→ development（dev 环境）
 *   `npm run build:*`（uni build 打包）→ production（prod 环境）
 * 据此选择「默认服务器」；列表里另一条环境仍保留，可在选择器里手动切换。
 */

/* 云端/生产 nginx 统一入口端口 30080；旧版本本地直连也用过这个端口，读取本机历史地址时迁移到本地 Docker 入口 */
export const CURRENT_PORT = 30080
/* 旧版本本地直连端口 8000（已废弃） */
export const LEGACY_PORT = 8000
/* 本地 Docker 开发环境入口端口（从 30000 起顺延，见 suiji-server/.env.dev） */
export const LOCAL_DEV_PORT = 30000

/* 运行环境标识：'dev' | 'prod'。非 production 一律按 dev 处理（本地调试/HBuilderX 预览） */
export const APP_ENV = (process.env.NODE_ENV === 'production') ? 'prod' : 'dev'

/* 可选服务器列表（登录页 / 「我的」页共用）：
 * id 为本机「已选服务器」记录用的稳定标识；env 标记所属环境；
 * is_default 仅在对应编译环境下作为首次启动默认地址（下方按 APP_ENV 计算）。 */
const SERVER_DEFS = [
  { id: 'cloud', name: '云服务', env: 'prod', url: 'http://49.233.77.155:30080/api/v1' },
  { id: 'local', name: '本地调试', env: 'dev', url: 'http://localhost:30000/api/v1' }
]

/* 当前编译环境对应的默认服务器：dev 包默认本地，prod 包默认云端；
 * 列表本身两条都保留，方便在选择器里临时切到另一套后端。 */
const __defaultServer = SERVER_DEFS.find(s => s.env === APP_ENV) || SERVER_DEFS[0]

export const SERVERS = SERVER_DEFS.map(s => ({ ...s, is_default: s.id === __defaultServer.id }))

/* 兜底地址：本机没选过服务器时使用，默认取当前环境的那条 */
export const DEFAULT_BASE = __defaultServer.url

/* 登录页是否展示「数据保存位置 / 切换服务器」入口（含底部选择面板）。
 * 0/false：隐藏入口，地址固定走当前环境默认项（正式打包默认值）；
 * 1/true：  展示入口，可在登录页切换服务器（本地调试用）。
 * 规则：dev 编译默认打开便于切换；prod 编译默认关闭。需要在 prod 包里临时切换时改这里。 */
export const SHOW_SERVER_PICKER = APP_ENV === 'dev' ? 1 : 0

/* 消息（家人动态）获取周期，单位毫秒：App 在前台时每该间隔发一次
 * GET /events/count（一个请求同时带回未读通知，见 utils/api.js checkEvents）。
 * 改这里即可调整拉取频率：15000=15 秒，30000=30 秒，60000=60 秒。
 * 现值取 30 秒：单请求 + 只在真有新记录时才重拉快照后，这个节奏下前台通知延迟
 * 最多 30 秒，QPS/电量/流量都比旧实现低；越短实时性越好但同比上升。
 * 后台/被杀不轮询，靠下次冷启动 init() 补弹，本参数不影响后台可达性。 */
export const MESSAGE_POLL_INTERVAL = 30000
