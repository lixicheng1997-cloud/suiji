<!--
  uikit · 控件样式演示页（v2 森林绘本）
  集中展示 sj-* uview-plus 封装控件全家族：开关 / 勾选 / 步进器 / 输入 / 搜索 / 进度 / 空态 / 评分 / 单选 / 滑块 / 分段器 / 标签 / 徽标 / 按钮 / 选项卡 / 通知栏 / 骨架屏 / 环形进度 / 对话框 / 日历 / 图标 / 吉祥物。
  顶部可实时切换 bear/duck 主题，验证全组件换肤。仅演示用途，不写任何业务存储。
-->
<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏 -->
    <view class="uk-head">
      <view class="uk-back" hover-class="hover-press" :hover-stay-time="80" @click="back">
        <image class="uk-back-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <view class="uk-title">
        <text class="ut-main">控件演示</text>
        <text class="ut-sub">sj-* · uview-plus · v2 森林绘本</text>
      </view>
      <view class="uk-theme" hover-class="hover-press" :hover-stay-time="80" @click="switchTheme">
        <sj-mascot :size="40" />
        <text>{{ label }}</text>
      </view>
    </view>

    <!-- 01 基础交互 -->
    <view class="uk-group">
      <text class="ug-label">01 · 基础交互</text>

      <view class="uk-row">
        <text class="ur-name">开关 sj-switch</text>
        <sj-switch :checked="sw1" @change="v => (sw1 = v)" />
      </view>
      <view class="uk-row">
        <text class="ur-name">开关（关）</text>
        <sj-switch :checked="sw2" @change="v => (sw2 = v)" />
      </view>
      <view class="uk-row">
        <text class="ur-name">开关（禁用）</text>
        <sj-switch :checked="true" disabled />
      </view>

      <view class="uk-row">
        <text class="ur-name">勾选 sj-checkbox</text>
        <view class="ur-cks">
          <sj-checkbox :checked="ck1" @change="v => (ck1 = v)" />
          <sj-checkbox :checked="false" @change="() => {}" />
          <sj-checkbox :checked="true" disabled />
        </view>
      </view>
      <view class="uk-row">
        <text class="ur-name">勾选（带 label）</text>
        <sj-checkbox :checked="ck2" label="同意条款" @change="v => (ck2 = v)" />
      </view>

      <view class="uk-row">
        <text class="ur-name">步进器 sj-number-box（ml）</text>
        <sj-number-box v-model="num1" :min="0" :max="999" :step="10" />
      </view>
      <view class="uk-row">
        <text class="ur-name">步进器（小数，cm）</text>
        <sj-number-box v-model="num2" :min="25" :max="60" :step="0.5" />
      </view>
    </view>

    <!-- 02 表单输入 -->
    <view class="uk-group">
      <text class="ug-label">02 · 表单输入</text>

      <view class="uk-field">
        <sj-input v-model="txt" placeholder="单行输入 sj-input（clearable 清除钮）" clearable />
      </view>
      <view class="uk-field">
        <sj-input v-model="fixedTxt" disabled placeholder="禁用输入" />
      </view>
      <view class="uk-field">
        <sj-textarea v-model="memo" placeholder="多行备注 sj-textarea（clearable 清除钮）" :maxlength="200" height="176rpx" clearable />
      </view>
      <view class="uk-field">
        <sj-search v-model="q" placeholder="搜索控件 sj-search（含语音钮）" voice @search="onSearch" @clear="onClear" @voice="onVoice" />
      </view>
    </view>

    <!-- 03 反馈展示 -->
    <view class="uk-group">
      <text class="ug-label">03 · 反馈展示</text>

      <text class="ur-name ug-tip">进度条 sj-progress（点步进器联动）</text>
      <sj-progress :percent="num1 / 10" :height="10" />
      <view class="uk-row">
        <text class="ur-name">percent = {{ Math.round(num1 / 10) }}%</text>
        <view class="ur-inline">
          <sj-number-box v-model="num1" :min="0" :max="999" :step="10" />
        </view>
      </view>

      <text class="ur-name ug-tip">空态 sj-empty</text>
      <view class="uk-empty-box">
        <sj-empty text="这里空空如也" sub="缺省 ctl-v2 空态切图 · 随主题切换" />
      </view>
    </view>

    <!-- 04 第一批新控件 -->
    <view class="uk-group">
      <text class="ug-label">04 · 第一批新控件</text>

      <text class="ur-name ug-tip">评分 sj-rate</text>
      <view class="uk-row">
        <text class="ur-name">可交互（{{ rate1 }} / 5）</text>
        <sj-rate v-model="rate1" :size="22" />
      </view>
      <view class="uk-row">
        <text class="ur-name">禁用（固定 3 心）</text>
        <sj-rate :model-value="3" disabled />
      </view>

      <text class="ur-name ug-tip">单选 sj-radio（三枚共享一个 v-model）</text>
      <view class="uk-row">
        <text class="ur-name">当前 = {{ radioVal }}</text>
        <view class="ur-inline">
          <sj-radio v-model="radioVal" name="A" label="A" />
          <sj-radio v-model="radioVal" name="B" label="B" />
          <sj-radio v-model="radioVal" name="C" label="C" />
        </view>
      </view>

      <text class="ur-name ug-tip">滑块 sj-slider（右侧自带值文本）</text>
      <view class="uk-row">
        <text class="ur-name">体温 35–42℃</text>
        <view class="ur-slider">
          <sj-slider v-model="tempVal" :min="35" :max="42" :step="0.1" :decimals="1" unit=" ℃" />
        </view>
      </view>
      <view class="uk-row">
        <text class="ur-name">普通 0–100</text>
        <view class="ur-slider">
          <sj-slider v-model="pctVal" :min="0" :max="100" :step="1" unit="%" />
        </view>
      </view>

      <text class="ur-name ug-tip">分段器 sj-subsection（v-model = 下标，当前 {{ segIdx }}）</text>
      <view class="uk-seg">
        <sj-subsection v-model="segIdx" :options="['日', '周', '月']" />
      </view>

      <text class="ur-name ug-tip">选择器 sj-datetime-picker（点触发文案弹滚轮，change 回写）</text>
      <view class="uk-row">
        <text class="ur-name">日期 / 时间</text>
        <view class="ur-inline">
          <sj-datetime-picker mode="date" :value="pickDate" @change="onPickDate">
            <text class="ur-unit">{{ pickDate }} ▾</text>
          </sj-datetime-picker>
          <sj-datetime-picker mode="time" :value="pickTime" @change="onPickTime">
            <text class="ur-unit">{{ pickTime }} ▾</text>
          </sj-datetime-picker>
        </view>
      </view>

      <text class="ur-name ug-tip">标签 sj-tag（default/soft/plain/ok/warn/err/pill + mini）</text>
      <view class="uk-tags">
        <sj-tag text="default" />
        <sj-tag text="soft" variant="soft" />
        <sj-tag text="plain" variant="plain" />
        <sj-tag text="ok" variant="ok" />
        <sj-tag text="warn" variant="warn" />
        <sj-tag text="err" variant="err" />
        <sj-tag text="类别色" variant="pill" bg="#FFE7EE" color="#D9568A" />
        <sj-tag text="mini" variant="soft" size="mini" />
        <sj-tag text="标签" variant="soft" icon="42-ctl-tag" />
        <sj-tag text="筛选" variant="pill" icon="43-ctl-tag-filter" />
      </view>

      <text class="ur-name ug-tip">徽标 sj-badge（包裹宿主图标）</text>
      <view class="uk-badges">
        <sj-badge :value="5"><sj-icon name="25-fn-notify" :size="72" /></sj-badge>
        <sj-badge dot><sj-icon name="25-fn-notify" :size="72" /></sj-badge>
        <sj-badge :value="120" :max="99"><sj-icon name="25-fn-notify" :size="72" /></sj-badge>
      </view>
    </view>

    <!-- 05 第二批新控件 -->
    <view class="uk-group">
      <text class="ug-label">05 · 第二批新控件</text>

      <text class="ur-name ug-tip">按钮 sj-button（六变体 + icon 前置 ctl 切图）</text>
      <view class="uk-tags">
        <sj-button text="主按钮" variant="primary" />
        <sj-button text="描边" variant="plain" />
        <sj-button text="浅底" variant="light" />
        <sj-button text="中性" variant="ghost" />
        <sj-button text="文字" variant="text" />
        <sj-button text="危险" variant="danger" />
        <sj-button text="确认" icon="40-ctl-btn-confirm" />
        <sj-button text="添加" variant="light" icon="41-ctl-btn-add" />
      </view>

      <text class="ur-name ug-tip">按钮（mini / loading 点一下 2 秒自动关 / 禁用 / block 通栏）</text>
      <view class="uk-tags">
        <sj-button text="mini" size="mini" />
        <sj-button text="mini 危险" size="mini" variant="danger" />
        <sj-button :text="btnLoading ? '加载中' : '点击加载'" :loading="btnLoading" @click="onBtnLoading" />
        <sj-button text="禁用" disabled />
      </view>
      <view class="uk-block">
        <sj-button block variant="plain" text="通栏 sj-button block" />
      </view>

      <text class="ur-name ug-tip">选项卡 sj-tabs（v-model = 下标）</text>
      <sj-tabs :items="tabItems" v-model="tabIdx" />
      <text class="ur-unit ug-tip">当前下标 = {{ tabIdx }}（{{ tabItems[tabIdx] }}）</text>

      <text class="ur-name ug-tip">通知栏 sj-notify（页面尾部挂一处实例，$refs 方法调用）</text>
      <view class="uk-tags">
        <sj-button text="ok" variant="light" size="mini" @click="onNotify('ok')" />
        <sj-button text="warn" variant="light" size="mini" @click="onNotify('warn')" />
        <sj-button text="err" variant="light" size="mini" @click="onNotify('err')" />
      </view>

      <text class="ur-name ug-tip">骨架屏 sj-skeleton（rows=3 + avatar，切换显真实内容）</text>
      <view class="uk-row">
        <text class="ur-name">skelOn = {{ skelOn }}</text>
        <sj-button text="刷新骨架" variant="plain" size="mini" @click="skelOn = !skelOn" />
      </view>
      <view class="uk-skel-box">
        <sj-skeleton :loading="skelOn" :rows="3" :rowsHeight="['128rpx', '88rpx', '176rpx']" :avatar="true">
          <view class="uk-skel-card">
            <text class="ur-name">宝宝记录卡 · 真实内容 slot</text>
            <text class="ur-unit">2026-10-27 · 体重 12.4 kg · 身高 88 cm</text>
            <text class="ur-unit">sj-skeleton 在 loading=false 时渲染本 slot</text>
          </view>
        </sj-skeleton>
      </view>

      <text class="ur-name ug-tip">环形进度 sj-circle-progress（与第一批 sj-progress 呼应）</text>
      <view class="uk-rings">
        <view class="uk-ring-item">
          <sj-circle-progress :percent="72" :size="74" :stroke-width="9" />
          <text class="ur-unit">默认中心文本</text>
        </view>
        <view class="uk-ring-item">
          <sj-circle-progress :percent="75" :size="74" :stroke-width="9">
            <text class="uk-ring-custom">9/12</text>
          </sj-circle-progress>
          <text class="ur-unit">slot 自定义中心</text>
        </view>
      </view>

      <text class="ur-name ug-tip">对话框 sj-modal（v-model:show，三实例放页面尾部）</text>
      <view class="uk-tags">
        <sj-button text="危险确认" variant="danger" size="mini" @click="mdDanger = true" />
        <sj-button text="信息单按钮" variant="plain" size="mini" @click="mdInfo = true" />
        <sj-button text="自定义内容" variant="light" size="mini" @click="mdCustom = true" />
      </view>

      <text class="ur-name ug-tip">日历 sj-calendar（single/range 弹层，confirm = 库原样日期数据）</text>
      <view class="uk-tags">
        <sj-button text="单选日期" variant="plain" size="mini" @click="calShowSingle = true" />
        <sj-button text="区间日期" variant="plain" size="mini" @click="calShowRange = true" />
      </view>
      <text v-if="calResult" class="ur-unit ug-tip">已选：{{ calResult }}</text>

      <text class="ur-name ug-tip">全屏加载动画 sj-loading（IP 主图标 + 进度，3.2 秒自动关闭演示）</text>
      <view class="uk-tags">
        <sj-button text="打开全屏 loading" variant="plain" size="mini" @click="onLoadingDemo" />
        <sj-button text="ui.loading() 全局通道" variant="plain" size="mini" @click="onLoadingChannel" />
      </view>
    </view>

    <!-- 05.5 第三批新控件（对齐 v2 components.html 头像 / 选择器 / 步骤条 / 单元格 / 顶部导航卡） -->
    <view class="uk-group">
      <text class="ug-label">05.5 · 第三批新控件</text>

      <text class="ur-name ug-tip">通用选择器 sj-picker（单列 · confirm = 文案 + 索引 + 原始条目）</text>
      <view class="uk-tags">
        <sj-picker :columns="feedCols" title="喂养方式" @confirm="onPickFeed">
          <sj-button :text="feedText || '喂养方式 ▾'" variant="plain" size="mini" />
        </sj-picker>
      </view>

      <text class="ur-name ug-tip">通用选择器 sj-picker（双列联动演示 · 出生年 / 月）</text>
      <view class="uk-tags">
        <sj-picker :columns="ymCols" :default-index="ymIdx" title="出生年月" @confirm="onPickYm">
          <sj-button :text="ymText || '出生年月 ▾'" variant="light" size="mini" />
        </sj-picker>
      </view>

      <text class="ur-name ug-tip">头像 sj-avatar（图片 / 角色占位 / 主题图标 / 昵称首字 / 方形 / 描边变体 / 徽标）</text>
      <view class="uk-avs">
        <sj-avatar :url="avaUrl" />
        <sj-avatar />
        <sj-avatar icon="29-fn-babies" themed ring="g2" />
        <sj-avatar icon="13-tab-me" themed ring="g3" />
        <sj-avatar text="安安" />
        <sj-avatar icon="04-photo" themed shape="square" />
        <sj-badge :value="3"><sj-avatar icon="25-fn-notify" themed /></sj-badge>
        <sj-badge dot><sj-avatar icon="27-fn-trash" themed /></sj-badge>
      </view>

      <text class="ur-name ug-tip">头像重叠组 sj-avatar-group（family 成员 + more 计数位）</text>
      <view class="uk-avs">
        <sj-avatar-group :more="2">
          <sj-avatar icon="29-fn-babies" themed overlap />
          <sj-avatar icon="13-tab-me" themed ring="g2" overlap />
          <sj-avatar icon="28-fn-invite" themed ring="g3" overlap />
        </sj-avatar-group>
        <text class="ur-unit">家庭空间 · 5 位成员</text>
      </view>

      <text class="ur-name ug-tip">步骤条 sj-steps（done 绿✓ / now 主色呼吸 / 未到灰；点标签前进）</text>
      <sj-steps :current="stCurrent" :items="stItems" @click="onStepAdv" />

      <text class="ur-name ug-tip">单元格 sj-cell（右值 / tag / 开关 / 徽标 / 危险项；点击 toast 演示）</text>
      <view class="uk-cells">
        <sj-cell icon="29-fn-babies" title="宝宝档案" value="安安 · 8月12天" @click="onCellToast('宝宝档案')" />
        <sj-cell icon="22-fn-backup" title="云端备份" value="今日 08:30 已同步" tag="正常" @click="onCellToast('云端备份')" />
        <sj-cell icon="30-fn-elder" title="长辈模式" :show-switch="true" v-model:checked="elderOn" />
        <sj-cell icon="27-fn-trash" title="回收站" value="3 条待清理" :danger-value="true" @click="onCellToast('回收站')" />
        <sj-cell icon="25-fn-notify" title="消息通知" :badge="12" @click="onCellToast('消息通知')" />
        <sj-cell icon="27-fn-trash" title="删除全部本地数据" danger @click="onCellToast('删除全部本地数据')" />
      </view>

      <text class="ur-name ug-tip">顶部导航 sj-navbar（晨光渐变 + 圆形返回钮 + #right 插槽；页内预览形态）</text>
      <view class="uk-navbar-box">
        <sj-navbar title="成长曲线" :back="false">
          <template #right>
            <sj-badge dot><image class="uk-nb-ic" src="/static/icons/25-fn-notify.png" /></sj-badge>
          </template>
        </sj-navbar>
      </view>
    </view>

    <!-- 06 品牌资源 -->
    <view class="uk-group">
      <text class="ug-label">06 · 品牌资源</text>
      <view class="uk-icons">
        <view class="uk-ic-item" v-for="n in iconNames" :key="n">
          <sj-icon :name="n" :size="72" />
          <text>{{ n }}</text>
        </view>
      </view>
      <view class="uk-mascots">
        <sj-mascot :size="200" />
        <text class="ur-unit">sj-mascot · 眨眼/浮动动画</text>
      </view>
    </view>

    <view class="scroll-end"><text>· 全组件随 bear / duck 实时换肤 ·</text></view>

    <!-- 第二批弹层组件（fixed 定位不占布局）：通知栏一处 / 对话框三实例 / 日历两实例 -->
    <sj-notify ref="ntf" />

    <sj-modal
      v-model:show="mdDanger"
      icon="danger"
      danger
      title="确认删除这条记录吗？"
      content="删除后将进入回收站，30 天内可恢复。"
      confirm-text="删除"
      cancel-text="取消"
      @confirm="onMdDanger"
    />
    <sj-modal
      v-model:show="mdInfo"
      icon="info"
      title="数据已同步到云端"
      content="本次共上传 128 条本地记录，同步已完成。"
      confirm-text="知道了"
      @confirm="onMdInfo"
    />
    <sj-modal
      v-model:show="mdCustom"
      icon="ok"
      title="提醒设置"
      confirm-text="保存"
      cancel-text="取消"
      @confirm="onMdCustom"
    >
      <view class="uk-row">
        <text class="ur-name">疫苗接种提醒</text>
        <sj-checkbox :checked="ck3" @change="v => (ck3 = v)" />
      </view>
      <view class="uk-row">
        <text class="ur-name">生长曲线异常提醒</text>
        <sj-checkbox :checked="ck4" @change="v => (ck4 = v)" />
      </view>
    </sj-modal>

    <sj-calendar :show="calShowSingle" mode="single" @confirm="onCalConfirm" @close="calShowSingle = false" />
    <sj-calendar :show="calShowRange" mode="range" @confirm="onCalConfirm" @close="calShowRange = false" />
    <!-- 全屏加载动画（IP 主图标 + 进度副文案，设计稿见 suiji-loading-fullscreen/） -->
    <sj-loading
      :show="ldOn"
      text="正在同步云端…"
      :sub="'已同步 ' + Math.round(ldPct * 0.34) + ' / 34 条'"
      :percent="ldPct"
    />

    <sj-ui-host />
  </view>
</template>

<script>
import * as ui from '@/utils/ui.js'
import { THEME_LABELS } from '@/theme/theme.js'

export default {
  data() {
    return {
      /* 01 基础交互 */
      sw1: true,
      sw2: false,
      ck1: true,
      ck2: false,
      num1: 120,
      num2: 50,
      /* 02 表单输入 */
      txt: '',
      fixedTxt: '禁用输入演示',
      memo: '',
      q: '',
      /* 04 第一批新控件（全部本地演示态，不写业务存储） */
      rate1: 2,
      radioVal: 'A',
      tempVal: 36.8,
      pctVal: 60,
      segIdx: 0,
      pickDate: '2026-10-27',
      pickTime: '14:30',
      /* 05 第二批新控件（全部本地演示态，不写业务存储） */
      btnLoading: false,
      tabItems: ['体重', '身高', '头围'],
      tabIdx: 0,
      skelOn: true,
      ck3: true,
      ck4: false,
      mdDanger: false,
      mdInfo: false,
      mdCustom: false,
      calShowSingle: false,
      calShowRange: false,
      calResult: '',
      /* 全屏加载动画演示显隐（3.2 秒自动关）与演示进度 */
      ldOn: false,
      ldPct: 0,
      ldTimer: null,
      /* 05.5 第三批新控件（全部本地演示态，不写业务存储） */
      feedCols: ['母乳', '配方奶', '辅食'].map(t => ({ text: t, id: t })),
      feedText: '',
      ymCols: [[2024, 2025, 2026].map(y => y + '年'), ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']],
      ymIdx: [2, 9],
      ymText: '',
      avaUrl: '/static/icons/bear/29-fn-babies.png',
      stCurrent: 2,
      stItems: ['创建家庭', '监护人同意', '宝宝信息', '开始记录'],
      elderOn: false,
      /* 06 品牌资源 */
      iconNames: ['01-feeding', '03-milestone', '05-measure', '10-tab-home', '24-fn-search', '30-fn-elder']
    }
  },
  computed: {
    label() {
      return THEME_LABELS[this.__theme]
    }
  },
  methods: {
    back() {
      uni.navigateBack()
    },
    /* 演示页内直接换肤：全局混入 toggleTheme + 广播驱动重渲染 */
    switchTheme() {
      this.toggleTheme()
      this.$refs.ntf.show({ type: 'ok', message: '已切换到「' + THEME_LABELS[this.__theme] + '」' })
    },
    onSearch() {
      this.$refs.ntf.show({ type: 'ok', message: 'search 事件：' + (this.q || '(空)') })
    },
    onClear() {
      this.$refs.ntf.show({ type: 'ok', message: 'clear 事件' })
    },
    onVoice() {
      this.$refs.ntf.show({ type: 'warn', message: '语音搜索：功能开发中（演示）' })
    },
    /* ===== 05 第二批新控件演示 ===== */
    /* loading 按钮：点击置 loading，2 秒自动恢复（库在 loading 中拦截重复点击） */
    onBtnLoading() {
      if (this.btnLoading) return
      this.btnLoading = true
      setTimeout(() => { this.btnLoading = false }, 2000)
    },
    /* 通知栏：三语义 ok/warn/err，经 ref 方法调用 sj-notify.show */
    onNotify(type) {
      const msgs = { ok: '保存成功（演示）', warn: '请检查输入（演示）', err: '操作失败（演示）' }
      this.$refs.ntf.show({ type, message: msgs[type], duration: 2500 })
    },
    /* 选择器 change：{ detail: { value } } 负载回写演示值（与原生 picker 处理签名兼容） */
    onPickDate(e) {
      this.pickDate = e.detail.value
    },
    onPickTime(e) {
      this.pickTime = e.detail.value
    },
    onMdDanger() {
      this.$refs.ntf.show({ type: 'ok', message: '已删除（演示）' })
    },
    onMdInfo() {
      this.$refs.ntf.show({ type: 'ok', message: '知道了（演示）' })
    },
    onMdCustom() {
      this.$refs.ntf.show({ type: 'ok', message: '设置已保存（演示）' })
    },
    /* 日历 confirm：库原样日期数据 → 展示文本 + toast；父页面负责关闭弹层 */
    onCalConfirm(dates) {
      this.calResult = this.formatCal(dates)
      this.calShowSingle = false
      this.calShowRange = false
      this.$refs.ntf.show({ type: 'ok', message: '已选日期（演示）' })
    },
    /* 兼容对象数组（u-calendar 原样载荷）与字符串数组两种形态 */
    formatCal(dates) {
      const arr = Array.isArray(dates) ? dates : [dates]
      return arr.filter(Boolean).map(d => (d && d.date) ? d.date : String(d)).join(' → ')
    },
    /* 全屏加载动画演示：打开后进度递增，3.2 秒自动关闭 */
    onLoadingDemo() {
      clearInterval(this.ldTimer)
      this.ldPct = 0
      this.ldOn = true
      this.ldTimer = setInterval(() => {
        this.ldPct = Math.min(100, this.ldPct + 7)
      }, 200)
      setTimeout(() => {
        clearInterval(this.ldTimer)
        this.ldOn = false
      }, 3200)
    },
    /* 全局调用通道：页面不铺 <sj-loading> 标签，改由 ui.loading() 经 <sj-ui-host> 渲染。
     * 业务页一律走这条（见 utils/ui.js 的 loading / 句柄 update / close）。 */
    onLoadingChannel() {
      clearInterval(this.ldTimer)
      const ld = ui.loading('正在同步云端…', { percent: 0 })
      let pct = 0
      this.ldTimer = setInterval(() => {
        pct = Math.min(100, pct + 7)
        ld.update({ percent: pct, sub: '已同步 ' + Math.round(pct * 0.34) + ' / 34 条' })
      }, 200)
      setTimeout(() => { clearInterval(this.ldTimer); ld.close() }, 3200)
    },
    /* ===== 05.5 第三批新控件演示 ===== */
    /* sj-picker 单列：confirm 载荷 { value, index, items }，items 取回对象条目（含 id） */
    onPickFeed(e) {
      const it = e.items[0]
      this.feedText = (it && it.text) || e.value[0] || ''
      this.$refs.ntf.show({ type: 'ok', message: '喂养方式：' + this.feedText + '（id=' + (it && it.id) + '，演示）' })
    },
    /* sj-picker 双列：多列文案以「 / 」拼接 */
    onPickYm(e) {
      this.ymText = e.value.join(' / ')
      this.ymIdx = e.index
      this.$refs.ntf.show({ type: 'ok', message: '出生年月：' + this.ymText + '（演示）' })
    },
    /* sj-steps：点节点推进当前步（0..items-1 循环） */
    onStepAdv(i) {
      this.stCurrent = (this.stCurrent + 1) % this.stItems.length
    },
    onCellToast(name) {
      this.$refs.ntf.show({ type: 'ok', message: '进入「' + name + '」（演示）' })
    }
  }
}
</script>

<style scoped>
.page {
  /* 建立层叠上下文：z-index:-1 的 <sj-bg /> 需沉在本层内，否则会被 uni-page-body 的不透明底色盖住 */
  position: relative;
  z-index: 0;
  min-height: 100vh;
  /* 背景交给 <sj-bg /> 图层（z-index:-1），根节点必须透明否则遮住光斑 */
  background: transparent;
  padding: 0 32rpx;
  box-sizing: border-box;
}

/* 顶栏 */
.uk-head { display: flex; align-items: center; gap: 16rpx; padding: 24rpx 0 20rpx; }
.uk-back {
  width: 68rpx; height: 68rpx; border-radius: 50%;
  background: var(--sj-surface); border: 2rpx solid var(--sj-line);
  display: flex; align-items: center; justify-content: center; flex: none;
}
.uk-back-ic { width: 32rpx; height: 32rpx; }
.uk-title { flex: 1; display: flex; flex-direction: column; }
.ut-main { font-size: 40rpx; font-weight: 900; color: var(--sj-ink); }
.ut-sub { font-size: 22rpx; color: var(--sj-sub); }
.uk-theme {
  display: flex; align-items: center; gap: 8rpx; flex: none;
  padding: 12rpx 24rpx; border-radius: var(--sj-r-pill);
  background: var(--sj-primary-soft);
  font-size: 24rpx; font-weight: 800; color: var(--sj-primary-deep);
}

/* 分组卡 */
.uk-group {
  background: var(--sj-surface); border: 2rpx solid var(--sj-line);
  border-radius: var(--sj-r-lg); padding: 28rpx; margin-bottom: 28rpx;
  box-shadow: var(--sj-sh-sm);
}
.ug-label {
  display: block; font-size: 26rpx; font-weight: 900; letter-spacing: 2rpx;
  color: var(--sj-primary-deep); margin-bottom: 20rpx;
}
.ug-tip { display: block; margin: 20rpx 0 12rpx; }

/* 行 */
.uk-row {
  display: flex; align-items: center; justify-content: space-between;
  min-height: 88rpx; border-bottom: 2rpx dashed var(--sj-line);
}
.uk-row:last-child { border-bottom: none; }
.ur-name { font-size: 27rpx; font-weight: 700; color: var(--sj-ink); }
.ur-cks { display: flex; align-items: center; gap: 28rpx; }
.ur-inline { display: flex; align-items: center; gap: 12rpx; }
.ur-unit { font-size: 24rpx; color: var(--sj-sub); font-weight: 700; }
/* 滑块行：sj-slider 根节点 width:100%，行内用弹性容器限宽占位 */
.ur-slider { flex: 1; margin-left: 24rpx; }

/* 分段器（整宽展示） */
.uk-seg { padding: 8rpx 0 4rpx; }

/* 标签一排（自动换行） */
.uk-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 16rpx; }

/* 徽标行：留出徽标右上溢出空间（top -12rpx / right -20rpx） */
.uk-badges { display: flex; align-items: center; gap: 64rpx; padding: 16rpx 24rpx 8rpx 0; }

/* 通栏按钮行（按钮一排复用 .uk-tags 自动换行） */
.uk-block { padding-top: 8rpx; }

/* 骨架屏演示盒（虚线容器，同空态盒规格） */
.uk-skel-box {
  border: 2rpx dashed var(--sj-line); border-radius: var(--sj-r-md);
  padding: 24rpx; margin-top: 4rpx;
}
.uk-skel-card { display: flex; flex-direction: column; gap: 12rpx; }

/* 环形进度并排 */
.uk-rings { display: flex; align-items: flex-start; gap: 48rpx; padding: 8rpx 0; }
.uk-ring-item { display: flex; flex-direction: column; align-items: center; gap: 12rpx; }
/* slot 自定义中心文本：对齐组件默认百分比形态（display 字体 primary-deep 特粗） */
.uk-ring-custom {
  font-family: var(--sj-font-display); font-size: 30rpx; font-weight: 900;
  color: var(--sj-primary-deep);
}

/* 表单域 */
.uk-field { margin-bottom: 24rpx; }
.uk-field:last-child { margin-bottom: 0; }

/* 空态容器 */
.uk-empty-box {
  border: 2rpx dashed var(--sj-line); border-radius: var(--sj-r-md);
  padding: 20rpx 0;
}

/* 图标网格 */
.uk-icons { display: flex; flex-wrap: wrap; gap: 24rpx; }
.uk-ic-item {
  width: 200rpx; display: flex; flex-direction: column; align-items: center; gap: 8rpx;
  background: var(--sj-cream); border-radius: var(--sj-r-md); padding: 20rpx 0;
}
.uk-ic-item text { font-size: 20rpx; color: var(--sj-faint); }
.uk-mascots {
  display: flex; flex-direction: column; align-items: center; gap: 12rpx;
  padding-top: 28rpx;
}

/* 05.5 第三批：头像行 / 单元格列 / 导航页内预览框 */
.uk-avs { display: flex; flex-wrap: wrap; align-items: center; gap: 20rpx; margin: 8rpx 0 24rpx; }
.uk-cells { display: flex; flex-direction: column; gap: 16rpx; margin: 8rpx 0 24rpx; }
.uk-navbar-box {
  border: 2rpx solid var(--sj-line); border-radius: var(--sj-r-md);
  overflow: hidden; margin: 8rpx 0 8rpx;
}
.uk-nb-ic { width: 44rpx; height: 44rpx; display: block; }

.scroll-end { text-align: center; font-size: 22rpx; color: var(--sj-faint); padding: 24rpx 0 40rpx; letter-spacing: 4rpx; }
</style>
