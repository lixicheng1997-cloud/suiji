<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回按钮 + display 标题 + AI 生成标识胶囊） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">AI 成长日记</text>
      <sj-tag class="diary-tag" variant="pill" bg="#F0EAFB" color="#7A5FB0" text="AI 生成" />
    </view>

    <view class="content">
      <!-- AI 生成提示条（v2 pg-hint 虚线提示；合规文案原样保留） -->
      <view class="pg-hint">
        <text>内容由 AI 自动生成，请核对</text>
        <text class="hint-sub">基础版 · 模型降级时按事实模板拼装</text>
      </view>

      <!-- 统计周期 + 状态徽标 -->
      <view class="range-row">
        <text class="diary-range">{{ diary.range }}</text>
        <text class="d-st-tag draft">草稿 · 待核对</text>
      </view>

      <!-- 段落卡片 + 来源溯源折叠（v2 grow-card：白底 surface + line 边 + r-md + sh-sm） -->
      <view class="grow-card" v-for="(p, i) in diary.paras" :key="i">
        <text class="diary-text">{{ p.text }}</text>
        <view class="d-src-btn" hover-class="hover-press" :hover-stay-time="80" @click="toggleSrc(i)">
          <text>来源 · {{ p.src.length }} 条记录</text>
          <image class="d-chev" :class="{ open: srcOpen[i] }" src="/static/icons/chevron-down.svg" />
        </view>
        <view class="d-src-list" v-if="srcOpen[i]">
          <sj-tag
            v-for="(s, j) in p.src"
            :key="j"
            variant="chip"
            pressable
            :text="s"
            @click="onJump"
          />
          <sj-tag variant="chip" pressable active text="点击可跳转原始记录" @click="onJump" />
        </view>
      </view>

      <!-- 编辑草稿（v2 pg-sec 小节标题 + sj-textarea 输入卡） -->
      <view class="pg-sec"><text>编辑草稿</text></view>
      <sj-textarea v-model="draft" height="640rpx" placeholder="直接修改文字，归档后不可再编辑（可另存副本）" />

      <!-- 暂存 / 归档 双按钮 -->
      <view class="d-actions">
        <sj-button class="d-act" block variant="plain" :loading="saving" :disabled="archiving" text="暂存" @click="onSave" />
        <sj-button class="d-act" block size="lg" :loading="archiving" :disabled="saving" text="确认归档" @click="onArchive" />
      </view>

      <!-- 底部说明（v2 pg-hint；合规文案原样保留） -->
      <view class="pg-hint tail"><text>未归档草稿保留 30 天后自动清理 · 归档后进入成长档案并标注「AI 生成」</text></view>
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import { play } from '@/utils/sound.js'

export default {
  data() {
    return {
      diary: { id: '', range: '', paras: [] },
      srcOpen: [],
      draft: '',
      origDraft: '',
      /* 暂存 / 归档请求在途：互斥且禁止重复提交 */
      saving: false,
      archiving: false,
      statusBarHeight: 20,
      /* onLoad 传入的日记 id：空 = 新建（进页面即 AI 生成） */
      editId: '',
      initDone: false
    }
  },

  onLoad(options) {
    this.editId = (options && options.id) || ''
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
  },

  async onShow() {
    /* 只初始化一次：生成/加载为一次性动作，返回本页不重复触发 */
    if (this.initDone) return
    this.initDone = true
    try {
      if (this.editId) {
        const d = (await api.listDiaries()).find(x => x.id === this.editId)
        if (!d) {
          this.$refs.ntf.show({ type: 'warn', message: '日记不存在或已删除' })
          this.goBack()
          return
        }
        /* 已归档只能预览：回列表页查看 */
        if (d.status === 'archived') {
          this.$refs.ntf.show({ type: 'warn', message: '已归档日记只能预览，请在日记档案页查看' })
          this.goBack()
          return
        }
        this.apply(d)
      } else {
        /* 新建：generateDiary 走 POST /journals/generate（真实 AI 调用，数秒量级），全屏阻断等待 */
        const ld = ui.loading('AI 正在撰写成长日记…', { sub: '正在整理本周记录' })
        let d = null
        try {
          d = await api.generateDiary()
        } finally {
          ld.close()
        }
        this.editId = d.id
        this.apply(d)
        /* AI 日记生成成功、进入草稿待确认：播 E04 */
        play('E04')
      }
    } catch (e) {
      ui.error(e, '日记加载失败')
      this.goBack()
    }
  },

  methods: {
    /* 装载日记：段落卡 + 来源折叠 + 草稿编辑框回填 */
    apply(d) {
      this.diary = { id: d.id, range: d.range, paras: d.paras || [] }
      this.srcOpen = this.diary.paras.map(() => false)
      this.draft = this.diary.paras.map(p => p.text).join('\n\n')
      this.origDraft = this.draft
    },
    /* 编辑框按空行拆段提交（来源标注按段落序号对应保留） */
    buildParas() {
      const blocks = this.draft.split(/\n\s*\n/).map(s => s.trim()).filter(Boolean)
      return blocks.map((text, i) => {
        const old = this.diary.paras[i] || {}
        return { text, src: old.src || [], entryIds: old.entryIds || [] }
      })
    },
    toggleSrc(i) {
      this.srcOpen[i] = !this.srcOpen[i]
    },
    onJump() {
      /* 模板未传段落下标，跳当前日记首个带来源记录的段落原始记录 */
      const p = (this.diary.paras || []).find(x => x.entryIds && x.entryIds.length)
      const id = p ? p.entryIds[0] : ''
      if (id) {
        uni.navigateTo({ url: '/pages/detail/detail?id=' + id })
      } else {
        this.$refs.ntf.show({ type: 'warn', message: '暂无可跳转的原始记录' })
      }
    },
    /* 暂存：只保存正文，状态保持草稿 */
    async onSave() {
      if (this.saving || this.archiving) return
      if (!this.diary.id) return
      if (this.draft === this.origDraft) {
        this.$refs.ntf.show({ type: 'ok', message: '草稿没有修改' })
        this.goBack()
        return
      }
      this.saving = true
      const ld = ui.loading('正在暂存草稿…')
      try {
        await api.updateDiary(this.diary.id, { paras: this.buildParas() })
        this.$refs.ntf.show({ type: 'ok', message: '已暂存 · 30 天内可继续编辑' })
        this.goBack()
      } catch (e) {
        ui.error(e, '暂存失败，草稿已保留')
      } finally {
        ld.close()
        this.saving = false
      }
    },
    /* 归档：保存正文并置为已归档（归档后只能预览） */
    async onArchive() {
      if (this.archiving || this.saving) return
      if (!this.diary.id) return
      /* 归档后不可再编辑：正文清空就按下去，会存出一份没有内容、也改不回来的档案 */
      if (!this.draft.trim()) {
        this.$refs.ntf.show({ type: 'warn', message: '正文为空，先写点什么再归档' })
        return
      }
      this.archiving = true
      const ld = ui.loading('正在归档日记…')
      try {
        await api.updateDiary(this.diary.id, { paras: this.buildParas(), status: 'archived' })
        /* 日记归档成功：播 E06 */
        play('E06')
        this.$refs.ntf.show({ type: 'ok', message: '已归档 · 进入成长档案并标注「AI 生成」' })
        this.goBack()
      } catch (e) {
        /* 归档失败留在本页继续编辑草稿，不能谎报成功 */
        ui.error(e, '归档失败，草稿已保留')
      } finally {
        ld.close()
        this.archiving = false
      }
    },
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/diary/diary' })
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;
  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
}

/* ---------- 顶栏 pg-back ---------- */
.pg-back {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding-left: 24rpx;
  padding-right: 24rpx;
  padding-bottom: 24rpx;
}
.bk {
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--sj-sh-sm);
  flex: none;
}
.bk:active { transform: scale(0.92); }
.bk-ic { width: 40rpx; height: 40rpx; }
.pg-title {
  flex: 1;
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: var(--sj-ink);
}
/* AI 标识小胶囊（sj-tag pill，配色经组件 props 下发） */
.diary-tag { flex: none; }

/* ---------- 内容区 ---------- */
.content { padding: 8rpx 32rpx 48rpx; }

/* 虚线提示行（v2 pg-hint） */
.pg-hint {
  font-size: 23rpx;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: 24rpx;
  padding: 16rpx 24rpx;
  margin-bottom: 24rpx;
  line-height: 1.5;
}
.pg-hint.tail { margin-top: 40rpx; margin-bottom: 0; }
.hint-sub {
  display: block;
  font-size: 21rpx;
  color: var(--sj-faint);
  margin-top: 6rpx;
}

/* 周期行 + 状态徽标 */
.range-row { display: flex; align-items: center; gap: 16rpx; margin-bottom: 20rpx; }
.diary-range { display: block; font-size: 24rpx; font-weight: 700; color: var(--sj-sub); }
.d-st-tag { font-size: 20rpx; font-weight: 700; padding: 4rpx 16rpx; border-radius: var(--sj-r-pill); flex: none; }
.d-st-tag.draft { color: #B47714; background: #FFF3D6; }

/* 段落卡（v2 grow-card 观感） */
.grow-card {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  box-shadow: var(--sj-sh-sm);
  padding: 28rpx;
  margin-bottom: 24rpx;
}
.diary-text { display: block; font-size: 28rpx; color: var(--sj-ink); line-height: 1.9; margin-bottom: 16rpx; }

/* 来源折叠 */
.d-src-btn {
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 24rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
}
.d-chev {
  width: 28rpx;
  height: 28rpx;
  transform: rotate(-90deg);
  transition: transform 0.25s cubic-bezier(.22,.8,.3,1);
}
.d-chev.open { transform: rotate(0deg); }
.d-src-list { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 20rpx; }

/* 小节标题（v2 pg-sec：primary 短竖条 + faint 大字） */
.pg-sec {
  display: flex;
  align-items: center;
  gap: 12rpx;
  font-size: 24rpx;
  font-weight: 900;
  color: var(--sj-faint);
  margin: 28rpx 0 16rpx;
}
.pg-sec::before {
  content: "";
  width: 10rpx;
  height: 28rpx;
  border-radius: 6rpx;
  background: var(--sj-primary);
  flex: none;
}

/* 暂存 / 归档 双按钮：等宽并排 */
.d-actions { display: flex; gap: 20rpx; margin-top: 40rpx; }
.d-act { flex: 1; display: flex; }
</style>
