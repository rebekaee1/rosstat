"""Т-11: fixture-тесты парсеров без покрытия.

Каждый parser_type получает минимальный синтетический файл/payload в формате
источника; проверяем, что извлечение точек не ломается молча (regex-дрейф,
смена координат строк — главный класс инцидентов ETL).

Сетевых вызовов нет: XLSX/XLS строятся в памяти, HTTP-клиенты подменяются.
"""

import io
from datetime import date, datetime

import openpyxl
import xlwt

from app.services.binance_btcusdt_parser import _klines_to_points
from app.services.rosstat_demo_parser import (
    parse_demo14_xlsx,
    parse_demo21_xlsx,
    parse_pensioners_xlsx,
)
from app.services.rosstat_fixedassets_parser import parse_depreciation_xlsx
from app.services.rosstat_science_parser import parse_kadry_xls, parse_nauka_total_xls
from app.services.rosstat_weekly_price_parser import (
    _parse_fuel_bulletin_html,
    parse_weekly_price_xlsx,
)


def _xlsx_bytes(rows: list[list], sheet_title: str = "Sheet1") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _xls_bytes(rows: list[list], sheet_name: str = "1") -> bytes:
    wb = xlwt.Workbook()
    ws = wb.add_sheet(sheet_name)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            if val is not None:
                ws.write(r, c, val)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── rosstat_demo ─────────────────────────────────────────────────────


def test_parse_demo21():
    rows = [
        ["Годы", "Родившихся", "Умерших", "прирост", "на 1000: род.", "на 1000: ум.", "x"],
        ["2020", 1436514, 2138586, None, 9.8, 14.6, None],
        ["2021", 1398253, 2441594, None, 9.6, 16.7, None],
        ["всего", "мусор", None, None, None, None, None],
    ]
    out = parse_demo21_xlsx(_xlsx_bytes(rows))
    assert [p.value for p in out["births"]] == [1436.5, 1398.3]  # тыс.
    assert out["death-rate"][0].value == 14.6
    assert len(out["deaths"]) == 2


def test_parse_demo14():
    rows = [[None] for _ in range(5)]
    rows.append(["Возраст", "2022", "2023", "2024"])          # строка 5 — годы
    rows += [[None] for _ in range(9)]                          # 6..14
    rows.append(["моложе трудоспособного возраста", 27000, 26800, 26500])   # 15
    rows.append(["в трудоспособном возрасте", 83000, 83500, 84000])         # 16
    rows.append(["старше трудоспособного возраста", 36000, 35800, 35500])   # 17
    rows += [[None] for _ in range(10)]                         # до >=26 строк
    out = parse_demo14_xlsx(_xlsx_bytes(rows))
    assert [p.value for p in out["working-age-population"]] == [83.0, 83.5, 84.0]
    assert out["pop-under-working-age"][0].date == date(2022, 1, 1)
    assert len(out["pop-over-working-age"]) == 3


def test_parse_pensioners():
    rows = [
        ["Показатель", "2021", "2022", "2023", "2024"],
        ["Всего пенсионеров", 42000.5, 41800.2, 41500.0, 41200.9],
        [None],
        [None],
        [None],
    ]
    out = parse_pensioners_xlsx(_xlsx_bytes(rows, sheet_title="РФ"))
    assert [p.value for p in out] == [42000.5, 41800.2, 41500.0, 41200.9]
    assert out[0].date == date(2021, 1, 1)


# ── rosstat_fixed_assets ─────────────────────────────────────────────


def test_parse_depreciation():
    rows = [
        ["Годы", "Степень износа, %"],
        ["2022", "40,5"],
        ["2023", 41.2],
        ["2024", "999"],   # вне (0,100) → отброс
        ["не год", 50.0],
    ]
    out = parse_depreciation_xlsx(_xlsx_bytes(rows, sheet_title="Данные"))
    assert [(p.date.year, p.value) for p in out] == [(2022, 40.5), (2023, 41.2)]


# ── rosstat_science (.xls) ───────────────────────────────────────────


def test_parse_kadry_xls():
    rows = [
        ["Годы", "Всего"],
        [2022.0, 110000.0],
        ["2023", "108 000"],
        ["2023", 999.0],       # дубль года → игнор
    ]
    out = parse_kadry_xls(_xls_bytes(rows), sheet_idx=0)
    assert [(p.date.year, p.value) for p in out] == [(2022, 110000.0), (2023, 108000.0)]


def test_parse_nauka_total_xls():
    rows = [
        ["", 2021.0, 2022.0, 2023.0],
        ["Всего организаций", 4175.0, 4195.0, 4200.0],
    ]
    out = parse_nauka_total_xls(_xls_bytes(rows, sheet_name="1"), sheet_name="1")
    assert [(p.date.year, p.value) for p in out] == [
        (2021, 4175.0), (2022, 4195.0), (2023, 4200.0),
    ]


# ── rosstat_weekly_price ─────────────────────────────────────────────


def test_parse_weekly_price_xlsx():
    rows = [
        ["О средних потребительских ценах"],
        [None],
        [None],
        ["Наименование", "на 12 января", "на 19 января", "мусор"],
        ["Бензин автомобильный марки АИ-92, л", "58,44", 58.61, None],
        ["Дизельное топливо, л", 65.2, "…", None],
    ]
    out = parse_weekly_price_xlsx(
        _xlsx_bytes(rows, sheet_title="2026"),
        "Бензин автомобильный марки АИ-92, л",
    )
    assert [(p.date, p.value) for p in out] == [
        (date(2026, 1, 12), 58.44),
        (date(2026, 1, 19), 58.61),
    ]


def test_parse_fuel_bulletin_html():
    html = """
    <h2>Средние потребительские цены на нефтепродукты по Российской Федерации</h2>
    <table>
      <tr><th></th><th>22 июня 2026 г.</th><th>29 июня 2026 г.</th></tr>
      <tr><td>Бензин марки АИ-92</td><td>58,44</td><td>58,61</td></tr>
      <tr><td>Дизельное топливо</td><td>67,10</td><td>67,25</td></tr>
    </table>
    """
    out = _parse_fuel_bulletin_html(html, "аи-92")
    assert [(p.date, p.value) for p in out] == [
        (date(2026, 6, 22), 58.44),
        (date(2026, 6, 29), 58.61),
    ]
    assert _parse_fuel_bulletin_html("<p>ничего</p>", "аи-92") == []


# ── binance ──────────────────────────────────────────────────────────


def test_binance_klines_to_points():
    day_close_ms = int(datetime(2026, 7, 1, 23, 59, 59).timestamp() * 1000)
    klines = [
        [0, "1", "2", "0.5", "65000.5", "10", day_close_ms],
        [0, "1", "2", "0.5", "битые-данные", "10", day_close_ms],  # skip
        [0, "1", "2", "0.5", "65100.0"],                            # короткая → skip
    ]
    out = _klines_to_points(klines)
    assert len(out) == 1
    assert out[0][1] == 65000.5


# ── moex_index ───────────────────────────────────────────────────────


def test_moex_fetch_page_parses_payload(monkeypatch):
    import app.services.moex_index_parser as m

    payload = {
        "history": {
            "columns": ["BOARDID", "TRADEDATE", "CLOSE"],
            "data": [
                ["SNDX", "2026-07-01", 3250.5],
                ["SNDX", "2026-07-02", None],      # NULL CLOSE → пропуск, но строка считается
                ["SNDX", "2026-07-03", 3260.1],
            ],
        }
    }

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            return _Resp()

    monkeypatch.setattr(m.httpx, "Client", _Client)
    points, raw_n = m._fetch_page("IMOEX", 0, None)
    assert raw_n == 3, "пагинация обязана шагать по сырым строкам"
    assert points == [(date(2026, 7, 1), 3250.5), (date(2026, 7, 3), 3260.1)]


# ── cbr_monetary_agg ─────────────────────────────────────────────────


def test_fetch_monetary_agg_sums_rows(monkeypatch):
    import app.services.cbr_monetary_agg_parser as m

    # Лист «Денежные агрегаты»: header — datetime-колонки; данные по строкам
    # из ROW_MAP (M0 → строка 2; 1-базная нумерация).
    rows = [
        ["Показатель", datetime(2026, 5, 1), datetime(2026, 6, 1)],
        ["M0", 17000.5, 17100.25],
    ]
    xlsx = _xlsx_bytes(rows, sheet_title="Денежные агрегаты")

    class _Resp:
        content = xlsx

        def raise_for_status(self):
            pass

    class _Session:
        def get(self, url, timeout=None):
            return _Resp()

        def close(self):
            pass

    monkeypatch.setattr(m, "create_session", lambda: _Session())
    out = m.fetch_monetary_agg("M0", year_from=2020)
    # date_offset_months=-1: данные «на 1 июня» относятся к маю.
    assert out == [(date(2026, 4, 1), 17000.5), (date(2026, 5, 1), 17100.25)]
