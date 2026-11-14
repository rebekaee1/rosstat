"""Серверный счётчик упоров в лимит скачиваний (14.11.2026): Redis, день × путь × формат, без идентификаторов."""
import asyncio
from datetime import date

import fakeredis.aioredis

from app.config import settings
from app.services import download_content as dc
from app.services import wall_counter as wc

TABLE = {"format": "xlsx", "filename": "t.xlsx", "points": [{"date": "2020-01-01", "actual": 1}],
         "history": {"source": "table", "params": {"href": "/russia/indicator/fuel-diesel?mode=eop-month#chart"}}}
GRID = {"format": "csv", "filename": "g.csv", "title": "x", "columns": [{"key": "date", "label": "Дата"}],
        "rows": [{"date": "2020-01-01"}]}


def _fake_state(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def get():
        return fake

    import app.core.cache as cache_mod
    monkeypatch.setattr(cache_mod, "get_state_redis", get)
    return fake


def test_normalize_path():
    assert wc.normalize_path("/russia/indicator/cpi?mode=yoy#chart") == "/russia/indicator/cpi"
    assert wc.normalize_path("https://ru.forecasteconomy.com/compare/?codes=a,b") == "/compare"
    assert wc.normalize_path("//evil.example/x") == "/x"  # хост отброшен, остался путь
    assert wc.normalize_path("javascript:alert(1)") == "unknown"
    assert wc.normalize_path(None) == "unknown"
    assert len(wc.normalize_path("/" + "a" * 500)) == wc.MAX_PATH
    assert wc.field_for("XLSX", "/a") == "xlsx|/a" and wc.field_for("pdf", "/a") == "other|/a"


def test_refusal_is_recorded_with_path_and_format_only(auth_client, monkeypatch):
    calls = []

    async def spy(fmt, page, day=None):
        calls.append((fmt, page))

    monkeypatch.setattr(wc, "record_wall", spy)
    monkeypatch.setattr(settings, "download_anon_limit", 0)
    r = auth_client.post("/api/v1/export/table", json=TABLE)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "download_limit"
    r = auth_client.post("/api/v1/export/grid", json=GRID,
                         headers={"Referer": "https://ru.forecasteconomy.com/russia/region/map/vrp?year=2020"})
    assert r.status_code == 403
    assert calls == [("xlsx", "/russia/indicator/fuel-diesel?mode=eop-month#chart"),
                     ("csv", "https://ru.forecasteconomy.com/russia/region/map/vrp?year=2020")]


def test_signed_in_user_is_never_counted(auth_client, monkeypatch):
    calls = []

    async def spy(fmt, page, day=None):
        calls.append((fmt, page))

    monkeypatch.setattr(wc, "record_wall", spy)
    monkeypatch.setattr(settings, "download_anon_limit", 0)
    r = auth_client.post("/api/v1/auth/register", json={"email": "w@example.com", "password": "supersecret1",
                                                          "consent": True})
    assert r.status_code == 201
    assert auth_client.post("/api/v1/export/table", json=TABLE).status_code == 200
    assert calls == []


def test_record_writes_day_hash_with_ttl_and_no_identifiers(monkeypatch):
    fake = _fake_state(monkeypatch)

    async def scenario():
        await wc.record_wall("xlsx", "/russia/indicator/fuel-diesel?mode=eop-month", date(2026, 11, 14))
        await wc.record_wall("xlsx", "https://ru.forecasteconomy.com/russia/indicator/fuel-diesel", date(2026, 11, 14))
        await wc.record_wall("csv", None, date(2026, 11, 14))
        key = wc.key_for(date(2026, 11, 14))
        return await fake.keys("*"), await fake.hgetall(key), await fake.ttl(key)

    keys, fields, ttl = asyncio.run(scenario())
    assert keys == ["fe:wall:2026-11-14"]
    assert fields == {"xlsx|/russia/indicator/fuel-diesel": "2", "csv|unknown": "1"}
    assert 0 < ttl <= wc.TTL_SECONDS


def test_redis_failure_is_swallowed_and_read_says_unknown(monkeypatch):
    async def broken():
        raise ConnectionError("redis down")

    import app.core.cache as cache_mod
    monkeypatch.setattr(cache_mod, "get_state_redis", broken)
    asyncio.run(wc.record_wall("csv", "/x"))  # не бросает
    assert asyncio.run(wc.read_walls(dc.period_for_window("7", date(2026, 11, 14)))) is None


def test_read_sums_days_of_the_period_and_report_shows_both_numbers(monkeypatch):
    fake = _fake_state(monkeypatch)

    async def scenario():
        await fake.hset(wc.key_for(date(2026, 11, 13)), mapping={"xlsx|/russia/indicator/cpi": 2})
        await fake.hset(wc.key_for(date(2026, 11, 14)), mapping={"xlsx|/russia/indicator/cpi": 1, "csv|/compare": 4})
        await fake.hset(wc.key_for(date(2026, 11, 1)), mapping={"csv|/old": 9})  # вне периода
        return await wc.read_walls(dc.period_for_window("7", date(2026, 11, 14)))

    counts = asyncio.run(scenario())
    assert counts == {"xlsx|/russia/indicator/cpi": 3, "csv|/compare": 4}

    s = dc.server_summary(counts, {"xlsx|/russia/indicator/cpi": "Инфляция"}, browser=5)
    assert s["count"] == 7 and s["items"][0] == {"title": "/compare", "path": "/compare", "format": "csv", "count": 4}
    text = dc.format_report({**dc.summarize([]), "server": s}, "7 дней")
    assert "Лимит скачиваний: сервер видел упоров 7 / браузер сообщил 5" in text
    down = {**dc.summarize([]), "server": dc.server_summary(None, {}, browser=3)}
    assert "сервер — нет ответа счётчика / браузер сообщил 3" in dc.format_report(down, "7 дней")
    book = dc.build_xlsx({"period": dc.period_for_window("7", date(2026, 11, 14)), "rows": [],
                          "summary": {**dc.summarize([]), "server": s}})
    from io import BytesIO

    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(book))
    assert wb["Сервер — упоры"]["A2"].value == "/compare" and wb["Сервер — упоры"]["D2"].value == 4
