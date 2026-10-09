"""Круг 11, зона H: гигиена параметров событий на приёме (белый список, размер, почты и телефоны)."""
import asyncio
import json

from sqlalchemy import select

from app.models import BehaviorSession, FrontendEvent
from app.services.event_params import MAX_PARAMS_BYTES, sanitize_event_params


def test_signup_keeps_only_whitelisted_keys():
    cleaned = sanitize_event_params("signup", {
        "method": "yandex", "newsletter": 1, "site_locale": "ru", "trigger": "gate_download",
        "landing": "/indicator/cpi", "first_visit_days": 4, "authed": 0,
        "email": "x@y.ru", "display_name": "Иван", "note": "лишнее",
    })
    assert cleaned == {"method": "yandex", "newsletter": 1, "site_locale": "ru",
                       "trigger": "gate_download", "landing": "/indicator/cpi",
                       "first_visit_days": 4, "authed": 0}


def test_general_rules_drop_personal_keys_and_scrub_values():
    cleaned = sanitize_event_params("search_query", {
        "q": "напишите мне ivan@example.com или +7 (999) 123-45-67",
        "results": 0, "email": "a@b.ru", "user_phone": "123", "Password": "x", "ip": "1.2.3.4",
        "query_text": "ввп 2025", "bad key!": 1, "flag": True, "nothing": None,
    })
    assert cleaned["q"] == "напишите мне [скрыто] или [скрыто]"
    assert cleaned["results"] == 0 and cleaned["query_text"] == "ввп 2025"
    assert cleaned["flag"] is True and cleaned["nothing"] is None
    for dropped in ("email", "user_phone", "Password", "ip", "bad key!"):
        assert dropped not in cleaned


def test_size_ceiling_and_marker():
    big = {f"k{i}": "x" * 190 for i in range(30)}
    cleaned = sanitize_event_params("table_search", big)
    assert len(json.dumps(cleaned, ensure_ascii=False).encode()) <= MAX_PARAMS_BYTES
    assert cleaned["_truncated"] == 1 and len(cleaned) > 3


def test_long_strings_lists_and_nested_values_are_bounded():
    cleaned = sanitize_event_params("chart_zoom", {
        "s": "a" * 1000, "codes": list(range(100)), "nested": {"a": 1, "email": "q@w.er", "deep": {"x": 1}},
        "obj": object(), "nan": float("nan"),
    })
    assert len(cleaned["s"]) == 200
    assert len(cleaned["codes"]) == 20
    assert cleaned["nested"] == {"a": 1}  # второй уровень вложенности отбрасывается
    assert "obj" not in cleaned and "nan" not in cleaned


def test_non_dict_params_become_empty():
    assert sanitize_event_params("signup", None) == {}
    assert sanitize_event_params("signup", ["a"]) == {}


def test_collector_stores_clean_params(auth_client, auth_env):
    r = auth_client.post("/api/v1/analytics/events", json={
        "event_name": "search_query", "session_id": "s", "visitor_id": "v",
        "url": "https://ru.forecasteconomy.com/", "params": {"q": "почта bob@example.org", "results": 0, "email": "z@z.ru"},
    })
    assert r.status_code == 200 and r.json()["accepted"] is True
    r = auth_client.post("/api/v1/analytics/events", json={
        "event_name": "auth_error", "params": {"stage": "email_login", "code": "credentials", "email": "z@z.ru",
                                              "message": "Неверный пароль для z@z.ru"},
    })
    assert r.status_code == 200

    async def rows():
        async with auth_env["session_maker"]() as db:
            return (await db.execute(select(FrontendEvent).order_by(FrontendEvent.id))).scalars().all()

    stored = asyncio.run(rows())
    assert stored[0].params_json == {"q": "почта [скрыто]", "results": 0}
    assert stored[1].params_json == {"stage": "email_login", "code": "credentials"}


def test_behavior_portrait_stores_site_language_from_host(auth_client, auth_env):
    """Язык сайта сессии берётся по хосту запроса, а не из языка браузера."""
    batch = {"session_id": "sess-1", "visitor_id": "vis-1", "events": [
        {"t": "session_start", "ts": 1760000000000, "lang": "ru-RU", "url": "/"},
    ]}
    r = auth_client.post("/api/v1/analytics/behavior", json=batch, headers={"X-FE-Locale": "en"})
    assert r.status_code == 200, r.text

    async def rows():
        async with auth_env["session_maker"]() as db:
            return (await db.execute(select(BehaviorSession))).scalars().all()

    stored = asyncio.run(rows())
    assert len(stored) == 1
    assert stored[0].language == "ru-RU" and stored[0].site_locale == "en"
