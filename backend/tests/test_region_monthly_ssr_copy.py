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


def _render_weekly(locale):
    """Карточка «дизельное топливо × Санкт-Петербург» с недельным слоем (ЕМИСС 37426, 18.11.2026)."""
    from datetime import date

    from app.models import RegionWeeklyPoint
    from app.services.seo_regional import render_region_indicator_html

    async def scenario(maker):
        async with maker() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            spb = Region(slug="sankt-peterburg", name="г. Санкт-Петербург", kind="region")
            ind = RegionIndicator(code="ceni-dt", table_code="16.22", section_num=16, section_name="Транспорт",
                                  name="Потребительские цены на дизельное топливо, рублей за литр",
                                  unit="рубль за литр")
            db.add_all([rf, spb, ind])
            await db.flush()
            db.add_all([RegionMonthlyPoint(indicator_id=ind.id, region_id=r.id, month=m, value=v)
                        for r in (rf, spb) for m, v in ((202512, 75.9), (202601, 77.3))])
            weeks = ((date(2025, 12, 22), 75.83, 75.80), (date(2026, 1, 12), 77.21, 76.90))
            db.add_all([RegionWeeklyPoint(indicator_id=ind.id, region_id=spb.id, date=d, value=v) for d, v, _ in weeks])
            db.add_all([RegionWeeklyPoint(indicator_id=ind.id, region_id=rf.id, date=d, value=r) for d, _, r in weeks])
            await db.commit()
            token = set_locale(locale)
            try:
                return await render_region_indicator_html("sankt-peterburg", "ceni-dt", db)
            finally:
                reset_locale(token)

    return _run_with_db(scenario)


def test_weekly_layer_answers_price_on_date_ru():
    status, html = _render_weekly("ru")
    assert status == 200
    title = re.search(r"<title>([^<]+)</title>", html).group(1)
    assert "Дизельное топливо — г. Санкт-Петербург: 77,21 руб./л на 12 января 2026" in title
    assert "Литр дизельного топлива в регионе г. Санкт-Петербург на 12 января 2026 стоил в среднем 77,21 руб./л" in html
    assert "В среднем по России в тот же день — 76,90 руб./л." in html
    # «ДТ в СПб на 01.01.2026» — ответ в FAQ: последняя запись до 1 января, с копейками.
    assert "На начало 2026 года (регистрация 22 декабря 2025) — 75,83 руб./л" in html
    assert 'id="weekly"' in html and "<td>22 декабря 2025</td><td>75,83</td><td>75,80</td>" in html
    assert "Роснефть" in html  # честно: цен отдельных сетей нет


def test_weekly_layer_en_has_no_russian_text():
    status, html = _render_weekly("en")
    assert status == 200
    body = html.split("<body", 1)[-1]
    assert "Diesel fuel — " in html and "77.21 RUB/l on 12 January 2026" in html
    for russian in ("недел", "Росстат", "регистрац", "руб."):
        assert russian not in body


def test_federal_fuel_page_lists_regions_on_last_record_of_year():
    """Федеральная страница топлива ведёт в регионы: цена всех субъектов на последнюю запись года."""
    from datetime import date

    from app.models import RegionWeeklyPoint
    from app.services.regional_weekly import fuel_regions_section

    async def scenario(maker):
        async with maker() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            spb = Region(slug="sankt-peterburg", name="г. Санкт-Петербург", kind="region")
            cfo = Region(slug="cfo", name="Центральный федеральный округ", kind="district")
            ind = RegionIndicator(code="ceni-dt", table_code="16.22", section_num=16, section_name="Транспорт",
                                  name="Потребительские цены на дизельное топливо", unit="рубль за литр")
            db.add_all([rf, spb, cfo, ind])
            await db.flush()
            for d, v in ((date(2025, 12, 22), 75.83), (date(2026, 1, 12), 77.21)):
                db.add_all([RegionWeeklyPoint(indicator_id=ind.id, region_id=r.id, date=d, value=v)
                            for r in (rf, spb, cfo)])
            await db.commit()
            token = set_locale("ru")
            try:
                return (await fuel_regions_section(db, "fuel-diesel", year=2025),
                        await fuel_regions_section(db, "fuel-diesel"),
                        await fuel_regions_section(db, "cpi"))
            finally:
                reset_locale(token)

    year_html, latest_html, other = _run_with_db(scenario)
    assert "Цена дизельного топлива по регионам на 22 декабря 2025" in year_html
    assert '<a href="/russia/region/sankt-peterburg/ceni-dt">г. Санкт-Петербург</a></td><td>75,83</td>' in year_html
    assert "Центральный федеральный округ" not in year_html  # только субъекты
    assert "на 12 января 2026" in latest_html and other == ""
