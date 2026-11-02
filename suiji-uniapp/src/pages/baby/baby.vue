<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：奶油渐隐 sticky + 圆形返回钮 + 显示字族标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">{{ pageTitle }}</text>
    </view>

    <view class="form-wrap">
      <!-- 头像 + 昵称（v2 pg-ava 圆底白描边 + 相机角标；头像支持相册 / 拍照自定义） -->
      <view class="pn-avatar-row">
        <view class="pn-avatar-wrap" hover-class="hover-press" :hover-stay-time="80" @click="onAvatar">
          <view class="pg-ava">
            <image class="ava-img" :src="avatarSrc || ('/static/icons/ctl/' + __theme + '/128/45-ctl-avatar.png')" :mode="avatarSrc ? 'aspectFill' : 'aspectFit'" />
          </view>
          <view class="pn-avatar-badge">
            <image class="pn-badge-ic" :src="'/static/icons/ctl/' + __theme + '/48/58-ctl-upload.png'" />
          </view>
        </view>
        <view class="pn-name-col">
          <!-- 昵称输入：sj-input 无边框透明输入，白底描边容器由页面 .name-input 自绘；
               12 字上限同时兜住服务端加密列宽（宝宝昵称不该更长） -->
          <view class="name-input">
            <sj-input v-model="name" :maxlength="12" placeholder="宝宝昵称" />
          </view>
          <text class="pn-av-tip">点击头像更换照片：相册选图或拍照</text>
        </view>
      </view>

      <!-- 性别（单选 chips，v2 pg-chips） -->
      <view class="pg-sec"><text>性别 </text><text class="req">*</text></view>
      <view class="pg-chips">
        <sj-tag
          v-for="c in genders"
          :key="c"
          variant="chip"
          pressable
          :active="gender === c"
          :text="c"
          @click="gender = c"
        />
      </view>

      <!-- 出生日期 + 实时月龄（v2 pg-field：label 灰粗 / val 墨色特粗） -->
      <view class="pg-sec"><text>出生日期 </text><text class="req">*</text></view>
      <view class="pg-field">
        <text class="pf-label">出生日期</text>
        <!-- 行内只留触发文本：面板实例挂在页面根（见下方 dtp），避开 .pg-field 的 backdrop-filter 包含块 -->
        <text class="pf-val dt-trigger" hover-class="hover-press" :hover-stay-time="80" @click="openBirthPicker">{{ birthDate || '选择出生日期' }} ▾</text>
        <text class="bp-age-chip" v-if="birthDate">{{ ageLabel }}</text>
      </view>

      <!-- 早产与矫正月龄（sj-switch：开=语义绿，change 回写状态） -->
      <view class="pg-sec"><text>早产与矫正月龄</text></view>
      <view class="pg-field">
        <text class="pf-label">是否早产</text>
        <sj-switch :checked="preterm" class="sw-right" @change="(v) => (preterm = v)" />
      </view>
      <block v-if="preterm">
        <view class="pg-field">
          <text class="pf-label">出生胎周</text>
          <!-- 步进器（sj-number-box：限幅 0–37 周，步长 1；单位已含在 label 中） -->
          <sj-number-box v-model="gestWeek" :min="0" :max="37" :step="1" class="nb-right" />
        </view>
        <view class="pg-hint warn">
          <text>成长曲线将自动按矫正年龄计算（胎龄 {{ gestWeek }} 周）</text>
          <text class="pb-tag">矫正</text>
        </view>
      </block>

      <!-- 出生数据（步进器嵌在 pg-field 内） -->
      <view class="pg-sec"><text>出生数据</text></view>
      <view class="pg-field">
        <text class="pf-label">出生体重（g）</text>
        <!-- 步进器（sj-number-box：限幅 0–6000 g，步长 50；单位放 label） -->
        <sj-number-box v-model="birthWeight" :min="0" :max="6000" :step="50" class="nb-right" />
      </view>
      <view class="pg-field">
        <text class="pf-label">出生身长（cm）</text>
        <!-- 步进器（sj-number-box：限幅 0–60 cm，步长 0.5；单位放 label） -->
        <sj-number-box v-model="birthHeight" :min="0" :max="60" :step="0.5" class="nb-right" />
      </view>

      <!-- 过敏史（合规：仅记录原话，不做医学解读） -->
      <view class="pg-sec"><text>过敏史</text></view>
      <!-- 过敏史备注（sj-textarea：白底描边容器由组件自绘，上限 500 字） -->
      <sj-textarea v-model="allergy" placeholder="如：奶粉蛋白过敏、药物过敏史…（仅记录原话，不做医学解读）" :maxlength="500" height="176rpx" />

      <!-- 底部通栏主按钮（v2 pg-btn：primary 渐变） -->
      <sj-button
        class="pg-btn"
        block
        size="lg"
        :loading="busy"
        :text="isNew ? '创建档案' : '保存'"
        @click="onSave"
      />
    </view>

    <!-- 出生日期滚轮面板：挂在页面根（与 vaccine 页同款），fixed 弹层不被 .pg-field 的
         backdrop-filter 包含块困住，才能贴住视口底部；ghost 触发器零尺寸不占布局 -->
    <sj-datetime-picker ref="dtp" mode="date" :value="birthDate" @change="onDateChange">
      <view class="dtp-ghost" />
    </sj-datetime-picker>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import { GENDERS } from '@/utils/mock.js'
import { pickAvatar } from '@/utils/avatar.js'
import * as http from '@/api/http.js'
import * as ui from '@/utils/ui.js'

/* 月龄计算（逐字照原型 ageFromBirth：月差 + 日差，借上月天数） */
function ageFromBirth(dstr) {
  const b = new Date(dstr + 'T00:00:00')
  if (isNaN(b.getTime())) return '—'
  const now = new Date()
  let months = (now.getFullYear() - b.getFullYear()) * 12 + (now.getMonth() - b.getMonth())
  let days = now.getDate() - b.getDate()
  if (days < 0) { months -= 1; days += new Date(now.getFullYear(), now.getMonth(), 0).getDate() }
  if (months < 0) return '未出生'
  return months + ' 个月 ' + days + ' 天'
}

export default {
  data() {
    return {
      /* 新建模式（?new=1）：保存时创建新档案并切换为当前宝宝 */
      isNew: false,
      /* 指定档案模式（?id=xxx）：查看/编辑该宝宝，不要求其为当前宝宝 */
      editId: '',
      /* 保存中：头像上传 + 建档/更新 + 疫苗排期串成一条链路，期间禁止重复提交 */
      busy: false,
      statusBarHeight: 20,
      /* 自定义头像源：选图后为本地临时路径，保存时上传 /files 换成文件 URL */
      avatar: '',
      name: '',
      gender: '男',
      genders: GENDERS,
      birthDate: '',
      preterm: false,
      gestWeek: 0,
      birthWeight: 0,
      birthHeight: 0,
      allergy: ''
    }
  },

  computed: {
    /* 未自定义头像时留空（模板回退本地图标占位）；/api/ 文件路径解析为带 token 的绝对 URL */
    avatarSrc() {
      return api.fileSrc(this.avatar)
    },
    pageTitle() {
      if (this.isNew) return '新建宝宝档案'
      if (this.editId) return this.name ? '编辑 · ' + this.name : '编辑宝宝档案'
      return '宝宝档案'
    },
    ageLabel() {
      return ageFromBirth(this.birthDate)
    }
  },

  onLoad(query) {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
    this.isNew = !!(query && query.new)
    this.editId = (query && query.id) || ''
    /* 新建模式保留空表单，编辑模式回填目标宝宝（?id= 指定，缺省为当前宝宝） */
    if (!this.isNew) this.loadProfile()
  },

  methods: {
    /* 读取目标宝宝档案（DB 行 → 页面字段：kg→g、boy/girl→男/女、胎周<40 视为早产） */
    loadProfile() {
      const b = this.editId ? api.getBabyById(this.editId) : api.getBaby()
      /* 指定档案不存在（如已被删除）：提示后返回，不落入演示默认值 */
      if (this.editId && !b) {
        /* onLoad 期间 ref 未就绪：nextTick 等首渲染后弹横幅，延迟返回让其完整可见 */
        this.$nextTick(() => {
          this.$refs.ntf.show({ type: 'err', message: '该宝宝档案不存在' })
          setTimeout(() => this.goBack(), 1200)
        })
        return
      }
      /* 无档案：保留空表单，不填任何演示值 */
      if (!b) return
      this.name = b.name || ''
      this.avatar = b.avatar || ''
      this.gender = b.gender === 'girl' ? '女' : '男'
      this.birthDate = b.birth_date
      this.preterm = Number(b.gestational_weeks) < 40
      this.gestWeek = this.preterm ? Number(b.gestational_weeks) : 0
      this.birthWeight = Math.round((Number(b.birth_weight) || 0) * 1000)
      this.birthHeight = Number(b.birth_length) || 0
      this.allergy = b.allergy || ''
    },

    /* 自定义头像：真实调起相册 / 相机，选中后本地路径即时预览，点保存时上传 /files */
    onAvatar() {
      pickAvatar().then(path => {
        if (!path) { this.$refs.ntf.show({ type: 'err', message: '未能读取该图片，请重试' }); return }
        this.avatar = path
        this.$refs.ntf.show({ type: 'ok', message: '头像已选择 · 保存后生效' })
      }).catch(() => { /* 用户取消 */ })
    },

    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    /* 建档完成后：尚未留痕隐私同意 → 先补同意（同意后回首页）；否则提示后返回列表页 */
    afterCreate() {
      if (!api.getConsent()) {
        uni.reLaunch({ url: '/pages/consent/consent' })
        return
      }
      setTimeout(() => this.goBack(), 800)
    },

    /* 行内触发文本 → 打开页面根的滚轮面板实例（同 vaccine 页 $refs.dtp.open() 模式） */
    openBirthPicker() {
      this.$refs.dtp.open()
    },

    onDateChange(e) {
      this.birthDate = e.detail.value
    },

    /* 保存：页面字段 → DB 行（g→kg、男/女→boy/girl、早产记胎周否则 40）；建档/更新走云端 */
    async onSave() {
      if (this.busy) return
      if (this.isNew && !this.birthDate) {
        this.$refs.ntf.show({ type: 'warn', message: '请先选择出生日期' })
        return
      }
      this.busy = true
      const ld = ui.loading(this.isNew ? '正在创建宝宝档案…' : '正在保存档案…')
      try {
        /* 头像为本地临时路径时先上传 /files（契约 §7.5）：已有档案直接挂载，新建档案创建后补挂 */
        let avatarUrl = this.avatar
        let avatarFileId = ''
        if (avatarUrl && !/^\/api\/|^data:|^https?:/i.test(avatarUrl)) {
          ld.update({ text: '正在上传头像…' })
          const cur0 = api.getBaby()
          const mountId = this.isNew ? '' : (this.editId || (cur0 ? cur0.id : ''))
          try {
            const f = await http.uploadFile(avatarUrl, { businessType: 'baby', businessId: mountId, babyId: mountId })
            avatarUrl = f.url || ''
            avatarFileId = f.id || ''
          } catch (e) {
            ui.error(e)
            this.$refs.ntf.show({ type: 'warn', message: '头像上传失败，本次不带头像保存' })
            avatarUrl = ''
          }
        }
        const patch = {
          avatar: avatarUrl,
          name: this.name || '宝宝',
          gender: this.gender === '女' ? 'girl' : 'boy',
          birth_date: this.birthDate,
          gestational_weeks: this.preterm ? this.gestWeek : 40,
          birth_length: this.birthHeight,
          birth_weight: this.birthWeight / 1000,
          allergy: this.allergy
        }
        if (this.isNew) {
          /* createBaby 变异步：服务端建档时同步初始化里程碑与疫苗排期 */
          const row = await api.createBaby(patch)
          if (avatarFileId) http.patch('/files/' + avatarFileId, { business_type: 'baby', business_id: row.id }).catch(() => {})
          api.setActiveBaby(row.id)
          ld.update({ text: '正在排布疫苗计划…' })
          await api.ensureVaccineSchedule()
          this.$refs.ntf.show({ type: 'ok', message: '已创建「' + patch.name + '」档案 · 已切换' })
          this.afterCreate()
          return
        }
        /* 编辑目标：?id= 指定的档案，缺省为当前宝宝 */
        const cur = api.getBaby()
        const id = this.editId || (cur ? cur.id : '')
        if (!id) {
          const row = await api.createBaby(patch)
          if (avatarFileId) http.patch('/files/' + avatarFileId, { business_type: 'baby', business_id: row.id }).catch(() => {})
          ld.update({ text: '正在排布疫苗计划…' })
          await api.ensureVaccineSchedule()
          this.$refs.ntf.show({ type: 'ok', message: '已创建「' + patch.name + '」档案 · 已切换' })
          this.afterCreate()
          return
        }
        await api.updateBaby(id, patch)
        /* 当前宝宝的出生日期可能变化：从服务端刷新疫苗计划日期 */
        if (cur && cur.id === id) {
          ld.update({ text: '正在排布疫苗计划…' })
          await api.ensureVaccineSchedule()
        }
        this.$refs.ntf.show({ type: 'ok', message: '「' + patch.name + '」档案已更新' })
        /* 保存成功：短暂展示提示后返回宝宝档案列表页 */
        setTimeout(() => this.goBack(), 800)
      } catch (e) {
        ui.error(e, '保存失败，请重试')
      } finally {
        ld.close()
        this.busy = false
      }
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
}

/* ---------- 顶栏（v2 pg-back：sticky 奶油渐隐 + 圆形返回钮） ---------- */
.pg-back {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding-left: 32rpx;
  padding-right: 32rpx;
  padding-bottom: 24rpx;
  position: sticky;
  top: 0;
  z-index: 10;
  background: linear-gradient(var(--sj-cream) 82%, transparent);
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
.bk-ic { width: 36rpx; height: 36rpx; }
.pg-title {
  flex: 1;
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: var(--sj-ink);
}

/* ---------- 表单内容区：左右 32rpx，元素间距 24rpx ---------- */
.form-wrap { padding: 8rpx 32rpx 80rpx; }

/* 分组小标题（v2 pg-sec：前置主色圆角短条） */
.pg-sec {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
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
.req { color: var(--sj-primary); }

/* 头像 + 昵称行 */
.pn-avatar-row { display: flex; align-items: center; gap: 28rpx; margin-bottom: 8rpx; }
.pn-avatar-wrap { position: relative; flex: none; }
/* 头像（v2 pg-ava：primary-soft 圆底 + 白描边） */
.pg-ava {
  width: 144rpx;
  height: 144rpx;
  border-radius: 50%;
  background: var(--sj-primary-soft);
  border: 4rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.ava-img { width: 100%; height: 100%; }
/* 相机角标（v2 主色渐变圆钮） */
.pn-avatar-badge {
  position: absolute;
  right: -2rpx;
  bottom: -2rpx;
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: linear-gradient(145deg, var(--sj-primary), var(--sj-primary-deep));
  border: 3rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}
.pn-badge-ic { width: 24rpx; height: 24rpx; }
.pn-name-col { flex: 1; display: flex; flex-direction: column; gap: 10rpx; min-width: 0; }
.pn-av-tip { font-size: 21rpx; color: var(--sj-faint); line-height: 1.4; }
/* 昵称输入容器（v2 pg-field 同款：毛玻璃面 + 半透高光边 + 28rpx 圆角；输入本身由 sj-input 承担） */
.name-input {
  width: 100%;
  /* 防 H5 固定高度被垂直 padding 压塌后无法点击聚焦，显式给总高并垂直居中 */
  height: 88rpx;
  border: 2rpx solid var(--sj-glass-line);
  border-radius: 28rpx;
  background: var(--sj-glass);
  box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
  padding: 0 24rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  transition: border-color 0.2s var(--sj-smooth), box-shadow 0.2s var(--sj-smooth);
}
.name-input:focus-within {
  border-color: var(--sj-primary);
  box-shadow: var(--sj-glass-hi), 0 8rpx 28rpx rgba(247, 161, 92, 0.22);
}

/* chips 单选（v2 pg-chips：选中 primary-soft 底 + primary 描边） */
.pg-chips { display: flex; flex-wrap: wrap; gap: 16rpx; margin-bottom: 24rpx; }

/* 字段行（v2 pg-field：毛玻璃面 + 半透高光描边 + 28rpx 圆角；玻璃配方见 App.vue --sj-glass*） */
.pg-field {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-glass);
  border: 2rpx solid var(--sj-glass-line);
  border-radius: 28rpx;
  box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
  padding: 20rpx 28rpx;
  margin-bottom: 24rpx;
  font-size: 27rpx;
  transition: border-color 0.2s var(--sj-smooth), box-shadow 0.2s var(--sj-smooth);
}
/* 行内输入聚焦：描边转主色 + 主色柔投影，给出「可书写」的即时反馈 */
.pg-field:focus-within {
  border-color: var(--sj-primary);
  box-shadow: var(--sj-glass-hi), 0 8rpx 28rpx rgba(247, 161, 92, 0.22);
}
/* label 宽 240rpx + 禁换行：带单位标签（如「出生身长（cm）」，全角括号实际渲染宽于估算）保持单行 */
.pf-label { color: var(--sj-sub); font-weight: 700; flex: none; width: 240rpx; white-space: nowrap; }
.pf-val { flex: 1; color: var(--sj-ink); font-weight: 800; }
/* 出生日期触发文本：pf-val 自带 flex:1 撑满剩余宽度，居右对齐（面板实例挂在页面根） */
.dt-trigger { text-align: right; }
/* 页面根 picker 的 ghost 触发器：零尺寸不占布局（同 vaccine 页 .dtp-ghost） */
.dtp-ghost { width: 0; height: 0; }
/* 月龄软标（v2 ms-badge 同款金调） */
.bp-age-chip {
  margin-left: auto;
  font-size: 21rpx;
  font-weight: 800;
  color: #B47714;
  background: var(--sj-duck-soft, #FFF3C4);
  padding: 6rpx 20rpx;
  border-radius: var(--sj-r-pill);
  white-space: nowrap;
  flex: none;
}

/* 提示文案行（v2 pg-hint；warn 金调变体用于矫正月龄说明） */
.pg-hint {
  display: flex;
  align-items: center;
  gap: 12rpx;
  font-size: 23rpx;
  color: var(--sj-sub);
  background: var(--sj-cream);
  border: 2rpx dashed var(--sj-line);
  border-radius: 24rpx;
  padding: 16rpx 24rpx;
  margin-bottom: 24rpx;
  line-height: 1.5;
}
.pg-hint.warn { color: #8A6A1E; border-color: #F0CE7A; background: #FFF3D6; }
.pb-tag {
  font-size: 20rpx;
  font-weight: 800;
  background: rgba(0, 0, 0, 0.07);
  color: #8A6A1E;
  border-radius: var(--sj-r-pill);
  padding: 2rpx 16rpx;
  margin-left: auto;
  flex: none;
}

/* 步进器行内布局：sj-number-box 右对齐（原自绘 .num-stepper 由控件库接管；单位统一放 label，不再行内展示） */
.nb-right { margin-left: auto; }

/* 开关行内布局：sj-switch 右对齐（原自绘 .pg-sw 由控件库接管） */
.sw-right { margin-left: auto; }
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn {
  display: flex;
  margin-top: 40rpx;
}
</style>
