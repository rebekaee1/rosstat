"""Display-adapter (В-22): storage-значение → пользовательское представление.

Класс инцидента «Инфляция — 100,2%»: CPI-семейство хранит индекс ~100.xx,
наружу (SSR, OG, RSS, embed) обязано уходить изменение цен в %, русские числа
и даты. Плюс синхронность списка CPI-кодов с frontend/src/lib/format.js.
"""
import re
from datetime import date
from pathlib import Path

from app.services.display import (
    CPI_INDEX_CODES,
    annual_summary,
    annual_summary_kind,
    display_value,
    display_value_text,
    format_date_ru,
    format_month_ru,
    format_number_ru,
)


def test_cpi_index_shown_as_change():
    assert display_value("cpi", 100.17) == 0.17
    assert display_value("cpi", 99.4) == -0.6
    assert display_value("inflation-weekly", 100.07) == 0.07


def test_non_cpi_passes_through():
    assert display_value("gdp-nominal", 17624.3) == 17624.3
    assert display_value("key-rate", 16.0) == 16.0
    assert display_value(None, 5.0) == 5.0


def test_value_text_for_cpi_has_sign_and_period():
    assert display_value_text("cpi", 100.17, "%", "monthly") == "+0,17 % за месяц"
    assert display_value_text("inflation-weekly", 100.07, "%", "weekly") == "+0,07 % за неделю"
    # Дефляция — с типографским минусом (U+2212), как во всех публичных числах
    assert display_value_text("cpi", 99.83, "%", "monthly") == "\u22120,17 % за месяц"


def test_value_text_for_level_series():
    assert display_value_text("gdp-nominal", 17624.3, "млрд руб.", "quarterly") == (
        "17\u202f624,3 млрд руб."
    )
    assert display_value_text("cpi", None, "%") == "нет данных"


def test_localize_unit_and_value_text_en():
    from app.services.display import localize_unit
    from app.services.locale import reset_locale, set_locale

    assert localize_unit("млрд руб.", locale="en") == "bln RUB"
    assert localize_unit("руб.", locale="en") == "RUB"
    assert localize_unit("млрд руб.", locale="ru") == "млрд руб."
    assert display_value_text(
        "gdp-nominal", 17624.3, "млрд руб.", "quarterly", locale="en"
    ) == "17,624.3 bln RUB"
    assert display_value_text(
        "gdp-nominal", 49869.5, "млрд руб.", "quarterly", locale="en"
    ) == "49,869.5 bln RUB"
    assert display_value_text("cpi", 100.17, "%", "monthly", locale="en") == (
        "+0.17 % over the month"
    )
    token = set_locale("en")
    try:
        assert display_value_text("cpi", None, "%") == "no data"
        # Economist English: period decimal, comma thousands.
        assert display_value_text("key-rate", 16.5, "%") == "16.5 %"
        assert "," not in display_value_text("key-rate", 16.5, "%")
        assert format_number_ru(49869.5) == "49,869.5"
    finally:
        reset_locale(token)


def test_localize_category_name_en():
    from app.services.seo_i18n import localize_category_name

    assert localize_category_name("Цены", locale="en") == "Prices and inflation"
    assert localize_category_name("Рынок труда", locale="en") == "Labor market"
    assert localize_category_name("Прочее", locale="en") == "Other"
    assert localize_category_name("Общество", locale="en") == "Society"
    assert localize_category_name("Цены", locale="ru") == "Цены"


def test_event_public_title_en():
    from app.services.seo_i18n import event_public_title

    assert event_public_title("ИПЦ", "Consumer Price Index", locale="en") == (
        "Consumer Price Index"
    )
    assert event_public_title("ИПЦ", None, locale="en") == "ИПЦ"
    assert event_public_title("ИПЦ", "CPI", locale="ru") == "ИПЦ"


def test_ru_number_format():
    assert format_number_ru(15.35, locale="ru") == "15,35"
    # Хвостовой ноль — ложная точность: источник даёт один знак, показываем один.
    assert format_number_ru(1234567.8, locale="ru") == "1\u202f234\u202f567,8"
    assert format_number_ru(1234567.85, locale="ru") == "1\u202f234\u202f567,85"
    assert format_number_ru(85_664_944, locale="ru") == "85\u202f664\u202f944"
    assert format_number_ru(5, locale="ru") == "5"
    assert format_number_ru(None, locale="ru") == "нет данных"
    assert format_number_ru(15.35, locale="en") == "15.35"
    assert format_number_ru(1234567.8, locale="en") == "1,234,567.8"
    assert format_number_ru(85_664_944, locale="en") == "85,664,944"
    assert format_number_ru(None, locale="en") == "no data"


def test_ru_dates():
    assert format_date_ru(date(2026, 5, 1)) == "1 мая 2026"
    assert format_date_ru(None) == "нет данных"
    assert format_month_ru(date(2026, 5, 1)) == "май 2026"


def test_format_month_year_locale():
    from app.services.display import format_month_year
    from app.services.locale import reset_locale, set_locale

    d = date(2025, 12, 1)
    assert format_month_year(d, locale="ru") == "декабрь 2025"
    assert format_month_year(d, locale="en") == "December 2025"
    token = set_locale("en")
    try:
        assert format_month_year(d) == "December 2025"
    finally:
        reset_locale(token)


def test_concept_public_name_en():
    from app.data.world_concepts import CONCEPT_BY_SLUG, concept_public_name

    c = CONCEPT_BY_SLUG["unemployment-rate"]
    assert concept_public_name(c, locale="ru") == "Уровень безработицы"
    assert concept_public_name(c, locale="en") == "Unemployment rate"
    assert "Уровень" not in concept_public_name(c, locale="en")


def test_annual_summary_kinds():
    # CPI — цепной рост цен за год
    assert annual_summary_kind("cpi") == "chain"
    label, text = annual_summary("cpi", [100.5, 100.5], "%")
    assert label == "Рост цен за год"
    assert text == "+1 %"  # 1.005 × 1.005 → +1,0025% → «+1 %»
    # Потоки — сумма (T6 flow_sum: budget-revenue в generic-семьях)
    assert annual_summary_kind("budget-revenue") == "sum"
    # Запасы — конец года (T3/T4/T5 stock: international-reserves)
    assert annual_summary_kind("international-reserves") == "last"
    # Ставки/уровни — среднее
    assert annual_summary_kind("key-rate") == "avg"
    # Неизвестный код — консервативное среднее
    assert annual_summary_kind("no-such-code") == "avg"


def test_cpi_codes_in_sync_with_frontend():
    """Список CPI-кодов бэкенда обязан совпадать с format.js (одна семантика)."""
    fmt_js = (
        Path(__file__).resolve().parents[2]
        / "frontend" / "src" / "lib" / "format.js"
    ).read_text(encoding="utf-8")
    m = re.search(r"CPI_INDEX_CODES = new Set\(\[(.*?)\]\)", fmt_js, re.S)
    assert m, "CPI_INDEX_CODES не найден в format.js"
    frontend_codes = set(re.findall(r"'([a-z0-9-]+)'", m.group(1)))
    assert frontend_codes == set(CPI_INDEX_CODES)


def test_bea_units_en_no_cyrillic_via_map_and_prose():
    """P0 SEO: US BEA unit_ru must not leak Cyrillic on the EN host.

    Prefer official Latin ``unit`` prose (chained vs constant 2017 dollars);
    ``unit_ru``-only paths still resolve through ``_UNIT_EN``.
    """
    from app.services.display import contains_cyrillic, localize_unit, public_unit_en

    cases = [
        ("тыс. долл.", "Thousands of dollars", "Thousands of dollars", "thousand USD"),
        (
            "млн долл., текущие цены",
            "Millions of current dollars",
            "Millions of current dollars",
            "million USD, current prices",
        ),
        (
            "млн долл. 2017 г.",
            "Millions of chained 2017 dollars",
            "Millions of chained 2017 dollars",
            "million 2017 USD",
        ),
        (
            "млн долл. 2017 г.",
            "Millions of constant 2017 dollars",
            "Millions of constant 2017 dollars",
            "million 2017 USD",
        ),
        ("млн долл.", "Millions of dollars", "Millions of dollars", "million USD"),
        ("долл. 2017 г.", "Constant 2017 dollars", "Constant 2017 dollars", "2017 USD"),
        ("долл.", "Dollars", "Dollars", "USD"),
        ("рабочих мест", "Number of jobs", "Number of jobs", "jobs"),
        ("отношение", "Ratio", "Ratio", "ratio"),
        ("человек", "Number of persons", "Number of persons", "people"),
        ("индекс", "Quantity index", "Quantity index", "index"),
        ("п. п.", "Percentage points", "Percentage points", "pp"),
        ("%", "Percent change", "Percent change", "%"),
    ]
    for unit_ru, unit_en, expect_prose, expect_map in cases:
        prose = public_unit_en(unit_ru, unit_storage=unit_en)
        mapped = public_unit_en(unit_ru)
        assert prose == expect_prose, (unit_ru, prose)
        assert mapped == expect_map, (unit_ru, mapped)
        assert not contains_cyrillic(prose)
        assert not contains_cyrillic(mapped)
        assert not contains_cyrillic(localize_unit(unit_ru, locale="en"))


def test_public_unit_en_ignores_eurostat_measure_codes():
    """Eurostat ``unit`` codes stay codes — EN comes from unit_ru map / codelist."""
    from app.services.display import is_english_unit_prose, public_unit_en

    assert not is_english_unit_prose("I15")
    assert not is_english_unit_prose("PC_ACT")
    assert not is_english_unit_prose("CLV15_MEUR")
    # Measure code must not override a mapped Russian unit.
    assert public_unit_en("индекс (2015 = 100)", unit_storage="I15") == (
        "index (2015 = 100)"
    )


def test_bea_catalog_unit_ru_all_map_to_latin_en():
    """Every published US BEA catalog unit_ru localizes without Cyrillic."""
    import json
    from pathlib import Path

    from app.services.display import contains_cyrillic, public_unit_en

    catalog = json.loads(
        (Path(__file__).resolve().parents[1] / "app/data/world_bea_regional/us.json")
        .read_text(encoding="utf-8")
    )
    series = catalog["series"]
    assert len(series) >= 1500
    for row in series:
        en = public_unit_en(row["unit_ru"], unit_storage=row["unit"])
        assert en, row["code"]
        assert not contains_cyrillic(en), (row["code"], row["unit_ru"], en)
        assert not contains_cyrillic(public_unit_en(row["unit_ru"])), row["code"]
