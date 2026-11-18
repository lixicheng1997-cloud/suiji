/**
 * compress-png.mjs · static PNG 有损压缩（libimagequant 调色板量化，等效 pngquant）
 * 用法：node scripts/compress-png.mjs
 * 策略：palette + quality 60~85；仅当结果比原文件小才覆盖（保证可重复执行不劣化）。
 * 注意：gen-mp-png.mjs 重新生成 PNG 后需重跑本脚本。
 */
import { readdirSync, statSync, readFileSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import sharp from 'sharp'

const ROOT = new URL('../src/static/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (name.toLowerCase().endsWith('.png')) out.push(p)
  }
  return out
}

const files = walk(ROOT)
let before = 0, after = 0, saved = 0, checked = 0
for (const f of files) {
  const src = readFileSync(f)
  before += src.length
  checked++
  try {
    const buf = await sharp(src).png({ palette: true, quality: 85, effort: 7 }).toBuffer()
    if (buf.length < src.length) {
      writeFileSync(f, buf)
      after += buf.length
      saved += src.length - buf.length
      console.log(`- ${(relative(ROOT, f))}: ${(src.length / 1024).toFixed(1)}K -> ${(buf.length / 1024).toFixed(1)}K`)
    } else {
      after += src.length
    }
  } catch (e) {
    after += src.length
    console.log(`! 跳过 ${relative(ROOT, f)}: ${e.message}`)
  }
}
console.log(`\n共 ${checked} 张 PNG，压缩前 ${(before / 1024).toFixed(1)}K，压缩后 ${(after / 1024).toFixed(1)}K，节省 ${(saved / 1024).toFixed(1)}K（${((saved / before) * 100).toFixed(1)}%）`)
