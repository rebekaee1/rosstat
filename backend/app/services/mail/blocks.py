"""Блоки выпуска рассылки (14.11.2026): «Число недели», обычный блок, прогноз, таблица,
календарь — по заданию редактора (`.artifacts/newsletter-editorial-2026-11-14/новые-блоки.md`),
утверждённому координатором.

Правила вида — принципы владельца: без рамок (блоки — светлый слой и отступы), золото —
линия под шапкой и короткая черта у «Числа недели», у прогноза — маленькая золотая точка;
в прогнозе только одно число (никаких диапазонов — проверка в ``validate_block``);
мини-график — ячейки таблицы, а не картинка. Цифры — моноширинные (tabular-nums).
"""
from __future__ import annotations

import re
from datetime import date
from html import escape

from app.services.mail.templates import (
    ARROW, BLUE, BLUE_DEEP, DELTA, FONT, GOLD, HAIRLINE, INK, LAYER, LAYER_PERSONAL, MUTED, TEXT,
)

NUM = "font-variant-numeric:tabular-nums;font-feature-settings:'tnum' 1;"
TYPES = ("lead", "story", "forecast", "table", "calendar", "section")
RANGE_FIELDS = {"lower", "upper", "range", "min", "max", "interval", "ci", "low", "high"}
_RANGE_RE = re.compile(r"\d[\d\s .,]*\s*[–—-]\s*[−-]?\d|(?<!\w)от\s.+\sдо\s|(?<!\w)from\s.+\sto\s", re.I)
LABELS = {
    "ru": {"source": "Источник", "last": "Последнее значение", "chart": "График", "open": "Открыть график",
           "open_cal": "Весь календарь",
           "lead": "Число недели", "more": "Ещё на этой неделе", "calendar": "Что выйдет дальше"},
    "en": {"source": "Source", "last": "Last value", "chart": "Chart", "open": "Open the chart",
           "open_cal": "Full calendar",
           "lead": "Number of the week", "more": "Also this week", "calendar": "Dates ahead"},
}


class BlockError(ValueError):
    pass


def _l(locale: str, key: str) -> str:
    return LABELS["en" if locale == "en" else "ru"][key]


def validate_block(b: dict) -> None:
    """Проверка блока при разборе выпуска; ошибка — понятной фразой для редактора."""
    kind = b.get("type")
    if kind not in TYPES:
        raise BlockError(f"неизвестный тип блока: {kind!r}")
    if not str(b.get("title") or "").strip() and kind != "calendar":
        raise BlockError(f"{kind}: нужен title")
    if kind == "forecast":
        bad = RANGE_FIELDS & set(b)
        if bad or _RANGE_RE.search(str(b.get("value") or "")):
            raise BlockError("в прогнозе только одно число (правило владельца № 8): уберите диапазон")
    if kind == "lead" and b.get("bars"):
        pts = b["bars"].get("points") or []
        if not 2 <= len(pts) <= 16 or not all(isinstance(p, list) and len(p) == 2 for p in pts):
            raise BlockError("lead.bars.points: от 2 до 16 пар [подпись, число]")
    if kind == "table":
        cols, rows = b.get("columns") or [], b.get("rows") or []
        if not 1 <= len(cols) <= 3 or len(rows) > 8 or any(len(r) != len(cols) for r in rows):
            raise BlockError("table: до 3 колонок, до 8 строк, в каждой строке столько ячеек, сколько колонок")


# --- общие части --------------------------------------------------------------

def _kicker(text: str) -> str:
    if not text:
        return ""
    # Верхний регистр строкой, а не CSS: почта может выкинуть text-transform.
    return (f'<div style="margin:0 0 8px;font-family:{FONT};font-size:11px;line-height:1.2;font-weight:700;'
            f'color:{MUTED};">{escape(text.upper())}</div>')


def _title(text: str, url: str, size: float = 16) -> str:
    inner = escape(text)
    if url:
        inner = (f'<a href="{escape(url, quote=True)}" target="_blank" style="color:{INK};text-decoration:none;">'
                 f'{inner}</a>')
    return (f'<div style="font-family:{FONT};font-size:{size}px;font-weight:600;line-height:1.38;color:{INK};">'
            f'{inner}</div>')


def _text(text: str) -> str:
    if not text:
        return ""
    return (f'<div style="margin-top:6px;font-family:{FONT};font-size:14px;line-height:1.58;color:{TEXT};">'
            f'{rich(text)}</div>')


def _why(text: str) -> str:
    """«Почему этот блок вам» (персональный выпуск): 12 px, приглушённо, под источником."""
    if not text:
        return ""
    return (f'<div style="margin-top:6px;font-family:{FONT};font-size:12px;line-height:1.45;color:{MUTED};">'
            f'{escape(text)}</div>')


def _source(text: str, locale: str) -> str:
    if not text:
        return ""
    return (f'<div style="margin-top:8px;font-family:{FONT};font-size:12px;line-height:1.4;color:{MUTED};">'
            f'{escape(_l(locale, "source"))}: {escape(text)}</div>')


def _link(inner: str, url: str, color: str = INK) -> str:
    """Обёртка-ссылка без подчёркивания: число, график и заголовок блока ведут на одну страницу."""
    if not url:
        return inner
    return (f'<a href="{escape(url, quote=True)}" target="_blank" style="color:{color};text-decoration:none;">'
            f'{inner}</a>')


def _open(url: str, locale: str, key: str = "open") -> str:
    """Явная ссылка действия под блоком: на телефоне по ней попадают пальцем."""
    if not url:
        return ""
    return (f'<div style="margin-top:12px;font-family:{FONT};font-size:13px;line-height:1.3;font-weight:600;">'
            f'<a href="{escape(url, quote=True)}" target="_blank" style="color:{BLUE};text-decoration:none;">'
            f'{escape(_l(locale, key))}&nbsp;&rarr;</a></div>')


_BOLD_RE = re.compile(
    r"(?<![\w,.])([−+\-]?\d[\d\u00a0\u202f ]*(?:[.,]\d+)?[\u00a0\u202f ]?(?:%|₽|\$|€|п\.[\u00a0 ]?п\.|pp\b))")


def rich(text: str) -> str:
    """Текст письма с выделенными числами: «74,72 ₽», «6,3 %», «$92.14» — полужирным графитом, чтобы
    абзац читался по числам. Только числа со знаком единицы; даты и годы не выделяются."""
    out = escape(text)
    out = re.sub(r"(\$\d[\d,]*(?:\.\d+)?)", rf'<b style="font-weight:600;color:{INK};">\1</b>', out)
    return _BOLD_RE.sub(rf'<b style="font-weight:600;color:{INK};">\1</b>', out)


def _meta(source: str, why: str, locale: str) -> str:
    """Служебная строка блока: источник и (в личном блоке) причина — одной приглушённой строкой."""
    parts = []
    if source:
        parts.append(f'{escape(_l(locale, "source"))}: {escape(source)}')
    if why:
        parts.append(escape(why.rstrip(".")))
    if not parts:
        return ""
    return (f'<div style="margin-top:9px;font-family:{FONT};font-size:12px;line-height:1.45;color:{MUTED};">'
            + " &nbsp;·&nbsp; ".join(parts) + "</div>")


def _why_shown(b: dict) -> str:
    """Причина блока в служебной строке — только если её не сказала рубрика («Вы скачивали» уже причина)."""
    return "" if b.get("kicker") else str(b.get("why") or "")


def _delta(b: dict) -> str:
    """Изменение к прошлому периоду: стрелка и число отдельной строкой сразу под заголовком."""
    if not b.get("delta"):
        return ""
    arrow = {"up": "▲", "down": "▼"}.get(b.get("delta_dir") or "", "")
    mark = f'<span style="color:{ARROW};">{arrow}</span>&nbsp;' if arrow else ""
    return (f'<div style="margin-top:6px;font-family:{FONT};font-size:13.5px;line-height:1.4;font-weight:600;'
            f'color:{DELTA};{NUM}">{mark}{escape(str(b["delta"]).replace(chr(0x202f), chr(0xa0)))}</div>')


def _layer(inner: str, personal: bool = False) -> str:
    bg = LAYER_PERSONAL if personal else LAYER
    return ('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
            f'bgcolor="{bg}" style="margin:0 0 16px;background:{bg};border-radius:16px;">'
            f'<tr><td style="padding:22px 24px;">{inner}</td></tr></table>')


def chapter(index: int, title: str, text: str = "", *, rule: bool | None = None) -> str:
    """Глава письма: номер, название, строка пояснения. Между главами — воздух и линия-свет."""
    with_rule, rule = (index > 1 if rule is None else rule), ""
    if with_rule:
        rule = ('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
                'style="margin:28px 0 24px;"><tr>'
                f'<td height="1" bgcolor="{HAIRLINE}" style="height:1px;line-height:1px;font-size:1px;'
                f'background:{HAIRLINE};">&nbsp;</td></tr></table>')
    note = (f'<div style="margin-top:5px;font-family:{FONT};font-size:14px;line-height:1.55;color:{TEXT};">'
            f'{escape(text)}</div>') if text else ""
    return (rule + '<div style="margin:0 0 16px;">'
            f'<div style="font-family:{FONT};font-size:11px;line-height:1.2;font-weight:700;color:{BLUE};{NUM}">'
            f'{index:02d}</div>'
            f'<div style="margin-top:5px;font-family:{FONT};font-size:19px;font-weight:700;letter-spacing:-.01em;'
            f'line-height:1.3;color:{INK};">{escape(title)}</div>{note}</div>')


def _with_value(head: str, rest: str, value_html: str, mobile_html: str = "") -> str:
    """Заголовок и текст слева, крупное число справа. На телефоне число встаёт сразу под
    заголовок: правая ячейка прячется, а копия под заголовком показывается. Копия скрыта
    встроенным стилем, поэтому почта, которая вырезает медиазапросы, покажет число один раз."""
    if not value_html:
        return head + rest
    mobile = (f'<div class="fe-val-m" style="display:none;max-height:0;overflow:hidden;mso-hide:all;">'
              f'<div style="padding-top:8px;">{mobile_html or value_html}</div></div>')
    return ('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
            f'<td valign="top">{head}{mobile}{rest}</td>'
            f'<td class="fe-val" valign="top" align="right" style="padding:0 0 0 24px;white-space:nowrap;">'
            f'{value_html}</td></tr></table>')


_NUM_RE = re.compile(r"^([−+\-]?\d[\d\s\u00a0\u202f.,]*)(.*)$")
_SHORT_UNITS = {"%", "₽", "$", "€", "£", "¥"}


def split_value(value: str) -> tuple[str, str]:
    """«614,3 млрд руб.» → («614,3», «млрд руб.»): число читается одним взглядом, единица — подписью.
    Знак валюты и процента остаётся при числе; в числе тысячи разделены обычным неразрывным пробелом
    (узкий пробел в жирном начертании не виден, и «16 949,24» сливается в «16949,24»)."""
    v = (value or "").strip()
    m = _NUM_RE.match(v)
    if not m:
        return v, ""
    num, unit = m.group(1).rstrip(), m.group(2).strip()
    if not unit or unit in _SHORT_UNITS:
        return v.replace("\u202f", "\u00a0"), ""
    return num.replace("\u202f", "\u00a0").replace(" ", "\u00a0"), unit


def _spark(points: list, align: str = "right") -> str:
    """Мини-график блока: до 8 последних значений столбиками, последний — синий. Ячейки таблицы, не картинка."""
    try:
        vals = [float(v) for v in (points or [])][-8:]
    except (TypeError, ValueError):
        return ""
    if len(vals) < 4:
        return ""
    lo, hi = min(vals), max(vals)
    cells = []
    for i, v in enumerate(vals):
        h = 12 if hi == lo else round(4 + 20 * (v - lo) / (hi - lo))
        color = BLUE if i == len(vals) - 1 else "#C9D3E2"
        cells.append(f'<td valign="bottom" style="padding:0 0 0 3px;height:24px;line-height:1px;font-size:1px;">'
                     f'<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>'
                     f'<td width="6" height="{h}" bgcolor="{color}" style="width:6px;height:{h}px;line-height:{h}px;'
                     f'font-size:1px;background:{color};border-radius:2px 2px 0 0;">&nbsp;</td></tr></table></td>')
    return (f'<table role="presentation" align="{align}" cellspacing="0" cellpadding="0" border="0" '
            f'style="margin-top:10px;"><tr>{"".join(cells)}</tr></table>')


def _value(value: str, color: str = INK, dot: bool = False, spark: list | None = None, align: str = "right",
           url: str = "") -> str:
    if not value:
        return ""
    num, unit = split_value(value)
    mark = (f'<span style="display:inline-block;width:6px;height:6px;border-radius:3px;background:{GOLD};'
            'vertical-align:middle;margin:0 8px 5px 0;"></span>') if dot else ""
    unit_html = (f'<div style="margin-top:4px;font-family:{FONT};font-size:12px;line-height:1.3;font-weight:600;'
                 f'color:{MUTED};">{escape(unit)}</div>') if unit else ""
    return (f'<div style="font-family:{FONT};font-size:26px;font-weight:700;line-height:1.1;'
            f'color:{color};white-space:nowrap;{NUM}">{mark}{_link(escape(num), url, color)}</div>{unit_html}'
            + (_link(_spark(spark, align), url) if spark else ""))


# --- блоки --------------------------------------------------------------------

def _bars(bars: dict) -> str:
    pts = [(str(p[0]), float(p[1])) for p in bars.get("points") or []]
    if len(pts) < 2:
        return ""
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    heights = [32 if hi == lo else round(8 + 56 * (v - lo) / (hi - lo)) for v in vals]
    last_label = bars.get("last_label") or ""
    cells = []
    for i, ((_label, v), h) in enumerate(zip(pts, heights)):
        last = i == len(pts) - 1
        color = BLUE if last else "#C9D3E2"
        top = (f'<div style="font-family:{FONT};font-size:12px;font-weight:700;color:{INK};line-height:1;'
               f'padding-bottom:5px;white-space:nowrap;{NUM}">{escape(last_label or _fmt_num(v))}</div>') if last else ""
        cells.append(
            f'<td valign="bottom" align="center" style="padding:0 2px;height:84px;">{top}'
            '<table role="presentation" width="62%" cellspacing="0" cellpadding="0" border="0" '
            f'style="margin:0 auto;"><tr><td height="{h}" bgcolor="{color}" style="height:{h}px;line-height:{h}px;'
            f'font-size:1px;background:{color};border-radius:3px 3px 0 0;">&nbsp;</td></tr></table></td>')
    first_l, last_l = pts[0][0], pts[-1][0]
    unit = bars.get("unit") or ""
    caption = (f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
               f'<td style="font-family:{FONT};font-size:11px;color:{MUTED};padding-top:6px;">{escape(first_l)}</td>'
               f'<td align="center" style="font-family:{FONT};font-size:11px;color:{MUTED};padding-top:6px;">{escape(unit)}</td>'
               f'<td align="right" style="font-family:{FONT};font-size:11px;color:{MUTED};padding-top:6px;">{escape(last_l)}</td>'
               '</tr></table>')
    return ('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
            'style="margin-top:18px;table-layout:fixed;"><tr>' + "".join(cells) + "</tr></table>" + caption)


def _fmt_num(v: float) -> str:
    text = f"{v:,.2f}".rstrip("0").rstrip(".")
    return text.replace(",", " ").replace(".", ",")


def lead(b: dict, locale: str, *, kicker: bool = True) -> str:
    delta = _delta(b)
    value = (f'<div class="fe-lead-num" style="font-family:{FONT};font-size:46px;font-weight:700;letter-spacing:-.03em;'
             f'line-height:1.04;color:{INK};white-space:nowrap;{NUM}">'
             f'{_link(escape(b.get("value") or ""), b.get("url") or "")}</div>')
    gold = (f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:16px 0 14px;">'
            f'<tr><td width="30" height="2" bgcolor="{GOLD}" style="width:30px;height:2px;line-height:2px;'
            f'font-size:2px;background:{GOLD};">&nbsp;</td></tr></table>')
    return ('<div style="margin:6px 0 4px;">' + (_kicker(b.get("kicker") or "") if kicker else "") + value + delta
            + gold + _title(b["title"], b.get("url") or "", 17) + _text(b.get("text") or "")
            + _meta(b.get("source") or "", b.get("why") or "", locale)
            + (_link(_bars(b["bars"]), b.get("url") or "") if b.get("bars") else "")
            + _open(b.get("url") or "", locale) + "</div>")


def story(b: dict, locale: str) -> str:
    head = _kicker(b.get("kicker") or "") + _title(b["title"], b.get("url") or "")
    url = b.get("url") or ""
    rest = (_delta(b) + _text(b.get("text") or "") + _meta(b.get("source") or "", _why_shown(b), locale)
            + _open(url, locale))
    return _layer(_with_value(head, rest, _value(b.get("value") or "", spark=b.get("spark"), url=url),
                              _value(b.get("value") or "", url=url)), personal=bool(b.get("why")))


def forecast(b: dict, locale: str) -> str:
    last = ""
    if b.get("last_actual"):
        last = (f'<div style="margin-top:4px;font-family:{FONT};font-size:13px;color:{MUTED};{NUM}">'
                f'{escape(_l(locale, "last"))}: {escape(b["last_actual"])}</div>')
    head = _kicker(b.get("kicker") or "") + _title(b["title"], b.get("url") or "")
    url = b.get("url") or ""
    rest = (last + _text(b.get("text") or "") + _meta(b.get("source") or "", _why_shown(b), locale)
            + _open(url, locale))
    return _layer(_with_value(head, rest, _value(b.get("value") or "", BLUE_DEEP, dot=True, url=url)),
                  personal=bool(b.get("why")))


def table(b: dict, locale: str) -> str:
    cols, rows = b.get("columns") or [], b.get("rows") or []
    head = "".join(
        f'<td align="{"left" if i == 0 else "right"}" style="padding:0 10px 8px;font-family:{FONT};font-size:11px;'
        f'font-weight:600;color:{MUTED};">{escape(str(c))}</td>' for i, c in enumerate(cols))
    body = []
    urls = b.get("row_urls") or []
    for n, r in enumerate(rows):
        bg = LAYER if n % 2 == 0 else "#FFFFFF"
        link = urls[n] if n < len(urls) else ""
        tds = "".join(
            f'<td class="fe-td" align="{"left" if i == 0 else "right"}" style="padding:9px 10px;font-family:{FONT};font-size:14px;'
            f'line-height:1.35;color:{INK};{"" if i == 0 else "white-space:nowrap;" + NUM}'
            f'{"border-radius:10px 0 0 10px;" if i == 0 else ""}{"border-radius:0 10px 10px 0;" if i == len(r) - 1 else ""}">'
            f'{_link(escape(str(c).replace(chr(0x202f), chr(0xa0))), link if i == 0 else "")}</td>'
            for i, c in enumerate(r))
        body.append(f'<tr style="background:{bg};" bgcolor="{bg}">{tds}</tr>')
    tbl = ('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;">'
           f'<tr>{head}</tr>' + "".join(body) + "</table>")
    return ('<div style="margin:6px 0 22px;">' + _kicker(b.get("kicker") or "") + _title(b["title"], b.get("url") or "")
            + tbl + _meta(b.get("source") or "", _why_shown(b), locale) + "</div>")


def calendar(b: dict, locale: str, today: date | None = None, *, bare: bool = False) -> str:
    rows = []
    for e in visible_entries(b, today):
        when = escape(str(e.get("date") or ""))
        if e.get("time"):
            when += (f'<div style="font-family:{FONT};font-size:12px;font-weight:400;color:{MUTED};margin-top:2px;">'
                     f'{escape(str(e["time"]))}</div>')
        rows.append(
            f'<tr><td valign="top" width="118" style="width:118px;padding:0 14px 12px 0;font-family:{FONT};'
            f'font-size:14px;font-weight:700;color:{INK};white-space:nowrap;">{when}</td>'
            f'<td valign="top" style="padding:0 0 12px;font-family:{FONT};font-size:14px;line-height:1.5;color:{TEXT};">'
            f'{escape(str(e.get("title") or ""))}</td></tr>')
    if not rows:
        return ""
    head = "" if bare else _kicker(b.get("kicker") or "") + _title(b.get("title") or "", b.get("url") or "")
    return (f'<div style="margin:{"0 0 10px" if bare else "10px 0 18px"};">' + head
            + '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
            + f'style="margin-top:{0 if bare else 12}px;">' + "".join(rows) + "</table>"
            + _open(b.get("url") or "", locale, "open_cal") + "</div>")


def visible_entries(b: dict, today: date | None) -> list[dict]:
    """Строки календаря без прошедших дат: письмо, ушедшее позже, не покажет прошлое будущим."""
    out = []
    for e in b.get("entries") or []:
        iso = e.get("date_iso")
        if iso and today is not None:
            try:
                if date.fromisoformat(iso) < today:
                    continue
            except ValueError:
                pass
        out.append(e)
    return out


def section(b: dict, locale: str) -> str:
    """Заголовок раздела выпуска («Для вас»): без подложки, крупнее заголовка блока."""
    text = (f'<div style="margin-top:4px;font-family:{FONT};font-size:14px;line-height:1.55;color:{TEXT};">'
            f'{escape(b["text"])}</div>') if b.get("text") else ""
    return (f'<div style="margin:22px 0 12px;"><div style="font-family:{FONT};font-size:19px;font-weight:700;'
            f'letter-spacing:-.01em;line-height:1.3;color:{INK};">{escape(b["title"])}</div>{text}</div>')


def render(b: dict, locale: str, today: date | None = None) -> str:
    kind = b.get("type")
    if kind == "section":
        return section(b, locale)
    if kind == "calendar":
        return calendar(b, locale, today)
    return {"lead": lead, "story": story, "forecast": forecast, "table": table}[kind](b, locale)


def _chapters(blocks: list[dict], locale: str, today: date | None, started: bool = False):
    """Порядок повествования выпуска: (номер главы | None, название, пояснение, блок | None).

    Главы: «Число недели» (блок lead) → «Для вас» (блок section и личные блоки — у них есть поле
    `why`) → «Ещё на этой неделе» (остальные блоки редакции) → «Что выйдет дальше» (календарь).
    Выпуск без lead и section (старый формат) идёт без глав.
    """
    n = 0
    group = None
    for b in blocks:
        kind = b.get("type")
        if kind == "lead":
            n += 1
            yield n, str(b.get("kicker") or _l(locale, "lead")), "", None
            yield None, "", "", b
            group = "lead"
        elif kind == "section":
            n += 1
            yield n, str(b.get("title") or ""), str(b.get("text") or ""), None
            group = "personal"
        elif kind == "calendar":
            if not visible_entries(b, today):
                continue
            if n or started:
                n += 1
                yield n, str(b.get("title") or _l(locale, "calendar")), "", None
            yield None, "", "", b
            group = "calendar"
        else:
            if not b.get("why") and group != "editorial" and (n or started):
                n += 1
                yield n, _l(locale, "more"), "", None
            if not b.get("why"):
                group = "editorial"
            yield None, "", "", b


def render_all(blocks: list[dict], locale: str, today: date | None = None, *, after_cover: bool = False) -> str:
    """Все блоки выпуска с главами — единственный путь вёрстки тела письма рассылки.
    `after_cover` — блоки после обложки (число недели уже показано): главы идут с 01."""
    out = []
    chaptered = False
    for index, title, text, b in _chapters(blocks, locale, today, after_cover):
        if b is None:
            out.append(chapter(index, title, text, rule=True if after_cover else None))
            chaptered = True
        elif b.get("type") == "lead":
            out.append(lead(b, locale, kicker=not chaptered))
        elif b.get("type") == "calendar":
            out.append(calendar(b, locale, today, bare=chaptered))
        else:
            out.append(render(b, locale, today))
    return "".join(out)


def text_all(blocks: list[dict], locale: str, today: date | None = None, *, after_cover: bool = False) -> list[str]:
    """То же повествование простым текстом: название главы заглавными, затем блоки."""
    out = []
    for index, title, text, b in _chapters(blocks, locale, today, after_cover):
        if b is None:
            out.append("\n".join(x for x in (f"{index:02d} · {title.upper()}", text) if x))
        elif b.get("type") == "section":
            continue
        else:
            t = as_text(b, locale, today)
            if t:
                out.append(t)
    return out


def as_text(b: dict, locale: str, today: date | None = None) -> str:
    """Блок простым текстом (вторая часть письма и почтовые программы без HTML)."""
    kind = b.get("type")
    lines = []
    if b.get("kicker"):
        lines.append(str(b["kicker"]).upper())
    if kind == "calendar":
        lines.append(str(b.get("title") or ""))
        for e in visible_entries(b, today):
            when = str(e.get("date") or "") + (f", {e['time']}" if e.get("time") else "")
            lines.append(f"{when} — {e.get('title') or ''}")
    elif kind == "table":
        lines.append(str(b["title"]))
        lines.append(str(b.get("text") or "; ".join(" ".join(map(str, r)) for r in b.get("rows") or [])))
    else:
        head = str(b["title"]) + (f" — {b['value']}" if b.get("value") else "")
        lines.append(head)
        if b.get("delta"):
            lines.append(str(b["delta"]))
        if b.get("last_actual"):
            lines.append(f"{_l(locale, 'last')}: {b['last_actual']}")
        if b.get("text"):
            lines.append(str(b["text"]))
        if b.get("bars"):
            pts = b["bars"].get("points") or []
            if pts:
                lines.append(f"{_l(locale, 'chart')}: " + " → ".join(_fmt_num(float(p[1])) for p in pts)
                             + f" {b['bars'].get('unit') or ''} ({pts[0][0]} — {pts[-1][0]})")
    if kind == "section":
        return "\n".join(x for x in (str(b.get("title") or "").upper(), str(b.get("text") or "")) if x)
    if b.get("source"):
        lines.append(f"{_l(locale, 'source')}: {b['source']}")
    if b.get("why"):
        lines.append(str(b["why"]))
    if b.get("url"):
        lines.append(str(b["url"]))
    return "\n".join(x for x in lines if x)
