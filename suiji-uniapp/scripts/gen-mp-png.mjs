/**
 * 小程序 SVG 兜底 PNG 生成脚本（第 9 项一期）
 *
 * 微信小程序 <image> 不支持 SVG（尤其 Android 真机），本脚本把 static/anim 与
 * static/loading 下所有 .svg 渲染为 3× 同名 .png，供组件在 MP-WEIXIN 条件编译下切换后缀。
 *
 * 动效 SVG 取基础帧（resvg 不执行 CSS animation，渲染 <style> 前的静态状态），
 * 一期先保证"有图"，二期再补 sprite 帧动画。
 *
 * 用法：node scripts/gen-mp-png.mjs
 * 依赖：@resvg/resvg-js（devDependency）
 */
import { Resvg } from '@resvg/resvg-js'
import { readFileSync, writeFileSync, readdirSync } from 'node:fs'
import { join, basename, extname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const SCALE = 3
const DIRS = ['src/static/anim', 'src/static/loading']
let count = 0

for (const dir of DIRS) {
  const abs = join(__dirname, '..', dir)
  const files = readdirSync(abs).filter(f => extname(f) === '.svg')
  for (const f of files) {
    const svg = readFileSync(join(abs, f), 'utf8')
    const png = basename(f, '.svg') + '.png'
    try {
      const r = new Resvg(svg, { fitTo: { mode: 'zoom', value: SCALE } })
      const data = r.render().asPng()
      writeFileSync(join(abs, png), data)
      count++
    } catch (e) {
      console.error(`FAIL ${dir}/${f}: ${e.message}`)
    }
  }
}
console.log(`已生成 ${count} 张 3× PNG`)
