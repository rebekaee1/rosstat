"""Туризм по России в целом (20.11.2026): реестр, разбор ЦБ, Росстата (ФСБ, туриндустрия) и ЕМИСС, резервный снимок.

Фикстуры — файлы, скачанные агентами сбора 20.11.2026 (`app/data/tourism_snapshots`: ответы dataGrid ЕМИСС, только
строки России; `Poezdki_10-2026.xlsx`; `VDS_ti_OKVED2_vvp.xlsx`). Контрольные значения сверены с файлами вручную.
"""
import asyncio
import io
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pytest

from app.data import tourism_russia as reg
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN
from app.data.indicator_seo import (
    INDICATOR_HIDDEN_FROM_LISTING, INDICATOR_SEO, INDICATOR_SEO_BLOCKS, INDICATOR_SEO_KEYWORDS,
)
from app.data.view_model_families import FAMILY_BY_BASE
from app.services import emiss_tourism_parser as emiss
from app.services import rosstat_tourism_parser as rt
from app.services.base_parser import fallback_reason
from app.services.cbr_bop_parser import parse_bop_xlsx
from app.services.cbr_trade_services_monthly_parser import parse_trade_services_monthly_xlsx
from app.services.rosstat_cpi_parser import PARSER_REGISTRY

SNAP = Path(reg.__file__).parent / "tourism_snapshots"
FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src"
RF, RF_NEW = emiss.RUSSIA, emiss.RUSSIA_WITHOUT_NEW


def emiss_points(code):
    s = reg.SERIES[code]
    main = emiss.parse_snapshot_or_answer(emiss.load_snapshot(s.cfg["emiss_dataset"]), s.cfg)
    den = (emiss.parse_snapshot_or_answer(emiss.load_snapshot(s.cfg["emiss_ratio_of"]), s.cfg)
           if s.cfg.get("emiss_ratio_of") else None)
    return {p.date: p.value for p in emiss.series_points(main, s.cfg, den)}


# ── Реестр ────────────────────────────────────────────────────────────────────

def test_every_series_reaches_seed_parser_texts_seo_and_listing():
    import seed_data

    seeded = {row["code"]: row for row in seed_data.INDICATORS}
    for code, s in reg.SERIES.items():
        assert code.startswith("tour-")
        row = seeded[code]
        assert row["category"] == "Туризм" and row["parser_type"] in PARSER_REGISTRY
        assert INDICATOR_COPY_EN[code]["name"] == s.name_en and INDICATOR_COPY_EN[code]["unit"] == s.unit_en
        assert INDICATOR_SEO[code]["seo_title"] and INDICATOR_SEO_KEYWORDS[code].startswith(s.name)
        assert len(INDICATOR_SEO_BLOCKS[code]) == 6
        assert (code in INDICATOR_HIDDEN_FROM_LISTING) == (not s.listed)
        for text in (s.description, s.methodology, s.methodology_en, s.description_en):
            assert not re.search(r"ЕМИСС|парсер|parser|API|ADR|dataGrid|fedstat", text), (code, text)
        if s.family:
            assert FAMILY_BY_BASE[code].template == s.family


def test_hidden_series_are_reachable_and_frontend_groups_mirror_registry():
    grouped = {code for _key, _label, members in reg.VARIANT_GROUPS for code, *_ in members}
    for code in reg.hidden_codes():
        cfg = reg.SERIES[code].cfg
        assert code in grouped or cfg.get("primary_indicator_code") in reg.SERIES, code
    variants = (FRONT / "lib" / "indicatorVariants.js").read_text(encoding="utf-8")
    ru = (FRONT / "i18n" / "messages.ru.js").read_text(encoding="utf-8")
    en = (FRONT / "i18n" / "messages.en.js").read_text(encoding="utf-8")
    for key, label, members in reg.VARIANT_GROUPS:
        assert f"'variant.{key}.group'" in ru and f"'variant.{key}.group'" in en
        for code, member_label, _ in members:
            assert f"code: '{code}', label: '{member_label}'" in variants
    # Каждая группа держит хотя бы один ряд витрины: иначе её срезы видны только в поиске.
    for _key, _label, members in reg.VARIANT_GROUPS:
        assert any(reg.SERIES[code].listed for code, *_ in members)


def test_forecasts_only_where_the_series_allows():
    import seed_data

    by_code = {row["code"]: row for row in seed_data.INDICATORS}
    assert reg.forecast_codes("monthly_auto") <= seed_data.MONTHLY_AUTO_FORECAST_CODES
    assert reg.forecast_codes("annual_auto") <= seed_data.ANNUAL_AUTO_FORECAST_CODES
    assert by_code["tour-travel-balance"]["model_config_json"]["forecast_strategy"] == "signed_quarterly"
    # Страны, чартеры, доли и короткие ряды без прогноза.
    for code in ("tour-outbound-turkey", "tour-air-passengers-charter", "tour-gva-share", "tour-hotel-nights-monthly"):
        assert by_code[code]["model_config_json"]["forecast_steps"] == 0


# ── Банк России: «Поездки» ────────────────────────────────────────────────────

def _monthly_book():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "месяцы "
    ws.append([])
    ws.append(["Внешняя торговля Российской Федерации услугами по месяцам"])
    ws.append([None, None, None, "млн долларов США"])
    ws.append([None, "янв.26", "фев.26", "мар.26\n(оценка)"])
    for row in (["Услуги ", -1, -2, -3], ["Экспорт услуг", 10, 11, 12], ["Импорт услуг", 11, 13, 15],
                ["Транспортные услуги", 1, 1, 1], ["Экспорт", 5, 5, 5], ["Импорт ", 4, 4, 4],
                ["Поездки", -2018.47, -1097.13, -3490.65], ["Экспорт", 708.23, 607.05, 843.69],
                ["Импорт ", 2726.7, 1704.18, 4334.34]):
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_monthly_travel_rows_are_found_under_their_article_not_by_repeated_label():
    content = _monthly_book()
    get = lambda target: [(p.date, p.value) for p in parse_trade_services_monthly_xlsx(content, target)]
    assert get("travel-exports-monthly") == [(date(2026, 1, 1), 708.23), (date(2026, 2, 1), 607.05),
                                             (date(2026, 3, 1), 843.69)]
    assert get("travel-imports-monthly")[0] == (date(2026, 1, 1), 2726.7)
    assert get("travel-balance-monthly")[-1] == (date(2026, 3, 1), -3490.65)
    assert get("services-exports-monthly")[0] == (date(2026, 1, 1), 10)


def _bop_book(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Кварталы"
    for _ in range(4):
        ws.append([])
    ws.append([None, "1 квартал 1998 г.", "2 квартал 1998 г.", "1 квартал 1999 г."])
    ws.append(["Счет текущих операций", 1, 1, 1])
    ws.append(["Товары", 1, 1, 1])
    ws.append(["Экспорт", 1, 1, 1])
    ws.append(["Импорт", 1, 1, 1])
    ws.append(["Услуги", 1, 1, 1])
    ws.append(["Экспорт", 1, 1, 1])
    ws.append(["Импорт", 1, 1, 1])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_bop_travel_drops_unpublished_leading_zeros_and_refuses_all_zero_rows():
    content = _bop_book([
        ["Поездки", -805.36, -1219.42, -900], ["Экспорт", 434.8, 659.5, 500], ["Импорт", 1240.16, 1878.92, 1400],
        ["Деловые поездки", 0, 0, -96.12], ["Экспорт", 0, 0, 311.72], ["Импорт", 0, 0, 407.84],
        ["Личные поездки", 0, 0, 0], ["Экспорт", 0, 0, 0], ["Импорт", 0, 0, 0],
    ])
    assert [(p.date, p.value) for p in parse_bop_xlsx(content, "travel-imports")][0] == (date(1998, 3, 1), 1240.16)
    assert [(p.date, p.value) for p in parse_bop_xlsx(content, "travel-business-exports")] == [(date(1999, 3, 1), 311.72)]
    with pytest.raises(ValueError, match="zero over the whole history"):
        parse_bop_xlsx(content, "travel-personal-imports")


# ── Росстат по данным ФСБ ─────────────────────────────────────────────────────

TRIPS = (SNAP / "Poezdki_10-2026.xlsx").read_bytes()


def test_trips_quarters_are_differences_of_year_to_date_totals_from_2015():
    inbound = {p.date: p.value for p in rt.parse_trips(TRIPS, "inbound")}
    assert min(inbound) == date(2015, 3, 1)  # в 2014 году нет I квартала
    assert inbound[date(2025, 3, 1)] == 1581.501
    assert inbound[date(2025, 12, 1)] == pytest.approx(7859.392 - 6315)
    assert max(inbound) == date(2026, 6, 1) and inbound[date(2026, 6, 1)] == pytest.approx(3307.333 - 1437.41)
    outbound = {p.date: p.value for p in rt.parse_trips(TRIPS, "outbound")}
    # «Январь-декабрь*» и год «2022*» со сноской читаются.
    assert sum(v for d, v in outbound.items() if d.year == 2025) == pytest.approx(29754.945)
    assert outbound[date(2022, 12, 1)] == pytest.approx(22486.541 - 17148.585)


def test_trips_by_country_follow_renamed_rows_and_monthly_inbound_is_in_thousands():
    thailand = {p.date: p.value for p in rt.parse_trips(TRIPS, "outbound", country=["Таиланд", "Тайланд"])}
    assert sum(v for d, v in thailand.items() if d.year == 2025) == pytest.approx(1375, abs=1)
    abkhazia = rt.parse_trips(TRIPS, "inbound", country=["Абхазия"])  # в файле «Абхазия » с пробелом
    assert len(abkhazia) == 46
    monthly = {p.date: p.value for p in rt.parse_trips(TRIPS, "inbound", monthly=True)}
    assert min(monthly) == date(2022, 1, 1) and max(monthly) == date(2026, 10, 1)
    assert monthly[date(2026, 10, 1)] == pytest.approx(590.0)
    assert monthly[date(2026, 2, 1)] == pytest.approx(440.0)


# ── Туристская индустрия ──────────────────────────────────────────────────────

GVA = (SNAP / "VDS_ti_OKVED2_vvp.xlsx").read_bytes()


def test_gva_quarters_add_up_to_the_year_and_footnoted_years_are_read():
    quarters = {p.date: p.value for p in rt.parse_gva(GVA, "value_quarterly")}
    assert sum(v for d, v in quarters.items() if d.year == 2017) == pytest.approx(2195.2159, abs=0.01)
    assert date(2025, 12, 1) in quarters and max(quarters) == date(2026, 6, 1)
    share = {p.date: p.value for p in rt.parse_gva(GVA, "share_annual")}
    assert share[date(2025, 1, 1)] == pytest.approx(3.1415, abs=1e-4)  # шапка «20252)»
    assert min(share) == date(2017, 1, 1) and len(share) == 9
    volume = {p.date: p.value for p in rt.parse_gva(GVA, "volume_quarterly")}
    assert volume[date(2020, 6, 1)] == pytest.approx(59.5197, abs=1e-3)


# ── ЕМИСС ─────────────────────────────────────────────────────────────────────

def test_air_totals_sum_scheduled_and_charter_domestic_and_international():
    total = emiss_points("tour-air-passengers")
    parts = [emiss_points(c) for c in ("tour-air-passengers-domestic", "tour-air-passengers-international")]
    day = date(2026, 9, 1)
    assert min(total) == date(2009, 1, 1) and max(total) == day
    assert total[day] == pytest.approx(sum(p[day] for p in parts))
    assert 2000 < total[date(2009, 1, 1)] < 3000 and 8000 < total[day] < 12000
    load = emiss_points("tour-air-load-factor")
    assert all(30 < v < 100 for v in load.values()) and load[date(2020, 4, 1)] < 40  # апрель 2020 — локдаун


def test_hotels_annual_russia_row_and_monthly_nights_from_running_totals():
    guests = emiss_points("tour-hotel-guests")
    assert guests[date(2024, 1, 1)] == pytest.approx(90.06877)  # 90 068 770 человек = цифра на сайте
    assert min(guests) == date(2002, 1, 1)
    nights = emiss_points("tour-hotel-nights-monthly")
    assert nights[date(2023, 1, 1)] == pytest.approx(16.924942)
    assert nights[date(2023, 2, 1)] == pytest.approx(34.42493 - 16.924942)
    assert max(nights) == date(2026, 7, 1)
    assert emiss_points("tour-agencies")[date(2025, 1, 1)] == 17535


def test_emiss_rows_prefer_russia_without_new_regions_from_2023_and_skip_incomplete_sums():
    cfg = {"emiss_dataset": 1, "emiss_period": "monthly", "emiss_match": {}, "emiss_sum_dims": ["37002"]}
    row = lambda terr, kind, y, v: {"dim57831": terr, "dim33560": "январь", "dim37002": kind, f"dim{y}_s": v}
    rows = [row(RF, "Внутренние", 2022, "10"), row(RF, "Международные", 2022, "5"),
            row(RF, "Внутренние", 2023, "10"), row(RF_NEW, "Внутренние", 2023, "9"),
            row(RF, "Международные", 2023, "5"), row(RF_NEW, "Международные", 2023, "4,5"),
            row(RF_NEW, "Внутренние", 2024, "8"), row("Центральный федеральный округ", "Внутренние", 2024, "1")]
    assert emiss.parse_rows(rows, cfg) == {date(2022, 1, 1): 15.0, date(2023, 1, 1): 13.5}
    with pytest.raises(emiss.EmissTourismFormatError, match="не выбран"):
        emiss.parse_rows(rows, {**cfg, "emiss_sum_dims": []})


def test_live_request_selects_only_russia_and_requested_years():
    page = "\n".join([
        "filters: {",
        " " * 28 + "0: {", " " * 32 + "title: 'Показатель',", " " * 36 + "37022: {", " " * 40 + "title: 'x',",
        " " * 28 + "3: {", " " * 32 + "title: 'Год',", " " * 36 + "2025: {", " " * 40 + "title: '2025',",
        " " * 36 + "2026: {", " " * 40 + "title: '2026',",
        " " * 28 + "57831: {", " " * 32 + "title: 'ОКАТО',", " " * 36 + "1: {",
        " " * 40 + f"title: '{RF}',", " " * 36 + "2: {", " " * 40 + "title: 'Центральный федеральный округ',",
        "left_columns",
    ])
    filters = emiss.parse_page_filters(page)
    params = emiss.grid_params(filters, range(2026, 2027))
    selected = {v for k, v in params if k == "selectedFilterIds"}
    assert selected == {"0_37022", "3_2026", "57831_1"}
    assert ("columnObjectIds", "3") in params and ("lineObjectIds", "57831") in params


def _db(latest):
    async def scalar(_query):
        return latest
    return SimpleNamespace(scalar=scalar)


def test_snapshot_only_fills_an_empty_series_and_never_overwrites_history(monkeypatch):
    async def banned(*_a, **_k):
        raise RuntimeError("dataGrid.do?id=37022: RuntimeError: HTTP 403")

    monkeypatch.setattr(emiss, "fetch_dataset", banned)
    parser = emiss.EmissTourismParser()
    indicator = SimpleNamespace(id=1, code="tour-air-passengers")
    cfg = reg.SERIES["tour-air-passengers"].cfg
    log = SimpleNamespace()
    points, url = asyncio.run(parser._fetch_and_parse(_db(None), indicator, cfg, log))
    assert len(points) == 213 and "403" in fallback_reason(log) and url.endswith("/37022")
    with pytest.raises(RuntimeError, match="403"):
        asyncio.run(parser._fetch_and_parse(_db(date(2026, 9, 1)), indicator, cfg, SimpleNamespace()))


def test_rosstat_file_snapshot_only_for_an_empty_series(monkeypatch):
    def unreachable(*_a):
        raise rt.RosstatUnreachable("rosstat down") if hasattr(rt, "RosstatUnreachable") else RuntimeError("down")

    monkeypatch.setattr(rt, "fetch_file", unreachable)
    parser = rt.RosstatTourismGvaParser()
    indicator = SimpleNamespace(id=1, code="tour-gva")
    log = SimpleNamespace()
    points, _ = asyncio.run(parser._fetch_and_parse(_db(0), indicator, reg.SERIES["tour-gva"].cfg, log))
    assert len(points) == 38 and fallback_reason(log)
    with pytest.raises(Exception, match="down"):
        asyncio.run(parser._fetch_and_parse(_db(5), indicator, reg.SERIES["tour-gva"].cfg, SimpleNamespace()))


def test_destination_country_series_keep_their_own_source_and_drop_the_mislabelled_thai_total():
    text = (SNAP / rt.DESTINATIONS_FILE).read_text(encoding="utf-8")
    thailand = {p.date: p.value for p in rt.parse_destination(text, "TH", "monthly")}
    assert date(2025, 11, 1) not in thailand and thailand[date(2026, 10, 1)] == 143.638
    kz = [(p.date, p.value) for p in rt.parse_destination(text, "KZ", "ytd_quarterly")]
    assert kz == [(date(2026, 3, 1), 564.669), (date(2026, 6, 1), 918.259), (date(2026, 9, 1), 1287.794)]
    egypt = {p.date: p.value for p in rt.parse_destination(text, "EG", "annual")}
    assert egypt[date(2016, 1, 1)] == 48.036 and min(egypt) == date(2008, 1, 1)
    for slug, *_rest in reg.DESTINATIONS:
        s = reg.SERIES[f"tour-dest-{slug}"]
        assert s.source != reg.SRC_FSB and "ФСБ" in s.methodology  # подпись: данные страны, не российские


# ── Вторая волна: ИПЦ туристских позиций, налоги с туристов, сборник «Туризм в России» ──

def test_cpi_items_are_found_by_code_including_the_misnamed_september_2025_sheet():
    content = (SNAP / rt.CPI_SNAPSHOT).read_bytes()
    tourism = {p.date: p.value for p in rt.parse_cpi_item(content, "9530")}
    assert len(tourism) == 21 and date(2025, 9, 1) in tourism  # лист «0922025»
    assert tourism[date(2026, 9, 1)] == 9.29  # индекс 109,29 → +9,29 % за год
    assert rt.parse_cpi_item(content, "9536")[-1].value == -10.15  # Черноморское побережье подешевело
    # Позиции, введённые в 2025 году, получают изменение к прошлому году только с 2026 года.
    assert rt.parse_cpi_item(content, "9464")[0].date == date(2026, 1, 1)


def test_static_series_tax_resort_fee_and_redenominated_prices():
    text = (SNAP / rt.STATIC_FILE).read_text(encoding="utf-8")
    get = lambda code: {p.date: p.value for p in rt.parse_static(text, code)}
    tax = get("tour-tax")
    assert tax[date(2025, 3, 1)] == 0  # налог за I квартал платят в апреле
    assert sum(v for d, v in tax.items() if d.year == 2025) == pytest.approx(5635.253)  # Казначейство: 5 636,5
    fee = get("tour-resort-fee")
    assert min(fee) == date(2018, 1, 1) and max(fee) == date(2024, 1, 1)  # остаток 2025 года не берётся
    assert fee[date(2024, 1, 1)] == pytest.approx(2468.05, abs=0.01)
    sanatorium = get("tour-price-sanatorium")
    assert sanatorium[date(1997, 1, 1)] == pytest.approx(168.016) and sanatorium[date(1998, 1, 1)] == 201.84
    assert get("tour-package-price")[date(2023, 1, 1)] == pytest.approx(111.75, abs=0.01)


def test_c5_destination_series_drop_sri_lanka_annual_total_and_label_dubai_as_a_region():
    text = (SNAP / rt.DESTINATIONS_FILE).read_text(encoding="utf-8")
    lk = {p.date: p.value for p in rt.parse_destination(text, "LK", "monthly")}
    assert 49.397 not in lk.values() and lk[date(2020, 12, 1)] == 0  # ряд g3: граница закрыта, а не годовой итог
    assert lk[date(2026, 10, 1)] == 6.75
    seychelles = rt.parse_destination(text, "SC", "monthly")
    assert len(seychelles) == 322 and seychelles[0].date == date(2000, 1, 1)  # ряд без пропусков → суммы за год
    vietnam = {p.date: p.value for p in rt.parse_destination(text, "VN", "monthly")}
    assert min(vietnam) == date(2012, 2, 1) and vietnam[date(2026, 10, 1)] == 120.116  # 2008 со сноской «*» не взят
    dubai = reg.SERIES["tour-dest-dubai"]
    assert "Россию отдельно" in dubai.description and "Прибытия россиян" not in dubai.name
    # Ряды с пропусками месяцев без шаблона «сумма за год».
    for code in ("tour-dest-vietnam", "tour-dest-sri-lanka", "tour-dest-zanzibar", "tour-dest-dominican-republic"):
        assert reg.SERIES[code].family is None


def test_page_labels_mix_cyrillic_and_unicode_escapes_without_mojibake():
    assert emiss._unescape(r"Пассажиры \u0430виа \'x\'") == "Пассажиры авиа 'x'"
    assert emiss._unescape("Российская Федерация") == "Российская Федерация"
    assert reg.SERIES["tour-packages"].unit == "тыс. турпакетов"  # шапка «6,4 млн турпакетов», а не «6,4 млн»


def test_g2_g3_history_airports_and_replaced_sri_lanka():
    static = (SNAP / rt.STATIC_FILE).read_text(encoding="utf-8")
    hist = {p.date.year: p.value for p in rt.parse_static(static, "tour-hist-outbound")}
    assert hist[1993] == 8475 and hist[2013] == 38521 and 1994 not in hist
    sochi = {p.date.year: p.value for p in rt.parse_static(static, "tour-airport-annual-sochi")}
    assert sochi[2025] == 12500 and 2020 in sochi  # 2020 — сумма месяцев Росавиации
    assert "вторичный" in reg.SERIES["tour-airport-annual-sochi"].methodology
    dest = (SNAP / rt.DESTINATIONS_FILE).read_text(encoding="utf-8")
    lk = {p.date: p.value for p in rt.parse_destination(dest, "LK", "monthly")}
    assert min(lk) == date(2017, 3, 1) and len(lk) == 115  # ряд g3: сумма месяцев = годовым итогам SLTDA
    abkhazia = {p.date.year: p.value for p in rt.parse_destination(dest, "AB", "annual")}
    assert 2014 not in abkhazia and abkhazia[2025] == 609.3
    assert "1,88 млн" in reg.SERIES["tour-dest-abkhazia"].methodology


def test_border_history_country_slices_and_macao_year_to_date():
    static = (SNAP / rt.STATIC_FILE).read_text(encoding="utf-8")
    turkey = {p.date.year: p.value for p in rt.parse_static(static, "tour-hist-outbound-turkey")}
    assert min(turkey) == 2002 and max(turkey) == 2013
    assert "другой учёт" in reg.SERIES["tour-hist-outbound-turkey"].methodology
    dest = (SNAP / rt.DESTINATIONS_FILE).read_text(encoding="utf-8")
    assert [p.value for p in rt.parse_destination(dest, "MO", "annual")] == [4.112, 39.584]
    ytd = {p.date: p.value for p in rt.parse_destination(dest, "MO-YTD", "monthly")}
    assert ytd[date(2025, 12, 1)] == 39.584 and "с начала года" in reg.SERIES["tour-dest-macao-ytd"].name
