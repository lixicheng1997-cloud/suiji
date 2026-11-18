<template>
  <div class="page">
    <div class="page-toolbar">
      <el-input v-model="kw" placeholder="搜索家庭名 / ID" clearable style="width: 260px"
                @keyup.enter="search" @clear="search" />
      <el-button type="primary" @click="search">搜索</el-button>
      <span class="muted">共 {{ total }} 个家庭</span>
    </div>

    <el-table :data="items" v-loading="loading" border stripe>
      <el-table-column prop="name" label="家庭名称" min-width="160" />
      <el-table-column prop="id" label="ID" min-width="120" />
      <el-table-column label="创建者" min-width="120">
        <template #default="{ row }">{{ row.creator_name || row.creator_id || '-' }}</template>
      </el-table-column>
      <el-table-column prop="member_count" label="成员" width="80" />
      <el-table-column prop="baby_count" label="宝宝" width="80" />
      <el-table-column prop="entry_count" label="记录" width="80" />
      <el-table-column label="创建时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openMembers(row)">成员</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination v-model:current-page="page" :page-size="size" :total="total"
                     layout="prev, pager, next, total" @current-change="load" />
    </div>

    <el-dialog v-model="membersVisible" :title="'成员 · ' + membersFamily" width="640px">
      <el-table :data="members" v-loading="membersLoading" size="small" border>
        <el-table-column prop="username" label="账号" min-width="110" />
        <el-table-column prop="name" label="昵称" min-width="100" />
        <el-table-column label="角色" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_creator" size="small">创建者</el-tag>
            <span v-else>成员</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.status === 1" type="warning" size="small">停用</el-tag>
            <span v-else>正常</span>
          </template>
        </el-table-column>
        <el-table-column label="加入时间" width="140">
          <template #default="{ row }">{{ fmtTime(row.joined_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button size="small" type="danger" plain
                       :disabled="row.is_creator || !!row.is_admin" @click="unbind(row)">解绑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="muted" style="margin-top:10px">创建者与管理员账号不可解绑；解绑不删除历史数据。</div>
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

const membersVisible = ref(false)
const membersLoading = ref(false)
const membersFamily = ref('')
const membersFid = ref('')
const members = ref([])

async function load() {
  loading.value = true
  try {
    const q = new URLSearchParams({ kw: kw.value || '', page: page.value, size })
    const d = await http.get('/admin/families?' + q.toString())
    items.value = d.items || []
    total.value = d.total || 0
  } finally {
    loading.value = false
  }
}

function search() { page.value = 1; load() }

async function openMembers(row) {
  membersVisible.value = true
  membersLoading.value = true
  membersFamily.value = row.name
  membersFid.value = row.id
  members.value = []
  try {
    const d = await http.get('/admin/families/' + row.id + '/members')
    members.value = d.items || []
  } catch (e) {
    ElMessage.error(e.friendly || '加载成员失败')
  } finally {
    membersLoading.value = false
  }
}

async function unbind(row) {
  try {
    await ElMessageBox.confirm(
      '解绑后「' + (row.name || row.username) + '」将退出家庭「' + membersFamily.value +
      '」，App 端会被引导重新加入家庭；历史数据留在原家庭，重新加入后仍可见。确定解绑吗？',
      '强制解绑',
      { confirmButtonText: '确定解绑', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (e) { return }
  try {
    await http.post(`/admin/families/${membersFid.value}/members/${row.user_id}/unbind`)
    ElMessage.success('已解绑')
    openMembers({ id: membersFid.value, name: membersFamily.value })
    load()
  } catch (e) {
    ElMessage.error(e.friendly || '解绑失败')
  }
}

onMounted(load)
</script>
