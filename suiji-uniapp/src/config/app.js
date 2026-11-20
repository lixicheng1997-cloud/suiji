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

/* 默认一律连云服务：真机调试基座访问不到开发机的 localhost，本地后端调试
 * 可在登录页「服务器地址」选择器手动切回「本地调试」。列表两条都保留。 */
const __defaultServer = SERVER_DEFS.find(s => s.id === 'cloud') || SERVER_DEFS[0]

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

/* ---------- 阿里云号码认证（一键登录 / 本机号码校验） ----------
 * 总开关：置 0 可一键下线手机号登录入口（后端另有 ALIYUN_PHONE_ENABLED 端点级闸）。
 * 平台支持：App（Android/iOS 原生插件）+ H5（网页版 SDK）；微信小程序不支持。
 * 注意：App 端需在 DCloud 插件市场选购「阿里云号码认证」插件并打自定义基座后，
 * 真机才有取号能力；标准基座 / 未插 SIM / 运营商不支持时前端自动回退账号密码。 */
export const PHONE_LOGIN_ENABLED = 1
/* App 端原生插件名与初始化参数（以实际选购插件的文档为准，改这里即可适配）：
 * 插件契约：setAuthSDKInfo(info) 设置密钥；getLoginToken(timeout, config, tokenCb, uiCb, customCb)
 * 唤起一键登录授权页；getVerifyToken(timeout, cb) 取本机号码校验令牌。
 * 回调统一 {resultCode, msg, token}，resultCode 为字符串 "600000" 表示成功。
 * 插件市场地址：https://ext.dcloud.net.cn/plugin?id=4297 */
export const PHONE_AUTH_PLUGIN = 'AliCloud-NirvanaPns'
/* 阿里云号码认证控制台生成的密钥（与 Bundle Id / 包名绑定，必填，否则 SDK 无法初始化）：
 * 控制台路径：号码认证服务 → 认证方案管理 → 创建方案 → 复制 SDK信息 */
export const PHONE_AUTH_SDK_INFO = 'Y/wsdfqrj7O3EVxU99bzb+9EHhQDvcx+ZH4G3/bxy+eVWMvBbIqQ2f5nlQR1mRysg8u8+ATXIhM4aOl79YtVvPk7MTm3dEqzoyx7PeerA0yl/Bp3UrvweTW1jjT1XsNJXFU1s7YQrutZRbM8kq34GSCQ/B79R1LLysAIvKC9GGBKHZyDIbWX0jKT2IkDP/i+9FZHarEbmrp7K8S7JtpftZ/eVMsc5Aa0dDNIIzAkJLvkiv/XXFUN7zkqFwyO/kMynjsyWrBo8LgSoIRGHHRAwzocntPoygj8D7h4f+H4b9U='
/* H5 网页版认证 SDK 地址与全局对象名（以阿里云控制台开通号码认证后给出的接入文档为准） */
export const PHONE_AUTH_H5_SDK = 'https://g.alicdn.com/dypns/phoneauth/latest/index.js'
export const PHONE_AUTH_H5_GLOBAL = 'PhoneAuth'
