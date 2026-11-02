<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 渐变头图（v2 主色族渐变 + 圆角收尾；与登录页同构的品牌开场） -->
    <view class="fs-hero" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 56rpx)' }">
      <view class="fs-mark">
        <sj-icon name="12-tab-family" :size="72" />
      </view>
      <text class="fs-title">还没有属于你的家庭</text>
      <text class="fs-sub">创建一个新家庭，或输入家人分享的邀请码加入</text>
    </view>

    <!-- 创建 / 加入卡片（v2 set-group 同款白卡 + sj-subsection 分段器） -->
    <view class="fs-card">
      <sj-subsection
        class="fs-seg"
        :modelValue="mode === 'create' ? 0 : 1"
        :options="['创建家庭', '邀请码加入']"
        @change="onMode"
      />

      <view v-if="mode === 'create'" class="fs-field">
        <text class="fs-label">家庭名称<text class="fs-opt">（可选）</text></text>
        <sj-input v-model="familyName" variant="box" placeholder="如：小岁的家" :maxlength="20" />
        <text class="fs-hint">留空则默认为「你的昵称 + 的家庭」</text>
      </view>
      <view v-else class="fs-field">
        <text class="fs-label">邀请码</text>
        <sj-input
          class="fs-code"
          :modelValue="code"
          variant="box"
          placeholder="8 位邀请码"
          :maxlength="8"
          @update:modelValue="onCode"
        />
        <text class="fs-hint">邀请码由家庭创建者在「家庭 → 邀请家人」中生成，7 天内有效</text>
      </view>

      <!-- 主按钮（sj-button 通栏大号，busy 由库拦截重复点击） -->
      <sj-button
        class="fs-btn"
        block
        size="lg"
        :loading="busy"
        :text="busy ? '处理中…' : (mode === 'create' ? '创建并进入' : '加入并进入')"
        @click="submit"
      />
    </view>

    <view class="fs-logout" hover-class="hover-press" :hover-stay-time="80" @click="logout">
      <text>换个账号登录</text>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import * as guide from '@/utils/first-run.js'
import { play } from '@/utils/sound.js'

/* 登录后家庭门控页（强制流程）：账号没有关联家庭时只能做两件事——
 * ① 输入家庭名称创建 ② 输入家庭邀请码加入；完成前前端禁止进入任何业务页面、
 * 后端对业务接口一律 409 need_family。成功后重新走 goAfterLogin（宝宝 → 同意 → 首页）。 */
export default {
  data() {
    return {
      mode: 'create',
      familyName: '',
      code: '',
      busy: false,
      statusBarHeight: 20
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  /* 已关联家庭就无需停留：继续后续门控（宝宝 → 隐私同意 → 首页） */
  onShow() {
    if (api.hasFamily()) guide.goAfterLogin()
  },

  /* 强制流程：创建/加入完成前不允许返回业务页面（物理返回键 / 端侧返回手势） */
  onBackPress() {
    this.$refs.ntf.show({ type: 'warn', message: '请先创建家庭，或用邀请码加入家庭' })
    return true
  },

  methods: {
    /* 分段器下标 → 模式字符串 */
    onMode(index) {
      this.mode = index === 0 ? 'create' : 'join'
    },
    /* 邀请码统一大写（库回传字符串，钳到 8 位） */
    onCode(val) {
      this.code = String(val || '').toUpperCase()
    },
    submit() {
      if (this.busy) return
      if (this.mode === 'join' && this.code.trim().length < 8) {
        this.$refs.ntf.show({ type: 'warn', message: '请输入完整的 8 位邀请码' })
        return
      }
      this.busy = true
      const req = this.mode === 'create'
        ? api.createFamily(this.familyName)
        : api.joinFamily(this.code)
      req
        .then(() => {
          this.busy = false
          /* 凭码加入家庭成功（创建家庭不算）：播 E10 */
          if (this.mode === 'join') play('E10')
          this.$refs.ntf.show({ type: 'ok', message: this.mode === 'create' ? '家庭创建成功' : '已加入家庭' })
          setTimeout(() => guide.goAfterLogin(), 600)
        })
        .catch(e => {
          this.busy = false
          ui.error(e, '操作失败，请重试')
        })
    },

    logout() {
      api.logout()
    }
  }
}
</script>

<style lang="scss" scoped>
/* 页面底：v2 奶油色（themeVars 由全局混入注入到根节点） */
.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;
  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
  font-family: var(--sj-font-body);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-bottom: 64rpx;
  box-sizing: border-box;
}

/* ---------- 渐变头图（v2 主色族三段渐变 + 底部大圆角） ---------- */
.fs-hero {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-bottom: 64rpx;
  background: linear-gradient(160deg, var(--sj-primary) 0%, var(--sj-blush) 55%, var(--sj-accent) 100%);
  border-radius: 0 0 56rpx 56rpx;
  box-shadow: var(--sj-sh-md);
}
/* 品牌标记（白底圆角盒 + v2 家庭图标） */
.fs-mark {
  width: 132rpx;
  height: 132rpx;
  border-radius: 44rpx;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: inset 0 0 0 6rpx rgba(255, 255, 255, 0.5), var(--sj-sh-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 28rpx;
}
.fs-title {
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: #fff;
  letter-spacing: 4rpx;
}
.fs-sub { font-size: 24rpx; color: rgba(255, 255, 255, 0.9); margin-top: 14rpx; letter-spacing: 2rpx; }

/* ---------- 创建 / 加入卡片（v2 毛玻璃卡；卡内 sj-input box 由 App.vue 统一改成透明玻璃槽） ---------- */
.fs-card {
  width: calc(100% - 64rpx);
  margin-top: -32rpx;
  background: var(--sj-glass);
  border: 2rpx solid var(--sj-glass-line);
  border-radius: var(--sj-r-lg);
  box-shadow: var(--sj-glass-hi), var(--sj-sh-md);
  padding: 36rpx 40rpx 44rpx;
  box-sizing: border-box;
}

/* 分段器（v2 pg-seg：白底胶囊容器，选中 primary 底白字） */
/* 分段切换（sj-subsection） */
.fs-seg {
  display: block;
  margin-bottom: 32rpx;
}

/* 字段区：label 灰粗 / 输入框外观由 sj-input variant=box 自带 */
.fs-field { margin-bottom: 28rpx; }
.fs-label { display: block; font-size: 24rpx; font-weight: 700; color: var(--sj-sub); margin-bottom: 12rpx; }
.fs-opt { font-size: 22rpx; color: var(--sj-faint); font-weight: 400; }
/* 邀请码：字距加宽（letter-spacing 继承到内部输入节点） */
.fs-code { letter-spacing: 8rpx; }
.fs-hint { display: block; font-size: 22rpx; color: var(--sj-faint); margin-top: 12rpx; line-height: 1.5; }

/* 主按钮（sj-button lg block） */
.fs-btn {
  display: flex;
  margin-top: 12rpx;
}

/* 换账号登录（次级文字链） */
.fs-logout { margin-top: 40rpx; padding: 12rpx 32rpx; }
.fs-logout text { font-size: 24rpx; color: var(--sj-sub); }
</style>
