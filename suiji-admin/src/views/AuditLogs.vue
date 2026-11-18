<template>
  <div class="page">
    <div class="page-toolbar">
      <el-input v-model="actor" placeholder="操作人 / 关键词" clearable style="width: 180px" @keyup.enter="search" />
      <el-input v-model="action" placeholder="动作（如 admin_media_view）" clearable style="width: 200px" @keyup.enter="search" />
      <el-select v-model="family" placeholder="全部家庭" clearable style="width: 180px">
        <el-option v-for="f in families" :key="f.id" :label="f.name" :value="f.id" />
      </el-select>
      <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
                      start-placeholder="开始" end-placeholder="结束" style="width: 240px" />
      <el-button type="primary" @click="search">查询</el-button>
      <span class="muted">共 {{ total }} 条</span>
    </div>

    <el-table :data="items" v-loading="loading" border stripe>
      <el-table-column label="时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作人" min-width="120">
        <template #default="{ row }">{{ row.actor_name || row.actor_id || '系统' }}</template>
      </el-table-column>
      <el-table-column prop="action" label="动作" min-width="130" />
      <el-table-column prop="text" label="内容" min-width="240" show-overflow-tooltip />
      <el-table-column prop="family_name" label="家庭" min-width="130" />
      <el-table-column label="目标" min-width="130">
        <template #default="{ row }">
          <span class="muted">{{ row.target_type ? row.target_type + ' · ' + row.target_id : '-' }}</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination v-model:current-page="page" :page-size="size" :total="total"
                     layout="prev, pager, next, total" @current-change="load" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as http from '../api/http'
import { fmtTime } from '../utils/format'

const actor = ref('')
const action = ref('')
const family = ref('')
const range = ref(null)
const items = ref([])
const families = ref([])
const total = ref(0)
const page = ref(1)
const size = 20
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const q = new URLSearchParams({ page: page.value, size })
    if (actor.value) q.set('actor', actor.value)
    if (action.value) q.set('action', action.value)
    if (family.value) q.set('family', family.value)
    if (range.value && range.value.length === 2) {
      q.set('start', range.value[0])
      q.set('end', range.value[1])
    }
    const d = await http.get('/admin/audit?' + q.toString())
    items.value = d.items || []
    total.value = d.total || 0
  } finally {
    loading.value = false
  }
}

function search() { page.value = 1; load() }

onMounted(async () => {
  try {
    const d = await http.get('/admin/families?page=1&size=100')
    families.value = d.items || []
  } catch (e) { /* ignore */ }
  load()
})
</script>
