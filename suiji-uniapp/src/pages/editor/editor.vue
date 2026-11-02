<template>
  <view class="page" :style="themeVars">
    <sj-bg />
    <!-- 顶栏（v2 pg-back：圆形返回按钮 + 标题 + 宝宝·月龄小字；保存移至底部通栏按钮） -->
    <view class="pg-back" :style="{ paddingTop: 'calc(' + statusBarHeight + 'px + 8rpx)' }">
      <view class="bk" hover-class="hover-press" :hover-stay-time="80" @click="goBack">
        <image class="bk-ic" :src="backIconSrc" mode="aspectFit" />
      </view>
      <view class="pg-title-row">
        <text class="pg-title">{{ pageTitle }}</text>
        <text class="pg-type">{{ typeLabel }}</text>
      </view>
      <text class="pg-baby">{{ babyLabel }}</text>
    </view>

    <!-- 类型胶囊行（v2 pg-chips：10 类横向滚动，点击只切换表单、不清空已填内容） -->
    <!-- <scroll-view class="type-scroll" scroll-x :show-scrollbar="false">
      <view class="type-chips">
        <sj-tag
          v-for="k in typeKeys"
          :key="k"
          class="tchip"
          variant="chip"
          pressable
          :active="type === k"
          :text="TYPES[k].label"
          @click="switchType(k)"
        />
      </view>
    </scroll-view> -->

    <view class="form-wrap">
      <!-- ========== 喂养 ========== -->
      <block v-if="type === 'feeding'">
        <view class="pg-sec"><text>喂养方式 </text><text class="req">*</text></view>
        <!-- 喂养方式单选（sj-radio ×3 横排：每枚内部自带 group，v-model 绑原字段 single.feedingMethod，
             name 沿用原取值（瓶喂/母乳亲喂/辅食），保证 buildPayload 的 method 字段兼容） -->
        <view class="radio-row">
          <sj-radio
            v-for="c in chipGroups.feedingMethod"
            :key="c"
            v-model="single.feedingMethod"
            :name="c"
            :label="c"
          />
        </view>

        <view class="pg-field">
          <text class="pf-label">本次奶量（ml）</text>
          <!-- 步进器（sj-number-box：步长 10ml、0–500ml；单位放 label。上限收住，误输 999 会污染喂养统计） -->
          <sj-number-box v-model="nums.feeding" :min="0" :max="500" :step="10" class="nb-right" />
        </view>
        <view class="pg-field">
          <text class="pf-label">温度</text>
          <!-- 体温滑块（sj-slider：35–42℃、步长 0.1、1 位小数，右侧自带值文本；
               v-model 仍绑 nums.temp（默认 37.0 在量程内），buildPayload 的 temp 字段照常读取） -->
          <sj-slider v-model="nums.temp" :min="35" :max="42" :step="0.1" :decimals="1" unit=" ℃" />
        </view>
        <view class="pg-field">
          <text class="pf-label">用时（分钟）</text>
          <!-- 步进器（sj-number-box：步长 1 分钟、0–180 分钟；单位放 label） -->
          <sj-number-box v-model="nums.duration" :min="0" :max="180" :step="1" class="nb-right" />
        </view>
        <view class="pg-hint" v-if="lastFeeding">已按上次 {{ lastFeeding.amount }}ml 智能带入</view>

        <!-- 辅食食材区：仅喂养方式选中“辅食”时显示 -->
        <block v-if="single.feedingMethod === '辅食'">
          <view class="pg-sec"><text>辅食食材</text></view>
          <view class="pg-chips">
            <sj-tag
              v-for="c in chipGroups.foods"
              :key="c"
              variant="chip"
              pressable
              :active="multi.foods.indexOf(c) > -1"
              :text="c"
              @click="toggleMulti('foods', c)"
            />
          </view>
          <!-- 自定义食材：点“+ 自定义”展开输入行，添加后并入上方 chips 并自动选中 -->
          <view v-if="foodCustomOpen" class="custom-row">
            <view class="custom-input">
              <sj-input v-model="foodCustom" :maxlength="20" placeholder="输入食材名，如：西兰花泥" @confirm="addCustomFood" />
            </view>
            <sj-button class="custom-add" size="mini" text="添加" @click="addCustomFood" />
          </view>
          <view v-if="multi.foods.length" class="custom-picked">
            <text class="cp-label">已选 </text>
            <sj-tag
              v-for="f in multi.foods"
              :key="f"
              variant="chip"
              size="mini"
              active
              pressable
              :text="f + ' ×'"
              @click="toggleMulti('foods', f)"
            />
          </view>
          <view class="pg-hint">新食材建议单一添加并连续观察 3 天（非医学建议）</view>
        </block>

        <sj-datetime-picker class="pk-wrap" mode="time" :value="times.feeding" @change="onTimeChange('feeding', $event)">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">时间</text>
            <text class="pf-val">{{ times.feeding }} ▾</text>
            <text class="pf-unit">{{ todayLabel }}</text>
          </view>
        </sj-datetime-picker>

        <view class="pg-sec"><text>备注</text></view>
        <!-- 备注（sj-textarea：白底描边容器由组件自绘，上限 500 字，超出会被输入框挡在本地） -->
        <sj-textarea v-model="note" placeholder="写点什么…" :maxlength="500" height="176rpx" />
      </block>

      <!-- ========== 睡眠 ========== -->
      <block v-else-if="type === 'sleep'">
        <view class="pg-sec"><text>睡眠区间 </text><text class="req">*</text></view>
        <sj-datetime-picker class="pk-wrap" mode="time" :value="times.sleepStart" @change="onTimeChange('sleepStart', $event)">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">开始</text>
            <text class="pf-val">今天 {{ times.sleepStart }} ▾</text>
          </view>
        </sj-datetime-picker>
        <sj-datetime-picker class="pk-wrap" mode="time" :value="times.sleepEnd" @change="onTimeChange('sleepEnd', $event)">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">结束</text>
            <text class="pf-val">今天 {{ times.sleepEnd }} ▾</text>
          </view>
        </sj-datetime-picker>
        <view class="pg-field">
          <text class="pf-label">时长</text>
          <text class="pf-val pf-val-right">{{ sleepDuration }}</text>
          <!-- <text class="pf-unit">自动计算</text> -->
        </view>

        <!-- <view class="timer-btn" hover-class="hover-press" :hover-stay-time="80" @click="onTimer">
          <text>{{ timerStart ? '⏸ 结束计时' : '▶ 开始计时' }}</text>
        </view> -->

        <view class="pg-sec"><text>备注</text></view>
        <!-- 备注（sj-textarea：白底描边容器由组件自绘，上限 500 字，超出会被输入框挡在本地） -->
        <sj-textarea v-model="note" placeholder="写点什么…" :maxlength="500" height="176rpx" />
      </block>

      <!-- ========== 里程碑 ========== -->
      <block v-else-if="type === 'milestone'">
        <view class="pg-sec"><text>选择里程碑（0–1 岁清单 · 5 大领域） </text><text class="req">*</text></view>
        <view class="pg-chips">
          <sj-tag
            v-for="c in chipGroups.milestonePick"
            :key="c"
            variant="chip"
            pressable
            :active="single.milestonePick === c"
            :text="c"
            @click="pickSingle('milestonePick', c)"
          />
        </view>
        <!-- 自定义里程碑：点"自定义"展开输入行，添加后并入上方 chips 并自动选中 -->
        <view v-if="msCustomOpen" class="custom-row">
          <view class="custom-input">
            <sj-input v-model="msCustom" :maxlength="30" placeholder="输入里程碑，如：第一次叫妈妈" @confirm="addCustomMilestone" />
          </view>
          <sj-button class="custom-add" size="mini" text="添加" @click="addCustomMilestone" />
        </view>

        <view class="pg-sec"><text>达成时间</text></view>
        <sj-datetime-picker class="pk-wrap" mode="time" :value="times.milestone" @change="onTimeChange('milestone', $event)">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">时间</text>
            <text class="pf-val">{{ times.milestone }} ▾</text>
            <!-- <text class="pf-unit">{{ todayLabel }}</text> -->
          </view>
        </sj-datetime-picker>
        <view class="pg-field">
          <text class="pf-label">日期不确定</text>
          <!-- 开关（sj-switch：change 新布尔值直写回 switches.dateUncertain） -->
          <sj-switch class="sw-right" :checked="switches.dateUncertain" @change="(v) => (switches.dateUncertain = v)" />
        </view>

        <view class="pg-sec"><text>照片 / 视频</text><text class="hint-chip">最多 9 张</text></view>
        <sj-photo-picker v-model="photos" :max="9" />

        <view class="pg-sec"><text>备注</text></view>
        <!-- 备注（sj-textarea：白底描边容器由组件自绘，上限 500 字，超出会被输入框挡在本地） -->
        <sj-textarea v-model="note" placeholder="写点什么…" :maxlength="500" height="176rpx" />
      </block>

      <!-- ========== 照片 ========== -->
      <block v-else-if="type === 'photo'">
        <view class="pg-sec"><text>照片 / 视频</text><text class="hint-chip">最多 9 张</text></view>
        <sj-photo-picker v-model="photos" :max="9" />

        <view class="pg-sec"><text>拍摄时间</text></view>
        <sj-datetime-picker class="pk-wrap" mode="time" :value="times.photo" @change="onTimeChange('photo', $event)">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">时间</text>
            <text class="pf-val">{{ times.photo }} ▾</text>
            <text class="pf-unit">{{ todayLabel }}</text>
          </view>
        </sj-datetime-picker>

        <view class="pg-sec"><text>备注</text></view>
        <!-- 备注（sj-textarea：白底描边容器由组件自绘，上限 500 字，超出会被输入框挡在本地） -->
        <sj-textarea v-model="note" placeholder="写点什么…" :maxlength="500" height="176rpx" />
      </block>

      <!-- ========== 便便 ========== -->
      <block v-else-if="type === 'poop'">
        <view class="pg-sec"><text>性状 </text><text class="req">*</text></view>
        <view class="pg-chips">
          <sj-tag
            v-for="c in chipGroups.poopTexture"
            :key="c"
            variant="chip"
            pressable
            :active="single.poopTexture === c"
            :text="c"
            @click="pickSingle('poopTexture', c)"
          />
        </view>

        <view class="pg-sec"><text>异常标记（仅标记，系统不做医学解读）</text></view>
        <view class="pg-chips">
          <sj-tag
            v-for="c in chipGroups.poopAbnormal"
            :key="c"
            variant="chip"
            pressable
            :active="multi.poopAbnormal.indexOf(c) > -1"
            :text="c"
            @click="toggleMulti('poopAbnormal', c)"
          />
        </view>

        <view class="pg-sec"><text>时间</text></view>
        <sj-datetime-picker class="pk-wrap" mode="time" :value="times.poop" @change="onTimeChange('poop', $event)">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">时间</text>
            <text class="pf-val">{{ times.poop }} ▾</text>
            <text class="pf-unit">{{ todayLabel }}</text>
          </view>
        </sj-datetime-picker>

        <view class="pg-sec"><text>备注</text></view>
        <!-- 备注（sj-textarea：白底描边容器由组件自绘，上限 500 字，超出会被输入框挡在本地） -->
        <sj-textarea v-model="note" placeholder="写点什么…" :maxlength="500" height="176rpx" />
      </block>

      <!-- ========== 体温 ========== -->
      <block v-else-if="type === 'temp'">
        <view class="pg-sec"><text>体温 </text><text class="req">*</text></view>
        <view class="big-temp">
          <text class="bt-num">{{ nums.temp.toFixed(1) }}</text><text class="bt-unit">°C</text>
        </view>
        <!-- 体温录入滑块（sj-slider：35–42℃、步长 0.1、1 位小数，右侧自带值文本；与喂养温度行同规格） -->
        <view class="pg-field">
          <sj-slider v-model="nums.temp" :min="35" :max="42" :step="0.1" :decimals="1" unit=" ℃" />
        </view>
        <view class="pg-chips center">
          <sj-tag
            v-for="c in chipGroups.tempSite"
            :key="c"
            variant="chip"
            pressable
            :active="single.tempSite === c"
            :text="c"
            @click="pickSingle('tempSite', c)"
          />
        </view>
        <view class="pg-hint ok">正常 · 36.0–37.3℃ 显示绿色徽章</view>
        <view class="pg-hint">体温 ≥ 38°C 时显示固定文案：体温偏高，建议咨询医生</view>

        <view class="pg-sec"><text>备注</text></view>
        <!-- 备注（sj-textarea：白底描边容器由组件自绘，上限 500 字，超出会被输入框挡在本地） -->
        <sj-textarea v-model="note" placeholder="写点什么…" :maxlength="500" height="176rpx" />
      </block>

      <!-- ========== 测量 ========== -->
      <block v-else-if="type === 'measure'">
        <view class="pg-sec"><text>测量值 </text><text class="req">*</text><text class="hint-chip" v-if="lastMeasure">上次：{{ lastMeasure.date }} · {{ lastMeasure.by }}</text></view>
        <view class="pg-field">
          <text class="pf-label">身高（cm）</text>
          <!-- 步进器（sj-number-box：步长 0.5cm、0–120cm；单位放 label。0 = 本次不记该项） -->
          <sj-number-box v-model="nums.height" :min="0" :max="120" :step="0.5" class="nb-right" />
        </view>
        <view class="pg-field">
          <text class="pf-label">体重（kg）</text>
          <!-- 步进器（sj-number-box：步长 0.1kg、0–50kg；单位放 label） -->
          <sj-number-box v-model="nums.weight" :min="0" :max="50" :step="0.1" class="nb-right" />
        </view>
        <view class="pg-field">
          <text class="pf-label">头围（cm）</text>
          <!-- 步进器（sj-number-box：步长 0.2cm、0–60cm；单位放 label） -->
          <sj-number-box v-model="nums.head" :min="0" :max="60" :step="0.2" class="nb-right" />
        </view>

        <!-- 测量日期（默认今天；可补录过去日期，occurred_at 用它 + 当前时刻落库） -->
        <view class="pg-sec"><text>测量日期</text></view>
        <sj-datetime-picker class="pk-wrap" mode="date" :value="measureDate" @change="onMeasureDate">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">日期</text>
            <text class="pf-val">{{ measureDate }} ▾</text>
          </view>
        </sj-datetime-picker>

        <view class="pg-sec"><text>测量来源</text></view>
        <view class="pg-chips">
          <sj-tag
            v-for="c in chipGroups.measureSource"
            :key="c"
            variant="chip"
            pressable
            :active="single.measureSource === c"
            :text="c"
            @click="pickSingle('measureSource', c)"
          />
        </view>
        <!-- 机构选择（pg-field 行 + sj-picker 滚轮，选项见 orgOptions；key 随值重建使滚轮默认定位到当前项；来源为家庭自测时隐藏） -->
        <sj-picker v-if="single.measureSource !== '家庭自测'" class="pk-wrap" :key="'org-' + org" :columns="orgOptions" title="机构" :default-index="[Math.max(0, orgOptions.indexOf(org))]" @confirm="onPickOrg">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">机构</text>
            <text class="pf-val">{{ org }}</text>
            <text class="pf-unit">▾</text>
          </view>
        </sj-picker>

        <view class="pg-sec"><text>体检摘要</text></view>
        <!-- 体检摘要（sj-textarea：同备注框规格） -->
        <sj-textarea v-model="summary" placeholder="如：6 月龄儿保，医生口头建议继续观察（仅记录原话，不做解读）" :maxlength="500" height="176rpx" />

        <view class="pg-hint" style="margin-top: 24rpx">保存后自动标点至生长曲线 · 标准来源：WHO 儿童生长标准（2006）</view>
      </block>

      <!-- ========== 用药 ========== -->
      <block v-else-if="type === 'med'">
        <view class="pg-sec"><text>药品名称 </text><text class="req">*</text></view>
        <!-- 药品名称输入（sj-input：无边框透明输入，白底描边容器由页面 .text-input 自绘；30 字足够写清药名） -->
        <view class="text-input">
          <sj-input v-model="medName" :maxlength="30" placeholder="如：维生素 D3 滴剂" />
        </view>

        <view class="pg-sec"><text>剂量与用法</text></view>
        <!-- 单次剂量选择（pg-field 行 + sj-picker 滚轮，选项见 doseOptions） -->
        <sj-picker class="pk-wrap" :key="'dose-' + dose" :columns="doseOptions" title="单次剂量" :default-index="[Math.max(0, doseOptions.indexOf(dose))]" @confirm="onPickDose">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">单次剂量</text>
            <text class="pf-val">{{ dose }}</text>
            <text class="pf-unit">▾</text>
          </view>
        </sj-picker>
        <sj-datetime-picker class="pk-wrap" mode="time" :value="times.med" @change="onTimeChange('med', $event)">
          <view class="pg-field pk-field" hover-class="hover-press" :hover-stay-time="80">
            <text class="pf-label">服用时间</text>
            <text class="pf-val">今天 {{ times.med }} ▾</text>
          </view>
        </sj-datetime-picker>
        <view class="pg-field">
          <text class="pf-label">连续用药中</text>
          <!-- 开关（sj-switch：change 新布尔值直写回 switches.medOngoing，保存时仍由 buildPayload 读取） -->
          <sj-switch class="sw-right" :checked="switches.medOngoing" @change="(v) => (switches.medOngoing = v)" />
        </view>

        <view class="pg-sec"><text>依据来源</text></view>
        <view class="pg-chips">
          <sj-tag
            v-for="c in chipGroups.medBasis"
            :key="c"
            variant="chip"
            pressable
            :active="single.medBasis === c"
            :text="c"
            @click="pickSingle('medBasis', c)"
          />
        </view>
        <view class="pg-hint">用药记录默认仅家庭成员可见 · 系统不提供用药建议与医学解读</view>

        <view class="pg-sec"><text>备注</text></view>
        <!-- 备注（sj-textarea：白底描边容器由组件自绘，上限 500 字，超出会被输入框挡在本地） -->
        <sj-textarea v-model="note" placeholder="写点什么…" :maxlength="500" height="176rpx" />
      </block>

      <!-- ========== 心情（P09 mood：备注式 textarea + 4 情绪 chips + 爱心评分） ========== -->
      <block v-else-if="type === 'mood'">
        <!-- 备注（sj-textarea：白底描边容器由组件自绘，上限 500 字，超出会被输入框挡在本地） -->
        <sj-textarea v-model="note" placeholder="写点什么…" :maxlength="500" height="176rpx" />
        <view class="pg-chips">
          <sj-tag
            v-for="c in chipGroups.moodPick"
            :key="c"
            variant="chip"
            pressable
            :active="single.moodPick === c"
            :text="c"
            @click="pickSingle('moodPick', c)"
          />
        </view>

        <view class="pg-field">
          <text class="pf-label">今日心情</text>
          <!-- 爱心评分（sj-rate：0–5 心，v-model 绑新字段 moodRate，默认 0 即未评分） -->
          <sj-rate v-model="moodRate" :size="22" />
        </view>
      </block>

      <!-- ========== 语音 ========== -->
      <block v-else-if="type === 'voice'">
        <!-- 果冻形象球录音面板：开始/结束录音与试听全在组件内，页面只持有 voice 结果 -->
        <sj-voice-sheet v-model="voice" />
        <view class="pg-sec"><text>备注</text></view>
        <sj-textarea v-model="note" placeholder="记一句当时的情景…" :maxlength="500" height="176rpx" />
      </block>

      <!-- ========== 兜底（未知类型只给备注，同原型 EDITORS[type] || NOTE） ========== -->
      <block v-else>
        <view class="pg-sec"><text>备注</text></view>
        <!-- 备注（sj-textarea：白底描边容器由组件自绘，上限 500 字，超出会被输入框挡在本地） -->
        <sj-textarea v-model="note" placeholder="写点什么…" :maxlength="500" height="176rpx" />
      </block>

      <!-- 底部通栏主按钮（v2 pg-btn） -->
      <sj-button
        class="pg-btn"
        block
        size="lg"
        :loading="saving"
        text="保存记录"
        @click="onSave"
      />
    </view>

    <sj-notify ref="ntf" />
    <sj-ui-host />
  </view>
</template>

<script>
import { TYPES } from '@/utils/mock.js'
import * as api from '@/utils/api.js'
import * as ui from '@/utils/ui.js'
import { play } from '@/utils/sound.js'

/* 当前时间 HH:mm；plusMin 可选，为睡眠结束等场景提供偏移（跨日自动归到 23:59 前循环） */
function nowHHmm(plusMin) {
  const d = new Date(Date.now() + (plusMin || 0) * 60 * 1000)
  const p = x => (x < 10 ? '0' + x : String(x))
  return p(d.getHours()) + ':' + p(d.getMinutes())
}

/* 今天 'YYYY-MM-DD'（测量日期默认值；与 todayKey() 方法同格式） */
function todayKeyStr() {
  const d = new Date()
  const p = x => (x < 10 ? '0' + x : String(x))
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate())
}

export default {
  data() {
    return {
      TYPES,
      /* 类型胶囊行顺序（对齐 v2 P09 设计稿） */
      typeKeys: ['feeding', 'sleep', 'milestone', 'measure', 'poop', 'temp', 'med', 'photo', 'mood', 'voice'],
      type: 'feeding',
      entryId: '',
      photos: [],
      /* 语音录入结果（sj-voice-sheet v-model）：{ duration, wave, segments, url, path, platform } */
      voice: null,
      /* 保存中：照片上传期间禁止重复提交 */
      saving: false,
      statusBarHeight: 20,
      /* 顶栏右侧小字：{宝宝名} · {月龄}（月龄缺失时只显示名字） */
      babyLabel: '',
      /* 测量表单"上次"提示：最近一次测量记录（{ date, by }），无记录时为 null 不显示 */
      lastMeasure: null,
      /* 测量日期（默认今天；补录可改过去日期，保存时并入 occurred_at） */
      measureDate: todayKeyStr(),
      /* 编辑模式记下的原 occurred_at：保存时日期未改则沿用原时间戳（保留原始时刻） */
      measureOccurred: '',
      /* 喂养表单"智能带入"数据源：最近一次有奶量的喂养记录（{ amount, occurred_at }），无记录为 null */
      lastFeeding: null,

      /* 备注 / 体检摘要 / 药品名（各表单共用本地 state） */
      note: '',
      summary: '',
      medName: '维生素 D3 滴剂',
      /* 心情爱心评分（sj-rate，0–5；0 表示未评分，保存并入 mood payload 的 rate 字段） */
      moodRate: 0,

      /* 各类型时间行的时间值（picker mode="time" 要求 HH:mm），默认带入当前时间 */
      times: {
        feeding: nowHHmm(),
        sleepStart: nowHHmm(),
        sleepEnd: nowHHmm(30),
        milestone: nowHHmm(),
        photo: nowHHmm(),
        poop: nowHHmm(),
        temp: nowHHmm(),
        med: nowHHmm()
      },
      /* 机构 / 单次剂量（当前值；选项数据源见下方 orgOptions/doseOptions） */
      org: '区妇幼保健院',
      dose: '400 IU',
      /* 机构 / 剂量滚轮选择器选项（字符串数组显示即取值） */
      orgOptions: ['区妇幼保健院', '社区卫生服务中心', '家庭自测', '其他'],
      doseOptions: ['400 IU', '600 IU', '遵医嘱自定义'],
      /* 睡眠真实计时：开始时间戳（null 表示未开始）；时长见 computed sleepDuration */
      timerStart: null,

      /* 单选组：每组当前选中值 */
      single: {
        feedingMethod: '瓶喂',
        milestonePick: '独坐',
        poopTexture: '金黄糊状',
        tempSite: '腋下',
        measureSource: '儿保医院',
        medBasis: '医生处方',
        moodPick: '开心'
      },
      /* 多选组：数组存选中项 */
      multi: {
        foods: [],
        poopAbnormal: []
      },
      /* 辅食食材自定义：输入面板开关与输入值 */
      foodCustomOpen: false,
      foodCustom: '',
      /* 里程碑自定义：输入面板开关与输入值（点"自定义"展开，添加后并入 chips 并选中） */
      msCustomOpen: false,
      msCustom: '',
      /* 步进器数值（Number，sj-number-box v-model 契约；限幅/步长由控件 :min/:step 接管） */
      nums: {
        feeding: 120,
        temp: 37.0,
        duration: 12,
        height: 67.5,
        weight: 7.8,
        head: 43.2
      },
      switches: {
        dateUncertain: false,
        medOngoing: true
      },
      chipGroups: {
        feedingMethod: ['瓶喂', '母乳亲喂', '辅食'],
        foods: ['高铁米粉', '南瓜泥', '苹果泥', '+ 自定义'],
        milestonePick: ['独坐', '爬行', '扶站', '叫爸爸妈妈', '自定义'],
        poopTexture: ['金黄糊状', '成形软便', '稀水样', '绿色'],
        poopAbnormal: ['血丝', '黏液', '颜色异常', '量异常'],
        tempSite: ['腋下', '耳温', '额温'],
        measureSource: ['儿保医院', '家庭自测'],
        medBasis: ['医生处方', '药品说明书', '其他'],
        moodPick: ['开心', '惊喜', '平静', '担忧']
      }
    }
  },

  computed: {
    /* 返回钮切图：ctl-v2 59 举左向箭头指示牌，随主题换肤（与 sj-navbar 一致） */
    backIconSrc() {
      return `/static/icons/ctl/${this.__theme}/56/59-ctl-nav-back.png`
    },
    /* 「今天 · X 月 X 日」实时日期（替代原型写死日期） */
    todayLabel() {
      const d = new Date()
      return '今天 · ' + (d.getMonth() + 1) + ' 月 ' + d.getDate() + ' 日'
    },
    pageTitle() {
      /* 编辑模式（query.id 存在）显示「编辑记录」，否则「添加记录」 */
      return this.entryId ? '编辑记录' : '添加记录'
    },
    /* 标题后的当前记录类型徽标：随 switchType 实时联动 */
    typeLabel() {
      return (this.TYPES[this.type] || {}).label || ''
    },
    /* 睡眠时长：由 times.sleepStart / sleepEnd 实时计算（结束早于开始视为跨夜） */
    sleepDuration() {
      const toMin = s => {
        const [h, m] = String(s || '').split(':').map(Number)
        return Number.isFinite(h) && Number.isFinite(m) ? h * 60 + m : null
      }
      const start = toMin(this.times.sleepStart)
      const end = toMin(this.times.sleepEnd)
      if (start === null || end === null) return '—'
      let mins = end - start
      if (mins < 0) mins += 24 * 60
      if (mins === 0) return '0 分'
      const h = Math.floor(mins / 60)
      const m = mins % 60
      return h > 0 ? h + ' 小时 ' + (m > 0 ? m + ' 分' : '') : m + ' 分'
    }
  },

  onLoad(query) {
    try {
      this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20
    } catch (e) { /* 保持默认 */ }
    /* 顶栏宝宝标签：名字必有，月龄可选 */
    const b = api.getBaby()
    if (b) this.babyLabel = b.age ? b.name + ' · ' + b.age : b.name
    /* 测量表单"上次"提示：取最近一条测量记录的日期与来源（getMeasures 已按日期倒序） */
    const ms = api.getMeasures()
    if (ms.length) this.lastMeasure = ms[0]
    /* 喂养表单"智能带入"：上次奶量作为本次默认值并展示真实提示（无记录保持默认 120、不显示提示） */
    this.lastFeeding = api.getLastFeeding()
    if (this.lastFeeding) this.nums.feeding = this.lastFeeding.amount
    /* mood/voice 等须为已注册类型（note 历史别名经 TYPES 命中 mood 同族配置） */
    if (query && query.type && TYPES[query.type]) this.type = query.type
    /* 编辑模式：按 id 载入已有记录回填表单（fetchEntry 附带原始 payload，可回填类型专属字段） */
    if (query && query.id) {
      this.entryId = query.id
      api.fetchEntry(query.id).then(e => {
        if (!e) {
          this.$refs.ntf.show({ type: 'err', message: '记录不存在' })
          return
        }
        if (TYPES[e.type]) this.type = e.type
        this.note = e.note || ''
        /* 按类型把 payload 回填到表单控件（体温/奶量/睡眠区间/测量值等各类型专属字段） */
        this.hydrate(e)
        /* 里程碑回填：按 payload.name 选中对应 chip；自定义里程碑不在预置清单中，先并入选项再选中 */
        if (e.type === 'milestone' && e.payload && e.payload.name) {
          const nm = e.payload.name
          const g = this.chipGroups.milestonePick
          if (g.indexOf(nm) === -1) {
            const at = g.indexOf('自定义')
            g.splice(at > -1 ? at : g.length, 0, nm)
          }
          this.single.milestonePick = nm
        }
        /* 已有照片回填（fetchEntry 返回 payload.photos / entry_media 的展示地址） */
        if (Array.isArray(e.photos) && e.photos.length) this.photos = e.photos.slice()
        /* 语音回填：payload.voice（旧数据）或 type=voice 的顶层语音字段，切到试听态 */
        if (e.type === 'voice') {
          const v = (e.payload && (e.payload.voice || e.payload)) || null
          if (v && v.duration) this.voice = { segments: [], wave: [], url: '', path: '', ...v }
        }
      }).catch(() => { /* 保留空表单 */ })
    }
  },

  methods: {
    /**
     * 返回上级页面：栈内只有本页时（分享链接/刷新直达编辑页）navigateBack 会静默失败，
     * 此时回退到首页；正常入栈时用 navigateBack，失败同样兜底回首页。
     */
    goBack() {
      const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
      if (pages && pages.length > 1) {
        uni.navigateBack({ delta: 1, fail: () => uni.reLaunch({ url: '/pages/index/index' }) })
        return
      }
      uni.reLaunch({ url: '/pages/index/index' })
    },
    /* 类型胶囊：只切换表单，不清空已填内容（编辑模式同样允许切换） */
    switchType(k) {
      this.type = k
    },
    /* 单选组：点击替换 active */
    pickSingle(key, val) {
      /* 里程碑的"自定义"不是选项，点击展开自定义输入行 */
      if (key === 'milestonePick' && val === '自定义') {
        this.msCustomOpen = !this.msCustomOpen
        return
      }
      this.single[key] = val
    },
    /* 机构 / 单次剂量：sj-picker 滚轮选择（confirm 载荷 value 为各列文案数组，单列取 [0]） */
    onPickOrg(e) {
      this.org = e.value[0]
    },
    onPickDose(e) {
      this.dose = e.value[0]
    },
    /* 多选组（异常标记 / 辅食食材）：点击 toggle */
    toggleMulti(key, val) {
      /* 辅食食材的“+ 自定义”不是选项，点击展开自定义输入行 */
      if (key === 'foods' && val === '+ 自定义') {
        this.foodCustomOpen = !this.foodCustomOpen
        return
      }
      const arr = this.multi[key]
      const i = arr.indexOf(val)
      if (i > -1) arr.splice(i, 1)
      else arr.push(val)
    },
    /* 自定义食材：加入选项列表（插在“+ 自定义”前）并自动选中 */
    addCustomFood() {
      const v = (this.foodCustom || '').trim()
      if (!v) {
        this.$refs.ntf.show({ type: 'warn', message: '请输入食材名称' })
        return
      }
      const g = this.chipGroups.foods
      const at = g.indexOf('+ 自定义')
      if (g.indexOf(v) === -1) g.splice(at > -1 ? at : g.length, 0, v)
      if (this.multi.foods.indexOf(v) === -1) this.multi.foods.push(v)
      this.foodCustom = ''
      this.foodCustomOpen = false
    },
    /* 自定义里程碑：加入选项列表（插在"自定义"前）并自动选中 */
    addCustomMilestone() {
      const v = (this.msCustom || '').trim()
      if (!v) {
        this.$refs.ntf.show({ type: 'warn', message: '请输入里程碑名称' })
        return
      }
      const g = this.chipGroups.milestonePick
      const at = g.indexOf('自定义')
      if (g.indexOf(v) === -1) g.splice(at > -1 ? at : g.length, 0, v)
      this.single.milestonePick = v
      this.msCustom = ''
      this.msCustomOpen = false
    },
    /* 时间选择器（picker mode="time"）选中回填 */
    onTimeChange(k, e) {
      this.times[k] = e.detail.value
    },
    /* 测量日期选择回填（sj-datetime-picker date 模式回传 'YYYY-MM-DD'） */
    onMeasureDate(e) {
      this.measureDate = e.detail.value
    },
    /* 睡眠真实计时：首次点击开始，再次点击结束并回填睡眠区间与时长 */
    onTimer() {
      if (!this.timerStart) {
        this.timerStart = Date.now()
        this.$refs.ntf.show({ type: 'ok', message: '已开始计时' })
        /* 计时开始播音效 */
        play('T01')
        return
      }
      const now = Date.now()
      const p = x => (x < 10 ? '0' + x : String(x))
      const hhmm = t => { const d = new Date(t); return p(d.getHours()) + ':' + p(d.getMinutes()) }
      this.times.sleepStart = hhmm(this.timerStart)
      this.times.sleepEnd = hhmm(now)
      this.timerStart = null
      this.$refs.ntf.show({ type: 'ok', message: '计时结束 · 已回填睡眠区间' })
      /* 计时结束音效：夜间时段（22:00–07:00）只振动不发声，其余时段正常播 */
      const nh = new Date().getHours()
      play('T04', (nh >= 22 || nh < 7) ? { vibrateOnly: true } : {})
    },
    /* 选图由 sj-photo-picker 内部完成（拍照/相册 + 缩略图回显），页面只持有 photos 数组 */
    /* 'YYYY-MM-DD'（用于睡眠区间等需要日期的 payload） */
    todayKey() {
      const d = new Date()
      const p = x => (x < 10 ? '0' + x : String(x))
      return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate())
    },
    /**
     * 编辑模式回显：把已有记录的 payload 写回各表单控件（buildPayload 的逆映射）。
     * 缺失字段保持表单默认值；时间行优先取保存时随 payload 落库的 times 全量映射，
     * 旧记录无 times 时按记录发生时间 occurred_at 派生 HH:mm。
     */
    hydrate(e) {
      const p = e.payload || {}
      const num = (k, v) => { const n = parseFloat(v); if (!isNaN(n)) this.nums[k] = n }
      /* 单选值仍在预置选项内才回填（自定义值由各类型单独处理） */
      const pick = (key, val, group) => { if (val && group.indexOf(val) > -1) this.single[key] = val }
      const t = p.times || {}
      const m = /[T ](\d{2}:\d{2})/.exec(String(e.occurred_at || ''))
      const hm = m ? m[1] : ''
      const setTime = (k, v) => { if (/^\d{1,2}:\d{2}$/.test(String(v || ''))) this.times[k] = v }
      switch (this.type) {
        case 'feeding':
          pick('feedingMethod', p.method, this.chipGroups.feedingMethod)
          num('feeding', p.amount); num('temp', p.temp); num('duration', p.duration)
          if (Array.isArray(p.foods)) {
            /* 自定义食材不在预置清单：先并入 chips（插在「+ 自定义」前）再选中 */
            p.foods.forEach(f => {
              if (f && f !== '+ 自定义' && this.chipGroups.foods.indexOf(f) === -1) {
                const at = this.chipGroups.foods.indexOf('+ 自定义')
                this.chipGroups.foods.splice(at > -1 ? at : this.chipGroups.foods.length, 0, f)
              }
            })
            this.multi.foods = p.foods.slice()
          }
          setTime('feeding', t.feeding || hm)
          break
        case 'sleep': {
          /* payload.start/end 形如 'YYYY-MM-DD HH:mm'，取尾部 HH:mm 回填时间行 */
          const tail = s => /^\d{2}:\d{2}$/.test(String(s || '').slice(-5)) ? String(s).slice(-5) : ''
          setTime('sleepStart', t.sleepStart || tail(p.start) || hm)
          setTime('sleepEnd', t.sleepEnd || tail(p.end))
          break
        }
        case 'milestone':
          setTime('milestone', t.milestone || hm)
          /* 日期不确定：保存时落 backfill 徽标，回显原路取回 */
          this.switches.dateUncertain = e.badge === 'backfill'
          break
        case 'photo':
          setTime('photo', t.photo || hm)
          break
        case 'poop':
          pick('poopTexture', p.texture, this.chipGroups.poopTexture)
          if (Array.isArray(p.abnormal)) this.multi.poopAbnormal = p.abnormal.slice()
          setTime('poop', t.poop || hm)
          break
        case 'temp':
          num('temp', p.value)
          pick('tempSite', p.site, this.chipGroups.tempSite)
          setTime('temp', t.temp || hm)
          break
        case 'measure':
          num('height', p.height); num('weight', p.weight); num('head', p.head)
          pick('measureSource', p.source, this.chipGroups.measureSource)
          if (p.org && this.orgOptions.indexOf(p.org) > -1) this.org = p.org
          /* measure 表单无备注框：保存时体检摘要写入 note，回显原路取回 */
          this.summary = e.note || ''
          /* 测量日期回填：取原 occurred_at 的日期部分；原完整时间戳记下，保存时日期未改可原样沿用 */
          this.measureOccurred = String(e.occurred_at || '')
          if (/^\d{4}-\d{2}-\d{2}$/.test(this.measureOccurred.slice(0, 10))) {
            this.measureDate = this.measureOccurred.slice(0, 10)
          }
          break
        case 'med':
          if (p.name) this.medName = p.name
          if (p.dose && this.doseOptions.indexOf(p.dose) > -1) this.dose = p.dose
          pick('medBasis', p.basis, this.chipGroups.medBasis)
          if (typeof p.ongoing === 'boolean') this.switches.medOngoing = p.ongoing
          setTime('med', t.med || hm)
          break
        case 'mood': {
          /* 历史 title 格式「心情 · X」：X 在预置情绪内才选中；rate 限幅 0–5 */
          const mm = /·\s*(.+)$/.exec(String(p.title || ''))
          if (mm) pick('moodPick', mm[1].trim(), this.chipGroups.moodPick)
          const r = parseInt(p.rate, 10)
          if (!isNaN(r)) this.moodRate = Math.min(5, Math.max(0, r))
          break
        }
        /* voice / 未知类型：payload 回填由 onLoad 既有的语音分支处理，此处不动 */
      }
    },
    /* 表单 state → summary.js 定义的 payload 字段（示例形状见 utils/mock.js） */
    buildPayload() {
      const n = k => parseFloat(this.nums[k]) || 0
      switch (this.type) {
        case 'feeding':
          return {
            method: this.single.feedingMethod,
            amount: n('feeding'),
            temp: n('temp'),
            duration: n('duration'),
            foods: this.multi.foods
          }
        case 'sleep': {
          const day = this.todayKey()
          return { period: '午睡', start: day + ' ' + this.times.sleepStart, end: day + ' ' + this.times.sleepEnd }
        }
        case 'milestone':
          return { name: this.single.milestonePick }
        case 'photo':
          return { photos: this.photos, video: 0 }
        case 'measure':
          return {
            height: n('height'),
            weight: n('weight'),
            head: n('head'),
            source: this.single.measureSource,
            org: this.single.measureSource === '家庭自测' ? '' : this.org
          }
        case 'poop':
          return { texture: this.single.poopTexture, abnormal: this.multi.poopAbnormal }
        case 'temp':
          return { value: n('temp'), site: this.single.tempSite }
        case 'med':
          return {
            name: this.medName,
            dose: this.dose,
            basis: this.single.medBasis,
            ongoing: this.switches.medOngoing
          }
        case 'mood':
          /* 独立 rate 字段并入（不改 title 旧格式，历史记录不受影响；0 即未评分） */
          return { title: '心情 · ' + this.single.moodPick, rate: this.moodRate }
        case 'voice': {
          /* 未录（或录完又取消）时给空壳，saveEntry 会跳过上传 */
          const v = this.voice || {}
          return {
            duration: v.duration || 0,
            wave: v.wave || [],
            segments: v.segments || [],
            url: v.url || '',
            path: v.path || '',
            platform: v.platform || ''
          }
        }
        default:
          return { title: this.note }
      }
    },
    async onSave() {
      if (this.saving) return
      if (this.type === 'voice' && !(this.voice && this.voice.duration)) {
        this.$refs.ntf.show({ type: 'warn', message: '先录一段宝宝的声音再保存' })
        /* 表单校验失败拦截保存时播音效 */
        play('S04')
        return
      }
      /* 里程碑自定义面板里已输入但没点「添加」的名称：保存时自动落选，
         否则 buildPayload 仍取旧选中值，用户以为已改成自定义、实际保存的还是原选项 */
      if (this.type === 'milestone' && this.msCustomOpen && (this.msCustom || '').trim()) {
        this.addCustomMilestone()
      }
      /* 测量日期不能晚于今天 */
      if (this.type === 'measure' && this.measureDate > todayKeyStr()) {
        this.$refs.ntf.show({ type: 'warn', message: '测量日期不能晚于今天' })
        play('S04')
        return
      }
      /* 测量三项全 0 = 没填：直接落库会生成一条空记录点，曲线上看不出区别 */
      if (this.type === 'measure' && !Number(this.nums.height) && !Number(this.nums.weight) && !Number(this.nums.head)) {
        this.$refs.ntf.show({ type: 'warn', message: '至少填写身高、体重或头围其中一项' })
        play('S04')
        return
      }
      /* 用药：药名是这条记录的唯一标识，空着保存以后无法辨认吃的是什么 */
      if (this.type === 'med' && !(this.medName || '').trim()) {
        this.$refs.ntf.show({ type: 'warn', message: '请填写药品名称' })
        play('S04')
        return
      }
      /* 睡眠：起止相同（或没填）会存出 0 分钟记录，多半是误触 */
      if (this.type === 'sleep' && this.times.sleepStart === this.times.sleepEnd) {
        this.$refs.ntf.show({ type: 'warn', message: '睡眠的开始与结束时间相同，请检查' })
        play('S04')
        return
      }
      const localPhotos = this.photos.filter(p => !/^(https?:|\/api\/|data:|blob:)/i.test(String(p || '')))
      /* 语音分段同理：blob:/temp 路径都要先传 /files 换云端地址 */
      const localVoice = this.type === 'voice'
        ? (this.voice.segments || []).filter(s => s && !/^(https?:|\/api\/)/i.test(String(s.url || s.path || '')))
        : []
      this.saving = true
      /* 串行逐张上传 + 落库，1~15 秒量级：全屏阻断，避免用户以为没响应而重复提交或切页 */
      const busy = localPhotos.length
        ? '正在上传 ' + localPhotos.length + ' 张照片…'
        : (localVoice.length ? '正在上传 ' + localVoice.length + ' 段语音…' : '正在保存记录…')
      const ld = ui.loading(busy, { sub: (localPhotos.length || localVoice.length) ? '保持应用打开，勿切后台' : '', timeout: 180000 })
      const entry = {
        type: this.type,
        /* 保存 payload 时一并带上各时间行的当前值 */
        payload: { ...this.buildPayload(), times: this.times },
        /* measure 表单无备注框，体检摘要文本作为记录备注 */
        note: this.type === 'measure' ? (this.summary || this.note) : this.note,
        photos: this.photos
      }
      if (this.entryId) entry.id = this.entryId
      /* 测量自定义日期：occurred_at = 所选日期 + 当前时刻；编辑时日期未改则沿用原时间戳（保留原始时刻） */
      if (this.type === 'measure') {
        entry.occurred_at = (this.measureOccurred && String(this.measureOccurred).slice(0, 10) === this.measureDate)
          ? this.measureOccurred
          : this.measureDate + ' ' + nowHHmm()
      }
      if (this.type === 'milestone' && this.switches.dateUncertain) entry.backfill = true
      /* 里程碑首次达成判定：必须在调用 saveEntry 前采样缓存——
         saveEntry 内部会先乐观更新把 done 置 true，调用后再查就永远"已达成"；
         编辑已有记录（entryId）不算首次 */
      const msKey = this.type === 'milestone' && !this.entryId ? String(this.single.milestonePick || '') : ''
      const msFirst = !!msKey && !api.getMilestones().some(m => m.name === msKey && m.done)
      let saved = false
      try {
        await api.saveEntry(entry)
        saved = true
        /* NFR-06：保存成功音效只在服务端确认（上方 await 的 REST 成功 resolve）之后播 */
        play('S03')
        /* 测量记录：生长曲线新数据点落位音效（音量极低，S03 之后顺序叠加一次 E03） */
        if (this.type === 'measure') play('E03')
        /* 里程碑类型首次达成叠加 E01（key 绑定变体）；普通记录只播 S03 不叠加 */
        if (msFirst) play('E01', { key: msKey })
        /* 成功提示走 sj-notify 顶部横幅；延迟返回让横幅完整可见后再收起 */
        this.$refs.ntf.show({ type: 'ok', message: '已保存' })
        /* 延迟返回让「已保存」提示可见；goBack 内含无上级页面时的兜底 */
        setTimeout(() => this.goBack(), 1600)
      } catch (e) {
        /* 失败保留表单（只读模式下服务端返回 403） */
        ui.error(e, '保存失败')
        /* 保存失败/无网络时播音效 */
        play('S05')
      } finally {
        ld.close()
        /* 成功后不再解锁：新建记录走的是「每次点击生成新 id」的路径，
           1.6s 提示窗口内再按一次保存会落成两条重复记录 */
        if (!saved) this.saving = false
      }
    }
  }
}
</script>

<style lang="scss" scoped>
/* 页面底：v2 奶油色；正文用圆润显示字族体系 */
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
  color: var(--sj-ink);
  box-shadow: var(--sj-sh-sm);
  flex: none;
}
.bk:active { transform: scale(0.92); }
.bk-ic { width: 56rpx; height: 56rpx; }
/* 标题行：标题 + 当前记录类型徽标（整行占位，右侧宝宝标签不受影响） */
.pg-title-row { flex: 1; display: flex; align-items: center; gap: 14rpx; min-width: 0; }
.pg-title {
  font-family: var(--sj-font-display);
  font-size: 40rpx;
  font-weight: 900;
  color: var(--sj-ink);
  flex: none;
}
/* 类型徽标（沿用 hint-chip 的 primary-soft 胶囊规范，尺寸略收） */
.pg-type {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  padding: 4rpx 18rpx;
  border-radius: var(--sj-r-pill);
  flex: none;
}
.pg-baby { font-size: 22rpx; color: var(--sj-sub); flex: none; }

/* ---------- 类型胶囊行（横向滚动 scroll-view） ---------- */
.type-scroll {
  width: 100%;
  white-space: nowrap;
}
.type-chips {
  display: inline-block;
  white-space: nowrap;
  padding: 0 32rpx 24rpx;
}
/* 胶囊本体外观由 sj-tag（variant=chip）提供，此处仅保留横向滚动间距 */
.tchip { margin-right: 16rpx; }

/* ---------- 表单内容区：左右 32rpx，元素间距 24rpx ---------- */
.form-wrap { padding: 8rpx 32rpx 80rpx; }

/* 分组小标题（v2 pg-sec：前置圆角短条 + 12px 字） */
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
.hint-chip {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  padding: 6rpx 20rpx;
  border-radius: var(--sj-r-pill);
}

/* 喂养方式单选行（sj-radio ×3 横排；原该行 pg-chips 自绘样式由控件库接管，pg-chips 仍服务其余行） */
.radio-row { display: flex; flex-wrap: wrap; align-items: center; gap: 36rpx; margin-bottom: 24rpx; }

/* chips 单选 / 多选（v2 pg-chips） */
.pg-chips { display: flex; flex-wrap: wrap; gap: 16rpx; margin-bottom: 24rpx; }
.pg-chips.center { justify-content: center; }

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
/* label 宽 240rpx + 禁换行：带单位标签（如「本次奶量（ml）」，全角括号实际渲染宽于估算）保持单行 */
.pf-label { color: var(--sj-sub); font-weight: 700; flex: none; width: 240rpx; white-space: nowrap; }
.pf-val { flex: 1; color: var(--sj-ink); font-weight: 800; }
.pf-val-right { text-align: right; }
.pf-unit { color: var(--sj-faint); font-size: 24rpx; flex: none; }
/* 滚轮包裹层（sj-picker / sj-datetime-picker 共用）：组件根为 inline-flex，作为 .pg-field 外层时补拉伸 + 满宽，
   保持行布局不变；弹层挂在玻璃行外，fixed 面板不被 .pg-field 的 backdrop-filter 包含块困住（贴视口底部） */
.pk-wrap { width: 100%; }
.pk-field { flex: 1; width: 100%; }
.pk-field .pf-val { text-align: right; }

/* 提示文案行（v2 pg-hint：cream 底 + 虚线边；ok/bad 语义变体） */
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
.pg-hint.ok { color: #2E7D4F; border-color: #BFE6CF; background: #EDF9F2; }
.pg-hint.bad { color: #B04A4A; border-color: #F3C4C4; background: #FDF0F0; }

/* 步进器行内布局：sj-number-box 右对齐（原自绘 .num-stepper 由控件库接管；单位统一放 label，不再行内展示） */
.nb-right { margin-left: auto; }

/* 辅食食材自定义输入行（输入与按钮外观由 sj-input / sj-button 承担，此处只做容器与排布） */
.custom-row { display: flex; align-items: center; gap: 16rpx; margin-bottom: 20rpx; }
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

/* 已选食材（sj-tag chip 选中态，点击移除） */
.custom-picked { display: flex; flex-wrap: wrap; align-items: center; gap: 12rpx; margin-bottom: 20rpx; }
.cp-label { font-size: 22rpx; color: var(--sj-faint); }

/* 药品名称输入容器（v2：毛玻璃面 + 半透高光边 + 28rpx 圆角；输入本身由 sj-input 承担，无边框透明嵌入） */
.text-input {
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
  margin-bottom: 24rpx;
  transition: border-color 0.2s var(--sj-smooth), box-shadow 0.2s var(--sj-smooth);
}
.text-input:focus-within {
  border-color: var(--sj-primary);
  box-shadow: var(--sj-glass-hi), 0 8rpx 28rpx rgba(247, 161, 92, 0.22);
}

/* 睡眠计时按钮（v2 软底胶囊） */
.timer-btn {
  width: 100%;
  font-size: 28rpx;
  font-weight: 900;
  color: var(--sj-primary-deep);
  background: var(--sj-primary-soft);
  border: 2rpx solid var(--sj-line);
  padding: 24rpx 0;
  border-radius: var(--sj-r-pill);
  text-align: center;
  box-sizing: border-box;
  margin-bottom: 24rpx;
  transition: transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.timer-btn:active { transform: scale(0.97); }

/* 体温大字（v2 font-display 粗体主色深） */
.big-temp { text-align: center; padding: 8rpx 0 24rpx; }
.bt-num { font-family: var(--sj-font-display); font-size: 96rpx; font-weight: 900; color: var(--sj-primary-deep); }
.bt-unit { font-size: 32rpx; color: var(--sj-faint); vertical-align: super; }

/* 开关行内布局：sj-switch 右对齐（原自绘 .pg-sw 由控件库接管） */
.sw-right { margin-left: auto; }
/* 主按钮：外观由 sj-button（block size=lg）统一提供，此处仅保留布局 */
.pg-btn {
  display: flex;
  margin-top: 40rpx;
}
</style>
