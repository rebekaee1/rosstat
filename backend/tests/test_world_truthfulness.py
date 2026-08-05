"""Тесты правдивости мирового блока: срез↔имя, правдоподобие, страны, headline."""

from __future__ import annotations

import pytest

from app.data.eurostat_country_visibility import (
    COUNTRY_VITRINE_MIN_CATEGORIES,
    COUNTRY_VITRINE_MIN_LISTED,
    country_passes_vitrine_threshold,
)
from app.data.eurostat_headline import HEADLINE_MEMBER_OVERRIDES, headline_priority_for
from app.data.eurostat_substance import (
    apply_substance_to_subject,
    slice_concept_matches_name,
    substance_subject_ru,
)
from app.data.eurostat_titles_ru import build_public_name, slice_reflected_in_name
from app.data.eurostat_units_ru import resolve_public_unit, unit_suffix
from app.services.eurostat_parser import choose_headline_slice, pick_headline_member
from app.services.world_plausibility import (
    check_constant_hundred_pct,
    check_constant_series,
    check_mostly_zeros,
    check_pct_with_huge_levels,
    check_tautological_gdp_pc_gdp,
    check_unit_domain_mismatch,
    is_plausible_for_listing,
    plausibility_reasons,
)


# --- headline overrides -----------------------------------------------------


def test_headline_override_deficit_prefers_b9_not_b1gq():
    dims = {
        "freq": ["A"],
        "unit": ["PC_GDP", "MIO_EUR"],
        "sector": ["S1", "S13"],
        "na_item": ["B1GQ", "B9", "B9_T3", "GD"],
        "geo": ["DE", "FR"],
        "time": ["2020", "2021"],
    }
    global_pick = pick_headline_member("na_item", dims["na_item"])
    assert global_pick == "B1GQ"  # глобальный приоритет всё ещё ВВП

    sliced = choose_headline_slice(dims, dataset_id="gov_10dd_edpt1")
    assert sliced["na_item"] == "B9"
    assert sliced["sector"] == "S13"
    assert headline_priority_for("gov_10dd_edpt1", "na_item")[0] == "B9"
    assert "gov_10dd_edpt1" in HEADLINE_MEMBER_OVERRIDES


def test_headline_override_gdp_prefers_volume_unit():
    dims = {
        "freq": ["A"],
        "unit": ["PC_GDP", "CLV15_MEUR", "CP_MEUR", "MIO_EUR"],
        "na_item": ["B1GQ", "P3"],
        "geo": ["DE"],
        "time": ["2020"],
    }
    sliced = choose_headline_slice(dims, dataset_id="nama_10_gdp")
    assert sliced["na_item"] == "B1GQ"
    assert sliced["unit"] == "CLV15_MEUR"


# --- slice vs name ----------------------------------------------------------


def test_substance_renames_deficit_when_slice_is_gdp():
    sl = {"na_item": "B1GQ", "unit": "PC_GDP", "sector": "S1"}
    assert substance_subject_ru(sl) == "Валовой внутренний продукт"
    assert apply_substance_to_subject("Дефицит или профицит бюджета", sl) == (
        "Валовой внутренний продукт"
    )
    assert slice_concept_matches_name("Дефицит или профицит бюджета", sl) is False
    assert slice_reflected_in_name("Дефицит или профицит бюджета", sl) is False


def test_substance_keeps_deficit_when_slice_is_b9():
    sl = {"na_item": "B9", "unit": "PC_GDP", "sector": "S13"}
    assert slice_concept_matches_name("Дефицит или профицит бюджета", sl) is True
    name = build_public_name(
        "Дефицит или профицит бюджета, за год",
        unit="PC_GDP",
        slice_json=sl,
        frequency="annual",
        dataset_id="gov_10dd_edpt1",
    )
    assert "дефицит" in name.lower() or "профицит" in name.lower()
    assert slice_reflected_in_name(name, sl) is True


def test_slice_name_mismatch_gdp_named_as_deficit():
    assert slice_concept_matches_name(
        "Дефицит или профицит бюджета, % ВВП",
        {"na_item": "B1GQ", "unit": "PC_GDP"},
    ) is False


# --- units ------------------------------------------------------------------


def test_interest_rate_unit_not_per_1000_pop():
    ru, prov = resolve_public_unit(
        dataset_id="ei_mfir_m",
        unit_code="",
        slice_json={"indic": "MF-DDI-RT", "freq": "M"},
    )
    assert ru == "%"
    assert "1000" not in (ru or "")


def test_sdg_pps_unit_not_percent():
    ru, _ = resolve_public_unit(
        dataset_id="sdg_10_10",
        unit_code="PC",
        slice_json={
            "unit": "PC",
            "indic_ppp": "EXP_PPS_EU27_2020_HAB",
            "ppp_cat18": "GDP",
        },
    )
    assert ru is not None
    assert not ru.startswith("%")
    assert "ППС" in ru or "душу" in ru.lower()


# --- plausibility -----------------------------------------------------------


def test_plausibility_tautological_gdp():
    vals = [100.0] * 20
    assert check_tautological_gdp_pc_gdp(
        slice_json={"na_item": "B1GQ", "unit": "PC_GDP"},
        unit="PC_GDP",
        values=vals,
    )
    assert not is_plausible_for_listing(
        name_ru="Валовой внутренний продукт, % ВВП",
        unit="PC_GDP",
        unit_ru="% ВВП",
        slice_json={"na_item": "B1GQ", "unit": "PC_GDP"},
        values=vals,
    )


def test_plausibility_constant_hundred():
    assert check_constant_hundred_pct(
        unit="PC_GDP", unit_ru="% ВВП", values=[100.0] * 12,
    )


def test_plausibility_pct_huge_levels():
    assert check_pct_with_huge_levels(
        unit="PC",
        unit_ru="%",
        slice_json={"unit": "PC", "indic_ppp": "EXP_PPS_EU27_2020_HAB"},
        values=[40000.0, 47700.0],
        name_ru="ВВП на душу населения по паритету покупательной способности",
    )


def test_plausibility_unit_domain_rates():
    assert check_unit_domain_mismatch(
        name_ru="Процентные ставки",
        unit_ru="на 1000 человек населения",
    )


def test_plausibility_constant_series_any_value():
    zeros = [0.0] * 20
    assert check_constant_series(values=zeros) == "constant_series"
    flat = [42.5] * 12
    assert check_constant_series(values=flat) == "constant_series"
    varying = [0.0] * 10 + [1.0]
    assert check_constant_series(values=varying) is None
    assert not is_plausible_for_listing(
        name_ru="Твёрдое топливо",
        unit="THS_T",
        unit_ru="тыс. тонн",
        slice_json={"siec": "C0100", "nrg_bal": "IPRD"},
        values=zeros,
        dataset_id="nrg_cb_sffm",
    )


def test_plausibility_mostly_zeros():
    vals = [0.0] * 95 + [1.0, 2.0, 0.0, 0.0, 0.0]
    assert check_mostly_zeros(values=vals) == "mostly_zeros"
    assert "mostly_zeros" in plausibility_reasons(
        name_ru="x", unit="GWH", unit_ru="ГВт·ч",
        slice_json={}, values=vals, dataset_id="nrg_cb_em",
    )


def test_energy_headline_prefers_inland_not_empty_production():
    dims = {
        "freq": ["M"],
        "unit": ["THS_T"],
        "siec": ["C0100", "C0200"],
        "nrg_bal": ["IPRD", "IMP", "GID_OBS", "EXP"],
        "geo": ["DE"],
        "time": ["2020"],
    }
    sliced = choose_headline_slice(dims, dataset_id="nrg_cb_sffm")
    assert sliced["nrg_bal"] == "GID_OBS"

    dims_em = {
        "freq": ["M"],
        "unit": ["GWH"],
        "siec": ["E7000"],
        "nrg_bal": ["IMP", "EXP", "AIM", "DL"],
        "geo": ["CY"],
        "time": ["2020"],
    }
    sliced_em = choose_headline_slice(dims_em, dataset_id="nrg_cb_em")
    assert sliced_em["nrg_bal"] == "AIM"


def test_country_visibility_idempotent_flag_logic():
    """Порог детерминирован: одни и те же входы → один вердикт (флаг в БД)."""
    median = 200.0
    assert country_passes_vitrine_threshold(
        listed_cards=3, category_count=2, median_listed=median,
    ) is False
    assert country_passes_vitrine_threshold(
        listed_cards=3, category_count=2, median_listed=median,
    ) is False  # повтор
    assert country_passes_vitrine_threshold(
        listed_cards=180, category_count=6, median_listed=median,
    ) is True
    assert country_passes_vitrine_threshold(
        listed_cards=180, category_count=6, median_listed=median,
    ) is True


def test_plausibility_extreme_tourism_change():
    vals = [-99.0, 100.0, 24563.0, -38.0] + [10.0] * 8
    assert "pct_out_of_range" in plausibility_reasons(
        name_ru="Прибытия в средства размещения",
        unit="PCH_SM",
        unit_ru="изменение к тому же периоду прошлого года",
        slice_json={"unit": "PCH_SM"},
        values=vals,
        dataset_id="tour_occ_arm",
    )


def test_plausibility_real_deficit_ok():
    vals = [-3.2, -2.8, -4.1, -5.0, -3.5, -2.1, -1.8, -2.4, -3.0, -2.7]
    assert is_plausible_for_listing(
        name_ru="Дефицит или профицит бюджета, % ВВП",
        unit="PC_GDP",
        unit_ru="% ВВП",
        slice_json={"na_item": "B9", "unit": "PC_GDP", "sector": "S13"},
        values=vals,
        dataset_id="gov_10dd_edpt1",
    )
    assert not plausibility_reasons(
        name_ru="Дефицит или профицит бюджета, % ВВП",
        unit="PC_GDP",
        unit_ru="% ВВП",
        slice_json={"na_item": "B9", "unit": "PC_GDP"},
        values=vals,
    )


# --- country visibility -----------------------------------------------------


def test_country_threshold_hides_partners():
    median = 230.0
    # Китай: 3 карточки
    assert country_passes_vitrine_threshold(
        listed_cards=3, category_count=2, median_listed=median,
    ) is False
    # США: 21
    assert country_passes_vitrine_threshold(
        listed_cards=21, category_count=4, median_listed=median,
    ) is False
    # UK Brexit-хвост: 15
    assert country_passes_vitrine_threshold(
        listed_cards=15, category_count=5, median_listed=median,
    ) is False
    # Армения: 17 / 1 тема
    assert country_passes_vitrine_threshold(
        listed_cards=17, category_count=1, median_listed=median,
    ) is False
    # Германия-уровень
    assert country_passes_vitrine_threshold(
        listed_cards=200, category_count=8, median_listed=median,
    ) is True
    # Порог на границе
    assert COUNTRY_VITRINE_MIN_LISTED == 30
    assert COUNTRY_VITRINE_MIN_CATEGORIES == 3
    assert country_passes_vitrine_threshold(
        listed_cards=30, category_count=3, median_listed=200,
    ) is True
    assert country_passes_vitrine_threshold(
        listed_cards=29, category_count=5, median_listed=200,
    ) is False


# --- единица рядом с числом -------------------------------------------------


@pytest.mark.parametrize(
    ("unit_ru", "expected"),
    [
        # безразмерные и описательные — справа от числа не ставятся
        ("индекс", ""),
        ("индекс (2015 = 100)", ""),
        ("индекс (2015 = 100), среднегодовой", ""),
        ("балл индекса", ""),
        ("сальдо", ""),
        ("изменение за год", ""),
        ("темп изменения к предыдущему периоду", ""),
        ("вероятность / лет", ""),
        ("раз", ""),
        # обычные единицы приписываются как есть
        ("%", "%"),
        ("тысяч человек", "тысяч человек"),
        ("млн евро", "млн евро"),
        ("на 1000 живорождённых", "на 1000 живорождённых"),
        ("пунктов индекса Джини", "пунктов индекса Джини"),
        # составные: приписывается измеримая часть
        ("в постоянных ценах 2015 года, млн евро", "млн евро"),
        ("млн евро, с сезонной корректировкой", "млн евро"),
        ("изменение за месяц, п.п.", "п.п."),
        ("на душу населения, евро", "евро"),
        ("", ""),
        (None, ""),
    ],
)
def test_unit_suffix_never_produces_broken_russian(unit_ru, expected):
    assert unit_suffix(unit_ru) == expected
