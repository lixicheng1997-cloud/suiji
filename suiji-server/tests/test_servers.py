"""服务器地址配置：GET /servers 公开可读、按 sort 排序、与播种数据一致。"""
from conftest import API

# 与 static/config/servers.json 对齐
SEEDED = [
    ("云服务", "http://49.233.77.155:30080/api/v1", 1),
    ("本地调试", "http://localhost:30080/api/v1", 2),
]


def test_list_servers_is_public(client):
    """登录前就要能拉到列表：无需 Authorization。"""
    r = client.get(API + "/servers")
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert rows, "应已按 servers.json 播种"
    for row in rows:
        assert row["url"].startswith("http")
        assert row["name"]


def test_list_servers_matches_seed(client):
    rows = client.get(API + "/servers").json()["rows"]
    got = [(row["name"], row["url"], row["sort"]) for row in rows]
    assert got == SEEDED
    # 默认项唯一，且为云服务
    defaults = [row for row in rows if row["is_default"]]
    assert len(defaults) == 1 and defaults[0]["name"] == "云服务"


def test_list_servers_sorted(client):
    rows = client.get(API + "/servers").json()["rows"]
    keys = [(row["sort"], row["name"]) for row in rows]
    assert keys == sorted(keys)
