"""Автоподбор кегля на OG-постерах: ни один текст не выходит за ширину canvas.

Владелец (2026-08): «везде должно всё влезать и всё должно быть чётко и по
факту». Тест бьёт рендеры длинными реальными строками (длинные названия
индикаторов, длинные регионы, гигантские значения с единицами) и для каждого
рендера проверяет раскладку через общие функции _layout_* в og_image.py:
ни одна строка (включая перенос единицы на вторую строку) не шире доступной
полосы соответствующего блока. Ширины замеряются тем же шрифтом, который
выбран раскладкой (ImageFont.getlength), — падение теста означает фактическое
обрезание пикселей на постере.
"""

from PIL import ImageFont

from app.services.og_image import (
    WIDTH,
    FG,
    _layout,
    _layout_indicator,
    og_hero_number,
)

LONG_NAME = "Гармонизированный индекс потребительских цен"
LONG_REGION = "Ханты-Мансийский автономный округ — Югра"
LONG_VALUE = "13 149,8 тысяч человек"
LONG_MONEY = "1 431 498,7 млрд долларов"
LONG_NAME_EN = "Harmonised index of consumer prices"


def _measure(text: str, size: int, wght: int = 400) -> float:
    return FG(size, wght).getlength(text)


# ---------------------------------------------------------------- indicator J6


def test_indicator_layout_long_value_fits():
    for value_text in (LONG_VALUE, LONG_MONEY, "+0,54"):
        L = _layout_indicator(
            name=LONG_NAME,
            value_text=value_text,
            date_text="на 1 августа 2026",
            subtitle="индекс потребительских цен, изменение за месяц",
            context_pill="Годовая инфляция — 6,0%",
            unit_suffix=None,
            period_text="Июль 2026",
        )
        margin = 56
        limit = WIDTH - margin - 24
        n1, n2 = L["value_lines"]
        assert _measure(n1, L["value_size"], 800) <= limit, value_text
        if n2:
            assert _measure(n2, L["value_unit_size"], 700) <= limit, value_text
        for line in L["title_lines"]:
            assert _measure(line, L["title_size"], 800) <= limit, line
        assert _measure(L["subtitle"], L["subtitle_size"], 500) <= limit
        assert _measure(L["context_pill"], L["context_pill_size"], 800) <= limit
        # перенос единицы происходит, когда число с ней не влезает одной строкой
        if _measure(value_text, L["value_size"], 800) > limit:
            assert n2, f"единица не перенесена на вторую строку: {value_text}"


def test_indicator_layout_default_scale_untouched():
    """Короткие привычные строки не должны деградировать: число 200, заголовок 46."""
    L = _layout_indicator(
        name="Инфляция",
        value_text="+0,54",
        date_text="на 1 августа 2026",
        subtitle=None,
        context_pill="Годовая инфляция — 6,0%",
        unit_suffix=None,
        period_text="Июль 2026",
    )
    assert L["value_size"] == 200
    assert L["title_size"] == 46
    assert L["subtitle"] == ""
    assert L["value_lines"] == ("+0,54", None)


def test_indicator_layout_unit_wrap_two_lines():
    """«13 149,8 тысяч человек»: число — первой строкой, единица — второй."""
    L = _layout_indicator(
        name=LONG_NAME,
        value_text=LONG_VALUE,
        date_text="2023",
        subtitle=None,
        context_pill=None,
        unit_suffix=None,
        period_text="2023 год",
    )
    num, unit = L["value_lines"]
    assert num == "13 149,8"
    assert unit == "тысяч человек"
    margin = 56
    limit = WIDTH - margin - 24
    assert _measure(num, L["value_size"], 800) <= limit
    assert _measure(unit, L["value_unit_size"], 700) <= limit


def test_indicator_layout_pill_grows_down_not_offscreen():
    """Пилюля, не влезающая справа от числа, уходит вниз и остаётся в кадре."""
    L = _layout_indicator(
        name="Инфляция",
        value_text="+0,54",
        date_text="на 1 августа 2026",
        subtitle=None,
        context_pill="Годовая инфляция — 6,0%",
        unit_suffix=None,
        period_text="Июль 2026",
    )
    x, _y = L["context_pill_xy"]
    assert 56 <= x
    assert x + L["context_pill_w"] <= WIDTH - 56


def test_indicator_layout_pill_fits_width():
    L = _layout_indicator(
        name="Инфляция",
        value_text="+0,54",
        date_text="на 1 августа 2026",
        subtitle=None,
        context_pill="Годовая инфляция — 6,0%",
        unit_suffix=None,
        period_text="Июль 2026",
    )
    px, _ = L["context_pill_xy"]
    assert px + L["context_pill_w"] <= WIDTH - 56


def test_layout_dispatch_full_indicator():
    """Общий диспетчер _layout распознаёт indicator-набор параметров."""
    L = _layout(
        name=LONG_NAME,
        value_text=LONG_MONEY,
        date_text="на 1 августа 2026",
        subtitle=None,
        context_pill=None,
        unit_suffix=None,
        period_text="Июль 2026",
    )
    margin = 56
    limit = WIDTH - margin - 24
    n1, n2 = L["value_lines"]
    assert _measure(n1, L["value_size"], 800) <= limit
    if n2:
        assert _measure(n2, L["value_unit_size"], 700) <= limit


# ---------------------------------------------------------------- ratings


def test_rating_layout_long_rows_fit():
    rows = [
        (LONG_REGION, 13_149.8),
        ("Республика Саха (Якутия)", 9_812.4),
        ("Московская область", 8_103.2),
    ]
    layout = _layout(name=LONG_NAME, rows=rows, total=85, unit="человек")
    assert layout["title_lines"], "заголовок рейтинга не разложен"
    for line in layout["title_lines"]:
        assert _measure(line, layout["title_size"], 700) <= WIDTH - 128
    margin = 64
    label_limit = 330 - 16
    for i, (label, _v) in enumerate(rows):
        assert _measure(layout["row_labels"][i], layout["label_size"]) <= label_limit, label
    assert _measure(layout["footer_note"], layout["footer_size"]) <= WIDTH - 128


def test_rating_layout_long_unit_note_fits():
    layout = _layout(
        name=LONG_NAME,
        rows=[(LONG_REGION, 1.0)],
        total=85,
        unit="человек; изменение к предыдущему периоду, в процентах",
    )
    assert _measure(layout["footer_note"], layout["footer_size"]) <= WIDTH - 128


def test_world_rating_layout_long_rows_fit():
    rows = [
        ("Сент-Китс и Невис", 101.4),
        ("Босния и Герцеговина", 100.9),
        ("Северная Македония", 100.2),
    ]
    layout = _layout(
        name=LONG_NAME_EN, rows=rows, total=30,
        unit="%, year-over-year change", kind="countries",
    )
    for line in layout["title_lines"]:
        assert _measure(line, layout["title_size"], 700) <= WIDTH - 128
    for i, (label, _v) in enumerate(rows):
        assert _measure(layout["row_labels"][i], layout["label_size"]) <= 330 - 16
    assert _measure(layout["footer_note"], layout["footer_size"]) <= WIDTH - 128


# ---------------------------------------------------------------- today hub


def test_today_hub_layout_long_items_fit():
    layout = _layout(
        items=[
            ("Ключевая ставка ЦБ", "16,50%"),
            ("Средняя зарплата, рублей в месяц", "87 952"),
            ("Ставка по ипотеке, среднегодовая", "21,4%"),
        ],
        title="Экономика России сегодня",
        footer="официальные данные — обновление по мере публикации",
    )
    cell_w = (WIDTH - 64 * 2 - 24) // 2
    assert _measure(layout["title"], layout["title_size"], 700) <= WIDTH - 128
    for i in range(len(layout["items"])):
        lbl, val = layout["items"][i]
        assert _measure(lbl, layout["label_size"]) <= cell_w - 40, lbl
        assert _measure(val, layout["value_size"], 700) <= cell_w - 40, val
    assert _measure(layout["footer_note"], layout["footer_size"]) <= WIDTH - 128


# ---------------------------------------------------------------- region vs


def test_region_vs_layout_long_names_fit():
    layout = _layout(
        name_a=LONG_REGION,
        name_b="Республика Северная Осетия — Алания",
        vs_rows=[
            ("Численность населения на 1 января, тысяч человек", "13 149,8", "1 665,3"),
            ("Среднедушевые денежные доходы в месяц", "87 952,1", "34 118,6"),
        ],
        eyebrow="сравнение регионов",
        footer="данные Росстата",
    )
    for line in layout["title_lines"]:
        assert _measure(line, layout["title_size"], 700) <= WIDTH - 128
    col_w = 260
    metric_limit = 600 - 64 - 24
    assert _measure(layout["head_a"], layout["head_size"], 700) <= col_w
    assert _measure(layout["head_b"], layout["head_size"], 700) <= col_w
    for i in range(len(layout["rows"])):
        m, a, b = layout["rows"][i]
        assert _measure(m, layout["row_size"]) <= metric_limit, m
        assert _measure(a, layout["value_size"], 700) <= col_w
        assert _measure(b, layout["value_size"], 700) <= col_w


# ---------------------------------------------------------------- world country


def test_world_country_layout_long_items_fit():
    layout = _layout(
        country="Германия",
        items=[
            ("Валовой внутренний продукт на душу населения", "48 717,5"),
            ("Гармонизированный индекс потребительских цен", "102,3"),
            ("Уровень безработицы, сглаженная", "6,2%"),
        ],
        count_line="18 показателей — Евростат",
        footer="официальные данные Евростата",
        eyebrow="мировая экономика",
    )
    cell_w = (WIDTH - 64 * 2 - 24) // 2
    for i, (label, value) in enumerate(layout["items"]):
        assert _measure(label, layout["label_size"]) <= cell_w - 40, label
        assert _measure(value, layout["value_size"], 700) <= cell_w - 40, value
    assert _measure(layout["count_line"], layout["sub_size"]) <= WIDTH - 128
    for line in layout["title_lines"]:
        assert _measure(line, layout["title_size"], 700) <= WIDTH - 128
    assert _measure(layout["footer_note"], layout["footer_size"]) <= WIDTH - 128


# ---------------------------------------------------------------- PNG smoke


def test_indicator_png_with_long_strings_smoke():
    """Рендер не падает и выдаёт PNG при самых длинных входах."""
    from app.services.og_image import render_indicator_og

    png = render_indicator_og(
        code="smoke",
        name=f"{LONG_NAME} — {LONG_REGION}",
        value_text=LONG_VALUE,
        date_text="на 1 января 2023",
        values=[12_900.0, 13_000.5, 13_149.8],
        subtitle="численность населения, оценка на 1 января",
        context_pill="Годовая инфляция — 6,0%",
        unit_suffix=None,
        period_text="2023 год",
        x_labels=("2015", "2023"),
    )
    assert png[:4] == b"\x89PNG"


def test_og_hero_number_plus_only_on_change_series():
    assert og_hero_number("key-rate", 21.0) == "21,0"
    assert og_hero_number("key-rate", 21.0, locale="en") == "21.0"
    assert og_hero_number("cpi", 0.54).startswith("+")
    assert og_hero_number("key-rate", -1.2).startswith("\u2212")
