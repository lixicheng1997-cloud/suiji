# 岁记 v3.0 前后端 API 契约（云端轻量版）

> 本文件是 suiji-server（FastAPI）与 suiji-uniapp（uni-app）的唯一协调基准。
> 上游依据：《岁记-宝宝成长记录App-技术设计文档-TDD-v3.0》§5/§6/§8。
> 基础路径 `/api/v1`；鉴权 `Authorization: Bearer <JWT access>`；401 未认证 / 403 越权或只读 / 404 / 422 校验失败。
> 时间统一 UTC ISO8601 字符串（如 `2026-10-23T12:00:00Z`）。

## 0. 设计原则（缓存镜像模式）

- 客户端启动时调 `GET /bootstrap` 一次性拉取当前家庭全量数据，填充内存缓存；
  页面所有同步读取（getBaby/fetchEntries/getGrowth/…）只读缓存，**签名与旧本地版完全一致**。
- 写操作：客户端先乐观更新缓存，再调 REST；REST 成功 Promise 才 resolve，失败 reject（页面已有错误提示）。
- 记录的派生字段（title/meta/badge/photo 摘要）由客户端计算后随请求提交，服务端原样存储（导出/多端一致时以存储值为准）。
- 百分位：服务端在写入 measurement 时用同一张 WHO 参考表计算并落 `growth_point`，留痕权威在服务端。

## 1. 数据行形状（与客户端旧 db 行一致，snake_case）

```jsonc
// baby
{ "id":"baby_xxx", "name":"小满", "birth_date":"2026-03-01", "gestational_weeks":40,
  "gender":"boy|girl", "birth_length":50.0, "birth_weight":3.3, "avatar":"", 
  "is_active":1, "created_at":"...", "updated_at":"..." }
// entry（核心表；软删 deleted_at 非空即回收站）
{ "id":"e_xxx", "baby_id":"baby_xxx", "type":"feeding|sleep|milestone|measure|poop|temp|med|photo|note|mood|voice",
  "occurred_at":"...", "created_at":"...", "updated_at":"...", "is_backfilled":0,
  "note":"", "creator":"妈妈 · 李芳", "title":"", "meta":"", "badge":"", "photo":"<url或''>",
  "payload":{...}, "deleted_at":null }
// entry_media
{ "id":"md_xxx", "entry_id":"e_xxx", "baby_id":"", "storage_key":"...", "url":"/api/v1/media/{id}",
  "local_path":"<url>", "sha256":"", "size":0, "width":0, "height":0 }
// measurement
{ "id":"m_xxx", "entry_id":"e_xxx", "baby_id":"", "metric":"height|weight|head", "value":7.2,
  "occurred_at":"...", "corrected_age_flag":0 }
// milestone_record（建档时服务端按清单自动初始化该宝宝全部条目）
{ "id":"msr_xxx", "baby_id":"", "name":"翻身", "domain":"大运动", "month":"4-7月",
  "ref":"4-7 月龄", "done":false, "achieved_at":"", "source_entry_id":"", "creator":"", "sort":0 }
// vaccine（建档时服务端按内置国家免疫规划排期自动生成）
{ "id":"v_xxx", "code":"bcg", "baby_id":"", "n":"卡介苗", "dose":"第 1 剂", "age":"出生时",
  "months":0, "cls":"一类", "sort":0, "plan_date":"2026-03-01", "done":false, "done_date":"",
  "org":"", "lot":"", "remind":true, "remind_lead":7, "created_at":"...", "updated_at":"..." }
// ai_journal
{ "id":"j_xxx", "baby_id":"", "range":"3月1日 – 3月7日 · 周记草稿", "range_start":"2026-03-01",
  "range_end":"2026-03-07", "paras":[{"text":"...","cites":["e_xxx"]}], "status":"draft|archived",
  "model_version":"gpt|template", "prompt_version":"v1", "fact_count":0, "created_at":"...", "updated_at":"..." }
// member（avatar/relation 取该用户 setting.parent.avatar / setting.parent.relation，家长信息页保存；未设置为空串）
{ "id":"usr_xxx", "name":"妈妈", "role":"creator|member", "color":"#FF6B8B", "avatar":"/api/files/xxx/download", "relation":"妈妈" }
// setting（每用户一个 JSON 对象，键与旧 db.getSetting 一致）
{ "account":{...}, "parent":{...}, "switches":{...}, "consent":{...}, "remind":{...},
  "elder":{...}, "backupFlags":{...}, "family":{...}, "ai":{...}, "trash":[...] }
```

## 1.5 传输加密（敏感接口端到端加密）

客户端与服务端之间是明文 HTTP，口令 / 令牌 / 邀请码 / 导出数据在链路上裸奔，
故对下列敏感接口叠加一层应用层端到端加密（**不是** HTTPS 的替代，是纵深防御）：

| 接口 | 加密内容 |
| --- | --- |
| `POST /auth/register` `POST /auth/login` `POST /auth/password` | 请求：口令；响应：令牌三件套 |
| `POST /auth/refresh` `POST /auth/logout` | 请求：refresh；响应：新令牌 |
| `POST /family/join` | 请求：邀请码 |
| `POST /family/invite` | 响应：生成的邀请码 |
| `GET /export/data` | 响应：全量家庭数据 |

**算法**：`RSA-OAEP-256`（SHA-256 + MGF1-SHA256）封装一次性会话密钥 CEK(32B)
+ `A256CBC-HS256`（AES-256-CBC + HMAC-SHA256，Encrypt-then-MAC）加密报文。
密钥派生 `enc=SHA256(CEK||"suiji:enc:v1")` / `mac=SHA256(CEK||"suiji:mac:v1")`；
HMAC 覆盖 `suiji:v1|kid|ts|req|resp|path`，密文不能跨接口搬运。

**公网接口**：`GET /crypto/public-key` → `{alg, enc, kid, pem, n, e, max_bytes}`
（JWK 形式的 `n`/`e` 供无 ASN.1 解析器的小程序 / App 直接使用）。

**请求头**：`X-Sj-Enc: <v>|<kid>|<ts_ms>|<iv_b64>|<rsa(cek)_b64>`
**请求体**（有 body 时）：`{"v":1,"enc":"A256CBC-HS256","data":"<b64>","tag":"<b64>"}`
**响应体**（请求加密时）：`{"v":1,"enc":"A256CBC-HS256","iv":"<b64>","data":"<b64>","tag":"<b64>"}`
**GET 无 body**：只发 `X-Sj-Enc` 头，用于加密响应（如 `/export/data`）。

**服务端开关** `CRYPTO_MODE`：`off` 关闭 / `optional` 加密明文都收（默认，兼容旧客户端与冒烟脚本）
/ `required` 清单内接口明文一律 `400`（客户端全量升级后必须开启，否则中间人剥掉头即可强制降级）。
时间戳偏移超过 `CRYPTO_TS_WINDOW`（默认 300s）返回 `400`；`kid` 不匹配返回 `409`（客户端重取公钥后重试）。

## 2. 认证 `/auth`

| 方法 路径 | 入参 | 出参 |
| --- | --- | --- |
| POST `/auth/register` | `{username, password, name?}` | `{access, refresh, media, user:{id,name,username}, family:null, need_family:true}`；**注册只建账号，不代建家庭**；用户名已占用返回 `409 {"detail":"用户名「x」已被注册，请换一个"}`（detail 即可直接展示的文案，客户端在注册页钉在账号行下方） |
| POST `/auth/login` | `{username, password}` | 已关联家庭：`{access, refresh, media, user, family:{id,name,readonly,role}, need_family:false}`；未关联（新注册 / 被创建者移除后回落）返回 `{access, refresh, media, user, family:null, need_family:true}` |
| POST `/auth/refresh` | `{refresh}` | `{access, refresh, media, need_family}`；**refresh 一次性轮换**，客户端必须整组覆盖本地令牌 |
| POST `/auth/logout` | `{refresh?, all?}` | `{ok:true}`；撤销当前 access，并作废传入的 refresh（需 Bearer access）；`all:true` 额外抬高用户水位线，使本账号**所有设备**已签发的令牌立即失效 |
| POST `/auth/password` | `{old_password, new_password}` | `{access, refresh, media, user, need_family}`；校验旧密码后写新哈希，**抬高用户水位线**（旧令牌全部失效），并为当前设备重签三件套（无需重新登录） |
| GET `/auth/me` | — | `{user, family:{id,name,readonly,role}\|null, need_family}` |

JWT payload：`{user_id, family_id, role, type, jti, iat, iat_ms, exp}`。三类令牌互不通用：

| type | 寿命 | 用途 |
| --- | --- | --- |
| `access` | 2 小时 | 业务接口 `Authorization: Bearer` |
| `refresh` | 30 天 | 仅 `POST /auth/refresh`，**用一次即失效**；重放判定为泄露，抬高该用户水位线使全部令牌失效 |
| `media` | 24 小时 | 仅 `/files/*/download`、`/media/{id}` 下载；**不能调用任何业务接口**，用于替代把 access 塞进 `<img src>` 的 query |

**下载端点的令牌位置约束**：`?token=` 只接受 `media` 令牌——它会落进 nginx 日志、浏览器历史与
Referer。`access` 令牌只能走 `Authorization` 头，放进 query 一律 403。

撤销：`jti` 进 Redis 黑名单（登出/轮换）、用户水位线 `epoch`（refresh 重放、改密、登出全部设备）。
Redis 不可用时降级进程内存（**临时降级，到点自动重连**，见 `core/session_store.py`），单副本语义不变。
密码 bcrypt。

**认证端点限流**（无鉴权即可调用，必须有配额）：注册 5 次/小时、登录 10 次/5 分钟、refresh 60 次/5 分钟、
`/family/join` 10 次/5 分钟、上传 60 次/5 分钟（按客户端 IP，配额见 `core/config.py`）。
超限时返回 `429 {"detail":"操作太频繁，请 N 秒后再试"}` 并带 `Retry-After`。
注册密码要求：≥8 位、首尾无空格、不能是纯数字或纯字母（`PASSWORD_MIN_LENGTH` 可调）。

**家庭强制关联（need_family）**：账号必须属于某个家庭才能使用业务能力，两条关联路径为
① `POST /family`（输入家庭名称创建）② `POST /family/join`（输入家庭邀请码加入）。
账号与家庭为「唯一归属」关系（§4.0）：一个用户同一时刻只能关联 1 个家庭。
未完成关联时服务端对所有业务路由返回 `409 {"detail":"need_family"}`，放行范围仅限 `/auth/*`、
`/bootstrap`（引导页据此读取「当前无家庭」状态并在建家/加入后灌缓存）与 `/family/*`
（创建、加入、邀请码、成员管理）。`/files`、`/media` 的下载端点支持 `?token=` 直连，
其门控写在各端点内部以保证无 token 仍按契约返回 403。

## 3. 引导 `/bootstrap`

GET `/bootstrap` → 全量快照（一次请求填充客户端缓存）：

```json
{ "user":{...}, "family":{"id","name","readonly","role","events_version","members":[member...]},
  "active_baby_id":"", "babies":[baby...], "entries":[entry...未软删],
  "measurements":[...], "media":[...], "milestone_records":[...], "vaccines":[...],
  "journals":[...], "settings":{...}, "trash":[entry...已软删（含 deleted_at/deleted_by）] }
```

## 4. 家庭 `/family`

| 方法 路径 | 说明 |
| --- | --- |
| GET `/family` | `{family, members}` |
| POST `/family` | `{name?}` → 创建新家庭并归属为 creator，返回 `{family, members}`；已关联家庭 422 |
| POST `/family/invite` | 创建者→`{code, expires_at}`（7 天有效，可重复生成即失效旧的） |
| POST `/family/join` | `{code}` → **与当前家庭解绑后**加入为 member，返回 `{family, members, left_family}`；重复加入 422 |
| PATCH `/family/readonly` | `{readonly:bool}` 仅创建者 |
| PATCH `/family/members/{user_id}` | `{role:"creator|member"}` 仅创建者（转让/设管理员用） |
| DELETE `/family/members/{user_id}` | 创建者移除成员；移除自己 422 |
| GET `/family/audit?limit=200&days=180` | 操作留痕列表 `{"items":[audit_log...]}`（FR-22，见 §4.1） |
| POST `/family/audit/export` | 客户端本机导出（备份包/成长档案）上报一次「导出」留痕，服务端不可观测时由客户端调用 |

只读开关置位后，非创建者所有写接口返回 403 `{detail:"只读模式"}`。

### 4.0 家庭归属唯一

- 一个用户同一时刻**只能关联 1 个家庭**：`user.family_id` 是唯一归属指针，`family_member` 中同一 user 至多 1 行（服务端在每次归属变更时清理历史异常行）。
- 换家庭的唯一路径是**凭其他家庭的邀请码加入**：`POST /family/join` 先与当前家庭解绑（删除其成员行），再归属到新家庭。
- 解绑只改归属，**个人相关信息不变**：账号、昵称、设置（`settings`）一律不动；原家庭里的宝宝档案、记录、媒体仍留在该家庭，本人切换后不再可见。
- 创建者加入其他家庭时，把创建者身份自动交给原家庭最早加入的成员（并同步 `family.creator_id`），避免家庭无人管理；无人可交时家庭与其数据保留，创建者字段不变（本人日后被移出时可回落到自己创建的家庭）。
- 已关联家庭的账号不能再 `POST /family` 自建家庭（422）；创建者不能 `DELETE /family/members/{自己}`（422）。
- 响应 `left_family`：`{id, name} | null`——本次被解绑的原家庭；客户端据此提示用户并丢弃旧家庭缓存。
- 成员被移除后同样与该家庭解绑：优先回落到其自己创建的家庭，否则归属置空（`need_family` → 引导页二选一）。

### 4.1 操作留痕 `audit_log`（FR-22）

```jsonc
// audit_log（服务端写入，无对外增改删接口，成员不可删除）
// GET /family/audit 读取时：actor_name 按 actor_id 实时解析当前展示名（家长信息 parent.name 昵称 → User.name 注册昵称，
// 均无则为「家人」，绝不透出登录账号）；actor_relation 取家长信息 parent.relation（与宝宝关系，未设置为空串）
{ "id":"a_xxx", "action":"create|invite|join|leave|role|readonly|delete|purge|export|wipe",
  "actor_id":"usr_xxx", "actor_name":"妈妈", "actor_relation":"妈妈", "target_type":"family|member|entry|trash|data",
  "target_id":"...", "text":"创建家庭空间「小满的家」", "created_at":"2026-10-21T16:42:00Z" }
```

- 写入时机（服务端同一事务内）：创建家庭 / 生成邀请码 / 凭码加入 / 移除成员（退出）/ 角色变更 / 只读开关 / 记录软删 / 彻底删除（单条与清空回收站）/ 服务端导出 `GET /export/data` / 清空家庭数据 `DELETE /account/data`。
- 凭码加入其他家庭时，除向新家庭写 `join`，还向**原家庭**写一条 `leave`（创建者离开时另加一条 `role`，记录创建者身份交接）。
- 客户端本机导出（`exportBackup` / `exportArchive`）在落盘成功后回调 `POST /family/audit/export` 补一条 `export` 留痕；失败不影响导出结果。
- 读取：`GET /family/audit` 返回近 `days` 天（默认 180，与保留期一致）内本家庭留痕，按 `created_at desc` 倒序；`family_id` 为空（未关联家庭）返回空数组。
- 保留 180 天：超出窗口的行不返回（剥离/清理由服务端保留策略负责），全员可读，越权按家庭隔离。

## 5. 宝宝 `/babies`

| 方法 路径 | 说明 |
| --- | --- |
| GET `/babies` | 列表（含 is_active） |
| POST `/babies` | 创建；**服务端同时为该宝宝初始化 milestone_records（内置清单）与 vaccines（按 birth_date 排期）**；首个宝宝自动 active |
| PUT `/babies/{id}` | 更新（birth_date 变化时重排疫苗 plan_date，保留接种状态） |
| POST `/babies/{id}/activate` | 切换当前档案 |

## 6. 记录 `/entries`

| 方法 路径 | 说明 |
| --- | --- |
| POST `/entries` | 请求头 `Idempotency-Key`（客户端 UUID）；body 为 entry 行（含 payload/title/meta/badge/photo）；type=measure 时按 payload 生成 measurement 行并算百分位；type=milestone 且 payload.name 匹配时更新该宝宝对应 milestone_record.done；响应 `{id, ...row}`。补录（`is_backfilled=1`）静默，其余新建给家庭其他成员各落一条 `/notifications` 行（§6.6） |
| PUT `/entries/{id}` | 全量更新行；measure 类型重建 measurement。**不通知家人**（误触编辑会刷屏），仅 bump `events_version` 让他人重拉对齐 |
| DELETE `/entries/{id}` | 软删（deleted_at=now, deleted_by=操作人名）→ 进回收站；通知其他成员「X 删除了…」（§6.6） |
| POST `/entries/{id}/restore` | 恢复；通知其他成员「X 恢复了…」（§6.6） |
| DELETE `/entries/trash/{id}` | 彻底删除（连同 measurement/media） |
| DELETE `/entries/trash` | 清空回收站 |
| GET `/entries?baby=&type=&cursor=&limit=20` | 游标分页（MVP 客户端主要用 bootstrap，此端点供搜索/后续） |

## 6.5 增量探测 `/events`（家人动态实时通知 · 方案 A 纯轮询）

| 方法 路径 | 说明 |
| --- | --- |
| GET `/events/count?since=<entry水位>&ver=<版本水位>` | 需鉴权 + 家庭门控。**轮询唯一请求**，返回 `{count, cursor, version, changed, new_entries, notices}`：count=本家庭未软删且 `entry.id > since` 的记录数；version=`family.events_version` 当前值；changed = count>0 或 version>ver（首次探测 `since`/`ver` 皆空时为 false；`ver` 是宽松字符串参数，空串与非数字一律按 0 处理——客户端首轮发的是 `ver=`，声明成 int 会直接 422 断掉首探）；**new_entries = count>0，只有它才是真需要重拉快照**；cursor=新 entry 水位（无新增时原样回传 since）；notices=本人未读通知（形状同 `GET /notifications`，上限 50 条）。客户端 App 前台每 30s（`config/app.js` `MESSAGE_POLL_INTERVAL`）轮询一次，通知直接吃本响应的 `notices`，**不再**串行补一个 `GET /notifications`；弹窗去重走本地账本（sj_notices），故本端点不区分操作人 |

> 节流约定（上一次卡顿就是这三条没守住）：
> 1. **一周期一请求**：探测与取通知合并——弱网下两个串行请求就是肉眼可见的卡顿。
>    唯一例外是 `new_entries=true` 那一轮：客户端随后要重拉快照，`/bootstrap` 链路
>    仍会带一次 `GET /notifications`（冷启动/下拉刷新靠它补弹），账本按 id 去重不会重复弹；
> 2. **只在 `new_entries` 时重拉 `/bootstrap`**：疫苗打卡、里程碑勾选、删除/恢复都只
>    bump `events_version` 而不新增 entry id，为它们重下全家快照（entries +
>    measurements + media + journals 全量）的代价与记录数成正比；这类变更的数据对齐
>    交给冷启动 bootstrap 与下拉刷新，操作者本机本来就已乐观更新；
> 3. **维护型扫描不挂在读路径上**：`GET /notifications` 原先每次调用都跑一遍
>    `purge_old_notifications`（全表过期 DELETE + 按用户 GROUP BY 计数），跟着轮询
>    频率跑等于把清理成本摊到每一次读上；现在只由 6 小时后台任务负责。

> 版本变化时客户端需**就地推进** `sj_events_ver`（不重拉也要推进，否则每次轮询都会
> 重复判定 changed 白跑一趟）；两个水位都落本机：`sj_events_cursor`（entry id）与
> `sj_events_ver`（events_version），冷启动时从 `/bootstrap` 的 `family.events_version` 对齐，
> 避免把存量记录当成新动态补弹。

> 游标为什么用 `entry.id` 而不是 `created_at`：created_at 由客户端以 `'YYYY-MM-DD HH:mm'` 本地时间写入，服务端兜底才是 UTC `'...Z'`，两种格式混存时字符串比较会错乱（空格 < 'T'）；id 两端同算法生成（base36 毫秒时间戳 + 随机段），字典序即时间序，是稳定水位线。已知限制：离线创建、延迟同步的记录（id 时间戳早于当前水位）轮询探测不到，但数据随下次 bootstrap / 下拉刷新出现。

## 6.6 家庭通知 `/notifications`（站内投递 · 读后即删）

服务端在同一事务里按**收件人 user_id 逐人落一行** `notification`（精确排除操作者本人，
永不误弹自己），客户端拉取后「已读即删」，因此 GET 返回的就是本人全部未读，无需已读状态列。

| 方法 路径 | 说明 |
| --- | --- |
| GET `/notifications` | 需鉴权 + 家庭门控。返回 `{items:[{id,type,title,content,actor,entry_id,created_at}]}`，时间倒序、上限 200 条。**不跑清理**（保留 30 天 / 单人 200 条由 `main.py` 的 6 小时后台任务收敛）；前台轮询请直接用 `/events/count` 携带的 `notices`，本端点只留给消息中心手动刷新等场景 |
| POST `/notifications/read` | `{ids:[...]}` 逐条删行；`ids` 省略或为空 = 本人全部已读（全删）。返回 `{ok,count,read_at}` |
| 记录人展示口径 | `entry.creator`、`Notification.actor` 与动态文案里的操作人一律「与宝宝关系在前、昵称在后」（`rows.actor_label`，如「妈妈 · 李芳」；关系为空只剩昵称，两者皆无落「家人」）。`family.members[].name` 仍是昵称优先、关系另列在 `.relation`（`display_name`），供家庭卡两列分开显示，两个口径不可互换 |

投递触发面（`services/notify_service.py::notify_family`，每次投递同时 bump `events_version`）：

| type | 触发点 | 文案 |
| --- | --- | --- |
| `feed` | POST `/entries`（补录除外） | 「X 记录了一次喂养「瓶喂 120ml」」——voice=录了一段声音、note=记了一条随手记，poop/temp/med 统一「记录了一次照护情况」，不含健康数值 |
| `delete` | DELETE `/entries/{id}` | 「X 删除了「标题」」 |
| `restore` | POST `/entries/{id}/restore` | 「X 恢复了「标题」」 |
| `milestone` | PUT `/milestones/{id}` 且**未达成 → 达成** | 「X 达成了里程碑「第一次翻身」」 |
| `vaccine` | PUT `/vaccines/{id}` 置 done；POST `/vaccines/sync` 批量置 done | 单剂「X 完成了疫苗接种「乙肝 第1剂」」；批量合并为一条「…：A、B 等 N 剂」 |
| `journal` | POST `/journals/generate` 成功 | 「X 生成了成长日记（10-24 – 10-30 · 周记草稿）」 |

状态跃迁才投递（done false→true、记录新增/删除/恢复），反复改日期、取消达成、编辑记录都不通知。
`entry_id` 供客户端直达记录详情页；milestone 无 entry 时回落时光轴。

> 离线送达限制：无第三方推送通道（既未接 UniPush，也未做微信订阅消息），轮询仅在 App 前台运行，
> 退后台/被杀期间的通知留在库里，靠下次冷启动 `bootstrap → pullServerNotices` 补弹。

## 7. 媒体 `/media`

| 方法 路径 | 说明 |
| --- | --- |
| POST `/media` | multipart `file`（+ 可选 `entry_id`）→ `{id, storage_key, url:"/api/v1/media/{id}", sha256, size}`；字节入对象存储（MinIO，MEDIA_BACKEND=local 时退化为本地磁盘），库里只存路径；同时登记一条 `entry_media` 类型文件台账（见 §7.5） |
| GET `/media/{id}` | 需鉴权，返回文件字节（Header Bearer 或 `?token=` 传 media 令牌；无/非法/已撤销 token 403） |

客户端保存含照片记录时：先逐张 POST /media 拿 url，回填 entry.photo / payload.photos 后再 POST /entries。

## 7.5 非结构化文件 `/files`

统一的文件接口：任何非结构化数据（照片、附件、体检报告、音频、导出包…）的字节只进 MinIO，结构化库只保留 `storage_key`（对象路径）与元信息。

| 方法 路径 | 说明 |
| --- | --- |
| POST `/files` | multipart `file` + 可选 `business_type`（entry/baby/entry_media/other…）、`business_id`、`baby_id`；挂载点必须属于当前家庭，否则 404；同家庭+同内容+同挂载点直接复用已有行 |
| POST `/files/batch` | multipart `files`（多个）+ 同一组挂载参数 → `{items, errors, count}`；单个失败不中断其余 |
| GET `/files?business_type=&business_id=&baby_id=&keyword=&limit=50&offset=0` | 分页列表（按创建时间倒序）→ `{items, total, limit, offset}`；keyword 匹配原始文件名 |
| GET `/files/{id}` | 文件行详情 |
| PATCH `/files/{id}` | `{business_type?, business_id?, baby_id?, original_name?, meta?}` 改名/挂载/改挂业务；内容与 storage_key 不可变 |
| DELETE `/files/{id}` | 删除台账行；同家庭无其他引用时才真正删除对象存储中的字节 |
| GET `/files/{id}/download?token=&inline=0` | 下载字节（鉴权：`Authorization: Bearer` 用 access/media，或 `?token=` 传 **media 令牌**；access 放 query 一律 403——它会落进日志与 Referer。无/非法/已撤销 token 403）。`inline=1` 且内容类型属图片/音视频/PDF 时才走服务端代理并带 `Content-Disposition: inline`；**其余类型强制 `attachment`**，避免上传的 HTML 被同源渲染成存储型 XSS |
| GET `/files/{id}/url?expires=` | 临时直链（MinIO 预签名）；有效期由服务端封顶 `MEDIA_URL_MAX_EXPIRES`（默认 3600s），客户端传再大也无效。本地磁盘后端 `url=null`，请走 `/download` |

**上传类型白名单**（`/files`、`/files/batch`、`/media` 共用，见 `app/media/safety.py`）：
扩展名必须是 jpg/jpeg/png/gif/webp/bmp/heic/heif/avif/tiff、mp4/mov/m4v/webm/3gp、
mp3/m4a/aac/wav/ogg/flac、pdf/txt/csv/json/zip 之一；并按 magic bytes 嗅探真实类型——
声明与实际不符（如 `.png` 实为 HTML）一律 422。库里登记的 `content_type` 取嗅探结果，不回显客户端传值。
| GET `/files/stats` | 当前家庭 `{count, total_size, by_business_type[]}` |

文件行形状：

```json
{
  "id": "file_xxx", "business_type": "entry", "business_id": "ent_xxx", "baby_id": "",
  "original_name": "体检报告.pdf", "content_type": "application/pdf", "ext": ".pdf",
  "storage_key": "fam_xxx/2026-10-24/体检报告.pdf",
  "url": "/api/v1/files/file_xxx/download",
  "sha256": "...", "size": 102400, "uploader_id": "usr_x",
  "created_at": "...", "updated_at": "", "meta": {}
}
```

要点：

- `storage_key` 即对象存储路径，格式为 `{family_id}/{YYYY-MM-DD}/{文件名}`：家庭一级目录做数据隔离、日期二级目录按天归档、末级保留原始文件名（非法字符替换为 `_`，超 96 字符截断并保留扩展名）。
- 同家庭同内容（sha256）复用同一对象：一条字节可有多条台账引用；同一天上传同名但内容不同的文件，末尾自动追加 `_<sha前8位>` 避免覆盖。
- 上传为流式处理（分块算 sha256，超限 `FILE_MAX_BYTES` 默认 200MB 返回 422），不把整份文件读进内存。
- 彻底删除记录（`DELETE /entries/trash/{id}`）会连同挂在它上面的文件一起释放（引用计数为 0 才删字节）。
- 环境变量：`MEDIA_BACKEND=minio`、`MINIO_*`、`FILE_MAX_BYTES`、`MEDIA_URL_EXPIRES`、`MEDIA_DOWNLOAD_MODE`、`MEDIA_PATH_DATE_UTC`（日期目录取 UTC）。

## 8. 疫苗 `/vaccines`

| 方法 路径 | 说明 |
| --- | --- |
| GET `/vaccines?baby_id=` | 当前宝宝剂次（服务端建档已排期） |
| PUT `/vaccines/{id}` | `{plan_date,done,done_date,org,lot,remind}` 局部更新（`plan_date` 为用户自定义的预期接种日期）；done 由 false→true 时通知其他成员（§6.6） |
| POST `/vaccines/sync` | `{rows:[{code,...patch}]}` 批量更新提醒/状态（ensureVaccineSchedule 与一键开关用）；本批新置 done 的剂次合并成一条通知（§6.6） |

剂次状态派生（overdue/pending）由客户端计算，服务端只存原始字段。

## 9. 里程碑 `/milestones`

| 方法 路径 | 说明 |
| --- | --- |
| GET `/milestones?baby_id=` | 该宝宝全部条目 |
| PUT `/milestones/{id}` | `{done, achieved_at, source_entry_id, month, creator}`；done 由未达成→达成时通知其他成员「X 达成了里程碑「…」」（§6.6），反复改达成日期/取消达成不通知 |

## 10. 设置 `/settings`

| 方法 路径 | 说明 |
| --- | --- |
| GET `/settings` | 整个 settings JSON |
| PUT `/settings` | `{key, value}` 单键写入（account/parent/switches/consent/remind/elder/backupFlags/family/trash 等） |

## 11. AI 日记 `/journals`

| 方法 路径 | 说明 |
| --- | --- |
| POST `/journals/generate` | `{baby_id?, range_start?, range_end?}`（缺省=近 7 天）；服务端管线：事实提取→（配了 LLM 则调用+OutputGuard，失败重生成 1 次）→模板兜底；响应 journal 行 |
| GET `/journals` | 列表（倒序） |
| PUT `/journals/{id}` | `{paras?, status?}`（归档/编辑） |

LLM 配置走服务端环境变量 `LLM_API_BASE / LLM_API_KEY / LLM_MODEL`；未配置直接模板兜底。Key 绝不下发客户端。
AI 配置开关（enabled）存 settings.ai，仅作为是否请求生成的门控。
每次生成成功（模板兜底也算）给家庭其他成员落一条 `type=journal` 通知（§6.6），文案只带时间区间，不含正文与宝宝姓名。

## 12. 导出/数据 `/export` `/import` `/account`

| 方法 路径 | 说明 |
| --- | --- |
| GET `/export/data` | 全量 JSON（同 bootstrap 形状），供数据副本导出 |
| POST `/import` | `{snapshot}`（buildPack 解析后的形状）按 id upsert 合并、同 id 取 updated_at 新者。**仅接受每表列白名单内的字段**：`storage_key`/`sha256`/`size`/`width`/`height`/`deleted_by` 一律由服务端决定（否则可构造指向他人对象的记录跨家庭读取）；`baby_id`/`entry_id` 必须落在本家庭内，否则置空。单次上限 20000 行 |
| DELETE `/account/data` | 清空该家庭全部业务数据（保留账号）——**仅家庭创建者**可调用（普通成员 403） |

## 13. 生长曲线 `/growth`

GET `/growth/curve?metric=weight&baby_id=` → `{points:[{ageM,value,percentile}], standard_version:"who-2006-anchor-v1"}`
（客户端图表仍用本地 chartData 画参考带；此端点供导出与校验。）

## 14. 服务端静态配置（static/config/）

- `milestones.json`：0-1 岁 5 领域清单（从客户端 `src/infra/seed.js` 的里程碑数组移植）。
- `vaccine_schedule.json`：国家免疫规划（从客户端 `src/domain/vaccine.js` VACCINE_SCHEDULE 移植）。
- `growth_lms.json`：WHO 0-24 月龄 P3/P15/P50/P85/P97 锚点表（从客户端 `src/domain/growth.js` T 表移植），含 `standard_version`。
- `servers.json`：客户端可选服务器地址的播种源（见 §17）。

## 15. 服务器地址配置 `/servers`

客户端登录页 /「我的」页的服务器地址不再手输，改为从服务端 `server_endpoint` 表读取并选择（**页面只读，暂无配置界面**）。

| 项 | 说明 |
| --- | --- |
| GET `/servers` | 公开端点（无 JWT、无家庭门控，登录前可读）→ `{rows:[{id,name,url,env,remark,is_default,sort}]}`，只返回 `enabled=1` 的行，按 `sort` 升序 |
| 数据来源 | `server_endpoint` 表；表空时（未播种）本次请求内自动补种一次 |
| 播种 | 服务启动时表为空则按 `static/config/servers.json` 写入；改配置后跑 `python scripts/seed_servers.py`（`--replace` 全量对齐、`--list` 查看） |
| 迁移 | `alembic/versions/48da6530eef1_add_server_endpoint.py`（首个迁移版本）：新库 `alembic upgrade head` 建表；既有库因 `create_all` 已建表会跳过建表只记版本（等价 `alembic stamp head`） |
| 客户端行为 | 选中后只在本机留 `{id,name,url}`（`sj_server`）与 base url（`sj_api_base`）；接口不可达时回落内置本机地址兜底 |

## 16. 错误形状

FastAPI 默认 `{detail: string}`；客户端 http 层按 status 映射提示文案。

## 17. 部署

- `docker-compose.yml`：postgres:16（卷持久化，端口 `POSTGRES_PORT`:5432，默认 5433 避免冲突）+ redis:7-alpine（端口 `REDIS_PORT`，默认 6379）+ minio（非结构化文件对象存储，`MINIO_PORT` API / `MINIO_CONSOLE_PORT` 控制台，默认 9000/9001，卷持久化）+ api（构建镜像，`API_PORT`:8000，默认 8000:8000，依赖 db/redis/minio）+ nginx（统一入口，`NGINX_PORT`:`NGINX_LISTEN_PORT`，默认 80:80，依赖 api）。所有端口、凭据与后端参数均通过环境变量配置，见 `.env.example`（复制为 `.env` 后修改）。
- 反向代理（nginx，配置见 `nginx/nginx.conf` 与模板 `nginx/templates/default.conf.template`，启动时由镜像 envsubst 渲染为 `/etc/nginx/conf.d/default.conf`）：`/api/`→api:8000（关闭缓冲以支持 `/files/{id}/download`、`/media/{id}` 流式传输与 200MB 上传直透，`client_max_body_size` 与 `FILE_MAX_BYTES` 对齐）、`/docs`+`/redoc`+`/openapi.json`+`/static-offline-docs`→api:8000（离线文档资源）、`/healthz` 为 nginx 自身探测。客户端服务器地址填 `http://<host>/api/v1`。nginx 不转发 MinIO：api 经 compose 内网 `minio:9000` 直连取回字节后由服务端代理回源下发；MinIO 控制台仅可直连 `http://<host>:9001`（`MINIO_CONSOLE_PORT`，只绑 127.0.0.1）。
- api 容器 `DATABASE_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}`（由 db 服务凭据自动拼装）、`REDIS_URL=redis://redis:6379/0`、`JWT_SECRET`、`MEDIA_DIR=/app/data/media`。
- 非结构化文件（图片/附件）存储后端由 `MEDIA_BACKEND` 决定：`minio`（默认，对象存储，`MINIO_ENDPOINT=minio:9000`、`MINIO_BUCKET=suiji`，桶不存在时自动创建）或 `local`（本地卷 `MEDIA_DIR`）。两种后端目录结构一致：`{family_id}/{YYYY-MM-DD}/{文件名}`，桶/目录内按家庭隔离、按天归档，便于按家庭备份与清理。
- 下载方式：`MINIO_PUBLIC_URL` 有值且 `MEDIA_DOWNLOAD_MODE!=proxy` 时返回 307 跳预签名 URL（`MEDIA_URL_EXPIRES` 秒有效、上限 `MEDIA_URL_MAX_EXPIRES`，下载仍需先过 `/media/{id}` 的 JWT 鉴权）；否则由 api 服务端代理回源。
- **对外暴露面**：只有 nginx 的 `NGINX_PORT` 绑 0.0.0.0，db/redis/minio/api 一律绑 `127.0.0.1`。
  `/docs`、`/openapi.json` 走 `NGINX_ADMIN_ALLOW` IP 白名单（默认 127.0.0.1 = 公网不可访问）。
- **HTTPS**：默认未启用（保持现有 http 部署可用）。启用方式见 `nginx/templates/tls.conf.template`
  头部三步说明（挂载模板 + 证书卷 + 443 映射）。上 HTTPS 后需同步把 `server_endpoint` 表、
  `static/config/servers.json` 与客户端已存的服务器地址改成 `https://`，否则令牌仍是明文过公网。
- **限流**：nginx 侧 `auth_limit`（20r/m，覆盖 `/api/v1/auth/*` 与 `/family/join`）与 `api_limit`（30r/s）；
  api 侧按 IP 的固定窗口计数（见 §2）。Redis 可用时两侧都走 Redis，不可用时降级内存并定期重试恢复。
- 开发期也可直接本机运行：`python app/main.py`（等价 `uvicorn app.main:app --reload`，可用 HOST/PORT/RELOAD 覆盖）或 `uvicorn`（DATABASE_URL 指向 localhost:5433，MinIO 指向 localhost:9000 或直接 `MEDIA_BACKEND=local`）。
- Redis 用途：Idempotency-Key 去重（SETNX，TTL 24h）；不可用时降级进程内存。
