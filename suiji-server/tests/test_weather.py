"""首页天气：GET /weather 公开可读；测试环境无公网定位/天气，降级为空对象且不报错。"""
from conftest import API


def test_weather_is_public_and_degrades_empty(client, monkeypatch):
    """无需登录；外部定位/天气不可用时返回空天气，前端据此隐藏天气行。"""
    # 测试环境无外网：把服务层打桩为返回空，避免用例依赖外部接口可用性
    import app.services.weather_service as ws
    monkeypatch.setattr(ws, "get_weather", lambda ip: {"text": "", "temp": None, "city": ""})

    r = client.get(API + "/weather")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == ""
    assert body["temp"] is None
    assert body["city"] == ""
