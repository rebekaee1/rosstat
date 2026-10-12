"""Официальный прогноз МВФ (WEO) как публичный прогноз world-ряда (круг 12)."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from sqlalchemy import select

from app.services.imf_weo_adapter import (
    WEO_LUR,
    WEO_NGDP_RPCH,
    WEO_NGDPD,
    WeoProjection,
    parse_imf_weo_projections,
    parse_imf_weo_sdmx,
    weo_max_observation_year,
)
from app.services.world_official_forecast import (
    OFFICIAL_STRATEGY,
    check_official_projection,
    official_forecast_info,
    store_official_forecast,
)

TODAY = date(2026, 10, 12)


def _payload(code: str = "NGDP_RPCH", years=("2024", "2025", "2026", "2027", "2031"), update="9/25/2025"):
    values = {str(index): [str(1.0 + index)] for index in range(len(years))}
    return {
        "data": {
            "dataSets": [{"series": {"0:0:0": {"attributes": [0, update], "observations": values}}}],
            "structures": [{
                "dimensions": {
                    "series": [
                        {"id": "COUNTRY", "values": [{"id": "CHN"}]},
                        {"id": "INDICATOR", "values": [{"id": code}]},
                        {"id": "FREQUENCY", "values": [{"id": "A"}]},
                    ],
                    "observation": [{"id": "TIME_PERIOD", "values": [{"value": y} for y in years]}],
                },
                "attributes": {"series": [
                    {"id": "SCALE", "values": [{"id": "0"}]},
                    {"id": "COUNTRY_UPDATE_DATE"},
                ]},
            }],
        }
    }


def test_projection_is_the_first_year_after_observations_and_carries_vintage():
    payload = _payload()
    observations = parse_imf_weo_sdmx(payload)
    projections = parse_imf_weo_projections(payload, today=TODAY)

    assert weo_max_observation_year(WEO_NGDP_RPCH, TODAY) == 2025
    assert [item.period.year for item in observations if item.period.year >= 2024] == [2024, 2025]
    assert len(projections) == 1
    projection = projections[0]
    assert projection.country_iso3 == "CHN" and projection.weo_code == WEO_NGDP_RPCH
    assert [period.year for period, _ in projection.points] == [2026]
    assert projection.vintage == date(2025, 9, 25)


def test_far_projection_years_are_never_stored():
    projections = parse_imf_weo_projections(_payload(), today=TODAY)
    assert all(period.year <= 2026 for item in projections for period, _ in item.points)


def _history(last_year: int = 2025, count: int = 15, base: float = 5.0):
    return [(date(last_year - count + 1 + index, 1, 1), base + index * 0.1) for index in range(count)]


def _projection(code=WEO_NGDP_RPCH, year=2026, value=6.0, vintage=date(2025, 9, 25)):
    return WeoProjection("CHN", code, ((date(year, 1, 1), value),), vintage)


def test_check_accepts_adjacent_consistent_projection():
    points, reason = check_official_projection(
        weo_code=WEO_NGDP_RPCH, history=_history(), projection=_projection(), today=TODAY,
    )
    assert reason == "ok" and points == [(date(2026, 1, 1), 6.0)]


@pytest.mark.parametrize(
    "projection, code, expected",
    [
        (_projection(vintage=date(2024, 1, 1)), WEO_NGDP_RPCH, "vintage_too_old"),
        (_projection(year=2028), WEO_NGDP_RPCH, "projection_not_adjacent"),
        (_projection(value=500.0), WEO_NGDP_RPCH, "implausible_projection"),
        (_projection(code=WEO_LUR, value=140.0), WEO_LUR, "out_of_range"),
        (_projection(code=WEO_NGDPD, value=-3.0), WEO_NGDPD, "out_of_range"),
        (_projection(value=float("nan")), WEO_NGDP_RPCH, "non_finite_projection"),
    ],
)
def test_check_rejects_inconsistent_projection(projection, code, expected):
    history = _history(base=60.0) if code == WEO_LUR else _history()
    points, reason = check_official_projection(
        weo_code=code, history=history, projection=projection, today=TODAY,
    )
    assert points is None and reason == expected


def test_check_rejects_short_history():
    points, reason = check_official_projection(
        weo_code=WEO_NGDP_RPCH, history=_history(count=2), projection=_projection(), today=TODAY,
    )
    assert points is None and reason == "history_too_short"


@pytest.fixture
def china_env(auth_env):
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    ids: dict[str, int] = {}

    async def _seed():
        async with auth_env["session_maker"]() as db:
            cn = WorldCountry(
                code="CN", slug="china", name_ru="Китай", name_en="China",
                region_ru="Азия", sort_order=5,
            )
            db.add(cn)
            await db.flush()
            ind = WorldIndicator(
                country_id=cn.id,
                code="cn-weo-ngdp-rpch",
                provider="imf",
                dataset_id="WEO",
                slice_json={"weo_code": "NGDP_RPCH"},
                slice_hash="weo-ngdp-rpch-cn",
                name_ru="Рост реального ВВП",
                name_en="Real GDP growth",
                name_quality="curated",
                unit="PC",
                unit_ru="изменение за год, %",
                frequency="annual",
                category_ru="Национальные счета",
                source="Международный валютный фонд",
                source_url="https://www.imf.org/en/Publications/WEO",
                description="Рост реального ВВП — годовая оценка Международного валютного фонда.",
                methodology="Source: International Monetary Fund, World Economic Outlook.",
                history_start=date(2011, 1, 1),
                history_end=date(2025, 1, 1),
                points_count=15,
                is_listed=True,
            )
            db.add(ind)
            await db.flush()
            db.add_all([
                WorldDataPoint(indicator_id=ind.id, date=d, value=v) for d, v in _history()
            ])
            await db.commit()
            ids["indicator"] = ind.id

    asyncio.run(_seed())
    return ids


def _store(auth_env, indicator_id, points, vintage=date(2025, 9, 25)):
    async def _run():
        async with auth_env["session_maker"]() as db:
            outcome = await store_official_forecast(
                db, indicator_id=indicator_id, weo_code=WEO_NGDP_RPCH,
                points=points, vintage=vintage, history_end=date(2025, 1, 1), points_count=15,
            )
            await db.commit()
            return outcome

    return asyncio.run(_run())


def test_store_is_idempotent_and_replaces_on_new_vintage(auth_env, china_env):
    from app.models import WorldForecast

    pid = china_env["indicator"]
    assert _store(auth_env, pid, [(date(2026, 1, 1), 4.8)]) == "created"
    assert _store(auth_env, pid, [(date(2026, 1, 1), 4.8)]) == "unchanged"
    assert _store(auth_env, pid, [(date(2026, 1, 1), 4.6)], vintage=date(2026, 4, 14)) == "created"

    async def _rows():
        async with auth_env["session_maker"]() as db:
            return (await db.execute(
                select(WorldForecast).where(WorldForecast.world_indicator_id == pid)
            )).scalars().all()

    rows = asyncio.run(_rows())
    assert len(rows) == 2
    current = [row for row in rows if row.is_current]
    assert len(current) == 1 and current[0].strategy == OFFICIAL_STRATEGY
    assert current[0].gate_status == "passed" and current[0].mase is None
    assert official_forecast_info(current[0]) == {
        "provider": "imf", "publication": "World Economic Outlook", "vintage": "2026-04-14",
    }
    assert _store(auth_env, pid, None) == "withdrawn"


def test_api_shows_official_forecast_without_range_and_with_signature(auth_env, china_env):
    from fastapi.testclient import TestClient

    assert _store(auth_env, china_env["indicator"], [(date(2026, 1, 1), 4.8)]) == "created"
    with TestClient(auth_env["app"]) as client:
        meta = client.get("/api/v1/world/indicators/china/cn-weo-ngdp-rpch")
        assert meta.status_code == 200
        assert meta.json().get("forecast_available") is True
        data = client.get(
            "/api/v1/world/indicators/china/cn-weo-ngdp-rpch/data",
            params={"mode": "level", "include_forecast": True},
        )
    assert data.status_code == 200
    forecast = data.json()["forecast"]
    assert forecast is not None
    assert forecast["official"] == {
        "provider": "imf", "publication": "World Economic Outlook", "vintage": "2025-09-25",
    }
    assert forecast["quality"]["gate_status"] == "passed"
    assert forecast["quality"]["mase"] is None
    assert forecast["points"] == [{"date": "2026-01-01", "value": 4.8}]
    assert all(set(point) == {"date", "value"} for point in forecast["points"])  # никаких границ диапазона


def test_platform_pipeline_does_not_touch_official_imf_forecast():
    """Плановый пересчёт моделью платформы не снимает и не заменяет прогноз МВФ."""
    from types import SimpleNamespace

    from app.services.world_forecast_pipeline import retrain_world_indicator_forecast

    indicator = SimpleNamespace(id=1, provider="IMF", dataset_id="WEO")
    # БД не нужна: решение принимается до первого обращения к ней.
    assert asyncio.run(retrain_world_indicator_forecast(None, indicator)) == "official"


def test_circle12_flags_are_off_by_default():
    from app.config import Settings
    from app.services.imf_weo_adapter import WEO_BCA_NGDPD, WEO_CIRCLE12_CODES

    assert WEO_CIRCLE12_CODES == {WEO_NGDP_RPCH, WEO_BCA_NGDPD}
    for name in (
        "world_imf_official_forecast_enabled",
        "world_forecast_candidates_enabled",
        "rest_world_forecast_enabled",
    ):
        assert Settings.model_fields[name].default is False  # выпуск в два шага


def test_weo_categories_have_english_names():
    """Группы показателей МВФ (в том числе «Внешний сектор») в английском каталоге страны без кириллицы."""
    import re

    from app.services.imf_weo_adapter import WEO_SERIES
    from app.services.seo_i18n import localize_category_name

    for weo_code, meta in WEO_SERIES.items():
        name = localize_category_name(meta["category_ru"], locale="en")
        assert name and not re.search(r"[А-Яа-яЁё]", name), (weo_code, name)


def test_new_weo_series_have_readable_english_units(monkeypatch):
    """Рост реального ВВП и счёт текущих операций в EN: не «PC» и не «Percentage of gross domestic product (GDP)»."""
    from types import SimpleNamespace

    import app.api.world as world_api

    monkeypatch.setattr(world_api, "get_locale", lambda: "en")
    growth = SimpleNamespace(
        provider="imf", code="in-weo-ngdp-rpch", unit="PC", unit_ru="изменение за год, %",
        dataset_id="WEO", slice_json=None,
    )
    bca = SimpleNamespace(
        provider="imf", code="in-weo-bca", unit="PC_GDP", unit_ru="% ВВП", dataset_id="WEO", slice_json=None,
    )
    assert world_api._indicator_public_unit(growth) == "annual change, %"
    assert world_api._indicator_public_unit(bca) == "% of GDP"
    # В заголовках данных единица тоже не из понятия.
    assert world_api._concept_unit_for_indicator(object(), growth) == "annual change, %"
    assert world_api._concept_unit_for_indicator(object(), bca) == "% of GDP"
    monkeypatch.setattr(world_api, "get_locale", lambda: "ru")
    assert world_api._indicator_public_unit(bca) == "% ВВП"


def test_forecast_job_times_are_configurable_and_default_to_the_old_schedule():
    """Круг 13: время пакетов США и «остального мира» вынесено в настройки, по умолчанию прежнее (05:20 и 04:50 МСК)."""
    from app.config import Settings

    fields = Settings.model_fields
    assert (fields["us_world_forecast_hour"].default, fields["us_world_forecast_minute"].default) == (5, 20)
    assert (fields["rest_world_forecast_hour"].default, fields["rest_world_forecast_minute"].default) == (4, 50)
    assert (fields["europe_world_forecast_hour"].default, fields["europe_world_forecast_minute"].default) == (21, 0)
    assert fields["world_forecast_max_age_days_annual"].default == 0
    assert fields["world_forecast_max_age_days_quarterly"].default == 0


def test_europe_forecast_time_ceiling_has_its_own_setting_defaulting_to_the_common_one():
    from app.config import Settings

    assert Settings.model_fields["europe_world_forecast_max_run_seconds"].default == 0  # 0 = общий потолок
    assert Settings.model_fields["world_forecast_max_run_seconds"].default == 2400
