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
TEXT_TERTIARY = (26, 26, 46, 120)
CHAMPAGNE = (184, 148, 47)    # --color-champagne
LINE = (184, 148, 47)
AREA_FILL = (184, 148, 47, 38)   # полупрозрачная заливка под линией
GRID = (0, 0, 0, 22)
AXIS = (0, 0, 0, 60)
WATERMARK = (26, 26, 46, 34)

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
) -> bytes:
    """Собрать PNG. Чистая функция от данных — кэширование на вызывающей стороне.

    `period_text` — необязательная метка периода (например «2024 год») для
    годовых landing-страниц: показывается рядом с брендом, чтобы у каждой
    годовой картинки был свой контекст в выдаче и ответах Алисы.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    margin = 64
    # бренд-полоска
    draw.rectangle([0, 0, WIDTH, 8], fill=CHAMPAGNE)

    eyebrow_font = _font(26, bold=True)
    eyebrow = "FORECAST ECONOMY"
    draw.text((margin, 44), eyebrow, font=eyebrow_font, fill=CHAMPAGNE)
    if period_text:
        ew = draw.textlength(eyebrow, font=eyebrow_font)
        draw.text((margin + ew + 18, 44), f"· {period_text}", font=eyebrow_font, fill=TEXT_SECONDARY)

    name_font = _font(50, bold=True)
    lines = _wrap_text(draw, name, name_font, WIDTH - margin * 2)
    y = 90
    for line in lines:
        draw.text((margin, y), line, font=name_font, fill=TEXT_PRIMARY)
        y += 60

    # Компактная строка: последнее значение · дата (вместо гигантского числа,
    # чтобы график занимал основную площадь — вид «скачанного PNG»).
    value_font = _font(46, bold=True)
    draw.text((margin, 212), value_text, font=value_font, fill=TEXT_PRIMARY)
    vw = draw.textlength(value_text, font=value_font)
    date_font = _font(28)
    draw.text((margin + vw + 18, 226), f"· {date_text}", font=date_font, fill=TEXT_SECONDARY)

    # Большой area-график. Левый гаттер (margin..px0) — под подписи значений,
    # нижний гаттер (py1..) — под даты. Так подписи не пересекаются с линией.
    chart_box = (margin + 92, 300, WIDTH - margin, 540)

    # Водяной знак: бренд по центру графика, едва заметный.
    wm_font = _font(58, bold=True)
    wm = "forecasteconomy.com"
    ww = draw.textlength(wm, font=wm_font)
    cx = (chart_box[0] + chart_box[2]) / 2 - ww / 2
    cy = (chart_box[1] + chart_box[3]) / 2 - 36
    draw.text((cx, cy), wm, font=wm_font, fill=WATERMARK)

    _area_chart(draw, values, chart_box, x_labels=x_labels)

    footer_font = _font(26)
    draw.text((margin, HEIGHT - 42), "forecasteconomy.com", font=footer_font, fill=TEXT_TERTIARY)

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
