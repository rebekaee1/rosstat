"""Описание годовой страницы ряда отвечает на запросы про максимум/минимум/конец года."""
from app.services import seo_year_ui as ui
from app.services.seo_renderer import _year_page_title_desc


def test_ru_note_has_low_high_and_year_end():
    note = ui.year_range_note([21.0, 21.0, 19.0, 16.0], "%", en=False)
    assert note == " Минимум — 16 %, максимум — 21 %, последнее за год — 16 %."


def test_partial_year_says_latest_value():
    note = ui.year_range_note([1.5, 2.5, 2.0], "%", en=False, last_is_partial=True)
    assert "последнее значение — 2 %" in note


def test_en_note():
    note = ui.year_range_note([21.0, 19.0, 16.0], "%", en=True)
    assert note == " Low 16 %, high 21 %, last of the year 16 %."


def test_flat_or_short_series_get_no_note():
    assert ui.year_range_note([5.0, 5.0, 5.0], "%", en=False) == ""
    assert ui.year_range_note([5.0, 6.0], "%", en=False) == ""


def test_multi_observation_description_keeps_source_last():
    note = ui.year_range_note([21.0, 19.0, 16.0], "%", en=False)
    _t, desc = _year_page_title_desc(
        name="Ключевая ставка ЦБ РФ", year=2025, frequency="daily", n_rows=254, current_year=False,
        period_note="", summary_label="Среднее за год", summary_text="19,13 %", source="Банк России",
        range_note=note,
    )
    assert "Минимум — 16 %, максимум — 21 %" in desc
    assert desc.endswith("Официальные данные — Банк России.")
    # Без заметки текст прежний.
    _t, old = _year_page_title_desc(
        name="Ключевая ставка ЦБ РФ", year=2025, frequency="daily", n_rows=254, current_year=False,
        period_note="", summary_label="Среднее за год", summary_text="19,13 %", source="Банк России",
    )
    assert old == "Ключевая ставка ЦБ РФ в 2025 году: 254 значений, среднее за год — 19,13 %. Официальные данные — Банк России."
