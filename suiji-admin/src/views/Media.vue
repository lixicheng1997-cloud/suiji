<template>
  <div class="page">
    <div class="page-toolbar">
      <el-select v-model="family" placeholder="全部家庭" clearable style="width: 200px" @change="search">
        <el-option v-for="f in families" :key="f.id" :label="f.name" :value="f.id" />
      </el-select>
      <el-select v-model="mtype" placeholder="全部类型" clearable style="width: 130px" @change="search">
        <el-option label="图片" value="image" />
        <el-option label="视频" value="video" />
        <el-option label="音频" value="audio" />
        <el-option label="其他" value="other" />
      </el-select>
      <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
                      start-placeholder="开始日期" end-placeholder="结束日期" style="width: 260px" @change="search" />
      <el-button type="primary" @click="search">查询</el-button>
      <span class="muted">共 {{ total }} 个文件 · 查看原图/完整视频会记入审计日志</span>
    </div>

    <div v-loading="loading" class="media-grid">
      <div v-for="m in items" :key="m.id" class="media-cell" @click="openPreview(m)">
        <div class="media-thumb">
          <el-image v-if="kind(m) === 'image'" :src="http.mediaUrl(m.thumb_url)" fit="cover" lazy class="thumb-img">
            <template #error><div class="thumb-fail">图片加载失败</div></template>
          </el-image>
          <el-image v-else-if="kind(m) === 'video' && hasCover(m)" :src="coverUrl(m)" fit="cover" lazy class="thumb-img">
            <template #error><div class="thumb-video"><img class="thumb-ico" :src="icoVideo" alt="" /></div></template>
          </el-image>
          <div v-else-if="kind(m) === 'video'" class="thumb-video">
            <img class="thumb-ico" :src="icoVideo" alt="" />
          </div>
          <div v-else-if="kind(m) === 'audio'" class="thumb-video">
            <img class="thumb-ico" :src="icoVoice" alt="" />
          </div>
          <div v-else class="thumb-video">
            <el-icon :size="26"><Document /></el-icon>
          </div>
          <span class="media-size">{{ fmtBytes(m.size) }}</span>
        </div>
        <div class="media-meta">
          <div class="media-name" :title="m.original_name">{{ m.original_name || m.id }}</div>
          <div class="muted">{{ m.family_name || '未知家庭' }} · {{ m.uploader_name || '未知上传者' }}</div>
          <div class="muted">{{ fmtTime(m.created_at) }}<span v-if="m.entry_id"> · 关联记录</span></div>
        </div>
      </div>
      <el-empty v-if="!loading && !items.length" description="没有符合条件的文件" />
    </div>

    <div class="pager">
      <el-pagination v-model:current-page="page" :page-size="size" :total="total"
                     layout="prev, pager, next, total" @current-change="load" />
    </div>

    <el-dialog v-model="previewVisible" width="760px" top="6vh" :title="previewTitle" destroy-on-close>
      <div class="preview-body">
        <img v-if="previewKind === 'image'" :src="previewUrl" class="preview-img" alt="" />
        <video v-else-if="previewKind === 'video'" :src="previewUrl" :poster="previewPoster" controls class="preview-video" />
        <template v-else-if="previewKind === 'audio'">
          <div class="preview-audio-wrap">
            <audio :src="previewUrl" controls class="preview-audio" />
            <div class="audio-hint muted">
              语音为 AAC 录音，部分桌面浏览器不支持直接播放；无法播放时可
              <el-link type="primary" :href="previewUrl" download target="_blank">下载后用本地播放器打开</el-link>
            </div>
          </div>
        </template>
        <div v-else>
          <el-link type="primary" :href="previewUrl" target="_blank">在新窗口打开文件</el-link>
        </div>
      </div>
      <div v-if="previewMeta" class="preview-meta muted">{{ previewMeta }}</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Document } from '@element-plus/icons-vue'
import * as http from '../api/http'
import { fmtBytes, fmtTime } from '../utils/format'
import icoVideo from '../assets/icons/33-fn-video.png'
import icoVoice from '../assets/icons/09-voice.png'

const family = ref('')
const mtype = ref('')
const range = ref(null)
const page = ref(1)
const size = 24
const total = ref(0)
const items = ref([])
const families = ref([])
const loading = ref(false)

const previewVisible = ref(false)
const previewUrl = ref('')
const previewKind = ref('')
const previewTitle = ref('')
const previewMeta = ref('')
const previewPoster = ref('')

/* 视频封面：上传时后台抽帧生成的 JPEG（meta.cover_key），经 content 通道 variant=cover 取 */
function hasCover(m) {
  return !!(m.meta && m.meta.cover_key)
}
function coverUrl(m) {
  return http.mediaUrl(m.content_url + '&variant=cover')
}

function kind(m) {
  const ct = (m.content_type || '').toLowerCase()
  if (ct.startsWith('image/')) return 'image'
  if (ct.startsWith('video/')) return 'video'
  if (ct.startsWith('audio/')) return 'audio'
  return 'other'
}

async function load() {
  loading.value = true
  try {
    const q = new URLSearchParams({ page: page.value, size })
    if (family.value) q.set('family', family.value)
    if (mtype.value) q.set('type', mtype.value)
    if (range.value && range.value.length === 2) {
      q.set('start', range.value[0])
      q.set('end', range.value[1])
    }
    const d = await http.get('/admin/media?' + q.toString())
    items.value = d.items || []
    total.value = d.total || 0
  } finally {
    loading.value = false
  }
}

function search() { page.value = 1; load() }

function openPreview(m) {
  previewKind.value = kind(m)
  previewTitle.value = m.original_name || m.id
  previewUrl.value = http.mediaUrl(m.content_url)
  previewPoster.value = previewKind.value === 'video' && hasCover(m) ? coverUrl(m) : ''
  previewMeta.value = `家庭：${m.family_name || '-'} · 上传者：${m.uploader_name || '-'} · 时间：${fmtTime(m.created_at)} · 大小：${fmtBytes(m.size)}`
  previewVisible.value = true
}

async function loadFamilies() {
  try {
    const d = await http.get('/admin/families?page=1&size=100')
    families.value = d.items || []
  } catch (e) { /* 下拉拉不到不阻塞列表 */ }
}

onMounted(() => { loadFamilies(); load() })
</script>

<style scoped>
.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 14px;
  min-height: 120px;
}
.media-cell {
  background: var(--sj-card);
  border-radius: var(--sj-radius-md);
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--sj-line);
  transition: transform .25s var(--sj-ease-pop), box-shadow .25s var(--sj-ease-pop);
}
.media-cell:hover { transform: translateY(-3px); box-shadow: var(--sj-shadow-md); }
.media-thumb {
  position: relative;
  height: 140px;
  background: var(--sj-honey-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}
.thumb-img { width: 100%; height: 100%; }
.thumb-video { font-size: 26px; color: var(--sj-honey-deep); }
.thumb-ico { width: 30px; height: 30px; }
.thumb-fail { color: var(--sj-ink-3); font-size: 12px; }
.media-size {
  position: absolute;
  right: 6px;
  bottom: 6px;
  background: rgba(91, 70, 54, .55);
  color: #fff;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
}
.media-meta { padding: 8px 10px 10px; }
.media-name {
  font-size: 13px;
  color: var(--sj-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 3px;
}
.preview-body { display: flex; justify-content: center; align-items: center; min-height: 200px; }
.preview-img { max-width: 100%; max-height: 62vh; }
.preview-video { max-width: 100%; max-height: 62vh; }
.preview-audio-wrap { width: 100%; }
.preview-audio { width: 100%; }
.audio-hint { margin-top: 10px; font-size: 12px; text-align: center; }
.preview-meta { margin-top: 10px; text-align: center; }
</style>
