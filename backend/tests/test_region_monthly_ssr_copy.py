"""Месячная карточка цен региона: падежи месяца и английская страница (рассылка 14.11.2026, «в сентября 2026»)."""
import re

import pytest

from app.models import Region, RegionIndicator, RegionMonthlyPoint
from app.services.locale import reset_locale, set_locale
from app.services.seo_regional import _fmt, _month_label, _render_region_indicator_monthly
from tests.test_analytics2 import _run_with_db


def _with_locale(locale, fn):
    token = set_locale(locale)
    try:
        return fn()
    finally:
        reset_locale(token)


def test_month_label_cases_ru_and_en():
    assert _with_locale("ru", lambda: _month_label(202609, "prep")) == "сентябре 2026"
    assert _with_locale("ru", lambda: _month_label(202509, "dat")) == "сентябрю 2025"
    assert _with_locale("ru", lambda: _month_label(202001, "gen")) == "января 2020"
    assert _with_locale("ru", lambda: _month_label(202609)) == "сентябрь 2026"
    assert _with_locale("en", lambda: _month_label(202609, "prep")) == "September 2026"
    assert _with_locale("en", lambda: _fmt(101.39)) == "101.4"
    assert _with_locale("en", lambda: _fmt(146980.061)) == "146,980"


def _render(locale):
    async def scenario(maker):
        async with maker() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            ind = RegionIndicator(code="ceni-test-yaytsa", table_code="p", section_num=99, section_name="Цены",
                                  name="Средняя цена: яйца куриные", unit="рублей за 10 штук")
            db.add_all([rf, ind])
            await db.flush()
            values = {202509: 85.7, 202608: 100.0, 202609: 101.39}
            db.add_all([RegionMonthlyPoint(indicator_id=ind.id, region_id=rf.id, month=m, value=v)
                        for m, v in values.items()])
            await db.commit()
            rows = sorted(values.items())
            token = set_locale(locale)
            try:
                return await _render_region_indicator_monthly("russia", ind.code, rf, ind, rows, db)
            finally:
                reset_locale(token)

    return _run_with_db(scenario)


def test_ru_card_uses_prepositional_and_dative():
    status, html = _render("ru")
    assert status == 200
    assert "в сентября" not in html and "В сентября" not in html
    desc = re.search(r'<meta name="description" content="([^"]+)"', html).group(1)
    assert "в сентябре 2026" in desc
    assert "К сентябрю 2025 —" in html
    assert "С августа 2026 по сентябрь 2026 показатель" in html  # месячное изменение — от прошлого месяца
    assert "заправки" in html and "на топливо" not in html


@pytest.mark.parametrize("russian", ["в регионе", "в сентября", "Динамика", "Росстата", "Вопросы"])
def test_en_card_has_no_russian_template_text(russian):
    status, html = _render("en")
    assert status == 200
    body = html.split("<body", 1)[-1]
    assert russian not in body
    desc = re.search(r'<meta name="description" content="([^"]+)"', html).group(1)
    assert "in September 2026" in desc and "101.4" in desc
