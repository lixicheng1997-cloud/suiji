<!--
  sj-photo-bg · 图片版全局氛围背景（与 sj-bg 用法一致，可互换）
  用法：<sj-photo-bg ip="pony" page="home" />   放在页面根节点第一个子节点，根节点背景保持 transparent。
  资源：src/static/backgrounds/{ip}/{page}.jpg（1440×2560，来自 suiji-page-backgrounds/app/）
  说明：本文件是新增组件，不替换也不修改既有 sj-bg；两者都可用 v-if 按主题切换。
-->
<template>
  <view class="sj-photo-bg" :style="style" />
</template>

<script>
export default {
  name: 'SjPhotoBg',
  props: {
    ip: { type: String, default: 'bear' },      // bear | duck | pony
    page: { type: String, required: true },     // home | grow | family | me | splash
    blur: { type: Boolean, default: false }     // 低端机可关掉模糊，直接压暗
  },
  computed: {
    style() {
      const url = `/static/backgrounds/${this.ip}/${this.page}.jpg`;
      return {
        backgroundImage: `url(${url})`,
        filter: this.blur ? 'blur(2px) brightness(1.02)' : 'none'
      };
    }
  }
};
</script>

<style scoped>
.sj-photo-bg {
  position: fixed;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: -1;
  overflow: hidden;
  pointer-events: none;
  background-color: var(--sj-cream);
  background-size: cover;
  background-position: center top;
  background-repeat: no-repeat;
}
</style>
