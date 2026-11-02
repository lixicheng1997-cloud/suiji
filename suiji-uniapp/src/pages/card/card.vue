<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回按钮 + display 标题；原页头「生成」动作迁移至底部通栏按钮） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="'/static/icons/ctl/' + __theme + '/56/59-ctl-nav-back.png'" />
      </view>
      <text class="pg-title">纪念卡</text>
    </view>

    <view class="content">
      <!-- 卡片类型切换（sj-tag chip 可选中胶囊：百日 / 周岁 / 里程碑） -->
      <view class="pg-chips">
        <sj-tag
          v-for="(t, i) in CARD_TYPES"
          :key="i"
          variant="chip"
          pressable
          :active="type === i"
          :text="t.name"
          @click="pickType(i)"
        />
      </view>

      <!-- 里程碑选择（仅里程碑纪念卡：只列已达成的里程碑，卡面按所选动态派生） -->
      <block v-if="type === 2">
        <view class="pg-sec"><text>选择里程碑</text></view>
        <view class="pg-chips" v-if="milestones.length">
          <sj-tag
            v-for="(m, i) in milestones"
            :key="m.id"
            variant="chip"
            pressable
            :active="msIdx === i"
            :text="m.name"
            @click="pickMs(i)"
          />
        </view>
        <view class="pg-hint" v-else><text>还没有已达成的里程碑 · 在首页记录「里程碑」后即可在此选择</text></view>
      </block>

      <!-- 预览卡（卡面与装饰跟随当前主题皮肤，与导出图同源） -->
      <view class="mem-card" :style="mcStyle">
        <!-- 主题横幅：庆祝彩带 + 吉祥物圆章（bear 小熊岁岁 / duck 小鸭叽叽） -->
        <view class="mc-head">
          <view class="mc-bits">
            <view
              v-for="(c, i) in skin.confetti"
              :key="'cf' + i"
              class="mc-bit"
              :style="{ background: c }"
            />
          </view>
          <sj-mascot class="mc-crest" :size="112" />
        </view>
        <image v-if="photos.length" class="mc-photo" :src="photos[photo] ? photos[photo].url : photos[0].url" mode="aspectFill" />
        <view v-else class="mc-photo mc-ph" :style="mcTintStyle">
          <image class="mc-ph-ic" :src="'/static/icons/ctl/' + __theme + '/96/58-ctl-upload.png'" mode="aspectFit" />
          <text>还没有照片记录 · 先在首页添加</text>
        </view>
        <text class="mc-title">{{ cardTitle }}</text>
        <text class="mc-date">{{ cardDateText }}</text>
        <text class="mc-text">{{ text || defaultSub }}</text>
        <!-- 主题小径：熊掌 / 鸭蹼 + 星光 / 羽毛 -->
        <view class="mc-trail">
          <image class="mt-g mt-g-1" :src="glyphSrc" mode="aspectFit" />
          <image class="mt-s" :src="sparkSrc" mode="aspectFit" />
          <image class="mt-g mt-g-2" :src="glyphSrc" mode="aspectFit" />
        </view>
        <text class="mc-foot">{{ '岁 记 · ' + babyAge }}</text>
      </view>

      <!-- 祝福语（v2 pg-sec 小节标题 + sj-textarea 输入卡） -->
      <view class="pg-sec"><text>祝福语</text></view>
      <sj-textarea v-model="text" height="176rpx" placeholder="写一句祝福 · 留空则使用模板文案" />

      <!-- 选择照片（v2 相册网格：真实照片记录，白描边缩略图，选中 primary 描边） -->
      <view class="pg-sec"><text>选择照片</text></view>
      <view class="album-grid" v-if="photos.length">
        <image
          class="album-img"
          :class="{ on: photo === i }"
          v-for="(p, i) in photos"
          :key="i"
          :src="p.url"
          mode="aspectFill"
          lazy-load
          hover-class="hover-press"
          :hover-stay-time="80"
          @click="pickPhoto(i)"
        />
      </view>
      <view class="pg-hint" v-else><text>暂无可选照片 · 记录宝宝照片后即可在此挑选</text></view>

      <!-- 当前主题说明（卡片元素/配色随形象变化） -->
      <view class="pg-hint"><text>{{ '卡片元素与配色跟随当前主题 · ' + themeLabel + '（形象可在「我的」切换）' }}</text></view>

      <!-- 生成主按钮（sj-button 通栏大号渐变） -->
      <sj-button class="cd-btn" block size="lg" text="生成纪念卡" @click="gen" />
    </view>

    <!-- 离屏导出画布：不可见，仅用于把纪念卡绘制成图片 -->
    <canvas canvas-id="cardCanvas" class="card-canvas" :style="{ width: CW + 'px', height: CH + 'px' }"></canvas>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import * as api from '@/utils/api.js'
import { CARD_TYPES } from '@/utils/mock.js'
import { palette, cardSkin, withAlpha, THEME_LABELS } from '@/theme/theme.js'
import { play } from '@/utils/sound.js'

export default {
  data() {
    return {
      CARD_TYPES,
      /* 可选照片：当前宝宝的真实照片记录（含图条目），无记录时为空态 */
      photos: [],
      /* 已达成的里程碑（里程碑纪念卡数据源）与当前所选索引 */
      milestones: [],
      msIdx: 0,
      type: 0,
      photo: 0,
      text: '',
      babyName: '',
      babyAge: '',
      statusBarHeight: 20,
      /* 离屏导出画布：1 画布单位 = 1rpx，尺寸/间距全部照抄 .mem-card 的排版度量，
         避免预览与导出图比例不一致（照片被压扁即由此而来）；导出按 2x 放大。
         CH 取祝福语 3 行时的最高卡高，实际导出按内容高度裁切 */
      CW: 686,
      CH: 1010,
      /* 生成中标志，防重复点击 */
      generating: false
    }
  },

  computed: {
    /* 当前所选里程碑（越界或未达成时为 null，卡面回退通用文案） */
    curMs() {
      return this.milestones[this.msIdx] || null
    },
    /* 卡面标题：里程碑卡用里程碑名，其余用类型 tag */
    cardTitle() {
      const tag = this.type === 2 ? (this.curMs ? this.curMs.name : this.CARD_TYPES[2].tag) : this.CARD_TYPES[this.type].tag
      return (this.babyName || '宝宝') + ' · ' + tag
    },
    /* 卡面日期：里程碑卡标注达成日（YYYY.MM.DD），其余为生成日 */
    cardDateText() {
      if (this.type === 2 && this.curMs && this.curMs.achieved_at) {
        return String(this.curMs.achieved_at).slice(0, 10).replace(/-/g, '.')
      }
      return this.todayText
    },
    /* 祝福语留空时的模板文案：里程碑卡按所选里程碑派生 */
    defaultSub() {
      if (this.type === 2) {
        return this.curMs
          ? '里程碑「' + this.curMs.name + '」达成 · 每一个第一次都值得被记住'
          : this.CARD_TYPES[2].sub
      }
      return this.CARD_TYPES[this.type].sub
    },
    /* 当前主题的纪念卡皮肤：卡面渐变 / 描边 / 掌印 / 彩带，预览与导出共用一份 */
    skin() {
      return cardSkin(this.__theme)
    },
    themeLabel() {
      return THEME_LABELS[this.__theme] || ''
    },
    /* 生成日期：预览与导出图共用，标注在祝福语上方 */
    todayText() {
      const d = new Date()
      const pad = n => (n < 10 ? '0' + n : '' + n)
      return d.getFullYear() + '.' + pad(d.getMonth() + 1) + '.' + pad(d.getDate())
    },
    /* 卡面色由令牌下发（页面 CSS 不写死色值）；预览保留 .84 半透，导出用实色 */
    mcStyle() {
      const s = this.skin
      return {
        background: 'linear-gradient(160deg, ' + withAlpha(s.bgFrom, 0.84) + ', ' + withAlpha(s.bgTo, 0.84) + ')',
        'border-color': withAlpha(s.edge, 0.92)
      }
    },
    mcTintStyle() {
      return { background: withAlpha(this.skin.tint, 0.9) }
    },
    /* 预览装饰直接用 IP 素材；canvas 端为程序化等价绘制（小程序 canvas 画 SVG 不可靠） */
    glyphSrc() {
      return this.__theme === 'duck' ? '/static/anim/bg-foot-duck.svg' : '/static/anim/sym-paw.svg'
    },
    sparkSrc() {
      return this.__theme === 'duck' ? '/static/anim/bg-feather.svg' : '/static/anim/sym-star.svg'
    }
  },

  onLoad(options) {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
    /* 宝宝名/月龄取当前档案，无档案留空 */
    const b = api.getBaby()
    this.babyName = (b && b.name) || ''
    this.babyAge = (b && b.age) || ''
    /* 已达成的里程碑（纪念卡按达成先后排列） */
    this.milestones = api.getMilestones().filter(m => m.done)
    /* 里程碑直达：?type=milestone&ms=<id>（成长页）或 &entry=<记录id>（首页庆祝弹层）
       → 主动选中里程碑卡并预选对应里程碑 */
    if (options && options.type === 'milestone' && this.milestones.length) {
      this.type = 2
      const j = this.milestones.findIndex(m =>
        m.id === (options.ms || '') || (options.entry && m.source_entry_id === options.entry))
      if (j > -1) this.msIdx = j
    }
    /* 拉取真实照片记录（时光轴按日分组 → 拍平取含图条目；带 entry id 供里程碑联动选图） */
    api.fetchEntries({}).then(groups => {
      const items = []
      groups.forEach(g => g.items.forEach(i => { if (i.photo) items.push({ url: i.photo, entryId: i.id }) }))
      this.photos = items
      /* 照片到位后再做一次联动：直达场景下 onLoad 时 photos 尚为空 */
      this.syncMsPhoto()
    }).catch(() => { /* 拉取失败保持空态 */ })
  },

  methods: {
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
      } else {
        uni.reLaunch({ url: '/pages/index/index' })
      }
    },

    pickType(i) {
      this.type = i
      /* 切到里程碑卡但还没有达成的里程碑：提示去记录，页面同时展示空态说明 */
      if (i === 2 && !this.milestones.length) {
        this.$refs.ntf.show({ type: 'warn', message: '还没有已达成的里程碑，先去首页记录吧' })
      }
    },
    pickPhoto(i) { this.photo = i },
    /* 选里程碑：若来源记录带照片，自动切到那张（里程碑与照片同源同框） */
    pickMs(i) {
      this.msIdx = i
      this.syncMsPhoto()
    },
    /* 把当前所选里程碑的来源记录照片置为选中（无来源照片则不动） */
    syncMsPhoto() {
      const ms = this.milestones[this.msIdx]
      if (this.type !== 2 || !ms || !ms.source_entry_id) return
      const j = this.photos.findIndex(p => p.entryId === ms.source_entry_id)
      if (j > -1) this.photo = j
    },

    /**
     * 生成纪念卡并保存到相册：
     * 离屏 canvas 绘制卡片 → canvasToTempFilePath 导出临时图 → saveImageToPhotosAlbum 存相册。
     * 失败/无权限给出可读提示；H5 无相册 API，改为触发下载。
     */
    async gen() {
      if (this.generating) return
      /* 里程碑卡必须先有可达成的里程碑 */
      if (this.type === 2 && !this.milestones.length) {
        this.$refs.ntf.show({ type: 'warn', message: '还没有已达成的里程碑，先去首页记录吧' })
        return
      }
      this.generating = true
      try {
        const path = await this.renderCard()
        await this.saveToAlbum(path)
        /* 纪念卡生成完成：百日/周岁各绑 E07 变体，里程碑卡不传 key */
        play('E07', this.type === 0 ? { key: 'hundred' } : this.type === 1 ? { key: 'year' } : {})
        this.$refs.ntf.show({ type: 'ok', message: '纪念卡已保存到相册' })
      } catch (e) {
        this.onGenFail(e)
      } finally {
        this.generating = false
      }
    },

    /* 在离屏画布上按当前主题皮肤复刻 .mem-card，导出为临时图片路径
       坐标系 1 单位 = 1rpx，导出按 2x 放大 */
    renderCard() {
      const W = this.CW, CH = this.CH
      const pal = palette(this.__theme)
      const skin = this.skin
      const ctx = uni.createCanvasContext('cardCanvas', this)
      /* 以下度量取预览实测（.mem-card 686 宽 / 横幅 131 / 照片 610x408 / 行距） */
      const PX = 38, PY = 165, PW = W - 76, PH = 408, PR = 40
      const FB = 6 /* 照片白描边宽度（同 .mc-photo 的 6rpx） */
      const sel = this.photos[this.photo] || this.photos[0]

      return new Promise((resolve, reject) => {
        /* 祝福语先按 25rpx 量好行数（最多 3 行），卡高随行数收放 —— 与预览的流式高度一致，
           避免定高画布在少行文案时留出一段空白 */
        ctx.setFontSize(25)
        const body = this.text || this.defaultSub
        const all = this.wrapText(ctx, body, PW)
        const lines = all.length > 3 ? all.slice(0, 3) : all
        if (lines.length < all.length) {
          lines[lines.length - 1] = String(lines[lines.length - 1]).replace(/[,，。.!？?]$/, '') + '…'
        }
        const ty = PY + PH + 72
        const dy = ty + 50
        const by = dy + 57
        const H = Math.min(CH, by + (lines.length - 1) * 43 + 168)

        /* 背景：圆角 + 主题渐变 + 金边 + 内细线花框 + 四角点缀 */
        const grad = ctx.createLinearGradient(0, 0, 0, H)
        grad.addColorStop(0, skin.bgFrom)
        grad.addColorStop(1, skin.bgTo)
        this.roundRect(ctx, 0, 0, W, H, 56)
        ctx.setFillStyle(grad)
        ctx.fill()
        this.roundRect(ctx, 2, 2, W - 4, H - 4, 54)
        ctx.setStrokeStyle(skin.edge)
        ctx.setLineWidth(4)
        ctx.stroke()
        this.roundRect(ctx, 16, 16, W - 32, H - 32, 42)
        ctx.setStrokeStyle(skin.edgeIn)
        ctx.setLineWidth(2)
        ctx.stroke()
        this.corners(ctx, W, H, pal, skin)

        /* 主题元素：彩带 + 吉祥物圆章 + 掌印/掌蹼小径 */
        this.confetti(ctx, W, pal, skin)
        this.crest(ctx, W / 2, 100, 56, pal, skin)
        this.trail(ctx, W, H, pal, skin)

        /* 照片（aspectFill 裁剪 + 圆角），加载失败由调用方回退占位 */
        const drawPhoto = (info) => {
          const ip = info.path || sel.url
          const ix = PX + FB, iy = PY + FB, iw = PW - FB * 2, ih = PH - FB * 2
          const s = Math.max(iw / info.width, ih / info.height)
          const dw = info.width * s, dh = info.height * s
          ctx.save()
          this.roundRect(ctx, PX, PY, PW, PH, PR)
          ctx.clip()
          ctx.setFillStyle('#FFFFFF')
          ctx.fillRect(PX, PY, PW, PH)
          ctx.drawImage(ip, ix - (dw - iw) / 2, iy - (dh - ih) / 2, dw, dh)
          ctx.restore()
        }

        /* 文案 + 落笔导出 */
        const finish = () => {
          ctx.setTextAlign('center')

          /* 标题（双绘模拟加粗） */
          const title = this.cardTitle
          ctx.setFontSize(38)
          ctx.setFillStyle(pal['primary-deep'])
          ctx.fillText(title, W / 2 - 0.6, ty)
          ctx.fillText(title, W / 2 + 0.6, ty)

          /* 日期（里程碑卡为达成日，其余为生成日） */
          ctx.setFontSize(22)
          ctx.setFillStyle(pal['faint'])
          ctx.fillText(this.cardDateText, W / 2, dy)

          /* 祝福语 */
          ctx.setFontSize(25)
          ctx.setFillStyle(pal['sub'])
          lines.forEach((ln, i) => ctx.fillText(ln, W / 2, by + i * 43))

          /* 页脚 */
          ctx.setFontSize(20)
          ctx.setFillStyle(pal['faint'])
          ctx.fillText('岁 记 · ' + (this.babyAge || ''), W / 2, H - 46)

          /* 落笔并导出（draw 回调后留一帧，确保 App 端渲染完成） */
          ctx.draw(false, () => {
            setTimeout(() => {
              uni.canvasToTempFilePath({
                canvasId: 'cardCanvas',
                x: 0, y: 0, width: W, height: H,
                destWidth: W * 2, destHeight: H * 2,
                fileType: 'png',
                success: r => resolve(r.tempFilePath),
                fail: reject
              }, this)
            }, 120)
          })
        }

        if (sel && sel.url) {
          uni.getImageInfo({
            src: sel.url,
            success: info => { drawPhoto(info); finish() },
            /* 图片拉取失败不阻断：画占位后继续导出 */
            fail: () => { this.photoPlaceholder(ctx, PX, PY, PW, PH, PR); finish() }
          })
        } else {
          this.photoPlaceholder(ctx, PX, PY, PW, PH, PR)
          finish()
        }
      })
    },

    /* ============ 主题元素绘制（canvas 老接口） ============
       小程序/App 的 canvas 上下文没有 ellipse()，也没有可靠的 SVG 解码，
       故椭圆一律 translate+rotate+scale+arc 画，吉祥物按 140 视框等比复刻。 */

    /* 实心椭圆：rx 沿旋转后的横轴，ry 沿纵轴 */
    ell(ctx, cx, cy, rx, ry, fill, rot) {
      ctx.save()
      ctx.translate(cx, cy)
      if (rot) ctx.rotate(rot)
      ctx.scale(1, ry / rx)
      ctx.beginPath()
      ctx.arc(0, 0, rx, 0, Math.PI * 2)
      ctx.setFillStyle(fill)
      ctx.fill()
      ctx.restore()
    },

    /* 等粗描边椭圆：stroke 会被 scale 压扁，改为「线色大椭圆 + 填色小椭圆」叠出 */
    ellOut(ctx, cx, cy, rx, ry, fill, line, lw, rot) {
      this.ell(ctx, cx, cy, rx + lw, ry + lw, line, rot)
      this.ell(ctx, cx, cy, rx, ry, fill, rot)
    },

    /* 圆（fill / line 任一可省） */
    disc(ctx, cx, cy, r, fill, line, lw) {
      ctx.save()
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      if (fill) {
        ctx.setFillStyle(fill)
        ctx.fill()
      }
      if (line && lw) {
        ctx.setStrokeStyle(line)
        ctx.setLineWidth(lw)
        ctx.stroke()
      }
      ctx.restore()
    },

    /* 四角点缀：bear 蜂蜜星光 / duck 池塘涟漪环 */
    corners(ctx, W, H, pal, skin) {
      const r = 9
      ;[[32, 32], [W - 32, 32], [32, H - 32], [W - 32, H - 32]].forEach(p => {
        ctx.save()
        ctx.setGlobalAlpha(0.75)
        if (skin.glyph === 'paw') {
          this.disc(ctx, p[0], p[1], r, pal['accent-soft'])
          this.disc(ctx, p[0], p[1], r * 0.45, skin.spark)
        } else {
          this.disc(ctx, p[0], p[1], r, null, skin.spark, 2)
        }
        ctx.restore()
      })
    },

    /* 庆祝彩带：马卡龙色小粒，位置/尺寸对齐预览 .mc-bit（16x24rpx） */
    confetti(ctx, W, pal, skin) {
      const bits = [
        [90, 82, -24], [172, 120, 16], [260, 56, 12], [W - 172, 76, -8], [W - 90, 116, 28]
      ]
      bits.forEach((b, i) => {
        ctx.save()
        ctx.translate(b[0], b[1])
        ctx.rotate(b[2] * Math.PI / 180)
        ctx.setGlobalAlpha(0.92)
        this.roundRect(ctx, -8, -12, 16, 24, 6)
        ctx.setFillStyle(skin.confetti[i % skin.confetti.length])
        ctx.fill()
        ctx.restore()
      })
    },

    /* 掌印小径：左下角三枚渐远的脚印 + 右下角星光/涟漪
       （与 <sj-bg /> 的「主题小径」同一叙事：bear 熊掌 / duck 鸭蹼） */
    trail(ctx, W, H, pal, skin) {
      const duck = skin.glyph === 'web'
      const body = duck ? pal['duck-body'] : pal['bear-body']
      const line = duck ? pal['duck-line'] : pal['bear-line']
      /* [x, 距底, 透明度, 朝向 deg, 大小]：小径带与预览 .mc-trail 同高（祝福语下 26rpx），随卡高浮动 */
      const steps = [
        [92, H - 100, 0.6, 96, 32],
        [156, H - 132, 0.45, 88, 28],
        [220, H - 104, 0.3, 100, 24]
      ]
      steps.forEach(s => {
        ctx.save()
        ctx.translate(s[0], s[1])
        ctx.rotate((s[3] - 90) * Math.PI / 180)
        ctx.setGlobalAlpha(s[2])
        this.footprint(ctx, skin.glyph, s[4], body, line, pal)
        ctx.restore()
      })
      /* 右下角点缀 */
      ctx.save()
      ctx.setGlobalAlpha(0.8)
      this.sparkle(ctx, skin, W - 96, H - 104, 15, 10)
      this.sparkle(ctx, skin, W - 150, H - 140, 9, -14)
      this.sparkle(ctx, skin, W - 76, H - 160, 6, 20)
      ctx.restore()
    },

    /* 单枚脚印（局部原点绘制，调用方负责平移/旋转/透明度）
       两遍绘制：先画整体放大的线色轮廓，再按原尺寸填色 —— 掌蹼因此连成一片，不留内缝 */
    footprint(ctx, kind, size, body, line, pal) {
      const u = size / 48
      const lw = 1.3 * u
      /* [cx, cy, rx, ry, rot]：rx 为旋转后横半轴 */
      const shapes = []
      if (kind === 'paw') {
        shapes.push([0, 8 * u, 13 * u, 11 * u, 0])
        ;[[-14.5, -3.5, 5.4], [-5.5, -11.5, 5.6], [5.5, -11.5, 5.6], [14.5, -3.5, 5.4]]
          .forEach(t => shapes.push([t[0] * u, t[1] * u, t[2] * u, t[2] * u, 0]))
      } else {
        /* 鸭蹼：三趾大角度扇开 + 一片连蹼掌垫（不画脚跟，小尺寸下才像足迹而非花瓣） */
        ;[[-0.8, 8.6], [0, 10], [0.8, 8.6]].forEach(t => {
          shapes.push([Math.sin(t[0]) * 9 * u, -Math.cos(t[0]) * 9 * u + 3 * u, 4.8 * u, t[1] * u, t[0]])
        })
        shapes.push([0, 6 * u, 9.6 * u, 6 * u, 0])
      }
      shapes.forEach(s => this.ell(ctx, s[0], s[1], s[2] + lw, s[3] + lw, line, s[4]))
      shapes.forEach(s => this.ell(ctx, s[0], s[1], s[2], s[3], body, s[4]))
      if (kind === 'paw') this.ell(ctx, 0, 9 * u, 6.6 * u, 5.2 * u, pal['primary-soft'])
    },

    /* 点缀图形：bear 四角星光 / duck 池塘涟漪环 */
    sparkle(ctx, skin, cx, cy, r, rotDeg) {
      if (skin.glyph === 'paw') {
        ctx.save()
        ctx.translate(cx, cy)
        ctx.rotate((rotDeg || 0) * Math.PI / 180)
        ctx.beginPath()
        ctx.moveTo(0, -r)
        ctx.quadraticCurveTo(r * 0.18, -r * 0.18, r, 0)
        ctx.quadraticCurveTo(r * 0.18, r * 0.18, 0, r)
        ctx.quadraticCurveTo(-r * 0.18, r * 0.18, -r, 0)
        ctx.quadraticCurveTo(-r * 0.18, -r * 0.18, 0, -r)
        ctx.closePath()
        ctx.setFillStyle(skin.spark)
        ctx.fill()
        ctx.restore()
      } else {
        ctx.save()
        ctx.setStrokeStyle(skin.spark)
        ctx.setLineWidth(2.5)
        ctx.beginPath()
        ctx.arc(cx, cy, r, 0, Math.PI * 2)
        ctx.stroke()
        ctx.beginPath()
        ctx.arc(cx, cy, r * 0.55, 0, Math.PI * 2)
        ctx.stroke()
        ctx.restore()
      }
    },

    /* 吉祥物圆章：按 static/anim/{bear|duck}-face.svg 的 140 视框等比复刻，
       导出图与 App 内 IP 保持同一张脸（颜色取 theme.js IP 令牌） */
    crest(ctx, cx, cy, R, pal, skin) {
      const duck = skin.glyph === 'web'
      const body = duck ? pal['duck-body'] : pal['bear-body']
      const line = duck ? pal['duck-line'] : pal['bear-line']
      /* 底托：白圈 + 主题浅底 + 主色环 */
      this.disc(ctx, cx, cy, R + 4, pal['white'], skin.edge, 3)
      this.disc(ctx, cx, cy, R - 4, pal['primary-soft'], pal['primary'], 4)
      /* 视框映射：头部 (70,80) r≈47 → 章内留边 */
      const k = (R - 16) / 47
      const X = px => cx + (px - 70) * k
      const Y = py => cy + (py - 80) * k
      if (!duck) {
        this.disc(ctx, X(34), Y(38), 20 * k, body, line, 5 * k)
        this.disc(ctx, X(106), Y(38), 20 * k, body, line, 5 * k)
        this.disc(ctx, X(34), Y(38), 9 * k, pal['ear-inner'])
        this.disc(ctx, X(106), Y(38), 9 * k, pal['ear-inner'])
      } else {
        /* 头冠一撮毛（SVG 里是摇摆的小扇形，这里用倾角椭圆近似） */
        this.ellOut(ctx, X(72), Y(28), 5 * k, 12 * k, body, line, 2.5 * k, 0.4)
      }
      this.disc(ctx, X(70), Y(80), (duck ? 46 : 47) * k, body, line, 5 * k)
      if (!duck) {
        this.ell(ctx, X(70), Y(94), 22 * k, 16 * k, pal['bear-muzzle'])
        this.ell(ctx, X(70), Y(88), 7 * k, 5 * k, line)
        ctx.save()
        ctx.beginPath()
        ctx.moveTo(X(70), Y(93))
        ctx.quadraticCurveTo(X(70), Y(99), X(63), Y(100))
        ctx.setStrokeStyle(line)
        ctx.setLineWidth(3 * k)
        ctx.stroke()
        ctx.beginPath()
        ctx.moveTo(X(70), Y(93))
        ctx.quadraticCurveTo(X(70), Y(99), X(77), Y(100))
        ctx.stroke()
        ctx.restore()
      } else {
        /* 喙：上缘外凸、下缘收圆（同 SVG 的三段二次贝塞尔） */
        ctx.save()
        ctx.beginPath()
        ctx.moveTo(X(52), Y(86))
        ctx.quadraticCurveTo(X(70), Y(76), X(88), Y(86))
        ctx.quadraticCurveTo(X(84), Y(100), X(70), Y(100))
        ctx.quadraticCurveTo(X(56), Y(100), X(52), Y(86))
        ctx.closePath()
        ctx.setFillStyle(pal['duck-beak'])
        ctx.fill()
        ctx.setStrokeStyle(line)
        ctx.setLineWidth(4 * k)
        ctx.stroke()
        ctx.restore()
      }
      this.disc(ctx, X(duck ? 54 : 52), Y(72), 5.5 * k, pal['eye-ink'])
      this.disc(ctx, X(duck ? 86 : 88), Y(72), 5.5 * k, pal['eye-ink'])
      /* 腮红 .85 */
      ctx.save()
      ctx.setGlobalAlpha(0.85)
      this.ell(ctx, X(38), Y(duck ? 84 : 86), 8 * k, 5 * k, pal['cheek'])
      this.ell(ctx, X(102), Y(duck ? 84 : 86), 8 * k, 5 * k, pal['cheek'])
      ctx.restore()
    },

    /* 圆角矩形路径（不含 fill/stroke，由调用方决定） */
    roundRect(ctx, x, y, w, h, r) {
      ctx.beginPath()
      ctx.moveTo(x + r, y)
      ctx.arcTo(x + w, y, x + w, y + h, r)
      ctx.arcTo(x + w, y + h, x, y + h, r)
      ctx.arcTo(x, y + h, x, y, r)
      ctx.arcTo(x, y, x + w, y, r)
      ctx.closePath()
    },

    /* 逐字换行（中文无空格，按 measureText 断行；保留手动换行 \n） */
    wrapText(ctx, text, maxW) {
      const out = []
      String(text || '').split('\n').forEach(seg => {
        let cur = ''
        for (const ch of seg) {
          if (ctx.measureText(cur + ch).width > maxW && cur) {
            out.push(cur)
            cur = ch
          } else {
            cur += ch
          }
        }
        out.push(cur)
      })
      return out
    },

    photoPlaceholder(ctx, x, y, w, h, r) {
      const skin = this.skin
      const duck = skin.glyph === 'web'
      const pal = palette(this.__theme)
      const ix = x + 6, iy = y + 6, iw = w - 12, ih = h - 12
      /* 先铺整块白，再在其内画 tint —— 留出与有照片时一致的 6rpx 白框 */
      this.roundRect(ctx, x, y, w, h, r)
      ctx.setFillStyle('#FFFFFF')
      ctx.fill()
      this.roundRect(ctx, ix, iy, iw, ih, r - 6)
      ctx.setFillStyle(skin.tint)
      ctx.fill()
      /* 空态用当前主题脚印占位，切形象即换图形 */
      ctx.save()
      ctx.setGlobalAlpha(0.5)
      ctx.translate(ix + iw / 2, iy + ih / 2 - 34)
      this.footprint(ctx, skin.glyph, 72,
        duck ? pal['duck-body'] : pal['bear-body'],
        duck ? pal['duck-line'] : pal['bear-line'], pal)
      ctx.restore()
      ctx.setTextAlign('center')
      ctx.setFontSize(22)
      ctx.setFillStyle(pal['faint'])
      ctx.fillText('还没有照片记录 · 先在首页添加', ix + iw / 2, iy + ih / 2 + 60)
    },

    /* 保存到相册（H5 走下载兜底） */
    saveToAlbum(filePath) {
      return new Promise((resolve, reject) => {
        // #ifdef H5
        try {
          const a = document.createElement('a')
          a.href = filePath
          a.download = '岁记纪念卡.png'
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
          resolve()
        } catch (e) { reject(e) }
        // #endif
        // #ifndef H5
        uni.saveImageToPhotosAlbum({ filePath, success: resolve, fail: reject })
        // #endif
      })
    },

    /* 取消静默；权限类与其它错误分别给出可读提示 */
    onGenFail(e) {
      const msg = (e && (e.errMsg || e.message)) || ''
      if (!msg || /cancel/i.test(msg)) return
      if (/permission|denied|auth|授权|权限|write|storage/i.test(msg)) {
        this.$refs.ntf.show({ type: 'err', message: '未获得相册写入权限，请在系统设置中开启后重试' })
        return
      }
      this.$refs.ntf.show({ type: 'err', message: '生成失败：' + msg })
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

/* ---------- 内容区 ---------- */
.content { padding: 8rpx 32rpx 48rpx; }

/* 类型胶囊行（胶囊本体由 sj-tag chip 负责，此处仅排布） */
.pg-chips { display: flex; flex-wrap: wrap; gap: 16rpx; margin-bottom: 24rpx; }

/* 小节标题（v2 pg-sec） */
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

/* 预览卡（v2 P32 纪念卡：卡面渐变与描边由 theme.js 纪念卡皮肤 :style 下发，随主题切换） */
.mem-card {
  position: relative;
  overflow: hidden;
  border: 2rpx solid transparent;
  border-radius: var(--sj-r-lg);
  box-shadow: var(--sj-sh-md);
  padding: 32rpx 36rpx 36rpx;
  text-align: center;
  margin-bottom: 8rpx;
}

/* 主题横幅：庆祝彩带 + 居中的吉祥物圆章 */
.mc-head {
  position: relative;
  height: 128rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.mc-bits { position: absolute; left: 0; top: 0; right: 0; bottom: 0; }
.mc-bit {
  position: absolute;
  width: 16rpx;
  height: 24rpx;
  border-radius: 6rpx;
  opacity: 0.92;
}
.mc-bit:nth-child(1) { left: 44rpx; top: 36rpx; transform: rotate(-24deg); }
.mc-bit:nth-child(2) { left: 126rpx; top: 74rpx; transform: rotate(16deg); }
.mc-bit:nth-child(3) { right: 126rpx; top: 30rpx; transform: rotate(-8deg); }
.mc-bit:nth-child(4) { right: 44rpx; top: 70rpx; transform: rotate(28deg); }
.mc-bit:nth-child(5) { left: 214rpx; top: 10rpx; transform: rotate(12deg); }

/* 照片（aspectFill 裁剪 + 白描边） */
.mc-photo {
  width: 100%;
  height: 400rpx;
  border-radius: var(--sj-r-md);
  border: 6rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
  background: var(--sj-surface);
  display: block;
}
/* 无照片空态（底色取皮肤 tint，图标取当前主题资源） */
.mc-ph {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  box-sizing: border-box;
  font-size: 22rpx;
  color: var(--sj-faint);
}
.mc-ph-ic { width: 72rpx; height: 72rpx; opacity: 0.85; }
.mc-title {
  display: block;
  font-family: var(--sj-font-display);
  font-size: 38rpx;
  font-weight: 900;
  color: var(--sj-primary-deep);
  margin-top: 28rpx;
  letter-spacing: 4rpx;
}
.mc-date {
  display: block;
  font-size: 22rpx;
  color: var(--sj-faint);
  margin-top: 10rpx;
  letter-spacing: 2rpx;
}
.mc-text {
  display: block;
  font-size: 25rpx;
  color: var(--sj-sub);
  margin-top: 18rpx;
  line-height: 1.7;
}
/* 主题小径：祝福语与落款之间的一道花（bear 熊掌+星光 / duck 鸭蹼+羽毛） */
.mc-trail {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18rpx;
  margin-top: 26rpx;
  opacity: 0.8;
}
.mt-g { width: 34rpx; height: 34rpx; }
.mt-g-1 { transform: rotate(96deg); }
.mt-g-2 { transform: rotate(-88deg); }
.mt-s { width: 26rpx; height: 26rpx; }
.mc-foot {
  display: block;
  font-size: 20rpx;
  color: var(--sj-faint);
  margin-top: 24rpx;
  letter-spacing: 6rpx;
}

/* 相册网格（v2 缩略图：白描边 + sh-sm，选中 primary 描边 + soft 光环） */
.album-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16rpx;
  margin-bottom: 8rpx;
}
.album-img {
  width: 100%;
  height: 160rpx;
  border-radius: var(--sj-r-sm);
  border: 6rpx solid #fff;
  box-shadow: var(--sj-sh-sm);
  background: var(--sj-surface);
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.album-img:active { transform: scale(0.95); }
.album-img.on {
  border-color: var(--sj-primary);
  box-shadow: 0 0 0 6rpx var(--sj-primary-soft), var(--sj-sh-sm);
}

/* 主按钮：外观由 sj-button（block lg）统一提供 */
.cd-btn {
  display: flex;
  margin-top: 40rpx;
}

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
.pg-hint.tail { margin-top: 24rpx; margin-bottom: 0; }

/* 离屏导出画布：移出可视区且不占布局，仅承载绘制 */
.card-canvas {
  position: fixed;
  top: 0;
  left: -2000px;
  opacity: 0;
  pointer-events: none;
  z-index: -1;
}
</style>
