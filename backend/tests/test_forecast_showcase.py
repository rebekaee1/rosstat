"""Витрина «Прогнозы»: расчёт изменения, честные границы и API (герметичный SQLite)."""

from __future__ import annotations

import asyncio
from datetime import date

from app.services import forecast_showcase as fs


# --- чистые функции ---------------------------------------------------------


def test_horizon_accepts_one_year_and_rejects_short_or_long():
    assert fs.horizon_ok(date(2026, 8, 1), date(2027, 8, 1))
    assert fs.horizon_ok(date(2026, 4, 1), date(2027, 4, 1))  # квартальный ряд, 4 шага
    assert not fs.horizon_ok(date(2026, 8, 1), date(2026, 10, 1))
    assert not fs.horizon_ok(date(2026, 8, 1), date(2029, 8, 1))
    assert not fs.horizon_ok(None, date(2027, 8, 1))


def test_change_percent_series_is_points_and_level_series_is_percent():
    rate = fs.compute_change("percent", 2.4, 2.1)
    assert rate == {"unit": "points", "value": -0.3, "direction": "down"}
    index = fs.compute_change("level", 100.0, 102.5)
    assert index == {"unit": "percent", "value": 2.5, "direction": "up"}
    assert fs.compute_change("level", 100.0, 100.01)["direction"] == "flat"
    assert fs.compute_change("level", 0.0, 5.0) is None
    assert fs.compute_change("level", -3.0, 5.0) is None


def _rows(start_year: int, start_month: int, count: int, base: float, step: float):
    out = []
    year, month = start_year, start_month
    for i in range(count):
        out.append((date(year, month, 1), base + step * i))
        month += 1
        if month == 13:
            month, year = 1, year + 1
    return out


def test_build_item_keeps_history_and_future_only():
    actual = _rows(2023, 9, 36, 100.0, 0.2)
    last = actual[-1][0]
    forecast = [
        (d, v)
        for d, v in _rows(last.year + (last.month // 12), last.month % 12 + 1, 12, actual[-1][1] + 0.2, 0.2)
    ]
    item = fs.build_item(
        item_id="x", scope="world", theme="inflation", kind="level", title="T",
        country={"slug": "germany", "code": "DE", "name": "Германия"},
        unit="индекс", frequency="monthly", source="Евростат", path="/germany/indicator/x",
        actual=actual, forecast=forecast, updated=date(2026, 9, 1), verified=True,
    )
    assert item is not None
    assert len(item["history"]) == fs.HISTORY_POINTS["monthly"]
    assert item["history"][-1]["date"] == last.isoformat()
    assert item["forecast"][0]["date"] > item["last_actual"]["date"]
    assert item["change"]["horizon_months"] == 12
    assert item["change"]["unit"] == "percent" and item["change"]["direction"] == "up"
    # Только точечный прогноз: никаких границ диапазона ни в конце, ни по точкам.
    assert set(item["forecast_end"]) == {"date", "value"}
    assert all(set(row) == {"date", "value"} for row in item["forecast"])


def test_build_item_rejects_series_without_a_year_horizon():
    actual = _rows(2025, 1, 12, 5.0, 0.0)
    forecast = [(date(2026, 1, 1), 5.0), (date(2026, 2, 1), 5.1)]
    assert fs.build_item(
        item_id="x", scope="russia", theme="rates", kind="percent", title="T",
        country={"slug": "russia", "code": "RU", "name": "Россия"},
        unit="%", frequency="monthly", source="Банк России", path="/p",
        actual=actual, forecast=forecast, updated=None, verified=False,
    ) is None
    assert fs.build_item(
        item_id="x", scope="russia", theme="rates", kind="percent", title="T",
        country={"slug": "russia", "code": "RU", "name": "Россия"},
        unit="%", frequency="monthly", source="Банк России", path="/p",
        actual=[], forecast=forecast, updated=None, verified=False,
    ) is None


def test_pick_world_candidates_orders_by_priority_and_keeps_freshest_per_country():
    cands = [
        {"country_slug": "poland", "history_end": date(2026, 7, 1)},
        {"country_slug": "germany", "history_end": date(2026, 6, 1), "tag": "old"},
        {"country_slug": "germany", "history_end": date(2026, 8, 1), "tag": "new"},
        {"country_slug": "united-states", "history_end": date(2026, 8, 1)},
    ]
    picked = fs.pick_world_candidates(cands, max_items=3)
    assert [c["country_slug"] for c in picked] == ["united-states", "germany", "poland"]
    assert picked[1]["tag"] == "new"


def test_showcase_never_mentions_imf_projections_as_a_source():
    """Честная граница витрины записана в коде: ряды МВФ из выборки исключены."""
    class Ind:
        provider = "imf"
        code = "de-weo-pcpipch"
        frequency = "annual"
        dataset_id = "weo"
        slice_json = {"weo_code": "PCPIPCH"}
        unit = "PC"
        unit_ru = "изменение за год, %"

    assert fs._theme_for_world(Ind(), fs.WORLD_THEMES[0]) is False


# --- API на SQLite ----------------------------------------------------------


def _seed(session_maker):
    from app.models import (
        Forecast,
        ForecastValue,
        Indicator,
        IndicatorData,
        WorldCountry,
        WorldDataPoint,
        WorldDatasetState,
        WorldForecast,
        WorldForecastValue,
        WorldIndicator,
    )

    async def run():
        async with session_maker() as db:
            actual_months = _rows(2023, 9, 36, 3.0, 0.0)
            fc_months = _rows(2026, 9, 12, 3.0, 0.0)

            # Россия: безработица с текущим прогнозом на год.
            ind = Indicator(
                code="unemployment", name="Уровень безработицы", unit="%",
                frequency="monthly", source="Росстат", parser_type="rosstat_labor",
                is_active=True, is_listed=True,
            )
            db.add(ind)
            await db.flush()
            for d, v in actual_months:
                db.add(IndicatorData(indicator_id=ind.id, date=d, value=2.2 + (v - 3.0)))
            fc = Forecast(indicator_id=ind.id, model_name="Auto-test", is_current=True)
            db.add(fc)
            await db.flush()
            for i, (d, _v) in enumerate(fc_months):
                db.add(ForecastValue(
                    forecast_id=fc.id, date=d, value=2.4 - 0.05 * i,
                    lower_bound=2.0 - 0.05 * i, upper_bound=2.8 - 0.05 * i,
                ))

            # Мир: США, безработица (национальный ряд, прошёл проверку v2).
            us = WorldCountry(
                code="US", slug="united-states", name_ru="США",
                name_en="United States", region_ru="Америка", sort_order=1,
            )
            db.add(us)
            await db.flush()
            wi = WorldIndicator(
                country_id=us.id, code="us-unemployment-rate", dataset_id="us_bls",
                provider="bls", slice_json={}, slice_hash="us-ur",
                name_ru="Уровень безработицы", name_en="Unemployment rate",
                name_quality="curated", unit="PC_ACT", unit_ru="% экономически активного населения",
                frequency="monthly", category_ru="Рынок труда", source="Бюро трудовой статистики США",
                history_start=date(2023, 9, 1), history_end=date(2026, 8, 1),
                points_count=36, is_listed=True,
            )
            db.add(wi)
            await db.flush()
            for d, v in actual_months:
                db.add(WorldDataPoint(indicator_id=wi.id, date=d, value=4.0 + (v - 3.0)))
            wf = WorldForecast(
                world_indicator_id=wi.id, strategy="monthly_auto", model_name="World-test-v2",
                model_params={"method_version": 2}, gate_status="passed",
                gate_reason="beats_baseline", mase=0.7, baseline_mase=1.0,
                origins=8, horizon=12, is_current=True,
            )
            db.add(wf)
            await db.flush()
            for i, (d, _v) in enumerate(fc_months):
                db.add(WorldForecastValue(
                    forecast_id=wf.id, date=d, value=4.1 + 0.02 * i,
                    lower_bound=3.7, upper_bound=4.5,
                ))

            # Ряд МВФ без прогноза платформы в витрину не попадает.
            weo = WorldIndicator(
                country_id=us.id, code="us-weo-lur", dataset_id="weo", provider="imf",
                slice_json={"weo_code": "LUR"}, slice_hash="us-lur-weo",
                name_ru="Уровень безработицы", name_quality="curated", unit="PC_ACT",
                unit_ru="% экономически активного населения", frequency="annual",
                category_ru="Рынок труда", source="МВФ",
                history_start=date(2000, 1, 1), history_end=date(2026, 1, 1),
                points_count=27, is_listed=True,
            )
            db.add(weo)
            await db.commit()

    asyncio.run(run())


def test_showcase_api_returns_only_real_forecasts(auth_env):
    from fastapi.testclient import TestClient

    _seed(auth_env["session_maker"])
    with TestClient(auth_env["app"]) as tc:
        response = tc.get("/api/v1/forecasts/showcase")
    assert response.status_code == 200
    assert response.headers["vary"] == "Host, x-fe-locale"
    body = response.json()
    ids = {item["id"]: item for item in body["items"]}
    assert set(ids) == {"russia-unemployment", "united-states-unemployment"}
    ru = ids["russia-unemployment"]
    assert ru["scope"] == "russia" and ru["verified"] is False
    assert ru["path"] == "/russia/indicator/unemployment"
    assert ru["change"]["unit"] == "points" and ru["change"]["direction"] == "down"
    # В базе границы есть, в публичном ответе их нет: только точечный прогноз.
    assert set(ru["forecast_end"]) == {"date", "value"}
    for item in body["items"]:
        assert all(set(row) == {"date", "value"} for row in item["forecast"])
    assert "lower" not in response.text and "upper" not in response.text
    assert "lower_bound" not in response.text and "upper_bound" not in response.text
    us = ids["united-states-unemployment"]
    assert us["scope"] == "world" and us["verified"] is True
    assert us["path"] == "/united-states/indicator/us-unemployment-rate"
    assert us["change"]["direction"] == "up"
    assert [t["id"] for t in body["themes"]] == ["unemployment"]
    assert body["locale"] == "ru"


def test_showcase_english_titles_and_unit(auth_env):
    from fastapi.testclient import TestClient

    _seed(auth_env["session_maker"])
    with TestClient(auth_env["app"]) as tc:
        body = tc.get("/api/v1/forecasts/showcase", headers={"X-FE-Locale": "en"}).json()
    titles = {item["id"]: item["title"] for item in body["items"]}
    assert titles["russia-unemployment"] == "Russia: unemployment rate"
    assert titles["united-states-unemployment"] == "United States: unemployment rate"
    assert body["locale"] == "en"
    assert [t["name"] for t in body["themes"]] == ["Jobs"]


def test_showcase_empty_database_is_an_honest_empty_list(auth_env):
    from fastapi.testclient import TestClient

    with TestClient(auth_env["app"]) as tc:
        response = tc.get("/api/v1/forecasts/showcase")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["themes"] == []


def test_forecasts_page_is_server_rendered_from_the_same_data(auth_env):
    from fastapi.testclient import TestClient

    _seed(auth_env["session_maker"])
    with TestClient(auth_env["app"]) as tc:
        response = tc.get("/seo/page/forecasts")
    assert response.status_code == 200
    html = response.text
    assert "<h1>Прогнозы</h1>" in html
    assert 'href="/russia/indicator/unemployment"' in html
    assert 'href="/united-states/indicator/us-unemployment-rate"' in html
    assert "Россия: безработица" in html and "США: безработица" in html
    assert "ниже на" in html and "выше на" in html
    assert 'rel="canonical" href="' in html and "/forecasts" in html
    # Вторая ссылка про метод остаётся на странице.
    assert 'href="/methodology#read"' in html
    assert "·" not in html.split("<main", 1)[1]
    # Диапазона прогноза нет ни в таблицах, ни в описании: только точечное значение.
    low = html.lower()
    assert "коридор" not in low and "диапазон" not in low and "интервал" not in low


def test_forecasts_page_without_data_is_still_an_honest_text_page(auth_env):
    from fastapi.testclient import TestClient

    with TestClient(auth_env["app"]) as tc:
        response = tc.get("/seo/page/forecasts")
    assert response.status_code == 200
    assert "Чего здесь нет" in response.text
    assert "<table" not in response.text


def test_forecasts_page_english(auth_env):
    from fastapi.testclient import TestClient

    _seed(auth_env["session_maker"])
    with TestClient(auth_env["app"]) as tc:
        html = tc.get("/seo/page/forecasts", headers={"X-FE-Locale": "en"}).text
    assert "<h1>Forecasts</h1>" in html
    assert "Russia: unemployment rate" in html
    assert "percentage points" in html
    low = html.lower()
    assert "range" not in low and "corridor" not in low and "confidence interval" not in low


def test_forecasts_is_a_platform_path_not_a_country_slug():
    from app.services import site_paths
    from app.services.seo_content import STATIC_PAGES

    assert site_paths.forecasts() == "/forecasts"
    assert site_paths.is_reserved_first_segment("forecasts")
    assert any(path == "/forecasts" for path, _freq, _prio in STATIC_PAGES)


def test_nginx_routes_forecasts_to_the_ssr_page_and_guards_the_country_slug():
    from pathlib import Path

    conf = (Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "compare|forecasts|calculator|widgets)/?$" in conf
    # Каждый шаблон «слаг страны» исключает служебный сегмент, иначе /forecasts стал бы страной.
    assert conf.count("compare$|forecasts$|widgets$") >= 6
    assert "compare$|widgets$" not in conf


def test_russian_inflation_uses_twelve_month_cumulative_not_monthly_index(auth_env):
    from fastapi.testclient import TestClient

    from app.models import Forecast, ForecastValue, Indicator, IndicatorData

    async def seed():
        async with auth_env["session_maker"]() as db:
            ind = Indicator(
                code="cpi", name="ИПЦ", unit="%", frequency="monthly", source="Росстат",
                parser_type="rosstat_cpi_xlsx", is_active=True, is_listed=True,
                model_config_json={"forecast_steps": 12},
            )
            db.add(ind)
            await db.flush()
            for d, _v in _rows(2023, 9, 36, 0.0, 0.0):
                db.add(IndicatorData(indicator_id=ind.id, date=d, value=100.5))
            fc = Forecast(indicator_id=ind.id, model_name="CPI-combined", is_current=True)
            db.add(fc)
            await db.flush()
            for d, _v in _rows(2026, 9, 12, 0.0, 0.0):
                db.add(ForecastValue(
                    forecast_id=fc.id, date=d, value=100.4, lower_bound=100.2, upper_bound=100.6,
                ))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as tc:
        body = tc.get("/api/v1/forecasts/showcase").json()
    item = {i["id"]: i for i in body["items"]}["russia-inflation"]
    # Месячный индекс 100,5 даёт около 6,2 % за год, а не «100,5».
    assert 6.0 < item["last_actual"]["value"] < 6.3
    assert 4.8 < item["forecast_end"]["value"] < 5.1
    assert item["change"]["unit"] == "points" and item["change"]["direction"] == "down"
    assert item["unit"] == "% за 12 месяцев"


def test_eurostat_forecast_needs_a_confirmed_source_state(auth_env):
    from datetime import datetime

    from fastapi.testclient import TestClient

    from app.models import (
        WorldCountry, WorldDataPoint, WorldDatasetState, WorldForecast,
        WorldForecastValue, WorldIndicator,
    )

    async def seed(state_ok: bool):
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия", name_en="Germany",
                region_ru="Европа", sort_order=2,
            )
            db.add(de)
            await db.flush()
            ind = WorldIndicator(
                country_id=de.id, code="de-prc_hicp_midx-cp00-i15", dataset_id="prc_hicp_midx",
                provider="eurostat", slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="de-hicp", name_ru="Гармонизированный индекс потребительских цен",
                name_quality="curated", unit="I15", unit_ru="индекс 2015=100",
                frequency="monthly", category_ru="Цены", source="Евростат",
                history_start=date(2023, 9, 1), history_end=date(2026, 8, 1),
                points_count=36, is_listed=True,
            )
            db.add(ind)
            await db.flush()
            for i, (d, _v) in enumerate(_rows(2023, 9, 36, 0.0, 0.0)):
                db.add(WorldDataPoint(indicator_id=ind.id, date=d, value=120.0 + 0.2 * i))
            wf = WorldForecast(
                world_indicator_id=ind.id, strategy="monthly_auto", model_name="World-v2",
                model_params={"method_version": 2}, gate_status="passed",
                gate_reason="ok", mase=0.6, baseline_mase=1.0, origins=8, horizon=12,
                is_current=True, created_at=datetime(2026, 9, 5),
            )
            db.add(wf)
            await db.flush()
            for i, (d, _v) in enumerate(_rows(2026, 9, 12, 0.0, 0.0)):
                db.add(WorldForecastValue(
                    forecast_id=wf.id, date=d, value=127.4 + 0.2 * i,
                    lower_bound=126.0 + 0.2 * i, upper_bound=129.0 + 0.2 * i,
                ))
            if state_ok:
                db.add(WorldDatasetState(
                    provider="eurostat", dataset_id="prc_hicp_midx", status="ok",
                    last_success_at=datetime(2026, 9, 1),
                ))
            await db.commit()

    asyncio.run(seed(False))
    with TestClient(auth_env["app"]) as tc:
        assert "germany-inflation" not in {i["id"] for i in tc.get("/api/v1/forecasts/showcase").json()["items"]}


def test_eurostat_forecast_appears_when_source_state_is_ok(auth_env):
    from datetime import datetime

    from fastapi.testclient import TestClient

    from app.models import (
        WorldCountry, WorldDataPoint, WorldDatasetState, WorldForecast,
        WorldForecastValue, WorldIndicator,
    )

    async def seed():
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия", name_en="Germany",
                region_ru="Европа", sort_order=2,
            )
            db.add(de)
            await db.flush()
            ind = WorldIndicator(
                country_id=de.id, code="de-prc_hicp_midx-cp00-i15", dataset_id="prc_hicp_midx",
                provider="eurostat", slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="de-hicp", name_ru="Гармонизированный индекс потребительских цен",
                name_quality="curated", unit="I15", unit_ru="индекс 2015=100",
                frequency="monthly", category_ru="Цены", source="Евростат",
                history_start=date(2023, 9, 1), history_end=date(2026, 8, 1),
                points_count=36, is_listed=True,
            )
            db.add(ind)
            await db.flush()
            for i, (d, _v) in enumerate(_rows(2023, 9, 36, 0.0, 0.0)):
                db.add(WorldDataPoint(indicator_id=ind.id, date=d, value=120.0 + 0.2 * i))
            wf = WorldForecast(
                world_indicator_id=ind.id, strategy="monthly_auto", model_name="World-v2",
                model_params={"method_version": 2}, gate_status="passed",
                gate_reason="ok", mase=0.6, baseline_mase=1.0, origins=8, horizon=12,
                is_current=True, created_at=datetime(2026, 9, 5),
            )
            db.add(wf)
            await db.flush()
            for i, (d, _v) in enumerate(_rows(2026, 9, 12, 0.0, 0.0)):
                db.add(WorldForecastValue(
                    forecast_id=wf.id, date=d, value=127.4 + 0.2 * i,
                    lower_bound=126.0 + 0.2 * i, upper_bound=129.0 + 0.2 * i,
                ))
            db.add(WorldDatasetState(
                provider="eurostat", dataset_id="prc_hicp_midx", status="ok",
                last_success_at=datetime(2026, 9, 1),
            ))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as tc:
        body = tc.get("/api/v1/forecasts/showcase").json()
    item = {i["id"]: i for i in body["items"]}["germany-inflation"]
    assert item["change"]["unit"] == "percent" and item["change"]["direction"] == "up"
    assert item["unit"] == "индекс 2015=100" and item["verified"] is True



# --- прогрев кэша ------------------------------------------------------------


def test_warm_showcase_cache_builds_both_locales_and_skips_when_cached(monkeypatch):
    """Старт собирает витрину ru и en в кэш; повторный старт без force ничего не пересобирает."""
    import app.api.forecast_showcase as api

    store: dict[str, dict] = {}
    built: list[str] = []

    class _Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *exc):
            return False

    async def fake_build(db, locale):
        built.append(locale)
        return {"locale": locale, "items": [{"id": locale}], "themes": []}

    async def fake_key(ns, rest):
        return f"{ns}:{rest}"

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl=None):
        store[key] = value

    import app.database as database

    monkeypatch.setattr(database, "async_session", lambda: _Session())
    monkeypatch.setattr(api, "build_showcase", fake_build)
    monkeypatch.setattr(api, "versioned_key", fake_key)
    monkeypatch.setattr(api, "cache_get", fake_get)
    monkeypatch.setattr(api, "cache_set", fake_set)

    assert asyncio.run(api.warm_showcase_cache()) == {"ru": 1, "en": 1}
    assert built == ["ru", "en"]
    assert len(store) == 2

    built.clear()
    assert asyncio.run(api.warm_showcase_cache()) == {"ru": 1, "en": 1}
    assert built == []  # ключ уже лежит в кэше

    assert asyncio.run(api.warm_showcase_cache(force=True)) == {"ru": 1, "en": 1}
    assert built == ["ru", "en"]


def test_warm_showcase_cache_survives_one_failing_locale(monkeypatch):
    import app.api.forecast_showcase as api
    import app.database as database

    class _Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *exc):
            return False

    async def fake_build(db, locale):
        if locale == "ru":
            raise RuntimeError("db down")
        return {"locale": locale, "items": [{"id": 1}, {"id": 2}], "themes": []}

    async def fake_key(ns, rest):
        return f"{ns}:{rest}"

    async def fake_get(key):
        return None

    async def fake_set(key, value, ttl=None):
        return None

    monkeypatch.setattr(database, "async_session", lambda: _Session())
    monkeypatch.setattr(api, "build_showcase", fake_build)
    monkeypatch.setattr(api, "versioned_key", fake_key)
    monkeypatch.setattr(api, "cache_get", fake_get)
    monkeypatch.setattr(api, "cache_set", fake_set)

    assert asyncio.run(api.warm_showcase_cache(force=True)) == {"en": 2}
