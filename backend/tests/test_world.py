"""Юнит-тесты мирового блока: режимы + smoke API (герметичный SQLite)."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.world_cards import build_modes_matrix, members_by_freq
from app.services.world_view_modes import (
    apply_mode,
    is_signed_or_zero_crossing,
    transform_avg_year,
    transform_index_first,
    transform_mom,
    transform_yoy,
)
from app.data.eurostat_titles_ru import (
    build_public_name,
    compose_title,
    is_listed_for_quality,
)


# --- pure modes -------------------------------------------------------------


def test_mom_and_yoy_arithmetic():
    series = [
        (date(2024, 1, 1), 100.0),
        (date(2024, 2, 1), 110.0),
        (date(2025, 1, 1), 120.0),
        (date(2025, 2, 1), 132.0),
    ]
    mom = dict(transform_mom(series))
    assert mom[date(2024, 2, 1)] == 10.0
    yoy = dict(transform_yoy(series))
    assert yoy[date(2025, 1, 1)] == 20.0
    assert yoy[date(2025, 2, 1)] == 20.0


def test_index_first_and_avg_year():
    series = [
        (date(2024, 1, 1), 50.0),
        (date(2024, 2, 1), 100.0),
        (date(2024, 3, 1), 150.0),
    ]
    idx = dict(transform_index_first(series))
    assert idx[date(2024, 1, 1)] == 100.0
    assert idx[date(2024, 2, 1)] == 200.0
    avg = dict(transform_avg_year(series))
    assert avg[date(2024, 1, 1)] == 100.0


class _Ind:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _matrix(freq, series, unit=""):
    ind = _Ind(
        code="x", frequency=freq, points_count=len(series),
        history_start=series[0][0], history_end=series[-1][0],
    )
    return build_modes_matrix(
        by_freq=members_by_freq([ind]),
        series_by_code={"x": series},
        unit=unit,
    )


def _available(modes):
    return {m["id"] for m in modes if m["available"]}


def test_signed_series_compares_in_units_not_percent():
    signed = [
        (date(2024, 1, 1), -10.0),
        (date(2024, 2, 1), 5.0),
        (date(2025, 1, 1), 8.0),
    ]
    assert is_signed_or_zero_crossing(signed)
    modes = _matrix("monthly", signed, unit="млн евро")
    ids = _available(modes)
    types = {m["type"] for m in modes}
    assert "yoy-monthly" not in ids
    assert "yoyabs-monthly" in ids
    assert "index" not in types  # база-100 у знакопеременного ряда переворачивает график
    assert "step-monthly" in ids
    by_id = {m["id"]: m for m in modes}
    assert by_id["step-monthly"]["unit"] == "млн евро"
    assert "forecast" not in types


def test_positive_monthly_has_full_matrix():
    series = [(date(2024, m, 1), 100.0 + m) for m in range(1, 13)]
    series += [(date(2025, m, 1), 120.0 + m) for m in range(1, 7)]
    modes = _matrix("monthly", series, unit="индекс")
    ids = _available(modes)
    assert {"level-monthly", "step-monthly", "yoy-monthly", "index-monthly"} <= ids
    assert {"level-quarterly", "level-annual"} <= ids  # агрегация вверх
    assert "yoyabs-monthly" not in ids  # процентный YoY уже покрывает сравнение
    by_id = {m["id"]: m for m in modes}
    assert by_id["step-monthly"]["unit"] == "%"
    assert apply_mode(series, "level")[0][1] == series[0][1]


def test_quarterly_has_qoq_not_mom():
    series = [(date(2024, m, 1), 10.0 + m) for m in (1, 4, 7, 10)]
    modes = _matrix("quarterly", series)
    ids = _available(modes)
    assert "step-quarterly" in ids
    assert "step-monthly" not in ids  # месячного ряда нет — агрегация вниз невозможна
    assert "level-annual" in ids


def test_annual_has_no_subannual_steps():
    series = [(date(y, 1, 1), float(y)) for y in range(2010, 2025)]
    ids = _available(_matrix("annual", series))
    assert "step-monthly" not in ids
    assert "step-quarterly" not in ids
    assert "level-annual" in ids


def test_title_curated_and_composer():
    r = compose_title("Unemployment by sex and age - monthly data", "une_rt_m")
    assert r.quality == "curated"
    assert "Безработица" in r.name_ru
    assert not any(c.isascii() and c.isalpha() for c in r.name_ru)
    assert is_listed_for_quality(r.quality)

    r2 = compose_title(
        "Completely unknown widget flux by xyzzy - monthly data",
        "zz_unknown_flux",
    )
    assert r2.quality == "raw"
    assert not is_listed_for_quality(r2.quality)


def test_build_public_name_distinguishes_measures():
    idx = build_public_name(
        "Гармонизированный индекс потребительских цен, помесячно",
        unit="I15",
        frequency="monthly",
    )
    yoy = build_public_name(
        "Гармонизированный индекс потребительских цен, помесячно",
        unit="RCH_A",
        frequency="monthly",
    )
    assert idx != yoy
    assert "индекс (2015 = 100)" in idx
    assert "изменение за год" in yoy
    assert not idx.endswith("помесячно")
    assert "помесячно" not in idx
    assert "помесячно" not in yoy
    assert "Счёт текущих операций" in compose_title("", "teibp010").name_ru
    assert "Россия" not in compose_title("", "teibp010").name_ru


def test_public_texts_name_country_not_template():
    from app.data.eurostat_titles_ru import (
        has_frequency_suffix,
        has_template_stub,
        public_description,
        public_seo_title,
    )

    title = public_seo_title(
        "Уровень безработицы, помесячно",
        country_prep="Германии",
        country_name_ru="Германия",
    )
    assert title == "Уровень безработицы в Германии — график и данные"
    assert not has_frequency_suffix(title)

    desc = public_description(
        "Уровень безработицы",
        "monthly",
        "% экономически активного населения",
        country_name_ru="Германия",
        country_prep="Германии",
        available_frequencies=["monthly", "quarterly"],
    )
    assert "Германии" in desc
    assert "по стране" not in desc
    assert "выбранной величины" not in desc
    assert not has_template_stub(desc)
    assert "по месяцам" in desc and "по кварталам" in desc
    assert "график и данные" not in desc  # не копия seo_title
    assert "Источник — Евростат" in desc


# --- API smoke (auth_env hermetic) ------------------------------------------


@pytest.fixture
def world_client(auth_env):
    import asyncio
    from fastapi.testclient import TestClient
    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            de = WorldCountry(
                code="DE", slug="germany", name_ru="Германия",
                name_en="Germany", region_ru="Европа", sort_order=1,
            )
            fr = WorldCountry(
                code="FR", slug="france", name_ru="Франция",
                name_en="France", region_ru="Европа", sort_order=2,
            )
            db.add_all([de, fr])
            await db.flush()
            ind = WorldIndicator(
                country_id=de.id,
                code="de-prc_hicp_midx-cp00-i15",
                dataset_id="prc_hicp_midx",
                slice_json={"unit": "I15", "coicop": "CP00", "freq": "M"},
                slice_hash="abc",
                name_ru="Гармонизированный индекс потребительских цен, помесячно",
                name_en="HICP - monthly data (index)",
                name_quality="curated",
                unit="I15",
                unit_ru="индекс 2015=100",
                frequency="monthly",
                category_ru="Цены",
                source="Евростат",
                source_url="https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx",
                description="Гармонизированный индекс потребительских цен в Германии — официальный ряд Евростата.",
                methodology="Источник данных — Евростат. Частота публикации — месячная.",
                history_start=date(2024, 1, 1),
                history_end=date(2025, 6, 1),
                points_count=18,
                is_listed=True,
            )
            raw = WorldIndicator(
                country_id=de.id,
                code="de-zz_raw",
                dataset_id="zz_raw",
                slice_json={},
                slice_hash="raw",
                name_ru="Экономический показатель",
                name_quality="raw",
                unit="",
                unit_ru="",
                frequency="monthly",
                category_ru="Прочее",
                source="Евростат",
                history_start=date(2024, 1, 1),
                history_end=date(2024, 8, 1),
                points_count=8,
                is_listed=False,
            )
            db.add_all([ind, raw])
            await db.flush()
            for i in range(18):
                y = 2024 + (i // 12)
                m = (i % 12) + 1
                db.add(WorldDataPoint(
                    indicator_id=ind.id,
                    date=date(y, m, 1),
                    value=100.0 + i,
                ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_world_countries(world_client):
    r = world_client.get("/api/v1/world/countries")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert body["countries"][0]["slug"] == "germany"
    assert "indicators_count" in body["countries"][0]


def test_world_country_detail_hides_raw(world_client):
    r = world_client.get("/api/v1/world/countries/germany")
    assert r.status_code == 200
    body = r.json()
    codes = [
        i["code"]
        for cat in body["categories"]
        for i in cat["indicators"]
    ]
    assert "de-prc_hicp_midx-cp00-i15" in codes
    assert "de-zz_raw" not in codes


def test_world_indicator_modes_and_data(world_client):
    meta = world_client.get("/api/v1/world/indicators/germany/de-prc_hicp_midx-cp00-i15")
    assert meta.status_code == 200
    body = meta.json()
    assert "primary_code" in body
    mode_ids = [m["id"] for m in body["modes"]]
    assert "level-monthly" in mode_ids
    assert "yoy-monthly" in mode_ids
    assert "step-monthly" in mode_ids
    assert all("forecast" not in m for m in mode_ids)

    data = world_client.get(
        "/api/v1/world/indicators/germany/de-prc_hicp_midx-cp00-i15/data",
        params={"mode": "level"},
    )
    assert data.status_code == 200
    payload = data.json()
    pts = payload["points"]
    assert len(pts) == 18
    assert pts[0]["value"] == 100.0
    assert payload["mode"] == "level-monthly"
    assert payload["aggregated"] is False

    yoy = world_client.get(
        "/api/v1/world/indicators/germany/de-prc_hicp_midx-cp00-i15/data",
        params={"mode": "yoy"},
    ).json()
    assert yoy["mode"] == "yoy-monthly"
    by_date = {p["date"]: p["value"] for p in yoy["points"]}
    assert by_date["2025-01-01"] == 12.0


def test_world_search_and_404(world_client):
    s = world_client.get("/api/v1/world/search", params={"q": "потребительских"})
    assert s.status_code == 200
    assert s.json()["total"] >= 1

    assert world_client.get("/api/v1/world/countries/no-such").status_code == 404
    assert world_client.get(
        "/api/v1/world/indicators/germany/no-such-code"
    ).status_code == 404
    assert world_client.get(
        "/api/v1/world/indicators/germany/no-such-code/data"
    ).status_code == 404
