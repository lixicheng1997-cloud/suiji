<template>
  <div class="page" v-loading="loading">
    <el-row :gutter="14">
      <el-col v-for="c in cards" :key="c.label" :xs="12" :sm="8" :md="6" :lg="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label"><span class="stat-emoji"><img :src="c.icon" alt="" /></span>{{ c.label }}</div>
          <div class="stat-value">{{ c.value }}</div>
          <div v-if="c.sub" class="muted">{{ c.sub }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="trend-card">
      <template #header>
        <div class="trend-head">
          <span>新增趋势（用户 / 记录）</span>
          <el-radio-group v-model="days" size="small" @change="loadTrend">
            <el-radio-button :value="7">近 7 天</el-radio-button>
            <el-radio-button :value="30">近 30 天</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <svg v-if="trend.length" :viewBox="`0 0 ${W} ${H}`" class="trend-svg" preserveAspectRatio="none">
        <line v-for="(g, i) in gridY" :key="'g' + i" :x1="PAD" :x2="W - PAD" :y1="g" :y2="g" stroke="#F3E4D3" stroke-width="1" />
        <polyline :points="userLine" fill="none" stroke="#F7A15C" stroke-width="2" />
        <polyline :points="entryLine" fill="none" stroke="#6FBDE0" stroke-width="2" />
        <circle v-for="(p, i) in userDots" :key="'u' + i" :cx="p[0]" :cy="p[1]" r="2.5" fill="#F7A15C" />
        <circle v-for="(p, i) in entryDots" :key="'e' + i" :cx="p[0]" :cy="p[1]" r="2.5" fill="#6FBDE0" />
        <text v-for="(t, i) in xLabels" :key="'t' + i" :x="t[0]" :y="H - 6" font-size="10" fill="#9C8878" text-anchor="middle">{{ t[1] }}</text>
      </svg>
      <div class="trend-legend">
        <span><i style="background:#F7A15C"></i>新增用户</span>
        <span><i style="background:#6FBDE0"></i>新增记录</span>
        <span class="muted">{{ note }}</span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import * as http from '../api/http'
import icoUser from '../assets/icons/13-tab-me.png'
import icoFamily from '../assets/icons/12-tab-family.png'
import icoBaby from '../assets/icons/29-fn-babies.png'
import icoPhoto from '../assets/icons/04-photo.png'
import icoBackup from '../assets/icons/22-fn-backup.png'
import icoDiary from '../assets/icons/20-fn-diary.png'

const loading = ref(false)
const days = ref(7)
const trend = ref([])
const note = ref('')
const stats = ref({})

const W = 640, H = 220, PAD = 24

const cards = computed(() => {
  const s = stats.value
  return [
    { icon: icoUser, label: '用户', value: fmt(s.users), sub: `今日新增 ${fmt(s.users_today)}` },
    { icon: icoFamily, label: '家庭', value: fmt(s.families) },
    { icon: icoBaby, label: '宝宝', value: fmt(s.babies) },
    { icon: icoPhoto, label: '记录', value: fmt(s.entries), sub: `今日新增 ${fmt(s.entries_today)}` },
    { icon: icoBackup, label: '存储用量', value: humanBytes(s.storage_bytes), sub: `${fmt(s.files)} 个文件` },
    { icon: icoDiary, label: 'AI 周记生成', value: fmt(s.llm_journals) }
  ]
})

function fmt(n) { return (n === undefined || n === null) ? '-' : Number(n).toLocaleString() }
function humanBytes(b) {
  b = Number(b || 0)
  if (b < 1024) return b + ' B'
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB'
  if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MB'
  return (b / 1073741824).toFixed(2) + ' GB'
}

const maxV = computed(() => {
  let m = 1
  for (const t of trend.value) m = Math.max(m, t.users || 0, t.entries || 0)
  return m
})
function pts(key) {
  const n = trend.value.length
  if (!n) return []
  const step = n > 1 ? (W - PAD * 2) / (n - 1) : 0
  return trend.value.map((t, i) => [
    PAD + i * step,
    H - PAD - ((t[key] || 0) / maxV.value) * (H - PAD * 2)
  ])
}
function toStr(p) { return p.map(q => q[0].toFixed(1) + ',' + q[1].toFixed(1)).join(' ') }
const userDots = computed(() => pts('users'))
const entryDots = computed(() => pts('entries'))
const userLine = computed(() => toStr(userDots.value))
const entryLine = computed(() => toStr(entryDots.value))
const gridY = computed(() => [0.25, 0.5, 0.75].map(r => PAD + r * (H - PAD * 2)))
const xLabels = computed(() => {
  const n = trend.value.length
  if (!n) return []
  const step = n > 1 ? (W - PAD * 2) / (n - 1) : 0
  const out = []
  const show = Math.max(1, Math.floor(n / 6))
  trend.value.forEach((t, i) => {
    if (i % show === 0 || i === n - 1) out.push([PAD + i * step, t.date.slice(5)])
  })
  return out
})

async function loadTrend() {
  const d = await http.get('/admin/stats/trend?days=' + days.value)
  trend.value = d.items || []
  note.value = d.note || ''
}

async function load() {
  loading.value = true
  try {
    const d = await http.get('/admin/stats/overview')
    stats.value = d
    note.value = d.note || ''
    await loadTrend()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.stat-card {
  margin-bottom: 14px;
  transition: transform .25s var(--sj-ease-pop), box-shadow .25s var(--sj-ease-pop);
}
/* hover 轻微上浮 */
.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--sj-shadow-md) !important;
}
.stat-label { color: var(--sj-ink-2); font-size: 13px; display: flex; align-items: center; gap: 6px; }
.stat-emoji {
  width: 34px; height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--sj-honey-soft);
  border-radius: 10px;
}
.stat-emoji img { width: 26px; height: 26px; }
.stat-value { font-size: 26px; font-weight: 700; font-family: var(--sj-font-title); color: var(--sj-ink); margin: 8px 0 2px; }
.trend-card { margin-top: 4px; }
.trend-head { display: flex; align-items: center; justify-content: space-between; font-family: var(--sj-font-title); }
.trend-svg { width: 100%; height: 220px; }
.trend-legend { display: flex; gap: 18px; align-items: center; margin-top: 8px; font-size: 12px; color: var(--sj-ink); }
.trend-legend i { display: inline-block; width: 10px; height: 10px; border-radius: 999px; margin-right: 5px; }
</style>
