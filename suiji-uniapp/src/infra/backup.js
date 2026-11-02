/**
 * 岁记 · 备份包加解密（TDD §7）
 * 导出：给了密码就出加密包（AES-256-CBC + PBKDF2），没给才落明文 JSON（兼容旧行为）。
 * 导入：兼容旧版加密包（parsePack）与云端版明文包。
 * 完整性：manifest 记录明文 sha256，解密后校验，校验失败中止且不落库。
 *
 * 备份文件会离开应用（下载目录、分享给微信/邮件、网盘），里面是宝宝姓名、
 * 生日、生长数据与照片台账——明文落盘等于绕过服务端鉴权把整份数据交出去。
 */
import CryptoJS from 'crypto-js'

/** 备份包格式标识（明文包与加密包共用，靠有无 cipher 区分） */
export const FORMAT = 'suiji-backup'

const ITERATIONS = 10000

function sha256(s) {
  return CryptoJS.SHA256(s).toString(CryptoJS.enc.Hex)
}

function deriveKey(password, saltHex) {
  return CryptoJS.PBKDF2(password || 'suiji', CryptoJS.enc.Hex.parse(saltHex), {
    keySize: 256 / 32, iterations: ITERATIONS
  })
}

/** 导出：把快照打成加密包（返回值是可直接写入文件的文本） */
export function buildPack(data, password) {
  const salt = CryptoJS.lib.WordArray.random(16)
  const iv = CryptoJS.lib.WordArray.random(16)
  const key = CryptoJS.PBKDF2(password || 'suiji', salt, { keySize: 256 / 32, iterations: ITERATIONS })
  const plain = JSON.stringify(data)
  const cipher = CryptoJS.AES.encrypt(plain, key, {
    iv: iv, mode: CryptoJS.mode.CBC, padding: CryptoJS.pad.Pkcs7
  }).toString()
  return JSON.stringify({
    format: FORMAT,
    enc: { salt: salt.toString(CryptoJS.enc.Hex), iv: iv.toString(CryptoJS.enc.Hex), iterations: ITERATIONS },
    cipher: cipher,
    manifest: { data_sha256: sha256(plain), created_at: new Date().toISOString() }
  })
}

/** 导入：解密 + 校验；任何一步失败抛错，调用方不得落库 */
export function parsePack(text, password) {
  let pack
  try { pack = JSON.parse(text) } catch (e) { throw new Error('备份包已损坏，无法解析') }
  if (!pack) throw new Error('备份包已损坏，无法解析')
  if (pack.format !== FORMAT) throw new Error('不是岁记备份包')
  const { enc, cipher, manifest } = pack
  if (!enc || !cipher) throw new Error('备份包缺少加密信息')
  if (!password) throw new Error('这是加密备份包，请输入密码')
  const key = deriveKey(password, enc.salt)
  let plain
  try {
    plain = CryptoJS.AES.decrypt(cipher, key, {
      iv: CryptoJS.enc.Hex.parse(enc.iv), mode: CryptoJS.mode.CBC, padding: CryptoJS.pad.Pkcs7
    }).toString(CryptoJS.enc.Utf8)
  } catch (e) { /* 下方统一判空 */ }
  if (!plain) throw new Error('密码错误或备份包损坏，未导入')
  if (sha256(plain) !== (manifest && manifest.data_sha256)) {
    throw new Error('备份包校验失败（sha256 不匹配），未导入')
  }
  try {
    return { data: JSON.parse(plain), manifest }
  } catch (e) {
    throw new Error('备份包内容异常，未导入')
  }
}
