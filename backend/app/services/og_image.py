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

import hashlib
import io
import logging
import os
import random
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

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


def _brand_header(draw: ImageDraw.ImageDraw, eyebrow_extra: str | None = None) -> None:
    """Бренд-полоска + eyebrow — общая шапка всех OG-карточек."""
    margin = 64
    draw.rectangle([0, 0, WIDTH, 8], fill=CHAMPAGNE)
    eyebrow_font = _font(26, bold=True)
    eyebrow = "FORECAST ECONOMY"
    draw.text((margin, 44), eyebrow, font=eyebrow_font, fill=CHAMPAGNE)
    if eyebrow_extra:
        ew = draw.textlength(eyebrow, font=eyebrow_font)
        draw.text((margin + ew + 18, 44), f"· {eyebrow_extra}", font=eyebrow_font, fill=TEXT_SECONDARY)


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
) -> bytes:
    """Рейтинг регионов: горизонтальный барчарт топ-8 + бренд (для /region-rating).

    Самодостаточная картинка под Алису/Нейро: заголовок, год, лидеры со
    значениями, счётчик «из N регионов», домен.
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

    note = f"топ-{len(top)} из {total} регионов"
    if unit:
        note += f" · {unit}"
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

    _brand_footer(draw, "официальные данные · обновляется ежедневно")
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
    """Сравнение двух регионов: таблица «показатель · A · B» (для /region-vs).

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
        f"{indicators_count} показателей · Евростат",
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
