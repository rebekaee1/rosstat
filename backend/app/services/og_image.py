"""Per-indicator OG-превью (PNG 1200×630) — редакционная карточка быстрой ссылки.

Раздаётся как `https://forecasteconomy.com/og/{code}.png` (nginx → backend
`/api/v1/og-image/indicator/{code}.png`). Подключается в SSR через
`build_document(og_image=...)` — у каждой карточки своё превью в соцсетях,
мессенджерах и выдаче вместо одной общей картинки.

Карточка быстрой ссылки: утверждённая liquid glass композиция, Manrope,
тематическая скульптура, крупный ответ и точный график. Картинка самодостаточна:
название, число, период, подпись ряда и домен forecasteconomy.com
справа внизу. Гарнитура — Manrope (OFL), кириллица и латиница. Тёмный постер J6 этим рендером заменён.

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
import math
from functools import lru_cache
import os
import random
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1200, 630

# Manrope's bundled subset lacks some Unicode spacing glyphs. Formatting stays
# unchanged for HTML/data; raster typography uses a normal space for every Zs
# separator, in both measurement and painting, so line fitting stays identical.
_RASTER_SPACES = str.maketrans({ord(char): " " for char in
    "\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"})


def _raster_text(value):
    return value.translate(_RASTER_SPACES) if isinstance(value, str) else value


class _RasterDraw(ImageDraw.ImageDraw):
    def text(self, xy, text, *args, **kwargs):
        return super().text(xy, _raster_text(text), *args, **kwargs)

    def textbbox(self, xy, text, *args, **kwargs):
        return super().textbbox(xy, _raster_text(text), *args, **kwargs)

    def textlength(self, text, *args, **kwargs):
        return super().textlength(_raster_text(text), *args, **kwargs)


def _raster_draw(image, mode=None):
    return _RasterDraw(image, mode)

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

_LEGACY_BG = (238, 240, 244)
TEXT_PRIMARY = (32, 42, 60)
CHAMPAGNE = (173, 138, 72)
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
    # Плюс — у изменений (ИПЦ и т.п.), не у уровней. См. og_hero_number.
    sign = "+" if v >= 0 else "\u2212"
    return f"{sign}{fmt_ru(abs(v), locale=locale)}"


def og_hero_number(code: str | None, v: float, *, locale: str | None = None) -> str:
    """Крупное число на OG: «+» только у рядов-изменений, уровень без плюса."""
    from app.services.display import display_sign

    if display_sign(code):
        return fmt_signed(v, locale=locale)
    if v < 0:
        return f"\u2212{fmt_ru(abs(v), locale=locale)}"
    return fmt_ru(v, locale=locale)


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
_GOLOS_PATH = _FONT_DIR / "Manrope-Variable.ttf"
_FONT_PATH = _FONT_DIR / "Inter-Variable.ttf"

_CACHE: dict[str, tuple[float, bytes]] = {}
_CACHE_TTL = 3600.0
_CACHE_MAX = 600
_CACHE_MAX_BYTES = 64 * 1024 * 1024
_CACHE_LOCK = threading.RLock()

# PIL ImageFont.truetype держит REG-дескриптор файла. Без кэша каждый OG-рендер
# открывает Inter/Golos заново; объекты с __del__ плохо собирает GC.
_FONT_CACHE: dict[tuple[str, int, int], ImageFont.FreeTypeFont] = {}
_FONT_FILE_BYTES: dict[str, bytes] = {}


def _cached_truetype(path: Path, size: int, *axes: float) -> ImageFont.FreeTypeFont:
    key = (str(path), size, int(axes[-1]) if axes else 0)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached
    blob = _FONT_FILE_BYTES.get(str(path))
    if blob is None:
        blob = path.read_bytes()
        _FONT_FILE_BYTES[str(path)] = blob
    font = ImageFont.truetype(io.BytesIO(blob), size)
    if axes:
        try:
            font.set_variation_by_axes(list(axes))
        except OSError:
            pass
    _FONT_CACHE[key] = font
    return font


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    return FG(size, 700 if bold else 400)


def FG(size: int, wght: int = 400) -> ImageFont.FreeTypeFont:
    """Manrope variable, shared with the approved RU/EN browser typography."""
    return _cached_truetype(_GOLOS_PATH, size, float(min(800, max(200, wght))))


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
    return lines


def _wrap_fit_lines(
    text: str,
    size: int,
    wght: int,
    max_width: int,
    min_size: int,
    max_lines: int = 2,
) -> tuple[list[str], int]:
    """Перенос заголовка на 2 строки с автоподбором кегля под ширину полосы.

    Сначала пробуется полный размер и обычный перенос; если хоть одна строка
    не влезает — кегль уменьшается до тех пор, пока перенесённые строки не
    станут короче max_width (floor — min_size). Гарантирует, что и перенос,
    и каждая строка переноса умещаются в полосу.
    """
    probe = _raster_draw(Image.new("RGB", (8, 8)))
    size = max(int(size), min_size)
    while True:
        font = FG(size, wght)
        lines = _wrap_text(probe, text, font, max_width)
        if (len(lines) <= max_lines and all(
            probe.textlength(line, font=font) <= max_width for line in lines
        )) or size <= min_size:
            return lines, size
        size -= 2


def _fit_text_block(text: str, size: int, weight: int, width: int, height: int,
                    *, min_size: int = 18) -> tuple[list[str], int]:
    """Fit the complete label into a height budget; never discard title words.

    max_lines alone is not a hard bound once its minimum font size is reached.
    This geometry check is used where a chart or a fact needs reserved space.
    """
    probe = _raster_draw(Image.new("RGB", (8, 8)))
    while True:
        lines = _wrap_text(probe, text, FG(size, weight), width)
        fits = len(lines) * round(size * 1.2) <= height and all(
            probe.textlength(line, font=FG(size, weight)) <= width for line in lines
        )
        if fits or size <= min_size:
            return lines, size
        size -= 1


def _split_value_lines(value_text: str) -> tuple[str, str | None]:
    """Число отдельно от словесной единицы: «13 149,8 тысяч человек» →
    («13 149,8», «тысяч человек»). Разрез по последнему пробелу, слева от
    которого стоит чисто числовая часть (цифры, пробелы-разряды, разделитель,
    знак); «+0,54 %» остаётся одной строкой."""
    if "%" in value_text or not value_text:
        return value_text, None
    stripped = value_text.strip()
    number_only = stripped.replace("\u202f", "").replace("\u00a0", "").replace(" ", "")
    if number_only and all(c.isdigit() or c in ",.+-−" for c in number_only):
        return stripped, None
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
    probe = _raster_draw(Image.new("RGB", (8, 8)))
    while probe.textlength(text, font=FG(size, wght)) > max_width and size > min_size:
        size -= 2
    return size


def _fit_text_width(text: str, size: int, wght: int, max_width: int) -> str:
    """Пиксельная обрезка с многоточием на подобранном кегле (последний рубеж)."""
    probe = _raster_draw(Image.new("RGB", (8, 8)))
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
    _raster_draw(poly_mask).polygon(sm + [(sm[-1][0], y1 + 2), (sm[0][0], y1 + 2)], fill=85)
    gh = y1 - y0 + 1
    ga = np.zeros((gh, WIDTH, 4), dtype=np.uint8)
    fade = np.tile(np.linspace(1, 0, gh)[:, None], (1, WIDTH))
    for i, c in enumerate(GOLD):
        ga[:, :, i] = (c * fade).astype(np.uint8)
    ga[:, :, 3] = (fade * 84).astype(np.uint8)
    grad_full = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    grad_full.paste(Image.fromarray(ga, "RGBA"), (0, y0))
    img.paste(grad_full, (0, 0), poly_mask)

    d = _raster_draw(img, "RGBA")
    if lo < 0 < hi:
        zy = y1 - (y1 - y0) * (0 - lo) / rngv
        for i in range(int(x0), int(x1), 14):
            d.line([(i, zy), (i + 7, zy)], fill=(255, 255, 255, 40), width=1)
    d.line(sm, fill=GOLD_BRIGHT + (255,), width=5, joint="curve")

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
    _raster_draw(tmp).text(xy, text, font=f, fill=255)
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


_ART_DIR = Path(__file__).parent.parent / "assets" / "quicklinks"
OG_DESIGN_VERSION = "glass-manrope-6"


def quicklink_art_theme(text: str) -> str:
    """Visual family only: never derives, substitutes, or labels numerical data."""
    key = text.lower().replace("_", "-")
    if "nonfarm" in key:
        return "population"
    if any(word in key for word in ("doctoral", "аспирант", "докторант")):
        return "education"
    groups = (
        ("ict", ("internet", "broadband", "telecom", "digital", "electronic", "интернет", "цифров", "связи", "электронн")),
        ("trade", ("export", "import", "trade", "экспорт", "импорт", "торгов")),
        ("justice", ("crime", "justice", "court", "преступ", "правосуд", "судеб")),
        ("housing", ("housing", "house-price", "mortgage", "жиль", "жилищ", "ипотек", "строитель")),
        ("health", ("health", "hospital", "doctor", "life-expect", "здоров", "врач", "смерт")),
        ("education", ("education", "school", "student", "образован", "учащ")),
        ("science", ("research", "science", "patent", "r-and-d", "наук", "исследован")),
        ("agriculture", ("agri", "harvest", "crop", "farm", "сельск", "урож")),
        ("tourism", ("touris", "hotel", "travel", "туризм", "турист", "гостиниц")),
        ("environment", ("emission", "environment", "pollut", "эколог", "выброс")),
        ("energy", ("electric", "energy", "gas-prod", "энерг", "электр")),
        ("transport", ("transport", "freight", "passenger", "транспорт", "грузо")),
        ("commodity", ("brent", "crude", "commodity", "metal", "gold", "copper", "нефт", "топлив", "золот")),
        ("industry", ("industrial", "manufactur", "production", "gdp", "ввп", "промышлен", "производ")),
        ("population", ("population", "demograph", "migration", "labor", "labour", "wage", "employ", "насел", "зарплат", "безработ", "занятост")),
    )
    return next((theme for theme, words in groups if any(word in key for word in words)), "finance")


@lru_cache(maxsize=17)
def _art_background(theme: str) -> Image.Image:
    """Bounded decoded art cache; Pillow never retains an open file descriptor."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (*BG, 255))
    path = _ART_DIR / f"{theme}.webp"
    if path.is_file():
        with Image.open(path) as original:
            art = original.convert("RGBA")
            height = round(art.height * WIDTH / art.width)
            art = art.resize((WIDTH, height), Image.Resampling.LANCZOS)
        img.alpha_composite(art, (0, (HEIGHT - height) // 2))
    # Keep the sculpture visible behind the glass, while the answer has a calm,
    # high-contrast surface. This is a compositional veil, not a data overlay.
    veil = Image.new("RGBA", (WIDTH, HEIGHT))
    vd = _raster_draw(veil)
    for x in range(WIDTH):
        alpha = int(245 * max(0, min(1, (720 - x) / 290)))
        vd.line((x, 0, x, HEIGHT), fill=(*BG, alpha))
    img.alpha_composite(veil)
    return img


def _pearl_base(theme: str = "finance") -> Image.Image:
    return _art_background(theme).copy()


def _glass_panel(draw: ImageDraw.ImageDraw, box, radius: int = 24) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=(255, 255, 255, 220),
                           outline=(255, 255, 255, 255), width=2)
    x0, y0, x1, _y1 = box
    draw.line((x0 + radius, y0 + 3, x1 - radius, y0 + 3), fill=(255, 255, 255, 255), width=1)


def _draw_wordmark(draw: ImageDraw.ImageDraw, x: int = 46, y: int = 30) -> None:
    # The same f + champagne square as the approved browser wordmark.
    draw.rounded_rectangle((x, y + 4, x + 28, y + 15), radius=7, fill=TEXT_PRIMARY)
    draw.rectangle((x, y + 12, x + 9, y + 37), fill=TEXT_PRIMARY)
    draw.rectangle((x + 7, y + 19, x + 25, y + 27), fill=TEXT_PRIMARY)
    draw.rectangle((x + 23, y + 30, x + 30, y + 37), fill=CHAMPAGNE)
    start = x + 44
    draw.text((start, y - 3), "forecast", font=FG(29, 750), fill=TEXT_PRIMARY)
    width = draw.textlength("forecast", font=FG(29, 750))
    draw.text((start + width, y - 3), "economy", font=FG(29, 400), fill=TEXT_PRIMARY)
    draw.text((start + 1, y + 31), "ECONOMIC INTELLIGENCE", font=FG(9, 600), fill=CHAMPAGNE)


def _chart_coordinates(values, box, point_dates=None, *, zero_baseline=False):
    """No invented endpoints, no implicit tail slicing; x is elapsed time."""
    finite = [(i, float(v)) for i, v in enumerate(values) if v is not None and math.isfinite(float(v))]
    if not finite:
        return [], (0.0, 1.0)
    x0, y0, x1, y1 = box
    low, high = min(v for _, v in finite), max(v for _, v in finite)
    if zero_baseline:
        low, high = min(0, low), max(0, high)
    pad = ((high - low) or abs(high) or 1) * .14
    lo, hi = low - pad, high + pad
    if zero_baseline:
        rough = (high-low or abs(high) or 1)/4
        magnitude = 10 ** math.floor(math.log10(rough))
        step = next(m for m in (1,2,2.5,5,10) if m*magnitude >= rough) * magnitude
        lo, hi = math.floor(low/step)*step, math.ceil(high/step)*step
        if lo == hi:
            hi = lo + step
    dates = None
    if point_dates and len(point_dates) == len(values):
        from datetime import date
        try:
            dates = [d.toordinal() if hasattr(d, "toordinal") else date.fromisoformat(str(d)[:10]).toordinal() for d in point_dates]
        except (ValueError, TypeError):
            dates = None
    xx = dates or list(range(len(values)))
    start, end = min(xx), max(xx)
    points = [(i, x0 + (x1-x0) * ((xx[i]-start)/(end-start) if end != start else .5),
               y1 - (y1-y0)*(v-lo)/(hi-lo)) for i, v in finite]
    return points, (lo, hi)


def _draw_editorial_chart(draw, values, box, *, point_dates=None, frequency=None,
                          chart_kind="line", selected_index=None, text_scale=1.0, selection_label=None) -> None:
    x0, y0, x1, y1 = box
    coordinate_box = (x0+18, y0, x1-18, y1) if chart_kind == "bar" else box
    points, (lo, hi) = _chart_coordinates(values, coordinate_box, point_dates, zero_baseline=chart_kind == "bar")
    muted = (91, 105, 124, 255)
    if not points:
        label = "No published observations" if _effective_locale(None) == "en" else "Нет опубликованных наблюдений"
        draw.text((x0, (y0+y1)//2), label, font=FG(18, 500), fill=muted)
        return
    intervals = 4 if chart_kind == "bar" else 3
    for k in range(intervals+1):
        gy = y0 + (y1-y0) * k/intervals
        draw.line((x0, gy, x1, gy), fill=(32, 42, 60, 28), width=1)
        value = hi - (hi-lo)*k/intervals
        draw.text((x0-10, gy-10), _fmt_axis(value), anchor="ra", font=FG(round(15*text_scale), 500), fill=muted)
    zero_y = y1-(y1-y0)*(0-lo)/(hi-lo)
    if lo < 0 < hi:
        draw.line((x0, zero_y, x1, zero_y), fill=(32, 42, 60, 100), width=1)
    if chart_kind == "bar":
        bw = max(2, min(30, (x1-x0)/max(1, len(values))*.52))
        for index, x, y in points:
            color = (*CHAMPAGNE, 235) if values[index] >= 0 else (82, 119, 143, 255)
            if abs(y-zero_y) >= 1:
                draw.rounded_rectangle((x-bw/2, min(y, zero_y), x+bw/2, max(y, zero_y)), radius=2, fill=color)
            else:
                draw.line((x-bw/2, zero_y, x+bw/2, zero_y), fill=color, width=2)
    else:
        for (prev_i, px, py), (i, x, y) in zip(points, points[1:]):
            # A missing value or a missing monthly/annual interval stays a gap.
            adjacent = i == prev_i + 1
            if point_dates and frequency in ("monthly", "quarterly", "annual", "yearly"):
                a, b = str(point_dates[prev_i])[:10], str(point_dates[i])[:10]
                delta = (int(b[:4])-int(a[:4]))*12 + int(b[5:7])-int(a[5:7])
                adjacent &= delta <= {"monthly": 1, "quarterly": 3, "annual": 12, "yearly": 12}[frequency]
            if adjacent:
                segment = [(px, py), (x, py), (x, y)] if chart_kind == "step" else [(px, py), (x, y)]
                draw.line(segment, fill=(55, 76, 96, 255), width=4, joint="curve")
        if len(points) <= 24:
            for _, x, y in points:
                draw.ellipse((x-3, y-3, x+3, y+3), fill=(55, 76, 96, 255))
    selected = next((p for p in points if p[0] == selected_index), points[-1])
    _, sx, sy = selected
    if selection_label:
        for y in range(int(y0), int(y1), 10):
            draw.line((sx, y, sx, min(y+4,y1)), fill=(*CHAMPAGNE,140), width=2)
        font = FG(round(15*text_scale), 700)
        tx = max(x0, min(sx + 12, x1-draw.textlength(selection_label,font=font)))
        draw.text((tx, y0-32*text_scale), selection_label, font=font, fill=CHAMPAGNE)
    draw.ellipse((sx-7, sy-7, sx+7, sy+7), fill=(*CHAMPAGNE, 255), outline=(255,255,255,255), width=2)


def render_indicator_og(
    *, code: str, name: str, value_text: str, date_text: str, values: list[float],
    period_text: str | None = None, x_labels: tuple[str, str] | None = None,
    context_pill: str | None = None, subtitle: str | None = None,
    unit_suffix: str | None = None, point_dates=None, frequency: str | None = None,
    source_label: str | None = None, selected_index: int | None = None,
    portrait: bool = False,
) -> bytes:
    """One data-driven glass template for national, world and regional pages.

    Labels/values are supplied by the public-data adapters. Art is thematic only;
    no artwork, fixture or interpolation provides numerical observations.
    """
    if portrait:
        return _render_indicator_portrait(code=code, name=name, value_text=value_text,
            date_text=date_text, values=values, period_text=period_text, x_labels=x_labels,
            context_pill=context_pill, subtitle=subtitle, unit_suffix=unit_suffix,
            point_dates=point_dates, frequency=frequency, source_label=source_label,
            selected_index=selected_index)
    img = _pearl_base(quicklink_art_theme(code + " " + name)).convert("RGB")
    draw = _raster_draw(img, "RGBA")
    ink, muted = (*TEXT_PRIMARY, 255), (91, 105, 124, 255)
    _draw_wordmark(draw)
    if period_text:
        draw.text((1152, 43), period_text, anchor="ra", font=FG(18, 600), fill=muted)
    loc = _effective_locale(None)
    title_lines, title_size = _wrap_fit_lines(name or " ", 43, 600, 410, 23, max_lines=3)
    extended_title = len(title_lines) * round(title_size * 1.2) > 145
    if extended_title:
        # Long official titles span the poster; the number and real chart keep
        # separate lower columns instead of colliding in the narrow left rail.
        title_lines, title_size = _fit_text_block(name, 31, 600, 1104, 104, min_size=18)
        draw.rectangle((30, 96, 1171, 225), fill=(238, 240, 244, 150))
    else:
        draw.text((46, 119), "OFFICIAL STATISTICS" if loc == "en" else "ОФИЦИАЛЬНАЯ СТАТИСТИКА",
                  font=FG(12, 700), fill=CHAMPAGNE)
    ty = 145 if not extended_title else 110
    for line in title_lines:
        draw.text((46, ty), line, font=FG(title_size, 600), fill=ink)
        ty += int(title_size * 1.2)
    num, unit = _split_value_lines(value_text or "—")
    if unit_suffix and unit_suffix not in (value_text or ""):
        unit = f"{unit or ''} {unit_suffix}".strip()
    size = _fit_font_size(num, 88 if not extended_title else 70, 550, 414, 33)
    ny = max(ty+22, 301)
    draw.text((43, ny), num, font=FG(size, 550), fill=ink)
    my = ny+int(size*1.19)
    if unit:
        draw.text((47, my), unit, font=FG(_fit_font_size(unit, 21, 500, 412, 13), 500), fill=muted)
        my += 32
    for label, color in ((date_text, muted), (context_pill, CHAMPAGNE)):
        if label:
            lines, fs = _wrap_fit_lines(label, 17, 500, 415, 13)
            for line in lines:
                draw.text((47, my), line, font=FG(fs, 500), fill=color)
                my += fs+6
    panel_top = max(142, ty + 14) if extended_title else 142
    _glass_panel(draw, (490, panel_top, 1155, 529))
    axis_unit = unit_suffix or unit or ("%" if "%" in value_text else "")
    heading = subtitle or (("Observed values" if loc == "en" else "Опубликованные значения") + (f", {axis_unit}" if axis_unit else ""))
    draw.text((513, panel_top + 20), heading, font=FG(_fit_font_size(heading, 20, 650, 613, 14),650), fill=ink)
    chart = (569, panel_top + (64 if extended_title else 80), 1122, 462 if extended_title else 442)
    kind = "step" if "key-rate" in code or "keyrate" in code else "bar" if ("cpi" in code and len(values) <= 15) else "line"
    _draw_editorial_chart(draw, values, chart, point_dates=point_dates, frequency=frequency,
                          chart_kind=kind, selected_index=selected_index,
                          selection_label=str(period_text) if selected_index is not None and selected_index < len(values)-1 else None)
    if x_labels:
        if x_labels[0] == x_labels[1]:
            draw.text(((chart[0]+chart[2])/2,chart[3]+16),x_labels[0],anchor="ma",font=FG(15,600),fill=muted)
        else:
            draw.text((chart[0], chart[3]+16), x_labels[0], font=FG(15, 600), fill=muted)
            draw.text((chart[2], chart[3]+16), x_labels[1], anchor="ra", font=FG(15, 600), fill=muted)
    draw.text((1128, 497), "forecasteconomy.com", anchor="ra", font=FG(15, 650), fill=CHAMPAGNE)
    draw.line((46, 556, 1154, 556), fill=(32,42,60,35), width=1)
    note = source_label or ("Source and methodology on the indicator page" if loc == "en" else "Источник и методология — в карточке показателя")
    draw.text((46, 577), note, font=FG(_fit_font_size(note, 16, 500, 735, 12),500), fill=muted)
    draw.text((1154, 574), "forecasteconomy.com", anchor="ra", font=FG(21, 600), fill=ink)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def _render_indicator_portrait(*, code, name, value_text, date_text, values,
        period_text, x_labels, context_pill, subtitle, unit_suffix,
        point_dates, frequency, source_label, selected_index):
    """1080×1350 companion: axis text stays >=11 px on a 288 px content width."""
    width, height = 1080, 1350
    img = Image.new("RGB", (width,height), BG)
    art = _pearl_base(quicklink_art_theme(code + " " + name)).convert("RGB")
    art = art.resize((1080, 567), Image.Resampling.LANCZOS)
    img.paste(art, (0,70))
    draw = _raster_draw(img, "RGBA")
    muted = (91,105,124,255)
    draw.rectangle((0, 95, width, 637), fill=(238, 240, 244, 100))
    _draw_wordmark(draw, 54, 28)
    loc = _effective_locale(None)
    if period_text:
        draw.text((1026, 45), period_text, anchor="ra", font=FG(29,600), fill=muted)
    number, unit = _split_value_lines(value_text or "—")
    if unit_suffix and unit_suffix not in value_text:
        unit = f"{unit or ''} {unit_suffix}".strip()
    unit_lines, unit_size = _wrap_fit_lines(unit or "", 39, 500, 955, 32, max_lines=2)
    metadata_height = len(unit_lines) * (unit_size + 7) + sum(43 for label in (date_text,context_pill) if label)
    # Keep at least a 100px main fact and a >=200px plotting area. A long
    # official title uses more lines and less art/number whitespace.
    title_budget = 655 - 137 - 14 - 120 - metadata_height
    lines, size = _fit_text_block(name,60,600,960,title_budget,min_size=24)
    ty = 137
    for line in lines:
        draw.text((53,ty),line,font=FG(size,600),fill=TEXT_PRIMARY)
        ty += round(size*1.2)
    ny = max(ty+14, 285)
    available_size = max(72, int((655 - ny - metadata_height) / 1.2))
    number_size = _fit_font_size(number,min(145,available_size),550,970,72)
    draw.text((47,ny), number, font=FG(number_size,550), fill=TEXT_PRIMARY)
    my = ny + round(number_size*1.2)
    for line in unit_lines:
        draw.text((56,my), line, font=FG(unit_size,500),fill=muted)
        my+=unit_size+7
    for label,color in ((date_text,muted),(context_pill,CHAMPAGNE)):
        if label:
            fs=_fit_font_size(label,34,500,960,27)
            fitted=_fit_text_width(label,fs,500,960)
            draw.text((55,my),fitted,font=FG(fs,500),fill=color)
            my+=fs+9
    panel_top = max(630, my+25)
    # Long metadata has a bounded allowance before the real data chart; no
    # observation or label is dropped to make room for artwork.
    _glass_panel(draw,(38,panel_top,1042,1215),radius=32)
    # The complete unit is already printed above the plot. Repeating a long
    # unit in this heading must not consume the reserved plotting height.
    heading=subtitle or ("Observed values" if loc=="en" else "Опубликованные значения")
    ls,fs=_fit_text_block(heading,39,650,930,60,min_size=29)
    hy=panel_top+25
    for line in ls:
        draw.text((66,hy),line,font=FG(fs,650),fill=TEXT_PRIMARY)
        hy+=fs+10
    chart=(201,hy+74,978,1058)
    kind="step" if "key-rate" in code or "keyrate" in code else "bar" if "cpi" in code and len(values)<=15 else "line"
    _draw_editorial_chart(draw,values,chart,point_dates=point_dates,frequency=frequency,
        chart_kind=kind,selected_index=selected_index,text_scale=2.8,
        selection_label=str(period_text) if selected_index is not None and selected_index<len(values)-1 else None)
    if x_labels:
        if x_labels[0] == x_labels[1]:
            draw.text(((chart[0]+chart[2])/2,1081),x_labels[0],anchor="ma",font=FG(42,600),fill=muted)
        else:
            draw.text((chart[0],1081),x_labels[0],font=FG(42,600),fill=muted)
            draw.text((chart[2],1081),x_labels[1],anchor="ra",font=FG(42,600),fill=muted)
    draw.text((996,1162),"forecasteconomy.com",anchor="ra",font=FG(34,650),fill=CHAMPAGNE)
    note=source_label or ("Source and methodology on the page" if loc=="en" else "Источник и методология — на странице")
    draw.text((54,1251),note,font=FG(_fit_font_size(note,32,500,965,25),500),fill=muted)
    draw.text((54,1303),"forecasteconomy.com",font=FG(25,650),fill=TEXT_PRIMARY)
    buf=io.BytesIO(); img.save(buf,format="PNG",compress_level=6)
    return buf.getvalue()


def render_demographics_og(*, year: int, groups: list[tuple[str, float]], unit: str,
        source_label: str, name: str | None = None, portrait: bool = False,
        locale: str | None = None) -> bytes:
    """Three additive age groups of one year/base; never an invented pyramid.

    Callers must provide all three comparable counts. Invalid/absent components
    are rejected so the endpoint can show an honest unavailable image state.
    """
    from app.services.display import format_number_ru

    if len(groups) != 3 or any(value is None or not math.isfinite(float(value)) or float(value)<0 for _,value in groups):
        raise ValueError("Three finite non-negative age-group counts are required")
    total = sum(float(value) for _,value in groups)
    if total <= 0:
        raise ValueError("Age-group total must be positive")
    loc = _effective_locale(locale)
    name = name or ("Age structure of Russia's population" if loc == "en" else "Возрастная структура населения России")
    colors = ((173,138,72),(82,119,143),(107,119,145))
    fmt = lambda value: format_number_ru(value, locale=loc)
    shares = [float(value)/total*100 for _,value in groups]
    if portrait:
        img = Image.new("RGB",(1080,1350),BG)
        img.paste(_pearl_base("population").convert("RGB").resize((1080,567),Image.Resampling.LANCZOS),(0,70))
        draw=_raster_draw(img,"RGBA")
        _draw_wordmark(draw,54,28)
        draw.text((1026,44),str(year),anchor="ra",font=FG(32,600),fill=TEXT_SECONDARY)
        lines,fs=_wrap_fit_lines(name,60,600,960,38,max_lines=2)
        y=135
        for line in lines:
            draw.text((54,y),line,font=FG(fs,600),fill=TEXT_PRIMARY)
            y+=round(fs*1.2)
        draw.text((50,max(290,y+20)),fmt(total),font=FG(_fit_font_size(fmt(total),128,550,965,62),550),fill=TEXT_PRIMARY)
        draw.text((57,466),unit,font=FG(_fit_font_size(unit,42,500,955,32),500),fill=TEXT_SECONDARY)
        total_label="Sum of the three age groups" if loc=="en" else "Сумма трёх возрастных групп"
        draw.text((57,526),total_label,font=FG(34,500),fill=TEXT_SECONDARY)
        for i,((label,value),share,color) in enumerate(zip(groups,shares,colors)):
            top=618+i*185
            _glass_panel(draw,(38,top,1042,top+168),radius=26)
            draw.text((67,top+19),label,font=FG(_fit_font_size(label,42,600,940,29),600),fill=TEXT_PRIMARY)
            draw.text((67,top+79),fmt(value),font=FG(47,600),fill=TEXT_PRIMARY)
            draw.text((1007,top+79),f"{fmt(round(share,1))} %",anchor="ra",font=FG(44,600),fill=color)
            draw.rounded_rectangle((68,top+143,1008,top+153),radius=5,fill=(32,42,60,22))
            if share>0:
                draw.rounded_rectangle((68,top+143,68+940*share/100,top+153),radius=5,fill=color)
        draw.text((1009,1203),"forecasteconomy.com",anchor="ra",font=FG(34,650),fill=CHAMPAGNE)
        draw.text((54,1260),source_label,font=FG(_fit_font_size(source_label,36,500,950,25),500),fill=TEXT_SECONDARY)
        draw.text((54,1311),"forecasteconomy.com",font=FG(25,650),fill=TEXT_PRIMARY)
    else:
        img=_pearl_base("population").convert("RGB")
        draw=_raster_draw(img,"RGBA")
        _draw_wordmark(draw)
        draw.text((1154,43),str(year),anchor="ra",font=FG(20,600),fill=TEXT_SECONDARY)
        lines,fs=_wrap_fit_lines(name,40,600,1104,28)
        y=107
        for line in lines:
            draw.text((46,y),line,font=FG(fs,600),fill=TEXT_PRIMARY)
            y+=round(fs*1.2)
        total_label="Three age groups" if loc=="en" else "Три возрастные группы"
        draw.text((48,227),total_label,font=FG(18,600),fill=TEXT_SECONDARY)
        draw.text((44,269),fmt(total),font=FG(_fit_font_size(fmt(total),74,550,365,35),550),fill=TEXT_PRIMARY)
        draw.text((48,369),unit,font=FG(_fit_font_size(unit,23,500,361,15),500),fill=TEXT_SECONDARY)
        _glass_panel(draw,(428,193,1154,530))
        draw.text((451,213),"Share of the total" if loc=="en" else "Доли возрастных групп",font=FG(21,650),fill=TEXT_PRIMARY)
        x=451
        for share,color in zip(shares,colors):
            next_x=x+679*share/100
            draw.rectangle((x,263,next_x,300),fill=color)
            if next_x-x>72:
                draw.text(((x+next_x)/2,269),f"{fmt(round(share,1))}%",anchor="ma",font=FG(19,650),fill=(255,255,255))
            x=next_x
        for i,((label,value),share,color) in enumerate(zip(groups,shares,colors)):
            y=323+i*62
            draw.rounded_rectangle((451,y+7,462,y+18),radius=3,fill=color)
            draw.text((473,y),label,font=FG(_fit_font_size(label,20,500,410,14),500),fill=TEXT_PRIMARY)
            draw.text((1129,y),fmt(value),anchor="ra",font=FG(23,650),fill=TEXT_PRIMARY)
            draw.text((1129,y+29),f"{fmt(round(share,1))} %",anchor="ra",font=FG(16,500),fill=color)
        draw.text((1130,504),"forecasteconomy.com",anchor="ra",font=FG(15,650),fill=CHAMPAGNE)
        _brand_footer(draw,source_label,size=18)
    buf=io.BytesIO();img.save(buf,format="PNG",compress_level=6)
    return buf.getvalue()


def _brand_header(draw: ImageDraw.ImageDraw, eyebrow_extra: str | None = None) -> None:
    _draw_wordmark(draw, 64, 24)
    if eyebrow_extra:
        size = _fit_font_size(eyebrow_extra, 20, 500, 660, 13)
        draw.text((1136, 38), eyebrow_extra, anchor="ra", font=FG(size,500), fill=TEXT_SECONDARY)


def _brand_footer(draw: ImageDraw.ImageDraw, note: str = "", *, size: int = 26) -> None:
    draw.line((64, HEIGHT-66, WIDTH-64, HEIGHT-66), fill=(32,42,60,38), width=1)
    if note:
        size = _fit_font_size(note, min(size,18), 400, 745, 12)
        draw.text((64, HEIGHT-44), note, font=FG(size,400), fill=TEXT_SECONDARY)
    draw.text((WIDTH-64, HEIGHT-46), "forecasteconomy.com", anchor="ra", font=FG(20,650), fill=CHAMPAGNE)


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
    bw = f.getlength(_raster_text(last_label))
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
    num_w = nf.getlength(_raster_text(value_num if has_unit_line else value_text))

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
        pill_w = pf.getlength(_raster_text(context_pill)) + 52
        pill_h = 56
        # Якорь — правый край числа (или единицы, если она шире). Не влезает
        # справа — пилюля уходит вниз под число, оставаясь в пределах полосы.
        anchor = margin - 4 + max(num_w, pf.getlength(_raster_text(value_unit or "")) if value_unit else 0)
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
    scope_word: str | None = None,
    locale: str | None = None,
) -> dict:
    labels = _rating_labels(locale, kind=kind)
    tl = title_label or labels["title_label"]
    ct = count_template or labels["count_template"]
    sw = scope_word or labels["scope_word"]
    limit = WIDTH - 128
    title_lines, title_size = _fit_text_block(f"{name}: {tl}", 44, 700, limit, 145)

    top = rows[:8]
    label_size = 24
    if top:
        label_size = min(
            (_fit_font_size(rn, 24, 400, 330 - 16, 14) for rn, _v in top),
            default=24,
        )
    from app.services.display import format_number_ru
    val_texts = [format_number_ru(v, locale=locale) for _n, v in top]
    val_size = min((_fit_font_size(t, 24, 700, 156, 12) for t in val_texts), default=24)
    note = f"{order_label} — {ct.format(n=len(top), total=total, scope=sw)}"
    if unit:
        note += f" — {unit}"
    footer_size = _fit_font_size(note, 26, 400, limit, 14)
    return {
        "title_lines": title_lines,
        "title_size": title_size,
        "title_line_h": round(title_size * 1.2),
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
    separator: str = " и ",
) -> dict:
    limit = WIDTH - 128
    title_lines, title_size = _fit_text_block(f"{name_a}{separator}{name_b}", 46, 700, limit, 86)
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
        "title_line_h": round(title_size * 1.2),
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
    title_lines, title_size = _fit_text_block(
        title_template.format(country=country), 48, 700, limit, 108)
    cell_w = (WIDTH - 64 * 2 - 24) // 2
    label_size = min((_fit_font_size(lbl, 24, 400, cell_w - 40, 12) for lbl, _v in items), default=24)
    val_size = min((_fit_font_size(v, 34, 700, cell_w - 40, 14) for _l, v in items), default=34)
    return {
        "title_lines": title_lines,
        "title_size": title_size,
        "title_line_h": round(title_size * 1.2),
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


def _portrait_frame(title: str, *, eyebrow: str = "", subline: str = "", theme: str = "finance"):
    """Shared phone composition; artwork is decorative, all text is drawn natively."""
    img = Image.new("RGB", (1080, 1350), BG)
    art = _pearl_base(theme).convert("RGB").resize((1080, 567), Image.Resampling.LANCZOS)
    img.paste(art, (0, 70))
    draw = _raster_draw(img, "RGBA")
    draw.rectangle((0, 95, 1080, 630), fill=(238, 240, 244, 120))
    _draw_wordmark(draw, 54, 28)
    if eyebrow:
        draw.text((54, 108), _fit_text_width(eyebrow, 36, 600, 970), font=FG(36, 600), fill=CHAMPAGNE)
    lines, size = _fit_text_block(title, 56, 650, 970, 184, min_size=28)
    y = 155
    for line in lines:
        draw.text((52, y), line, font=FG(size, 650), fill=TEXT_PRIMARY)
        y += round(size * 1.2)
    if subline:
        lines, size = _wrap_fit_lines(subline, 36, 500, 965, 32, max_lines=2)
        y += 8
        for line in lines:
            draw.text((55, y), line, font=FG(size, 500), fill=TEXT_SECONDARY)
            y += round(size * 1.2)
    return img, draw, max(355, y + 14)


def _portrait_finish(img, draw, note: str = "") -> bytes:
    # A second domain sits next to the data, independently of the bottom footer.
    draw.text((1024, 1192), "forecasteconomy.com", anchor="ra", font=FG(33, 650), fill=CHAMPAGNE)
    draw.line((54, 1230, 1026, 1230), fill=(32, 42, 60, 38), width=2)
    if note:
        # Preserve full provenance where space allows; the page carries the full
        # source metadata when a multi-provider list exceeds this two-line area.
        lines, size = _wrap_fit_lines(note, 33, 500, 970, 32, max_lines=2)
        for i, line in enumerate(lines[:2]):
            draw.text((54, 1237 + i * 37), _fit_text_width(line, size, 500, 970), font=FG(size, 500), fill=TEXT_SECONDARY)
    draw.text((54, 1314), "forecasteconomy.com", font=FG(25, 650), fill=TEXT_PRIMARY)
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def _render_rating_portrait(*, name, title_label, period_text, unit, rows, total,
                           order_label, count_template, scope_word, locale, source_label):
    from app.services.display import format_number_ru
    top = rows[:8]
    count = count_template.format(n=len(top), total=total, scope=scope_word)
    subline = " · ".join(part for part in (count, unit) if part)
    img, draw, y = _portrait_frame(f"{name}: {title_label}", eyebrow=period_text, subline=subline)
    _glass_panel(draw, (38, y - 12, 1042, 1180), radius=24)
    row_h = min(108, (1173 - y) / max(len(top), 1))
    low = min([0.0] + [float(v) for _, v in top])
    high = max([0.0] + [float(v) for _, v in top])
    span = high - low or 1.0
    left, right = 68, 1010
    zero = left + (right - left) * -low / span
    for rank, (label, value) in enumerate(top, 1):
        text = f"{rank}. {label}"
        value_text = format_number_ru(value, locale=locale)
        value_size = _fit_font_size(value_text, 44, 650, 290, 36)
        value_width = draw.textlength(value_text, font=FG(value_size, 650))
        label_width = 936 - value_width - 28
        label_size = _fit_font_size(text, 40, 550, label_width, 36)
        draw.text((left, y), _fit_text_width(text, label_size, 550, label_width), font=FG(label_size, 550), fill=TEXT_PRIMARY)
        draw.text((right, y), value_text, anchor="ra", font=FG(value_size, 650), fill=TEXT_PRIMARY)
        by = y + row_h - 30
        draw.rounded_rectangle((left, by, right, by + 14), radius=7, fill=(32, 42, 60, 20))
        end = left + (right - left) * (float(value) - low) / span
        if abs(end - zero) >= 1:
            draw.rounded_rectangle((min(zero, end), by, max(zero, end), by + 14), radius=5,
                                   fill=CHAMPAGNE if value >= 0 else (82, 119, 143))
        draw.line((zero, by - 3, zero, by + 18), fill=(32, 42, 60, 125), width=2)
        y += row_h
    note = " · ".join(part for part in (order_label, source_label) if part)
    return _portrait_finish(img, draw, note)


def _render_items_portrait(*, title, eyebrow, subline, items, footer_note):
    img, draw, y = _portrait_frame(title, eyebrow=eyebrow, subline=subline)
    grid = items[:6]
    row_h = min(144, (1173 - y) / max(len(grid), 1))
    for label, value in grid:
        _glass_panel(draw, (38, y, 1042, y + row_h - 12), radius=22)
        size = _fit_font_size(label, 40, 550, 940, 36)
        draw.text((66, y + 12), _fit_text_width(label, size, 550, 940), font=FG(size, 550), fill=TEXT_SECONDARY)
        # Dates follow values and remain readable; allow two lines rather than
        # shrinking all six cards to fit the single longest observation string.
        size = _fit_font_size(value, 51, 650, 940, 36)
        lines = _wrap_text(draw, value, FG(size, 650), 940)
        if len(lines) > 1:
            # The full value is more important than decorative top whitespace.
            lines, size = _wrap_fit_lines(value, 36, 650, 940, 32, max_lines=2)
        vy = y + 54
        for line in lines:
            draw.text((65, vy), _fit_text_width(line, size, 650, 940), font=FG(size, 650), fill=TEXT_PRIMARY)
            vy += round(size * 1.12)
        y += row_h
    return _portrait_finish(img, draw, footer_note)


def _render_compare_portrait(*, name_a, name_b, rows, eyebrow, separator, footer_note):
    img, draw, y = _portrait_frame(f"{name_a}{separator}{name_b}", eyebrow=eyebrow)
    _glass_panel(draw, (38, y - 13, 1042, 1180), radius=24)
    # Column identities are repeated above values, even when the title wraps.
    for x, name in ((65, name_a), (554, name_b)):
        lines, size = _wrap_fit_lines(name, 36, 650, 455, 32, max_lines=2)
        for i, line in enumerate(lines):
            draw.text((x, y + i * 42), _fit_text_width(line, size, 650, 455), font=FG(size, 650), fill=CHAMPAGNE)
    y += 97
    grid = rows[:6]
    row_h = min(245, (1173 - y) / max(len(grid), 1))
    for label, value_a, value_b in grid:
        draw.line((54, y, 1026, y), fill=(32, 42, 60, 40), width=2)
        size = _fit_font_size(label, 38, 550, 960, 34)
        draw.text((65, y + 10), _fit_text_width(label, size, 550, 960), font=FG(size, 550), fill=TEXT_SECONDARY)
        for x, value in ((65, value_a), (554, value_b)):
            size = _fit_font_size(value, 47 if len(grid) > 3 else 60, 650, 455, 34)
            lines = _wrap_text(draw, value, FG(size, 650), 455)
            for i, line in enumerate(lines):
                draw.text((x, y + 53 + i * round(size * 1.06)), _fit_text_width(line, size, 650, 455), font=FG(size, 650), fill=TEXT_PRIMARY)
        y += row_h
    return _portrait_finish(img, draw, footer_note)


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
    portrait: bool = False,
    period_text: str | None = None,
    source_label: str | None = None,
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

    if portrait:
        return _render_rating_portrait(name=name, title_label=title_label,
            period_text=period_text or _og_year_label(year, year_label), unit=unit,
            rows=rows, total=total, order_label=order_label, count_template=count_template,
            scope_word=scope_word, locale=locale, source_label=source_label)

    L = _layout_rating(
        name=name, rows=rows, total=total, unit=unit,
        order_label=order_label, title_label=title_label,
        count_template=count_template, scope_word=scope_word, locale=locale,
    )

    img = _pearl_base().convert("RGB")
    draw = _raster_draw(img, "RGBA")
    margin = 64
    _brand_header(draw, period_text or _og_year_label(year, year_label))

    name_font = _font(L["title_size"], bold=True)
    y = 88
    for line in L["title_lines"]:
        draw.text((margin, y), line, font=name_font, fill=TEXT_PRIMARY)
        y += L["title_line_h"]

    top = rows[:8]
    if top:
        vmin = min(0.0, min(v for _n, v in top))
        vmax = max(0.0, max(v for _n, v in top))
        span = (vmax - vmin) or 1.0
        bar_font = _font(L["label_size"])
        val_font = _font(L["value_size"], bold=True)
        bar_area_x0 = margin + 330
        bar_area_x1 = WIDTH - margin - 170
        zero_x = bar_area_x0 + (bar_area_x1-bar_area_x0) * (-vmin) / span
        row_y = y + 20
        row_h = (HEIGHT - 70 - row_y) // len(top)
        bar_h = min(30, row_h - 12)
        for i, (region_name, value) in enumerate(top):
            draw.text((margin, row_y + (row_h - 26) // 2),
                      L["row_labels"][i], font=bar_font, fill=TEXT_PRIMARY)
            end_x = bar_area_x0 + (bar_area_x1-bar_area_x0) * (value-vmin) / span
            by = row_y + (row_h - bar_h) // 2
            draw.rounded_rectangle(
                [min(zero_x, end_x), by, max(zero_x, end_x), by + bar_h],
                radius=4, fill=(*CHAMPAGNE, 220) if value >= 0 else (82,119,143,230),
            )
            draw.line((zero_x, row_y, zero_x, row_y+row_h), fill=(32,42,60,45), width=1)
            draw.text((bar_area_x1 + 14, row_y + (row_h - 26) // 2),
                      L["row_values"][i], font=val_font, fill=TEXT_PRIMARY)
            row_y += row_h

    _brand_footer(draw, L["footer_note"] + (f" · {source_label}" if source_label else ""), size=L["footer_size"])

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
    portrait: bool = False,
    period_text: str | None = None,
    source_label: str | None = None,
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

    if portrait:
        return _render_rating_portrait(name=name, title_label=title_label,
            period_text=period_text or _og_year_label(year, year_label), unit=unit,
            rows=rows, total=total, order_label=order_label, count_template=count_template,
            scope_word=scope_word, locale=locale, source_label=source_label)

    L = _layout_rating(
        name=name, rows=rows, total=total, unit=unit,
        order_label=order_label, title_label=title_label,
        count_template=count_template, scope_word=scope_word, locale=locale,
    )

    img = _pearl_base().convert("RGB")
    draw = _raster_draw(img, "RGBA")
    margin = 64
    _brand_header(draw, period_text or _og_year_label(year, year_label))

    name_font = _font(L["title_size"], bold=True)
    y = 88
    for line in L["title_lines"]:
        draw.text((margin, y), line, font=name_font, fill=TEXT_PRIMARY)
        y += L["title_line_h"]

    top = rows[:8]
    if top:
        vmin = min(0.0, min(v for _n, v in top))
        vmax = max(0.0, max(v for _n, v in top))
        span = (vmax - vmin) or 1.0
        bar_font = _font(L["label_size"])
        val_font = _font(L["value_size"], bold=True)
        bar_area_x0 = margin + 330
        bar_area_x1 = WIDTH - margin - 170
        zero_x = bar_area_x0 + (bar_area_x1-bar_area_x0) * (-vmin) / span
        row_y = y + 20
        row_h = (HEIGHT - 70 - row_y) // len(top)
        bar_h = min(30, row_h - 12)
        for i, (country_name, value) in enumerate(top):
            draw.text((margin, row_y + (row_h - 26) // 2),
                      L["row_labels"][i], font=bar_font, fill=TEXT_PRIMARY)
            end_x = bar_area_x0 + (bar_area_x1-bar_area_x0) * (value-vmin) / span
            by = row_y + (row_h - bar_h) // 2
            draw.rounded_rectangle(
                [min(zero_x, end_x), by, max(zero_x, end_x), by + bar_h],
                radius=4, fill=(*CHAMPAGNE, 220) if value >= 0 else (82,119,143,230),
            )
            draw.line((zero_x, row_y, zero_x, row_y+row_h), fill=(32,42,60,45), width=1)
            draw.text((bar_area_x1 + 14, row_y + (row_h - 26) // 2),
                      L["row_values"][i], font=val_font, fill=TEXT_PRIMARY)
            row_y += row_h

    _brand_footer(draw, L["footer_note"] + (f" · {source_label}" if source_label else ""), size=L["footer_size"])

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
    portrait: bool = False,
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

    if portrait:
        return _render_items_portrait(title=title_label, eyebrow=date_text, subline="",
                                     items=items, footer_note=footer_note)

    img = _pearl_base().convert("RGB")
    draw = _raster_draw(img, "RGBA")
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
                               fill=(255, 255, 255, 220), outline=(255, 255, 255, 255), width=2)
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
    portrait: bool = False,
) -> bytes:
    """Сравнение двух регионов: таблица «показатель — A — B» (для /region-vs).

    Колонки не наезжают друг на друга: подписи и значения проходят через
    автоподбор кегля (_layout), при min-кегле остаётся пиксельная обрезка.
    (Единицы измерения компактизирует вызывающая сторона:
    «тысяч человек» → «тыс. чел.».)
    """
    if portrait:
        return _render_compare_portrait(name_a=name_a, name_b=name_b, rows=rows,
            eyebrow=eyebrow_label, separator=title_separator, footer_note=footer_note)

    L = _layout_region_vs(
        name_a=name_a, name_b=name_b, rows=rows, footer=footer_note,
        eyebrow=eyebrow_label, separator=title_separator,
    )

    img = _pearl_base().convert("RGB")
    draw = _raster_draw(img, "RGBA")
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
    count_template: str = "{count} показателей",
    footer_note: str = "источники и методология на странице",
    locale: str | None = None,
    portrait: bool = False,
) -> bytes:
    """Сводка страны для /og/world/{slug}.png: сетка ключевых значений.

    Текстовые параметры по умолчанию — русские; EN-вызов передаёт EN-строки
    (sitemap.py) целиком, чтобы не получить смесь языков на постере.
    """
    if portrait:
        return _render_items_portrait(title=title_template.format(country=country_name),
            eyebrow=eyebrow_label, subline=count_template.format(count=indicators_count),
            items=items, footer_note=footer_note)

    L = _layout_world_country(
        country=country_name,
        items=items,
        count_line=count_template.format(count=indicators_count),
        footer=footer_note,
        title_template=title_template,
    )

    img = _pearl_base().convert("RGB")
    draw = _raster_draw(img, "RGBA")
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
            fill=(255, 255, 255, 220),
            outline=(255, 255, 255, 255),
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
    return _DISK_DIR / (hashlib.md5(f"{OG_DESIGN_VERSION}:{code}".encode()).hexdigest() + ".png")


def _remember_og(code: str, png: bytes) -> None:
    """Apply both bounds to disk promotions as well as new renders."""
    with _CACHE_LOCK:
        _CACHE.pop(code, None)
        if len(png) > _CACHE_MAX_BYTES:
            return
        while _CACHE and (
            len(_CACHE) >= _CACHE_MAX
            or sum(len(entry[1]) for entry in _CACHE.values()) + len(png) > _CACHE_MAX_BYTES
        ):
            oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
            _CACHE.pop(oldest, None)
        _CACHE[code] = (time.monotonic(), png)


def cached_og(code: str) -> bytes | None:
    with _CACHE_LOCK:
        entry = _CACHE.get(code)
        if entry and time.monotonic() - entry[0] < _CACHE_TTL:
            return entry[1]
        _CACHE.pop(code, None)
    try:
        p = _disk_path(code)
        if p.exists() and time.time() - p.stat().st_mtime < _CACHE_TTL:
            png = p.read_bytes()
            _remember_og(code, png)
            return png
    except OSError:
        pass
    return None


def store_og(code: str, png: bytes) -> None:
    _remember_og(code, png)
    tmp: Path | None = None
    try:
        _DISK_DIR.mkdir(parents=True, exist_ok=True)
        destination = _disk_path(code)
        # Separate workers may render the same key concurrently. A shared
        # hash.tmp can be replaced while another writer still owns its inode.
        # Each writer closes its unique sibling before atomic publication.
        with tempfile.NamedTemporaryFile(
            dir=_DISK_DIR, prefix=f".{destination.stem}-", suffix=".tmp", delete=False,
        ) as handle:
            tmp = Path(handle.name)
            handle.write(png)
        tmp.replace(destination)
        tmp = None
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
    finally:
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
