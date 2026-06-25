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


def _sparkline(
    draw: ImageDraw.ImageDraw,
    values: list[float],
    box: tuple[int, int, int, int],
    *,
    x_labels: tuple[str, str] | None = None,
) -> None:
    """Линейный график с осевыми подписями (min/max по Y, крайние метки по X).

    Подписи делают картинку самодостаточным «графиком», а не абстрактным
    спарклайном: Алиса/Нейро берут её со страницы и показывают в ответе, где
    она должна объяснять себя сама (значения, период, бренд).
    """
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

    # Осевые подписи: max сверху-слева, min снизу-слева над линией оси.
    axis_font = _font(24)
    draw.text((x0 + 6, y0 - 30), _fmt_axis(vmax), font=axis_font, fill=TEXT_SECONDARY)
    draw.text((x0 + 6, y1 + 8), _fmt_axis(vmin), font=axis_font, fill=TEXT_SECONDARY)
    if x_labels:
        left, right = x_labels
        draw.text((x0 + 6, y1 + 36), left, font=axis_font, fill=TEXT_SECONDARY)
        rw = draw.textlength(right, font=axis_font)
        draw.text((x1 - rw - 6, y1 + 36), right, font=axis_font, fill=TEXT_SECONDARY)


def render_indicator_og(
    *,
    code: str,
    name: str,
    value_text: str,
    date_text: str,
    values: list[float],
    period_text: str | None = None,
    x_labels: tuple[str, str] | None = None,
) -> bytes:
    """Собрать PNG. Чистая функция от данных — кэширование на вызывающей стороне.

    `period_text` — необязательная метка периода (например «2024 год») для
    годовых landing-страниц: показывается рядом с брендом, чтобы у каждой
    годовой картинки был свой контекст в выдаче и ответах Алисы.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    margin = 72
    # бренд-полоска
    draw.rectangle([0, 0, WIDTH, 8], fill=CHAMPAGNE)

    eyebrow_font = _font(26, bold=True)
    eyebrow = "FORECAST ECONOMY"
    draw.text((margin, 56), eyebrow, font=eyebrow_font, fill=CHAMPAGNE)
    if period_text:
        ew = draw.textlength(eyebrow, font=eyebrow_font)
        draw.text((margin + ew + 18, 56), f"· {period_text}", font=eyebrow_font, fill=TEXT_SECONDARY)

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

    _sparkline(draw, values, (margin, 400, WIDTH - margin, 526), x_labels=x_labels)

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
