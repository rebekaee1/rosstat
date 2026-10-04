"""Общие блоки серверных страниц года (Россия, мир, регионы).

Годовые лендинги раньше собирали «Итоги» маркированным списком, а таблицу
значений выводили целиком (у дневной ставки — 256 строк подряд). Здесь живёт
единый вид: плитки итогов, короткий вводный абзац, таблица с раскрывающимся
остатком и числа одного формата (один и тот же знак после запятой во всех
ячейках страницы). Данные и подписи не придумываются — их передаёт рендерер.

Намеренно нет средней точки и внутренних терминов (ряд, срез, точка): текст читает
обычный человек. Язык берётся из ``get_locale()``.
"""

from __future__ import annotations

import re
from datetime import date
from html import escape
from typing import Iterable, Sequence

from app.services.locale import get_locale

NBSP = " "
# Единицы короткие настолько, что их уместно повторять в каждой ячейке.
_SHORT_CELL_UNITS = frozenset({"%", "п.п.", "pp", "p.p.", "п. п."})

# Сколько строк таблицы видно сразу и с какого размера прячем остаток.
TABLE_SHOWN_ROWS = 12
TABLE_COLLAPSE_ABOVE = 20


def _en() -> bool:
    return get_locale() == "en"


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    """Русское склонение числительного: 1 значение, 2 значения, 5 значений."""
    n = abs(int(n))
    if 11 <= n % 100 <= 14:
        return many
    last = n % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def values_word(n: int) -> str:
    """«256 значений» / «1 value» — число вместе со словом."""
    if _en():
        return f"{n} value" if n == 1 else f"{n} values"
    return f"{n} {plural_ru(n, 'значение', 'значения', 'значений')}"


def _decimals_needed(value: float, cap: int) -> int:
    text = f"{abs(float(value)):.{cap}f}".rstrip("0")
    tail = text.split(".", 1)[1] if "." in text else ""
    return len(tail)


def common_decimals(values: Iterable[float | None]) -> int:
    """Одно число знаков после запятой для всей страницы.

    16 и 17,54 на одной странице превращаются в «16,00» и «17,54»: человек
    сравнивает числа глазами по столбцу, а «16» рядом с «14,25» выглядит как
    ошибка. Большие значения (от тысячи) не получают больше двух знаков.
    """
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return 0
    cap = 2 if max(abs(v) for v in nums) >= 1000 else 4
    return max(_decimals_needed(v, cap) for v in nums)


def decimals_in(text: str | None, *, cap: int = 2) -> int:
    """Сколько знаков после запятой в готовой строке («17,54 %» → 2).

    Главное число страницы (среднее за год) уже отформатировано; плитки и
    таблица подстраиваются под него, чтобы «17,54 %» стояло рядом с «16,00 %».
    """
    sep = r"\." if _en() else ","
    match = re.search(rf"\d{sep}(\d+)", text or "")
    return min(len(match.group(1)), cap) if match else 0


def format_fixed(
    value: float | None,
    decimals: int,
    *,
    signed: bool = False,
) -> str:
    """Число с фиксированным числом знаков, в стиле языка страницы.

    RU: ``17 624,30`` (узкий неразрывный пробел, запятая); EN: ``17,624.30``.
    Минус типографский (−).
    """
    if value is None:
        return "no data" if _en() else "нет данных"
    number = round(float(value), decimals)
    negative = number < 0
    text = f"{abs(number):,.{decimals}f}"
    if not _en():
        text = text.replace(",", " ").replace(".", ",")
    if negative:
        return f"−{text}"
    if signed and number > 0:
        return f"+{text}"
    return text


def cell_unit(unit: str | None, *, cpi_mode: bool = False) -> str:
    """Единица для ячеек таблицы: только короткая («%»); длинные — в шапке."""
    if cpi_mode:
        return "%"
    clean = (unit or "").strip()
    return clean if clean in _SHORT_CELL_UNITS else ""


def with_unit(number_text: str, unit: str = "") -> str:
    """«17,54 %» с неразрывным пробелом: число не отрывается от единицы."""
    return f"{number_text}{NBSP}{unit}" if unit else number_text


def year_lead(
    *,
    n_rows: int,
    year: int,
    source: str,
    current_year: bool = False,
    last_date_text: str = "",
    annual: bool = False,
) -> str:
    """Короткий человеческий абзац под заголовком вместо пересказа заголовка."""
    en = _en()
    if n_rows <= 1:
        if current_year and last_date_text:
            body = (
                f"Latest value, {last_date_text}." if en
                else f"Последнее значение на {last_date_text}."
            )
        elif annual:
            body = f"Annual value for {year}." if en else f"Значение за {year} год."
        else:
            body = (
                f"The value published for {year}." if en
                else f"Значение, опубликованное за {year} год."
            )
    elif current_year and last_date_text:
        body = (
            f"{values_word(n_rows)} since the start of {year}, the latest is dated {last_date_text}."
            if en
            else f"{values_word(n_rows)} с начала {year} года, последнее — на {last_date_text}."
        )
    else:
        body = (
            f"{values_word(n_rows)} for {year}." if en
            else f"{values_word(n_rows)} за {year} год."
        )
    src = f" Source: {source}." if en else f" Источник: {source}."
    return body + (src if source else "")


def chart_caption(year: int) -> str:
    """Подпись под картинкой: картинка — карточка, которой можно поделиться."""
    if _en():
        return f"Chart for {year}. Save the picture and send it to a friend."
    return f"График за {year} год. Картинку можно сохранить и отправить."


def year_tiles(items: Sequence[tuple[str, str, str, str]]) -> str:
    """Плитки итогов: (подпись, число, единица, примечание-дата)."""
    cells = []
    for label, number, unit, note in items:
        unit_html = f'<small class="seo-tile-unit">{escape(unit)}</small>' if unit else ""
        note_html = f'<small class="seo-tile-note">{escape(note)}</small>' if note else ""
        cells.append(
            '<div class="seo-tile">'
            f"<span>{escape(label)}</span>"
            f"<b>{escape(number)}{(NBSP + unit_html) if unit_html else ''}</b>"
            f"{note_html}</div>"
        )
    return f'<div class="seo-tiles seo-year-tiles">{"".join(cells)}</div>'


def year_facts(lines: Iterable[str]) -> str:
    """Короткие факты (изменение к прошлому году, место в истории) карточками."""
    items = "".join(f"<li>{escape(line)}</li>" for line in lines if line)
    return f'<ul class="seo-facts">{items}</ul>' if items else ""


def _table(rows: Sequence[tuple], head_date: str, head_value: str) -> str:
    body = []
    for row in rows:
        label, text = row[0], row[1]
        bold = len(row) > 2 and row[2]
        if bold:
            body.append(
                f"<tr><td><strong>{escape(label)}</strong></td>"
                f"<td><strong>{escape(text)}</strong></td></tr>"
            )
        else:
            body.append(f"<tr><td>{escape(label)}</td><td>{escape(text)}</td></tr>")
    return (
        f"<table><thead><tr><th>{escape(head_date)}</th><th>{escape(head_value)}</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def year_values_table(
    rows: Sequence[tuple],
    *,
    head_date: str,
    head_value: str,
    shown: int = TABLE_SHOWN_ROWS,
    collapse_above: int = TABLE_COLLAPSE_ABOVE,
) -> str:
    """Таблица значений: до 20 строк целиком, иначе 12 и «показать остальные».

    Остаток остаётся в разметке (внутри ``<details>``): поисковик видит все
    значения, человек не листает 256 одинаковых строк. Строка — кортеж
    ``(подпись, текст[, выделить])``.
    """
    wrap_open = '<div class="seo-table-scroll" tabindex="0">'
    if len(rows) <= collapse_above:
        return f"{wrap_open}{_table(rows, head_date, head_value)}</div>"
    head, rest = rows[:shown], rows[shown:]
    more = len(rest)
    summary = (
        f"Show {values_word(more)} more" if _en()
        else f"Показать ещё {values_word(more)}"
    )
    return (
        f"{wrap_open}{_table(head, head_date, head_value)}</div>"
        f'<details class="seo-more"><summary>{escape(summary)}</summary>'
        f"{wrap_open}{_table(rest, head_date, head_value)}</div></details>"
    )


def extreme_dates(
    dated_values: Sequence[tuple[date, float]],
) -> tuple[tuple[date, float], tuple[date, float]]:
    """(минимум, максимум) вместе с первой датой, когда значение достигнуто."""
    low = min(dated_values, key=lambda pair: pair[1])
    high = max(dated_values, key=lambda pair: pair[1])
    return low, high


def collapsible_note(summary: str, text: str) -> str:
    """Пояснение для тех, кому нужно: свёрнуто, но остаётся в разметке."""
    if not text:
        return ""
    return (
        f'<details class="seo-more seo-note-more"><summary>{escape(summary)}</summary>'
        f"<p>{escape(text)}</p></details>"
    )
