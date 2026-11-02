<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：奶油渐隐 sticky + 圆形返回钮 + 显示字族标题） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">家长信息</text>
    </view>

    <view class="form-wrap">
      <!-- 头像（v2 pg-ava：primary-soft 圆底白描边 + 相机角标；点击头像更换照片，与宝宝档案页同款） -->
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
          <text class="pn-av-tip">点击头像更换照片：相册选图或拍照</text>
        </view>
      </view>

      <!-- 昵称（v2 pg-field：label 灰粗 / 输入墨色特粗；输入由 sj-input 无边框透明控件承担）
           昵称是家人看到的称呼（成员卡片、记录人「妈妈 · 昵称」），不是登录账号；
           留空时服务端按注册昵称兜底，故不作必填校验 -->
      <view class="pg-field">
        <text class="pf-label">昵称</text>
        <sj-input v-model="name" placeholder="家人看到的称呼" class="pf-input" />
      </view>
      <view class="form-sub"><text>用于成员卡片与记录人展示（如「妈妈 · 昵称」）· 留空则沿用注册时填写的昵称</text></view>

      <!-- 账号（用户名，只读） -->
      <view class="pg-sec"><text>账号（用户名）</text><text class="hint-chip">用于登录 · 不可修改</text></view>
      <view class="pg-field">
        <text class="pf-label">登录账号</text>
        <text class="pf-val">{{ account }}</text>
      </view>

      <!-- 与宝宝关系（单选 chips + 自定义输入行，样式/交互与信息记录页 editor 同款） -->
      <view class="pg-sec"><text>与宝宝关系 </text><text class="req">*</text></view>
      <view class="pg-chips">
        <sj-tag
          v-for="c in relationChips"
          :key="c"
          variant="chip"
          pressable
          :active="!customOpen && relation === c"
          :text="c"
          @click="pickRelation(c)"
        />
      </view>
      <view v-if="customOpen" class="custom-row">
        <view class="custom-input">
          <sj-input v-model="customText" placeholder="输入关系称呼，如：姑姑" @confirm="addCustomRelation" />
        </view>
        <sj-button class="custom-add" size="mini" text="添加" @click="addCustomRelation" />
      </view>

      <!-- 角色权限（只读，由家庭创建者分配；role 徽标 v2 四色规范） -->
      <view class="pg-sec"><text>角色权限（家庭空间）</text></view>
      <view class="pg-field">
        <text class="pf-label">当前角色</text>
        <text class="role" :class="mom.role">{{ mom.tag }}</text>
      </view>
      <view class="form-sub"><text>{{ mom.desc }} · 角色由家庭创建者分配</text></view>

      <!-- 常用记录类别（多选 chips） -->
      <view class="pg-sec"><text>常用记录类别</text></view>
      <view class="pg-chips">
        <sj-tag
          v-for="k in sortedCatKeys"
          :key="k"
          variant="chip"
          pressable
          :active="cats.indexOf(k) > -1"
          :text="TYPES[k].label"
          @click="toggleCat(k)"
        />
      </view>
      <view class="form-sub"><text>选中的类别将排在快速记录面板前列</text></view>

      <!-- 底部通栏主按钮（v2 pg-btn：primary 渐变） -->
      <sj-button
        class="pg-btn"
        block
        size="lg"
        :loading="busy"
        text="保存"
        @click="onSave"
      />
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import { TYPES } from '@/utils/mock.js'
import { pickAvatar } from '@/utils/avatar.js'
import * as http from '@/api/http.js'
import * as ui from '@/utils/ui.js'

export default {
  data() {
    return {
      statusBarHeight: 20,
      TYPES,
      avatar: '',
      name: '',
      account: '',
      relation: '妈妈',
      relations: [],
      /* 自定义关系：customOpen 展开输入行（触发 chip“自定义”）；customText 为输入值；
       * 已保存值不在预设中时并入预设 chips 并选中（与信息记录页里程碑回显同款） */
      customOpen: false,
      customText: '',
      cats: [],
      catKeys: Object.keys(TYPES),
      /* 保存中：头像上传期间禁止重复提交 */
      busy: false,
      /* 当前账号在家庭空间中的角色（onLoad 按 family.role 派生，只读展示） */
      mom: { role: 'owner', tag: '创建者', desc: '创建家庭空间 · 全部权限' }
    }
  },

  computed: {
    /* /api/ 文件路径解析为带 token 的绝对 URL；本地临时路径与默认头像原样透传 */
    avatarSrc() {
      return api.fileSrc(this.avatar)
    },
    /* 常用记录类别 chips 顺序：已勾选的排最前（组内按勾选先后即 cats 顺序），未勾选的按 TYPES 顺序殿后 */
    sortedCatKeys() {
      const picked = this.cats.filter(k => this.catKeys.indexOf(k) > -1)
      const rest = this.catKeys.filter(k => this.cats.indexOf(k) === -1)
      return picked.concat(rest)
    },
    /* 关系 chips：预设 + “自定义”触发项（触发项不是选项，点击展开输入行） */
    relationChips() {
      return this.relations.concat(['自定义'])
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
    const p = api.getParentInfo()
    this.avatar = p.avatar
    /* 昵称未设置时回显注册昵称，与展示口径（家长昵称 → 注册昵称）一致 */
    this.name = p.name || api.getNickname()
    this.account = p.account || api.getUsername()
    this.relation = p.relation
    this.relations = p.relations
    /* 回显：已保存的关系不在预设中（旧数据“其他”或历史自定义值）→ 并入 chips 并选中，与信息记录页里程碑回显同款 */
    if (this.relations.indexOf(this.relation) === -1 && this.relation) {
      this.relations.push(this.relation)
    }
    this.cats = p.cats.slice()
    /* 角色徽标取当前账号在家庭中的角色（契约 §4 family.role：creator|member），
     * 成员行只有 {id,name,role,color}，tag/desc 需在此派生 */
    const fam = api.getFamilyInfo()
    if (fam) {
      const isCreator = fam.role === 'creator' || fam.role === 'owner'
      this.mom = isCreator
        ? { role: 'owner', tag: '创建者', desc: '创建家庭空间 · 全部权限' }
        : { role: 'editor', tag: '成员', desc: api.isFamilyReadonly() ? '家庭只读开启 · 仅可查看' : '参与家庭记录 · 权限由创建者分配' }
    }
  },

  methods: {
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },
    onAvatar() {
      /* 与宝宝档案页一致：pickAvatar 选图并压缩，保存时上传 /files（契约 §7.5） */
      pickAvatar().then(path => {
        if (!path) { this.$refs.ntf.show({ type: 'err', message: '未能读取该图片，请重试' }); return }
        this.avatar = path
        this.$refs.ntf.show({ type: 'ok', message: '头像已选择 · 保存后生效' })
      }).catch(() => { /* 用户取消 */ })
    },
    /* 关系选择：“自定义”触发项展开/收起输入行，其余直接赋值 */
    pickRelation(c) {
      if (c === '自定义') {
        this.customOpen = !this.customOpen
        return
      }
      this.relation = c
    },
    /* 自定义关系：加入 chips（去重）并自动选中，收起输入行 */
    addCustomRelation() {
      const v = (this.customText || '').trim()
      if (!v) {
        this.$refs.ntf.show({ type: 'warn', message: '请输入关系称呼' })
        return
      }
      if (this.relations.indexOf(v) === -1) this.relations.push(v)
      this.relation = v
      this.customText = ''
      this.customOpen = false
    },
    toggleCat(k) {
      const i = this.cats.indexOf(k)
      if (i > -1) this.cats.splice(i, 1)
      else this.cats.push(k)
    },
    async onSave() {
      if (this.busy) return
      /* 关系值必填（预设或已“添加”的自定义项都在 relation 上） */
      if (!this.relation) {
        this.$refs.ntf.show({ type: 'warn', message: '请选择与宝宝的关系' })
        return
      }
      /* 头像为本地临时路径时先上传 /files（契约 §7.5），档案只存返回的文件 URL */
      let avatarUrl = this.avatar
      const needUpload = !!avatarUrl && !/^\/api\/|^data:|^https?:/i.test(avatarUrl)
      /* 上传一张头像要走一次 multipart（几百 KB 起），慢网下页面必须给出阻断反馈 */
      const ld = needUpload ? ui.loading('正在上传头像…') : null
      this.busy = true
      try {
        if (needUpload) {
          try {
            const f = await http.uploadFile(avatarUrl, { businessType: 'parent' })
            avatarUrl = f.url || ''
            this.avatar = avatarUrl
          } catch (e) {
            ui.error(e)
            this.$refs.ntf.show({ type: 'warn', message: '头像上传失败，本次不带头像保存' })
            avatarUrl = api.getParentInfo().avatar || ''
          }
        }
        api.saveParentInfo({
          avatar: avatarUrl,
          name: this.name,
          account: this.account,
          relation: this.relation,
          cats: this.cats.slice()
        })
        this.$refs.ntf.show({ type: 'ok', message: '已保存' })
        /* 保存成功：短暂展示提示后返回“我的”列表页 */
        setTimeout(() => this.goBack(), 800)
      } finally {
        if (ld) ld.close()
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
/* 说明小胶囊（v2 hint-chip：primary-soft 底） */
.hint-chip {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  padding: 6rpx 20rpx;
  border-radius: var(--sj-r-pill);
}
/* 表单辅助说明文字 */
.form-sub { font-size: 22rpx; color: var(--sj-faint); line-height: 1.6; margin: -8rpx 0 24rpx; }

/* 头像行（v2 pg-ava + 相机角标，与宝宝档案页同款控件） */
.pn-avatar-row { display: flex; align-items: center; gap: 28rpx; margin-bottom: 28rpx; }
.pn-avatar-wrap { position: relative; flex: none; }
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
  flex: none;
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

/* 字段行（v2 pg-field：毛玻璃面 + 半透高光描边 + 28rpx 圆角，label 灰粗 / val 墨色特粗） */
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
.pf-label { color: var(--sj-sub); font-weight: 700; flex: none; width: 148rpx; }
.pf-val { flex: 1; color: var(--sj-ink); font-weight: 800; }
/* 行内输入（sj-input 无边框透明控件在本页仅负责占满 label 右侧剩余宽度） */
.pf-input {
  flex: 1;
  min-width: 0;
}

/* chips 单选 / 多选（v2 pg-chips） */
.pg-chips { display: flex; flex-wrap: wrap; gap: 16rpx; margin-bottom: 24rpx; }

/* 自定义关系输入行（与信息记录页 editor 的 custom-row 同款：毛玻璃胶囊输入 + mini 添加钮） */
.custom-row { display: flex; align-items: center; gap: 16rpx; margin-bottom: 24rpx; }
.custom-input {
  flex: 1;
  min-width: 0;
  height: 72rpx;
  display: flex;
  align-items: center;
  border: 2rpx solid var(--sj-glass-line);
  border-radius: var(--sj-r-pill);
  background: var(--sj-glass);
  box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
  padding: 0 24rpx;
  box-sizing: border-box;
  transition: border-color 0.2s var(--sj-smooth), box-shadow 0.2s var(--sj-smooth);
}
.custom-input:focus-within {
  border-color: var(--sj-primary);
  box-shadow: var(--sj-glass-hi), 0 8rpx 28rpx rgba(247, 161, 92, 0.22);
}
.custom-add { flex: none; }

/* 角色徽标（v2 role-* 四色：owner 主色 / edit 蓝 / view 紫；紧随 label 居左） */
.role {
  font-size: 21rpx;
  font-weight: 800;
  border-radius: var(--sj-r-pill);
  padding: 6rpx 20rpx;
  flex: none;
}
.role.owner { background: var(--sj-primary-soft); color: var(--sj-primary-deep); }
.role.editor { background: #E4F3FB; color: #2E7FA8; }
.role.viewer { background: #F0EAFB; color: #7A5FB0; }
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn {
  display: flex;
  margin-top: 40rpx;
}
</style>
