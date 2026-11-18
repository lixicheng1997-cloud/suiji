<template>
  <div class="page">
    <div class="page-toolbar">
      <el-input v-model="kw" placeholder="搜索账号 / 昵称 / ID" clearable style="width: 260px"
                @keyup.enter="search" @clear="search" />
      <el-button type="primary" @click="search">搜索</el-button>
      <span class="muted">共 {{ total }} 个账号</span>
    </div>

    <el-table :data="items" v-loading="loading" border stripe>
      <el-table-column prop="username" label="账号" min-width="130" />
      <el-table-column prop="name" label="昵称" min-width="110" />
      <el-table-column label="身份" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.is_admin" type="danger" size="small">管理员</el-tag>
          <span v-else class="muted">普通用户</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.status === 1" type="warning" size="small">已停用</el-tag>
          <el-tag v-else type="success" size="small">正常</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="家庭" min-width="150">
        <template #default="{ row }">
          <span v-if="row.family_name">{{ row.family_name }}</span>
          <span v-else class="muted">未关联</span>
          <el-tag v-if="row.role" size="small" class="role-tag">{{ row.role === 'creator' ? '创建者' : '成员' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">详情</el-button>
          <el-button size="small" :type="row.status === 1 ? 'success' : 'warning'"
                     :disabled="!!row.is_admin" @click="toggleStatus(row)">
            {{ row.status === 1 ? '启用' : '停用' }}
          </el-button>
          <el-button size="small" :disabled="!!row.is_admin" @click="resetPwd(row)">重置密码</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination v-model:current-page="page" :page-size="size" :total="total"
                     layout="prev, pager, next, total" @current-change="load" />
    </div>

    <el-dialog v-model="detailVisible" title="用户详情" width="560px">
      <div v-loading="detailLoading">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="账号">{{ detail.username }}</el-descriptions-item>
          <el-descriptions-item label="昵称">{{ detail.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="ID" :span="2">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.status === 1 ? '已停用' : '正常' }}</el-descriptions-item>
          <el-descriptions-item label="注册时间">{{ fmtTime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="宝宝数">{{ detail.babies }}</el-descriptions-item>
          <el-descriptions-item label="记录数">{{ detail.entries }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.deletion_scheduled_at" label="注销计划" :span="2">
            {{ fmtTime(detail.deletion_scheduled_at) }}（冷静期内登录可撤销）
          </el-descriptions-item>
        </el-descriptions>
        <div class="detail-sub">所属家庭</div>
        <el-table :data="detail.memberships || []" size="small" border>
          <el-table-column prop="family_name" label="家庭" min-width="140" />
          <el-table-column prop="role" label="角色" width="90">
            <template #default="{ row }">{{ row.role === 'creator' ? '创建者' : '成员' }}</template>
          </el-table-column>
          <el-table-column label="加入时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.joined_at) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as http from '../api/http'
import { fmtTime } from '../utils/format'

const kw = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const size = 20
const loading = ref(false)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref({})

async function load() {
  loading.value = true
  try {
    const q = new URLSearchParams({ kw: kw.value || '', page: page.value, size })
    const d = await http.get('/admin/users?' + q.toString())
    items.value = d.items || []
    total.value = d.total || 0
  } finally {
    loading.value = false
  }
}

function search() { page.value = 1; load() }

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = {}
  try {
    detail.value = await http.get('/admin/users/' + row.id)
  } catch (e) {
    ElMessage.error(e.friendly || '加载详情失败')
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

async function toggleStatus(row) {
  const disabling = row.status !== 1
  try {
    await ElMessageBox.confirm(
      disabling
        ? '停用后该账号会被踢掉全部设备，无法登录 App，直到重新启用。历史数据保留不动。确定停用「' + (row.name || row.username) + '」吗？'
        : '重新启用后，该账号可以正常登录使用。确定启用吗？',
      disabling ? '停用账号' : '启用账号',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (e) { return }
  try {
    await http.post('/admin/users/' + row.id + '/status', { status: disabling ? 1 : 0 })
    ElMessage.success(disabling ? '已停用，该账号全部设备已下线' : '已启用')
    load()
  } catch (e) {
    ElMessage.error(e.friendly || '操作失败')
  }
}

async function resetPwd(row) {
  try {
    await ElMessageBox.confirm(
      '将生成一次性临时密码并踢掉该账号全部设备（旧登录态立即失效）。临时密码只显示这一次，请复制后转告本人。确定重置「' + (row.name || row.username) + '」的密码吗？',
      '重置密码',
      { confirmButtonText: '确定重置', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (e) { return }
  try {
    const d = await http.post('/admin/users/' + row.id + '/reset-password')
    await ElMessageBox.alert(
      '临时密码：' + d.temp_password + '（只显示一次，用户下次登录后应自行修改）',
      '密码已重置',
      { confirmButtonText: '我已记录', type: 'success' }
    )
  } catch (e) {
    ElMessage.error(e.friendly || '重置失败')
  }
}

onMounted(load)
</script>

<style scoped>
.role-tag { margin-left: 6px; }
.detail-sub { margin: 14px 0 8px; font-weight: 600; font-family: var(--sj-font-title); color: var(--sj-ink); font-size: 13px; }
</style>
