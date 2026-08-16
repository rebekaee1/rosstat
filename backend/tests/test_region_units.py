"""Нормализация региональных единиц: чистые кейсы без загрузки gzip-артефакта."""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "regional"
sys.path.insert(0, str(_SCRIPTS))

from unit_normalize import normalize_unit, unit_defect  # noqa: E402


@pytest.mark.parametrize(
    "code,unit,note,exp_unit,exp_note_substr",
    [
        (
            "predostavlenie-grazhdanam-zhilyh-pomescheniy-chislo-semey-sostoyavshih",
            "тысяч",
            "на конец года; тысяч",
            "тысяч семей",
            "на конец года",
        ),
        (
            "chislo-organizatsiy",
            "на конец года",
            "на конец года",
            "единиц",
            "на конец года",
        ),
        (
            "chislennost-nezanyatyh-grazhdan-sostoyaschih-na-uchete-v",
            "на конец года, тысяч человек",
            "на конец года, тысяч человек",
            "тысяч человек",
            "на конец года",
        ),
        (
            "posevnye-ploschadi-selskohozyaystvennyh-kultur",
            "тысяча гектаров",
            "в хозяйствах всех категорий; тысяча гектаров",
            "тысяч гектаров",
            "в хозяйствах всех категорий",
        ),
        (
            "udelnyy-ves-gorodskogo-naseleniya-v-obschey-chislennosti",
            "в процентах",
            "оценка на конец года; в процентах",
            "%",
            "оценка на конец года",
        ),
        (
            "izmenenie-srednegodovoy-chislennosti-zanyatyh",
            "в процентах к предыдущему году",
            "в процентах к предыдущему году",
            "% к предыдущему году",
            "",
        ),
        (
            "stoimost-uslovnogo-minimalnogo-nabora-produktov-pitaniya-izmenenie",
            "к декабрю предыдущего года, в процентах",
            "на конец года; к декабрю предыдущего года, в процентах",
            "% к декабрю предыдущего года",
            "на конец года",
        ),
        ("x", "гектар", "гектар", "гектаров", ""),
        ("x", "килограмм", "килограмм", "килограммов", ""),
        ("x", "тысяч га", "на конец года; тысяч га", "тысяч гектаров", "на конец года"),
        ("x", "млн руб.", "", "миллионов рублей", ""),
    ],
)
def test_normalize_unit_cases(code, unit, note, exp_unit, exp_note_substr):
    new_u, new_n = normalize_unit(code, unit, note)
    assert new_u == exp_unit
    assert unit_defect(new_u) is None
    if exp_note_substr:
        assert exp_note_substr in new_n
    else:
        assert new_n == ""


@pytest.mark.parametrize(
    "unit,defect",
    [
        ("тысяч", "bare_thousands"),
        ("на конец года", "timing_in_unit"),
        ("на конец года, тысяч человек", "timing_in_unit"),
        ("тысяча гектаров", "singular_thousand_ha"),
        ("в процентах", "v_procentakh"),
        ("в процентах к предыдущему году", "v_procentakh_prefix"),
        ("к декабрю предыдущего года, в процентах", "k_dekabryu_pct"),
        ("тысяч га", "thousand_ga_abbrev"),
        ("гектар", "singular_ha_kg"),
        ("млн руб.", "mln_rub_abbrev"),
        ("%", None),
        ("тысяч семей", None),
        ("тысяч гектаров", None),
        ("единиц", None),
    ],
)
def test_unit_defect_detector(unit, defect):
    assert unit_defect(unit) == defect


@pytest.mark.parametrize(
    "unit,note,exp_note",
    [
        (
            "тысяч человек",
            "на конец года; тысяч человек. История до 2000 года дособрана "
            "из архивной редакции сборника (издание 2003 года).",
            "на конец года. История до 2000 года дособрана "
            "из архивной редакции сборника (издание 2003 года).",
        ),
        (
            "килограммов",
            "в год; килограммов. История до 2000 года дособрана "
            "из архивной редакции сборника (издание 2003 года).",
            "в год. История до 2000 года дособрана "
            "из архивной редакции сборника (издание 2003 года).",
        ),
    ],
)
def test_note_keeps_history_and_drops_unit_echo(unit, note, exp_note):
    """Эхо единицы склеено с примечанием об истории точкой, а не «;»."""
    _, new_note = normalize_unit("x", unit, note)
    assert new_note == exp_note


def test_note_fixes_country_case():
    """«Российской федерации» из источника — орфографическая ошибка в витрине."""
    _, note = normalize_unit(
        "x", "% организаций", "в процентах от общего числа обследованных "
        "организаций соответствующего субъекта Российской федерации",
    )
    assert "Российской Федерации" in note
    assert "Российской федерации" not in note
