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

from app.services.mail.templates import BLUE, BLUE_DEEP, FONT, GOLD, INK, LAYER, MUTED, TEXT

NUM = "font-variant-numeric:tabular-nums;font-feature-settings:'tnum' 1;"
TYPES = ("lead", "story", "forecast", "table", "calendar", "section")
RANGE_FIELDS = {"lower", "upper", "range", "min", "max", "interval", "ci", "low", "high"}
_RANGE_RE = re.compile(r"\d[\d\s .,]*\s*[–—-]\s*[−-]?\d|(?<!\w)от\s.+\sдо\s|(?<!\w)from\s.+\sto\s", re.I)
LABELS = {
    "ru": {"source": "Источник", "last": "Последнее значение", "chart": "График"},
    "en": {"source": "Source", "last": "Last value", "chart": "Chart"},
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
            f'{escape(text)}</div>')


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


def _layer(inner: str) -> str:
    return ('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
            f'style="margin:0 0 12px;background:{LAYER};border-radius:16px;">'
            f'<tr><td style="padding:18px 20px;">{inner}</td></tr></table>')


def _with_value(head: str, rest: str, value_html: str) -> str:
    """Заголовок и текст слева, крупное число справа. На телефоне число встаёт сразу под
    заголовок: правая ячейка прячется, а копия под заголовком показывается. Копия скрыта
    встроенным стилем, поэтому почта, которая вырезает медиазапросы, покажет число один раз."""
    if not value_html:
        return head + rest
    mobile = (f'<div class="fe-val-m" style="display:none;max-height:0;overflow:hidden;mso-hide:all;">'
              f'<div style="padding-top:6px;">{value_html}</div></div>')
    return ('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
            f'<td valign="top">{head}{mobile}{rest}</td>'
            f'<td class="fe-val" valign="top" align="right" style="padding:0 0 0 18px;white-space:nowrap;">'
            f'{value_html}</td></tr></table>')


def _value(value: str, color: str = INK, dot: bool = False) -> str:
    if not value:
        return ""
    mark = (f'<span style="display:inline-block;width:6px;height:6px;border-radius:3px;background:{GOLD};'
            'vertical-align:middle;margin:0 8px 4px 0;"></span>') if dot else ""
    return (f'<div style="font-family:{FONT};font-size:22px;font-weight:700;letter-spacing:-.02em;line-height:1.2;'
            f'color:{color};{NUM}">{mark}{escape(value)}</div>')


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


def lead(b: dict, locale: str) -> str:
    arrow = {"up": "▲", "down": "▼"}.get(b.get("delta_dir") or "", "—")
    delta = ""
    if b.get("delta"):
        delta = (f'<div style="margin-top:8px;font-family:{FONT};font-size:13.5px;font-weight:600;color:#2A3550;{NUM}">'
                 f'<span style="color:#6B7C99;">{arrow}</span>&nbsp;{escape(b["delta"])}</div>')
    value = (f'<div class="fe-lead-num" style="font-family:{FONT};font-size:46px;font-weight:700;letter-spacing:-.03em;'
             f'line-height:1.04;color:{INK};white-space:nowrap;{NUM}">{escape(b.get("value") or "")}</div>')
    gold = (f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:16px 0 14px;">'
            f'<tr><td width="30" height="2" bgcolor="{GOLD}" style="width:30px;height:2px;line-height:2px;'
            f'font-size:2px;background:{GOLD};">&nbsp;</td></tr></table>')
    return ('<div style="margin:6px 0 28px;">' + _kicker(b.get("kicker") or "") + value + delta + gold
            + _title(b["title"], b.get("url") or "", 17) + _text(b.get("text") or "")
            + _source(b.get("source") or "", locale) + _why(b.get("why") or "")
            + (_bars(b["bars"]) if b.get("bars") else "") + "</div>")


def story(b: dict, locale: str) -> str:
    head = _kicker(b.get("kicker") or "") + _title(b["title"], b.get("url") or "")
    rest = _text(b.get("text") or "") + _source(b.get("source") or "", locale) + _why(b.get("why") or "")
    return _layer(_with_value(head, rest, _value(b.get("value") or "")))


def forecast(b: dict, locale: str) -> str:
    last = ""
    if b.get("last_actual"):
        last = (f'<div style="margin-top:4px;font-family:{FONT};font-size:13px;color:{MUTED};{NUM}">'
                f'{escape(_l(locale, "last"))}: {escape(b["last_actual"])}</div>')
    head = _kicker(b.get("kicker") or "") + _title(b["title"], b.get("url") or "")
    rest = last + _text(b.get("text") or "") + _source(b.get("source") or "", locale) + _why(b.get("why") or "")
    return _layer(_with_value(head, rest, _value(b.get("value") or "", BLUE_DEEP, dot=True)))


def table(b: dict, locale: str) -> str:
    cols, rows = b.get("columns") or [], b.get("rows") or []
    head = "".join(
        f'<td align="{"left" if i == 0 else "right"}" style="padding:0 10px 8px;font-family:{FONT};font-size:11px;'
        f'font-weight:600;color:{MUTED};">{escape(str(c))}</td>' for i, c in enumerate(cols))
    body = []
    for n, r in enumerate(rows):
        bg = LAYER if n % 2 == 0 else "#FFFFFF"
        tds = "".join(
            f'<td align="{"left" if i == 0 else "right"}" style="padding:9px 10px;font-family:{FONT};font-size:14px;'
            f'line-height:1.35;color:{INK};{"" if i == 0 else "white-space:nowrap;" + NUM}'
            f'{"border-radius:10px 0 0 10px;" if i == 0 else ""}{"border-radius:0 10px 10px 0;" if i == len(r) - 1 else ""}">'
            f'{escape(str(c))}</td>' for i, c in enumerate(r))
        body.append(f'<tr style="background:{bg};" bgcolor="{bg}">{tds}</tr>')
    tbl = ('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;">'
           f'<tr>{head}</tr>' + "".join(body) + "</table>")
    return ('<div style="margin:6px 0 22px;">' + _kicker(b.get("kicker") or "") + _title(b["title"], b.get("url") or "")
            + tbl + _source(b.get("source") or "", locale) + _why(b.get("why") or "") + "</div>")


def calendar(b: dict, locale: str, today: date | None = None) -> str:
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
    return ('<div style="margin:10px 0 18px;">' + _kicker(b.get("kicker") or "")
            + _title(b.get("title") or "", b.get("url") or "")
            + '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;">'
            + "".join(rows) + "</table></div>")


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
