<template>
  <view class="page" :class="swipeClass" :style="themeVars" @touchstart="onTabTouchStart" @touchend="onTabTouchEnd">
    <sj-bg />
    <!-- 家庭标识行（v2 appbar-plain 的 fam-tag） -->
    <view class="fam-head">
      <text class="fh-title">{{ baby.name }}的小家</text>
      <text class="fam-tag">{{ members.length }} 人 · 共同记录 {{ sharedCount }} 条</text>
    </view>

    <!-- 成员宫格（4 列卡片 + 邀请卡）；超过一行改为堆叠头像（v2 .cu-avgrp） -->
    <view class="member-grid" v-if="!membersStacked">
      <view class="member-card" v-for="m in members" :key="m.n">
        <view class="mem-avatar" :style="{ background: m.c }">
          <image class="mem-img" v-if="m.av" :src="m.av" mode="aspectFill" />
          <text v-else>{{ m.n[0] }}</text>
        </view>
        <text class="mc-name">{{ m.n }}</text>
        <text class="mc-rel" :class="{ 'mc-rel-none': !m.rel }">{{ m.rel || '未设置' }}</text>
        <text class="role" :class="m.rc">{{ m.tag }}</text>
      </view>
      <view class="member-card member-add" v-if="isCreator" hover-class="hover-press" :hover-stay-time="80" @click="onInvite">
        <view class="add-plus"><text>+</text></view>
        <text class="mc-name">邀请家人</text>
        <text class="role role-invite">邀请码加入</text>
      </view>
    </view>
    <view class="member-stack" v-else>
      <view class="mem-avatar stack-av" v-for="m in members" :key="m.n" :style="{ background: m.c }">
        <image class="mem-img" v-if="m.av" :src="m.av" mode="aspectFill" />
        <text v-else>{{ m.n[0] }}</text>
      </view>
      <view class="mem-avatar stack-av stack-add" v-if="isCreator" hover-class="hover-press" :hover-stay-time="80" @click="onInvite">
        <text>+</text>
      </view>
    </view>

    <!-- 共享相册 -->
    <view class="fam-card" v-if="albumUrls.length">
      <text class="fc-title">共享相册</text>
      <view class="album-grid">
        <image class="album-img" v-for="(u, i) in albumUrls" :key="i" :src="u" mode="aspectFill" lazy-load />
      </view>
    </view>

    <!-- 家人动态卡（合规：不含健康数值） -->
    <view class="fam-card">
      <text class="fc-title">家庭动态</text>
      <view class="feed-item" v-for="(f, i) in feeds" :key="i">
        <view class="f-dot" :style="{ background: f.c }" />
        <view class="f-body"><text class="f-name">{{ f.who }}</text><text>{{ f.what }}</text></view>
        <text class="f-time">{{ f.time }}</text>
      </view>
    </view>

    <!-- 功能入口（v2 fam-entries 双列卡） -->
    <view class="entry-grid">
      <view class="entry-card" hover-class="hover-press" :hover-stay-time="80" @click="goAudit">
        <view class="ec-icon" style="background: #F0EAFB"><sj-icon name="35-fn-audit" :size="72" /></view>
        <text class="ec-title">操作记录</text>
        <text class="ec-sub">改动都能查到</text>
      </view>
      <view class="entry-card" hover-class="hover-press" :hover-stay-time="80" @click="onJoin">
        <view class="ec-icon" style="background: #FFE7EE"><sj-icon name="28-fn-invite" :size="72" /></view>
        <text class="ec-title">凭码加入家庭</text>
        <text class="ec-sub">收到 8 位邀请码？</text>
      </view>
    </view>

    <!-- 邀请说明（保留合规文案） -->
    <view class="invite-note">
      <text>邀请码 7 天有效 · 家人注册账号后凭码加入 · 可随时失效</text>
    </view>

    <!-- v2 悬浮底部导航（自动隐藏原生 tabBar） -->
    <sj-tabbar active="family" />
    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import tabSwipe, { pullRefresh } from '@/utils/tabSwipe.js'
import { play } from '@/utils/sound.js'

/* 角色 → v2 role-* 配色类 */
function roleClass(r, tag) {
  if (r === 'creator') return 'role-owner'
  if (r === 'editor' || (tag || '').indexOf('编辑') >= 0) return 'role-edit'
  if (r === 'viewer' || (tag || '').indexOf('只读') >= 0) return 'role-view'
  return 'role-edit'
}

export default {
  mixins: [tabSwipe],
  /* 下拉刷新（Vue3 生命周期必须顶层声明，混入 methods 里的不会触发）：重拉 bootstrap 后走 tabAfterPull */
  onPullDownRefresh() { pullRefresh(this) },
  data() {
    return {
      baby: { name: '宝宝' },
      members: [],
      sharedCount: 0,
      albumUrls: [],
      /* 家人动态：由真实记录派生，禁止出现健康数值 */
      feeds: [],
      /* 家庭契约状态（API-CONTRACT §4）：只读态用于成员权限描述 */
      familyReadonly: false,
      /* 当前登录账号是否家庭创建者（仅创建者显示「邀请家人」入口） */
      isCreator: false
    }
  },

  computed: {
    /* 成员（含邀请卡位）超过一行 4 列 → 卡片宫格改为单行堆叠头像 */
    membersStacked() {
      return this.members.length + (this.isCreator ? 1 : 0) > 4
    }
  },

  onShow() {
    this.refreshView()
  },

  methods: {
    /* 本页渲染链路（缓存 → data）。
       注意：uni-app Vue3 的页面生命周期 onShow 不挂在实例上，不能 this.onShow() 手动调，
       否则抛 TypeError 被调用方 catch 误报成接口错误（如加入家庭成功却弹「加入失败」）。 */
    refreshView() {
      const baby = api.getBaby()
      this.baby = baby ? { name: baby.name } : { name: '宝宝' }
      const f = api.getFamily()
      this.familyReadonly = api.isFamilyReadonly()
      /* 创建者判定：family.role（契约 §4 creator|member，历史 owner 视为 creator） */
      const role = api.getFamilyRole()
      this.isCreator = role === 'creator' || role === 'owner'
      const ro = this.familyReadonly
      /* member 行字段（name/role/color/avatar/relation[+可选 tag/desc]）→ 模板消费形状（n/r/rc/tag/c/av/rel）；两态角色缺省派生 */
      this.members = f.members.map(m => {
        const r = m.role === 'owner' ? 'creator' : (m.role || 'member')
        const tag = m.tag || (r === 'creator' ? '创建者' : '成员')
        return { n: m.name, r, tag, rel: m.relation || '', c: m.color, rc: roleClass(r, tag), av: m.avatar ? api.fileSrc(m.avatar) : '' }
      })
      this.sharedCount = f.sharedCount
      this.albumUrls = f.album
      this.feeds = f.feeds
    },
    /* 下拉刷新：tabSwipe 已重拉 bootstrap，重跑本页渲染链路 */
    tabAfterPull() { this.refreshView() },
    goAudit() {
      uni.navigateTo({ url: '/pages/audit/audit' })
    },
    onInvite() {
      api.inviteFamily()
        .then(r => {
          const code = (r && r.code) || ''
          const exp = r && r.expires_at ? String(r.expires_at).slice(0, 10) : '7 天'
          return ui.showModal({
            title: '家庭邀请码',
            icon: '28-fn-invite',
            content: '邀请码：' + (code || '-') + '\n有效期至 ' + exp + ' · 家人注册账号后凭码加入',
            confirmText: '一键复制',
            cancelText: '关闭'
          }).then(res => {
            if (!res.confirm || !code) return
            uni.setClipboardData({ data: code })
            this.$refs.ntf.show({ type: 'ok', message: '邀请码已复制' })
          })
        })
        .catch(e => ui.error(e, '生成邀请码失败'))
    },
    onJoin() {
      ui.showModal({
        title: '凭邀请码加入',
        icon: '28-fn-invite',
        editable: true,
        placeholderText: '输入 8 位邀请码'
      })
        .then(res => {
          if (!res.confirm) return null
          const code = (res.content || '').trim()
          if (!code) { this.$refs.ntf.show({ type: 'warn', message: '请输入邀请码' }); return null }
          const cur = api.getFamilyInfo()
          /* 一个用户仅关联一个家庭：加入其他家庭会与当前家庭解绑，先让用户确认 */
          if (!cur || !cur.id) return this.doJoin(code)
          play('S08') // 与当前家庭解绑危险确认弹出音效
          return ui.confirm({
            title: '加入其他家庭',
            content: '加入后将与当前家庭「' + (cur.name || '当前家庭') + '」解绑，该家庭的宝宝与记录将不再可见；你的个人资料不受影响。',
            confirmText: '解绑并加入',
            cancelText: '取消',
            danger: true
          }).then(r2 => (r2.confirm ? this.doJoin(code) : null))
        })
        .catch(e => ui.error(e, '加入失败，请检查邀请码'))
    },

    doJoin(code) {
      return api.joinFamily(code).then(r => {
        this.refreshView()
        /* 家人成功加入家庭空间：播 E10（生成邀请码成功不播） */
        play('E10')
        const left = r && r.left_family
        this.$refs.ntf.show({ type: 'ok', message: left && left.name ? '已加入新家庭 · 已与「' + left.name + '」解绑' : '已加入家庭空间' })
      })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 默认导航栏 Tab 页：左右安全边距 32rpx，底部留安全区 */
.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;
  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
  padding: 24rpx 32rpx 48rpx;
  box-sizing: border-box;
}

/* ---------- 家庭标识行 ---------- */
.fam-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24rpx; }
.fh-title { font-family: var(--sj-font-display); font-size: 44rpx; font-weight: 900; color: var(--sj-ink); }
.fam-tag {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  border-radius: var(--sj-r-pill);
  padding: 8rpx 20rpx;
}

/* ---------- 成员宫格（v2 member-grid） ---------- */
.member-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16rpx; margin-bottom: 28rpx; }
.member-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 24rpx 12rpx;
  box-shadow: var(--sj-sh-sm);
}
.mem-avatar {
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 4rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
  overflow: hidden;
}
.mem-avatar text { font-size: 34rpx; font-weight: 800; color: #fff; }
.mem-img { width: 100%; height: 100%; }
.mc-name { font-size: 25rpx; font-weight: 800; color: var(--sj-ink); }
/* ---------- 成员堆叠头像（超一行时，v2 .cu-avgrp 相邻左叠 -24rpx） ---------- */
.member-stack { display: flex; align-items: center; margin-bottom: 28rpx; }
.stack-av { margin-left: -24rpx; }
.stack-av:first-child { margin-left: 0; }
.stack-add { border-style: dashed; background: var(--sj-cream); }
.stack-add text { font-size: 44rpx; font-weight: 800; color: var(--sj-ok); line-height: 1; }
/* 与宝宝的关系（家长信息页 setting.parent.relation；未设置时置灰占位保持卡片对齐） */
.mc-rel { font-size: 20rpx; font-weight: 700; color: var(--sj-sub); }
.mc-rel-none { color: var(--sj-faint); }
.role { font-size: 19rpx; font-weight: 800; border-radius: var(--sj-r-pill); padding: 4rpx 16rpx; }
.role-owner { background: var(--sj-primary-soft); color: var(--sj-primary-deep); }
.role-edit { background: #E4F3FB; color: #2E7FA8; }
.role-view { background: #F0EAFB; color: #7A5FB0; }
.role-invite { background: #E2F5EA; color: #2E7D4F; }
.member-add {
  justify-content: center;
  border-style: dashed;
  background: var(--sj-cream);
}
.member-add:active { transform: scale(0.95); }
.add-plus {
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  background: #E2F5EA;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4rpx;
}
.add-plus text { font-size: 44rpx; font-weight: 800; color: var(--sj-ok); line-height: 1; }

/* ---------- 通用绘本卡 ---------- */
.fam-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 28rpx 32rpx;
  margin-bottom: 24rpx;
  box-shadow: var(--sj-sh-sm);
}
.fc-title { display: block; font-size: 27rpx; font-weight: 800; color: var(--sj-ink); margin-bottom: 16rpx; }

/* ---------- 共享相册 ---------- */
.album-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16rpx; }
.album-img {
  width: 100%;
  height: 150rpx;
  border-radius: 20rpx;
  border: 4rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
  box-sizing: border-box;
  background: var(--sj-cream);
}

/* ---------- 家庭动态（v2 feed-item） ---------- */
.feed-item {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 16rpx 0;
  border-top: 2rpx dashed var(--sj-line);
  font-size: 24rpx;
  color: var(--sj-sub);
}
.feed-item:first-of-type { border-top: none; }
.f-dot { width: 16rpx; height: 16rpx; border-radius: 50%; flex: none; }
.f-body { flex: 1; min-width: 0; }
.f-name { color: var(--sj-ink); font-weight: 700; margin-right: 8rpx; }
.f-time { font-size: 21rpx; color: var(--sj-faint); flex: none; }

/* ---------- 功能入口双列卡（v2 fam-entries） ---------- */
.entry-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20rpx; margin-bottom: 24rpx; }
.entry-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 28rpx;
  box-shadow: var(--sj-sh-sm);
}
.entry-card:active { transform: scale(0.96); }
.ec-icon {
  width: 80rpx;
  height: 80rpx;
  border-radius: 24rpx;
  padding: 4rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8rpx;
}
/* 图标图片圆角与外圈曲线平行（同心）：外半径 24 - 内边距 4 = 20rpx */
.ec-icon .sj-icon { border-radius: 20rpx; }
.ec-title { font-size: 27rpx; font-weight: 800; color: var(--sj-ink); }
.ec-sub { font-size: 22rpx; color: var(--sj-sub); }

/* ---------- 邀请说明 ---------- */
.invite-note {
  border: 2rpx dashed var(--sj-line);
  background: var(--sj-cream);
  border-radius: var(--sj-r-md);
  padding: 20rpx 28rpx;
  margin-bottom: 24rpx;
}
.invite-note text { font-size: 21rpx; color: var(--sj-sub); }

/* ---------- 底部 ---------- */
.scroll-end { text-align: center; font-size: 22rpx; color: var(--sj-faint); padding: 24rpx 0 200rpx; letter-spacing: 4rpx; }
</style>
