"""Т-1/Т-4–Т-7/Т-15: route-smoke главных публичных контрактов API.

Гермeтично: SQLite-схема + fakeredis (fixture `auth_env` из conftest) +
посевные данные уровня «минимальный живой каталог». Ловим классы регрессий:
- слом сериализации/響онтракта ответа (фронт слепо доверяет полям);
- утечку unlisted/estimated наружу;
- 404/400-дисциплину на кривых кодах;
- невалидный SVG / потерянный CORS в embed (виджеты на чужих сайтах).
"""

from datetime import date, datetime, timedelta
from xml.etree import ElementTree

import pytest

from app.models import (
    EconomicEvent,
    Forecast,
    ForecastValue,
    Indicator,
    IndicatorData,
    Region,
    RegionDataPoint,
    RegionIndicator,
)


@pytest.fixture
def route_client(auth_env):
    """auth_client + посевные данные каталога/календаря/регионов."""
    import asyncio

    async def _seed():
        async with auth_env["session_maker"]() as db:
            cpi = Indicator(
                code="cpi", name="Индекс потребительских цен", unit="%",
                frequency="monthly", category="Цены", is_active=True, is_listed=True,
                model_config_json={"forecast_steps": 6},
            )
            hidden = Indicator(
                code="cpi-annual", name="ИПЦ (годовой)", unit="%",
                frequency="annual", category="Цены", is_active=True, is_listed=False,
            )
            key_rate = Indicator(
                code="key-rate", name="Ключевая ставка ЦБ", unit="%",
                frequency="daily", category="Ставки", is_active=True, is_listed=True,
            )
            db.add_all([cpi, hidden, key_rate])
            await db.flush()

            # Свежие точки — /today живёт с freshness-guard (В-4).
            db.add_all([
                IndicatorData(indicator_id=key_rate.id,
                              date=date.today() - timedelta(days=1), value=14.0),
                IndicatorData(indicator_id=key_rate.id, date=date.today(), value=14.25),
            ])

            base = date(2025, 1, 1)
            for i in range(14):
                m = base.month + i
                db.add(IndicatorData(
                    indicator_id=cpi.id,
                    date=date(base.year + (m - 1) // 12, (m - 1) % 12 + 1, 1),
                    value=100 + i * 0.2,
                ))

            fc = Forecast(indicator_id=cpi.id, model_name="SARIMA-test", is_current=True)
            db.add(fc)
            await db.flush()
            db.add(ForecastValue(
                forecast_id=fc.id, date=date(2026, 3, 1),
                value=103.1, lower_bound=102.0, upper_bound=104.0,
            ))

            db.add(EconomicEvent(
                title="Публикация ИПЦ", event_type="release", source="rosstat",
                indicator_id=cpi.id,
                scheduled_date=date.today() + timedelta(days=3),
                is_estimated=False, importance=3, status="scheduled",
                date_confidence="official_explicit",
                event_key="rosstat:cpi:2026-07", source_url="https://rosstat.gov.ru/x",
                source_hash="a" * 64, last_seen_at=datetime(2026, 7, 1),
            ))
            db.add(EconomicEvent(
                title="Оценочное событие (не публиковать)", event_type="release",
                source="rosstat", scheduled_date=date.today() + timedelta(days=4),
                is_estimated=True, importance=2, status="scheduled",
                date_confidence="estimated",
            ))

            country = Region(slug="russia", name="Российская Федерация", kind="country")
            r1 = Region(slug="moskva", name="г. Москва", kind="region", district_slug="cfo")
            r2 = Region(slug="tulskaya-oblast", name="Тульская область", kind="region",
                        district_slug="cfo")
            # Ещё 10 регионов: рейтинг /region-rating требует ≥ 10 строк.
            extras = [
                Region(slug=f"region-{i}", name=f"Регион {i}", kind="region",
                       district_slug="cfo")
                for i in range(10)
            ]
            ri = RegionIndicator(
                code="naselenie", table_code="1.1", section_num=1,
                section_name="Население", name="Численность населения",
                unit="тыс. человек", year_min=2023, year_max=2024, is_listed=True,
            )
            db.add_all([country, r1, r2, ri, *extras])
            await db.flush()
            seeded_regions = [(r1, (13100, 13150)), (r2, (1450, 1440))] + [
                (rg, (1000 + i, 1010 + i)) for i, rg in enumerate(extras)
            ]
            for region, vals in seeded_regions:
                for year, v in zip((2023, 2024), vals):
                    db.add(RegionDataPoint(
                        indicator_id=ri.id, region_id=region.id, year=year, value=v,
                    ))
            await db.commit()

    asyncio.get_event_loop_policy().new_event_loop()
    import asyncio as _a
    loop = _a.new_event_loop()
    try:
        loop.run_until_complete(_seed())
    finally:
        loop.close()

    from fastapi.testclient import TestClient

    with TestClient(auth_env["app"]) as tc:
        yield tc


# ── Т-1: indicators ──────────────────────────────────────────────────


def test_indicators_list_hides_unlisted(route_client):
    r = route_client.get("/api/v1/indicators")
    assert r.status_code == 200
    codes = [x["code"] for x in r.json()]
    assert "cpi" in codes and "cpi-annual" not in codes


def test_indicators_list_include_unlisted(route_client):
    r = route_client.get("/api/v1/indicators", params={"include_unlisted": True})
    codes = [x["code"] for x in r.json()]
    assert "cpi-annual" in codes


def test_indicators_list_category_filter(route_client):
    r = route_client.get("/api/v1/indicators", params={"category": "Цены"})
    assert [x["code"] for x in r.json()] == ["cpi"]
    assert route_client.get(
        "/api/v1/indicators", params={"category": "Несуществующая"}
    ).json() == []


def test_indicators_category_localized_en(route_client):
    """X-FE-Locale: en → display category EN; category_ru keeps DB key."""
    listed = route_client.get(
        "/api/v1/indicators",
        headers={"X-FE-Locale": "en"},
    )
    assert listed.status_code == 200
    cpi_list = next(x for x in listed.json() if x["code"] == "cpi")
    assert cpi_list["category"] == "Prices and inflation"
    assert cpi_list["category_ru"] == "Цены"

    detail = route_client.get(
        "/api/v1/indicators/cpi",
        headers={"X-FE-Locale": "en"},
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["category"] == "Prices and inflation"
    assert body["category_ru"] == "Цены"

    ru = route_client.get("/api/v1/indicators/cpi")
    assert ru.json()["category"] == "Цены"
    assert ru.json()["category_ru"] == "Цены"


def test_indicator_detail_and_errors(route_client):
    r = route_client.get("/api/v1/indicators/cpi")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "cpi" and body["current_value"] is not None
    assert route_client.get("/api/v1/indicators/no-such-code").status_code == 404
    assert route_client.get("/api/v1/indicators/DROP%20TABLE").status_code == 400


def test_indicator_data_and_stats(route_client):
    data = route_client.get("/api/v1/indicators/cpi/data").json()
    assert len(data["data"]) == 14
    assert data["data"][0]["date"] < data["data"][-1]["date"]
    stats = route_client.get("/api/v1/indicators/cpi/stats").json()
    assert stats["data_count"] == 14
    assert stats["lowest"]["value"] <= stats["average"] <= stats["highest"]["value"]
    assert stats["std_dev"] is not None and stats["std_dev"] > 0


# ── Т-4: calendar (ADR-0005 estimated не утекают) ────────────────────


def test_calendar_estimated_never_leaks(route_client):
    r = route_client.get("/api/v1/calendar", params={
        "from": str(date.today() - timedelta(days=1)),
        "to": str(date.today() + timedelta(days=30)),
    })
    assert r.status_code == 200
    events = r.json()["events"]
    titles = [e["title"] for e in events]
    assert "Публикация ИПЦ" in titles
    assert all("не публиковать" not in t for t in titles)
    assert all(e["is_estimated"] is False for e in events)


def test_calendar_upcoming_and_ical(route_client):
    up = route_client.get("/api/v1/calendar/upcoming")
    assert up.status_code == 200
    assert up.json()["total"] >= 1
    ical = route_client.get("/api/v1/calendar/export/ical")
    assert ical.status_code == 200
    assert "BEGIN:VCALENDAR" in ical.text
    assert "не публиковать" not in ical.text


def test_calendar_cache_scoped_by_locale(route_client, auth_env):
    """RU and EN must not share one Redis hit — titles come from event_public_title."""
    import asyncio

    from sqlalchemy import select

    async def _set_title_en():
        async with auth_env["session_maker"]() as db:
            ev = (
                await db.execute(
                    select(EconomicEvent).where(EconomicEvent.title == "Публикация ИПЦ")
                )
            ).scalar_one()
            ev.title_en = "CPI release"
            await db.commit()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_set_title_en())
    finally:
        loop.close()

    params = {
        "from": str(date.today() - timedelta(days=1)),
        "to": str(date.today() + timedelta(days=30)),
    }
    ru = route_client.get("/api/v1/calendar", params=params, headers={"X-FE-Locale": "ru"})
    en = route_client.get("/api/v1/calendar", params=params, headers={"X-FE-Locale": "en"})
    assert ru.status_code == 200 and en.status_code == 200

    ru_titles = {e["title"] for e in ru.json()["events"]}
    en_titles = {e["title"] for e in en.json()["events"]}
    assert "Публикация ИПЦ" in ru_titles
    assert "CPI release" in en_titles
    assert "Публикация ИПЦ" not in en_titles

    up_ru = route_client.get(
        "/api/v1/calendar/upcoming", headers={"X-FE-Locale": "ru"}
    ).json()
    up_en = route_client.get(
        "/api/v1/calendar/upcoming", headers={"X-FE-Locale": "en"}
    ).json()
    assert up_ru["events"][0]["title"] == "Публикация ИПЦ"
    assert up_en["events"][0]["title"] == "CPI release"

    # Same locale second hit still locale-correct (cache hit, not cross-locale).
    en2 = route_client.get("/api/v1/calendar", params=params, headers={"X-FE-Locale": "en"})
    assert "CPI release" in {e["title"] for e in en2.json()["events"]}
    assert "Публикация ИПЦ" not in {e["title"] for e in en2.json()["events"]}


# ── Т-5: embed SVG (живут на чужих сайтах) ───────────────────────────


def _assert_valid_svg(resp):
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.headers.get("access-control-allow-origin") == "*", "CORS обязателен"
    root = ElementTree.fromstring(resp.content)
    assert root.tag.endswith("svg")


def test_embed_spark_card_badge_valid_svg(route_client):
    _assert_valid_svg(route_client.get("/api/v1/embed/spark/cpi.svg"))
    _assert_valid_svg(route_client.get("/api/v1/embed/card/cpi.svg"))
    _assert_valid_svg(route_client.get("/api/v1/embed/badge/cpi.svg"))


def test_embed_card_404_for_unknown(route_client):
    assert route_client.get("/api/v1/embed/card/no-such.svg").status_code == 404


# ── Т-6: regions ─────────────────────────────────────────────────────


def test_regions_catalog_sections(route_client):
    r = route_client.get("/api/v1/regions/catalog")
    assert r.status_code == 200
    sections = r.json()["sections"]
    assert sections[0]["num"] == 1
    assert sections[0]["indicators"][0]["code"] == "naselenie"


def test_regions_heatmap(route_client):
    r = route_client.get("/api/v1/regions/heatmap/naselenie")
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2024
    slugs = {v["slug"] for v in body["values"]}
    assert {"moskva", "tulskaya-oblast"} <= slugs and len(slugs) == 12
    assert body["default_sort"] == "desc"
    assert body["rank_as_achievement"] is False
    assert body["polarity"] is None
    assert route_client.get("/api/v1/regions/heatmap/no-such").status_code == 404


def test_region_profile_vs_and_indicator(route_client):
    prof = route_client.get("/api/v1/regions/moskva")
    assert prof.status_code == 200
    vs = route_client.get("/api/v1/regions/vs/moskva/tulskaya-oblast")
    assert vs.status_code == 200
    detail = route_client.get("/api/v1/regions/moskva/i/naselenie")
    assert detail.status_code == 200
    body = detail.json()
    assert body["rank"]["default_sort"] == "desc"
    assert body["rank"]["rank_as_achievement"] is False
    assert body["rank"]["position"] == 1
    assert body["rank"]["top"][0]["slug"] == "moskva"
    assert route_client.get("/api/v1/regions/no-such-region").status_code == 404


# ── Т-15: dashboard / demographics / ticker / forecast ───────────────


def test_dashboard_sparklines(route_client):
    r = route_client.get("/api/v1/dashboard/sparklines")
    assert r.status_code == 200
    body = r.json()
    assert "prices" in body  # flagship cpi засеян
    assert body["prices"]["point_count"] > 0


def test_demographics_structure_shape(route_client):
    r = route_client.get("/api/v1/demographics/structure")
    assert r.status_code == 200
    assert "series" in r.json() or isinstance(r.json(), dict)


def test_ticker_live_empty_redis(route_client):
    r = route_client.get("/api/v1/ticker/live")
    assert r.status_code == 200
    body = r.json()
    assert body["snapshots"] == [] and "server_time" in body
    assert route_client.get("/api/v1/ticker/live?lane=russia").status_code == 200
    assert route_client.get("/api/v1/ticker/live?lane=world").status_code == 200
    assert route_client.get("/api/v1/ticker/live?lane=unknown").status_code == 200


def test_forecast_route(route_client):
    r = route_client.get("/api/v1/indicators/cpi/forecast")
    assert r.status_code == 200
    fc = r.json()["forecast"]
    assert fc["model_name"] == "SARIMA-test"
    assert fc["values"][0]["value"] == 103.1
    assert route_client.get("/api/v1/indicators/no-such/forecast").status_code == 404
