"""Закреплённые срезы пяти наборов, застрявших в карантине структуры (круг 12).

Евростат добавил единицу RCH_A в prc_hpi_* и сдвинул порядок кодов в
tour_dem_exac; общий приоритет выбрал другой срез, и все публичные карточки
«не нашли срез в новой структуре». Тест строит измерения набора как в ответе
API 12.10.2026 и сверяет выбор с срезами, под которые построены карточки на проде.
"""
import pytest

from app.services.eurostat_parser import choose_headline_slice, slice_hash

CASES = [
    (
        "prc_hpi_q",
        {"freq": ["Q"], "purchase": ["TOTAL", "DW_NEW", "DW_EXST"],
         "unit": ["I15_Q", "I25_Q", "RCH_Q", "RCH_A"], "geo": ["FR"], "time": ["2026-Q2"]},
        {"freq": "Q", "unit": "I15_Q", "purchase": "TOTAL"},
    ),
    (
        "prc_hpi_ooq",
        {"freq": ["Q"], "expend": ["TOTAL"], "unit": ["I15_Q", "I25_Q", "RCH_Q", "RCH_A"],
         "geo": ["FR"], "time": ["2026-Q2"]},
        {"freq": "Q", "unit": "I15_Q", "expend": "TOTAL"},
    ),
    (
        "prc_hpi_hsnq",
        {"freq": ["Q"], "purchase": ["TOTAL"], "unit": ["RCH_A", "NR"], "geo": ["FR"], "time": ["2026-Q1"]},
        {"freq": "Q", "unit": "NR", "purchase": "TOTAL"},
    ),
    (
        "prc_hpi_hsvq",
        {"freq": ["Q"], "purchase": ["TOTAL"], "unit": ["RCH_A", "EUR"], "geo": ["FR"], "time": ["2026-Q1"]},
        {"freq": "Q", "unit": "EUR", "purchase": "TOTAL"},
    ),
    (
        "tour_dem_exac",
        {"freq": ["A"], "accommod": ["TOTAL", "TOT_R"], "duration": ["N_GE1", "N1-3", "N_GE4"],
         "purpose": ["TOTAL", "PER"], "c_dest": ["EU27_2020_FOR", "NEU27_2020_FOR", "DOM", "FOR", "WORLD"],
         "statinfo": ["TOTAL", "AVG_TRP"], "unit": ["EUR"], "geo": ["FR"], "time": ["2024"]},
        {"freq": "A", "unit": "EUR", "c_dest": "DOM", "purpose": "TOTAL", "accommod": "TOTAL",
         "duration": "N_GE1", "statinfo": "TOTAL"},
    ),
]


@pytest.mark.parametrize("dataset_id,dims,expected", CASES, ids=[c[0] for c in CASES])
def test_headline_slice_matches_published_cards(dataset_id, dims, expected):
    got = choose_headline_slice(dims, dataset_id=dataset_id)
    assert got == expected
    assert slice_hash(got) == slice_hash(expected)


def test_without_pins_the_new_unit_flips_the_slice():
    """Страж причины: без закрепления RCH_A выигрывает у I15_Q (то и было в проде)."""
    dims = {"freq": ["Q"], "purchase": ["TOTAL"], "unit": ["I15_Q", "I25_Q", "RCH_Q", "RCH_A"],
            "geo": ["FR"], "time": ["2026-Q2"]}
    assert choose_headline_slice(dims, dataset_id="some_new_hpi")["unit"] == "RCH_A"


def test_tour_dem_exac_expansion_reproduces_all_five_published_slices():
    """Круг починки 27.10.2026: план срезов набора совпадает с пятью срезами карточек на проде.

    Закрепление duration=N1-3 (круг 12) давало (N1-3, AVG_NGT/AVG_TRP) вместо опубликованных
    (N_GE1, AVG_NGT/AVG_TRP): 58 из 145 карточек без среза, карантин с 26.09. Измерения — как в API 27.10.2026.
    """
    from app.data.eurostat_deep_expand import resolve_slice_specs

    dims = {
        "freq": ["A"],
        "accommod": ["TOTAL", "TOT_R", "R_HOT", "R_CAMP", "R_APT", "R_OTH", "TOT_NR", "NR_OWN", "NR_RF", "NR_OTH"],
        "duration": ["N_GE1", "N1-3", "N_GE4"],
        "purpose": ["TOTAL", "PER", "PROF"],
        "c_dest": ["EU27_2020_FOR", "NEU27_2020_FOR", "DOM", "FOR", "WORLD"],
        "statinfo": ["TOTAL", "AVG_TRP", "AVG_NGT"],
        "unit": ["EUR"], "geo": ["FR"], "time": ["2025"],
    }
    plan = resolve_slice_specs("tour_dem_exac", dims)
    got = {(s["duration"], s["statinfo"]) for s in plan.specs}
    published = {
        ("N_GE1", "TOTAL"), ("N1-3", "TOTAL"), ("N_GE4", "TOTAL"),
        ("N_GE1", "AVG_NGT"), ("N_GE1", "AVG_TRP"),
    }
    assert got == published
    assert {s["c_dest"] for s in plan.specs} == {"DOM"}
