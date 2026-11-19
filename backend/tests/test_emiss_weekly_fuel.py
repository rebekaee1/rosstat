"""Недельные цены на топливо по субъектам (ЕМИСС 37426, 18.11.2026): разбор витрины и даты недель.

Ключи ячеек и подписи взяты из живого ответа dataGrid.do от 18.11.2026 (запрос с Mac):
``dim2025_1853940_d111260500_i11115`` — год, oid недели; ``dim57831``/``dim58273`` — названия
территории и позиции. Строка России 2025 года совпадает с федеральным рядом до копейки.
"""

import asyncio
from datetime import date

import pytest

from app.services import emiss_weekly_fuel as w
from app.services.regional_weekly import value_on

PAGE_SNIPPET = """
                        filters: {
                            33560: {
                                title: '\\u041F\\u0435\\u0440\\u0438\\u043E\\u0434',
                                values: {
                                    1853940: {
                                        title: '1 \\u043D\\u0435\\u0434\\u0435\\u043B\\u044F 2025',
                                    },
                                    1853941: {
                                        title: '2 \\u043D\\u0435\\u0434\\u0435\\u043B\\u044F 2025',
                                    },
                                    1856404: {
                                        title: '1 \\u043D\\u0435\\u0434\\u0435\\u043B\\u044F 2026',
                                    },
                                    1633352: {
                                        title: '01 \\u043D\\u0435\\u0434\\u0435\\u043B\\u044F ( \\u043D\\u0430 10 \\u044F\\u043D\\u0432\\u0430\\u0440\\u044F)',
                                    },
                                    2025: {
                                        title: '2025',
                                    },
"""

RF_NEW = "Российская Федерация без учета новых субъектов (с 01.01.2023)"
RF_OLD = "Российская Федерация"
SPB = "Город Санкт-Петербург город федерального значения"
AI92 = "Бензин автомобильный марки АИ-92, л"
AI95 = "Бензин автомобильный марки АИ-95, л"
DT = "Дизельное топливо, л"


def _row(territory, fuel, cells):
    row = {"dim57831": territory, "dim58273": fuel}
    for i, (oid, value) in enumerate(cells):
        row[f"dim2025_{oid}_d111260500_i{11115 + i}"] = value
    return row


def test_week_oids_from_page_only_dated_by_number():
    weeks = w.parse_week_oids(PAGE_SNIPPET)
    assert weeks == {2025: {1: "1853940", 2: "1853941"}, 2026: {1: "1856404"}}


def test_grid_splits_russia_and_subjects_and_skips_old_russia_after_2022():
    payload = {"results": [
        _row(RF_NEW, AI92, [("1853940", "55,46"), ("1853941", "55,49")]),
        _row(RF_OLD, AI92, [("1853940", "55,90")]),
        _row(SPB, DT, [("1853940", "70,02"), ("1853941", "-")]),
        _row("Неизвестная территория", DT, [("1853940", "70,00")]),
    ]}
    points, russia = w.parse_weekly_grid(
        payload, year=2025, week_by_oid={"1853940": 1, "1853941": 2},
        dimnames={SPB: "sankt-peterburg", RF_OLD: "russia", RF_NEW: "russia"},
    )
    assert russia == {"ceni-ai92": {1: 55.46, 2: 55.49}}
    assert points == {("ceni-dt", "sankt-peterburg"): {1: 70.02}}


def test_grid_uses_whole_russia_row_until_2022():
    payload = {"results": [
        {"dim57831": RF_OLD, "dim58273": AI92, "dim2022_1_d1_i1": "45,10"},
        {"dim57831": RF_NEW, "dim58273": AI92, "dim2022_1_d1_i2": "44,00"},
    ]}
    _points, russia = w.parse_weekly_grid(payload, year=2022, week_by_oid={"1": 1}, dimnames={})
    assert russia == {"ceni-ai92": {1: 45.10}}


NATIONAL_2025 = {
    "fuel-ai92": [(date(2025, 1, 9), 55.46), (date(2025, 1, 13), 55.49), (date(2025, 1, 20), 55.55)],
    "fuel-ai95": [(date(2025, 1, 9), 60.62), (date(2025, 1, 13), 60.63), (date(2025, 1, 20), 60.67)],
    "fuel-diesel": [(date(2025, 1, 9), 70.11), (date(2025, 1, 13), 70.15), (date(2025, 1, 20), 70.15)],
}


def test_week_dates_from_national_calendar_when_russia_matches():
    russia = {
        "ceni-ai92": {1: 55.46, 2: 55.49, 3: 55.55},
        "ceni-ai95": {1: 60.62, 2: 60.63, 3: 60.67},
        "ceni-dt": {1: 70.11, 2: 70.15, 3: 70.15},
        "ceni-ai98": {1: 80.0},
    }
    assert w.resolve_week_dates(russia, NATIONAL_2025) == {
        1: date(2025, 1, 9), 2: date(2025, 1, 13), 3: date(2025, 1, 20),
    }


def test_week_without_matching_national_price_gets_no_date():
    russia = {
        "ceni-ai92": {1: 55.46, 2: 99.99, 3: 55.55},
        "ceni-ai95": {1: 60.62, 2: 60.63, 3: 60.67},
        "ceni-dt": {1: 70.11, 2: 70.15, 3: 70.15},
    }
    assert w.resolve_week_dates(russia, NATIONAL_2025) == {1: date(2025, 1, 9), 3: date(2025, 1, 20)}


def test_week_dates_survive_missing_week_in_national_series():
    national = {code: [series[0], series[2]] for code, series in NATIONAL_2025.items()}
    russia = {
        "ceni-ai92": {1: 55.46, 2: 55.49, 3: 55.55},
        "ceni-ai95": {1: 60.62, 2: 60.63, 3: 60.67},
        "ceni-dt": {1: 70.11, 2: 70.15, 3: 70.15},
    }
    assert w.resolve_week_dates(russia, national) == {1: date(2025, 1, 9), 3: date(2025, 1, 20)}


def test_single_fuel_match_is_not_enough():
    russia = {"ceni-ai92": {1: 55.46}}
    assert w.resolve_week_dates(russia, NATIONAL_2025) == {}


@pytest.mark.parametrize("last, today, expected", [
    (None, date(2026, 11, 18), [2022, 2023, 2024, 2025, 2026]),
    (date(2026, 10, 26), date(2026, 11, 18), [2026]),
    (date(2025, 12, 22), date(2026, 1, 15), [2025, 2026]),
])
def test_years_to_fetch(last, today, expected):
    assert w.years_to_fetch(last, today=today) == expected


def test_value_on_date_takes_last_registration_not_later():
    points = [(date(2025, 12, 22), 75.83), (date(2026, 1, 12), 77.21)]
    assert value_on(points, date(2026, 1, 1)) == (date(2025, 12, 22), 75.83)
    assert value_on(points, date(2026, 1, 12)) == (date(2026, 1, 12), 77.21)
    assert value_on(points, date(2025, 1, 1)) == (date(2025, 12, 22), 75.83)
    assert value_on([], date(2026, 1, 1)) is None


def test_fetch_year_sends_weeks_in_columns_and_all_fuels():
    seen = {}

    async def fake_post(indicator_id, params):
        seen["id"] = indicator_id
        seen["params"] = params
        return {"results": [_row(RF_NEW, AI92, [("1853940", "55,46")])]}

    points, russia = asyncio.run(w.fetch_year(
        2025, {1: "1853940"}, ["1688519"], {SPB: "sankt-peterburg"}, post_grid=fake_post,
    ))
    assert seen["id"] == 37426
    params = seen["params"]
    assert ("columnObjectIds", "33560") in params and ("lineObjectIds", "58273") in params
    assert {v for k, v in params if v.startswith("58273_")} == {f"58273_{oid}" for oid in w.WEEKLY_FUELS}
    assert ("selectedFilterIds", "33560_1853940") in params
    assert russia == {"ceni-ai92": {1: 55.46}} and points == {}


def test_rows_without_any_price_mean_format_change():
    async def fake_post(_indicator_id, _params):
        return {"results": [{"dim57831": "?", "dim58273": "?"}]}

    with pytest.raises(w.EmissFormatError):
        asyncio.run(w.fetch_year(2025, {1: "1853940"}, [], {}, post_grid=fake_post))


# --- Цены по субъектам из PDF-бюллетеня Росстата (19.11.2026) ---------------------------------------
# Текст — pypdf-выгрузка 175_18-11-2026.pdf. 19.11 витрина 37426 стояла на 26.10; бюллетень за 26.10
# (169n-ben28.pdf) совпал с её точками на боевом во всех 373 парах «марка × территория».

from pathlib import Path  # noqa: E402

from app.services.emiss_regional_parser import load_dimnames  # noqa: E402

_BULLETIN_175 = (Path(__file__).parent / "fixtures" / "rosstat_fuel" / "bulletin_175_2026-11-18_pypdf.txt").read_text(
    encoding="utf-8"
)


def test_bulletin_gives_all_subjects_districts_and_russia_on_registration_date():
    reg_date, points, unmatched = w.parse_bulletin_regional_text(
        _BULLETIN_175, w.bulletin_territory_map(load_dimnames())
    )
    assert reg_date == date(2026, 11, 16)
    assert unmatched == []
    slugs = {slug for _code, slug in points}
    assert len(slugs) == 94  # 85 субъектов + 8 округов + Россия
    assert points[("ceni-dt", "russia")] == 87.09  # = федеральный ряд fuel-diesel на 16.11
    assert points[("ceni-ai92", "russia")] == 70.04
    assert points[("ceni-dt", "moskva")] == 82.96
    assert points[("ceni-ai95", "respublika-severnaya-osetiya")] == 82.03
    # Многострочные названия и «… (кроме …)»: берётся весь субъект, не его часть.
    assert points[("ceni-dt", "hanty-mansiyskiy-ao")] == 95.42
    assert points[("ceni-dt", "tyumenskaya-oblast")] == 93.81
    assert points[("ceni-dt", "arhangelskaya-oblast")] == 86.86
    # «…» — нет данных: точки нет, соседние марки есть.
    assert ("ceni-ai98", "nenetskiy-ao") not in points
    assert points[("ceni-dt", "nenetskiy-ao")] == 92.06


def test_bulletin_row_with_ascii_dots_does_not_glue_to_next_name():
    text = (
        "Средние потребительские цены на бензин автомобильный и дизельное топливо на 26 октября 2026 года\n"
        "рублей за литр\n"
        "Магаданская область 94,45 92,97 96,48 ... 137,75\n"
        "Сахалинская область 70,10 67,20 72,30 99,00 80,40\n"
    )
    tmap = w.bulletin_territory_map(load_dimnames())
    reg_date, points, unmatched = w.parse_bulletin_regional_text(text, tmap)
    assert reg_date == date(2026, 10, 26) and unmatched == []
    assert points[("ceni-dt", "magadanskaya-oblast")] == 137.75
    assert ("ceni-ai98", "magadanskaya-oblast") not in points
    assert points[("ceni-dt", "sahalinskaya-oblast")] == 80.40


def test_bulletin_without_regional_table_gives_nothing():
    assert w.parse_bulletin_regional_text("Об оценке индекса потребительских цен", {}) == (None, {}, [])


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self._rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, indicators, regions):
        self._answers = [_Rows(indicators), _Rows(regions)]
        self.commits = 0

    async def execute(self, _stmt):
        return self._answers.pop(0)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass


def test_bulletin_update_writes_points_for_known_indicators_and_regions(monkeypatch):
    from types import SimpleNamespace

    written: list[dict] = []

    async def fake_upsert(_db, values):
        written.extend(values)
        return len(values), 0

    async def noop(*_a, **_k):
        return None

    monkeypatch.setattr(w, "_upsert_weekly", fake_upsert)
    monkeypatch.setattr(w, "acquire_regional_write_lock", noop)
    monkeypatch.setattr(w, "publish_committed_regional_changes", noop)
    db = _FakeDb(
        [SimpleNamespace(code="ceni-dt", id=7), SimpleNamespace(code="ceni-ai92", id=5)],
        [("russia", 1), ("moskva", 77)],
    )
    stats = asyncio.run(w.run_bulletin_regional_update(db, fetch_texts=lambda: [_BULLETIN_175]))
    assert stats["bulletins"] == 1 and stats["dates"] == 1 and stats["unmatched"] == 0
    got = {(r["indicator_id"], r["region_id"]): r["value"] for r in written}
    assert got == {(7, 1): 87.09, (5, 1): 70.04, (7, 77): 82.96, (5, 77): 68.62}
    assert {r["date"] for r in written} == {date(2026, 11, 16)}


def test_job_runs_bulletin_even_when_emiss_showcase_fails_and_then_reraises(monkeypatch):
    """19.11.2026: сбой витрины (403 fedstat) не отменяет последнюю неделю из бюллетеня."""
    from contextlib import asynccontextmanager

    from app.config import settings

    calls: list[str] = []
    sent: list[str] = []

    @asynccontextmanager
    async def fake_session():
        yield object()

    async def failing_showcase(_db):
        calls.append("emiss")
        raise RuntimeError("fedstat 403")

    async def bulletin(_db):
        calls.append("bulletin")
        return {"bulletins": 1}

    async def not_muted(*_a, **_k):
        return False

    async def fake_send(text, kind=None):
        sent.append(kind)
        return True

    monkeypatch.setattr(w, "async_session", fake_session)
    monkeypatch.setattr(w, "run_weekly_fuel_update", failing_showcase)
    monkeypatch.setattr(w, "run_bulletin_regional_update", bulletin)
    monkeypatch.setattr(settings, "regional_fuel_bulletin_enabled", True)
    monkeypatch.setattr("app.services.alerting.alert_muted", not_muted)
    monkeypatch.setattr("app.services.alerting.send_telegram", fake_send)
    with pytest.raises(RuntimeError, match="fedstat 403"):
        asyncio.run(w.emiss_weekly_fuel_job())
    assert calls == ["emiss", "bulletin"]
    assert sent == ["etl_alert"]
