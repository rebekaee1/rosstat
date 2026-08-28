"""Слияние карточек каталога страны: catalog_merge_key + предпочтение меры.

Владелец (2026-08-28): «смысл одинаковый → одна карточка, а ВНУТРИ показателя
разные режимы выбираются». Уровень/темп/среднегодовой одного предмета
схлопываются в одну карточку; разные срезы (coicop FOOD vs CP00) и разные
возрасты/полы — НЕ схлопываются.
"""

from __future__ import annotations

from datetime import date

import pytest


from app.data.eurostat_listing import (
    card_key,
    catalog_merge_key,
    measure_preference_rank,
)


def _mk(
    ind_id: int,
    code: str,
    dataset_id: str,
    unit: str,
    unit_ru: str,
    points: int = 100,
    slice_json: dict | None = None,
    provider: str = "eurostat",
    frequency: str = "monthly",
):
    """Объект с атрибутами WorldIndicator, достаточными для чистых функций."""
    from types import SimpleNamespace

    return SimpleNamespace(
        id=ind_id,
        code=code,
        country_id=7,
        provider=provider,
        dataset_id=dataset_id,
        unit=unit,
        unit_ru=unit_ru,
        slice_json=slice_json or {},
        points_count=points,
        frequency=frequency,
        name_quality="curated",
        name_ru=code,
    )


# --- catalog_merge_key: что схлопывается, что нет ----------------------------


def test_merge_key_ignores_measure_class():
    """Индекс I15 и темп PCH_PRE одного stem/slice — один merge-ключ."""
    idx = _mk(1, "at-prc_hicp_midx", "prc_hicp_midx", "I15", "индекс (2015 = 100)")
    pch = _mk(2, "at-ei_cphi_m", "ei_cphi_m", "PCH_PRE", "изменение к предыдущему периоду")
    k1 = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id=idx.dataset_id,
        unit=idx.unit, unit_ru=idx.unit_ru, slice_json=idx.slice_json,
    )
    k2 = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id=pch.dataset_id,
        unit=pch.unit, unit_ru=pch.unit_ru, slice_json=pch.slice_json,
    )
    assert k1 == k2
    # но card_key их разводит (мера — часть identity card_key)
    assert card_key(
        country_id=7, dataset_id=idx.dataset_id, unit=idx.unit,
        unit_ru=idx.unit_ru, slice_json=idx.slice_json,
    ) != card_key(
        country_id=7, dataset_id=pch.dataset_id, unit=pch.unit,
        unit_ru=pch.unit_ru, slice_json=pch.slice_json,
    )


def test_merge_key_does_not_merge_unemployment_level_and_count():
    """Регресс живой БД: уровень % (PC_ACT) и численность (THS_PER) — разные
    показатели, слияние запрещено даже при одинаковых стемах."""
    k1 = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="une_rt_m",
        unit="PC_ACT", unit_ru="% экономически активного населения",
        slice_json={"age": "TOTAL", "sex": "T", "freq": "M", "unit": "PC_ACT", "s_adj": "SA"},
    )
    k2 = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="une_rt_m",
        unit="THS_PER", unit_ru="тысяч человек",
        slice_json={"age": "TOTAL", "sex": "T", "freq": "M", "unit": "THS_PER", "s_adj": "SA"},
    )
    assert k1 != k2


def test_merge_key_housing_stem_alias():
    """prc_hpi + ei_hppi — одна карточка через существующий алиас стемов."""
    k1 = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="prc_hpi_q",
        unit="I15_Q", unit_ru="индекс (2015 = 100)",
        slice_json={"freq": "Q", "unit": "I15_Q", "purchase": "TOTAL"},
    )
    k2 = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="ei_hppi_q",
        unit="I25_NSA", unit_ru="индекс (2025 = 100)",
        slice_json={"freq": "Q", "unit": "I25_NSA", "indic": "TOTAL"},
    )
    assert k1 == k2


def test_merge_key_keeps_coicop_slices_apart():
    """COICOP CP00 (итог) vs FOOD (срез) — разные карточки."""
    k_total = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="prc_hicp_midx",
        unit="I15", unit_ru="индекс (2015 = 100)",
        slice_json={"freq": "M", "unit": "I15", "coicop": "CP00"},
    )
    k_food = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="prc_hicp_midx",
        unit="I15", unit_ru="индекс (2015 = 100)",
        slice_json={"freq": "M", "unit": "I15", "coicop": "FOOD"},
    )
    assert k_total != k_food


def test_merge_key_keeps_age_sex_slices_apart():
    """age TOTAL vs Y15-74 (не-тоталиш) и пол M/F — разные карточки."""
    k_total = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="une_rt_m",
        unit="PC_ACT", unit_ru="% экономически активного населения",
        slice_json={"freq": "M", "age": "TOTAL", "sex": "T"},
    )
    k_age = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="une_rt_m",
        unit="PC_ACT", unit_ru="% экономически активного населения",
        slice_json={"freq": "M", "age": "Y_LT25", "sex": "T"},
    )
    assert k_total != k_age
    k_m = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="une_rt_m",
        unit="PC_ACT", unit_ru="% экономически активного населения",
        slice_json={"freq": "M", "age": "TOTAL", "sex": "M"},
    )
    assert k_total != k_m
    # Y15-74 — totalish для рынка труда, эквивалентен отсутствию среза
    k_y1574 = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="une_rt_m",
        unit="PC_ACT", unit_ru="% экономически активного населения",
        slice_json={"freq": "M", "age": "Y15-74", "sex": "T"},
    )
    assert k_total == k_y1574


def test_merge_key_provider_does_not_merge():
    """Разные провайдеры с тем же dataset_id не сливаются (identity по ведомству)."""
    k1 = catalog_merge_key(
        country_id=7, provider="eurostat", dataset_id="prc_hicp_midx",
        unit="I15", unit_ru="индекс (2015 = 100)", slice_json={},
    )
    k2 = catalog_merge_key(
        country_id=7, provider="imf", dataset_id="prc_hicp_midx",
        unit="I15", unit_ru="индекс (2015 = 100)", slice_json={},
    )
    assert k1 != k2


# --- предпочтение меры --------------------------------------------------------


def test_measure_preference_level_beats_change_at_equal_depth():
    """При равной глубине primary = уровень (индекс), не %-изменение."""
    idx = _mk(1, "at-idx", "prc_hicp_midx", "I15", "индекс (2015 = 100)", points=100)
    pch = _mk(2, "at-pch", "ei_cphi_m", "PCH_PRE", "изменение к предыдущему периоду", points=100)
    assert measure_preference_rank(idx) < measure_preference_rank(pch)
    winner = min([idx, pch], key=measure_preference_rank)
    assert winner.code == "at-idx"


def test_measure_preference_deeper_wins_within_same_class():
    """Внутри одного класса меры (оба уровень) — самый глубокий ряд."""
    shallow = _mk(1, "at-a", "prc_hpi_q", "I15_Q", "индекс (2015 = 100)", points=20)
    deep = _mk(2, "at-b", "ei_hppi_q", "I25_NSA", "индекс (2025 = 100)", points=65)
    assert measure_preference_rank(deep) < measure_preference_rank(shallow)


# --- интеграция: country_detail ----------------------------------------------


@pytest.fixture
def merged_catalog_client(auth_env):
    """Австрия-подобный мини-датасет: HICP (индекс/темп/среднегодовой) + жильё."""
    import asyncio

    from fastapi.testclient import TestClient

    from app.models import WorldCountry, WorldDataPoint, WorldIndicator

    async def _seed():
        async with auth_env["session_maker"]() as db:
            at = WorldCountry(
                code="AT", slug="austria", name_ru="Австрия",
                name_en="Austria", region_ru="Европа", sort_order=1,
            )
            db.add(at)
            await db.flush()

            def _ind(code, ds, unit, unit_ru, freq, pts, slice_json, cat="Цены"):
                return WorldIndicator(
                    country_id=at.id,
                    code=code,
                    dataset_id=ds,
                    slice_json=slice_json,
                    slice_hash=code,
                    name_ru="Гармонизированный индекс потребительских цен"
                    if "prc_hicp" in ds or "cphi" in ds
                    else "Индекс цен на жильё",
                    name_quality="curated",
                    unit=unit,
                    unit_ru=unit_ru,
                    frequency=freq,
                    category_ru=cat,
                    source="Евростат",
                    history_start=date(2020, 1, 1),
                    history_end=date(2025, 6, 1),
                    points_count=pts,
                    is_listed=True,
                )

            inds = [
                # ГИПЦ: индекс месячный (канон), среднегодовой, темп ei_cphi
                _ind("at-prc_hicp_midx-cp00-i15", "prc_hicp_midx", "I15",
                     "индекс (2015 = 100)", "monthly", 60,
                     {"freq": "M", "unit": "I15", "coicop": "CP00"}),
                _ind("at-prc_hicp_aind-cp00-inx-a-avg", "prc_hicp_aind", "INX_A_AVG",
                     "индекс, среднегодовой", "annual", 30,
                     {"freq": "A", "unit": "INX_A_AVG", "coicop": "CP00"}),
                _ind("at-ei_cphi_m-total-rt1", "ei_cphi_m", "RT1",
                     "темп изменения к предыдущему периоду", "monthly", 60,
                     {"freq": "M", "unit": "RT1", "indic": "TOTAL"}),
                # жильё: квартальный индекс + среднегодовой + быстрая оценка
                _ind("at-prc_hpi_q-total-i15-q", "prc_hpi_q", "I15_Q",
                     "индекс (2015 = 100)", "quarterly", 40,
                     {"freq": "Q", "unit": "I15_Q", "purchase": "TOTAL"}),
                _ind("at-prc_hpi_a-total-i15-a-avg", "prc_hpi_a", "I15_A_AVG",
                     "индекс (2015 = 100), среднегодовой", "annual", 16,
                     {"freq": "A", "unit": "I15_A_AVG", "purchase": "TOTAL"}),
                _ind("at-ei_hppi_q-total-i25-nsa", "ei_hppi_q", "I25_NSA",
                     "индекс (2025 = 100)", "quarterly", 20,
                     {"freq": "Q", "unit": "I25_NSA", "indic": "TOTAL"}),
                # coicop FOOD — отдельный срез, не сливается с CP00
                _ind("at-prc_hicp_midx-food-i15", "prc_hicp_midx", "I15",
                     "индекс (2015 = 100)", "monthly", 60,
                     {"freq": "M", "unit": "I15", "coicop": "FOOD"}),
            ]
            db.add_all(inds)
            await db.flush()
            for ind in inds:
                for i in range(min(ind.points_count, 20)):
                    db.add(WorldDataPoint(
                        indicator_id=ind.id,
                        date=date(2025, 1 + (i % 6), 1 + (i % 28)),
                        value=100.0 + i,
                    ))
            await db.commit()

    asyncio.run(_seed())
    with TestClient(auth_env["app"]) as tc:
        yield tc


def test_country_detail_merges_measures(merged_catalog_client):
    """HICP-уровень (3 меры) и жильё (3 ряда) → 2 карточки + срез FOOD."""
    body = merged_catalog_client.get("/api/v1/world/countries/austria").json()
    cards = [i for cat in body["categories"] for i in cat["indicators"]]
    codes = [c["code"] for c in cards]

    assert "at-prc_hicp_midx-cp00-i15" in codes
    # среднегодовой и темп не дают отдельных карточек
    assert "at-prc_hicp_aind-cp00-inx-a-avg" not in codes
    assert "at-ei_cphi_m-total-rt1" not in codes
    # жильё схлопнулось в квартальный индекс (глубже ei_hppi при равном ранге)
    assert "at-prc_hpi_q-total-i15-q" in codes
    assert "at-prc_hpi_a-total-i15-a-avg" not in codes
    assert "at-ei_hppi_q-total-i25-nsa" not in codes
    # срез FOOD — своя карточка
    assert "at-prc_hicp_midx-food-i15" in codes

    hicp = next(c for c in cards if c["code"] == "at-prc_hicp_midx-cp00-i15")
    merged_codes = {m["code"] for m in hicp["merged_slices"]}
    assert merged_codes == {
        "at-prc_hicp_aind-cp00-inx-a-avg",
        "at-ei_cphi_m-total-rt1",
    }
    # контракт merged_slices: {code, unit}
    for m in hicp["merged_slices"]:
        assert set(m.keys()) == {"code", "unit"}
        assert isinstance(m["unit"], str)
    # контракт частот не сломан: список строк от выбранной primary
    assert isinstance(hicp["frequencies"], list)
    assert all(isinstance(f, str) for f in hicp["frequencies"])
    assert "monthly" in hicp["frequencies"]
    assert isinstance(hicp["aggregated_frequencies"], list)


def test_country_detail_merged_card_carries_full_freq_matrix(merged_catalog_client):
    """Частоты слитой карточки — от members card_key primary (контракт поля)."""
    body = merged_catalog_client.get("/api/v1/world/countries/austria").json()
    cards = [i for cat in body["categories"] for i in cat["indicators"]]
    hicp = next(c for c in cards if c["code"] == "at-prc_hicp_midx-cp00-i15")
    # primary prc_hicp_midx — месячный ряд; annual приходит через
    # aggregated_frequencies (расчётная частота), frequencies — официальные.
    assert "monthly" in hicp["frequencies"]
    assert "annual" not in hicp["frequencies"]
    assert "annual" in hicp["aggregated_frequencies"]
