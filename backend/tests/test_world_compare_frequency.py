"""`/world/compare/series` с параметром `frequency`: свёртка вверх по правилам карточек, только полные периоды.

Месяц → квартал → год считается по политике понятия (у цен и безработицы — среднее). Тот же или более мелкий период
не достраивается, неизвестное значение игнорируется, а понятия, где реестр разрешает только официальный ряд,
остаются как есть.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.models import (
    Indicator,
    IndicatorData,
    WorldCountry,
    WorldDataPoint,
    WorldIndicator,
)


def _world_indicator(country, code, dataset, provider, slice_json, unit, unit_ru, frequency, history_end, *, points, listed=True):
    return WorldIndicator(
        country_id=country.id,
        code=code,
        dataset_id=dataset,
        provider=provider,
        slice_json=slice_json,
        slice_hash=code,
        name_ru="Ряд",
        name_quality="curated",
        unit=unit,
        unit_ru=unit_ru,
        frequency=frequency,
        category_ru="Цены",
        source="Тест",
        history_start=date(2023, 1, 1),
        history_end=history_end,
        points_count=points,
        is_listed=listed,
    )


def _months(start_year, start_month, count):
    year, month = start_year, start_month
    for _ in range(count):
        yield date(year, month, 1)
        month += 1
        if month == 13:
            year, month = year + 1, 1


@pytest.fixture
def frequency_client(auth_env):
    async def seed():
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany", region_ru="Европа", sort_order=1)
            jp = WorldCountry(code="JP", slug="japan", name_ru="Япония", name_en="Japan", region_ru="Азия", sort_order=2)
            db.add_all([de, jp])
            await db.flush()
            hicp = {"unit": "I15", "coicop": "CP00", "freq": "M"}
            rows = {
                # 26 месяцев: 2023 и 2024 полные, 2025 — только январь и февраль.
                "de_hicp": _world_indicator(de, "de-prc_hicp_minr-cp00-i15", "prc_hicp_minr", "eurostat", hicp,
                                            "I15", "индекс 2015=100", "monthly", date(2025, 2, 1), points=26),
                # Годовой ряд МВФ у Японии: просить у него месяц нельзя.
                "jp_weo": _world_indicator(jp, "jp-weo-pcpipch", "weo", "imf", {"weo_code": "PCPIPCH"}, "PC",
                                           "изменение за год, %", "annual", date(2025, 1, 1), points=3),
                # Квартальный ВВП: реестр разрешает только официальный ряд, расчёта года из кварталов нет.
                "de_gdp": _world_indicator(de, "de-namq_10_gdp-b1gq-sca-clv15_meur", "namq_10_gdp", "eurostat",
                                           {"na_item": "B1GQ", "s_adj": "SCA", "unit": "CLV15_MEUR"},
                                           "CLV15_MEUR", "в постоянных ценах 2015 года, млн евро", "quarterly",
                                           date(2024, 10, 1), points=8),
            }
            db.add_all(rows.values())
            await db.flush()
            for index, month in enumerate(_months(2023, 1, 26)):
                db.add(WorldDataPoint(indicator_id=rows["de_hicp"].id, date=month, value=100.0 + index))
            for year, value in ((2023, 3.2), (2024, 2.8), (2025, 2.5)):
                db.add(WorldDataPoint(indicator_id=rows["jp_weo"].id, date=date(year, 1, 1), value=value))
            for index in range(8):
                db.add(WorldDataPoint(
                    indicator_id=rows["de_gdp"].id,
                    date=date(2023 + index // 4, (index % 4) * 3 + 1, 1),
                    value=1000.0 + index,
                ))
            db.add_all([
                Indicator(code="cpi-yoy", name="ИПЦ за год", unit="%", frequency="monthly", source="Росстат",
                          parser_type="derived", is_active=True, is_listed=False),
                Indicator(code="unemployment", name="Безработица", unit="%", frequency="monthly", source="Росстат",
                          parser_type="rosstat_xlsx", is_active=True, is_listed=True),
                Indicator(code="population", name="Население", unit="млн чел.", frequency="annual", source="Росстат",
                          parser_type="rosstat_xlsx", is_active=True, is_listed=True),
            ])
            await db.flush()
            by_code = {row.code: row.id for row in (await db.execute(Indicator.__table__.select())).all()}
            for index, month in enumerate(_months(2023, 1, 21)):
                db.add(IndicatorData(indicator_id=by_code["cpi-yoy"], date=month, value=8.0 - index / 10))
                db.add(IndicatorData(indicator_id=by_code["unemployment"], date=month, value=3.0 + (index % 12) / 10))
            for year in (2023, 2024, 2025):
                db.add(IndicatorData(indicator_id=by_code["population"], date=date(year, 1, 1), value=146.0))
            await db.commit()

    asyncio.run(seed())
    with TestClient(auth_env["app"]) as client:
        yield client


def _series(client, country, concept, **params):
    response = client.get(f"/api/v1/world/compare/series/{country}/{concept}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _mean(values):
    return round(sum(values) / len(values), 4)


def test_monthly_series_folds_to_complete_years_by_mean(frequency_client):
    payload = _series(frequency_client, "germany", "hicp-index", frequency="annual")
    assert payload["meta"]["frequency"] == "annual"
    assert payload["meta"]["aggregated"] is True
    assert payload["meta"]["aggregation"] == {"source_frequency": "monthly", "policy": "mean"}
    assert payload["meta"]["indicator_code"] == "de-prc_hicp_minr-cp00-i15"
    assert payload["meta"]["unit"] == "индекс 2015=100"
    # 2025 — два месяца из двенадцати: неполный год не выдаётся.
    assert payload["data"] == [
        {"date": "2023-01-01", "value": _mean([100.0 + i for i in range(12)])},
        {"date": "2024-01-01", "value": _mean([100.0 + i for i in range(12, 24)])},
    ]


def test_monthly_series_folds_to_complete_quarters(frequency_client):
    payload = _series(frequency_client, "germany", "hicp-index", frequency="quarterly")
    assert payload["meta"]["frequency"] == "quarterly"
    dates = [point["date"] for point in payload["data"]]
    assert dates == [
        "2023-01-01", "2023-04-01", "2023-07-01", "2023-10-01",
        "2024-01-01", "2024-04-01", "2024-07-01", "2024-10-01",
    ]
    assert payload["data"][0]["value"] == _mean([100.0, 101.0, 102.0])


def test_same_or_finer_frequency_keeps_the_series_as_is(frequency_client):
    monthly = _series(frequency_client, "germany", "hicp-index", frequency="monthly")
    assert monthly["meta"]["frequency"] == "monthly"
    assert monthly["meta"]["aggregated"] is False
    assert len(monthly["data"]) == 26
    # Годовой ряд не превращается в месячный и квартальный.
    for requested in ("monthly", "quarterly", "annual"):
        japan = _series(frequency_client, "japan", "hicp-index", frequency=requested)
        assert japan["meta"]["frequency"] == "annual"
        assert japan["meta"]["aggregated"] is False
        assert len(japan["data"]) == 3


def test_unknown_frequency_is_ignored_and_yearly_is_annual(frequency_client):
    native = _series(frequency_client, "germany", "hicp-index")
    assert native["meta"]["frequency"] == "monthly"
    for requested in ("weekly", "daily", "foo", ""):
        assert _series(frequency_client, "germany", "hicp-index", frequency=requested)["data"] == native["data"]
    assert _series(frequency_client, "germany", "hicp-index", frequency="yearly")["meta"]["frequency"] == "annual"


def test_official_only_concept_is_never_calculated(frequency_client):
    payload = _series(frequency_client, "germany", "gdp-volume-quarterly", frequency="annual")
    assert payload["meta"]["frequency"] == "quarterly"
    assert payload["meta"]["aggregated"] is False
    assert len(payload["data"]) == 8


def test_russia_monthly_series_fold_to_complete_years_and_cache_stays_per_frequency(frequency_client):
    yearly = _series(frequency_client, "russia", "unemployment-rate", frequency="annual")
    assert yearly["meta"]["frequency"] == "annual"
    assert yearly["meta"]["aggregated"] is True
    # Ряд идёт 21 месяц с января 2023: полный год один — 2023.
    assert yearly["data"] == [{"date": "2023-01-01", "value": _mean([3.0 + i / 10 for i in range(12)])}]
    quarterly = _series(frequency_client, "russia", "hicp-index", frequency="quarterly")
    assert quarterly["meta"]["frequency"] == "quarterly"
    assert [point["date"] for point in quarterly["data"]][:2] == ["2023-01-01", "2023-04-01"]
    native = _series(frequency_client, "russia", "unemployment-rate")
    assert native["meta"]["frequency"] == "monthly"
    assert native["meta"]["aggregated"] is False
    assert len(native["data"]) == 21
    # Годовой ряд России остаётся годовым при любом запросе.
    population = _series(frequency_client, "russia", "population", frequency="annual")
    assert population["meta"]["frequency"] == "annual"
    assert population["meta"]["aggregated"] is False


@pytest.mark.parametrize(
    ("requested", "source", "expected"),
    [
        ("annual", "monthly", "annual"),
        ("quarterly", "monthly", "quarterly"),
        ("annual", "quarterly", "annual"),
        ("yearly", "monthly", "annual"),
        ("monthly", "monthly", None),
        ("quarterly", "quarterly", None),
        ("monthly", "annual", None),
        ("weekly", "monthly", None),
        ("", "monthly", None),
        (None, "monthly", None),
        ("annual", None, None),
    ],
)
def test_compare_target_frequency_only_goes_up(requested, source, expected):
    from app.services.world_compare import compare_target_frequency

    assert compare_target_frequency(requested, source) == expected


def test_official_sibling_must_be_the_same_measure():
    """Официальный ряд нужной частоты берётся, только если это тот же по смыслу ряд (единица и вид)."""
    from types import SimpleNamespace

    from app.data.world_concepts import CONCEPT_BY_SLUG
    from app.services.world_compare import official_compare_sibling

    concept = CONCEPT_BY_SLUG["unemployment-rate"]

    def national(ident, code, frequency, unit):
        return SimpleNamespace(
            id=ident, code=code, frequency=frequency, unit=unit, points_count=10, history_end=date(2025, 1, 1),
            dataset_id="national", provider="national", slice_json={}, is_listed=True, unit_ru=unit,
        )

    monthly = national(1, "zz-unemployment-m", "monthly", "% экономически активного населения")
    annual_same = national(2, "zz-unemployment-a", "annual", "% экономически активного населения")
    annual_other_unit = national(3, "zz-unemployment-b", "annual", "тыс. человек")
    codes = frozenset({"zz-unemployment-m", "zz-unemployment-a", "zz-unemployment-b"})
    picked = official_compare_sibling([monthly, annual_same, annual_other_unit], concept, codes, monthly, "annual")
    assert picked is not None and picked.code == "zz-unemployment-a"
    assert official_compare_sibling([monthly, annual_other_unit], concept, codes, monthly, "annual") is None
    assert official_compare_sibling([monthly], concept, codes, monthly, "annual") is None
