"""Росстат, раздел «Туризм» (rosstat.gov.ru/statistics/turizm): въезд и выезд по данным ФСБ России и туристская
индустрия в ВВП (реестр — ``app.data.tourism_russia``).

``Poezdki_MM-YYYY.xlsx`` — имя меняется с каждым выпуском, файл ищется по ссылке со страницы раздела.
- Листы ``1.YYYY`` (въезд иностранцев) и ``2.YYYY`` (выезд россиян): строка «Всего» и строки стран, столбцы —
  нарастающие итоги «Январь–март … Январь–декабрь», тысяч поездок. Квартал = разность соседних итогов. В 2014 году
  нет I квартала, поэтому ряды начинаются с 2015 года (иначе сумма за 2014 год была бы неполной).
- Листы ``3.YYYY`` (въезд, с 2022 года): итоги «Январь … Январь–декабрь» в миллионах поездок; месяц = разность.
- Ловушки (проверено 20.11.2026): числа строками с неразрывным пробелом («8 436») и запятой; сноски в подписях
  («Январь-март1)», «Январь-декабрь*», год «2023*»); перенос строки внутри подписи; «Абхазия » с пробелом;
  «Таиланд» и «Тайланд» в разные годы.

``VDS_ti_OKVED2_vvp.xlsx`` — добавленная стоимость туристской индустрии: лист 2 — квартал, млрд руб.; лист 4 — доля
в ВВП по кварталам; лист 3 — доля за год; лист 6 — индекс физического объёма к тому же кварталу прошлого года. Год в
шапке может нести сноску («20222)» = 2022 со сноской 2).

Если сайт Росстата недоступен и у ряда ещё нет ни одной точки, используется файл, скачанный 20.11.2026
(``app/data/tourism_snapshots``), со статусом ``fallback_used``; при уже загруженной истории сбой остаётся сбоем.
"""

from __future__ import annotations

import asyncio
import io
import re
from datetime import date
from pathlib import Path
from typing import ClassVar

import openpyxl
from sqlalchemy import func, select

from app.models import IndicatorData
from app.services.base_parser import BaseParser, mark_fallback_used
from app.services.rosstat_labor_parser import DataPoint
from app.services.rosstat_sdds_fetcher import resolve_mediabank_file

SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "data" / "tourism_snapshots"
TOURISM_PAGE = "https://rosstat.gov.ru/statistics/turizm"
TRIPS_PATTERN = r"Poezdki_\d{1,2}-\d{4}\.xlsx$"
GVA_PATTERN = r"VDS_ti_OKVED2_vvp\.xlsx$"
TRIPS_SNAPSHOT = "Poezdki_10-2026.xlsx"
GVA_SNAPSHOT = "VDS_ti_OKVED2_vvp.xlsx"

MONTHS = ("январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь",
          "ноябрь", "декабрь")
QUARTER_MONTH = {"i": 3, "ii": 6, "iii": 9, "iv": 12}
FIRST_TRIPS_YEAR = 2015


class RosstatTourismFormatError(ValueError):
    pass


def _num(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    if text in ("", "-", "—", "–", "…", "x", "х"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _label(raw) -> str:
    """«Абхазия », «Январь-\\nмарт1)», «Январь-декабрь*» → нормальный вид без сносок."""
    text = re.sub(r"\s+", " ", str(raw or "")).strip().lower()
    text = re.sub(r"[\d*)]+$", "", text).strip()
    return text.replace(" -", "-").replace("- ", "-").replace("–", "-")


def _ytd_month(raw) -> int | None:
    text = _label(raw)
    if text == "январь":
        return 1
    if text.startswith("январь-"):
        end = text.split("-", 1)[1].strip()
        return MONTHS.index(end) + 1 if end in MONTHS else None
    return None


def _year(raw) -> int | None:
    if isinstance(raw, (int, float)) and 1990 < raw < 2100:
        return int(raw)
    m = re.match(r"^\s*((?:19|20)\d{2})", str(raw or ""))
    return int(m.group(1)) if m else None


def _load(content: bytes):
    return openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)


# ── Въезд и выезд ─────────────────────────────────────────────────────────────

def _sheet_ytd(rows: list[tuple], names: set[str] | None) -> tuple[int, dict[int, float]]:
    """Один лист: (год, {месяц конца итога: тысяч поездок}) для строки «Всего» или страны из ``names``."""
    year = None
    header: dict[int, int] = {}
    scale = None
    for row in rows[:8]:
        for cell in row:
            text = _label(cell)
            if text.startswith("тысяч"):
                scale = 1.0
            elif text.startswith("млн"):
                scale = 1000.0
        if year is None:
            year = next((y for y in (_year(c) for c in row[1:]) if y), None)
        cols = {i: m for i, c in enumerate(row) if i and (m := _ytd_month(c))}
        if len(cols) > len(header):
            header = cols
    if year is None or not header or scale is None:
        raise RosstatTourismFormatError(f"лист без года, шапки периодов или единицы: {rows[:6]!r:.300}")
    wanted = {"всего"} if names is None else names
    for row in rows:
        if _label(row[0]) in wanted:
            values = {m: v * scale for i, m in header.items() if i < len(row) and (v := _num(row[i])) is not None}
            return year, values
    return year, {}


def _discrete(ytd: dict[int, float], step: int) -> dict[int, float]:
    """Нарастающие итоги → значения периода; период без предыдущего итога пропускается."""
    out: dict[int, float] = {}
    for month, value in sorted(ytd.items()):
        if month == step:
            out[month] = value
        elif month - step in ytd:
            out[month] = value - ytd[month - step]
    return out


def parse_trips(content: bytes, direction: str, *, country: list[str] | None = None,
                monthly: bool = False) -> list[DataPoint]:
    prefix = {"inbound": "1", "outbound": "2"}[direction]
    if monthly:
        if direction != "inbound" or country:
            raise ValueError("месячный ряд есть только у въезда в целом")
        prefix = "3"
    names = {_label(n) for n in country} if country else None
    wb = _load(content)
    try:
        sheets = [name for name in wb.sheetnames if re.fullmatch(rf"{prefix}\.\d{{4}}", name.strip())]
        if not sheets:
            raise RosstatTourismFormatError(f"нет листов {prefix}.ГГГГ")
        points: list[DataPoint] = []
        for name in sheets:
            year, ytd = _sheet_ytd(list(wb[name].iter_rows(values_only=True)), names)
            if year < FIRST_TRIPS_YEAR and not monthly:
                continue
            for month, value in _discrete(ytd, 1 if monthly else 3).items():
                if value < 0:
                    raise RosstatTourismFormatError(f"{name}: отрицательный период {month} ({value})")
                points.append(DataPoint(date(year, month, 1), round(value, 3)))
    finally:
        wb.close()
    if names is None and not points:
        raise RosstatTourismFormatError(f"{direction}: ни одной точки")
    return sorted(points, key=lambda p: p.date)


# ── Туристская индустрия в ВВП ────────────────────────────────────────────────

GVA_TABLES = {
    "value_quarterly": ("2", "quarterly"),
    "share_quarterly": ("4", "quarterly"),
    "share_annual": ("3", "annual"),
    "volume_quarterly": ("6", "quarterly"),
}


def parse_gva(content: bytes, table: str) -> list[DataPoint]:
    sheet, kind = GVA_TABLES[table]
    wb = _load(content)
    try:
        if sheet not in wb.sheetnames:
            raise RosstatTourismFormatError(f"нет листа {sheet}")
        rows = [r for r in wb[sheet].iter_rows(values_only=True) if any(c is not None for c in r)]
    finally:
        wb.close()
    year_row = next((i for i, r in enumerate(rows) if sum(1 for c in r if _year(c)) >= 2), None)
    if year_row is None:
        raise RosstatTourismFormatError(f"лист {sheet}: нет строки годов")
    years: dict[int, int] = {}
    current = None
    for i, cell in enumerate(rows[year_row]):
        y = _year(cell)
        if y:
            current = y
        if current:
            years[i] = current
    points: list[DataPoint] = []
    if kind == "annual":
        values = rows[year_row + 1]
        for i, y in years.items():
            if _year(rows[year_row][i]) and (v := _num(values[i])) is not None:
                points.append(DataPoint(date(y, 1, 1), round(v, 4)))
    else:
        quarters = rows[year_row + 1]
        values = rows[year_row + 2]
        for i, y in years.items():
            q = _label(quarters[i] if i < len(quarters) else "").split(" ")[0]
            if q in QUARTER_MONTH and i < len(values) and (v := _num(values[i])) is not None:
                points.append(DataPoint(date(y, QUARTER_MONTH[q], 1), round(v, 4)))
    if not points:
        raise RosstatTourismFormatError(f"лист {sheet}: ни одной точки")
    if len({p.date for p in points}) != len(points):
        raise RosstatTourismFormatError(f"лист {sheet}: повтор периода")
    return sorted(points, key=lambda p: p.date)


# ── Загрузка ──────────────────────────────────────────────────────────────────

def fetch_file(pattern: str, snapshot: str, page: str = TOURISM_PAGE) -> tuple[bytes, str]:
    return resolve_mediabank_file(catalog_urls=[page], name_patterns=[pattern])


def snapshot_file(snapshot: str) -> tuple[bytes, str]:
    return (SNAPSHOT_DIR / snapshot).read_bytes(), f"{TOURISM_PAGE} (файл {snapshot}, снимок 20.11.2026)"


class _TourismFileParser(BaseParser):
    pattern: ClassVar[str]
    snapshot: ClassVar[str]
    page: ClassVar[str] = TOURISM_PAGE

    def _parse(self, content: bytes, cfg: dict) -> list[DataPoint]:
        raise NotImplementedError

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        try:
            content, url = await asyncio.to_thread(fetch_file, self.pattern, self.snapshot, self.page)
        except Exception as exc:  # noqa: BLE001 — сеть/бан/имя файла: решает наличие истории
            has_history = await db.scalar(
                select(func.count()).select_from(IndicatorData).where(IndicatorData.indicator_id == indicator.id)
            )
            if has_history:
                raise
            content, url = snapshot_file(self.snapshot)
            mark_fallback_used(fetch_log, f"Росстат недоступен ({str(exc)[:160]}); файл 20.11.2026")
        points = await asyncio.to_thread(self._parse, content, cfg)
        return points, url


class RosstatTourismTripsParser(_TourismFileParser):
    parser_type: ClassVar[str] = "rosstat_tourism_trips"
    pattern = TRIPS_PATTERN
    snapshot = TRIPS_SNAPSHOT

    def _parse(self, content: bytes, cfg: dict) -> list[DataPoint]:
        return parse_trips(content, cfg["trips_direction"], country=cfg.get("trips_country"),
                           monthly=bool(cfg.get("trips_monthly")))


class RosstatTourismGvaParser(_TourismFileParser):
    parser_type: ClassVar[str] = "rosstat_tourism_gva"
    pattern = GVA_PATTERN
    snapshot = GVA_SNAPSHOT

    def _parse(self, content: bytes, cfg: dict) -> list[DataPoint]:
        return parse_gva(content, cfg["gva_table"])


# ── Россияне в странах назначения по данным этих стран ────────────────────────
#
# Таиланд (Министерство туризма и спорта, помесячно 2025–2026), Узбекистан (Нацкомстат, 2014–2025), Казахстан (Бюро
# национальной статистики, нарастающий итог 2026 года), Египет (ОЭСР по данным Египта, 2008–2025) — у этих стран нет
# своей страницы на сайте, поэтому ряды стоят у России рядом с выездом по данным ФСБ. Значения собраны агентами
# 20.11.2026 в один файл (`destinations_russians.csv`); строка Таиланда «2025-11 = 1 418 101» — на деле сумма
# января–октября 2025 года и исключена. Автоматического обновления у источников нет: ряд обновляется заменой файла.

DESTINATIONS_FILE = "destinations_russians.csv"


def parse_destination(text: str, iso2: str, kind: str) -> list[DataPoint]:
    import csv

    rows = [r for r in csv.DictReader(io.StringIO(text), delimiter=";") if r["iso2"].strip() == iso2]
    if not rows:
        raise RosstatTourismFormatError(f"нет строк страны {iso2}")
    points: list[DataPoint] = []
    if kind == "ytd_quarterly":
        ytd: dict[tuple[int, int], float] = {}
        for r in rows:
            m = re.fullmatch(r"(\d{4})-01\.\.(\d{2})", r["период"].strip())
            if not m or int(m.group(2)) % 3:
                raise RosstatTourismFormatError(f"{iso2}: период {r['период']!r}")
            ytd[(int(m.group(1)), int(m.group(2)))] = float(r["значение"])
        for (year, month), value in sorted(ytd.items()):
            prev = ytd.get((year, month - 3)) if month > 3 else 0.0
            if prev is not None:
                points.append(DataPoint(date(year, month, 1), round((value - prev) / 1000, 3)))
    else:
        for r in rows:
            period = r["период"].strip()
            day = date(int(period[:4]), int(period[5:7]), 1) if kind == "monthly" else date(int(period), 1, 1)
            points.append(DataPoint(day, round(float(r["значение"]) / 1000, 3)))
    if len({p.date for p in points}) != len(points):
        raise RosstatTourismFormatError(f"{iso2}: повтор периода")
    return sorted(points, key=lambda p: p.date)


class TourismDestinationParser(BaseParser):
    parser_type: ClassVar[str] = "tourism_destination_file"

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        text = (SNAPSHOT_DIR / DESTINATIONS_FILE).read_text(encoding="utf-8")
        return parse_destination(text, cfg["dest_iso2"], cfg["dest_kind"]), indicator.source_url


# ── ИПЦ туристских позиций по России (ipc_spr_MM-YYYY.xlsx, 20.11.2026) ──────
#
# Файл «Индексы потребительских цен и структура потребительских расходов» перезаписывается каждый месяц и хранит
# только текущий и прошлый год: лист на месяц (имя «ММГГГГ»; сентябрь 2025 назван «0922025»), строки — группы и
# товары-представители с локальным кодом во втором столбце, столбцы — вес в расходах, индекс к предыдущему месяцу, к
# декабрю, к тому же месяцу прошлого года. Ряд — изменение цены к тому же месяцу прошлого года, в процентах (индекс
# минус 100); позиция ищется по коду, а не по названию. Загруженная история при обрезке файла сохраняется.

PRICE_PAGE = "https://rosstat.gov.ru/statistics/price"
CPI_PATTERN = r"ipc_spr_\d{2}-\d{4}\.xlsx$"
CPI_SNAPSHOT = "ipc_spr_09-2026.xlsx"
_CPI_SHEET = re.compile(r"^(\d{2})\d*?((?:19|20)\d{2})$")


def parse_cpi_item(content: bytes, item: str) -> list[DataPoint]:
    wb = _load(content)
    try:
        points: list[DataPoint] = []
        for name in wb.sheetnames:
            m = _CPI_SHEET.match(name.strip())
            if not m or not 1 <= int(m.group(1)) <= 12:
                continue
            day = date(int(m.group(2)), int(m.group(1)), 1)
            for row in wb[name].iter_rows(values_only=True):
                if len(row) > 5 and str(row[1]).strip() == item:
                    yoy = _num(row[5])
                    if yoy is not None:
                        if not 20 < yoy < 500:
                            raise RosstatTourismFormatError(f"{name}: индекс {yoy} у позиции {item}")
                        points.append(DataPoint(day, round(yoy - 100, 2)))
                    break
    finally:
        wb.close()
    if not points:
        raise RosstatTourismFormatError(f"позиция {item}: ни одной точки")
    return sorted(points, key=lambda p: p.date)


class RosstatTourismCpiParser(_TourismFileParser):
    parser_type: ClassVar[str] = "rosstat_tourism_cpi"
    pattern = CPI_PATTERN
    snapshot = CPI_SNAPSHOT
    page = PRICE_PAGE

    def _parse(self, content: bytes, cfg: dict) -> list[DataPoint]:
        return parse_cpi_item(content, str(cfg["cpi_item"]))


# ── Разовые официальные ряды (tourism_static.csv, 20.11.2026) ─────────────────
#
# Источники без живого машиночитаемого ряда или с прекращённой публикацией: курортный сбор 2018–2024 (Казначейство,
# форма 0503317; эксперимент закончен, остаточные поступления 2025 года не берутся); туристический налог по кварталам
# поступления (ФНС, 1-НМ, нарастающий итог → квартал; итог 2025 года сходится с Казначейством: 5 635,3 и 5 636,5 млн
# руб.; в Москве налог не введён — поэтому её нет у Казначейства, у ФНС там ноль); цена дня в санатории и доме отдыха
# 1991–2025 (до 1998 года — деноминированные рубли, делены на 1000); таблицы сборника «Туризм в России» 2024 года за
# 2014–2023 (сборник снят с сайта Росстата, взят из веб-архива). Ряд обновляется заменой файла.

STATIC_FILE = "tourism_static.csv"


def parse_static(text: str, code: str) -> list[DataPoint]:
    import csv

    points = []
    for r in csv.DictReader(io.StringIO(text), delimiter=";"):
        if r["code"] != code:
            continue
        period = r["period"].strip()
        day = date.fromisoformat(period) if "-" in period else date(int(period), 1, 1)
        points.append(DataPoint(day, float(r["value"])))
    if not points:
        raise RosstatTourismFormatError(f"{code}: нет строк в {STATIC_FILE}")
    return sorted(points, key=lambda p: p.date)


class TourismStaticParser(BaseParser):
    parser_type: ClassVar[str] = "tourism_static_file"

    async def _fetch_and_parse(self, db, indicator, cfg, fetch_log):
        text = (SNAPSHOT_DIR / STATIC_FILE).read_text(encoding="utf-8")
        return parse_static(text, cfg.get("static_code", indicator.code)), indicator.source_url
