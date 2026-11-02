const fs = require('fs')
const path = require('path')
const root = path.resolve(__dirname)
const src = path.join(root, 'src')

function walk (d, out = []) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name)
    if (e.isDirectory()) walk(p, out)
    else out.push(p)
  }
  return out
}

const staticFiles = walk(path.join(src, 'static'))
const codeFiles = walk(src).filter(f => /\.(vue|js|scss|json)$/.test(f) && !f.includes('\\static\\'))
const haystack = codeFiles.map(f => fs.readFileSync(f, 'utf8')).join('\n')

const used = [], dead = []
for (const f of staticFiles) {
  const rel = path.join('static', path.relative(path.join(src, 'static'), f)).split(path.sep).join('/')
  const base = path.basename(f)
  // 组件里 src 是模板拼接（/static/icons/${theme}/${name}.png），需按目录+文件名分别判定
  const dirRefs = haystack.includes(rel.split('/')[1]) || haystack.includes('/' + base)
  const direct = haystack.includes(base) || haystack.includes(rel)
  if (direct) used.push([f, 'named'])
  else if (dirRefs && rel.startsWith('static/icons')) used.push([f, 'dynamic-theme-path'])
  else dead.push(f)
}

const size = f => fs.statSync(f).size / 1024
console.log('--- DEAD (no textual reference anywhere in src code) ---')
let d = 0
for (const f of dead) { d += size(f); console.log(String(Math.round(size(f))).padStart(6) + 'KB  ' + f.split(path.sep).join('/').replace(/\\/g, '/')) }
console.log('dead total:', Math.round(d / 1024) + 'MB')
console.log('\n--- USED files by dir ---')
const byDir = {}
for (const [f] of used) {
  const k = path.dirname(f).replace(/\\/g, '/').replace(/^.*\/src\//, '')
  byDir[k] = byDir[k] || { n: 0, kb: 0 }
  byDir[k].n++; byDir[k].kb += size(f)
}
for (const k of Object.keys(byDir).sort()) console.log(k.padEnd(26), String(byDir[k].n).padStart(3), 'files', String(Math.round(byDir[k].kb)).padStart(6) + 'KB')
