/**
 * 岁记 · 静态展示常量（自原型 app.js 迁移）
 * 规则：页面只读本文件渲染，不硬编码散落数据。
 * 颜色一律十六进制字面量（小程序端不支持运行时 CSS 变量取色）。
 * 与 uni.scss 的 $sj-c-* / $sj-tint-* 令牌一一对应，改色需两处同步。
 * 业务数据一律走 utils/api.js（云端缓存），本文件不承载业务假数据。
 */

/* ---------- 记录类型元数据（v2 · 10 类，色值与 uni.scss $sj-c-* / $sj-tint-* 同步） ----------
   iconKey：旧 SVG 名（页面 Phase5 前仍引用 /static/icons/{iconKey}.svg）
   png：v2 图标库文件名（sj-icon 按主题解析 /static/icons/{theme}/{png}.jpg） */
export const TYPES = {
  feeding:   { label: '喂养',   iconKey: 'bottle',      png: '01-feeding',    color: '#F7A15C', tint: '#FFEBD8' },
  sleep:     { label: '睡眠',   iconKey: 'moon',        png: '02-sleep',      color: '#8FA8DC', tint: '#E9EEFB' },
  milestone: { label: '里程碑', iconKey: 'trophy',      png: '03-milestone',  color: '#F5B32C', tint: '#FFF3C4' },
  photo:     { label: '照片',   iconKey: 'camera',      png: '04-photo',      color: '#FF8FAB', tint: '#FFE7EE' },
  measure:   { label: '测量',   iconKey: 'ruler',       png: '05-measure',    color: '#5FC08C', tint: '#E2F5EA' },
  poop:      { label: '便便',   iconKey: 'cloud',       png: '06-poop',       color: '#C49066', tint: '#F5E9DC' },
  temp:      { label: '体温',   iconKey: 'thermometer', png: '07-temp',       color: '#FF7B6B', tint: '#FFE7E2' },
  med:       { label: '用药',   iconKey: 'pill',        png: '08-med',        color: '#A994D8', tint: '#F0EAFB' },
  mood:      { label: '心情',   iconKey: 'heart',       png: '09-text-mood',  color: '#E86FA0', tint: '#FDE9F2' },
  voice:     { label: '语音',   iconKey: 'music',       png: '09-voice',      color: '#6FBDE0', tint: '#E4F3FB' },
  /* note 为 mood 的历史别名，保留以兼容既有数据/页面（Phase5 统一迁移后移除） */
  note:      { label: '心情',   iconKey: 'heart',       png: '09-text-mood',  color: '#E86FA0', tint: '#FDE9F2' }
}

/* ---------- 徽标文案 ---------- */
export const BADGES = {
  milestone: '里程碑',
  backfill: '补记',
  ongoing: '进行中',
  p50: 'P50'
}

/* ================================================================
   多页面数据（自原型 app.js v0.2/v0.3 迁移，页面只读渲染）
   注：原型期的文生图占位头像 / 假相册 / 假动态已移除，
   展示数据一律来自 utils/api.js 真实记录，页面自行处理空态。
   ================================================================ */

/* ---------- 监护人同意分项（建档前，FR-35） ---------- */
export const CONSENTS = [
  { t: '《隐私政策》', d: '账号与基础信息 · 我们会收集什么、用来做什么、保存多久', req: true, on: true },
  { t: '《儿童个人信息处理规则》', d: '会收集哪些信息、存在哪里、分享给谁，都逐项说明', req: true, on: true },
  { t: '同意处理宝宝健康记录', d: '喂养 / 睡眠 / 体温 / 用药 · 云端加密保存', req: true, on: true },
  { t: '同意宝宝照片与视频存储于云端', d: '照片默认保存到云端 · 加密存储 · 仅家庭成员可见', req: true, on: true },
  { t: '同意记录用于 AI 成长日记', d: '自动生成 · 只使用你的记录 · 可随时撤回', req: false, on: false }
]

/* ---------- 家长信息（parent 页默认值，用户保存后以 setting 'parent' 为准） ---------- */
export const PARENT_INFO = {
  avatar: '',
  name: '',
  account: '',
  relation: '妈妈',
  relations: ['妈妈', '爸爸', '奶奶', '爷爷', '外婆', '外公'],
  cats: ['feeding', 'sleep', 'photo', 'milestone']
}

/* ---------- 宝宝档案：性别选项 ---------- */
export const GENDERS = ['女', '男']

/* ---------- 引导欢迎页 · 成长之书（首尾为封面/封底，中间为成长页） ---------- */
export const WB_PAGES = [
  {},
  { age: '出生 · 第 1 天', icon: 'heart', tint: '#FFE9EF', t: '第一次被抱进怀里', d: '体重、身长、第一口奶，都值得被记下' },
  { age: '1 个月', icon: 'moon', tint: '#EBF0FA', t: '睡整觉，是全家的大事', d: '睡眠与喂养计时，替你记住每个深夜' },
  { age: '3 个月', icon: 'sparkles', tint: '#FFF6DC', t: '第一次对你笑', d: '里程碑打卡，定格转瞬即逝的「第一次」' },
  { age: '6 个月', icon: 'bottle', tint: '#FFF0E2', t: '翻身，加上第一口辅食', d: '生长曲线与辅食记录，看得见成长轨迹' },
  { age: '9 个月', icon: 'camera', tint: '#FDE9F2', t: '坐得稳稳，喊出妈妈', d: '照片与视频，按时间轴自动归位' },
  { age: '12 个月', icon: 'gift', tint: '#F0ECFA', t: '第一步，和一周岁', d: '纪念卡与 AI 日记，把一年翻成一篇故事' },
  {}
]

/* ---------- 成长之书封底信任项 ---------- */
export const OW_FEATURES = [
  { icon: 'shield', tint: '#F3EAE2', t: '数据只属于这个家', d: '云端加密存储 · 换机登录即恢复' },
  { icon: 'users', tint: '#EBF0FA', t: '全家一起记录', d: '邀请码加入共享空间 · 只读开关随时调整' },
  { icon: 'sparkles', tint: '#FFF6DC', t: 'AI 成长日记', d: '基于你的记录生成 · 需单独授权' }
]

/* ================================================================
   v0.3 新增页面数据（自原型 app.js 迁移，页面只读渲染）
   ================================================================ */

/* ---------- 国家免疫规划疫苗清单（vaccine-new 默认全选） ---------- */
export const VACCINE_PROGRAM = [
  { n: '乙肝疫苗', doses: ['出生24小时内', '1月龄', '6月龄'] },
  { n: '卡介苗', doses: ['出生24小时内'] },
  { n: '脊髓灰质炎疫苗', doses: ['2月龄', '3月龄', '4月龄', '4周岁'] },
  { n: '百白破疫苗', doses: ['3月龄', '4月龄', '5月龄', '18月龄', '6周岁'] },
  { n: '麻腮风疫苗', doses: ['8月龄', '18月龄'] },
  { n: '乙脑疫苗', doses: ['8月龄', '2周岁'] },
  { n: '流脑疫苗', doses: ['A群6月龄', 'A群9月龄', 'AC群3周岁', 'AC群6周岁'] },
  { n: '甲肝疫苗', doses: ['18月龄', '24月龄'] }
]

/* ---------- 我的数据 · 隐私看板类别（data · P26 · FR-41）
   条数不写死：types 供页面按真实记录计数，diary 行取日记草稿状态 ---------- */
export const DATA_CATS = [
  { icon: 'bottle', label: '照护记录', types: ['feeding', 'sleep', 'poop', 'temp', 'med', 'mood', 'voice'], vis: '仅创建者可见' },
  { icon: 'ruler', label: '体格测量', types: ['measure'], vis: '仅创建者可见' },
  { icon: 'trophy', label: '里程碑', types: ['milestone'], vis: '全员可见' },
  { icon: 'camera', label: '照片与视频', types: ['photo'], vis: '全员可见' },
  { icon: 'pencil', label: 'AI 日记草稿', diary: true, vis: '仅自己可见' }
]

/* ---------- PDF 导出章节（export · P24 · FR-31） ---------- */
export const EXPORT_SECS = [
  { t: '封面页', d: '宝宝昵称 · 头像 · 月龄区间', on: true },
  { t: '里程碑相册', d: '5 大领域达成时间线', on: true },
  { t: '生长曲线', d: '身高 / 体重 / 头围 WHO 百分位图', on: true },
  { t: '照片精选', d: '自动挑选 24 张（每月至多 6 张）', on: true },
  { t: '健康记录页', d: '喂养 / 睡眠 / 测量摘要 · 默认不含', on: false },
  { t: '免责声明页', d: '数据来源与「不构成医学建议」声明', on: true }
]

/* ---------- 纪念卡类型（card · P32 · FR-43）
   标题中的宝宝名不写死：页面用当前宝宝真实昵称 + tag 拼「名字 · 100 天」；
   里程碑纪念卡的 tag/sub 不固定，由页面按所选里程碑动态派生 ---------- */
export const CARD_TYPES = [
  { name: '百日纪念卡', tag: '100 天', sub: '出生第 100 天 · 愿你慢慢长大' },
  { name: '周岁纪念卡', tag: '1 岁', sub: '人生第一年 · 感谢每一天的陪伴' },
  { name: '里程碑纪念卡', tag: '里程碑', sub: '每一个第一次 · 都值得被记住' }
]

/* ---------- 成长视频（video · P33 · FR-44） ---------- */
export const VIDEO_RANGES = ['近 30 天', '近 90 天', '出生至今']
export const VIDEO_MUSIC = [
  { n: '暖阳', d: '0:45 · 尤克里里' },
  { n: '摇篮曲', d: '1:02 · 钢琴' },
  { n: '微风', d: '0:58 · 木吉他' }
]

/* ---------- 提醒设置默认（remind · P23，持久化见 api.getRemind） ---------- */
export const REMIND_DEFAULT = { vaccine: true, checkup: true, anniversary: true, quiet: false, msg: true, time: '09:00' }
