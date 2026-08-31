"""Per-indicator OG-превью (PNG 1200×630) — постерный тёмный рендер.

Раздаётся как `https://forecasteconomy.com/og/{code}.png` (nginx → backend
`/api/v1/og-image/indicator/{code}.png`). Подключается в SSR через
`build_document(og_image=...)` — у каждой карточки своё превью в соцсетях,
мессенджерах и выдаче вместо одной общей картинки.

Дизайн «J6» (утверждён владельцем 2026-08-22): тёмный градиентный фон,
гигантское число с градиентом и тенью, золотая пилюля контекста, широкая
лента динамики с неон-линией. Палитра проверена по WCAG-контрасту
(текст >= 4.5:1, крупный текст >= 3:1). Гарнитура — Golos Text (OFL),
кириллический дисплей; Inter остаётся фолбэком.

Форматы чисел/дат двуязычны: локаль берётся из контекста запроса
(`get_locale()` из `app.services.locale`, ставится middleware) либо задаётся
keyword-only `locale=`. Тёмный постер локализуется автоматически; пять
легаси светлых рендеров ниже оставляют русский текст дефолтом своих
параметров — вызывающая сторона может переопределить под EN.

Рендер — Pillow, чистая функция от данных; кэш in-process + диск (TTL 1 ч),
ключи формируют вызывающие.
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import random
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1200, 630

# --- палитра J6 (контраст выверен аудит-скриптом) ---
DARK0 = (15, 16, 32)
DARK1 = (26, 27, 50)
GOLD = (212, 175, 90)
GOLD_BRIGHT = (232, 200, 122)
GOLD_SOFT = (216, 190, 128)
IVORY = (250, 251, 255)
MUT = (168, 172, 196)
AXIS_TXT = (146, 152, 182)
PILL_TEXT = (28, 22, 10)

_LEGACY_BG = (248, 249, 252)
TEXT_PRIMARY = (26, 26, 46)
CHAMPAGNE = (184, 148, 47)
# Легаси-константы светлых карточек (рейтинги регионов/стран, today-хаб,
# сравнение регионов, страны мира) — до их перевода на тёмный постер.
BG = _LEGACY_BG
TEXT_SECONDARY = (26, 26, 46, 166)
TEXT_TERTIARY = (26, 26, 46, 120)

RU_MONTH_NOM = ("январь", "февраль", "март", "апрель", "май", "июнь",
                "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь")
RU_MONTH_DAT = ("январю", "февралю", "марту", "апрелю", "маю", "июню",
                "июлю", "августу", "сентябрю", "октябрю", "ноябрю", "декабрю")

# EN-месяцы локально (короткие для оси «Aug 2024», полные для заголовков
# «July 2026»); display._EN_MONTHS_NOM приватен и содержит пустой 0-й элемент.
EN_MONTH_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
EN_MONTHS_NOM = ("January", "February", "March", "April", "May", "June",
                 "July", "August", "September", "October", "November",
                 "December")


def _effective_locale(locale: str | None) -> str:
    """None → локаль запроса (contextvar); иначе переданное значение."""
    if locale is None:
        from app.services.locale import get_locale

        return get_locale()
    return locale


def fmt_ru(v: float, *, locale: str | None = None) -> str:
    loc = _effective_locale(locale)
    s = f"{v:.1f}" if abs(v) >= 10 else f"{v:.2f}"
    if loc == "en":
        return s
    return s.replace(".", ",")


def fmt_signed(v: float, *, locale: str | None = None) -> str:
    # U+2212 остаётся и в EN: Golos Text его рисует, для экономиста
    # типографский минус читабельнее дефиса.
    sign = "+" if v >= 0 else "\u2212"
    return f"{sign}{fmt_ru(abs(v), locale=locale)}"


def fmt_yoy(v: float, *, locale: str | None = None) -> str:
    """Годовая инфляция: всегда один знак («6,0» RU / «6.0» EN), не «6,00».

    Не делегировать в fmt_ru — у него 2 знака для abs(v) < 10.
    Отрицательные (дефляция) — с типографским минусом U+2212, не дефисом.
    """
    s = f"{abs(v):.1f}"
    if _effective_locale(locale) != "en":
        s = s.replace(".", ",")
    return f"\u2212{s}" if v < 0 else s


RU_MONTH_SHORT = ("янв", "фев", "мар", "апр", "мая", "июн",
                  "июл", "авг", "сен", "окт", "ноя", "дек")


def window_x_labels(first_date, last_date, *, locale: str | None = None) -> tuple[str, str]:
    """Крайние подписи окна графика: «авг 2024 — июл 2026» / «Aug 2024 — Jul 2026»."""
    if _effective_locale(locale) == "en":
        return (f"{EN_MONTH_SHORT[first_date.month - 1]} {first_date.year}",
                f"{EN_MONTH_SHORT[last_date.month - 1]} {last_date.year}")
    a = f"{RU_MONTH_SHORT[first_date.month - 1]} {first_date.year}"
    b = f"{RU_MONTH_SHORT[last_date.month - 1]} {last_date.year}"
    return a, b


def ru_period_lines(last_date, prev_date=None,
                    *, locale: str | None = None) -> tuple[str, str | None]:
    """«Июль 2026» + «к июню 2026» / «July 2026» + «to June 2026».

    Имя историческое (зовут из sitemap.py); функция двуязычна.
    """
    if _effective_locale(locale) == "en":
        period = f"{EN_MONTHS_NOM[last_date.month - 1]} {last_date.year}"
        compare = None
        if prev_date is not None:
            compare = f"to {EN_MONTHS_NOM[prev_date.month - 1]} {prev_date.year}"
        return period, compare
    period = f"{RU_MONTH_NOM[last_date.month - 1].capitalize()} {last_date.year}"
    compare = None
    if prev_date is not None:
        compare = f"к {RU_MONTH_DAT[prev_date.month - 1]} {prev_date.year}"
    return period, compare

_FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"
_GOLOS_PATH = _FONT_DIR / "GolosText-Variable.ttf"
_FONT_PATH = _FONT_DIR / "Inter-Variable.ttf"

_CACHE: dict[str, tuple[float, bytes]] = {}
_CACHE_TTL = 3600.0
_CACHE_MAX = 600


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(_FONT_PATH), size)
    try:
        font.set_variation_by_axes([14.0, 700 if bold else 400])
    except OSError:
        pass
    return font


def FG(size: int, wght: int = 400) -> ImageFont.FreeTypeFont:
    """Golos Text variable: вес 400–900."""
    f = ImageFont.truetype(str(_GOLOS_PATH), size)
    try:
        f.set_variation_by_axes([wght])
    except OSError:
        pass
    return f


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:2]


def _wrap_fit_lines(
    text: str,
    size: int,
    wght: int,
    max_width: int,
    min_size: int,
) -> tuple[list[str], int]:
    """Перенос заголовка на 2 строки с автоподбором кегля под ширину полосы.

    Сначала пробуется полный размер и обычный перенос; если хоть одна строка
    не влезает — кегль уменьшается до тех пор, пока перенесённые строки не
    станут короче max_width (floor — min_size). Гарантирует, что и перенос,
    и каждая строка переноса умещаются в полосу.
    """
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    size = max(int(size), min_size)
    while True:
        font = FG(size, wght)
        lines = _wrap_text(probe, text, font, max_width)
        if all(probe.textlength(line, font=font) <= max_width for line in lines) \
                or size <= min_size:
            return lines, size
        size -= 2


def _split_value_lines(value_text: str) -> tuple[str, str | None]:
    """Число отдельно от словесной единицы: «13 149,8 тысяч человек» →
    («13 149,8», «тысяч человек»). Разрез по последнему пробелу, слева от
    которого стоит чисто числовая часть (цифры, пробелы-разряды, разделитель,
    знак); «+0,54 %» остаётся одной строкой."""
    if "%" in value_text or not value_text:
        return value_text, None
    stripped = value_text.strip()
    for i in range(len(stripped) - 1, 0, -1):
        if stripped[i] != " ":
            continue
        left = stripped[:i]
        compact = left.replace("\u202f", "").replace("\u00a0", "").replace(" ", "")
        if compact and all(c.isdigit() or c in ",.+-−" for c in compact):
            return left, stripped[i + 1:]
    return stripped, None


def _fit_font_size(
    text: str,
    size: int,
    wght: int,
    max_width: int,
    min_size: int,
) -> int:
    """Максимальный кегль (Golos, вес wght), при котором text ≤ max_width."""
    size = max(int(size), min_size)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    while probe.textlength(text, font=FG(size, wght)) > max_width and size > min_size:
        size -= 2
    return size


def _fit_text_width(text: str, size: int, wght: int, max_width: int) -> str:
    """Пиксельная обрезка с многоточием на подобранном кегле (последний рубеж)."""
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    font = FG(size, wght)
    if probe.textlength(text, font=font) <= max_width:
        return text
    while text and probe.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def _fmt_axis(v: float, *, locale: str | None = None) -> str:
    """Компактная подпись значения для оси (RU «1 234,5 / 12,5 млн», EN «1,234.5 / 12.5M»)."""
    av = abs(v)
    if _effective_locale(locale) == "en":
        if av >= 1_000_000:
            return f"{v / 1_000_000:.1f}M"
        if av >= 1_000:
            return f"{v:,.0f}"
        if av >= 10:
            return f"{v:.0f}"
        return f"{v:.2f}"
    if av >= 1_000_000:
        s = f"{v / 1_000_000:.1f} млн"
    elif av >= 1_000:
        s = f"{v:,.0f}".replace(",", " ")
    elif av >= 10:
        s = f"{v:.0f}"
    else:
        s = f"{v:.2f}"
    return s.replace(".", ",")


# ---------------------------------------------------------------- J6 helpers

def _bg_rgba() -> Image.Image:
    g = np.linspace(0, 1, HEIGHT)[:, None]
    arr = np.zeros((HEIGHT, WIDTH, 3), dtype=np.float32)
    for i, (a, b) in enumerate(zip(DARK0, DARK1)):
        arr[:, :, i] = a + (b - a) * g
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    dist = np.sqrt(((xx - WIDTH * 0.10) / WIDTH) ** 2 + ((yy - HEIGHT * 0.02) / HEIGHT * 1.45) ** 2)
    glow = np.clip(1 - dist, 0, 1) ** 2.4 * 34
    arr += np.stack([glow * 1.35, glow * 1.05, glow * 0.45], axis=2)
    rng = np.random.default_rng(11)
    arr += rng.normal(0, 1.6, (HEIGHT, WIDTH, 1))
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGB").convert("RGBA")


def _spline(pts: list[tuple[float, float]], steps: int = 10) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    n = len(pts)
    for i in range(n - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
        for ti in range(steps):
            t = ti / steps
            t2 = t * t
            t3 = t2 * t
            x = .5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = .5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def _draw_poster_chart(
    img: Image.Image,
    values: list[float],
    box: tuple[int, int, int, int],
    last_label: str,
    *,
    badge_rect: tuple[float, float, float, float] | None = None,
    peak_label: str | None = None,
) -> None:
    """Лента динамики J6: градиентная заливка, неон-линия, шкала, экстремумы,
    бейдж последней точки у правого края."""
    x0, y0, x1, y1 = box
    vmin, vmax = min(values), max(values)
    pad = ((vmax - vmin) or 1) * .24
    lo, hi = vmin - pad, vmax + pad
    rngv = hi - lo
    n = len(values)
    pts = [(x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * (v - lo) / rngv) for i, v in enumerate(values)]
    sm = _spline(pts)

    poly_mask = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(poly_mask).polygon(sm + [(sm[-1][0], y1 + 2), (sm[0][0], y1 + 2)], fill=85)
    gh = y1 - y0 + 1
    ga = np.zeros((gh, WIDTH, 4), dtype=np.uint8)
    fade = np.tile(np.linspace(1, 0, gh)[:, None], (1, WIDTH))
    for i, c in enumerate(GOLD):
        ga[:, :, i] = (c * fade).astype(np.uint8)
    ga[:, :, 3] = (fade * 84).astype(np.uint8)
    grad_full = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    grad_full.paste(Image.fromarray(ga, "RGBA"), (0, y0))
    img.paste(grad_full, (0, 0), poly_mask)

    glow_l = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(glow_l).line(sm, fill=GOLD + (150,), width=12, joint="curve")
    img.alpha_composite(glow_l.filter(ImageFilter.GaussianBlur(9)))
    img.alpha_composite(glow_l.filter(ImageFilter.GaussianBlur(3)))

    d = ImageDraw.Draw(img, "RGBA")
    if lo < 0 < hi:
        zy = y1 - (y1 - y0) * (0 - lo) / rngv
        for i in range(int(x0), int(x1), 14):
            d.line([(i, zy), (i + 7, zy)], fill=(255, 255, 255, 40), width=1)
    d.line(sm, fill=GOLD_BRIGHT + (255,), width=4, joint="curve")

    rf = FG(14, 600)
    d.text((x0 + 10, y0 + 4), _fmt_axis(hi), font=rf, fill=AXIS_TXT)
    d.text((x0 + 10, y1 - 24), _fmt_axis(lo), font=rf, fill=AXIS_TXT)

    imax, imin = values.index(max(values)), values.index(min(values))
    mxf, myf = pts[imax]
    mnf, mynf = pts[imin]
    lx, ly = pts[-1]
    d.ellipse([mnf - 5, mynf - 5, mnf + 5, mynf + 5], fill=(190, 194, 214, 255))

    # бейдж последней точки — у правого края на высоте точки. Размер и
    # геометрия приходят из _layout_badge (badge_rect): кегль подобран под
    # текст, ширина пилюли = ширина текста + паддинг, правый край прижат к x1.
    if badge_rect is None:
        badge_rect = _layout_badge(last_label, int(x1 - x0) - 24)
    bf = FG(badge_rect[4], 800)
    bw = d.textlength(last_label, font=bf)
    pad = 14
    bx = x1 - bw - pad
    by = min(max(ly - 22, y0 + 2), y1 - badge_rect[5] - 6)
    d.rounded_rectangle([bx - pad, by - 6, bx + bw + pad, by + badge_rect[5]],
                        radius=10, fill=(10, 11, 24, 240), outline=GOLD + (200,), width=2)
    d.text((bx, by), last_label, font=bf, fill=IVORY)

    # подпись пика — над пиком; при риске пересечь бейдж уводим левее/выше
    peak_txt = peak_label or _fmt_axis(max(values))
    pf2 = FG(badge_rect[6], 700)
    pw = d.textlength(peak_txt, font=pf2)
    txm = min(max(mxf - pw / 2, x0 + 2), x1 - pw - 2)
    tym = myf - 32
    if txm + pw > bx - 20 and myf - 32 < by + 46 and tym + 24 > by - 6:
        tym = min(tym, by - 34)
        txm = min(txm, bx - pw - 24)
    tym = max(y0 + 2, tym)
    d.text((txm, tym), peak_txt, font=pf2, fill=(244, 236, 214))
    d.ellipse([mxf - 6, myf - 6, mxf + 6, myf + 6], outline=GOLD + (220,), width=2)
    d.ellipse([lx - 12, ly - 12, lx + 12, ly + 12], outline=GOLD + (110,), width=3)
    d.ellipse([lx - 6, ly - 6, lx + 6, ly + 6], fill=GOLD_BRIGHT)


def _draw_big_number(img: Image.Image, xy: tuple[int, int], text: str, size: int) -> tuple[int, int, int, int]:
    """Гигантское число с вертикальным градиентом и тенью-подложкой."""
    f = FG(size, 800)
    tmp = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(tmp).text(xy, text, font=f, fill=255)
    bb = tmp.getbbox()
    sh_a = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    sh_a[:, :, 0], sh_a[:, :, 1], sh_a[:, :, 2] = 6, 7, 16
    sh_a[:, :, 3] = (np.asarray(tmp.filter(ImageFilter.GaussianBlur(14)), dtype=np.float32) * 0.85).astype(np.uint8)
    img.alpha_composite(Image.fromarray(sh_a, "RGBA"), (-4, 10))
    gh_ = bb[3] - bb[1]
    ga = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    for i, (a, b) in enumerate(zip((252, 253, 255), (244, 220, 158))):
        col = np.tile(np.linspace(a, b, gh_)[:, None], (1, WIDTH))
        ga[bb[1]:bb[3], :, i] = col.astype(np.uint8)
    ga[:, :, 3] = tmp
    img.alpha_composite(Image.fromarray(ga, "RGBA"))
    return bb


def render_indicator_og(
    *,
    code: str,
    name: str,
    value_text: str,
    date_text: str,
    values: list[float],
    period_text: str | None = None,
    x_labels: tuple[str, str] | None = None,
    context_pill: str | None = None,
    subtitle: str | None = None,
    unit_suffix: str | None = None,
) -> bytes:
    """Постер J6: гигантское значение + контекстная пилюля + лента динамики.

    Чистая функция от данных — кэш на вызывающей стороне. `context_pill` —
    золотая пилюля справа от числа (например «Годовая инфляция — 6,0%»);
    `subtitle` — строка под заголовком (что показывает ряд); `period_text` —
    метка периода у бренда («2025 год» для годовых лендингов); `x_labels` —
    крайние подписи периода под лентой динамики.

    Все тексты проходят через `_layout` (автоподбор кегля): значение с длинной
    словесной единицей переносится на вторую строку, заголовок ужимается,
    бейдж последней точки растёт по ширине текста — обрезаний у краёв нет.
    """
    L = _layout_indicator(
        name=name,
        value_text=value_text,
        date_text=date_text,
        subtitle=subtitle,
        context_pill=context_pill,
        unit_suffix=unit_suffix,
        period_text=period_text,
    )
    margin = 56
    img = _bg_rgba()
    draw = ImageDraw.Draw(img, "RGBA")

    # шапка: бренд — источник/период
    draw.text((margin, 42), "F O R E C A S T   E C O N O M Y", font=FG(17, 700), fill=GOLD_BRIGHT)
    right_txt = period_text or date_text or ""
    if right_txt:
        sf = FG(16, 600)
        rw = draw.textlength(right_txt, font=sf)
        draw.text((WIDTH - margin - rw, 44), right_txt, font=sf, fill=MUT)

    # заголовок (до 2 строк, кегль подобран под полосу) + подзаголовок
    nf = FG(L["title_size"], 800)
    ty = 94
    for line in L["title_lines"]:
        draw.text((margin, ty), line, font=nf, fill=IVORY)
        ty += L["title_line_h"]
    if L["subtitle"]:
        draw.text((margin + 1, ty + 4), L["subtitle"], font=FG(L["subtitle_size"], 500), fill=MUT)

    # гигантское число: одна строка, либо число + единица второй строкой
    num_line, unit_line = L["value_lines"]
    vf = FG(L["value_size"], 800)
    bb = _draw_big_number(img, (margin - 4, 208), num_line, L["value_size"])
    draw = ImageDraw.Draw(img, "RGBA")
    num_w = draw.textlength(num_line, font=vf)
    unit_y = bb[3] - int(L["value_unit_size"] * 1.25)
    if unit_line:
        draw.text((margin - 4, unit_y), unit_line,
                  font=FG(L["value_unit_size"], 700), fill=(206, 210, 230))
        num_w = max(num_w, draw.textlength(unit_line, font=FG(L["value_unit_size"], 700)))

    # правая колонка: период/база (date_text) + пилюля контекста
    px, _ = L["context_pill_xy"]
    if date_text and not period_text:
        df2 = FG(21, 500)
        draw.text((px, bb[1] + 20), date_text, font=df2, fill=MUT)
    if L["context_pill"]:
        pf = FG(L["context_pill_size"], 800)
        pill_w = L["context_pill_w"]
        pill_h = L["context_pill_h"]
        pill_x, pill_y = px, bb[1] + 64
        if pill_x + pill_w > WIDTH - margin:
            pill_x, pill_y = margin, bb[3] + 24
        draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                               radius=28, fill=GOLD + (255,))
        draw.text((pill_x + 26, pill_y + 11), L["context_pill"], font=pf, fill=PILL_TEXT)

    # лента динамики: бейдж последней точки — по ширине текста, без обрезки
    chart_box = (60, 448, WIDTH - 60, 562)
    if len(values) < 2:
        values = (values + [values[-1] if values else 0.0])[:2] or [0.0, 0.0]
    last_label = " ".join(part for part in (num_line, unit_line) if part)
    peak_label = _fmt_axis(max(values[-48:])) if values else None
    badge = _layout_badge(last_label, int(chart_box[2] - chart_box[0]) - 24)
    _draw_poster_chart(img, values[-48:], chart_box, last_label,
                       badge_rect=badge, peak_label=peak_label)
    draw = ImageDraw.Draw(img, "RGBA")
    xf = FG(15, 600)
    if x_labels:
        l1, l2 = x_labels
        draw.text((62, 582), l1, font=xf, fill=AXIS_TXT)
        lw2 = draw.textlength(l2, font=xf)
        draw.text((WIDTH - 62 - lw2, 582), l2, font=xf, fill=AXIS_TXT)
    dom = "forecasteconomy.com"
    df3 = FG(15, 700)
    dw2 = draw.textlength(dom, font=df3)
    draw.text((WIDTH // 2 - dw2 / 2, 582), dom, font=df3, fill=GOLD_SOFT)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _brand_header(draw: ImageDraw.ImageDraw, eyebrow_extra: str | None = None) -> None:
    """Бренд-полоска + eyebrow — общая шапка всех OG-карточек."""
    margin = 64
    draw.rectangle([0, 0, WIDTH, 8], fill=CHAMPAGNE)
    eyebrow_font = _font(26, bold=True)
    eyebrow = "FORECAST ECONOMY"
    draw.text((margin, 44), eyebrow, font=eyebrow_font, fill=CHAMPAGNE)
    if eyebrow_extra:
        ew = draw.textlength(eyebrow, font=eyebrow_font)
        draw.text((margin + ew + 18, 44), f"— {eyebrow_extra}", font=eyebrow_font, fill=TEXT_SECONDARY)


def _brand_footer(draw: ImageDraw.ImageDraw, note: str = "", *, size: int = 26) -> None:
    footer_font = _font(size)
    draw.text((64, HEIGHT - 42), "forecasteconomy.com", font=footer_font, fill=TEXT_TERTIARY)
    if note:
        nw = draw.textlength(note, font=footer_font)
        draw.text((WIDTH - 64 - nw, HEIGHT - 42), note, font=footer_font, fill=TEXT_TERTIARY)


def _layout(
    *,
    name: str = "",
    value_text: str = "",
    date_text: str | None = None,
    subtitle: str | None = None,
    context_pill: str | None = None,
    unit_suffix: str | None = None,
    period_text: str | None = None,
    # rating (render_rating_og / render_world_rating_og)
    rows: list[tuple[str, float]] | None = None,
    total: int = 0,
    unit: str = "",
    order_label: str = "наибольшие значения",
    title_label: str | None = None,
    kind: str = "regions",
    # today hub (render_today_hub_og)
    items: list[tuple[str, str]] | None = None,
    title: str | None = None,
    footer: str = "",
    # region-vs (render_region_vs_og)
    name_a: str = "",
    name_b: str = "",
    vs_rows: list[tuple[str, str, str]] | None = None,
    eyebrow: str = "сравнение регионов",
    # world country (render_world_country_og)
    country: str = "",
    country_title_template: str = "Экономика {country}",
    count_line: str = "",
    # Локализованные тексты подставляет вызывающий рендер готовыми строками:
    # раскладка отвечает за геометрию и влезание, рендер — за слова.
) -> dict:
    """Единая раскладка текстовых блоков OG-постеров: кегль + факты влезания.

    Автоподбор кегля через ImageFont.getlength (шрифт Golos): каждый блок
    получает максимальный размер, при котором текст не шире своей полосы.
    Значение с длинной словесной единицей («13 149,8 тысяч человек») рендерится
    в две строки: число крупным кеглем, единица — вторая строка меньшего
    кегля. Тесты (test_og_fit.py) читают те же словари и замеряют ширины тем
    же шрифтом — расхождение «посчитали/нарисовали» исключено.
    """
    if name_a or name_b or vs_rows is not None:
        return _layout_region_vs(name_a=name_a, name_b=name_b,
                                 rows=vs_rows or [], eyebrow=eyebrow, footer=footer)
    if country or count_line:
        return _layout_world_country(country=country, items=items or [],
                                     count_line=count_line, footer=footer,
                                     title_template=country_title_template)
    if rows is not None:
        return _layout_rating(name=name, rows=rows, total=total, unit=unit,
                              order_label=order_label, title_label=title_label,
                              kind=kind)
    if items is not None or title is not None:
        return _layout_today_hub(items=items or [], title=title or "",
                                 footer=footer)
    return _layout_indicator(name=name, value_text=value_text, date_text=date_text,
                             subtitle=subtitle, context_pill=context_pill,
                             unit_suffix=unit_suffix, period_text=period_text)


def _layout_badge(last_label: str, limit: int) -> tuple[int, int, int, int, int, int, int]:
    """Геометрия бейджа последней точки ленты: (bx, by, bw, bh, size, bh, peak_size).

    bx/by заполняются в _draw_poster_chart (зависят от точки ряда); bw здесь —
    фактическая ширина текста при подобранном кегле. Кегль 23→14: даже самая
    длинная подпись остаётся внутри полосы графика, пилюля растёт по ширине
    текста, а не по лимиту символов.
    """
    pad = 14
    size = _fit_font_size(last_label, 23, 800, max(limit - 2 * pad, 60), 14)
    f = FG(size, 800)
    bw = f.getlength(last_label)
    line_h = int(size * 1.4)
    peak_size = _fit_font_size(_fmt_axis(0.0), 18, 700, max(limit, 80), 12)
    return (0.0, 0.0, bw + 2 * pad, line_h + 8, size, line_h + 8, peak_size)


def _layout_indicator(
    *,
    name: str,
    value_text: str,
    date_text: str | None,
    subtitle: str | None,
    context_pill: str | None,
    unit_suffix: str | None,
    period_text: str | None,
) -> dict:
    margin = 56
    limit = WIDTH - margin - 24  # полоса всех левых блоков постера J6

    value_num, value_unit = _split_value_lines(value_text)
    glyph = unit_suffix or ("%" if "%" in (value_text or "") else None)
    if glyph and "%" not in (value_text or ""):
        value_unit = (value_unit + " " + glyph).strip() if value_unit else glyph
    has_unit_line = value_unit is not None

    if has_unit_line:
        num_size = _fit_font_size(value_num, 200, 800, limit, 110)
        unit_size = _fit_font_size(value_unit, 62, 700, limit, 30)
    else:
        num_size = _fit_font_size(value_text, 200, 800, limit, 110)
        unit_size = 62
    nf = FG(num_size, 800)
    num_w = nf.getlength(value_num if has_unit_line else value_text)

    title_size = 46
    title_lines, title_size = _wrap_fit_lines(name, title_size, 800, limit, 28)

    subtitle_size = 19
    sub_text = subtitle or ""
    if sub_text:
        subtitle_size = _fit_font_size(sub_text, subtitle_size, 500, limit, 12)

    pill_w = pill_h = 0
    pill_size = 26
    pill_xy = (margin, 0)
    if context_pill:
        pill_size = _fit_font_size(context_pill, 26, 800, limit - 52, 16)
        pf = FG(pill_size, 800)
        pill_w = pf.getlength(context_pill) + 52
        pill_h = 56
        # Якорь — правый край числа (или единицы, если она шире). Не влезает
        # справа — пилюля уходит вниз под число, оставаясь в пределах полосы.
        anchor = margin - 4 + max(num_w, pf.getlength(value_unit or "") if value_unit else 0)
        px = anchor + 80
        if px + pill_w > WIDTH - margin:
            px = margin
        pill_xy = (px, 0)

    return {
        "value_lines": (value_num if has_unit_line else value_text, value_unit),
        "value_size": num_size,
        "value_unit_size": unit_size,
        "title_lines": title_lines,
        "title_size": title_size,
        "title_line_h": 56,
        "subtitle": sub_text,
        "subtitle_size": subtitle_size,
        "context_pill": context_pill or "",
        "context_pill_xy": pill_xy,
        "context_pill_w": pill_w,
        "context_pill_h": pill_h,
        "context_pill_size": pill_size,
    }


def _layout_rating(
    *,
    name: str,
    rows: list[tuple[str, float]],
    total: int,
    unit: str,
    order_label: str,
    title_label: str | None,
    count_template: str | None = None,
    kind: str = "regions",
    locale: str | None = None,
) -> dict:
    labels = _rating_labels(locale, kind=kind)
    tl = title_label or labels["title_label"]
    ct = count_template or labels["count_template"]
    limit = WIDTH - 128
    title_lines, title_size = _wrap_fit_lines(f"{name}: {tl}", 44, 700, limit, 24)

    top = rows[:8]
    label_size = 24
    if top:
        label_size = min(
            (_fit_font_size(rn, 24, 400, 330 - 16, 14) for rn, _v in top),
            default=24,
        )
    val_texts = [_fmt_axis(v, locale=locale) for _n, v in top]
    val_size = min((_fit_font_size(t, 24, 700, 380, 14) for t in val_texts), default=24)
    note = f"{order_label} — {ct.format(n=len(top), total=total, scope=labels['scope_word'])}"
    if unit:
        note += f" — {unit}"
    footer_size = _fit_font_size(note, 26, 400, limit, 14)
    return {
        "title_lines": title_lines,
        "title_size": title_size,
        "title_line_h": 52,
        "row_labels": [_fit_text_width(rn, label_size, 400, 330 - 16) for rn, _v in top],
        "label_size": label_size,
        "value_size": val_size,
        "row_values": val_texts,
        "footer_note": note,
        "footer_size": footer_size,
    }


def _layout_today_hub(
    *,
    items: list[tuple[str, str]],
    title: str,
    footer: str,
) -> dict:
    cell_w = (WIDTH - 64 * 2 - 24) // 2
    title_size = _fit_font_size(title, 52, 700, WIDTH - 128, 26)
    label_size = min((_fit_font_size(lbl, 26, 400, cell_w - 40, 13) for lbl, _v in items), default=26)
    val_size = min((_fit_font_size(v, 38, 700, cell_w - 40, 16) for _l, v in items), default=38)
    return {
        "title": title,
        "title_size": title_size,
        "items": items[:6],
        "label_size": label_size,
        "value_size": val_size,
        "cell_w": cell_w,
        "cell_h": 96,
        "footer_note": footer,
        "footer_size": _fit_font_size(footer, 26, 400, WIDTH - 128, 14),
    }


def _layout_region_vs(
    *,
    name_a: str,
    name_b: str,
    rows: list[tuple[str, str, str]],
    eyebrow: str,
    footer: str,
) -> dict:
    limit = WIDTH - 128
    title_lines, title_size = _wrap_fit_lines(f"{name_a} и {name_b}", 46, 700, limit, 24)
    col_w = 260
    metric_limit = 600 - 64 - 24
    head_size = min(_fit_font_size(name_a, 26, 700, col_w, 12),
                    _fit_font_size(name_b, 26, 700, col_w, 12))
    row_size = min((_fit_font_size(m, 25, 400, metric_limit, 12) for m, _a, _b in rows), default=25)
    val_size = min(
        (_fit_font_size(t, 25, 700, col_w, 12) for _m, a, b in rows for t in (a, b)),
        default=25,
    )
    return {
        "title_lines": title_lines,
        "title_size": title_size,
        "title_line_h": 54,
        "head_a": _fit_text_width(name_a, head_size, 700, col_w),
        "head_b": _fit_text_width(name_b, head_size, 700, col_w),
        "head_size": head_size,
        "rows": [
            (_fit_text_width(m, row_size, 400, metric_limit),
             _fit_text_width(a, val_size, 700, col_w),
             _fit_text_width(b, val_size, 700, col_w))
            for m, a, b in rows[:6]
        ],
        "row_size": row_size,
        "value_size": val_size,
        "footer_note": footer,
        "footer_size": _fit_font_size(footer, 26, 400, limit, 14),
        "eyebrow": eyebrow,
    }


def _layout_world_country(
    *,
    country: str,
    items: list[tuple[str, str]],
    count_line: str,
    footer: str,
    title_template: str = "Экономика {country}",
) -> dict:
    limit = WIDTH - 128
    title_lines, title_size = _wrap_fit_lines(
        title_template.format(country=country), 48, 700, limit, 24)
    cell_w = (WIDTH - 64 * 2 - 24) // 2
    label_size = min((_fit_font_size(lbl, 24, 400, cell_w - 40, 12) for lbl, _v in items), default=24)
    val_size = min((_fit_font_size(v, 34, 700, cell_w - 40, 14) for _l, v in items), default=34)
    return {
        "title_lines": title_lines,
        "title_size": title_size,
        "title_line_h": 54,
        "items": items[:6],
        "label_size": label_size,
        "value_size": val_size,
        "count_line": count_line,
        "sub_size": _fit_font_size(count_line, 26, 400, limit, 14),
        "footer_note": footer,
        "footer_size": _fit_font_size(footer, 26, 400, limit, 14),
    }


def _rating_labels(
    locale: str | None,
    *,
    kind: str,
) -> dict[str, str]:
    """Подписи рейтинговых OG-постеров по локали.

    kind="regions" — рейтинг регионов, kind="countries" — рейтинг стран.
    EN-строки — из существующих шаблонов SSR (seo_en.py, _rating_copy),
    ничего нового не изобретается.
    """
    loc = _effective_locale(locale)
    if loc != "en":
        if kind == "countries":
            return {
                "title_label": "рейтинг стран",
                "year_label": "год",
                "scope_word": "стран",
                "count_template": "{n} из {total} {scope}",
            }
        return {
            "title_label": "рейтинг регионов",
            "year_label": "год",
            "scope_word": "регионов",
            "count_template": "{n} из {total} {scope}",
        }
    # EN: готовые формулировки из REGIONAL_TEMPLATES_EN / WORLD_TEMPLATES_EN.
    if kind == "countries":
        return {
            "title_label": "country ranking",
            "year_label": "",
            "scope_word": "countries",
            "count_template": "{n} of {total} {scope}",
        }
    return {
        "title_label": "regional ranking",
        "year_label": "",
        "scope_word": "regions",
        "count_template": "{n} of {total} {scope}",
    }


def _og_year_label(year: int, year_label: str) -> str:
    """Шапка-eyebrow рейтинга: «{year} год» / «{year}» (EN без рус. слова)."""
    return f"{year} {year_label}" if year_label else str(year)


def render_rating_og(
    *,
    name: str,
    year: int,
    unit: str,
    rows: list[tuple[str, float]],
    total: int,
    order_label: str = "наибольшие значения",
    title_label: str | None = None,
    year_label: str | None = None,
    scope_word: str | None = None,
    count_template: str | None = None,
    locale: str | None = None,
) -> bytes:
    """Рейтинг регионов: горизонтальный барчарт топ-8 + бренд (для /region-rating).

    Самодостаточная картинка под Алису/Нейро: заголовок, год, первые строки
    текущего порядка со значениями, счётчик «из N регионов», домен.
    Подписи берутся по локали из _rating_labels; явная передача параметров
    переопределяет словарь (совместимость со старыми вызовами). Имена строк
    и значения — через автоподбор кегля (_layout), без обрезки символами.
    """
    labels = _rating_labels(locale, kind="regions")
    if title_label is None:
        title_label = labels["title_label"]
    if year_label is None:
        year_label = labels["year_label"]
    if scope_word is None:
        scope_word = labels["scope_word"]
    if count_template is None:
        count_template = labels["count_template"]

    L = _layout_rating(
        name=name, rows=rows, total=total, unit=unit,
        order_label=order_label, title_label=title_label,
        count_template=count_template, locale=locale,
    )

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, _og_year_label(year, year_label))

    name_font = _font(L["title_size"], bold=True)
    y = 88
    for line in L["title_lines"]:
        draw.text((margin, y), line, font=name_font, fill=TEXT_PRIMARY)
        y += L["title_line_h"]

    top = rows[:8]
    if top:
        vmax = max(abs(v) for _n, v in top) or 1.0
        bar_font = _font(L["label_size"])
        val_font = _font(L["value_size"], bold=True)
        bar_area_x0 = margin + 330
        bar_area_x1 = WIDTH - margin - 170
        row_y = y + 20
        row_h = (HEIGHT - 70 - row_y) // len(top)
        bar_h = min(30, row_h - 12)
        for i, (region_name, value) in enumerate(top):
            draw.text((margin, row_y + (row_h - 26) // 2),
                      L["row_labels"][i], font=bar_font, fill=TEXT_PRIMARY)
            w = int((bar_area_x1 - bar_area_x0) * abs(value) / vmax)
            by = row_y + (row_h - bar_h) // 2
            draw.rounded_rectangle(
                [bar_area_x0, by, bar_area_x0 + max(w, 6), by + bar_h],
                radius=6, fill=(184, 148, 47, 200),
            )
            draw.text((bar_area_x0 + max(w, 6) + 14, row_y + (row_h - 26) // 2),
                      L["row_values"][i], font=val_font, fill=TEXT_PRIMARY)
            row_y += row_h

    _brand_footer(draw, L["footer_note"], size=L["footer_size"])

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_world_rating_og(
    *,
    name: str,
    year: int,
    unit: str,
    rows: list[tuple[str, float]],
    total: int,
    order_label: str,
    title_label: str | None = None,
    year_label: str | None = None,
    scope_word: str | None = None,
    count_template: str | None = None,
    locale: str | None = None,
) -> bytes:
    """Рейтинг стран: горизонтальный барчарт первых строк текущего порядка.

    Подписи берутся по локали из _rating_labels; явная передача параметров
    переопределяет словарь (совместимость со старыми вызовами). Имена строк
    и значения — через автоподбор кегля (_layout), без обрезки символами.
    """
    labels = _rating_labels(locale, kind="countries")
    if title_label is None:
        title_label = labels["title_label"]
    if year_label is None:
        year_label = labels["year_label"]
    if scope_word is None:
        scope_word = labels["scope_word"]
    if count_template is None:
        count_template = labels["count_template"]

    L = _layout_rating(
        name=name, rows=rows, total=total, unit=unit,
        order_label=order_label, title_label=title_label,
        count_template=count_template, locale=locale,
    )

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, _og_year_label(year, year_label))

    name_font = _font(L["title_size"], bold=True)
    y = 88
    for line in L["title_lines"]:
        draw.text((margin, y), line, font=name_font, fill=TEXT_PRIMARY)
        y += L["title_line_h"]

    top = rows[:8]
    if top:
        vmax = max(abs(v) for _n, v in top) or 1.0
        bar_font = _font(L["label_size"])
        val_font = _font(L["value_size"], bold=True)
        bar_area_x0 = margin + 330
        bar_area_x1 = WIDTH - margin - 170
        row_y = y + 20
        row_h = (HEIGHT - 70 - row_y) // len(top)
        bar_h = min(30, row_h - 12)
        for i, (country_name, value) in enumerate(top):
            draw.text((margin, row_y + (row_h - 26) // 2),
                      L["row_labels"][i], font=bar_font, fill=TEXT_PRIMARY)
            w = int((bar_area_x1 - bar_area_x0) * abs(value) / vmax)
            by = row_y + (row_h - bar_h) // 2
            draw.rounded_rectangle(
                [bar_area_x0, by, bar_area_x0 + max(w, 6), by + bar_h],
                radius=6, fill=(184, 148, 47, 200),
            )
            draw.text((bar_area_x0 + max(w, 6) + 14, row_y + (row_h - 26) // 2),
                      L["row_values"][i], font=val_font, fill=TEXT_PRIMARY)
            row_y += row_h

    _brand_footer(draw, L["footer_note"], size=L["footer_size"])

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_today_hub_og(
    *,
    date_text: str,
    items: list[tuple[str, str]],
    title_label: str | None = None,
    footer_note: str | None = None,
    locale: str | None = None,
) -> bytes:
    """Сводка «Экономика России сегодня»: сетка «показатель → значение» (для /today).

    Лейблы по локали: EN — из today_hub_h1 (TODAY_HUB_H1_EN, тот же заголовок,
    что у SSR-хаба), RU — прежний русский дефолт.
    """
    from app.services.seo_i18n import today_hub_h1

    if title_label is None:
        title_label = today_hub_h1(locale) or (
            "Russia economy today"
            if _effective_locale(locale) == "en"
            else "Экономика России сегодня"
        )
    if footer_note is None:
        footer_note = (
            "official data — updated as sources publish"
            if _effective_locale(locale) == "en"
            else "официальные данные — обновление по мере публикации"
        )

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, date_text)

    L = _layout_today_hub(items=items, title=title_label, footer=footer_note or "")
    title_font = _font(L["title_size"], bold=True)
    draw.text((margin, 96), L["title"], font=title_font, fill=TEXT_PRIMARY)

    # 6 карточек (3 ряда): 4 ряда упирались в футер. cell_h+10 шаг, низ ~508.
    grid = L["items"]
    cols = 2
    cell_w = L["cell_w"]
    cell_h = L["cell_h"]
    top_y = 190
    label_font = _font(L["label_size"])
    value_font = _font(L["value_size"], bold=True)
    for i, (label, value_text) in enumerate(grid):
        cx = margin + (i % cols) * (cell_w + 24)
        cy = top_y + (i // cols) * (cell_h + 10)
        draw.rounded_rectangle([cx, cy, cx + cell_w, cy + cell_h], radius=14,
                               fill=(255, 255, 255), outline=(0, 0, 0, 28), width=1)
        draw.text((cx + 22, cy + 14), label, font=label_font, fill=TEXT_SECONDARY)
        draw.text((cx + 22, cy + 46), value_text, font=value_font, fill=TEXT_PRIMARY)

    _brand_footer(draw, L["footer_note"], size=L["footer_size"])
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """Обрезка по фактической ширине в пикселях (не по символам) с многоточием."""
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def render_region_vs_og(
    *,
    name_a: str,
    name_b: str,
    rows: list[tuple[str, str, str]],
    eyebrow_label: str = "сравнение регионов",
    title_separator: str = " и ",
    footer_note: str = "данные Росстата",
) -> bytes:
    """Сравнение двух регионов: таблица «показатель — A — B» (для /region-vs).

    Колонки не наезжают друг на друга: подписи и значения проходят через
    автоподбор кегля (_layout), при min-кегле остаётся пиксельная обрезка.
    (Единицы измерения компактизирует вызывающая сторона:
    «тысяч человек» → «тыс. чел.».)
    """
    L = _layout_region_vs(
        name_a=name_a, name_b=name_b, rows=rows, footer=footer_note,
        eyebrow=eyebrow_label,
    )

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, eyebrow_label)

    title_font = _font(L["title_size"], bold=True)
    y = 92
    for line in L["title_lines"]:
        draw.text((margin, y), line, font=title_font, fill=TEXT_PRIMARY)
        y += L["title_line_h"]

    col_metric_x = margin
    col_a_x = 600
    col_b_x = 880
    col_w = 260
    head_font = _font(L["head_size"], bold=True)
    y += 14
    draw.text((col_a_x, y), L["head_a"], font=head_font, fill=CHAMPAGNE)
    draw.text((col_b_x, y), L["head_b"], font=head_font, fill=CHAMPAGNE)
    y += 44

    row_font = _font(L["row_size"])
    val_font = _font(L["value_size"], bold=True)
    for metric, va, vb in L["rows"]:
        draw.line([(margin, y - 8), (WIDTH - margin, y - 8)], fill=(0, 0, 0, 22), width=1)
        draw.text((col_metric_x, y), metric, font=row_font, fill=TEXT_SECONDARY)
        draw.text((col_a_x, y), va, font=val_font, fill=TEXT_PRIMARY)
        draw.text((col_b_x, y), vb, font=val_font, fill=TEXT_PRIMARY)
        y += 54

    _brand_footer(draw, L["footer_note"], size=L["footer_size"])
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_world_country_og(
    *,
    country_name: str,
    indicators_count: int,
    items: list[tuple[str, str]],
    eyebrow_label: str = "мировая экономика",
    title_template: str = "Экономика {country}",
    count_template: str = "{count} показателей — Евростат",
    footer_note: str = "официальные данные Евростата",
    locale: str | None = None,
) -> bytes:
    """Сводка страны для /og/world/{slug}.png: сетка ключевых значений.

    Текстовые параметры по умолчанию — русские; EN-вызов передаёт EN-строки
    (sitemap.py) целиком, чтобы не получить смесь языков на постере.
    """
    L = _layout_world_country(
        country=country_name,
        items=items,
        count_line=count_template.format(count=indicators_count),
        footer=footer_note,
        title_template=title_template,
    )

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, eyebrow_label)

    title_font = _font(L["title_size"], bold=True)
    y = 92
    for line in L["title_lines"]:
        draw.text((margin, y), line, font=title_font, fill=TEXT_PRIMARY)
        y += L["title_line_h"]

    sub_font = _font(L["sub_size"])
    draw.text(
        (margin, y + 4),
        L["count_line"],
        font=sub_font,
        fill=TEXT_SECONDARY,
    )

    grid = L["items"]
    cols = 2
    cell_w = (WIDTH - margin * 2 - 24) // cols
    cell_h = 88
    top_y = y + 50
    label_font = _font(L["label_size"])
    value_font = _font(L["value_size"], bold=True)
    for i, (label, value_text) in enumerate(grid):
        cx = margin + (i % cols) * (cell_w + 24)
        cy = top_y + (i // cols) * (cell_h + 10)
        draw.rounded_rectangle(
            [cx, cy, cx + cell_w, cy + cell_h],
            radius=14,
            fill=(255, 255, 255),
            outline=(0, 0, 0, 28),
            width=1,
        )
        draw.text(
            (cx + 22, cy + 12),
            label,
            font=label_font,
            fill=TEXT_SECONDARY,
        )
        draw.text(
            (cx + 22, cy + 44),
            value_text,
            font=value_font,
            fill=TEXT_PRIMARY,
        )

    _brand_footer(draw, L["footer_note"], size=L["footer_size"])
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# П-16: дисковый слой под in-process кэшем. Пространство ключей — десятки
# тысяч (годовые landing'и, 40k региональных страниц); держать всё в памяти
# нельзя (_CACHE_MAX=600), а после рестарта контейнера in-process кэш холодный
# и бот-прожиг снова платит Pillow-рендер за каждую картинку. Диск (docker-том
# og_cache) переживает рестарты и вмещает всё; TTL тот же.
_DISK_DIR = Path(os.environ.get("OG_CACHE_DIR", "")) if os.environ.get("OG_CACHE_DIR") \
    else Path(tempfile.gettempdir()) / "fe-og-cache"


def _disk_path(code: str) -> Path:
    return _DISK_DIR / (hashlib.md5(code.encode()).hexdigest() + ".png")


def cached_og(code: str) -> bytes | None:
    entry = _CACHE.get(code)
    if entry and time.monotonic() - entry[0] < _CACHE_TTL:
        return entry[1]
    try:
        p = _disk_path(code)
        if p.exists() and time.time() - p.stat().st_mtime < _CACHE_TTL:
            png = p.read_bytes()
            _CACHE[code] = (time.monotonic(), png)
            return png
    except OSError:
        pass
    return None


def store_og(code: str, png: bytes) -> None:
    if len(_CACHE) >= _CACHE_MAX:
        oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
        _CACHE.pop(oldest, None)
    _CACHE[code] = (time.monotonic(), png)
    try:
        _DISK_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _disk_path(code).with_suffix(".tmp")
        tmp.write_bytes(png)
        tmp.replace(_disk_path(code))
        # Редкая (≈1/200 записей) уборка протухших файлов, чтобы каталог не рос вечно.
        if random.random() < 0.005:
            cutoff = time.time() - 2 * _CACHE_TTL
            for f in _DISK_DIR.glob("*.png"):
                try:
                    if f.stat().st_mtime < cutoff:
                        f.unlink()
                except OSError:
                    continue
    except OSError:
        logger.debug("OG disk cache write failed for %s", code, exc_info=True)
