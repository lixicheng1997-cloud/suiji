"""非结构化文件 /files：上传→去重→列表→下载→改挂→统计→删除（MEDIA_BACKEND=local）。"""
import re
from datetime import datetime, timedelta, timezone

from conftest import API, register

PDF = b"%PDF-1.4\n" + b"1" * 128


_MEDIA = {}


def _auth(client, prefix="file"):
    headers, body = register(client, prefix=prefix)
    _MEDIA[prefix] = body["media"]  # 下载 URL 只能用受限的 media 令牌
    return headers


def _media_token(prefix="file"):
    return _MEDIA[prefix]


def _create_entry(client, headers):
    """建宝宝 + 一条记录，返回 entry_id（文件挂载点必须真实存在）。"""
    birth = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%d")
    r = client.post(API + "/babies", headers=headers, json={
        "name": "小满", "birth_date": birth, "gestational_weeks": 40, "gender": "boy"})
    assert r.status_code == 200, r.text
    occurred = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    r = client.post(API + "/entries", headers=headers,
                    json={"type": "note", "occurred_at": occurred, "note": "附件"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _upload(client, headers, name="报告.pdf", data=PDF, ctype="application/pdf", **form):
    files = {"file": (name, data, ctype)}
    return client.post(API + "/files", headers=headers, files=files, data=form)


def test_upload_download_and_meta(client):
    headers = _auth(client)
    r = _upload(client, headers)
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["original_name"] == "报告.pdf" and f["size"] == len(PDF)
    # 结构化库只存路径，不存字节
    assert f["storage_key"].endswith(".pdf") and len(f["sha256"]) == 64
    assert f["url"] == f"/api/v1/files/{f['id']}/download"

    # 下载：Header 鉴权（access）与 ?token=（media）均可用
    r = client.get(f["url"], headers=headers)
    assert r.status_code == 200 and r.content == PDF
    assert client.get(f["url"], params={"token": _media_token()}).status_code == 200
    # URL 里不接受 access 令牌：它会落进 nginx 日志 / Referer，只允许走 Header
    access = headers["Authorization"].split()[1]
    assert client.get(f"{f['url']}?token={access}").status_code == 403
    # 无 token / 非法 token → 403
    assert client.get(f["url"]).status_code == 403
    assert client.get(f["url"], headers={"Authorization": "Bearer x.y.z"}).status_code == 403
    # 跨家庭 403
    other = _auth(client, "file2")
    assert client.get(f"/api/v1/files/{f['id']}", headers=other).status_code == 403


def test_storage_key_is_family_date_filename(client):
    """对象路径按 {家庭}/{日期}/{文件名} 归档（MEDIA_BACKEND=local 下同构落盘）。"""
    headers = _auth(client)
    f = _upload(client, headers, name="报告.pdf").json()
    assert re.match(r"^[^/]+/\d{4}-\d{2}-\d{2}/报告\.pdf$", f["storage_key"]), f["storage_key"]
    assert f["storage_key"].split("/")[1] == datetime.now().strftime("%Y-%m-%d")

    # 同一天同名但内容不同：不能互相覆盖，key 追加 sha 短码区分
    g = _upload(client, headers, name="报告.pdf", data=PDF + b"x").json()
    assert g["storage_key"] != f["storage_key"]
    assert client.get(f["url"], headers=headers).content == PDF
    assert client.get(g["url"], headers=headers).content == PDF + b"x"


def test_dedup_same_content_same_business(client):
    headers = _auth(client)
    e1, e2 = _create_entry(client, headers), _create_entry(client, headers)
    a = _upload(client, headers, business_type="entry", business_id=e1).json()
    b = _upload(client, headers, business_type="entry", business_id=e1).json()
    assert a["id"] == b["id"] and a["storage_key"] == b["storage_key"]
    # 换挂载点则是另一条台账，但对象仍复用
    c = _upload(client, headers, business_type="entry", business_id=e2).json()
    assert c["id"] != a["id"] and c["storage_key"] == a["storage_key"]
    # 挂载点不属于本家庭 → 404
    assert _upload(client, headers, business_type="entry", business_id="not_exist").status_code == 404


def test_batch_upload_and_list(client):
    headers = _auth(client)
    r = client.post(API + "/files/batch", headers=headers, data={"business_type": "other"},
                    files=[("files", ("a.txt", b"aaa", "text/plain")),
                           ("files", ("b.txt", b"bbb", "text/plain"))])
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 2 and not r.json()["errors"]

    lst = client.get(API + "/files?business_type=other", headers=headers).json()
    assert lst["total"] == 2 and {x["original_name"] for x in lst["items"]} == {"a.txt", "b.txt"}
    assert client.get(API + "/files?keyword=a.txt", headers=headers).json()["total"] == 1
    assert client.get(API + "/files?business_type=entry", headers=headers).json()["total"] == 0


def test_patch_business_and_stats(client):
    headers = _auth(client)
    entry_id = _create_entry(client, headers)
    f = _upload(client, headers, name="x.pdf").json()
    r = client.patch(API + f"/files/{f['id']}", headers=headers,
                     json={"business_type": "entry", "business_id": entry_id,
                           "original_name": "改名.pdf"})
    assert r.status_code == 200, r.text
    assert r.json()["business_type"] == "entry" and r.json()["original_name"] == "改名.pdf"

    s = client.get(API + "/files/stats", headers=headers).json()
    assert s["count"] == 1 and s["total_size"] == len(PDF)
    assert s["by_business_type"][0]["business_type"] == "entry"


def test_delete_releases_only_when_unreferenced(client):
    headers = _auth(client)
    e1, e2 = _create_entry(client, headers), _create_entry(client, headers)
    f1 = _upload(client, headers, business_type="entry", business_id=e1).json()
    f2 = _upload(client, headers, business_type="entry", business_id=e2).json()
    assert f1["storage_key"] == f2["storage_key"]

    # 还有另一条台账引用同一对象时，字节不能删：删 f1 后 f2 仍可下载
    assert client.delete(API + f"/files/{f1['id']}", headers=headers).status_code == 200
    assert client.get(f2["url"], headers=headers).status_code == 200
    # 最后一个引用删除后，台账与字节一起消失
    assert client.delete(API + f"/files/{f2['id']}", headers=headers).status_code == 200
    assert client.get(API + f"/files/{f2['id']}", headers=headers).status_code == 404
    assert client.get(API + "/files/stats", headers=headers).json()["count"] == 0


def test_empty_file_rejected(client):
    headers = _auth(client)
    r = _upload(client, headers, name="empty.pdf", data=b"")
    assert r.status_code == 422, r.text


def test_media_upload_registers_file_ledger(client):
    """/media 上传后应同步进统一文件台账。"""
    headers = _auth(client, "filemedia")
    m = client.post(API + "/media", headers=headers,
                    files={"file": ("p.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")}).json()
    lst = client.get(API + "/files?business_type=entry_media", headers=headers).json()
    assert lst["total"] == 1 and lst["items"][0]["business_id"] == m["id"]
    assert lst["items"][0]["storage_key"] == m["storage_key"]


def test_audio_m4a_sniffs_as_audio(client):
    """App 端录音是 m4a（ftyp brand 'M4A '）：不能按 mp4 视频回 Content-Type，
    且没有扩展名的临时文件也要能按字节推导成 .m4a。"""
    headers = _auth(client, "filevoice")
    m4a = b"\x00\x00\x00\x20ftypM4A \x00\x00\x02\x00isomM4A " + b"\x00" * 64
    f = _upload(client, headers, name="recorder_1730000000", data=m4a,
                ctype="application/octet-stream").json()
    assert f["ext"] == ".m4a" and f["storage_key"].endswith(".m4a"), f
    assert f["content_type"] == "audio/mp4", f["content_type"]
    r = client.get(f["url"], headers=headers)
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/mp4")


def test_download_supports_range(client):
    """语音/视频播放器要先看到 Accept-Ranges 才敢发 Range；拖动播放依赖 206 分段。"""
    headers = _auth(client, "filerange")
    f = _upload(client, headers, name="报告.pdf").json()
    full = client.get(f["url"], headers=headers)
    assert full.headers.get("Accept-Ranges") == "bytes"
    total = len(PDF)

    r = client.get(f["url"], headers={**headers, "Range": "bytes=0-9"})
    assert r.status_code == 206, r.text
    assert r.content == PDF[:10]
    assert r.headers["Content-Range"] == f"bytes 0-9/{total}"
    assert r.headers["Content-Length"] == "10"

    # 尾段与超界：越界按 RFC 9110 回 416，播放器据此停止重试
    assert client.get(f["url"], headers={**headers, "Range": "bytes=-20"}).content == PDF[-20:]
    bad = client.get(f["url"], headers={**headers, "Range": f"bytes={total + 5}-"})
    assert bad.status_code == 416, bad.text
    assert bad.headers["Content-Range"] == f"bytes */{total}"

    # 语法非法的 Range 不当错误处理：两个后端都忽略它、回整份 200
    ignored = client.get(f["url"], headers={**headers, "Range": "bytes=abc"})
    assert ignored.status_code == 200 and ignored.content == PDF


def test_purge_entry_clears_attached_files(client):
    """彻底删除记录时，挂在它上面的文件台账与字节一起释放。"""
    headers = _auth(client, "filepurge")
    entry_id = _create_entry(client, headers)
    f = _upload(client, headers, business_type="entry", business_id=entry_id).json()
    assert client.get(f["url"], headers=headers).status_code == 200

    assert client.delete(API + f"/entries/{entry_id}", headers=headers).status_code == 200
    assert client.delete(API + f"/entries/trash/{entry_id}", headers=headers).status_code == 200
    assert client.get(API + "/files", headers=headers).json()["total"] == 0
    assert client.get(API + "/files/stats", headers=headers).json()["count"] == 0
