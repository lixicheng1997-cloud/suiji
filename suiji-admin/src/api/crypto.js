/**
 * 岁记 · 应用层传输加密（客户端侧）
 *
 * 为什么要有这一层
 * ----------------
 * 客户端与服务端之间是明文 HTTP（nginx 30080），链路上任何一跳都能看到原文：
 * 登录口令、JWT 三件套、邀请码、导出数据全部裸奔。所以在应用层再做一层端到端加密——
 * 即便链路被看穿，拿到的也只是密文。
 *
 * 算法（与服务端 app/core/crypto.py 严格对应）
 * ------------------------------------------
 *   密钥封装  RSA-OAEP-256（SHA-256 + MGF1-SHA256，空 label）：加密随机会话密钥 CEK
 *   内容加密  AES-256-CBC(PKCS7) + HMAC-SHA256，Encrypt-then-MAC（先加密再签名）
 *   密钥派生  encKey = SHA256(CEK || "suiji:enc:v1")，macKey = SHA256(CEK || "suiji:mac:v1")
 *   绑定上下文  HMAC 覆盖 kid / 时间戳 / 方向(req|resp) / path，密文不能跨接口搬运
 *
 * 为什么不直接用 RSA 加密报文：RSA-2048 单次最多装 190 字节，装不下请求体。
 * 为什么不用 GCM：crypto-js 没有 GCM 实现；Encrypt-then-MAC 的 CBC+HMAC 是 TLS 1.2
 * 同款构造，且两端都是库原生实现，比自己手写 GHASH 更不容易出错。
 *
 * 依赖边界：只依赖已装好的 crypto-js，不引入 jsencrypt / node-forge。
 * RSA 用原生 BigInt 做模幂（e=65537 只需 17 轮平方-乘，毫秒级），
 * OAEP 编码用 crypto-js 的 SHA-256 拼出来，整个文件零新增依赖。
 */
import CryptoJS from 'crypto-js'

export const ENC_NAME = 'A256CBC-HS256'
export const ALG_NAME = 'RSA-OAEP-256'
const SCHEMA_V = 1
const CEK_BYTES = 32
const IV_BYTES = 16
const DERIVE_ENC = 'suiji:enc:v1'
const DERIVE_MAC = 'suiji:mac:v1'

/* ============================================================
 * 1. 字节 / 编码工具
 * ============================================================ */
function toWA(u8) {
  const words = []
  for (let i = 0; i < u8.length; i++) {
    words[i >>> 2] = (words[i >>> 2] || 0) | ((u8[i] & 0xff) << (24 - (i % 4) * 8))
  }
  return CryptoJS.lib.WordArray.create(words, u8.length)
}

function toBytes(wa) {
  const words = wa.words
  const n = wa.sigBytes
  const out = new Uint8Array(n)
  for (let i = 0; i < n; i++) out[i] = (words[i >>> 2] >>> (24 - (i % 4) * 8)) & 0xff
  return out
}

function utf8(s) {
  return toBytes(CryptoJS.enc.Utf8.parse(String(s)))
}

export function b64e(u8) {
  return CryptoJS.enc.Base64.stringify(toWA(u8))
}

export function b64d(s) {
  return toBytes(CryptoJS.enc.Base64.parse(String(s)))
}

/** base64url → 字节（JWK 的 n / e 用这种编码，无 padding） */
function b64urlToBytes(s) {
  let t = String(s).replace(/-/g, '+').replace(/_/g, '/')
  while (t.length % 4) t += '='
  return b64d(t)
}

function concatBytes() {
  const parts = Array.prototype.slice.call(arguments)
  let total = 0
  for (let i = 0; i < parts.length; i++) total += parts[i].length
  const out = new Uint8Array(total)
  let off = 0
  for (let i = 0; i < parts.length; i++) {
    out.set(parts[i], off)
    off += parts[i].length
  }
  return out
}

function sha256(u8) {
  return toBytes(CryptoJS.SHA256(toWA(u8)))
}

function hmacSha256(keyU8, msgU8) {
  return toBytes(CryptoJS.HmacSHA256(toWA(msgU8), toWA(keyU8)))
}

/** 常数时间比较：不等长直接 false，等长时逐字节累积差异（不提前退出） */
function safeEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false
  let diff = 0
  for (let i = 0; i < a.length; i++) diff |= (a[i] ^ b[i])
  return diff === 0
}

/* ============================================================
 * 2. 随机数
 *
 * 三端能力不一致：H5 在非安全上下文（http://IP:端口）拿不到 crypto.getRandomValues，
 * 小程序只有异步的 wx.getRandomValues，App 端两者都没有。
 * 这里的做法是「真随机熵池 + 本地熵混合扩散」：启动时异步预取一次系统随机（拿不到
 * 就用时间/计数器兜底），之后每次取随机数都把熵池、计数器、Math.random 一起进 SHA-256。
 * 底线：即便某端的 Math.random 可被预测，只要熵池里有一次真随机，输出就不可预测。
 * ============================================================ */
let entropyPool = null

function localEntropy() {
  const out = new Uint8Array(32)
  for (let i = 0; i < out.length; i++) out[i] = Math.floor(Math.random() * 256)
  return out
}

function systemRandom(len) {
  return new Promise(resolve => {
    // #ifdef MP-WEIXIN
    if (typeof wx !== 'undefined' && wx.getRandomValues) {
      try {
        wx.getRandomValues({
          length: len,
          success: r => resolve(r && r.randomValues ? new Uint8Array(r.randomValues) : null),
          fail: () => resolve(null)
        })
        return
      } catch (e) { /* 往下走 */ }
    }
    // #endif
    try {
      const g = typeof globalThis !== 'undefined' ? globalThis.crypto : null
      if (g && g.getRandomValues) {
        const a = new Uint8Array(len)
        g.getRandomValues(a)
        resolve(a)
        return
      }
    } catch (e) { /* 往下走 */ }
    resolve(null)
  })
}

/** 预取系统熵（并发安全：只取一次）。加解密前调用，失败也不阻断。 */
export async function ensureEntropy() {
  if (entropyPool) return entropyPool
  const got = await systemRandom(32)
  entropyPool = got && got.length ? got : concatBytes(localEntropy(), utf8(String(Date.now())))
  return entropyPool
}

let prngCounter = 0
export function randomBytes(n) {
  const out = new Uint8Array(n)
  let off = 0
  while (off < n) {
    const c = ++prngCounter
    const seed = concatBytes(
      entropyPool || new Uint8Array(0),
      new Uint8Array([c & 0xff, (c >>> 8) & 0xff, (c >>> 16) & 0xff, (c >>> 24) & 0xff]),
      utf8(String(Date.now())),
      localEntropy()
    )
    const block = sha256(seed)
    for (let i = 0; i < block.length && off < n; i++) out[off++] = block[i]
  }
  return out
}

/* ============================================================
 * 3. RSA-OAEP-256（BigInt 模幂 + 自写 OAEP 编码）
 * ============================================================ */
function bytesToBigInt(u8) {
  let hex = '0x'
  for (let i = 0; i < u8.length; i++) hex += ('0' + u8[i].toString(16)).slice(-2)
  return BigInt(hex)
}

function bigIntToBytes(value, len) {
  let hex = value.toString(16)
  if (hex.length % 2) hex = '0' + hex
  const bytes = hex.length / 2
  if (bytes > len) throw new Error('RSA 输出超长')
  const out = new Uint8Array(len)   // 前补零到固定长度（I2OSP）
  for (let i = 0; i < bytes; i++) {
    out[len - bytes + i] = parseInt(hex.substr(i * 2, 2), 16)
  }
  return out
}

function modPow(base, exp, mod) {
  let result = 1n
  let b = base % mod
  let e = exp
  while (e > 0n) {
    if (e & 1n) result = (result * b) % mod
    e >>= 1n
    b = (b * b) % mod
  }
  return result
}

/** MGF1(seed, len)：OAEP 的掩码生成函数（RFC 8017） */
function mgf1(seed, len) {
  const out = new Uint8Array(len)
  let off = 0
  let counter = 0
  while (off < len) {
    const c = new Uint8Array([(counter >>> 24) & 0xff, (counter >>> 16) & 0xff,
      (counter >>> 8) & 0xff, counter & 0xff])
    const block = sha256(concatBytes(seed, c))
    for (let i = 0; i < block.length && off < len; i++) out[off++] = block[i]
    counter++
  }
  return out
}

function xorBytes(a, b) {
  const out = new Uint8Array(a.length)
  for (let i = 0; i < a.length; i++) out[i] = a[i] ^ b[i]
  return out
}

/** 大整数的字节长度（I2OSP 的长度参数 = 模数字节数） */
function byteLengthOf(value) {
  let hex = value.toString(16)
  if (hex.length % 2) hex = '0' + hex
  return hex.length / 2
}

/** RSA/ECB/OAEPWithSHA-256AndMGF1Padding（与 cryptography 的 padding.OAEP(SHA256) 一致） */
function rsaEncryptOaep(msg, n, e, k) {
  const hLen = 32
  if (msg.length > k - 2 * hLen - 2) throw new Error('RSA 明文过长')
  const lHash = sha256(new Uint8Array(0))
  const ps = new Uint8Array(k - msg.length - 2 * hLen - 2)   // 全 0
  const db = concatBytes(lHash, ps, new Uint8Array([0x01]), msg)
  const seed = randomBytes(hLen)
  const dbMask = mgf1(seed, k - hLen - 1)
  const maskedDb = xorBytes(db, dbMask)
  const seedMask = mgf1(maskedDb, hLen)
  const maskedSeed = xorBytes(seed, seedMask)
  const em = concatBytes(new Uint8Array([0x00]), maskedSeed, maskedDb)
  return bigIntToBytes(modPow(bytesToBigInt(em), e, n), k)
}

/* ============================================================
 * 4. 会话密钥与报文加解密
 * ============================================================ */
let keyInfo = null    // { kid, n: BigInt, e: BigInt, k }

/** 服务端下发的公钥（/crypto/public-key）：内部只保留模数与指数 */
export function setPublicKey(info) {
  if (!info || !info.n || !info.e) return null
  const n = bytesToBigInt(b64urlToBytes(info.n))
  const e = bytesToBigInt(b64urlToBytes(info.e))
  keyInfo = { kid: info.kid || '', n: n, e: e, k: byteLengthOf(n) }
  return keyInfo.kid
}

export function getKeyId() {
  return keyInfo ? keyInfo.kid : ''
}

/** 作废本地公钥缓存：服务端轮换密钥（客户端 kid 失效）时重新拉取 */
export function clearPublicKey() {
  keyInfo = null
}

export function hasPublicKey() {
  return !!keyInfo
}

function context(kid, ts, direction, path) {
  return utf8('suiji:v1|' + kid + '|' + ts + '|' + direction + '|' + path)
}

function deriveKeys(cek) {
  return {
    enc: sha256(concatBytes(cek, utf8(DERIVE_ENC))),
    mac: sha256(concatBytes(cek, utf8(DERIVE_MAC)))
  }
}

function sealBytes(cek, iv, plain, ctx) {
  const k = deriveKeys(cek)
  const cipher = CryptoJS.AES.encrypt(toWA(plain), toWA(k.enc), {
    iv: toWA(iv), mode: CryptoJS.mode.CBC, padding: CryptoJS.pad.Pkcs7
  })
  const ct = toBytes(cipher.ciphertext)
  const tag = hmacSha256(k.mac, concatBytes(ctx, iv, ct))
  return { data: b64e(ct), tag: b64e(tag) }
}

function openBytes(cek, iv, ct, tag, ctx) {
  const k = deriveKeys(cek)
  if (!safeEqual(tag, hmacSha256(k.mac, concatBytes(ctx, iv, ct)))) return null
  try {
    const wa = CryptoJS.AES.decrypt({ ciphertext: toWA(ct) }, toWA(k.enc), {
      iv: toWA(iv), mode: CryptoJS.mode.CBC, padding: CryptoJS.pad.Pkcs7
    })
    return toBytes(wa)
  } catch (e) {
    return null
  }
}

/* ============================================================
 * 5. 对外：封装一个加密请求 / 打开一个加密响应
 * ============================================================ */
/**
 * 给敏感接口打包：生成一次性会话密钥，用 RSA 公钥封装后放进 X-Sj-Enc 头。
 *
 * @param {string} path 接口路径（/auth/login 这种，参与 HMAC 绑定，防跨接口搬运密文）
 * @param {object|undefined} payload 请求体对象；GET 等无 body 的请求传 undefined
 * @param {number} [ts] 时间戳（毫秒）；由 http.js 传入「按服务端时间校正过」的 now
 * @returns {{header: object, data: object|undefined, open: Function}|null}
 *          没有公钥时返回 null（调用方按明文发送）
 */
export async function sealRequest(path, payload, ts) {
  if (!keyInfo) return null
  await ensureEntropy()
  const cek = randomBytes(CEK_BYTES)
  const iv = randomBytes(IV_BYTES)
  const stamp = ts || Date.now()
  const wrapped = rsaEncryptOaep(cek, keyInfo.n, keyInfo.e, keyInfo.k)
  const header = {
    'X-Sj-Enc': [SCHEMA_V, keyInfo.kid, stamp, b64e(iv), b64e(wrapped)].join('|')
  }

  let data
  if (payload !== undefined && payload !== null) {
    const sealed = sealBytes(cek, iv, utf8(JSON.stringify(payload)),
      context(keyInfo.kid, stamp, 'req', path))
    data = { v: SCHEMA_V, enc: ENC_NAME, data: sealed.data, tag: sealed.tag }
  }

  return {
    header: header,
    data: data,
    /** 响应用同一条 CEK 加密（服务端生成新 IV）；不是密文包则原样返回 */
    open: body => {
      if (!body || typeof body !== 'object' || body.enc !== ENC_NAME) return body
      const plain = openBytes(cek, b64d(body.iv), b64d(body.data), b64d(body.tag),
        context(keyInfo.kid, stamp, 'resp', path))
      if (!plain) return null
      try {
        /* UTF-8 解码必须跨端一致：App 端（JSCore）没有 TextDecoder，
         * 旧兜底 String.fromCharCode 会把 UTF-8 字节按单字节解释，
         * 中文错误文案（如「用户名或密码错误」）全部变成乱码。
         * crypto-js 的 Utf8.stringify 是纯 JS 实现，三端行为一致。 */
        const text = typeof TextDecoder === 'function'
          ? new TextDecoder().decode(plain)
          : CryptoJS.enc.Utf8.stringify(toWA(plain))
        return JSON.parse(text)
      } catch (e) {
        return null
      }
    }
  }
}

/** 当前环境能否做 RSA（极老的 iOS 小程序可能没有 BigInt） */
export function supported() {
  try {
    return typeof BigInt === 'function'
  } catch (e) {
    return false
  }
}
