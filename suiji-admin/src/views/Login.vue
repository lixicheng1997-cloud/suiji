<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="login-mascot"><img :src="bearFace" alt="岁记" /></div>
      <div class="login-brand">岁记 · 管理台</div>
      <div class="login-sub">宝宝成长记录运营与合规管理</div>
      <el-form @submit.prevent="submit">
        <el-form-item>
          <el-input v-model="form.username" placeholder="管理员账号" size="large" clearable />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large"
                    show-password @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="submit">
          登 录
        </el-button>
        <div v-if="errMsg" class="login-err">{{ errMsg }}</div>
      </el-form>
      <div class="login-tip">登录与接口调用全程加密传输</div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSession } from '../stores/session'
import bearFace from '../assets/icons/bear-face.png'

const router = useRouter()
const session = useSession()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const errMsg = ref('')

async function submit() {
  errMsg.value = ''
  if (!form.username || !form.password) {
    errMsg.value = '请输入账号和密码'
    return
  }
  loading.value = true
  try {
    await session.login(form.username, form.password)
    router.push('/dashboard')
  } catch (e) {
    errMsg.value = e.friendly || e.message || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 奶油底 + 两团蜂蜜暖晕 */
.login-wrap {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(520px 320px at 12% 18%, rgba(255, 184, 107, .22), transparent 70%),
    radial-gradient(560px 360px at 88% 82%, rgba(245, 179, 44, .16), transparent 70%),
    var(--sj-cream);
}
.login-card {
  width: 390px;
  background: var(--sj-card);
  border: 1px solid var(--sj-line);
  border-radius: var(--sj-radius-lg);
  padding: 36px 34px 24px;
  box-shadow: var(--sj-shadow-lg);
  text-align: center;
}
/* 可爱标识：蜂蜜浅底圆徽 + bear 主题熊头 */
.login-mascot {
  width: 72px;
  height: 72px;
  margin: 0 auto 12px;
  border-radius: 50%;
  background: var(--sj-honey-soft);
  border: 2px solid var(--sj-honey-light);
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-mascot img { width: 56px; height: 56px; }
.login-brand {
  font-size: 24px;
  font-weight: 700;
  font-family: var(--sj-font-title);
  color: var(--sj-honey-deep);
}
.login-sub { color: var(--sj-ink-2); font-size: 13px; margin: 8px 0 26px; }
.login-btn { width: 100%; margin-top: 4px; letter-spacing: 6px; }
.login-err { color: var(--sj-coral); font-size: 13px; margin-top: 12px; text-align: center; }
.login-tip { color: var(--sj-ink-3); font-size: 12px; text-align: center; margin-top: 18px; }
</style>
