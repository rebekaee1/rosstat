"""Общая рамка выгрузки таблицы-сетки (CSV / Excel) для сравнения, рейтинга, таблицы
региона и графика платежей: POST /export/grid (круг 11, 2026-10-09).

В отличие от /export/table (один ряд «дата — значение — факт/прогноз») здесь колонки и
строки произвольны. Принимаются только ТОЧЕЧНЫЕ значения: полей `lower` / `upper`
(границ интервала прогноза) не существует ни в колонках, ни в строках (принцип 8).
Файл строится в рабочем потоке (render_export_async); файл нигде не хранится.
"""
from __future__ import annotations

import csv
import io
import re

from app.services.display import format_number_ru

FORBIDDEN_KEYS = frozenset({"lower", "upper"})
MAX_COLUMNS = 60
MAX_ROWS = 50_000
MAX_CELLS = 500_000
MAX_TEXT = 500

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
_NUMERIC_TEXT = re.compile(r"^[+-]?\d+([.,]\d+)?$")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def safe_text(value: str) -> str:
    """Текстовая ячейка без управляющих символов; формулы Excel/Sheets не исполняются.

    Строка, начинающаяся с = + - @, получает ведущий апостроф (как делает сам Excel),
    кроме обычных чисел с знаком («-5,2»)."""
    text = _CTRL.sub(" ", value)[:MAX_TEXT]
    if text.startswith(_FORMULA_START) and not _NUMERIC_TEXT.match(text):
        return "'" + text
    return text


def header_label(label: str, unit: str | None) -> str:
    base = safe_text(label)
    return f"{base}, {safe_text(unit)}" if unit else base


def _labels(locale: str) -> dict[str, str]:
    if locale == "en":
        return {"title": "Table", "source": "Source", "source_url": "Source URL", "country": "Country",
                "frequency": "Frequency", "provenance": "Calculation", "note": "Note",
                "exported_at": "Exported at", "default_source": "Not specified", "sheet": "Data",
                "description": "Description"}
    return {"title": "Таблица", "source": "Источник", "source_url": "URL источника", "country": "Страна",
            "frequency": "Частота", "provenance": "Расчёт", "note": "Примечание",
            "exported_at": "Дата выгрузки", "default_source": "Не указан", "sheet": "Данные",
            "description": "Описание"}


def meta_rows(title: str, meta: dict[str, str], exported_at: str, locale: str) -> list[tuple[str, str]]:
    lab = _labels(locale)
    rows = [(lab["title"], safe_text(title))]
    for key in ("country", "frequency"):
        if meta.get(key):
            rows.append((lab[key], safe_text(meta[key])))
    rows.append((lab["source"], safe_text(meta.get("source") or lab["default_source"])))
    for key in ("provenance", "note", "source_url"):
        if meta.get(key):
            rows.append((lab[key], safe_text(meta[key])))
    rows.append((lab["exported_at"], exported_at))
    return rows


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def build_csv(title, columns, rows, meta, exported_at: str, locale: str) -> bytes:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\n")
    for label, value in meta_rows(title, meta, exported_at, locale):
        w.writerow([f"# {label}", value])
    w.writerow([header_label(c["label"], c.get("unit")) for c in columns])
    for row in rows:
        cells = []
        for c in columns:
            v = row.get(c["key"])
            if v is None:
                cells.append("")
            elif _is_number(v):
                cells.append(format_number_ru(v, locale=locale))
            else:
                cells.append(safe_text(str(v)))
        w.writerow(cells)
    return ("﻿" + out.getvalue()).encode("utf-8")


def build_xlsx(title, columns, rows, meta, exported_at: str, locale: str) -> bytes:
    from openpyxl import Workbook

    lab = _labels(locale)
    wb = Workbook()
    ws_meta = wb.active
    ws_meta.title = lab["description"]
    for label, value in meta_rows(title, meta, exported_at, locale):
        ws_meta.append([label, value])
    ws = wb.create_sheet(lab["sheet"], 1)
    ws.append([header_label(c["label"], c.get("unit")) for c in columns])
    for row in rows:
        cells = []
        for c in columns:
            v = row.get(c["key"])
            # Числа хранятся нативно (Excel считает по ним); текст — без формул.
            cells.append(v if (v is None or _is_number(v)) else safe_text(str(v)))
        ws.append(cells)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
