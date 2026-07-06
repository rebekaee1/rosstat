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
    # Дефляция — с минусом
    assert display_value_text("cpi", 99.83, "%", "monthly") == "-0,17 % за месяц"


def test_value_text_for_level_series():
    assert display_value_text("gdp-nominal", 17624.3, "млрд руб.", "quarterly") == (
        "17\u202f624,30 млрд руб."
    )
    assert display_value_text("cpi", None, "%") == "нет данных"


def test_ru_number_format():
    assert format_number_ru(15.35) == "15,35"
    assert format_number_ru(1234567.8) == "1\u202f234\u202f567,80"
    assert format_number_ru(5) == "5"
    assert format_number_ru(None) == "нет данных"


def test_ru_dates():
    assert format_date_ru(date(2026, 5, 1)) == "1 мая 2026"
    assert format_date_ru(None) == "нет данных"
    assert format_month_ru(date(2026, 5, 1)) == "май 2026"


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
