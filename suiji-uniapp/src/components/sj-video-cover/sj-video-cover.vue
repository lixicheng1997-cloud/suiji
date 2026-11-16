<template>
  <!-- 有封面图：铺满；无封面：暖灰占位底，避免 App 原生 video 未播放时露出纯黑首帧 -->
  <image v-if="thumb" class="vc-img" :src="thumb" mode="aspectFill" lazy-load />
  <view v-else class="vc-ph" />
</template>

<script>
/**
 * 岁记 · 视频封面（easycom 自动注册）
 * 仅负责「封面底图 / 占位底色」，不实例化播放器；播放三角、遮罩、时长/段数角标
 * 仍由各父页面叠加。点击行为也在父级（全屏预览保留原生 <video>）。
 *
 * 背景：App 端原生 <video> 未播放时不解码首帧，poster 为空会露出卡片黑底；
 * 选片阶段 App 通常拿不到首帧缩略图、后端暂不抽帧，故无 thumb 时用占位兜底。
 * 用法：<sj-video-cover :thumb="video.thumb" class="xxx" />
 */
export default {
  name: 'SjVideoCover',
  props: {
    /* 封面图路径（本地临时或云端带 token 地址）；空字符串表示无封面 */
    thumb: { type: String, default: '' }
  }
}
</script>

<style lang="scss" scoped>
.vc-img,
.vc-ph {
  width: 100%;
  height: 100%;
  display: block;
}
/* 占位：暖深灰渐变，区别于纯黑，叠在其上的白色播放三角仍清晰 */
.vc-ph {
  background: linear-gradient(135deg, #57494d 0%, #2e2729 100%);
}
</style>
