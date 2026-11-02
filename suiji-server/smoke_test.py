# 端到端冒烟：注册→登录→bootstrap→建档→存记录(含媒体)→疫苗→设置→日记→回收站
# 注：本脚本全程明文调用——服务端 CRYPTO_MODE=optional 时放行明文（默认配置）。
# 若改成 CRYPTO_MODE=required，清单内的 /auth/*、/family/join 会被 400 拦掉，
# 需要加密调用的话参考 tests/test_crypto.py 里的 client_seal / client_wrap。
import io, json, os, sys, uuid, time
import httpx

BASE = os.getenv("SUIJI_BASE", "http://localhost:30080/api/v1")
u = "smoke_" + uuid.uuid4().hex[:8]
ok = lambda name: print(f"  ✅ {name}")

c = httpx.Client(base_url=BASE, timeout=60)

# 1. 注册（不再代建家庭）
r = c.post("/auth/register", json={"username": u, "password": "p@ss1234", "name": "妈妈"})
assert r.status_code == 200, r.text
assert r.json()["family"] is None and r.json()["need_family"] is True
tok = r.json()["access"]
H = {"Authorization": f"Bearer {tok}"}
ok(f"注册（{u}）")
# 未关联家庭：业务接口 409 need_family，必须先完成家庭引导
r = c.get("/entries", headers=H)
assert r.status_code == 409 and r.json()["detail"] == "need_family", r.text
# 引导：创建家庭（另一条路径是凭邀请码加入，见第 11 步）
r = c.post("/family", headers=H, json={"name": "小岁的家"})
assert r.status_code == 200 and r.json()["family"]["role"] == "creator"
ok("家庭门控：无家庭 409 need_family → 创建家庭后放行")
r = c.post("/auth/login", json={"username": u, "password": "p@ss1234"})
assert r.status_code == 200, r.text
ok("登录")

# 2. bootstrap（空家庭）
r = c.get("/bootstrap", headers=H)
assert r.status_code == 200, r.text
b = r.json()
assert b["family"]["role"] == "creator" and b["babies"] == []
ok("bootstrap 空快照 + creator 角色")

# 3. 创建宝宝 → 服务端自动排疫苗+里程碑
baby_id = "baby_" + uuid.uuid4().hex[:12]
r = c.post("/babies", headers=H, json={"id": baby_id, "name": "小满", "birth_date": "2026-03-01",
    "gender": "boy", "gestational_weeks": 40, "birth_length": 50, "birth_weight": 3.3})
assert r.status_code == 200, r.text
assert r.json()["id"] == baby_id
r = c.get("/bootstrap", headers=H)
b = r.json()
assert len(b["vaccines"]) == 22 and len(b["milestone_records"]) >= 10
assert b["vaccines"][0]["plan_date"] == "2026-03-01"
ok(f"建档：疫苗 {len(b['vaccines'])} 剂次 / 里程碑 {len(b['milestone_records'])} 条，首剂 plan_date 正确")

# 4. 上传媒体 + 保存含照片记录（幂等键重复提交）
png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001" "0d0a2db40000000049454e44ae426082")
r = c.post("/media", headers=H, files={"file": ("a.png", io.BytesIO(png), "image/png")})
assert r.status_code == 200, r.text
m = r.json()
ORIGIN = BASE.split("/api/")[0]
r = httpx.Client(follow_redirects=True).get(ORIGIN + m["url"], headers=H)  # MinIO 后端 307→预签名
assert r.status_code == 200 and r.content == png
r2 = httpx.get(ORIGIN + m["url"])  # 无 token
assert r2.status_code == 403
ok(f"媒体上传/鉴权下载/无 token 403（{m['id']}）")

eid = "e_" + uuid.uuid4().hex[:12]
entry = {"id": eid, "baby_id": baby_id, "type": "photo", "occurred_at": "2026-10-23T04:00:00Z",
    "title": "照片", "meta": "", "badge": "", "note": "冒烟", "creator": "妈妈",
    "photo": m["url"], "payload": {"photos": [m["url"]]}, "is_backfilled": 0}
IK = {"Idempotency-Key": eid}
r = c.post("/entries", headers={**H, **IK}, json=entry)
assert r.status_code == 200, r.text
r2 = c.post("/entries", headers={**H, **IK}, json=entry)  # 重复提交
assert r2.status_code == 200 and r2.json()["id"] == eid
r = c.get("/bootstrap", headers=H)
assert len([e for e in r.json()["entries"] if e["id"] == eid]) == 1
ok("记录保存 + 幂等去重（重复提交仅 1 条）")

# 5. measure → measurement + 百分位
mid = "e_" + uuid.uuid4().hex[:12]
r = c.post("/entries", headers={**H, "Idempotency-Key": mid}, json={
    "id": mid, "baby_id": baby_id, "type": "measure", "occurred_at": "2026-08-20T04:00:00Z",
    "title": "测量", "meta": "", "badge": "", "note": "", "creator": "妈妈", "photo": "",
    "payload": {"weight": 7.2, "height": 64}, "is_backfilled": 0})
assert r.status_code == 200, r.text
r = c.get("/growth/curve?metric=weight&baby_id=" + baby_id, headers=H)
pts = r.json()["points"]
assert pts and 3 < pts[0]["percentile"] < 97
ok(f"测量→百分位服务端留痕：weight 5.6月龄 P={pts[0]['percentile']}")

# 6. 里程碑达成（经 milestone 记录）
msid = b["milestone_records"][0]["id"]
r = c.post("/entries", headers={**H, "Idempotency-Key": "ms_" + uuid.uuid4().hex[:8]}, json={
    "id": "e_" + uuid.uuid4().hex[:12], "baby_id": baby_id, "type": "milestone",
    "occurred_at": "2026-10-20T04:00:00Z", "title": "里程碑", "meta": "", "badge": "", "note": "",
    "creator": "妈妈", "photo": "", "payload": {"name": b["milestone_records"][0]["name"]}, "is_backfilled": 0})
assert r.status_code == 200, r.text
r = c.get("/milestones?baby_id=" + baby_id, headers=H)
done = [x for x in r.json() if x["done"]]
assert done and done[0]["id"] == msid
ok(f"里程碑达成回写：{done[0]['name']} month={done[0].get('month')}")

# 7. 疫苗局部更新 + sync
vid = b["vaccines"][1]["id"]
r = c.put(f"/vaccines/{vid}", headers=H, json={"done": True, "done_date": "2026-04-01", "org": "社区医院", "lot": "L123"})
assert r.status_code == 200 and r.json()["done"] is True
r = c.post("/vaccines/sync", headers=H, json={"rows": [{"code": "bcg", "baby_id": baby_id, "remind": False}]})
assert r.status_code == 200
ok("疫苗标记接种 + sync 批量提醒")

# 8. 设置读写
r = c.put("/settings", headers=H, json={"key": "consent", "value": {"child_info": True, "agreed_at": "2026-10-23"}})
assert r.status_code == 200
r = c.get("/settings", headers=H)
assert r.json()["consent"]["child_info"] is True
ok("设置单键读写")

# 9. 日记生成（未配 LLM → 模板兜底）
r = c.post("/journals/generate", headers=H, json={"baby_id": baby_id})
assert r.status_code == 200, r.text
j = r.json()
assert j["status"] == "draft" and j["paras"] and j["model_version"]  # LLM 配置时返回模型名，否则 template
r = c.put(f"/journals/{j['id']}", headers=H, json={"status": "archived"})
assert r.status_code == 200 and r.json()["status"] == "archived"
ok(f"日记生成（{j['model_version']} {len(j['paras'])} 段）+ 归档")

# 10. 回收站：软删→列表→恢复→彻底删
r = c.delete(f"/entries/{eid}", headers=H)
assert r.status_code == 200
r = c.get("/bootstrap", headers=H)
b2 = r.json()
assert eid not in [e["id"] for e in b2["entries"]] and eid in [t["id"] for t in b2["trash"]]
r = c.post(f"/entries/{eid}/restore", headers=H)
assert r.status_code == 200
r = c.delete(f"/entries/{eid}", headers=H)
r = c.delete(f"/entries/trash/{eid}", headers=H)
assert r.status_code == 200
r = c.get("/bootstrap", headers=H)
assert eid not in [t["id"] for t in r.json()["trash"]]
ok("回收站软删/恢复/彻底删除")

# 11. 只读开关：邀请第二成员并置只读
r = c.post("/family/invite", headers=H)
code = r.json()["code"]
u2 = "smoke2_" + uuid.uuid4().hex[:8]
r = c.post("/auth/register", json={"username": u2, "password": "p@ss1234", "name": "爸爸"})
tok2 = r.json()["access"]
H2 = {"Authorization": f"Bearer {tok2}"}
# 第二条引导路径：凭邀请码直接加入，完成后自动归属该家庭
r = c.post("/family/join", headers=H2, json={"code": code})
assert r.status_code == 200, r.text
fam_id = r.json()["family"]["id"]
r = c.patch("/family/readonly", headers=H, json={"readonly": True})
assert r.status_code == 200
r = c.post("/entries", headers={**H2, "Idempotency-Key": "ro_" + uuid.uuid4().hex[:8]}, json={
    "id": "e_" + uuid.uuid4().hex[:12], "baby_id": baby_id, "type": "note",
    "occurred_at": "2026-10-23T05:00:00Z", "title": "x", "meta": "", "badge": "", "note": "",
    "creator": "爸爸", "photo": "", "payload": {}, "is_backfilled": 0})
assert r.status_code == 403 and r.json()["detail"] == "只读模式"
r = c.post("/entries", headers={**H, "Idempotency-Key": "cr_" + uuid.uuid4().hex[:8]}, json={
    "id": "e_" + uuid.uuid4().hex[:12], "baby_id": baby_id, "type": "note",
    "occurred_at": "2026-10-23T05:00:00Z", "title": "x", "meta": "", "badge": "", "note": "",
    "creator": "妈妈", "photo": "", "payload": {}, "is_backfilled": 0})
assert r.status_code == 200  # 创建者不受只读限制
r = c.patch("/family/readonly", headers=H, json={"readonly": False})
ok("邀请码加入→只读开关：成员写 403、创建者可写")

# 12. 跨家庭越权防护
r = c.get(f"/entries/{mid}", headers=H2)  # 成员2已加入同家庭，应可见；换个陌生账号验证 403/404
u3 = "smoke3_" + uuid.uuid4().hex[:8]
r = c.post("/auth/register", json={"username": u3, "password": "p@ss1234"})
H3 = {"Authorization": f"Bearer {r.json()['access']}"}
c.post("/family", headers=H3, json={"name": "别人家"})   # 陌生账号同样要先有自己的家庭
r = c.get(f"/entries/{mid}", headers=H3)
assert r.status_code in (403, 404)
r = c.put(f"/babies/{baby_id}", headers=H3, json={"name": "劫持"})
assert r.status_code in (403, 404)
ok(f"跨家庭越权拦截（404/403）")

# 13. 家庭归属唯一：凭其他家庭的邀请码加入 = 与原家庭解绑（个人资料不变）
r = c.post("/family/invite", headers=H3)
code3 = r.json()["code"]
r = c.post("/family/join", headers=H2, json={"code": code3})
assert r.status_code == 200, r.text
assert r.json()["left_family"]["id"] == fam_id      # 回传被解绑的原家庭
assert r.json()["family"]["role"] == "member"
r = c.get(f"/entries/{mid}", headers=H2)            # 原家庭记录已不可见
assert r.status_code in (403, 404)
assert c.get("/auth/me", headers=H2).json()["family"]["id"] != fam_id
ok("家庭归属唯一：加入其他家庭 → 与原家庭解绑")

# 14. 导出 + 清空
r = c.get("/export/data", headers=H)
assert r.status_code == 200 and r.json()["babies"]
r = c.delete("/account/data", headers=H)
assert r.status_code == 200
r = c.get("/bootstrap", headers=H)
b3 = r.json()
assert b3["entries"] == [] and b3["babies"] == []
ok("数据导出 + 清空家庭业务数据")

# 15. token 刷新
r = c.post("/auth/login", json={"username": u, "password": "p@ss1234"})
refresh = r.json()["refresh"]
r = c.post("/auth/refresh", json={"refresh": refresh})
assert r.status_code == 200 and r.json()["access"]
ok("refresh 换新 access")

print("\n全部 15 组冒烟通过 ✅")
