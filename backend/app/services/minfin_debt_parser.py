"""ETL: ФНБ и государственный долг России из файлов Минфина (19.11.2026).

Реестр рядов и адресов — ``app.data.minfin_debt``. Один parser_type ``minfin_debt_xlsx`` на шесть рядов: ряд
выбирается ``model_config_json.minfin_series``.

Путь данных:

1. Живой: страница Минфина → ссылка на самый свежий файл → файл. Боевому серверу Минфин отвечает 503/403 (сети
   Timeweb, см. docs/data_sources.md, раздел Минфина), поэтому живой путь там пока не работает; код его держит, чтобы
   доступ вернулся сам, если Минфин снимет блок.
2. Снимок ``app/data/minfin/<snapshot>``: в образе — файл из репозитория, поверх него свежий файл кладёт
   ``scripts/minfin-debt-sync-from-mac.sh`` с Mac владельца (launchd, дважды в день). Прогон по снимку пишет статус
   ``fallback_used``; точки новее снимка не удаляются (ряд не ``replace_series``).

Файл и неудача живого пути кэшируются в процессе на 10 минут на источник: четыре ряда ФНБ читают один файл, и
второй ряд не ждёт снова цепочку прокси до Минфина (до ~60 с).

Форматы (живые файлы 19.11.2026 — фикстуры теста):
- ФНБ ``Dannye_*.xlsx``: строка 3 — «Показатель», дальше столбцы-месяцы (первый — текст «Январь 2008¹», дальше
  даты); значение месяца — на конец месяца, хранится как 1-е число следующего;
- внутренний долг ``*.xls``: лист на год, строка «по состоянию на» с датами (текст « 01.01.2009» или число Excel),
  строка «…внутренний долг… — всего»;
- внешний долг ``GVD_*.xlsx``: столбец B — дата, C — всего, млн долларов → млрд.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.minfin_debt import SERIES_BY_CODE, SOURCES, SITE, Source
from app.models import FetchLog, Indicator
from app.services.base_parser import BaseParser, mark_fallback_used
from app.services.data_validator import validate_points

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "minfin"
ARTIFACT_URL_PREFIX = "artifact://"
_CACHE_TTL_S = 600
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"

_MONTHS_RU = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
    "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}
_EXCEL_EPOCH = date(1899, 12, 30)


@dataclass
class DebtPoint:
    date: date
    value: float


class MinfinFormatError(ValueError):
    """Файл Минфина пришёл, но нужной строки/шапки в нём нет — смена формата."""


# ── разбор файлов ──────────────────────────────────────────────────────────────

def _num(raw) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    # «12 405,77³» — ячейка ФНБ со сноской (апрель и октябрь 2020): знак сноски отбрасывается.
    text = str(raw).rstrip("¹²³⁴⁵⁶⁷⁸⁹⁰*").replace("\xa0", "").replace(" ", "").replace(",", ".").replace("−", "-")
    try:
        return float(text)
    except ValueError:
        return None


def _next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _nwf_month(raw) -> date | None:
    """Шапка столбца ФНБ → первый день месяца («Январь 2008¹» или дата)."""
    if isinstance(raw, datetime):
        return date(raw.year, raw.month, 1)
    if isinstance(raw, date):
        return date(raw.year, raw.month, 1)
    m = re.match(r"\s*([А-Яа-яЁё]+)\s+(\d{4})", str(raw or ""))
    if m and m.group(1).lower() in _MONTHS_RU:
        return date(int(m.group(2)), _MONTHS_RU[m.group(1).lower()], 1)
    return None


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def parse_nwf(content: bytes, row: str) -> list[DebtPoint]:
    """``Dannye_*.xlsx`` → точки на 1-е число месяца (значение «на конец» предыдущего месяца)."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        rows = [list(r) for r in wb[wb.sheetnames[0]].iter_rows(values_only=True)]
    finally:
        wb.close()
    header = next((r for r in rows if len(r) > 2 and _norm(r[1]) == "показатель"), None)
    if header is None:
        raise MinfinFormatError("ФНБ: нет строки «Показатель»")
    columns = [(i, m) for i, m in ((i, _nwf_month(v)) for i, v in enumerate(header)) if m]

    def find(prefix: str) -> list:
        for r in rows:
            if len(r) > 1 and _norm(r[1]).startswith(prefix):
                return r
        raise MinfinFormatError(f"ФНБ: нет строки «{prefix}»")

    total = find("объем на конец периода")
    pick = {
        "total": (total, None, 1.0),
        "usd": (find("объем средств фонда на конец периода (млрд. долларов"), None, 1.0),
        "gdp": (find("в т.ч. в процентах к ввп"), None, 100.0),
        "liquid": (total, find("размещено в иные разрешенные активы"), 1.0),
    }
    if row not in pick:
        raise ValueError(f"ФНБ: неизвестная строка {row!r}")
    main, minus, scale = pick[row]
    out: dict[date, float] = {}
    for i, month in columns:
        value = _num(main[i]) if i < len(main) else None
        if value is None:
            continue
        if minus is not None:
            other = _num(minus[i]) if i < len(minus) else None
            if other is None:
                continue
            value -= other
        value *= scale
        if value <= 0:
            continue
        out[_next_month(month)] = round(value, 3)
    return [DebtPoint(d, v) for d, v in sorted(out.items())]


def _xls_date(raw) -> date | None:
    if isinstance(raw, (int, float)) and 20000 < raw < 80000:
        return _EXCEL_EPOCH + timedelta(days=int(raw))
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", str(raw or ""))
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def parse_domestic(content: bytes) -> list[DebtPoint]:
    """``Obem_gosdolga_s_garantiyami*.xls`` → внутренний долг на 1-е число, млрд руб."""
    import xlrd

    book = xlrd.open_workbook(file_contents=content)
    out: dict[date, float] = {}
    for sheet in book.sheets():
        dates: list[tuple[int, date]] = []
        for r in range(sheet.nrows):
            values = sheet.row_values(r)
            label = _norm(values[0] if values else "")
            # Шапка дат — строка без подписи: суммы долга с 2023 года (20–37 тыс. млрд) попадают в диапазон чисел
            # дат Excel, поэтому строку с подписью датами не считаем.
            if not label:
                found = [(c, d) for c, d in ((c, _xls_date(v)) for c, v in enumerate(values)) if d]
                if len(found) >= 2:
                    dates = found
                continue
            if dates and "внутренн" in label and "всего" in label:
                for c, d in dates:
                    value = _num(values[c]) if c < len(values) else None
                    if value is not None and value > 0:
                        out[d] = round(value, 3)
                break
    if not out:
        raise MinfinFormatError("внутренний долг: ни одной точки (нет строки «… — всего» или дат)")
    return [DebtPoint(d, v) for d, v in sorted(out.items())]


def parse_external(content: bytes) -> list[DebtPoint]:
    """``GVD_*.xlsx`` → внешний долг на 1-е число, млрд долларов (в файле — млн)."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        rows = [list(r) for r in wb[wb.sheetnames[0]].iter_rows(values_only=True)]
    finally:
        wb.close()
    out: dict[date, float] = {}
    for r in rows:
        if len(r) < 3 or not isinstance(r[1], (datetime, date)):
            continue
        value = _num(r[2])
        if value is not None and value > 0:
            out[date(r[1].year, r[1].month, r[1].day)] = round(value / 1000, 3)
    if not out:
        raise MinfinFormatError("внешний долг: ни одной строки с датой")
    return [DebtPoint(d, v) for d, v in sorted(out.items())]


def parse_series(code: str, content: bytes) -> list[DebtPoint]:
    series = SERIES_BY_CODE[code]
    if series.source == "nwf":
        return parse_nwf(content, series.row)
    if series.source == "domestic":
        return parse_domestic(content)
    return parse_external(content)


# ── доставка файла ─────────────────────────────────────────────────────────────

def latest_link(html: str, source: Source) -> str | None:
    """Самая свежая ссылка на файл на странице (по году/месяцу в пути загрузки, затем по имени)."""
    links = sorted(set(re.findall(source.link_re, html)))
    return SITE + links[-1] if links else None


_lock = threading.Lock()
_cache: dict[str, tuple[float, bytes, str, str | None]] = {}


def _download(source: Source) -> tuple[bytes, str]:
    from app.services.http_client import create_session

    session = create_session()
    try:
        session.headers["User-Agent"] = _UA
        page = session.get(source.page, timeout=30)
        page.raise_for_status()
        url = latest_link(page.text, source)
        if not url:
            raise MinfinFormatError(f"на странице {source.page} нет ссылки на файл")
        r = session.get(url, timeout=60)
        r.raise_for_status()
        return r.content, url
    finally:
        session.close()


def fetch_source(source_key: str) -> tuple[bytes, str, str | None]:
    """→ (содержимое, адрес, ошибка живого пути или None). Снимок — если живой путь не ответил."""
    source = SOURCES[source_key]
    with _lock:
        hit = _cache.get(source_key)
        if hit and time.monotonic() - hit[0] < _CACHE_TTL_S:
            return hit[1], hit[2], hit[3]
        try:
            content, url = _download(source)
            error = None
        except Exception as exc:  # noqa: BLE001 — любая сетевая беда ведёт к снимку
            snapshot = SNAPSHOT_DIR / source.snapshot
            if not snapshot.is_file():
                raise
            logger.warning("Minfin %s: живой путь не ответил (%s), снимок %s", source_key, exc, snapshot.name)
            content, url, error = snapshot.read_bytes(), f"{ARTIFACT_URL_PREFIX}{snapshot.name}", (
                f"{type(exc).__name__}: {exc}"[:300])
        _cache[source_key] = (time.monotonic(), content, url, error)
        return content, url, error


def clear_cache() -> None:
    with _lock:
        _cache.clear()


class MinfinDebtParser(BaseParser):
    parser_type: ClassVar[str] = "minfin_debt_xlsx"

    async def _fetch_and_parse(
        self, db: AsyncSession, indicator: Indicator, cfg: dict, fetch_log: FetchLog,
    ) -> tuple[list, str]:
        code = str(cfg.get("minfin_series") or indicator.code)
        if code not in SERIES_BY_CODE:
            fetch_log.error_message = f"minfin_debt_xlsx: неизвестный ряд {code!r}"
            return [], ""
        source_key = SERIES_BY_CODE[code].source
        content, url, error = await asyncio.to_thread(fetch_source, source_key)
        points = await asyncio.to_thread(parse_series, code, content)
        if error is not None:
            last = points[-1].date if points else None
            mark_fallback_used(
                fetch_log,
                f"Minfin live source unavailable ({error[:200]}); snapshot {SOURCES[source_key].snapshot} "
                f"used, covers to {last}",
            )
        return points, url

    def _validate(self, points: list, cfg: dict) -> list:
        return validate_points(points, cfg)
