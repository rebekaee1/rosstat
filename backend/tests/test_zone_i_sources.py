"""Новые источники 19.11.2026: недельные цены на продукты (Росстат), ФНБ и госдолг (Минфин), МСП по регионам (ФНС).

Фикстуры — живые ответы 19.11.2026: `fixtures/rosstat_weekly_goods/nedel_sred_cen_2026-11-19.xlsx` (получен
через ETL-сессию прода: с Mac Росстат не открывался), снимки Минфина `app/data/minfin/*` (они же упакованный
резерв парсера), `fixtures/fns_msp/*` (сводка ФНС на 10.11.2025, урезана до округов и пяти субъектов).
"""

import asyncio
import json
from datetime import date
from pathlib import Path

import pytest

from app.data import fns_msp, minfin_debt, rosstat_weekly_goods as goods
from app.services import fns_msp_regional as msp
from app.services import minfin_debt_parser as debt
from app.services.rosstat_weekly_price_parser import parse_weekly_price_xlsx

FIX = Path(__file__).parent / "fixtures"
MINFIN = Path(debt.SNAPSHOT_DIR)


# ── недельные цены ────────────────────────────────────────────────────────────

def test_every_weekly_good_has_its_exact_row_and_last_week():
    content = (FIX / "rosstat_weekly_goods" / "nedel_sred_cen_2026-11-19.xlsx").read_bytes()
    expected_last = {"price-eggs": 111.46, "price-sugar": 80.78, "price-buckwheat": 93.87, "fuel-ai98": 103.97,
                     "price-potatoes": 50.27, "price-butter": 1110.74}
    for good in goods.GOODS:
        points = parse_weekly_price_xlsx(content, good.label)
        assert points, good.code
        # Сыр — с 2023 года: в 2022 строка была другой («Сыры сычужные твердые и мягкие»), ряды не склеиваем.
        assert points[0].date.year == (2023 if good.code == "price-cheese" else 2022), good.code
        assert points[-1].date == date(2026, 11, 9), good.code
        assert 0.5 < points[-1].value < good.max_value, good.code
        if good.code in expected_last:
            assert points[-1].value == expected_last[good.code]


def test_weekly_goods_are_seeded_with_english_copy_and_seo():
    import seed_data
    from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
    from app.data.indicator_seo import INDICATOR_SEO, INDICATOR_SEO_KEYWORDS

    seeded = {row["code"]: row for row in seed_data.INDICATORS}
    for good in goods.GOODS:
        row = seeded[good.code]
        assert row["parser_type"] == "rosstat_weekly_price" and row["frequency"] == "weekly"
        assert row["model_config_json"]["product_label"] == good.label
        assert INDICATOR_COPY_EN[good.code]["name"] == good.name_en
        assert good.code in INDICATOR_SEO and good.code in INDICATOR_SEO_KEYWORDS
    assert len(seeded) == len(seed_data.INDICATORS)


def test_weekly_xlsx_downloaded_once_for_all_goods(monkeypatch):
    from app.services import rosstat_weekly_price_parser as mod

    content = (FIX / "rosstat_weekly_goods" / "nedel_sred_cen_2026-11-19.xlsx").read_bytes()
    calls = []

    class Resp:
        def __init__(self, body):
            self.content, self.status_code = body, 200

        def raise_for_status(self):
            return None

    class Session:
        verify = True

        def get(self, url, **kw):
            calls.append(url)
            return Resp(content)

        def close(self):
            return None

    monkeypatch.setattr(mod, "create_session", Session)
    monkeypatch.setattr(mod, "_xlsx_cache", None)
    for good in goods.GOODS[:3]:
        points, _ = mod.fetch_weekly_price(good.label)
        assert points
    assert calls == [mod.WEEKLY_SRED_CEN_URL]


# ── Минфин: ФНБ и госдолг ─────────────────────────────────────────────────────

def _snap(source: str) -> bytes:
    return (MINFIN / minfin_debt.SOURCES[source].snapshot).read_bytes()


def test_nwf_values_on_first_day_of_next_month():
    total = debt.parse_series("nwf-volume", _snap("nwf"))
    by = {p.date: p.value for p in total}
    assert total[0].date == date(2008, 2, 1) and by[date(2008, 2, 1)] == 783.31   # конец января 2008
    assert by[date(2026, 11, 1)] == 13055.34                                     # «на 1 ноября 2026»
    assert by[date(2020, 5, 1)] == 12405.77                                      # ячейка «12 405,77³» со сноской
    assert len(total) == 226
    liquid = {p.date: p.value for p in debt.parse_series("nwf-liquid", _snap("nwf"))}
    assert liquid[date(2026, 11, 1)] == pytest.approx(13055.34 - 9476.86, abs=0.01)
    gdp = {p.date: p.value for p in debt.parse_series("nwf-gdp", _snap("nwf"))}
    assert gdp[date(2026, 11, 1)] == pytest.approx(5.6)
    usd = {p.date: p.value for p in debt.parse_series("nwf-volume-usd", _snap("nwf"))}
    assert usd[date(2026, 11, 1)] == 162.06


def test_domestic_debt_reads_every_year_sheet_including_large_values():
    points = debt.parse_series("gov-debt-domestic", _snap("domestic"))
    by = {p.date: p.value for p in points}
    assert points[0].date == date(2009, 1, 1) and by[date(2009, 1, 1)] == 1499.824
    # С 2023 года суммы (20–37 тыс. млрд) похожи на числа дат Excel — шапкой их считать нельзя.
    assert by[date(2025, 1, 1)] == 23742.293 and by[date(2026, 11, 1)] == 36919.143
    assert len(points) == 215


def test_external_debt_in_billions_of_dollars():
    by = {p.date: p.value for p in debt.parse_series("gov-debt-external", _snap("external"))}
    assert by[date(2011, 1, 1)] == 39.957 and by[date(2026, 1, 1)] == 57.271
    assert max(by) == date(2026, 11, 1)


def test_latest_link_takes_newest_upload():
    html = ('<a href="/common/upload/library/2026/10/main/Dannye_20261001.xlsx">x</a>'
            '<a href="/common/upload/library/2026/11/main/Dannye_20261101.xlsx">y</a>')
    assert debt.latest_link(html, minfin_debt.SOURCES["nwf"]).endswith("2026/11/main/Dannye_20261101.xlsx")
    assert debt.latest_link("<html></html>", minfin_debt.SOURCES["external"]) is None


def test_blocked_minfin_falls_back_to_snapshot_once_per_source(monkeypatch):
    calls = []

    def blocked(source):
        calls.append(source.key)
        raise ConnectionError("503 Service Temporarily Unavailable")

    monkeypatch.setattr(debt, "_download", blocked)
    debt.clear_cache()
    try:
        content, url, error = debt.fetch_source("nwf")
        again = debt.fetch_source("nwf")
    finally:
        debt.clear_cache()
    assert url == "artifact://nwf.xlsx" and "503" in error and again[1] == url
    assert calls == ["nwf"]                      # второй ряд ФНБ не ждёт снова цепочку прокси
    assert debt.parse_series("nwf-volume", content)


def test_parser_run_marks_fallback(monkeypatch):
    from types import SimpleNamespace

    from app.services.base_parser import fallback_reason

    monkeypatch.setattr(debt, "fetch_source", lambda key: (_snap(key), "artifact://x", "HTTPError: 503"))
    log = SimpleNamespace(error_message=None)
    parser = debt.MinfinDebtParser()
    points, url = asyncio.run(parser._fetch_and_parse(None, SimpleNamespace(code="nwf-gdp"),
                                                      {"minfin_series": "nwf-gdp"}, log))
    assert points and url == "artifact://x"
    assert "snapshot nwf.xlsx" in fallback_reason(log)


def test_minfin_series_seeded_and_registered():
    import seed_data
    from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
    from app.services.rosstat_cpi_parser import PARSER_REGISTRY

    assert PARSER_REGISTRY["minfin_debt_xlsx"] is debt.MinfinDebtParser
    seeded = {row["code"]: row for row in seed_data.INDICATORS}
    for s in minfin_debt.SERIES:
        assert seeded[s.code]["parser_type"] == "minfin_debt_xlsx"
        assert seeded[s.code]["model_config_json"]["minfin_series"] == s.code
        assert INDICATOR_COPY_EN[s.code]["unit"] == s.unit_en


# ── ФНС: МСП по регионам ─────────────────────────────────────────────────────

def _summary():
    return json.loads((FIX / "fns_msp" / "statistics-proc_10.11.2025.json").read_text(encoding="utf-8"))


def test_stat_dates_from_page_select():
    dates = msp.parse_dates((FIX / "fns_msp" / "statDate_select_2026-11-19.html").read_text(encoding="utf-8"))
    assert len(dates) == 124 and dates[0] == "01.08.2016" and dates[-1] == "10.11.2026"
    assert msp.period_of("10.11.2026") == 202611
    assert msp.dates_to_fetch(dates, {msp.period_of(d) for d in dates}) == dates[-2:]
    assert msp.dates_to_fetch(dates, set()) == dates


def test_summary_maps_russia_districts_regions_and_skips_new_subjects():
    points, unknown = msp.parse_summary(_summary(), 202511, msp.territory_slugs())
    by = {(code, slug): v for code, slug, _p, v in points}
    assert unknown == set()
    assert by[("msp-chislo", "russia")] == 6707476
    assert by[("msp-srednie", "russia")] == 21569 + 632
    assert by[("msp-mikro", "russia")] == 1956010 + 4494974
    assert by[("msp-rabotniki", "russia")] == 15178797
    assert ("msp-chislo", "moskva") in by and ("msp-chislo", "hanty-mansiyskiy-ao") in by
    assert ("msp-chislo", "respublika-severnaya-osetiya") in by and ("msp-chislo", "cfo") in by
    assert not any("donec" in slug for _c, slug in by)


def test_summary_without_russia_is_format_error():
    with pytest.raises(msp.FnsMspFormatError):
        msp.parse_summary([r for r in _summary() if r["cnt_level"] != 2], 202511, msp.territory_slugs())


def test_regional_rows_and_english_copy_cover_registry():
    from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN

    rows = json.loads((Path(fns_msp.__file__).parent / "regional" / "indicators.json").read_text(encoding="utf-8"))
    by_code = {r["code"]: r for r in rows}
    for s in fns_msp.SERIES:
        assert by_code[s.code]["frequency"] == "monthly" and by_code[s.code]["section_num"] == 11
        assert REGION_INDICATORS_EN[s.code]["name"] == s.name_en
    assert len({r["table_code"] for r in rows if r["section_num"] == 11}) == sum(
        1 for r in rows if r["section_num"] == 11)


def test_run_update_first_load_then_only_new_and_last(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models import Base, Region, RegionIndicator, RegionMonthlyPoint

    db_path = tmp_path / "msp.db"
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    asked: list[str] = []
    written: list[tuple] = []
    page = '<option value="10.09.2026">a</option><option value="10.10.2026">b</option><option value="10.11.2026">c'
    summary = _summary()

    def fake_summary(stat_date):
        asked.append(stat_date)
        return summary

    async def fake_upsert(db, values):
        fresh = [v for v in values if v not in written]
        written.extend(fresh)
        db.add_all(RegionMonthlyPoint(indicator_id=i, region_id=r, month=m, value=v) for i, r, m, v in fresh)
        await db.flush()
        return len(fresh), 0

    async def no_publish():
        return None

    monkeypatch.setattr(msp, "_upsert_monthly_points", fake_upsert)
    monkeypatch.setattr(msp, "publish_committed_regional_changes", no_publish)

    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as db:
                db.add_all([Region(slug="russia", name="Российская Федерация", kind="country"),
                            Region(slug="moskva", name="г. Москва", kind="region")])
                for s in fns_msp.SERIES:
                    db.add(RegionIndicator(code=s.code, table_code=s.table_code, section_num=11,
                                           section_name="Организации", name=s.name, unit=s.unit))
                await db.commit()
                first = await msp.run_fns_msp_update(db, fetch_page=lambda: page, fetch_summary=fake_summary,
                                                     pause_s=0)
                asked.clear()
                second = await msp.run_fns_msp_update(db, fetch_page=lambda: page, fetch_summary=fake_summary,
                                                      pause_s=0)
                return first, second
        finally:
            await engine.dispose()

    first, second = asyncio.run(scenario())
    assert first["dates"] == 3 and first["added"] == 3 * 2 * 7       # 3 сводки × (Россия, Москва) × 7 рядов
    assert asked == ["10.10.2026", "10.11.2026"]                     # потом — только две последние
    assert {w[2] for w in written} == {202609, 202610, 202611}


@pytest.mark.parametrize("query,needle", [
    ("средний бизнес", "средних предприятий"),
    ("количество ип белгородская область", "индивидуальные предприниматели"),
    ("занятых на малых предприятиях", "работники малого"),
    ("малый бизнес", "малого и среднего бизнеса"),
])
def test_search_reaches_msp_series(query, needle):
    from app.services.search_intent import normalize, parse_intent

    geometry = [dict(key="country:russia", kind="country", slug="russia", country_slug="russia", country_code="RU",
                     name_ru="Россия", name_en="Russia"),
                dict(key="region:russia:belgorodskaya-oblast", kind="region", slug="belgorodskaya-oblast",
                     country_slug="russia", name_ru="Белгородская область", name_en="Belgorod Oblast")]
    intent = parse_intent(query, geometry)
    assert any(needle in group for group in intent.terms), intent.terms
    assert any(needle in normalize(s.name) for s in fns_msp.SERIES)


@pytest.mark.parametrize("locale,banned,expected", [
    ("ru", ("потребительские цены", "ЕМИСС", "Какая цена"), "реестр МСП ФНС"),
    ("en", ("consumer price", "EMISS", "Rosstat"), "Federal Tax Service"),
])
def test_ssr_card_of_msp_series_names_tax_service(locale, banned, expected):
    from app.models import Region, RegionIndicator, RegionMonthlyPoint
    from app.services.locale import reset_locale, set_locale
    from app.services.seo_regional import _render_region_indicator_monthly
    from tests.test_analytics2 import _run_with_db

    series = fns_msp.SERIES_BY_CODE["msp-chislo"]

    async def scenario(maker):
        async with maker() as db:
            rf = Region(slug="russia", name="Российская Федерация", kind="country")
            ind = RegionIndicator(code=series.code, table_code=series.table_code, section_num=11,
                                  section_name="Организации", name=series.name, unit=series.unit)
            db.add_all([rf, ind])
            await db.flush()
            values = {202511: 6707476.0, 202610: 6880000.0, 202611: 6895487.0}
            db.add_all([RegionMonthlyPoint(indicator_id=ind.id, region_id=rf.id, month=m, value=v)
                        for m, v in values.items()])
            await db.commit()
            token = set_locale(locale)
            try:
                return await _render_region_indicator_monthly("russia", ind.code, rf, ind, sorted(values.items()), db)
            finally:
                reset_locale(token)

    status, html = _run_with_db(scenario)
    assert status == 200
    body = html.split("<body", 1)[-1]
    for phrase in banned:
        assert phrase not in body, phrase
    assert expected in body


@pytest.mark.parametrize("query,code", [
    ("цена яиц", "price-eggs"),
    ("цены на гречку", "price-buckwheat"),
    ("аи-98", "fuel-ai98"),
    ("бензин 98", "fuel-ai98"),
    ("фнб", "nwf-volume"),
    ("фонд национального благосостояния", "nwf-volume"),
    ("ликвидные активы фнб", "nwf-liquid"),
    ("госдолг россии", "gov-debt-domestic"),
    ("внешний государственный долг россии график", "gov-debt-external"),
])
def test_search_terms_reach_federal_series_by_name_or_keywords(query, code):
    """Поиск сопоставляет каждую группу терминов с кодом, названием или seo_keywords (search.py)."""
    import seed_data
    from app.data.indicator_seo import INDICATOR_SEO_KEYWORDS
    from app.services.search_intent import parse_intent

    row = next(r for r in seed_data.INDICATORS if r["code"] == code)
    haystack = " ".join((code, row["name"], row["name_en"], INDICATOR_SEO_KEYWORDS[code])).lower()
    for group in parse_intent(query, []).terms:
        if group == ("график",):
            continue                                 # слово формы ответа, не предмета
        assert any(term.lower() in haystack for term in group), (query, group)
