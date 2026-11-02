/* ================================================================
   岁记官网 v4 · 站点配置
   —— 上线前只需改这一个文件
   ================================================================ */
window.SUIJI_CONFIG = {
  /* 应用信息 */
  version: '1.0.0',
  versionName: 'v1.0.0',
  apkSize: '15.6 MB',

  /* 平台要求（与 manifest.json / PRD 对齐） */
  androidReq: 'Android 10 及以上',
  iosReq: 'iOS 14 及以上',

  /* 下载地址 */
  download: {
    /* Android 官网直链（相对路径，随站点一起部署） */
    android: 'downloads/suiji-v1.0.0.apk',
    /* iOS：上架后填 App Store 链接；留空则按钮提示「上架中」 */
    ios: '',
    /* 二维码图片（由 tools/build-assets.py 生成） */
    qrAndroid: 'assets/qr/android.png',
    qrIos: 'assets/qr/ios.png'
  },

  /* 官网基址，用于二维码内容与「复制官网链接」（suiji-server nginx 托管） */
  siteUrl: 'http://49.233.77.155:30080/suiji-website/',

  /* 隐私与合规声明（页脚展示） */
  disclaimer:
    '生长曲线、里程碑参考月龄与 AI 日记解读仅供参考，不构成医学诊断或就医建议。'
};
