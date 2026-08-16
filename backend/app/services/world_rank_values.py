"""Сопоставимые значения для карты и рейтинга стран.

Уровень индекса с разными базовыми периодами сравнивать нельзя: база сокращается
только в относительных изменениях. Здесь — разбор базы из метаданных ряда,
режим level/yoy и годовые срезы для choropleth/таблицы.
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Literal, Mapping, Sequence

from app.services.world_view_modes import mode_unit, transform_yoy

Series = list[tuple[date, float]]
RankMode = Literal["level", "yoy"]

# Доля от пикового покрытия по годам: год по умолчанию должен покрывать
# существенную часть стран, а не «хвост» из нескольких ранних публикаций.
DEFAULT_YEAR_COVERAGE_SHARE = 0.5
DEFAULT_YEAR_MIN_COUNTRIES = 8

_YOY_UNIT = "изменение за год, %"
_YOY_PERIOD_METHOD = (
    "Изменение к тому же периоду прошлого года; "
    "для каждого календарного года — последнее доступное наблюдение"
)
_LEVEL_PERIOD_METHOD = "Последнее опубликованное значение в каждом календарном году"

# Цены: даже при одинаковой базе Евростата на карте/в рейтинге показываем
# инфляцию — это то, что ищут, и это остаётся верным после подмешивания
# национальных рядов с другой базой.
_FORCE_YOY_CONCEPTS = frozenset({"hicp-index"})


def looks_like_index(unit: str | None, unit_ru: str | None) -> bool:
    u = (unit or "").strip().upper().replace("-", "_")
    ru = (unit_ru or "").strip().lower()
    if re.fullmatch(r"I\d{2,4}", u) or u in {"INDEX", "IX", "I"}:
        return True
    if "индекс" in ru:
        return True
    if re.search(r"=\s*100", ru):
        return True
    return False


def index_base_key(
    unit: str | None,
    unit_ru: str | None,
    slice_json: Mapping | None = None,
) -> str | None:
    """Канонический ключ базового периода индекса или None, если ряд не индекс.

    Неизвестный индекс (есть признак индекса, но базы в метаданных нет) →
    ``__unknown__``: его нельзя смешивать с известной базой на уровне.
    """
    if not looks_like_index(unit, unit_ru):
        return None

    sl = slice_json or {}
    for key in ("base_year", "base", "index_base", "ref_period"):
        raw = sl.get(key)
        if raw is None or str(raw).strip() == "":
            continue
        normalized = _normalize_base_token(str(raw))
        if normalized:
            return normalized

    u = (unit or "").strip().upper().replace("-", "_")
    m = re.fullmatch(r"I(\d{2})", u)
    if m:
        yy = int(m.group(1))
        return str(2000 + yy if yy < 80 else 1900 + yy)
    m = re.fullmatch(r"I(\d{4})", u)
    if m:
        return m.group(1)

    ru = (unit_ru or "").strip().lower().replace("–", "-").replace("—", "-")
    # «1982-84 = 100», «2011-12 = 100», «2015 = 100»
    m = re.search(
        r"(19|20)\d{2}\s*(?:-|/)\s*(?:\d{2}|(?:19|20)\d{2})\s*=\s*100",
        ru,
    )
    if m:
        return _normalize_base_token(m.group(0).split("=")[0])
    m = re.search(r"((?:19|20)\d{2})\s*=\s*100", ru)
    if m:
        return m.group(1)
    # «2-я половина июля 2018 = 100»
    m = re.search(r"((?:19|20)\d{2})\s*=\s*100", ru.replace("года", ""))
    if m:
        return m.group(1)

    return "__unknown__"


def _normalize_base_token(raw: str) -> str | None:
    text = (
        raw.strip()
        .lower()
        .replace("–", "-")
        .replace("—", "-")
        .replace(" ", "")
        .replace("=100", "")
    )
    if not text:
        return None
    m = re.fullmatch(r"(19|20)(\d{2})-(\d{2})", text)
    if m:
        century, a, b = m.group(1), m.group(2), m.group(3)
        return f"{century}{a}-{century}{b}" if len(b) == 2 and int(b) > 12 else f"{century}{a}-{b}"
    m = re.fullmatch(r"(19|20)\d{2}", text)
    if m:
        return text
    m = re.search(r"(19|20)\d{2}", text)
    return m.group(0) if m else text


def index_bases_mixed(
    members: Sequence[tuple[object, object]],
) -> bool:
    """True, если среди рядов есть индексы с разными (или неизвестными) базами."""
    keys: set[str] = set()
    for _country, indicator in members:
        key = index_base_key(
            getattr(indicator, "unit", None),
            getattr(indicator, "unit_ru", None),
            getattr(indicator, "slice_json", None),
        )
        if key is None:
            continue
        keys.add(key)
        if len(keys) > 1:
            return True
        if key == "__unknown__" and len(members) > 1:
            # Один неизвестный среди нескольких рядов — не доказываем сопоставимость уровня.
            # Если все неизвестные схлопнулись в один ключ — всё равно смешанность с
            # «известными» уже поймана выше; чисто unknown×N считаем несопоставимым.
            pass
    if "__unknown__" in keys and len(keys) == 1:
        # Несколько индексов без явной базы: базы могут отличаться — уровень закрыт.
        index_count = sum(
            1
            for _, ind in members
            if looks_like_index(getattr(ind, "unit", None), getattr(ind, "unit_ru", None))
        )
        return index_count > 1
    return len(keys) > 1


def ranking_value_mode(
    concept_slug: str,
    members: Sequence[tuple[object, object]],
) -> RankMode:
    if concept_slug in _FORCE_YOY_CONCEPTS:
        return "yoy"
    if index_bases_mixed(members):
        return "yoy"
    return "level"


def ranking_public_unit(mode: RankMode, concept_unit: str) -> str:
    if mode == "yoy":
        return _YOY_UNIT
    return concept_unit


def ranking_period_method(mode: RankMode) -> str:
    return _YOY_PERIOD_METHOD if mode == "yoy" else _LEVEL_PERIOD_METHOD


def ranking_display_name(mode: RankMode, concept_slug: str, concept_name: str) -> str:
    if mode == "yoy" and concept_slug == "hicp-index":
        return "Изменение потребительских цен за год"
    return concept_name


# Родительный падеж для заголовка «Рейтинг стран по …».
WORLD_RATING_QUERY_NAMES: dict[str, str] = {
    "hicp-index": "изменению потребительских цен за год",
    "unemployment-rate": "уровню безработицы",
    "budget-balance-gdp": "сальдо бюджета",
    "population": "численности населения",
    "long-term-interest-rate": "доходности долгосрочных государственных облигаций",
    "activity-rate": "уровню экономической активности",
    "gdp-per-capita-eu": "ВВП на душу относительно среднего по ЕС",
}


def world_rating_title(concept_slug: str, public_name: str, year: int | None) -> str:
    """Единый заголовок SSR и CSR для страницы рейтинга."""
    query_name = WORLD_RATING_QUERY_NAMES.get(concept_slug, public_name.lower())
    head = f"Рейтинг стран по {query_name}"
    if year is None:
        return head
    if query_name.rstrip().endswith("за год"):
        return f"{head}, {year}"
    return f"{head} за {year} год"


def apply_rank_series(series: Series, mode: RankMode) -> Series:
    if mode == "yoy":
        return transform_yoy(series)
    return sorted(((d, float(v)) for d, v in series), key=lambda p: p[0])


def latest_rank_point(series: Series, mode: RankMode) -> tuple[date, float] | None:
    transformed = apply_rank_series(series, mode)
    if not transformed:
        return None
    point_date, value = transformed[-1]
    if mode == "level" and value == 0:
        return None
    return point_date, float(value)


def yearly_last_points(
    series: Series,
    mode: RankMode,
) -> dict[int, tuple[date, float]]:
    """Последняя точка каждого календарного года после применения режима."""
    out: dict[int, tuple[date, float]] = {}
    for point_date, value in apply_rank_series(series, mode):
        if mode == "level" and value == 0:
            continue
        year = point_date.year
        prev = out.get(year)
        if prev is not None and prev[0] >= point_date:
            continue
        out[year] = (point_date, float(value))
    return out


def resolve_default_coverage_year(
    years: Sequence[int],
    values_by_year: Mapping[str, Mapping],
    *,
    share: float = DEFAULT_YEAR_COVERAGE_SHARE,
    min_countries: int = DEFAULT_YEAR_MIN_COUNTRIES,
) -> int | None:
    """Последний год, где есть данные у существенной доли стран.

    Порог = max(min_countries, ceil(peak_coverage * share)). Пик берём по
    годам ряда: так «дырявый» текущий год не перекрывает полный прошлый.
    """
    list_years = list(years)
    if not list_years:
        return None
    peak = max(len(values_by_year.get(str(year), {})) for year in list_years)
    if peak <= 0:
        return list_years[-1]
    threshold = max(min_countries, math.ceil(peak * share))
    for year in reversed(list_years):
        if len(values_by_year.get(str(year), {})) >= threshold:
            return year
    return list_years[-1]


def money_unit_compatible(
    concept_measure: str,
    indicator_unit: str | None,
    indicator_unit_ru: str | None,
) -> bool:
    """Денежный concept: сопоставимость по классу меры, не по формулировке unit_ru."""
    from app.data.eurostat_listing import measure_class

    return measure_class(indicator_unit, indicator_unit_ru) == concept_measure


def mode_unit_label(mode: RankMode, base_unit: str) -> str:
    if mode == "yoy":
        return mode_unit("yoy", base_unit)
    return base_unit
