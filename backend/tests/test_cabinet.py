"""Личный кабинет (круг 11): избранное, слежения, лента, история выгрузок, настройки, .ics.

Герметично: SQLite + fakeredis (auth_client), без Postgres/Redis-сервисов. Что здесь НЕ
проверяется: поведение индексов/планов на PostgreSQL и миграция (см. test_cabinet_migration.py
для статической проверки цепочки)."""
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models import (
    EconomicEvent, Indicator, IndicatorData, RegionIndicator, UserExport, UserPreference,
    UserSavedItem, UserWatch, WorldCountry, WorldDataPoint, WorldIndicator,
)
from tests.conftest import csrf_headers

C = "/api/v1/cabinet"


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "cabinet_enabled", True)


def reg(tc, email="a@example.com"):
    tc.cookies.clear()
    r = tc.post("/api/v1/auth/register", json={"email": email, "password": "supersecret1", "consent": True})
    assert r.status_code == 201, r.text
    return r


def seed(tc, auth_env, fn):
    async def run(maker):
        async with maker() as s:
            out = await fn(s)
            await s.commit()
            return out
    return tc.portal.call(run, auth_env["session_maker"])


def count(tc, auth_env, model):
    async def run(maker):
        async with maker() as s:
            return await s.scalar(select(func.count()).select_from(model))
    return tc.portal.call(run, auth_env["session_maker"])


async def _seed_series(s, last=date(2026, 8, 1)):
    ind = Indicator(code="cpi_yoy", name="Инфляция", name_en="Inflation", unit="%", frequency="monthly",
                    is_active=True, is_listed=True)
    s.add(ind)
    await s.flush()
    s.add_all([IndicatorData(indicator_id=ind.id, date=date(2026, 7, 1), value=8.1),
               IndicatorData(indicator_id=ind.id, date=last, value=8.4)])
    country = WorldCountry(code="TR", slug="turkey", name_ru="Турция", name_en="Turkey")
    s.add(country)
    await s.flush()
    w = WorldIndicator(country_id=country.id, code="tr-gdp", dataset_id="d", slice_hash="h", name_ru="ВВП Турции",
                       name_en="Turkey GDP", unit="USD", unit_ru="долл.", frequency="annual", is_listed=True,
                       history_end=date(2025, 1, 1))
    s.add(w)
    await s.flush()
    s.add(WorldDataPoint(indicator_id=w.id, date=date(2025, 1, 1), value=1100))
    s.add(RegionIndicator(code="reg-wage", table_code="1.1", section_num=1, section_name="Труд", name="Зарплата",
                          unit="руб.", year_max=2024, is_listed=True))


# ── флаг ──

def test_flag_off_everything_404_except_config(auth_client):
    reg(auth_client)
    h = csrf_headers(auth_client)
    assert auth_client.get(f"{C}/config").json() == {"enabled": False, "features": {}, "limits": {}}
    for method, path, kw in [
        ("get", "/saved", {}), ("post", "/saved", {"json": {"kind": "indicator", "item_key": "x"}}),
        ("get", "/watches", {}), ("get", "/feed", {}), ("get", "/exports", {}), ("get", "/prefs", {}),
        ("put", "/prefs", {"json": {}}), ("post", "/calendar-feed", {}),
        ("get", "/calendar.ics?token=" + "a" * 32, {}), ("post", "/saved/import", {"json": {"items": []}}),
    ]:
        r = getattr(auth_client, method)(C + path, headers=h, **kw)
        assert r.status_code == 404, (method, path, r.status_code)


def test_flag_off_even_for_guest_is_404_not_401(auth_client):
    assert auth_client.get(f"{C}/saved").status_code == 404


def test_flag_default_is_off():
    assert type(settings).model_fields["cabinet_enabled"].default is False


def test_config_when_on(auth_client, on):
    cfg = auth_client.get(f"{C}/config").json()
    assert cfg["enabled"] is True
    assert cfg["features"]["watch_channels"] == ["inapp"]
    assert cfg["limits"] == {"saved": 200, "watches": 50, "exports": 200, "import_batch": 100}
    assert auth_client.get(f"{C}/config").headers["cache-control"] == "no-store"


# ── сессия и CSRF ──

def test_guest_gets_401(auth_client, on):
    assert auth_client.get(f"{C}/saved").status_code == 401
    assert auth_client.get(f"{C}/watches").status_code == 401
    assert auth_client.get(f"{C}/feed").status_code == 401
    assert auth_client.get(f"{C}/exports").status_code == 401
    assert auth_client.get(f"{C}/prefs").status_code == 401


def test_mutations_require_csrf(auth_client, on):
    reg(auth_client)
    body = {"kind": "indicator", "item_key": "cpi_yoy"}
    assert auth_client.post(f"{C}/saved", json=body).status_code == 403          # без заголовка
    assert auth_client.post(f"{C}/saved", json=body, headers={"X-XSRF-TOKEN": "wrong"}).status_code == 403
    assert auth_client.post(f"{C}/saved", json=body, headers=csrf_headers(auth_client)).status_code == 201
    h = {}
    assert auth_client.put(f"{C}/prefs", json={}, headers=h).status_code == 403
    assert auth_client.post(f"{C}/watches", json={"subject_kind": "indicator", "subject_key": "x"}, headers=h).status_code == 403
    assert auth_client.delete(f"{C}/saved?kind=indicator&key=cpi_yoy", headers=h).status_code == 403
    assert auth_client.post(f"{C}/feed/seen", headers=h).status_code == 403
    assert auth_client.post(f"{C}/calendar-feed", headers=h).status_code == 403
    assert auth_client.delete(f"{C}/exports", headers=h).status_code == 403
    assert auth_client.post(f"{C}/saved/import", json={"items": []}, headers=h).status_code == 403


def test_responses_are_no_store(auth_client, on):
    reg(auth_client)
    for path in ("/saved", "/watches", "/feed", "/exports", "/prefs", "/calendar-feed"):
        assert auth_client.get(C + path).headers["cache-control"] == "private, no-store", path


# ── избранное ──

def test_saved_crud_and_upsert(auth_client, on):
    reg(auth_client)
    h = csrf_headers(auth_client)
    r = auth_client.post(f"{C}/saved", json={"kind": "comparison", "item_key": "codes=a,b&rep=value",
                                              "title": "Россия и Турция", "payload": {"codes": ["a", "b"], "rep": "value"}}, headers=h)
    assert r.status_code == 201
    item = r.json()["item"]
    assert r.json()["created"] is True and item["payload"] == {"codes": ["a", "b"], "rep": "value"}
    assert item["created_at"].endswith("Z")

    # повтор того же ключа = обновление, не дубль
    r2 = auth_client.post(f"{C}/saved", json={"kind": "comparison", "item_key": "codes=a,b&rep=value", "title": "Новое имя"}, headers=h)
    assert r2.status_code == 200 and r2.json()["created"] is False
    assert r2.json()["item"]["id"] == item["id"] and r2.json()["item"]["title"] == "Новое имя"
    assert r2.json()["item"]["payload"] == {"codes": ["a", "b"], "rep": "value"}  # payload не затёрт пустым

    listed = auth_client.get(f"{C}/saved").json()
    assert listed["count"] == 1 and listed["limit"] == 200

    ren = auth_client.patch(f"{C}/saved/{item['id']}", json={"title": "  Моё сравнение  "}, headers=h)
    assert ren.status_code == 200 and ren.json()["item"]["title"] == "Моё сравнение"
    assert auth_client.patch(f"{C}/saved/{item['id']}", json={"title": "   "}, headers=h).status_code == 422

    assert auth_client.delete(f"{C}/saved/{item['id']}", headers=h).status_code == 200
    assert auth_client.delete(f"{C}/saved/{item['id']}", headers=h).status_code == 404
    assert auth_client.get(f"{C}/saved").json()["count"] == 0


def test_saved_filters_and_delete_by_key(auth_client, on):
    reg(auth_client)
    h = csrf_headers(auth_client)
    auth_client.post(f"{C}/saved", json={"kind": "indicator", "item_key": "cpi_yoy"}, headers=h)
    auth_client.post(f"{C}/saved", json={"kind": "country", "item_key": "turkey"}, headers=h)
    only = auth_client.get(f"{C}/saved?kind=country").json()
    assert [i["item_key"] for i in only["items"]] == ["turkey"] and only["total"] == 2
    assert auth_client.get(f"{C}/saved?kind=indicator&key=cpi_yoy").json()["count"] == 1
    assert auth_client.get(f"{C}/saved?kind=bogus").status_code == 422
    d = auth_client.delete(f"{C}/saved?kind=indicator&key=cpi_yoy", headers=h)
    assert d.json() == {"ok": True, "removed": True}
    assert auth_client.delete(f"{C}/saved?kind=indicator&key=cpi_yoy", headers=h).json()["removed"] is False
    assert auth_client.get(f"{C}/saved").json()["count"] == 1


@pytest.mark.parametrize("body", [
    {"kind": "nope", "item_key": "x"},
    {"kind": "indicator", "item_key": ""},
    {"kind": "indicator", "item_key": "x" * 301},
    {"kind": "indicator", "item_key": "bad\nkey"},
    {"kind": "calc", "item_key": "k", "payload": {"lower": 1}},                  # границ диапазона нет
    {"kind": "calc", "item_key": "k", "payload": {"a": {"b": [{"UPPER": 3}]}}},
    {"kind": "calc", "item_key": "k", "payload": {"blob": "x" * 9000}},           # размер
    {"kind": "calc", "item_key": "k", "payload": {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}},  # глубина
])
def test_saved_validation(auth_client, auth_env, on, body):
    reg(auth_client)
    r = auth_client.post(f"{C}/saved", json=body, headers=csrf_headers(auth_client))
    assert r.status_code == 422, r.text
    assert "code" in r.json()["detail"]
    assert count(auth_client, auth_env, UserSavedItem) == 0


def test_saved_limit_200(auth_client, auth_env, on):
    reg(auth_client)
    h = csrf_headers(auth_client)
    uid = auth_client.get("/api/v1/auth/me").json()["user"]["id"]
    import uuid as _uuid

    async def fill(s):
        for i in range(200):
            s.add(UserSavedItem(user_id=_uuid.UUID(uid), kind="indicator", item_key=f"k{i}"))
    seed(auth_client, auth_env, fill)
    r = auth_client.post(f"{C}/saved", json={"kind": "indicator", "item_key": "extra"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "limit_reached" and r.json()["detail"]["limit"] == 200
    # обновление существующего при полном лимите разрешено
    assert auth_client.post(f"{C}/saved", json={"kind": "indicator", "item_key": "k5", "title": "t"}, headers=h).status_code == 200


def test_saved_import_keeps_existing_and_skips_bad(auth_client, on):
    reg(auth_client)
    h = csrf_headers(auth_client)
    auth_client.post(f"{C}/saved", json={"kind": "indicator", "item_key": "a", "title": "Моё"}, headers=h)
    r = auth_client.post(f"{C}/saved/import", json={"items": [
        {"kind": "indicator", "item_key": "a", "title": "Гостевое"},   # уже есть: не затираем
        {"kind": "country", "item_key": "turkey", "title": "Турция"},
        {"kind": "bogus", "item_key": "z"},                              # пропуск
    ]}, headers=h)
    assert r.status_code == 200
    assert r.json()["imported"] == 1 and r.json()["skipped"] == 2 and r.json()["total"] == 2
    kept = auth_client.get(f"{C}/saved?kind=indicator&key=a").json()["items"][0]
    assert kept["title"] == "Моё"
    too_many = {"items": [{"kind": "indicator", "item_key": f"k{i}"} for i in range(101)]}
    assert auth_client.post(f"{C}/saved/import", json=too_many, headers=h).status_code == 422


def test_other_users_records_are_invisible(auth_client, on):
    reg(auth_client, "a@example.com")
    ha = csrf_headers(auth_client)
    sid = auth_client.post(f"{C}/saved", json={"kind": "indicator", "item_key": "cpi_yoy"}, headers=ha).json()["item"]["id"]
    exp = auth_client.get(f"{C}/saved").json()
    assert exp["count"] == 1

    reg(auth_client, "b@example.com")
    hb = csrf_headers(auth_client)
    assert auth_client.get(f"{C}/saved").json()["count"] == 0
    assert auth_client.patch(f"{C}/saved/{sid}", json={"title": "взлом"}, headers=hb).status_code == 404
    assert auth_client.delete(f"{C}/saved/{sid}", headers=hb).status_code == 404
    assert auth_client.delete(f"{C}/saved?kind=indicator&key=cpi_yoy", headers=hb).json()["removed"] is False
    # один и тот же ключ у двух людей — две независимые записи
    assert auth_client.post(f"{C}/saved", json={"kind": "indicator", "item_key": "cpi_yoy"}, headers=hb).status_code == 201

    reg_back = auth_client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "supersecret1"})
    assert reg_back.status_code == 200
    assert auth_client.get(f"{C}/saved").json()["count"] == 1  # запись A цела


# ── слежения и лента ──

def test_watch_flow_and_feed(auth_client, auth_env, on):
    seed(auth_client, auth_env, _seed_series)
    reg(auth_client)
    h = csrf_headers(auth_client)

    r = auth_client.post(f"{C}/watches", json={"subject_kind": "indicator", "subject_key": "cpi_yoy"}, headers=h)
    assert r.status_code == 201, r.text
    w = r.json()["item"]
    assert w["title"] == "Инфляция" and w["latest_date"] == "2026-08-01" and w["latest_value"] == 8.4
    assert w["last_seen_date"] == "2026-08-01" and w["is_new"] is False and w["channel"] == "inapp"

    again = auth_client.post(f"{C}/watches", json={"subject_kind": "indicator", "subject_key": "cpi_yoy"}, headers=h)
    assert again.status_code == 200 and again.json()["created"] is False
    assert auth_client.get(f"{C}/feed").json() == {"new_count": 0, "items": [], "watching": 1}

    # вышло новое значение
    async def release(s):
        ind = await s.scalar(select(Indicator).where(Indicator.code == "cpi_yoy"))
        s.add(IndicatorData(indicator_id=ind.id, date=date(2026, 9, 1), value=8.9))
    seed(auth_client, auth_env, release)

    feed = auth_client.get(f"{C}/feed").json()
    assert feed["new_count"] == 1 and feed["items"][0]["latest_date"] == "2026-09-01"
    assert feed["items"][0]["latest_value"] == 8.9 and feed["items"][0]["is_new"] is True
    lst = auth_client.get(f"{C}/watches").json()
    assert lst["new_count"] == 1 and lst["items"][0]["is_new"] is True

    seen = auth_client.post(f"{C}/feed/seen", headers=h)
    assert seen.status_code == 200 and seen.json()["new_count"] == 0
    assert auth_client.get(f"{C}/feed").json()["new_count"] == 0

    assert auth_client.delete(f"{C}/watches?subject_kind=indicator&subject_key=cpi_yoy", headers=h).json()["removed"] is True
    assert auth_client.get(f"{C}/watches").json()["count"] == 0


def test_watch_world_and_region_and_english(auth_client, auth_env, on):
    seed(auth_client, auth_env, _seed_series)
    reg(auth_client)
    h = csrf_headers(auth_client)
    w = auth_client.post(f"{C}/watches", json={"subject_kind": "world", "subject_key": "tr-gdp"}, headers=h).json()["item"]
    assert w["title"] == "ВВП Турции" and w["country_slug"] == "turkey" and w["latest_value"] == 1100
    rg = auth_client.post(f"{C}/watches", json={"subject_kind": "region", "subject_key": "reg-wage"}, headers=h).json()["item"]
    assert rg["title"] == "Зарплата" and rg["latest_date"] == "2024-01-01" and rg["frequency"] == "annual"
    en = auth_client.get(f"{C}/watches", headers={"X-FE-Locale": "en"}).json()["items"]
    assert {i["title"] for i in en} >= {"Turkey GDP"}


@pytest.mark.parametrize("body,status,code", [
    ({"subject_kind": "indicator", "subject_key": "missing"}, 404, "subject_not_found"),
    ({"subject_kind": "country", "subject_key": "turkey"}, 422, "invalid_kind"),
    ({"subject_kind": "indicator", "subject_key": "cpi_yoy", "channel": "email"}, 422, "invalid_channel"),
    ({"subject_kind": "indicator", "subject_key": ""}, 422, "invalid_key"),
])
def test_watch_validation(auth_client, auth_env, on, body, status, code):
    seed(auth_client, auth_env, _seed_series)
    reg(auth_client)
    r = auth_client.post(f"{C}/watches", json=body, headers=csrf_headers(auth_client))
    assert r.status_code == status and r.json()["detail"]["code"] == code
    assert count(auth_client, auth_env, UserWatch) == 0


def test_watch_hidden_series_not_followable(auth_client, auth_env, on):
    async def hidden(s):
        s.add(Indicator(code="hid", name="Скрытый", unit="%", frequency="monthly", is_active=True, is_listed=False))
    seed(auth_client, auth_env, hidden)
    reg(auth_client)
    r = auth_client.post(f"{C}/watches", json={"subject_kind": "indicator", "subject_key": "hid"}, headers=csrf_headers(auth_client))
    assert r.status_code == 404


def test_watch_limit_50(auth_client, auth_env, on):
    seed(auth_client, auth_env, _seed_series)
    reg(auth_client)
    h = csrf_headers(auth_client)
    import uuid as _uuid
    uid = _uuid.UUID(auth_client.get("/api/v1/auth/me").json()["user"]["id"])

    async def fill(s):
        for i in range(50):
            s.add(UserWatch(user_id=uid, subject_kind="indicator", subject_key=f"gone{i}"))
    seed(auth_client, auth_env, fill)
    r = auth_client.post(f"{C}/watches", json={"subject_kind": "indicator", "subject_key": "cpi_yoy"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "limit_reached"
    # ряды, исчезнувшие из каталога, не ломают список: available=false и не «новые»
    lst = auth_client.get(f"{C}/watches").json()
    assert lst["count"] == 50 and lst["new_count"] == 0 and not any(i["available"] for i in lst["items"])


def test_watches_isolated_between_users(auth_client, auth_env, on):
    seed(auth_client, auth_env, _seed_series)
    reg(auth_client, "a@example.com")
    wid = auth_client.post(f"{C}/watches", json={"subject_kind": "indicator", "subject_key": "cpi_yoy"},
                           headers=csrf_headers(auth_client)).json()["item"]["id"]
    reg(auth_client, "b@example.com")
    assert auth_client.get(f"{C}/watches").json()["count"] == 0
    assert auth_client.delete(f"{C}/watches/{wid}", headers=csrf_headers(auth_client)).status_code == 404


def test_feed_is_batched_not_per_watch(auth_client, auth_env, on):
    """Лента — пакетные запросы по типам рядов, а не запрос на каждое слежение."""
    seed(auth_client, auth_env, _seed_series)
    reg(auth_client)
    h = csrf_headers(auth_client)
    for kind, key in [("indicator", "cpi_yoy"), ("world", "tr-gdp"), ("region", "reg-wage")]:
        assert auth_client.post(f"{C}/watches", json={"subject_kind": kind, "subject_key": key}, headers=h).status_code == 201

    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    statements = []

    def spy(conn, cursor, statement, *a):
        statements.append(statement)
    event.listen(Engine, "before_cursor_execute", spy)
    try:
        assert auth_client.get(f"{C}/feed").status_code == 200
    finally:
        event.remove(Engine, "before_cursor_execute", spy)
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    # сессия+пользователь (2) + слежения (1) + по 2 запроса на indicator/world + 1 на region = не больше 10
    assert len(selects) <= 10, selects


# ── история выгрузок ──

TABLE = {"format": "csv", "filename": "cpi.csv", "value_label": "Инфляция, %", "indicator_name": "Инфляция",
         "country": "Россия", "points": [{"date": "2020-01-01", "actual": 1.0}, {"date": "2021-01-01", "actual": 2.0}]}


def test_export_history_records_for_signed_in(auth_client, auth_env, on):
    reg(auth_client)
    body = {**TABLE, "history": {"source": "chart", "subject_key": "cpi_yoy", "params": {"country": "russia", "rep": "yoy"}}}
    assert auth_client.post("/api/v1/export/table", json=body).status_code == 200
    hist = auth_client.get(f"{C}/exports").json()
    assert hist["total"] == 1
    e = hist["items"][0]
    assert e["source"] == "chart" and e["subject_key"] == "cpi_yoy" and e["format"] == "csv" and e["rows_count"] == 2
    assert e["params"]["rep"] == "yoy" and e["params"]["period"] == {"from": "2020-01-01", "to": "2021-01-01"}
    assert "points" not in e["params"]  # хранятся параметры, не данные и не файл


def test_export_history_defaults_without_hint(auth_client, on):
    reg(auth_client)
    assert auth_client.post("/api/v1/export/table", json=TABLE).status_code == 200
    e = auth_client.get(f"{C}/exports").json()["items"][0]
    assert e["source"] == "table" and e["subject_key"] == "Инфляция"


def test_export_history_not_written_when_flag_off_or_guest(auth_client, auth_env, monkeypatch):
    reg(auth_client)
    assert auth_client.post("/api/v1/export/table", json=TABLE).status_code == 200   # флаг выключен
    assert count(auth_client, auth_env, UserExport) == 0
    monkeypatch.setattr(settings, "cabinet_enabled", True)
    monkeypatch.setattr(settings, "download_anon_limit", 5)
    auth_client.cookies.clear()
    assert auth_client.post("/api/v1/export/table", json=TABLE).status_code == 200   # гость
    assert count(auth_client, auth_env, UserExport) == 0


def test_export_survives_history_failure(auth_client, on, monkeypatch):
    reg(auth_client)
    from app.services import cabinet as svc

    async def boom(*a, **kw):
        raise RuntimeError("db down")
    monkeypatch.setattr(svc, "record_export", boom)
    r = auth_client.post("/api/v1/export/table", json=TABLE)
    assert r.status_code == 200 and b"2020-01-01;1;" in r.content


def test_export_history_trimmed_to_200_and_deletable(auth_client, auth_env, on, monkeypatch):
    reg(auth_client)
    from app.services import cabinet as svc
    monkeypatch.setattr(svc, "EXPORT_HISTORY_LIMIT", 3)
    for i in range(5):
        r = auth_client.post("/api/v1/export/table", json={**TABLE, "history": {"subject_key": f"k{i}"}})
        assert r.status_code == 200
    items = auth_client.get(f"{C}/exports").json()["items"]
    assert [i["subject_key"] for i in items] == ["k4", "k3", "k2"]  # новые сверху, старые удалены
    h = csrf_headers(auth_client)
    assert auth_client.delete(f"{C}/exports/{items[0]['id']}", headers=h).status_code == 200
    assert auth_client.delete(f"{C}/exports/{items[0]['id']}", headers=h).status_code == 404
    assert auth_client.delete(f"{C}/exports", headers=h).json()["removed"] == 2
    assert auth_client.get(f"{C}/exports").json()["total"] == 0


def test_export_history_range_in_params_is_dropped_not_stored(auth_client, on):
    reg(auth_client)
    body = {**TABLE, "history": {"params": {"lower": [1], "upper": [2]}}}
    assert auth_client.post("/api/v1/export/table", json=body).status_code == 200
    e = auth_client.get(f"{C}/exports").json()["items"][0]
    assert e["params"] is None  # ни lower, ни upper не сохранены


def test_export_history_isolated(auth_client, on):
    reg(auth_client, "a@example.com")
    auth_client.post("/api/v1/export/table", json=TABLE)
    eid = auth_client.get(f"{C}/exports").json()["items"][0]["id"]
    reg(auth_client, "b@example.com")
    assert auth_client.get(f"{C}/exports").json()["total"] == 0
    assert auth_client.delete(f"{C}/exports/{eid}", headers=csrf_headers(auth_client)).status_code == 404


# ── настройки ──

def test_prefs_roundtrip_and_whitelist(auth_client, on):
    reg(auth_client)
    h = csrf_headers(auth_client)
    assert auth_client.get(f"{C}/prefs").json() == {"data": {}, "updated_at": None}
    r = auth_client.put(f"{C}/prefs", json={"locale": "en", "currency": "TRY", "home_country": "turkey",
                                            "units": "compact", "newsletter_topics": ["macro", "macro", "rates"]}, headers=h)
    assert r.status_code == 200
    assert r.json()["data"] == {"locale": "en", "currency": "TRY", "home_country": "turkey", "units": "compact",
                                "newsletter_topics": ["macro", "rates"]}
    # PUT заменяет целиком
    r = auth_client.put(f"{C}/prefs", json={"locale": "ru"}, headers=h)
    assert r.json()["data"] == {"locale": "ru"}
    assert auth_client.get(f"{C}/prefs").json()["data"] == {"locale": "ru"}


@pytest.mark.parametrize("body", [
    {"theme": "dark"},                      # неизвестное поле
    {"locale": "de"},
    {"currency": "try"},
    {"home_country": "Tur key"},
    {"units": "a b"},
    {"newsletter_topics": ["x"] * 13},
    {"newsletter_topics": ["bad topic!"]},
])
def test_prefs_rejects_unknown_or_malformed(auth_client, on, body):
    reg(auth_client)
    assert auth_client.put(f"{C}/prefs", json=body, headers=csrf_headers(auth_client)).status_code == 422


def test_prefs_isolated(auth_client, on):
    reg(auth_client, "a@example.com")
    auth_client.put(f"{C}/prefs", json={"locale": "en"}, headers=csrf_headers(auth_client))
    reg(auth_client, "b@example.com")
    assert auth_client.get(f"{C}/prefs").json()["data"] == {}


# ── личный календарь .ics ──

async def _seed_event(s):
    await _seed_series(s)
    ind = await s.scalar(select(Indicator).where(Indicator.code == "cpi_yoy"))
    from datetime import datetime
    s.add(EconomicEvent(
        title="Инфляция, мой выход; с запятой", title_en="Inflation", event_type="release", source="rosstat",
        indicator_id=ind.id, scheduled_date=date.today() + timedelta(days=3), is_estimated=False,
        reference_period="сентябрь", date_confidence="official_explicit", event_key="k1",
        source_url="https://rosstat.gov.ru/x", source_hash="h", last_seen_at=datetime(2026, 10, 1)))
    other = Indicator(code="other", name="Чужое", unit="%", frequency="monthly", is_active=True, is_listed=True)
    s.add(other)
    await s.flush()
    s.add(EconomicEvent(
        title="Не моё", event_type="release", source="rosstat", indicator_id=other.id,
        scheduled_date=date.today() + timedelta(days=4), is_estimated=False, date_confidence="official_explicit",
        event_key="k2", source_url="https://rosstat.gov.ru/y", source_hash="h", last_seen_at=datetime(2026, 10, 1)))


def test_calendar_feed_token_lifecycle_and_content(auth_client, auth_env, on):
    seed(auth_client, auth_env, _seed_event)
    reg(auth_client)
    h = csrf_headers(auth_client)
    assert auth_client.get(f"{C}/calendar-feed").json() == {"active": False}
    auth_client.post(f"{C}/watches", json={"subject_kind": "indicator", "subject_key": "cpi_yoy"}, headers=h)

    issued = auth_client.post(f"{C}/calendar-feed", headers=h).json()
    token = issued["token"]
    assert issued["active"] is True and issued["path"] == f"/api/v1/cabinet/calendar.ics?token={token}" and len(token) >= 40
    assert auth_client.get(f"{C}/calendar-feed").json() == {"active": True}

    # в БД лежит только хэш токена
    async def hashes(s):
        return [r.feed_token_hash for r in (await s.scalars(select(UserPreference))).all()]
    stored = seed(auth_client, auth_env, hashes)
    assert stored and token not in stored and len(stored[0]) == 64

    auth_client.cookies.clear()   # ленту читает календарь телефона без сессии
    ics = auth_client.get(f"{C}/calendar.ics?token={token}")
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    assert ics.headers["cache-control"] == "private, no-store" and ics.headers["x-robots-tag"] == "noindex"
    text = ics.text
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
    assert r"Инфляция\, мой выход\; с запятой (сентябрь)" in text.replace("\r\n ", "")
    assert "Не моё" not in text and text.count("BEGIN:VEVENT") == 1
    assert "DTSTART;VALUE=DATE:" in text and "DTSTAMP:" in text
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))

    assert auth_client.get(f"{C}/calendar.ics?token={'x' * 40}").status_code == 404
    assert auth_client.get(f"{C}/calendar.ics").status_code == 422

    # перевыпуск гасит старую ссылку
    reg_back = auth_client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "supersecret1"})
    assert reg_back.status_code == 200
    new_token = auth_client.post(f"{C}/calendar-feed", headers=csrf_headers(auth_client)).json()["token"]
    assert new_token != token
    auth_client.cookies.clear()
    assert auth_client.get(f"{C}/calendar.ics?token={token}").status_code == 404
    assert auth_client.get(f"{C}/calendar.ics?token={new_token}").status_code == 200


def test_calendar_feed_revoke_and_empty(auth_client, on):
    reg(auth_client)
    h = csrf_headers(auth_client)
    token = auth_client.post(f"{C}/calendar-feed", headers=h).json()["token"]
    empty = auth_client.get(f"{C}/calendar.ics?token={token}")
    assert empty.status_code == 200 and "BEGIN:VEVENT" not in empty.text   # нет слежений = пустой календарь
    assert auth_client.delete(f"{C}/calendar-feed", headers=h).json() == {"active": False, "removed": True}
    assert auth_client.get(f"{C}/calendar.ics?token={token}").status_code == 404
    assert auth_client.delete(f"{C}/calendar-feed", headers=h).json()["removed"] is False


def test_calendar_ics_flag_off_404(auth_client):
    assert auth_client.get(f"{C}/calendar.ics?token={'a' * 40}").status_code == 404


# ── удаление и выгрузка данных человека ──

def test_delete_account_removes_all_cabinet_rows(auth_client, auth_env, on):
    seed(auth_client, auth_env, _seed_series)
    reg(auth_client, "gone@example.com")
    h = csrf_headers(auth_client)
    auth_client.post(f"{C}/saved", json={"kind": "indicator", "item_key": "cpi_yoy"}, headers=h)
    auth_client.post(f"{C}/watches", json={"subject_kind": "indicator", "subject_key": "cpi_yoy"}, headers=h)
    auth_client.post("/api/v1/export/table", json=TABLE)
    auth_client.put(f"{C}/prefs", json={"locale": "en"}, headers=h)
    auth_client.post(f"{C}/calendar-feed", headers=h)
    for model in (UserSavedItem, UserWatch, UserExport, UserPreference):
        assert count(auth_client, auth_env, model) == 1, model

    # строки другого человека не должны пострадать
    keeper_id = None
    reg(auth_client, "keeper@example.com")
    auth_client.post(f"{C}/saved", json={"kind": "country", "item_key": "turkey"}, headers=csrf_headers(auth_client))
    assert auth_client.post("/api/v1/auth/login", json={"email": "gone@example.com", "password": "supersecret1"}).status_code == 200

    r = auth_client.delete("/api/v1/auth/account", headers=csrf_headers(auth_client))
    assert r.status_code == 200
    assert count(auth_client, auth_env, UserSavedItem) == 1   # осталась запись keeper
    assert count(auth_client, auth_env, UserWatch) == 0
    assert count(auth_client, auth_env, UserExport) == 0
    assert count(auth_client, auth_env, UserPreference) == 0


def test_account_export_includes_cabinet_sections(auth_client, auth_env, on):
    seed(auth_client, auth_env, _seed_series)
    reg(auth_client)
    h = csrf_headers(auth_client)
    auth_client.post(f"{C}/saved", json={"kind": "comparison", "item_key": "k", "title": "T", "payload": {"codes": ["a"]}}, headers=h)
    auth_client.post(f"{C}/watches", json={"subject_kind": "indicator", "subject_key": "cpi_yoy"}, headers=h)
    auth_client.post("/api/v1/export/table", json=TABLE)
    auth_client.put(f"{C}/prefs", json={"currency": "USD"}, headers=h)
    token = auth_client.post(f"{C}/calendar-feed", headers=h).json()["token"]
    r = auth_client.get("/api/v1/auth/account/export")
    assert r.status_code == 200
    data = r.json()
    assert data["saved_items"][0]["payload"] == {"codes": ["a"]} and data["saved_items"][0]["title"] == "T"
    assert data["watches"][0]["subject_key"] == "cpi_yoy"
    assert data["exports"][0]["format"] == "csv"
    assert data["preferences"] == {"data": {"currency": "USD"}, "calendar_feed_active": True}
    assert token not in r.text and "feed_token_hash" not in r.text


def test_account_export_cabinet_sections_empty_when_nothing_saved(auth_client):
    reg(auth_client)
    data = auth_client.get("/api/v1/auth/account/export").json()
    assert data["saved_items"] == [] and data["watches"] == [] and data["exports"] == []
    assert data["preferences"] == {"data": {}, "calendar_feed_active": False}
