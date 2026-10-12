"""Парсер топлива читает сохранённые образцы реальных файлов Росстата.

12.10.2026 проверено вручную: живой `nedel_sred_cen.xlsx` и бюллетень
«О потребительских ценах на нефтепродукты» (156_07-10-2026) разбираются
текущим парсером; нулевой результат 09.10 был сетевым сбоем, не сменой вёрстки.
Образцы сжаты до нужных строк, структура листа и таблицы сохранена.
"""
from datetime import date
from pathlib import Path

from app.services.rosstat_weekly_price_parser import (
    _BULLETIN_HREF_RE,
    _FUEL_BULLETIN_TITLE_RE,
    _parse_fuel_bulletin_html,
    parse_weekly_price_xlsx,
)

FIX = Path(__file__).parent / "fixtures" / "rosstat_fuel"


def test_real_xlsx_sample_gives_weekly_prices_for_all_three_fuels():
    content = (FIX / "nedel_sred_cen_2026_fuel_trimmed.xlsx").read_bytes()
    for label in (
        "Бензин автомобильный марки АИ-92, л",
        "Бензин автомобильный марки АИ-95, л",
        "Дизельное топливо, л",
    ):
        points = parse_weekly_price_xlsx(content, label)
        assert len(points) >= 38, label  # с 12 января по конец сентября
        assert points[0].date == date(2026, 1, 12)
        assert all(40 < p.value < 120 for p in points)
        assert [p.date for p in points] == sorted({p.date for p in points})
    ai92 = {p.date: p.value for p in parse_weekly_price_xlsx(content, "Бензин автомобильный марки АИ-92, л")}
    assert ai92[date(2026, 9, 28)] == 74.51


def test_real_bulletin_sample_gives_last_two_registration_dates():
    html = (FIX / "bulletin_156_2026-10-07_trimmed.html").read_text(encoding="utf-8")
    assert _parse_fuel_bulletin_html(html, "аи-92")[-1].date == date(2026, 10, 5)
    out = {p.date: p.value for p in _parse_fuel_bulletin_html(html, "аи-92")}
    assert out == {date(2026, 9, 28): 74.51, date(2026, 10, 5): 74.72}
    diesel = {p.date: p.value for p in _parse_fuel_bulletin_html(html, "дизельное топливо")}
    assert diesel == {date(2026, 9, 28): 86.77, date(2026, 10, 5): 86.72}


def test_central_news_link_pattern_matches_real_markup():
    html = (
        '<a class="x" href="/storage/mediabank/156_07-10-2026.html" title="">'
        "О потребительских ценах на нефтепродукты с 29 сентября по 5 октября 2026 года</a>"
    )
    found = [(h, t) for h, t in _BULLETIN_HREF_RE.findall(html) if _FUEL_BULLETIN_TITLE_RE.search(t)]
    assert found and found[0][0].endswith("156_07-10-2026.html")
