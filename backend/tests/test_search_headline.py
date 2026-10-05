"""БД5: главное число рядов цен в поиске: инфляция за год, а не индекс или месячный прирост."""

from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

from app.services.search_latest import _months_back, attach_latest, world_price_headline


def _months(count: int, base: float, step: float, start=(2025, 1)):
    out, year, month = [], start[0], start[1]
    for i in range(count):
        out.append((date(year, month, 1), base + step * i))
        month += 1
        if month == 13:
            month, year = 1, year + 1
    return out


def _hicp(**kw):
    base = dict(
        provider="eurostat", dataset_id="prc_hicp_midx", code="de-prc_hicp_midx-cp00-i15",
        slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"}, unit="I15",
        unit_ru="индекс 2015=100", frequency="monthly",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_months_back_handles_year_boundaries():
    assert _months_back(date(2026, 3, 1), 12) == date(2025, 3, 1)
    assert _months_back(date(2026, 1, 1), 12) == date(2025, 1, 1)
    assert _months_back(date(2026, 1, 31), 11) is None or _months_back(date(2026, 1, 31), 11).month == 2


def test_eurostat_index_becomes_annual_inflation():
    series = _months(13, 120.0, 0.5)  # от янв 2025 до янв 2026
    headline = world_price_headline(_hicp(), series)
    assert headline["kind"] == "year_over_year" and headline["unit"] == "%"
    assert headline["date"] == "2026-01-01"
    assert round(headline["value"], 2) == round((126.0 / 120.0 - 1) * 100, 2)


def test_no_point_a_year_ago_means_no_number():
    series = _months(12, 120.0, 0.5)  # только 12 точек, год назад нет
    assert world_price_headline(_hicp(), series) is None
    gap = [row for row in _months(13, 120.0, 0.5) if row[0] != date(2025, 1, 1)]
    assert world_price_headline(_hicp(), gap) is None


def test_passthrough_and_index_minus_100_national_series():
    brazil = SimpleNamespace(
        provider="bcb_sgs", dataset_id="national", code="br-cpi-ipca-yoy", slice_json={},
        unit="PC", unit_ru="%", frequency="monthly",
    )
    assert world_price_headline(brazil, [(date(2026, 1, 1), 4.2)])["value"] == 4.2
    china = SimpleNamespace(
        provider="nbs", dataset_id="national", code="cn-cpi-all", slice_json={},
        unit="I", unit_ru="индекс", frequency="monthly",
    )
    assert world_price_headline(china, [(date(2026, 1, 1), 100.8)])["value"] == 0.8


def test_non_price_and_annual_series_get_no_headline():
    unemployment = SimpleNamespace(
        provider="bls", dataset_id="national", code="us-unemployment-rate", slice_json={},
        unit="PC_ACT", unit_ru="%", frequency="monthly",
    )
    assert world_price_headline(unemployment, _months(13, 4.0, 0.0)) is None
    assert world_price_headline(_hicp(frequency="annual"), _months(13, 120.0, 0.5)) is None


def test_federal_cpi_row_gets_the_stored_annual_figure_beside_the_monthly_value(auth_env):
    from app.models import Indicator, IndicatorData

    async def run():
        async with auth_env["session_maker"]() as db:
            cpi = Indicator(
                code="cpi", name="ИПЦ", unit="%", frequency="monthly", source="Росстат",
                parser_type="rosstat_cpi_xlsx", is_active=True, is_listed=True,
            )
            yoy = Indicator(
                code="cpi-yoy", name="ИПЦ год к году", unit="%", frequency="monthly",
                source="Росстат", parser_type="derived", is_active=True, is_listed=True,
            )
            db.add_all([cpi, yoy])
            await db.flush()
            for day, _ in _months(6, 0.0, 0.0):
                db.add(IndicatorData(indicator_id=cpi.id, date=day, value=100.4))
                db.add(IndicatorData(indicator_id=yoy.id, date=day, value=6.2))
            await db.commit()
            results = [
                {"kind": "russia", "code": "cpi", "frequency": "monthly"},
                {"kind": "russia", "code": "cpi-yoy", "frequency": "monthly"},
            ]
            await attach_latest(db, results)
            return results

    results = asyncio.run(run())
    monthly, annual = results
    assert monthly["latest"]["value"] == 100.4
    assert monthly["headline"] == {
        "kind": "year_over_year", "value": 6.2, "unit": "%",
        "date": "2025-06-01", "code": "cpi-yoy",
    }
    # Сам годовой ряд уже годовой: второе число ему не нужно.
    assert "headline" not in annual and annual["latest"]["value"] == 6.2


from test_world import world_client  # noqa: E402,F401  (фикстура мировой БД)


def test_country_card_for_prices_carries_the_annual_headline(world_client):
    body = world_client.get("/api/v1/world/countries/germany").json()
    items = [item for cat in body["categories"] for item in cat["indicators"]]
    prices = [item for item in items if item["code"] == "de-prc_hicp_midx-cp00-i15"]
    assert prices, "карточка цен Германии есть в каталоге страны"
    headline = prices[0]["headline"]
    assert headline["kind"] == "year_over_year" and headline["unit"] == "%"
    # Индекс вырос со 105 до 117 за год: около 11,4 %.
    assert round(headline["value"], 1) == round((117 / 105 - 1) * 100, 1)
    assert prices[0]["simple_name"] == "Цены"
