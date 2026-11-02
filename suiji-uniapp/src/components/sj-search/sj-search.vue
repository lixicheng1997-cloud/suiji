<template>
  <view class="sj-sc">
    <!-- 搜索交互交给 uview-plus u-search（内置放大镜图标/清除按钮/键盘搜索键由库保证） -->
    <u-search
      :modelValue="modelValue"
      :placeholder="placeholder"
      shape="round"
      bgColor="rgba(255,253,251,.72)"
      borderColor="rgba(255,255,255,.72)"
      searchIconColor="#C7B6A8"
      color="#5B4636"
      placeholderColor="#C7B6A8"
      :showAction="false"
      :clearabled="false"
      @update:modelValue="onInput"
      @search="onSearch"
      @clear="onClear"
    >
      <!-- 右缘按钮（inputRight 插槽）：清除钮（有内容时）+ 语音钮（voice=true 时），
           均为 ctl-v2 去底切图 48rpx；库自带 close-circle 清除已禁用 -->
      <template #inputRight>
        <image v-if="modelValue" class="sc-btn" :src="clearSrc" mode="aspectFit" @click="onClearTap" />
        <image v-if="voice" class="sc-btn" :src="voiceSrc" mode="aspectFit" @click="$emit('voice')" />
      </template>
    </u-search>
  </view>
</template>

<script>
/**
 * 岁记 · 搜索框（uview-plus u-search 封装，easycom 自动注册）
 * 外观严格对齐 v2 搜索字段观感（.pg-field tokens，styles.css L569-573）：毛玻璃底（半透暖白）+
 * 2rpx line 边 + 圆角 14px→28rpx（库 shape=round 内联 100px，经 .sj-sc 命名空间 !important 覆盖）
 * + 文字 ink 800、字号 13.5px→27rpx + 占位 faint、faint 放大镜；
 * 右侧 action 按钮不显示（showAction=false）。
 * surface/line/faint/ink 双主题相同，色值直接写死经 props 传入。
 * 事件按契约收敛：update:modelValue(字符串) / search() / clear()（库 search 载荷的
 * 关键字不透传，页面直接读 v-model 值即可）。
 * 右缘控件：库自带清除已禁用（clearabled=false），改用 ctl-v2 去底切图 ——
 * 清除 48-ctl-clear（有内容时）、语音 49-ctl-search-voice（voice=true 时，点击 emit voice），
 * 48rpx，scripts/cut-ctl-icons.py 生成到 /static/icons/ctl/{theme}/48/。
 * 用法：<sj-search v-model="kw" placeholder="搜索记录…" @search="doSearch" @clear="kw = ''" />
 *       <sj-search v-model="kw" voice @voice="onVoice" />
 */
export default {
  name: 'SjSearch',
  props: {
    /* 当前关键字（v-model） */
    modelValue: { type: String, default: '' },
    /* 占位文案 */
    placeholder: { type: String, default: '' },
    /* 显示语音搜索钮（点击 emit voice，功能由页面实现） */
    voice: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'search', 'clear', 'voice'],
  computed: {
    /* 当前主题下的切图路径（彩色绘本图，不走 color 重染） */
    clearSrc() {
      return `/static/icons/ctl/${this.__theme}/48/48-ctl-clear.png`
    },
    voiceSrc() {
      return `/static/icons/ctl/${this.__theme}/48/49-ctl-search-voice.png`
    }
  },
  methods: {
    /* u-search 的 update:modelValue 载荷即字符串值，直接透传 */
    onInput(val) {
      this.$emit('update:modelValue', val)
    },
    /* 键盘「搜索」键确认（库载荷为当前值，按契约不带负载转发） */
    onSearch() {
      this.$emit('search')
    },
    /* 点击清除切图：回写空串并通知页面 */
    onClearTap() {
      this.$emit('update:modelValue', '')
      this.$emit('clear')
    },
    /* 库清除事件保留透传（clearabled=false 后实际不再触发，兼容页面旧绑定） */
    onClear() {
      this.$emit('clear')
    }
  }
}
</script>

<style lang="scss" scoped>
/* 外层包裹：占满父容器宽度 */
.sj-sc {
  width: 100%;
}
/* 右缘切图按钮（48rpx，切图自带约 11% 留白） */
.sc-btn {
  width: 48rpx;
  height: 48rpx;
  margin-left: 12rpx;
  flex: none;
}
</style>

<style lang="scss">
/* ============ 非 scoped：以 .sj-sc 命名空间微调 u-search 内部节点 ============ */
.sj-sc {
  /* 容器圆角：v2 表单域 14px→28rpx（压过库 shape=round 的内联 100px 胶囊） */
  .u-search__content {
    border-radius: 28rpx !important;
    /* 毛玻璃（性能版）：底色经 bgColor 内联为半透，顶沿内高光，不做背景模糊 */
    box-shadow: var(--sj-glass-hi), var(--sj-sh-sm);
  }
  /* 输入文字：v2 表单域 27rpx ink 特粗（库默认 14px） */
  .u-search__content__input {
    font-size: 27rpx !important;
    font-weight: 800;
  }
}
</style>
