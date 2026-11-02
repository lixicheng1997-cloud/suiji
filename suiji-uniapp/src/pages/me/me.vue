<template>
  <view class="page" :class="swipeClass" :style="themeVars" @touchstart="onTabTouchStart" @touchend="onTabTouchEnd">
    <sj-bg />
    <!-- 顶部个人卡（v2 me-profile：暖渐变 + 圆角头像盒） -->
    <view class="me-profile">
      <view class="me-avatar">
        <image class="ma-img" :src="avatarUrl || ('/static/icons/ctl/' + __theme + '/128/45-ctl-avatar.png')" :mode="avatarUrl ? 'aspectFill' : 'aspectFit'" />
      </view>
      <view class="me-txt">
        <text class="mt-name">{{ parent.name }}</text>
        <text class="mt-sub">账号 {{ parent.account }} · {{ babyCount }} 个宝宝档案 · 全家共享</text>
      </view>
      <text class="me-edit" hover-class="hover-press" :hover-stay-time="80" @click="goParent">编辑</text>
    </view>

    <!-- 设置分组（v2 set-group + set-row：png 图标 / 状态 tag / 开关） -->
    <view class="set-group" v-for="g in groups" :key="g.label">
      <text class="sg-label">{{ g.label }}</text>
      <view
        class="set-row"
        v-for="r in g.rows"
        :key="r.label"
        hover-class="hover-press"
        :hover-stay-time="80"
        @click="onRow(r)"
      >
        <view class="sr-icon">
          <sj-mascot v-if="r.mascot" :size="56" />
          <sj-icon v-else :name="r.png" :size="56" />
        </view>
        <text v-if="!r.sd" class="sr-label">{{ r.label }}</text>
        <view v-else class="sr-label">
          <text>{{ r.label }}</text>
          <text class="sr-desc">{{ r.sd }}</text>
        </view>
        <text v-if="r.tag && r.val" class="set-tag" :class="r.tagCls">{{ r.val }}</text>
        <text v-else-if="r.val" class="sr-val">{{ r.val }}</text>
        <sj-switch
          v-if="r.sw !== undefined"
          class="row-sw"
          :checked="switches[r.sw]"
          @click.stop
          @change="setSwitch(r.sw, $event)"
        />
        <sj-switch
          v-else-if="r.swKey"
          class="row-sw"
          :checked="flags[r.swKey]"
          @click.stop
          @change="setFlag(r.swKey, $event)"
        />
        <image v-else-if="r.chev" class="sr-chev" src="/static/icons/chevron-right.svg" />
      </view>
    </view>

    <view class="scroll-end"><text>岁记 · 记录成长的每一刻</text></view>

    <!-- v2 悬浮底部导航（自动隐藏原生 tabBar） -->
    <sj-tabbar active="me" />

    <!-- 服务器地址选择面板（sj-popup 底部弹层，列表来自前端公共配置 config/app.js） -->
    <sj-popup
      v-model:show="serverShow"
      mode="bottom"
      title="选择服务器地址"
      left-text="取消"
      right-text=""
    >
      <scroll-view scroll-y class="sv-list">
        <view
          v-for="(s, idx) in serverList"
          :key="s.id || idx"
          class="sv-item"
          hover-class="hover-press"
          :hover-stay-time="80"
          @click="chooseServer(s)"
        >
          <view class="sv-item__main">
            <text class="sv-item__name">{{ s.name || s.url }}</text>
            <text class="sv-item__url">{{ s.url }}</text>
          </view>
          <text v-if="s.url === serverUrl" class="sv-item__check">✓</text>
        </view>
      </scroll-view>
    </sj-popup>

    <!-- 修改密码面板（sj-popup 底部弹层：当前 / 新 / 确认 三行输入） -->
    <sj-popup
      v-model:show="pwdShow"
      mode="bottom"
      title="修改密码"
      left-text="取消"
      right-text=""
    >
      <view class="pwd-form">
        <view class="pwd-field">
          <text class="pwf-label">当前密码</text>
          <sj-input class="pwf-in" v-model="pwd.old" type="password" placeholder="输入当前密码" />
        </view>
        <view class="pwd-field">
          <text class="pwf-label">新密码</text>
          <sj-input class="pwf-in" v-model="pwd.next" type="password" placeholder="至少 8 位，含字母和数字" />
        </view>
        <view class="pwd-field">
          <text class="pwf-label">确认密码</text>
          <sj-input class="pwf-in" v-model="pwd.confirm" type="password" placeholder="再次输入新密码" />
        </view>
        <sj-button class="pwd-btn" block size="lg" :loading="pwdBusy" :text="pwdBusy ? '提交中…' : '确认修改'" @click="submitPwd" />
      </view>
    </sj-popup>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import tabSwipe, { pullRefresh } from '@/utils/tabSwipe.js'
import { THEME_LABELS } from '@/theme/theme.js'
import { play, vibrate, isSoundOn, setSoundOn, isVibrateOn, setVibrateOn, debugSnapshot } from '@/utils/sound.js'

/* 开关行下标 → 持久化键（模板以数组下标消费 switches，形状保持不变） */
const SWITCH_KEYS = ['checkup', 'anniversary', 'notify']

export default {
  mixins: [tabSwipe],
  /* 下拉刷新（Vue3 生命周期必须顶层声明，混入 methods 里的不会触发）：重拉 bootstrap 后走 tabAfterPull */
  onPullDownRefresh() { pullRefresh(this) },
  data() {
    return {
      baby: { name: '宝宝', age: '' },
      babyCount: 0,
      /* 家长信息（家长信息页保存后此处真实展示） */
      parent: { name: '家长', account: '' },
      /* 头像：家长信息页更换后真实展示，未设置时模板回退本地图标占位 */
      avatarUrl: '',
      /* 开关状态：体检提醒 / 纪念日提醒 / 消息通知 */
      switches: [true, true, true],
      /* 非提醒类开关（家庭只读等，数据源来自服务端家庭状态；音效/震动为本地持久化开关） */
      flags: { familyReadonly: false, soundOn: true, vibrateOn: true },
      /* 消息中心未读通知数（待办不计入） */
      unread: 0,
      /* 服务器地址选择面板（sj-popup） */
      serverShow: false,
      serverList: [],
      serverUrl: '',
      /* 修改密码面板（sj-popup）：三行输入 + 提交防重复 */
      pwdShow: false,
      pwd: { old: '', next: '', confirm: '' },
      pwdBusy: false,
      THEME_LABELS,
      groups: []
    }
  },

  onShow() {
    this.refresh()
  },

  methods: {
    /* 下拉刷新：tabSwipe 已重拉 bootstrap，重建设置分组行 */
    tabAfterPull() { this.refresh() },
    /* 设置分组行运行时构造：数据来自真实仓储，行对象形状与模板消费一致（png=v2 图标名） */
    refresh() {
      const baby = api.getBaby()
      this.baby = baby ? { name: baby.name, age: baby.age } : { name: '宝宝', age: '' }
      const p = api.getParentInfo()
      /* 昵称未填时退回注册昵称，两者都没有才用「家长」占位 */
      this.parent = { name: p.name || api.getNickname() || '家长', account: p.account }
      if (p.avatar) this.avatarUrl = api.fileSrc(p.avatar) || p.avatar
      const s = api.getSwitches()
      this.switches = SWITCH_KEYS.map(k => !!s[k])
      this.flags = { familyReadonly: api.isFamilyReadonly(), soundOn: isSoundOn(), vibrateOn: isVibrateOn() }
      this.unread = api.getUnreadTotal()
      const babies = api.getBabies()
      this.babyCount = babies.length
      const vs = api.getVaccines()
      const pending = vs.filter(v => !v.done).length
      const overdue = vs.filter(v => v.status === 'overdue').length
      const ai = api.getAiConfig()
      const trashCount = api.listTrash().length
      const server = api.serverLabel()
      const admin = api.isAdmin()
      const rawGroups = [
        {
          label: '宝宝档案与提醒',
          rows: [
            { png: '29-fn-babies', label: '宝宝档案管理', val: `${babies.length} 个档案 · 当前「${this.baby.name}」`, chev: true, go: '/pages/baby-list/baby-list' },
            { png: '21-fn-remind', label: '提醒设置', val: '疫苗 / 体检 / 纪念日', chev: true, go: '/pages/remind/remind' },
            { png: '34-fn-vaccine', label: '疫苗接种时间表（0–6 岁）', val: `待接种 ${pending} 剂` + (overdue ? ` · 逾期 ${overdue}` : ''), tag: true, tagCls: overdue ? 'warn' : '', chev: true, go: '/pages/vaccine/vaccine' },
          ]
        },
        {
          label: '数据与安全',
          rows: [
            { png: '26-fn-export', label: '导出成长档案', val: '曲线 · 里程碑合集', chev: true, go: '/pages/export/export' },
            { png: '27-fn-trash', label: '回收站', val: `${trashCount} 条`, tag: true, chev: true, go: '/pages/trash/trash' }
          ]
        },
        {
          label: '贴心功能',
          rows: [
            { mascot: true, label: '主题切换（' + THEME_LABELS[this.__theme] + '）', val: '轻点换肤', chev: true, act: 'theme' },
            { png: '32-fn-card', label: '控件样式演示', val: 'sj-* 组件全览', chev: true, go: '/pages/uikit/uikit', adminOnly: true },
            { png: '22-fn-backup', label: '服务器地址', sd: '当前：' + api.serverUrl(), val: server, chev: true, act: 'server', adminOnly: true },
          ]
        },
        {
          label: '声音与振动',
          rows: [
            { png: '25-fn-notify', label: '音效', sd: '记录保存、危险确认等场景播放提示音', swKey: 'soundOn' },
            { png: '21-fn-remind', label: '手机震动', sd: '音效播放时同步震动反馈（音效关闭仍可独立振动）', swKey: 'vibrateOn' },
          ]
        },
        {
          label: '通用与账号',
          rows: [
            { png: '23-fn-privacy', label: '修改密码', val: '定期更换更安全', chev: true, act: 'password' },
            { png: '32-fn-card', label: '关于岁记', val: 'v3.0', chev: true, act: 'about' },
            { png: '33-fn-video', label: '启动加载动画（演示）', val: '品牌开场 · 轻点跳过', chev: true, go: '/pages/splash/splash?from=me', adminOnly: true },
            { png: '27-fn-trash', label: '退出登录', val: '切换账号 / 换机', chev: true, act: 'logout' }
          ]
        }
      ]
      /* 管理员专属入口（启动动画/服务器地址/控件样式演示）：非管理员过滤掉，空分组一并移除 */
      this.groups = rawGroups
        .map(g => ({ ...g, rows: g.rows.filter(r => !r.adminOnly || admin) }))
        .filter(g => g.rows.length)
    },

    goParent() {
      uni.navigateTo({ url: '/pages/parent/parent' })
    },

    onRow(r) {
      if (r.act === 'theme') {
        this.toggleTheme()
        this.$refs.ntf.show({ type: 'ok', message: '已切换到「' + THEME_LABELS[this.__theme] + '」' })
        this.refresh()
        return
      }
      if (r.act === 'elder') {
        uni.navigateTo({ url: '/pages/elder/elder' })
        return
      }
      if (r.act === 'aiConfig') return this.doAiConfig()
      if (r.act === 'server') return this.doServer()
      if (r.act === 'logout') return this.doLogout()
      if (r.act === 'password') return this.doPassword()
      if (r.act === 'visibility') return this.doVisibility()
      if (r.act === 'family') return uni.switchTab({ url: '/pages/family/family' })
      if (r.act === 'about') {
        return ui.showModal({
          title: '岁记 v3.0',
          content: '宝宝成长记录\n数据加密保存在云端，登录即可在手机、平板上查看',
          showCancel: false
        })
      }
      if (r.go) {
        uni.navigateTo({ url: r.go })
        return
      }
      this.$refs.ntf.show({ type: 'warn', message: r.label + '：功能开发中，敬请期待' })
    },

    /* 服务器地址：列表来自前端公共配置 config/app.js，用 sj-popup 底部面板选择 */
    doServer() {
      const listLd = ui.loading('正在读取服务器列表…')
      api.fetchServers().then(list => {
        listLd.close()
        if (!list.length) { this.$refs.ntf.show({ type: 'err', message: '暂时没有可选的服务器地址，请稍后再试' }); return }
        this.serverList = list
        this.serverUrl = api.serverUrl()
        this.serverShow = true
      }, () => listLd.close())
    },

    /* 选中某条：落库后全量 bootstrap 重拉对齐缓存，随后收起面板 */
    chooseServer(s) {
      api.setServer(s)
      this.serverUrl = api.serverUrl()
      this.serverShow = false
      /* 换服务器 = 全量 bootstrap 重拉：页面仍是上一台服务器的旧数据，
       * 不阻断的话用户看不出「切了但没生效」 */
      const ld = ui.loading('正在连接新服务器…', { sub: '正在更新数据' })
      api.bootstrap().then(() => {
        ld.close()
        this.$refs.ntf.show({ type: 'ok', message: '已切换到：' + (s.name || s.url) })
        this.refresh()
      }).catch(e => {
        ld.close()
        ui.error(e, '无法连接该服务器，请检查地址是否正确')
      })
    },

    doLogout() {
      ui.showModal({
        title: '退出登录',
        content: '退出后需要重新登录才能查看记录，确定退出吗？',
        confirmText: '退出',
        success: r => { if (r.confirm) api.logout() }
      })
    },

    /* 修改密码：每次打开清空表单，避免残留上次输入 */
    doPassword() {
      this.pwd = { old: '', next: '', confirm: '' }
      this.pwdShow = true
    },

    submitPwd() {
      if (this.pwdBusy) return
      const { old, next, confirm } = this.pwd
      if (!old || !next || !confirm) { this.$refs.ntf.show({ type: 'warn', message: '请填写完整的密码信息' }); return }
      /* 强度规则与服务端一致（≥8 位、非纯数字/纯字母、首尾无空格），本地先挡一次 */
      if (next.length < 8) { this.$refs.ntf.show({ type: 'warn', message: '新密码至少 8 位' }); return }
      if (/^\d+$/.test(next) || /^[a-zA-Z]+$/.test(next)) { this.$refs.ntf.show({ type: 'warn', message: '新密码不能是纯数字或纯字母' }); return }
      if (next !== next.trim()) { this.$refs.ntf.show({ type: 'warn', message: '新密码不能以空格开头或结尾' }); return }
      if (next === old) { this.$refs.ntf.show({ type: 'warn', message: '新密码不能与当前密码相同' }); return }
      if (next !== confirm) { this.$refs.ntf.show({ type: 'warn', message: '两次输入的新密码不一致' }); return }
      this.pwdBusy = true
      const ld = ui.loading('正在修改密码…')
      api.changePassword(old, next).then(() => {
        ld.close()
        this.pwdBusy = false
        this.pwdShow = false
        this.$refs.ntf.show({ type: 'ok', message: '密码已更新 · 其他设备需重新登录' })
      }).catch(e => {
        ld.close()
        this.pwdBusy = false
        ui.error(e, '密码修改失败，请重试')
      })
    },

    /* 健康日志可见性：0 家人可见 / 1 仅自己可见 / 2 隐藏（配置入口统一在「我的」） */
    doVisibility() {
      const opts = ['家人可见', '仅自己可见', '隐藏']
      ui.showActionSheet({
        itemList: opts,
        success: res => {
          api.setHealthVisibility(res.tapIndex)
          this.$refs.ntf.show({ type: 'ok', message: '已设为：' + opts[res.tapIndex] })
          this.refresh()
        }
      }).catch(() => {})
    },

    toggleSwitch(i) {
      const val = !this.switches[i]
      api.setSwitch(SWITCH_KEYS[i], val)
      this.switches[i] = val
      this.$refs.ntf.show({ type: 'ok', message: val ? '提醒已开启' : '提醒已关闭' })
    },

    /* 家庭只读开关：乐观翻转 + 服务端确认（原在家庭页，配置入口统一收进「我的」） */
    toggleFlag(key) {
      const val = !this.flags[key]
      this.flags[key] = val
      if (key === 'familyReadonly') {
        api.setFamilyReadonly(val).then(() => {
          this.$refs.ntf.show({ type: 'ok', message: val ? '家庭只读已开启 · 全体成员仅可浏览' : '家庭只读已关闭 · 成员可正常记录' })
        }).catch(e => {
          this.flags[key] = !val
          ui.error(e, '设置失败')
        })
      }
    },

    /* sj-switch 适配器：事件新值直写 + 保留 toggleSwitch 的持久化与提示（不改原方法） */
    setSwitch(i, v) {
      this.switches[i] = v
      api.setSwitch(SWITCH_KEYS[i], v)
      play('S11') // 提醒开关拨动音效
      this.$refs.ntf.show({ type: 'ok', message: v ? '提醒已开启' : '提醒已关闭' })
    },

    /* sj-switch 适配器：乐观写入 + 失败回滚，副作用与 toggleFlag 一致（不改原方法） */
    setFlag(key, v) {
      this.flags[key] = v
      /* 音效开关：本地持久化；打开时试听一次保存成功音（force 跳过去重） */
      if (key === 'soundOn') {
        setSoundOn(v)
        if (v) play('S03', { force: true })
        this.$refs.ntf.show({ type: 'ok', message: v ? '音效已开启 · 刚为你播放了一段试听' : '音效已关闭' })
        /* 临时诊断：900ms 后回显 API 回调结果（定位后删除） */
        if (v) setTimeout(() => this.$refs.ntf.show({ type: 'warn', message: '诊断 ' + debugSnapshot() }), 900)
        return
      }
      /* 震动开关：本地持久化；打开时立即震一次作为反馈 */
      if (key === 'vibrateOn') {
        setVibrateOn(v)
        if (v) vibrate('confirm_light')
        this.$refs.ntf.show({ type: 'ok', message: v ? '手机震动已开启' : '手机震动已关闭' })
        /* 临时诊断：500ms 后回显震动 API 结果（定位后删除） */
        if (v) setTimeout(() => this.$refs.ntf.show({ type: 'warn', message: '诊断 vib=' + debugSnapshot().split(' | ')[0] }), 500)
        return
      }
      if (key === 'familyReadonly') {
        api.setFamilyReadonly(v).then(() => {
          play('S11') // 家庭只读开关拨动成功音效
          this.$refs.ntf.show({ type: 'ok', message: v ? '家庭只读已开启 · 全体成员仅可浏览' : '家庭只读已关闭 · 成员可正常记录' })
        }).catch(e => {
          this.flags[key] = !v
          ui.error(e, '设置失败')
        })
      }
    },

    /* AI 配置简化：模型 Key 由服务端环境变量持有，客户端仅保留自动生成开关（契约 §11） */
    doAiConfig() {
      const ai = api.getAiConfig()
      api.setAiConfig({ enabled: !ai.enabled })
      this.$refs.ntf.show({ type: 'ok', message: !ai.enabled ? 'AI 自动生成已启用' : 'AI 自动生成已停用' })
      this.refresh()
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

/* ---------- 顶部个人卡（v2 me-profile） ---------- */
.me-profile {
  display: flex;
  align-items: center;
  gap: 24rpx;
  background: linear-gradient(135deg, #FFE8DB, #FFF2DE);
  border: 2rpx solid #FFDCC0;
  border-radius: var(--sj-r-md);
  padding: 28rpx 32rpx;
  margin-bottom: 28rpx;
}
.me-avatar {
  width: 104rpx;
  height: 104rpx;
  border-radius: 36rpx;
  background: var(--sj-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--sj-sh-sm);
  overflow: hidden;
  flex: none;
}
.ma-img { width: 92rpx; height: 92rpx; border-radius: 28rpx; }
.me-txt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6rpx; }
.mt-name { font-size: 30rpx; font-weight: 800; color: var(--sj-ink); }
.mt-sub { font-size: 22rpx; color: var(--sj-sub); }
.me-edit {
  flex: none;
  font-size: 23rpx;
  font-weight: 800;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  padding: 10rpx 24rpx;
  border-radius: var(--sj-r-pill);
}
.me-edit:active { transform: scale(0.94); }

/* ---------- 设置分组（v2 set-group） ---------- */
.set-group {
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-md);
  padding: 12rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: var(--sj-sh-sm);
}
.sg-label {
  display: block;
  font-size: 24rpx;
  font-weight: 800;
  color: var(--sj-faint);
  padding: 16rpx 4rpx 8rpx;
}
.set-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
  padding: 22rpx 4rpx;
  border-top: 2rpx dashed var(--sj-line);
}
.set-row:first-of-type { border-top: none; }
.set-row:active { background: var(--sj-cream); }
.sr-icon {
  width: 68rpx;
  height: 68rpx;
  border-radius: 20rpx;
  background: var(--sj-cream);
  padding: 6rpx;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
/* 图标图片圆角与外圈曲线平行（同心）：外半径 20 - 内边距 6 = 14rpx */
.sr-icon .sj-icon { border-radius: 14rpx; }
.sr-label { flex: 1; min-width: 0; font-size: 27rpx; font-weight: 600; color: var(--sj-ink); }
.sr-desc {
  display: block;
  font-size: 21rpx;
  font-weight: 400;
  color: var(--sj-sub);
  margin-top: 4rpx;
  line-height: 1.5;
}
.sr-val { font-size: 23rpx; color: var(--sj-sub); flex: none; max-width: 320rpx; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.sr-chev { width: 30rpx; height: 30rpx; flex: none; opacity: 0.5; }

/* 状态小标签（v2 set-tag） */
.set-tag {
  font-size: 21rpx;
  font-weight: 800;
  border-radius: var(--sj-r-pill);
  padding: 4rpx 18rpx;
  background: #F0EAFB;
  color: #7A5FB0;
  flex: none;
}
.set-tag.ok { background: #E2F5EA; color: #2E7D4F; }
.set-tag.warn { background: #FFF3C4; color: #B47714; }

/* ---------- 开关（sj-switch 封装，外观对齐 v2）：行内不收缩，沿用原 .switch 的 flex:none ---------- */
.row-sw { flex: none; }

/* ---------- 底部 ---------- */
.scroll-end { text-align: center; font-size: 22rpx; color: var(--sj-faint); padding: 24rpx 0 200rpx; letter-spacing: 4rpx; }

/* ---------- 服务器选择面板列表（sj-popup 底部弹层内） ---------- */
.sv-list {
  max-height: 60vh;
  padding: 8rpx 0 calc(20rpx + env(safe-area-inset-bottom));
}
.sv-item {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 24rpx 40rpx;
  border-bottom: 2rpx solid var(--sj-line);
}
.sv-item:last-child { border-bottom: none; }
.sv-item__main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6rpx; }
.sv-item__name {
  font-size: 28rpx;
  font-weight: 700;
  color: var(--sj-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sv-item__url {
  font-size: 22rpx;
  color: var(--sj-sub);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sv-item__check {
  flex: none;
  font-size: 32rpx;
  font-weight: 900;
  color: var(--sj-primary-deep);
}

/* ---------- 修改密码面板（sj-popup 底部弹层内，字段行外观对齐 v2 pg-field） ---------- */
.pwd-form { padding: 32rpx 40rpx calc(40rpx + env(safe-area-inset-bottom)); }
.pwd-field {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: var(--sj-cream);
  border: 2rpx solid var(--sj-line);
  border-radius: 28rpx;
  padding: 8rpx 28rpx;
  margin-bottom: 24rpx;
}
.pwf-label { flex: none; width: 160rpx; font-size: 27rpx; font-weight: 700; color: var(--sj-sub); }
.pwf-in { flex: 1; min-width: 0; }
.pwd-btn { display: flex; margin-top: 8rpx; }
.pwd-tip { display: block; font-size: 22rpx; color: var(--sj-faint); line-height: 1.5; margin-top: 20rpx; }
</style>
