"""График для Telegram-бота (ADR-0027, 08.11.2026): содержательный, в фирменном стиле, с водяным знаком.

Почему не картинка сайта (`/og/russia/<код>.png`): у дневных рядов она охватывает ~2 месяца и выглядит пустой,
а в чате человеку нужен смысл — где сейчас, где было год назад, куда идёт наш расчёт и с чем сравнить.

Что рисуется (Pillow, без новых зависимостей; холст 1600×1000 — 2× от показа, принцип «никакого пикселя»):
- ряд за окно (недельные и месячные — 3 года, дневные — 18 месяцев, дневные прорежены до недели);
- последняя точка (золотое кольцо), точка «год назад» с подписью, наш расчёт одной точкой пунктиром (без диапазона);
- линия сравнения по делу: цель ЦБ 4 % у инфляции, инфляция у ставки и вкладов, ключевая ставка у ипотеки;
- светлый холодный фон со светом (не пустой), без рамок, золото — тонким акцентом;
- водяной знак: крупная полупрозрачная F за графиком и словесный знак forecasteconomy внизу справа.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date

from PIL import Image, ImageDraw, ImageFilter

from app.services.og_image import CHAMPAGNE, FG, TEXT_PRIMARY, _spline

W, H = 1600, 1000
BG_TOP = (246, 247, 250)
BG_BOTTOM = (232, 236, 243)
INK = TEXT_PRIMARY            # графит
BLUE = (37, 64, 128)          # глубокий синий — основной ряд
BLUE_FILL = (37, 64, 128, 26)
MUTED = (112, 122, 146)
GRID = (205, 211, 224)
GOLD = CHAMPAGNE
COMPARE = (128, 136, 158)

_MONTHS_SHORT = ("янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")


@dataclass
class Series:
    title: str
    unit: str
    source: str
    points: list[tuple[date, float]]
    forecast: tuple[date, float] | None = None
    year_ago: tuple[date, float] | None = None
    compare_label: str | None = None
    compare_points: list[tuple[date, float]] | None = None
    target: tuple[str, float] | None = None   # горизонтальная линия, например («цель ЦБ», 4.0)
    is_rate: bool = False
    step: bool = False          # ступенчатый ряд (ключевая ставка): без сглаживания
    unit_note: str = ""         # подпись под заголовком, например «% за год»
    monthly: bool = False       # месячный ряд: «за авг 2026», а не «на 1 авг 2026»


def _num(v: float, digits: int = 2) -> str:
    s = f"{v:,.{digits}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def _short_date(d: date) -> str:
    return f"{_MONTHS_SHORT[d.month - 1]} {d.year}"


def _background() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG_TOP + (255,))
    grad = Image.linear_gradient("L").resize((W, H))
    bottom = Image.new("RGBA", (W, H), BG_BOTTOM + (255,))
    img = Image.composite(bottom, img, grad)
    # Мягкий холодный свет справа сверху: фон не пустой, но не спорит с данными.
    # Размываем только маску (L), иначе прозрачный чёрный по краям даёт серое пятно.
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse((W * 0.5, -H * 0.6, W * 1.3, H * 0.5), fill=170)
    img.paste(Image.new("RGBA", (W, H), (255, 255, 255, 255)), (0, 0), mask.filter(ImageFilter.GaussianBlur(140)))
    # Тонкая холодная полоса света по диагонали — «грань стекла».
    edge = Image.new("L", (W, H), 0)
    ImageDraw.Draw(edge).polygon([(W * 0.62, 0), (W * 0.66, 0), (W * 0.36, H), (W * 0.32, H)], fill=60)
    img.paste(Image.new("RGBA", (W, H), (255, 255, 255, 255)), (0, 0), edge.filter(ImageFilter.GaussianBlur(30)))
    return img


def _emblem_mask(scale: float) -> tuple[Image.Image, Image.Image]:
    """Знак F маской (как в шапке сайта: M8 38V17Q8 5 21 5H34V13H22Q17 13 17 19V20H31V28H17V38Z + квадрат).
    Рисуем в L-маске, чтобы полупрозрачность была ровной, без наложений."""
    size = (int(40 * scale), int(42 * scale))
    ink = Image.new("L", size, 0)
    d = ImageDraw.Draw(ink)

    def p(px: float, py: float) -> tuple[float, float]:
        return px * scale, py * scale
    d.pieslice((*p(8, 5), *p(34, 31)), 180, 270, fill=255)
    d.rectangle((*p(21, 5), *p(34, 13)), fill=255)
    d.rectangle((*p(8, 18), *p(17, 38)), fill=255)
    d.rectangle((*p(17, 13), *p(22, 19)), fill=0)
    d.pieslice((*p(17, 13), *p(27, 23)), 180, 270, fill=0)
    d.rectangle((*p(21, 13), *p(34, 19)), fill=0)
    d.rectangle((*p(17, 20), *p(31, 28)), fill=255)
    gold = Image.new("L", size, 0)
    ImageDraw.Draw(gold).rectangle((*p(29, 30), *p(35, 38)), fill=255)
    return ink, gold


def _stamp(img: Image.Image, x: int, y: int, scale: float, ink_alpha: int, gold_alpha: int) -> None:
    ink, gold = _emblem_mask(scale)
    img.paste(Image.new("RGBA", ink.size, INK + (255,)), (x, y), ink.point(lambda v: v * ink_alpha // 255))
    img.paste(Image.new("RGBA", gold.size, GOLD + (255,)), (x, y), gold.point(lambda v: v * gold_alpha // 255))


def _watermark(img: Image.Image) -> None:
    _stamp(img, 1030, 300, 13.0, 11, 22)          # крупная F за графиком — едва заметно
    d = ImageDraw.Draw(img)
    x, y = W - 470, H - 78
    _stamp(img, x, y - 6, 1.05, 200, 235)
    d.text((x + 48, y), "forecast", font=FG(30, 750), fill=INK + (200,))
    wdt = d.textlength("forecast", font=FG(30, 750))
    d.text((x + 48 + wdt, y), "economy", font=FG(30, 400), fill=INK + (200,))


def render_chart(s: Series) -> bytes:
    img = _background()
    _watermark(img)
    d = ImageDraw.Draw(img)

    # --- шапка ---
    d.text((90, 70), s.title, font=FG(58, 760), fill=INK)
    note = s.unit_note or s.unit
    d.text((92, 146), f"{note} · {s.source}" if note else s.source, font=FG(30, 450), fill=MUTED)
    last_d, last_v = s.points[-1]
    sign = "%" if s.unit.startswith("%") else ("₽" if s.unit.startswith("₽") else ("$" if s.unit.startswith("$") else ""))
    value = f"{_num(last_v)} {sign}".strip()
    vf = FG(88, 780)
    vw = d.textlength(value, font=vf)
    d.text((W - 90 - vw, 52), value, font=vf, fill=BLUE)
    sub = (f"за {_MONTHS_SHORT[last_d.month - 1]} {last_d.year}" if s.monthly
           else f"на {last_d.day} {_MONTHS_SHORT[last_d.month - 1]} {last_d.year}")
    if s.year_ago:
        yv = s.year_ago[1]
        if s.is_rate:
            ch = last_v - yv
            sub += f" · за год {'+' if ch > 0 else ''}{_num(ch)} пункта"
        elif yv:
            ch = (last_v / yv - 1) * 100
            sub += f" · за год {'+' if ch > 0 else ''}{_num(ch, 1)} %"
    sf = FG(30, 500)
    d.text((W - 90 - d.textlength(sub, font=sf), 160), sub, font=sf, fill=MUTED)

    # --- область графика ---
    left, top, right, bottom = 170, 250, W - 110, H - 150
    vals = [v for _, v in s.points]
    extra = [v for _, v in (s.compare_points or [])] + ([s.forecast[1]] if s.forecast else [])
    extra += [s.target[1]] if s.target else []
    lo, hi = min(vals + extra), max(vals + extra)
    pad = (hi - lo) * 0.12 or abs(hi) * 0.05 or 1
    lo, hi = lo - pad, hi + pad
    d0 = s.points[0][0].toordinal()
    d1 = (s.forecast[0] if s.forecast else last_d).toordinal()
    span = max(1, d1 - d0)

    def xy(dt: date, v: float) -> tuple[float, float]:
        return (left + (dt.toordinal() - d0) / span * (right - left),
                bottom - (v - lo) / (hi - lo) * (bottom - top))

    # сетка без рамки: 4 тонкие горизонтали и подписи слева
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        y = bottom - (bottom - top) * i / 4
        d.line((left, y, right, y), fill=GRID + (255,), width=2)
        lab = _num(v, 1 if abs(hi - lo) < 20 else 0)
        d.text((left - 18 - d.textlength(lab, font=FG(26, 450)), y - 16), lab, font=FG(26, 450), fill=MUTED)
    # подписи времени: начало, середина, конец
    for dt in (s.points[0][0], s.points[len(s.points) // 2][0], last_d):
        x, _ = xy(dt, lo)
        lab = _short_date(dt)
        tw = d.textlength(lab, font=FG(26, 500))
        d.text((min(max(x - tw / 2, left), right - tw), bottom + 20), lab, font=FG(26, 500), fill=MUTED)

    # цель (пунктир золотом) и линия сравнения (тонкий графит)
    if s.target:
        _, ty = xy(s.points[0][0], s.target[1])
        for x in range(left, right, 26):
            d.line((x, ty, min(x + 14, right), ty), fill=GOLD + (220,), width=3)
        d.text((left + 8, ty - 40), f"{s.target[0]} {_num(s.target[1], 0)} %", font=FG(26, 600), fill=GOLD)
    if s.compare_points and len(s.compare_points) > 1:
        cp = [xy(dt, v) for dt, v in s.compare_points if dt.toordinal() >= d0]
        if len(cp) > 1:
            d.line(_spline(cp, 6), fill=COMPARE + (255,), width=3, joint="curve")
            cx, cy = cp[-1]
            lab = s.compare_label or ""
            lw = d.textlength(lab, font=FG(24, 600))
            # Подпись над концом линии, внутри области графика (у правого края обрезалась).
            d.text((min(cx - lw / 2, right - lw), cy - 42), lab, font=FG(24, 600), fill=COMPARE)

    # основной ряд: заливка + линия
    pts = [xy(dt, v) for dt, v in s.points]
    if s.step:
        line = []
        for (x0, y0), (x1, _y1) in zip(pts, pts[1:]):
            line += [(x0, y0), (x1, y0)]
        line.append(pts[-1])
    else:
        line = _spline(pts, 6) if len(pts) > 2 else pts
    fill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(fill).polygon(line + [(line[-1][0], bottom), (line[0][0], bottom)], fill=BLUE_FILL)
    img.alpha_composite(fill)
    d = ImageDraw.Draw(img)
    d.line(line, fill=BLUE + (255,), width=6, joint="curve")

    # год назад
    if s.year_ago:
        yx, yy = xy(*s.year_ago)
        d.ellipse((yx - 11, yy - 11, yx + 11, yy + 11), fill=BG_TOP + (255,), outline=BLUE + (255,), width=4)
        lab = f"год назад {_num(s.year_ago[1])}"
        d.text((yx - d.textlength(lab, font=FG(26, 600)) / 2, yy - 52), lab, font=FG(26, 600), fill=INK)

    # наш расчёт — одной точкой
    lx, ly = pts[-1]
    if s.forecast:
        fx, fy = xy(*s.forecast)
        steps = 10
        for i in range(0, steps, 2):
            a, b = i / steps, (i + 1) / steps
            d.line((lx + (fx - lx) * a, ly + (fy - ly) * a, lx + (fx - lx) * b, ly + (fy - ly) * b),
                   fill=GOLD + (255,), width=5)
        d.ellipse((fx - 12, fy - 12, fx + 12, fy + 12), fill=GOLD + (255,))
        lab = f"наш расчёт {_num(s.forecast[1])}"
        tw = d.textlength(lab, font=FG(26, 650))
        d.text((min(fx - tw / 2, right - tw), fy + 22), lab, font=FG(26, 650), fill=GOLD)

    # последняя точка: синий центр, золотое кольцо
    d.ellipse((lx - 17, ly - 17, lx + 17, ly + 17), fill=BG_TOP + (255,), outline=GOLD + (255,), width=5)
    d.ellipse((lx - 8, ly - 8, lx + 8, ly + 8), fill=BLUE + (255,))

    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
