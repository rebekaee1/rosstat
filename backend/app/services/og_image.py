"""Per-indicator OG-превью (PNG 1200×630) со спарклайном и актуальным значением.

Раздаётся как `https://forecasteconomy.com/og/{code}.png` (nginx → backend
`/api/v1/og-image/indicator/{code}.png`). Подключается в SSR через
`build_document(og_image=...)` — у каждой карточки своё превью в соцсетях,
мессенджерах и выдаче вместо одной общей картинки.

Рендер — Pillow + Inter (variable TTF в `app/assets/fonts/`): DM Sans с сайта
не содержит кириллицу, Inter — ближайший нейтральный гротеск с полной
кириллицей (OFL). Кэш в памяти процесса с TTL: данные меняются раз в день,
скрейпы превью редкие.
"""

from __future__ import annotations

import io
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
BG = (248, 249, 252)          # --color-obsidian
TEXT_PRIMARY = (26, 26, 46)   # --color-ivory
TEXT_SECONDARY = (26, 26, 46, 166)
CHAMPAGNE = (184, 148, 47)    # --color-champagne
LINE = (184, 148, 47)
GRID = (0, 0, 0, 20)

_FONT_PATH = Path(__file__).parent.parent / "assets" / "fonts" / "Inter-Variable.ttf"

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


def _sparkline(draw: ImageDraw.ImageDraw, values: list[float], box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    if len(values) < 2:
        return
    vmin, vmax = min(values), max(values)
    spread = (vmax - vmin) or 1.0
    n = len(values)
    points = [
        (
            x0 + (x1 - x0) * i / (n - 1),
            y1 - (y1 - y0) * (v - vmin) / spread,
        )
        for i, v in enumerate(values)
    ]
    # лёгкая сетка
    for frac in (0.0, 0.5, 1.0):
        y = y0 + (y1 - y0) * frac
        draw.line([(x0, y), (x1, y)], fill=GRID, width=1)
    draw.line(points, fill=LINE, width=5, joint="curve")
    # точка последнего значения
    px, py = points[-1]
    draw.ellipse([px - 9, py - 9, px + 9, py + 9], fill=CHAMPAGNE)


def render_indicator_og(
    *,
    code: str,
    name: str,
    value_text: str,
    date_text: str,
    values: list[float],
) -> bytes:
    """Собрать PNG. Чистая функция от данных — кэширование на вызывающей стороне."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    margin = 72
    # бренд-полоска
    draw.rectangle([0, 0, WIDTH, 8], fill=CHAMPAGNE)

    eyebrow_font = _font(26, bold=True)
    draw.text((margin, 56), "FORECAST ECONOMY", font=eyebrow_font, fill=CHAMPAGNE)

    name_font = _font(54, bold=True)
    lines = _wrap_text(draw, name, name_font, WIDTH - margin * 2)
    y = 110
    for line in lines:
        draw.text((margin, y), line, font=name_font, fill=TEXT_PRIMARY)
        y += 66

    value_font = _font(88, bold=True)
    draw.text((margin, y + 18), value_text, font=value_font, fill=TEXT_PRIMARY)
    date_font = _font(30)
    draw.text((margin, y + 128), date_text, font=date_font, fill=TEXT_SECONDARY)

    _sparkline(draw, values, (margin, 420, WIDTH - margin, 560))

    footer_font = _font(26)
    draw.text((margin, HEIGHT - 48), "forecasteconomy.com", font=footer_font, fill=TEXT_SECONDARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def cached_og(code: str) -> bytes | None:
    entry = _CACHE.get(code)
    if entry and time.monotonic() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def store_og(code: str, png: bytes) -> None:
    if len(_CACHE) >= _CACHE_MAX:
        oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
        _CACHE.pop(oldest, None)
    _CACHE[code] = (time.monotonic(), png)
