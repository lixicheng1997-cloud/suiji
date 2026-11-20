<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- P05 登录 · 手机验证：居中布局（吉祥物 pg-ava + display 大标题 + pg-field 输入 + pg-btn 主按钮） -->
    <view class="lg-top" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 72rpx)' }">
      <!-- 品牌吉祥物（pg-ava 圆形氛围位） -->
      <view class="pg-ava">
        <sj-mascot :size="240" />
      </view>
      <text class="lg-name">岁记</text>
      <text class="lg-slogan">记录成长的每一刻</text>
    </view>

    <!-- 手机号登录：上下两个独立表单 —— ①自动获取的本机号码（大字 + 一键登录）；②手动输入手机号（本机 SIM 校验） -->
    <!-- #ifndef MP-WEIXIN -->
    <template v-if="phoneMode">
      <!-- 表单一：自动获取的本机号码（reading 读取中 → ready 主态）；未取到号整卡隐藏，不打扰用户 -->
      <view v-if="phoneState === 'reading' || phoneState === 'ready'" class="lg-card lg-loose">
        <view v-if="phoneState === 'reading'" class="pn-reading">
          <view class="pn-spin"></view>
          <text class="pn-read-t">正在读取你的手机号码…</text>
        </view>
        <template v-else>
          <text class="pn-num-label">本机号码</text>
          <view class="pn-num">
            <text class="pn-head">{{ maskedParts.head }}</text><text class="pn-mask">{{ maskedParts.mask }}</text><text class="pn-tail">{{ maskedParts.tail }}</text>
          </view>
          <view class="pn-carrier">
            <text class="pn-carrier-hl">运营商安全认证</text>
          </view>
          <sj-button
            class="lg-btn"
            block
            size="lg"
            :loading="busy"
            :text="busy ? '处理中…' : '一键登录'"
            @click="oneClick"
          />
          <!-- 其他手机号登录（展开下方手动输入表单）｜密码登录 -->
          <view class="lg-alt-row">
            <view class="lg-alt" hover-class="hover-press" :hover-stay-time="80" @click="showManualForm = true">
              <text class="lg-alt-t">切换其他手机号</text>
            </view>
            <text class="alt-sep"></text>
            <view class="lg-alt" hover-class="hover-press" :hover-stay-time="80" @click="phoneMode = false">
              <text class="lg-alt-t">密码登录</text>
            </view>
          </view>
        </template>
      </view>

      <!-- 表单二：手动输入手机号（本机 SIM 校验登录）。未取到号时常驻；
           取到号时默认收起，经表单一「切换其他手机号」展开 -->
      <view v-if="phoneState === 'manual' || showManualForm" class="lg-card lg-loose" :class="{ 'lg-card2': phoneState === 'reading' || phoneState === 'ready' }">
        <text class="fc-title">手机号登录</text>
        <view class="pg-field pg-field-lg">
          <text class="pf-label">手机号</text>
          <sj-input class="pf-in" v-model="phone" type="number" :maxlength="11" placeholder="11 位手机号" />
        </view>
        <sj-button
          class="lg-btn2"
          block
          size="lg"
          :loading="busy"
          :text="busy ? '处理中…' : '校验本机号码登录'"
          @click="submitPhone"
        />
        <view class="lg-alt-row">
          <view class="lg-alt" hover-class="hover-press" :hover-stay-time="80" @click="phoneMode = false">
            <text class="lg-alt-t">使用账号密码登录</text>
          </view>
        </view>
      </view>
    </template>

    <template v-else>
    <!-- #endif -->
    <!-- 登录 / 注册卡片（v2 白底 surface 圆角卡） -->
    <view class="lg-card">
      <!-- 分段切换（sj-subsection / u-subsection） -->
      <sj-subsection
        class="lg-seg"
        :modelValue="mode === 'login' ? 0 : 1"
        :options="['登录', '注册']"
        @change="onMode"
      />

      <!-- 字段行（v2 pg-field：label + 输入同行，输入交给 sj-input） -->
      <view class="pg-field" :class="{ 'pf-bad': !!usernameErr }">
        <text class="pf-label">账号</text>
        <sj-input class="pf-in" v-model="username" :maxlength="32" placeholder="用户名" />
      </view>
      <!-- 用户名被占用的精准提示：钉在账号行正下方，用户改一个字就消失 -->
      <text v-if="usernameErr" class="pf-hint">{{ usernameErr }}</text>
      <view class="pg-field">
        <text class="pf-label">密码</text>
        <sj-input class="pf-in" v-model="password" :maxlength="64" type="password" placeholder="至少 8 位" />
      </view>
      <view class="pg-field" v-if="mode === 'register'">
        <text class="pf-label">昵称</text>
        <sj-input class="pf-in" v-model="name" :maxlength="16" placeholder="如：妈妈" />
      </view>

      <!-- 主按钮（sj-button 通栏大号；busy 由库拦截重复点击并转圈） -->
      <sj-button
        class="lg-btn"
        block
        size="lg"
        :loading="busy"
        :text="busy ? '处理中…' : (mode === 'login' ? '登 录' : '注册并进入')"
        @click="submit"
      />

      <!-- 手机号登录入口（默认模式即手机号登录；此处仅供从账号密码切回。
           微信小程序不支持号码认证，整块不渲染） -->
      <!-- #ifndef MP-WEIXIN -->
      <template v-if="phoneLoginEnabled">
      <view class="lg-alt" hover-class="hover-press" :hover-stay-time="80" @click="phoneMode = true">
        <text class="lg-alt-t">返回手机号登录</text>
      </view>
      </template>
      <!-- #endif -->
    </view>
    <!-- #ifndef MP-WEIXIN -->
    </template>
    <!-- #endif -->

    <!-- 服务器地址入口：由前端公共配置 config/app.js 的 SHOW_SERVER_PICKER 控制显隐；
         关闭时整行与选择面板都不渲染，地址固定走配置默认项 -->
    <view v-if="showServerPicker" class="lg-server" hover-class="hover-press" :hover-stay-time="80" @click="pickServer">
      <image class="sv-ic" :src="'/static/icons/' + __theme + '/22-fn-backup.png'" />
      <text class="sv-text">数据保存在：{{ server }}</text>
      <text class="sv-edit">切换 ›</text>
    </view>

    <view class="lg-foot"><text>登录即表示同意《隐私政策》与儿童信息保护规则</text></view>

    <!-- 服务器地址选择面板（sj-popup 底部弹层，列表来自前端公共配置 config/app.js） -->
    <sj-popup
      v-if="showServerPicker"
      v-model:show="serverShow"
      mode="bottom"
      title="选择数据保存位置"
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

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import * as guide from '@/utils/first-run.js'
import { requestMediaPermissions, phoneAuthSupported, getOneClickToken, getVerifyToken, prefetchOneClickLogin } from '@/infra/platform.js'
import { SHOW_SERVER_PICKER, PHONE_LOGIN_ENABLED } from '@/config/app.js'

/* 媒体权限主动申请的落本机标记（只问一次，避免每次登录重复弹系统授权框） */
const PERM_ASKED_KEY = 'sj_media_perm_asked'

/* 云端版入口门控页：账号密码换 JWT（契约 §2），成功后 bootstrap 灌缓存，
 * 再按「家庭 → 宝宝档案 → 隐私同意」逐级判定去向（见 first-run.js goAfterLogin）。
 * 手机号登录（阿里云号码认证）：一键登录（SIM 免密）与手机号+本机校验两条链，
 * 账号融合在后端统一（已绑定手机号 → 登录；未绑定 → 自动注册）。 */
export default {
  data() {
    return {
      mode: 'login',
      username: '',
      password: '',
      name: '',
      usernameErr: '',
      busy: false,
      /* 手机号登录：默认即手机号模式（总开关开启时）。表单一（自动取号）phoneState：
       * reading 静默取号中 → ready 主态（大号脱敏号码 + 一键登录）/ manual 未取到号（表单一整体隐藏）；
       * 手动输入由表单二常驻承担；maskedPhone 为服务端预取的脱敏本机号码（ready 态展示） */
      phoneMode: !!PHONE_LOGIN_ENABLED,
      phoneState: 'reading',
      maskedPhone: '',
      /* 取到号后手动输入表单是否展开（表单一「切换其他手机号」触发） */
      showManualForm: false,
      phone: '',
      phoneLoginEnabled: !!PHONE_LOGIN_ENABLED,
      /* 登录页服务器入口开关：来自前端公共配置 config/app.js（0=隐藏，1=展示） */
      showServerPicker: !!SHOW_SERVER_PICKER,
      server: '',
      serverShow: false,
      serverList: [],
      serverUrl: '',
      statusBarHeight: 20
    }
  },

  watch: {
    /* 用户改账号即收回「已被注册」提示，避免旧结论挂在输入框下方误导 */
    username() { this.usernameErr = '' }
  },

  computed: {
    /* 脱敏号拆三段（138 | **** | 8888），中间星号用主色，对齐参考图 */
    maskedParts() {
      const m = this.maskedPhone || ''
      return { head: m.slice(0, 3), mask: m.slice(3, 7), tail: m.slice(7) }
    }
  },

  onLoad() {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
    /* 静默预取本机号码（能力探测 → 取号令牌 → 服务端换脱敏号），驱动手机号卡片状态机 */
    if (this.phoneLoginEnabled) this.prefetchPhone()
    /* 首次启动（本机没选过）：按配置 is_default 落一个默认地址；
     * 入口隐藏时仍需落默认地址，只是不在页面上展示可切换的行 */
    api.pickDefaultServer().then(() => {
      if (!this.showServerPicker) return
      this.server = api.serverLabel()
      this.serverUrl = api.currentServer().url
    })
  },

  methods: {
    /* 分段器下标 → 模式字符串（仅账号密码卡片使用；手机号卡片为独立表单） */
    onMode(index) {
      this.mode = index === 0 ? 'login' : 'register'
      this.usernameErr = ''
    },

    /* 服务器地址：列表来自前端公共配置 config/app.js，用 sj-popup 底部面板选择（不再手输） */
    pickServer() {
      api.fetchServers().then(list => {
        if (!list.length) { this.$refs.ntf.show({ type: 'err', message: '暂时没有可选的保存位置，请稍后再试' }); return }
        this.serverList = list
        this.serverUrl = api.currentServer().url
        this.serverShow = true
      })
    },

    /* 选中某条：落库并探测连通性，随后收起面板 */
    chooseServer(s) {
      api.setServer(s)
      this.server = api.serverLabel()
      this.serverUrl = api.currentServer().url
      this.serverShow = false
      /* 公开端点探测：不可达也保留选择，只是提示一下 */
      api.pingServer().then(ok => {
        this.$refs.ntf.show({ type: ok ? 'ok' : 'warn', message: ok ? '已切换到：' + (s.name || s.url) : '已切换，但暂时连不上，请检查网络' })
      })
    },

    /* 登录成功后主动申请相册/相机/麦克风：系统授权框每台设备只弹一次
     * （标记落本机 Storage）；被拒也不阻断——选图/录音功能层调起时仍会兜底再申请 */
    askMediaPermissions() {
      try {
        if (uni.getStorageSync(PERM_ASKED_KEY)) return
        uni.setStorageSync(PERM_ASKED_KEY, '1')
      } catch (e) { /* 存储不可用时照常申请 */ }
      requestMediaPermissions()
    },

    submit() {
      if (this.busy) return
      const name = this.username.trim()
      const pwd = this.password
      if (!name || !pwd) {
        this.$refs.ntf.show({ type: 'warn', message: '请输入账号和密码' })
        return
      }
      /* 注册侧的强度规则与服务端一致（用户名 ≥3 位、密码 ≥8 位且非纯数字/纯字母），
       * 先本地挡一次，避免每填一次都跑一趟网络才拿到 422 */
      if (this.mode === 'register') {
        if (name.length < 3) { this.$refs.ntf.show({ type: 'warn', message: '用户名至少 3 位' }); return }
        if (pwd.length < 8) { this.$refs.ntf.show({ type: 'warn', message: '密码至少 8 位' }); return }
        if (/^\d+$/.test(pwd) || /^[a-zA-Z]+$/.test(pwd)) { this.$refs.ntf.show({ type: 'warn', message: '密码不能是纯数字或纯字母' }); return }
        if (pwd !== pwd.trim()) { this.$refs.ntf.show({ type: 'warn', message: '密码不能以空格开头或结尾' }); return }
      }
      this.busy = true
      this.usernameErr = ''
      /* 登录后要拉全量 bootstrap（记录/疫苗/日记），慢网下数秒：全屏阻断，
       * 只有按钮转圈会让用户以为卡死而重复点或杀进程 */
      const ld = ui.loading('正在登录…')
      const req = this.mode === 'login'
        ? api.login(name, pwd)
        : api.register(name, pwd, this.name.trim())
      req
        .then(() => {
          ld.update({ text: '正在准备你的成长记录…', sub: '首次进入需要一点时间' })
          return api.bootstrap()
        })
        .then(() => {
          this.busy = false
          ld.close()
          /* 逐级门控：无家庭 → 创建/加入引导页；无档案 → 建档页；未留痕 → 隐私页；否则进首页 */
          guide.goAfterLogin()
          /* 登录成功后主动申请相册/相机/麦克风权限（本机只弹一次） */
          this.askMediaPermissions()
        })
        .catch(e => {
          ld.close()
          this.busy = false
          /* 用户名已被注册：服务端 409 的 detail 就是给用户看的文案，
           * 除了弹出来还要钉回账号行下方——只弹 toast 用户看不出是哪一个字段的问题 */
          if (this.mode === 'register' && e && e.status === 409) {
            this.usernameErr = e.friendly || '该用户名已被注册，请换一个'
            ui.error(e, this.usernameErr)
            return
          }
          ui.error(e, '操作失败，请重试')
        })
    },

    /* ---------- 手机号登录（阿里云号码认证，App/H5；小程序无此入口） ---------- */

    /* 登录成功后的公共收尾：拉全量 bootstrap 灌缓存 → 逐级门控进 App（与 submit 共用口径） */
    _afterLogin(ld) {
      ld.update({ text: '正在准备你的成长记录…', sub: '首次进入需要一点时间' })
      return api.bootstrap()
        .then(() => {
          this.busy = false
          ld.close()
          /* 逐级门控：无家庭 → 创建/加入引导页；无档案 → 建档页；未留痕 → 隐私页；否则进首页 */
          guide.goAfterLogin()
          this.askMediaPermissions()
        })
        .catch(e => {
          ld.close()
          this.busy = false
          ui.error(e, '登录成功但数据加载失败，请重试')
        })
    },

    /* 静默预取本机号码（状态机驱动）：能力探测 → getVerifyToken 静默令牌 →
     * 服务端 /auth/phone/prefetch 换脱敏号 → ready；任一环节失败 → manual 回退手动输入。
     * 预取令牌一次性消费，不影响后续一键登录（getLoginToken 另发新令牌） */
    prefetchPhone() {
      this.phoneState = 'reading'
      phoneAuthSupported().then(ok => {
        if (!ok) { this.phoneState = 'manual'; return }
        /* 提前预取，让一键登录授权页可秒开 */
        prefetchOneClickLogin()
        return getVerifyToken().then(token => {
          if (!token) { this.phoneState = 'manual'; return }
          return api.phonePrefetch(token).then(r => {
            this.maskedPhone = (r && r.masked) || ''
            this.showManualForm = false
            this.phoneState = this.maskedPhone ? 'ready' : 'manual'
          })
        })
      }).catch(() => { this.phoneState = 'manual' })
    },

    /* 一键登录：拉起运营商授权页 → SDK 取号令牌 → 服务端 GetMobile 换手机号 →
     * 已绑定手机号直接登录该账号，未绑定自动注册（融合规则在后端） */
    oneClick() {
      if (this.busy) return
      this.busy = true
      const ld = ui.loading('正在识别本机号码…')
      getOneClickToken().then(token => {
        if (!token) {
          /* 无 SIM / 运营商不支持 / 用户取消：不抛错，引导走其他手机号或账号密码 */
          ld.close()
          this.busy = false
          this.$refs.ntf.show({ type: 'warn', message: '本机号码读取失败，可换个手机号试试，或用账号密码登录' })
          return
        }
        api.phoneOneClick(token)
          .then(() => this._afterLogin(ld))
          .catch(e => {
            ld.close()
            this.busy = false
            ui.error(e, '一键登录失败，请使用账号密码登录')
          })
      })
    },

    /* 手机号 + 本机号码校验登录：输入号必须与本机 SIM 一致（VerifyPhone PASS） */
    submitPhone() {
      if (this.busy) return
      const p = this.phone.trim()
      if (!/^1\d{10}$/.test(p)) {
        this.$refs.ntf.show({ type: 'warn', message: '请输入 11 位手机号' })
        return
      }
      this.busy = true
      const ld = ui.loading('正在校验本机号码…')
      getVerifyToken().then(token => {
        if (!token) {
          ld.close()
          this.busy = false
          this.$refs.ntf.show({ type: 'warn', message: '手机号与本机不一致或校验不可用，请使用账号密码登录' })
          return
        }
        api.phoneVerifyLogin(p, token)
          .then(() => this._afterLogin(ld))
          .catch(e => {
            ld.close()
            this.busy = false
            ui.error(e, '登录失败，请使用账号密码登录')
          })
      })
    }
  }
}
</script>

<style lang="scss" scoped>
/* 页面底：v2 奶油色 + 顶部主色柔光氛围（森林绘本双主题随 themeVars 切换） */
.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;
  min-height: 100vh;
  /* 顶部暖光晕保留，奶油底交给 <sj-bg /> 图层（z-index:-1），根节点不铺不透明色 */
  background: radial-gradient(920rpx 620rpx at 50% 0%, var(--sj-primary-soft), transparent 72%);
  font-family: var(--sj-font-body);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-bottom: 64rpx;
  box-sizing: border-box;
}

/* ---------- 品牌区（pg-ava 吉祥物 + display 大标题） ---------- */
.lg-top {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.pg-ava {
  width: 280rpx;
  height: 280rpx;
  border-radius: 50%;
  background: var(--sj-primary-soft);
  border: 4rpx solid var(--sj-white);
  box-shadow: var(--sj-sh-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.lg-name {
  margin-top: 28rpx;
  font-family: var(--sj-font-display);
  font-size: 56rpx;
  font-weight: 900;
  color: var(--sj-ink);
  letter-spacing: 12rpx;
}
.lg-slogan {
  font-size: 25rpx;
  color: var(--sj-sub);
  margin-top: 12rpx;
  letter-spacing: 4rpx;
}

/* 登录 / 注册卡片（v2：整卡为一块毛玻璃，卡内字段行改用透明底 + 白色细描边，避免玻璃叠玻璃） */
.lg-card {
  width: calc(100% - 96rpx);
  margin-top: 56rpx;
  background: var(--sj-glass);
  border: 2rpx solid var(--sj-glass-line);
  border-radius: var(--sj-r-lg);
  box-shadow: var(--sj-glass-hi), var(--sj-sh-md);
  padding: 40rpx 40rpx 44rpx;
  box-sizing: border-box;
}

/* 手机号双表单布局：表单一（自动取号）与表单二（手动输入）上下叠放，间距收紧一档 */
.lg-card2 { margin-top: 32rpx; }
/* 宽松版卡片：加大内边距，元素间距更舒展（手机号表单专用） */
.lg-loose { padding: 48rpx 44rpx 48rpx; }
.lg-loose .lg-btn { margin-top: 40rpx; }
.lg-loose .lg-btn2 { margin-top: 8rpx; }

/* 独立表单卡片标题（手机号登录卡片） */
.fc-title {
  display: block;
  text-align: center;
  font-family: var(--sj-font-display);
  font-size: 34rpx;
  font-weight: 900;
  color: var(--sj-ink);
  margin-bottom: 28rpx;
}

/* 分段切换（sj-subsection，卡内下沿留白） */
.lg-seg {
  display: block;
  margin-bottom: 32rpx;
}

/* 字段行（v2 pg-field：label + 值同行；卡为玻璃面，故行内透明底 + 白色细描边） */
.pg-field {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background: rgba(255, 255, 255, 0.34);
  border: 2rpx solid rgba(255, 255, 255, 0.55);
  border-radius: 28rpx;
  padding: 16rpx 28rpx;
  margin-bottom: 20rpx;
  font-size: 27rpx;
  transition: border-color 0.2s var(--sj-smooth), background 0.2s var(--sj-smooth);
}
/* 聚焦：底提亮、描边转主色（主色压在玻璃上仍清晰） */
.pg-field:focus-within {
  background: rgba(255, 255, 255, 0.62);
  border-color: var(--sj-primary);
}
/* 账号被占用：描边转红。写在 focus-within 之后，同级特异性才能盖掉聚焦主色 */
.pg-field.pf-bad {
  background: rgba(239, 122, 122, 0.14);
  border-color: var(--sj-bad);
}
.pf-label { color: var(--sj-sub); font-weight: 700; flex: none; width: 140rpx; }
/* 手机号输入行加大版：更高、更圆、字号更大，不紧凑 */
.pg-field-lg {
  padding: 28rpx 34rpx;
  border-radius: 34rpx;
  margin: 36rpx 0 32rpx;
  font-size: 32rpx;
}
/* 字段级错误文案（紧跟出错的行，随用户改动消失） */
.pf-hint {
  display: block;
  margin: -12rpx 12rpx 16rpx 28rpx;
  font-size: 22rpx;
  font-weight: 700;
  line-height: 1.5;
  color: var(--sj-bad);
}
.pf-opt { font-size: 22rpx; color: var(--sj-faint); font-weight: 400; }
/* sj-input 在行内占据剩余宽度 */
.pf-in { flex: 1; min-width: 0; }

/* 主按钮（sj-button lg 通栏，仅补上沿间距） */
.lg-btn {
  display: flex;
  margin-top: 20rpx;
}

/* ---------- 手机号登录状态机 ---------- */
/* ① 读取中：转圈 + 说明 */
.pn-reading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 0 56rpx;
}
.pn-spin {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  border: 6rpx solid var(--sj-primary-soft);
  border-top-color: var(--sj-primary-deep);
  animation: pn-spin 1s linear infinite;
}
@keyframes pn-spin { to { transform: rotate(360deg); } }
.pn-read-t { margin-top: 24rpx; font-size: 25rpx; color: var(--sj-sub); }
/* ② 主态：本机号码大字展示 */
.pn-num-label {
  display: block;
  text-align: center;
  font-size: 23rpx;
  color: var(--sj-sub);
  letter-spacing: 2rpx;
  margin-top: 8rpx;
}
.pn-num {
  display: flex;
  justify-content: center;
  align-items: baseline;
  font-family: var(--sj-font-display);
  font-size: 68rpx;
  font-weight: 900;
  color: var(--sj-ink);
  letter-spacing: 4rpx;
  margin: 16rpx 0 8rpx;
}
/* 中间脱敏星号用主色，前后数字保持墨色（对齐参考图） */
.pn-mask { color: var(--sj-primary-deep); }
.pn-carrier {
  display: flex;
  justify-content: center;
  margin-bottom: 4rpx;
}
.pn-carrier-hl { font-size: 22rpx; color: var(--sj-primary-deep); }
/* 文字链接行（账号密码登录入口） */
.lg-alt-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 24rpx;
  margin-top: 24rpx;
}
.lg-alt-row .lg-alt { margin-top: 0; padding: 8rpx 0; }
/* 双链接行内的入口用灰色常规文字（对齐参考图，主操作仍靠上方大按钮） */
.lg-alt-row .lg-alt .lg-alt-t { color: var(--sj-sub); font-weight: 400; }
.alt-sep { width: 2rpx; height: 24rpx; background: var(--sj-line); flex: none; }
/* 校验本机号码次按钮（plain 描边变体，仅补上沿间距） */
.lg-btn2 {
  display: flex;
  margin-top: 24rpx;
}
/* 文字切换链接（手机号登录 ↔ 账号密码） */
.lg-alt {
  display: flex;
  justify-content: center;
  margin-top: 24rpx;
  padding: 8rpx;
}
.lg-alt-t { font-size: 24rpx; font-weight: 700; color: var(--sj-primary-deep); }

/* ---------- 服务器地址行 ---------- */
.lg-server {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 40rpx;
  padding: 18rpx 32rpx;
  background: var(--sj-surface);
  border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-pill);
  box-shadow: var(--sj-sh-sm);
  max-width: calc(100% - 80rpx);
  box-sizing: border-box;
}
.sv-ic { width: 40rpx; height: 40rpx; flex: none; }
.sv-text {
  font-size: 22rpx;
  color: var(--sj-sub);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}
.sv-edit { font-size: 22rpx; font-weight: 700; color: var(--sj-primary-deep); flex: none; }

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

/* ---------- 合规脚注：贴屏幕底部（页根为 flex 纵向，margin-top:auto 推到底） ---------- */
.lg-foot {
  margin-top: auto;
  padding: 40rpx 0 calc(24rpx + env(safe-area-inset-bottom));
}
.lg-foot text { font-size: 21rpx; color: var(--sj-faint); letter-spacing: 2rpx; }
</style>
