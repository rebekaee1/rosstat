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

Рендер — Pillow, чистая функция от данных; кэш in-process + диск (TTL 1 ч).
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
LINE = (184, 148, 47)
AREA_FILL = (184, 148, 47, 38)
GRID = (0, 0, 0, 22)
AXIS = (0, 0, 0, 60)
WATERMARK = (26, 26, 46, 34)

RU_MONTH_NOM = ("январь", "февраль", "март", "апрель", "май", "июнь",
                "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь")
RU_MONTH_DAT = ("январю", "февралю", "марту", "апрелю", "маю", "июню",
                "июлю", "августу", "сентябрю", "октябрю", "ноябрю", "декабрю")


def fmt_ru(v: float) -> str:
    s = f"{v:.1f}" if abs(v) >= 10 else f"{v:.2f}"
    return s.replace(".", ",")


def fmt_signed(v: float) -> str:
    sign = "+" if v >= 0 else "\u2212"
    return f"{sign}{fmt_ru(abs(v))}"


def fmt_yoy(v: float) -> str:
    """Годовая инфляция: один знак после запятой («6,0», не «6,00»)."""
    return f"{v:.1f}".replace(".", ",")


RU_MONTH_SHORT = ("янв", "фев", "мар", "апр", "мая", "июн",
                  "июл", "авг", "сен", "окт", "ноя", "дек")


def window_x_labels(first_date, last_date) -> tuple[str, str]:
    """Крайние подписи окна графика: «авг 2024» — «июл 2026»."""
    a = f"{RU_MONTH_SHORT[first_date.month - 1]} {first_date.year}"
    b = f"{RU_MONTH_SHORT[last_date.month - 1]} {last_date.year}"
    return a, b


def ru_period_lines(last_date, prev_date=None) -> tuple[str, str | None]:
    """«Июль 2026» + «к июню 2026» — период и база сравнения для постера."""
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


def _fmt_axis(v: float) -> str:
    """Компактная подпись значения для оси (1 234,5 / 12,3 / 1,2 млн)."""
    av = abs(v)
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
    d.ellipse([mnf - 5, mynf - 5, mnf + 5, mynf + 5], fill=(190, 194, 214, 255))

    # бейдж последней точки — у правого края на высоте точки
    bf = FG(23, 800)
    bw = d.textlength(last_label, font=bf)
    lx, ly = pts[-1]
    bx = x1 - bw - 26
    by = min(max(ly - 22, y0 + 2), y1 - 44)
    d.rounded_rectangle([bx - 14, by - 6, bx + bw + 14, by + 40], radius=10,
                        fill=(10, 11, 24, 240), outline=GOLD + (200,), width=2)
    d.text((bx, by), last_label, font=bf, fill=IVORY)

    # подпись пика — над пиком; при риске пересечь бейдж уводим левее/выше
    peak_txt = _fmt_axis(max(values))
    pf2 = FG(18, 700)
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


def _area_chart(
    draw: ImageDraw.ImageDraw,
    values: list[float],
    box: tuple[int, int, int, int],
    *,
    x_labels: tuple[str, str] | None = None,
) -> None:
    """Area-график «как скачанный PNG»: заливка под линией, горизонтальная сетка
    с подписями значений в левом гаттере и метки периода под осью X.

    Подписи осей рисуются ВНЕ области графика (в гаттерах слева и снизу), поэтому
    не накладываются на линию, сетку и футер. Картинка самодостаточна: Алиса/Нейро
    берут её со страницы и показывают в ответе, где она должна объяснять себя сама
    (значения по оси, период, бренд).
    """
    x0, y0, x1, y1 = box
    if len(values) < 2:
        return
    vmin, vmax = min(values), max(values)
    spread = (vmax - vmin) or 1.0
    # Небольшой запас сверху/снизу, чтобы линия не липла к границам.
    pad = spread * 0.08
    lo, hi = vmin - pad, vmax + pad
    rng = (hi - lo) or 1.0
    n = len(values)
    points = [
        (x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * (v - lo) / rng)
        for i, v in enumerate(values)
    ]

    axis_font = _font(24)
    # Горизонтальная сетка + подписи значений (4 уровня), label справа в гаттере.
    for frac in (0.0, 1 / 3, 2 / 3, 1.0):
        y = y1 - (y1 - y0) * frac
        draw.line([(x0, y), (x1, y)], fill=GRID, width=1)
        tick_val = lo + rng * frac
        label = _fmt_axis(tick_val)
        lw = draw.textlength(label, font=axis_font)
        draw.text((x0 - 14 - lw, y - 13), label, font=axis_font, fill=TEXT_SECONDARY)

    # Ось Y и X — тонкие линии.
    draw.line([(x0, y0), (x0, y1)], fill=AXIS, width=2)
    draw.line([(x0, y1), (x1, y1)], fill=AXIS, width=2)

    # Заливка под линией (area).
    polygon = points + [(points[-1][0], y1), (points[0][0], y1)]
    draw.polygon(polygon, fill=AREA_FILL)

    # Линия + точка последнего значения.
    draw.line(points, fill=LINE, width=5, joint="curve")
    px, py = points[-1]
    draw.ellipse([px - 9, py - 9, px + 9, py + 9], fill=CHAMPAGNE)

    # Метки периода под осью X (крайние даты), в нижнем гаттере.
    if x_labels:
        left, right = x_labels
        draw.text((x0, y1 + 12), left, font=axis_font, fill=TEXT_SECONDARY)
        rw = draw.textlength(right, font=axis_font)
        draw.text((x1 - rw, y1 + 12), right, font=axis_font, fill=TEXT_SECONDARY)


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
    """
    img = _bg_rgba()
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 56

    # шапка: бренд — источник/период
    draw.text((margin, 42), "F O R E C A S T   E C O N O M Y", font=FG(17, 700), fill=GOLD_BRIGHT)
    right_txt = period_text or date_text or ""
    if right_txt:
        sf = FG(16, 600)
        rw = draw.textlength(right_txt, font=sf)
        draw.text((WIDTH - margin - rw, 44), right_txt, font=sf, fill=MUT)

    # заголовок (до 2 строк) + подзаголовок
    nf = FG(46, 800)
    title_lines = _wrap_text(draw, name, nf, WIDTH - margin * 2 - 40)
    ty = 94
    for line in title_lines:
        draw.text((margin, ty), line, font=nf, fill=IVORY)
        ty += 56
    if subtitle:
        draw.text((margin + 1, ty + 4), subtitle, font=FG(19, 500), fill=MUT)

    # гигантское число + единица справа (как в утверждённом J6: «+0,54 %»)
    big_size = 200
    bf = FG(big_size, 800)
    while draw.textlength(value_text, font=bf) > 560 and big_size > 110:
        big_size -= 10
        bf = FG(big_size, 800)
    bb = _draw_big_number(img, (margin - 4, 208), value_text, big_size)
    draw = ImageDraw.Draw(img, "RGBA")
    num_w = draw.textlength(value_text, font=bf)
    glyph = unit_suffix or ("%" if "%" in (value_text or "") else None)
    if glyph and "%" not in (value_text or ""):
        draw.text((margin - 4 + num_w + 16, bb[3] - 78), glyph, font=FG(62, 700), fill=(206, 210, 230))
        num_w += 56

    # правая колонка: период/база (date_text) + пилюля контекста
    px = margin - 4 + num_w + 80
    if date_text and not period_text:
        df2 = FG(21, 500)
        draw.text((px, bb[1] + 20), date_text, font=df2, fill=MUT)
    if context_pill:
        pf = FG(26, 800)
        tw = draw.textlength(context_pill, font=pf)
        pill_x = px
        pill_y = bb[1] + 64
        if pill_x + tw + 52 > WIDTH - margin:
            pill_x = max(margin, WIDTH - margin - tw - 52)
        if pill_x + tw + 52 > WIDTH - margin:  # совсем не влезает — под числом
            pill_x = margin
            pill_y = bb[3] + 24
        draw.rounded_rectangle([pill_x, pill_y, pill_x + tw + 52, pill_y + 56],
                               radius=28, fill=GOLD + (255,))
        draw.text((pill_x + 26, pill_y + 11), context_pill, font=pf, fill=PILL_TEXT)

    # лента динамики
    chart_box = (60, 448, WIDTH - 60, 562)
    if len(values) < 2:
        values = (values + [values[-1] if values else 0.0])[:2] or [0.0, 0.0]
    last_label = value_text if len(value_text) <= 12 else value_text[:11] + "…"
    if glyph and "%" not in last_label:
        last_label = f"{last_label}{glyph}"
    _draw_poster_chart(img, values[-48:], chart_box, last_label)
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


def _brand_footer(draw: ImageDraw.ImageDraw, note: str = "") -> None:
    footer_font = _font(26)
    draw.text((64, HEIGHT - 42), "forecasteconomy.com", font=footer_font, fill=TEXT_TERTIARY)
    if note:
        nw = draw.textlength(note, font=footer_font)
        draw.text((WIDTH - 64 - nw, HEIGHT - 42), note, font=footer_font, fill=TEXT_TERTIARY)


def render_rating_og(
    *,
    name: str,
    year: int,
    unit: str,
    rows: list[tuple[str, float]],
    total: int,
    order_label: str = "наибольшие значения",
) -> bytes:
    """Рейтинг регионов: горизонтальный барчарт топ-8 + бренд (для /region-rating).

    Самодостаточная картинка под Алису/Нейро: заголовок, год, первые строки
    текущего порядка со значениями, счётчик «из N регионов», домен.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, f"{year} год")

    name_font = _font(44, bold=True)
    lines = _wrap_text(draw, f"{name}: рейтинг регионов", name_font, WIDTH - margin * 2)
    y = 88
    for line in lines:
        draw.text((margin, y), line, font=name_font, fill=TEXT_PRIMARY)
        y += 52

    top = rows[:8]
    if top:
        vmax = max(abs(v) for _n, v in top) or 1.0
        bar_font = _font(24)
        val_font = _font(24, bold=True)
        bar_area_x0 = margin + 330
        bar_area_x1 = WIDTH - margin - 170
        row_y = y + 20
        row_h = (HEIGHT - 70 - row_y) // len(top)
        bar_h = min(30, row_h - 12)
        for region_name, value in top:
            label = region_name if len(region_name) <= 24 else region_name[:23] + "…"
            draw.text((margin, row_y + (row_h - 26) // 2), label, font=bar_font, fill=TEXT_PRIMARY)
            w = int((bar_area_x1 - bar_area_x0) * abs(value) / vmax)
            by = row_y + (row_h - bar_h) // 2
            draw.rounded_rectangle(
                [bar_area_x0, by, bar_area_x0 + max(w, 6), by + bar_h],
                radius=6, fill=(184, 148, 47, 200),
            )
            draw.text((bar_area_x0 + max(w, 6) + 14, row_y + (row_h - 26) // 2),
                      _fmt_axis(value), font=val_font, fill=TEXT_PRIMARY)
            row_y += row_h

    note = f"{order_label} — {len(top)} из {total} регионов"
    if unit:
        note += f" — {unit}"
    _brand_footer(draw, note)

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
) -> bytes:
    """Рейтинг стран: горизонтальный барчарт первых строк текущего порядка."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, f"{year} год")

    name_font = _font(44, bold=True)
    lines = _wrap_text(draw, f"{name}: рейтинг стран", name_font, WIDTH - margin * 2)
    y = 88
    for line in lines:
        draw.text((margin, y), line, font=name_font, fill=TEXT_PRIMARY)
        y += 52

    top = rows[:8]
    if top:
        vmax = max(abs(v) for _n, v in top) or 1.0
        bar_font = _font(24)
        val_font = _font(24, bold=True)
        bar_area_x0 = margin + 330
        bar_area_x1 = WIDTH - margin - 170
        row_y = y + 20
        row_h = (HEIGHT - 70 - row_y) // len(top)
        bar_h = min(30, row_h - 12)
        for country_name, value in top:
            label = country_name if len(country_name) <= 24 else country_name[:23] + "…"
            draw.text((margin, row_y + (row_h - 26) // 2), label, font=bar_font, fill=TEXT_PRIMARY)
            w = int((bar_area_x1 - bar_area_x0) * abs(value) / vmax)
            by = row_y + (row_h - bar_h) // 2
            draw.rounded_rectangle(
                [bar_area_x0, by, bar_area_x0 + max(w, 6), by + bar_h],
                radius=6, fill=(184, 148, 47, 200),
            )
            draw.text((bar_area_x0 + max(w, 6) + 14, row_y + (row_h - 26) // 2),
                      _fmt_axis(value), font=val_font, fill=TEXT_PRIMARY)
            row_y += row_h

    note = f"{order_label} — {len(top)} из {total} стран"
    if unit:
        note += f" — {unit}"
    _brand_footer(draw, note)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_today_hub_og(*, date_text: str, items: list[tuple[str, str]]) -> bytes:
    """Сводка «Экономика России сегодня»: сетка «показатель → значение» (для /today)."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, date_text)

    title_font = _font(52, bold=True)
    draw.text((margin, 96), "Экономика России сегодня", font=title_font, fill=TEXT_PRIMARY)

    # 6 карточек (3 ряда): 4 ряда упирались в футер. cell_h+10 шаг, низ ~508.
    grid = items[:6]
    cols = 2
    cell_w = (WIDTH - margin * 2 - 24) // cols
    cell_h = 96
    top_y = 190
    label_font = _font(26)
    value_font = _font(38, bold=True)
    for i, (label, value_text) in enumerate(grid):
        cx = margin + (i % cols) * (cell_w + 24)
        cy = top_y + (i // cols) * (cell_h + 10)
        draw.rounded_rectangle([cx, cy, cx + cell_w, cy + cell_h], radius=14,
                               fill=(255, 255, 255), outline=(0, 0, 0, 28), width=1)
        draw.text((cx + 22, cy + 14), label, font=label_font, fill=TEXT_SECONDARY)
        draw.text((cx + 22, cy + 46), value_text, font=value_font, fill=TEXT_PRIMARY)

    _brand_footer(draw, "официальные данные — обновляется ежедневно")
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
) -> bytes:
    """Сравнение двух регионов: таблица «показатель — A — B» (для /region-vs).

    Колонки не наезжают друг на друга: подписи и значения обрезаются по
    фактической пиксельной ширине колонки (единицы измерения компактизирует
    вызывающая сторона: «тысяч человек» → «тыс. чел.»).
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, "сравнение регионов")

    title_font = _font(46, bold=True)
    title = f"{name_a} и {name_b}"
    lines = _wrap_text(draw, title, title_font, WIDTH - margin * 2)
    y = 92
    for line in lines:
        draw.text((margin, y), line, font=title_font, fill=TEXT_PRIMARY)
        y += 54

    col_metric_x = margin
    col_a_x = 600
    col_b_x = 880
    col_w = 260
    metric_w = col_a_x - margin - 24
    head_font = _font(26, bold=True)
    y += 14
    draw.text((col_a_x, y), _fit_text(draw, name_a, head_font, col_w), font=head_font, fill=CHAMPAGNE)
    draw.text((col_b_x, y), _fit_text(draw, name_b, head_font, col_w), font=head_font, fill=CHAMPAGNE)
    y += 44

    row_font = _font(25)
    val_font = _font(25, bold=True)
    for metric, va, vb in rows[:6]:
        draw.line([(margin, y - 8), (WIDTH - margin, y - 8)], fill=(0, 0, 0, 22), width=1)
        draw.text((col_metric_x, y), _fit_text(draw, metric, row_font, metric_w), font=row_font, fill=TEXT_SECONDARY)
        draw.text((col_a_x, y), _fit_text(draw, va, val_font, col_w), font=val_font, fill=TEXT_PRIMARY)
        draw.text((col_b_x, y), _fit_text(draw, vb, val_font, col_w), font=val_font, fill=TEXT_PRIMARY)
        y += 54

    _brand_footer(draw, "данные Росстата")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_world_country_og(
    *,
    country_name: str,
    indicators_count: int,
    items: list[tuple[str, str]],
) -> bytes:
    """Сводка страны для /og/world/{slug}.png: сетка ключевых значений."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    margin = 64
    _brand_header(draw, "мировая экономика")

    title_font = _font(48, bold=True)
    title = f"Экономика {country_name}"
    lines = _wrap_text(draw, title, title_font, WIDTH - margin * 2)
    y = 92
    for line in lines:
        draw.text((margin, y), line, font=title_font, fill=TEXT_PRIMARY)
        y += 54

    sub_font = _font(26)
    draw.text(
        (margin, y + 4),
        f"{indicators_count} показателей — Евростат",
        font=sub_font,
        fill=TEXT_SECONDARY,
    )

    grid = items[:6]
    cols = 2
    cell_w = (WIDTH - margin * 2 - 24) // cols
    cell_h = 88
    top_y = y + 50
    label_font = _font(24)
    value_font = _font(34, bold=True)
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
            _fit_text(draw, label, label_font, cell_w - 40),
            font=label_font,
            fill=TEXT_SECONDARY,
        )
        draw.text(
            (cx + 22, cy + 44),
            _fit_text(draw, value_text, value_font, cell_w - 40),
            font=value_font,
            fill=TEXT_PRIMARY,
        )

    _brand_footer(draw, "официальные данные Евростата")
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
