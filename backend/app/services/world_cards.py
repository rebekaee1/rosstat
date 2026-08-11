"""Сборка карточек мирового блока: card_key → primary + частоты + modes.

Чистая логика + тонкие хелперы над WorldIndicator. Без I/O.
Контракт mode-токена: ``{type}-{freq}``, type ∈ level|step|yoy|yoyabs|index,
freq ∈ monthly|quarterly|annual. Легаси-токены мапятся в новые.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Sequence

from app.data.eurostat_listing import (
    card_key,
    is_stale_history,
    listing_rank_tuple,
    meets_listing_depth,
    normalize_age_code,
    normalize_frequency,
    normalize_sex_code,
    variant_group_key,
)
from app.data.eurostat_titles_ru import split_freq_suffix
from app.data.world_aggregation import aggregate_series, aggregation_policy_for
from app.services.world_view_modes import (
    apply_mode,
    is_signed_or_zero_crossing,
    mode_unit as transform_unit,
)

MODE_TYPES = ("level", "step", "yoy", "yoyabs", "index")
MODE_FREQS = ("monthly", "quarterly", "annual")

TYPE_GROUP = {
    "level": "Уровень",
    "step": "К прошлому периоду",
    "yoy": "К году",
    "yoyabs": "К году",
    "index": "Индекс",
}

FREQ_LABEL = {
    "monthly": "По месяцам",
    "quarterly": "По кварталам",
    "annual": "По годам",
}

STEP_LABEL = {
    "monthly": "М/м",
    "quarterly": "Кв/кв",
    "annual": "Г/г",
}


_LEGACY_TO_COMPOSITE = {
    "level": None,  # → level-{native}
    "mom": ("step", "monthly"),
    "qoq": ("step", "quarterly"),
    "yoy": None,  # → yoy-{native}
    "yoy_abs": None,  # → yoyabs-{native}
    "index_first": None,  # → index-{native}
    "avg_quarter": ("level", "quarterly"),
    "avg_year": ("level", "annual"),
}


@dataclass(frozen=True)
class ParsedMode:
    type: str
    freq: str
    id: str  # canonical composite
    legacy: bool = False


@dataclass(frozen=True)
class ResolvedSeries:
    """Что грузить и как трансформировать."""

    source_code: str
    frequency: str
    transform: str  # ключ apply_mode / спец.
    aggregated: bool
    official: bool
    source_frequency: str
    aggregation_policy: str | None = None


def display_name(name_ru: str | None) -> str:
    """Имя карточки без частотного хвоста."""
    subject, _ = split_freq_suffix(name_ru or "")
    return subject or (name_ru or "")


def indicator_card_key(ind: Any) -> tuple:
    base = card_key(
        country_id=ind.country_id,
        dataset_id=ind.dataset_id,
        unit=ind.unit,
        unit_ru=ind.unit_ru,
        slice_json=ind.slice_json or {},
    )
    # Первая позиция остаётся country_id: peer_key=key[1:] становится
    # provider-aware и не склеивает одноимённые datasets разных ведомств.
    return (base[0], getattr(ind, "provider", "eurostat"), *base[1:])


def rank_indicator(ind: Any, substance_score_fn) -> tuple:
    return listing_rank_tuple(
        points_count=ind.points_count,
        unit=ind.unit,
        dataset_id=ind.dataset_id,
        slice_json=ind.slice_json or {},
        substance_score_fn=substance_score_fn,
    )


def pick_primary(members: Sequence[Any], substance_score_fn) -> Any | None:
    """Primary = самый глубокий среди тех, кто проходит порог глубины.

    Если никто не проходит — None (карточка не листингуется). Члены с малой
    глубиной остаются доступны через frequencies, если primary найден.
    """
    eligible = [
        m for m in members
        if meets_listing_depth(m.frequency, m.points_count)
        and not is_stale_history(m.history_end)
        and int(m.points_count or 0) > 0
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda m: rank_indicator(m, substance_score_fn))


def members_by_freq(members: Sequence[Any]) -> dict[str, Any]:
    """На частоту — лучший официальный ряд (по глубине)."""
    best: dict[str, Any] = {}
    for m in members:
        if int(m.points_count or 0) <= 0:
            continue
        freq = normalize_frequency(m.frequency)
        if freq not in MODE_FREQS and freq not in ("weekly", "daily"):
            continue
        prev = best.get(freq)
        if prev is None or int(m.points_count or 0) > int(prev.points_count or 0):
            best[freq] = m
    return best


def parse_mode_token(token: str | None, *, native_freq: str) -> ParsedMode:
    """Разобрать ?mode= в (type, freq). Легаси → композит."""
    raw = (token or "level").strip().lower()
    native = normalize_frequency(native_freq) or "monthly"
    if native not in MODE_FREQS:
        native = "monthly"

    if raw in MODE_TYPES:
        # type alone → native freq
        return ParsedMode(type=raw, freq=native, id=f"{raw}-{native}", legacy=True)

    if "-" in raw:
        typ, _, freq = raw.partition("-")
        typ = typ.strip()
        freq = normalize_frequency(freq.strip())
        if typ in MODE_TYPES and freq in MODE_FREQS:
            return ParsedMode(type=typ, freq=freq, id=f"{typ}-{freq}")

    if raw in _LEGACY_TO_COMPOSITE:
        mapped = _LEGACY_TO_COMPOSITE[raw]
        if mapped is None:
            typ = {
                "level": "level",
                "yoy": "yoy",
                "yoy_abs": "yoyabs",
                "index_first": "index",
            }[raw]
            return ParsedMode(type=typ, freq=native, id=f"{typ}-{native}", legacy=True)
        typ, freq = mapped
        return ParsedMode(type=typ, freq=freq, id=f"{typ}-{freq}", legacy=True)

    raise ValueError(f"unknown mode: {token}")


def resolve_series_for_mode(
    *,
    parsed: ParsedMode,
    by_freq: dict[str, Any],
    signed: bool,
) -> ResolvedSeries | None:
    """Выбрать source-ряд и transform. None = ячейка недоступна."""
    typ, freq = parsed.type, parsed.freq

    official = by_freq.get(freq)
    if official is not None:
        transform = _transform_for(typ, freq, signed)
        if transform is None:
            return None
        return ResolvedSeries(
            source_code=official.code,
            frequency=freq,
            transform=transform,
            aggregated=False,
            official=True,
            source_frequency=freq,
        )

    candidates = {
        "quarterly": ("monthly",),
        "annual": ("quarterly", "monthly"),
    }.get(freq, ())
    transform = _transform_for(typ, freq, signed)
    if transform is None:
        return None
    for source_frequency in candidates:
        source = by_freq.get(source_frequency)
        if source is None:
            continue
        policy = aggregation_policy_for(source)
        if policy is None:
            continue
        return ResolvedSeries(
            source_code=source.code,
            frequency=freq,
            transform=transform,
            aggregated=True,
            official=False,
            source_frequency=source_frequency,
            aggregation_policy=policy,
        )
    return None


def _transform_for(typ: str, freq: str, signed: bool = False) -> str | None:
    """Трансформ ячейки матрицы. У знакопеременных рядов проценты и база-100 врут:
    деление на отрицательную или околонулевую базу даёт бессмысленный график,
    поэтому сравнения считаются в единицах ряда, а «Индекс» не публикуется."""
    if typ == "level":
        return "level"
    if typ == "index":
        return None if signed else "index_first"
    if typ == "yoy":
        return None if signed else "yoy"
    if typ == "yoyabs":
        return "yoy_abs"
    if typ == "step":
        if freq == "monthly":
            return "mom_abs" if signed else "mom"
        if freq == "quarterly":
            return "qoq_abs" if signed else "qoq"
        if freq == "annual":
            # год к году на годовом ряду = yoy
            return "yoy_abs" if signed else "yoy"
    return None


def apply_resolved(
    series: list[tuple[date, float]],
    resolved: ResolvedSeries,
) -> list[tuple[date, float]]:
    """Применить transform к официальному исходному ряду.

    Для расчётной частоты сначала строится полный календарный уровень по
    верифицированной policy, затем к нему применяется выбранный режим.
    """
    tr = resolved.transform
    base = series
    if resolved.aggregated:
        if not resolved.aggregation_policy:
            raise ValueError("aggregation policy is required")
        base = aggregate_series(
            series,
            source_frequency=resolved.source_frequency,
            target_frequency=resolved.frequency,
            policy=resolved.aggregation_policy,
        )
    return apply_mode(base, tr)


def mode_unit_for(parsed: ParsedMode, base_unit: str, signed: bool = False) -> str:
    tr = _transform_for(parsed.type, parsed.freq, signed)
    if tr is None:
        return base_unit
    return transform_unit(tr, base_unit)


def publishable_mode_types(signed: bool) -> tuple[str, ...]:
    """Типы режимов карточки. Единственная точка истины о том, что мы публикуем:
    у знакопеременного ряда «к году» считается в единицах, а не в процентах,
    и базисный индекс не публикуется вовсе."""
    if signed:
        return ("level", "step", "yoyabs")
    return ("level", "step", "yoy", "index")


def build_modes_matrix(
    *,
    by_freq: dict[str, Any],
    series_by_code: dict[str, list[tuple[date, float]]] | None = None,
    unit: str = "",
) -> list[dict]:
    """Полная матрица type×freq для API."""
    # знак ряда — по самому мелкому официальному
    signed = False
    if series_by_code:
        for freq in MODE_FREQS:
            ind = by_freq.get(freq)
            if ind is None:
                continue
            pts = series_by_code.get(ind.code)
            if pts:
                signed = is_signed_or_zero_crossing(pts)
                break
    else:
        # без точек — предполагаем положительный (yoy доступен)
        signed = False

    out: list[dict] = []
    for typ in publishable_mode_types(signed):
        for freq in MODE_FREQS:
            parsed = ParsedMode(type=typ, freq=freq, id=f"{typ}-{freq}")
            resolved = resolve_series_for_mode(
                parsed=parsed, by_freq=by_freq, signed=signed,
            )
            available = resolved is not None
            # step-monthly без monthly — недоступен даже через агрегацию
            if typ == "step" and freq == "monthly" and "monthly" not in by_freq:
                available = False
            label = _mode_label(typ, freq)
            out.append({
                "id": parsed.id,
                "label": label,
                "group": TYPE_GROUP[typ],
                "type": typ,
                "freq": freq,
                "available": available,
                "official": bool(resolved and resolved.official) if available else False,
                "unit": mode_unit_for(parsed, unit, signed) if available else unit,
            })
    return out


def _mode_label(typ: str, freq: str) -> str:
    """Подпись нижнего ряда — всегда частота: тип задан верхним рядом."""
    if typ == "step":
        return STEP_LABEL[freq]
    return FREQ_LABEL.get(freq, freq)


def frequencies_payload(by_freq: dict[str, Any]) -> list[dict]:
    out = []
    for freq in MODE_FREQS:
        ind = by_freq.get(freq)
        if ind is None:
            continue
        out.append({
            "freq": freq,
            "code": ind.code,
            "points_count": ind.points_count,
            "history_start": ind.history_start.isoformat() if ind.history_start else None,
            "history_end": ind.history_end.isoformat() if ind.history_end else None,
            "official": True,
        })
    return out


def variant_label(ind: Any) -> str:
    """Подпись variant-pill для безработицы и аналогов."""
    sl = ind.slice_json or {}
    age = normalize_age_code(sl.get("age"))
    measure = (ind.unit_ru or ind.unit or "").strip()
    bits: list[str] = []
    if age == "Y_LT25":
        bits.append("15–24 лет")
    elif age == "Y25-74":
        bits.append("25–74 лет")
    elif age == "TOTAL":
        bits.append("Все возраста")
    else:
        bits.append(age)
    if "тысяч" in measure.lower() or (ind.unit or "").upper() in {"THS_PER", "THS"}:
        bits.append("тыс. человек")
    elif "%" in measure or (ind.unit or "").upper().startswith("PC"):
        bits.append("% ЭАН" if "активн" in measure.lower() or (ind.unit or "").upper() == "PC_ACT" else "%")
    elif measure:
        bits.append(measure)
    return ", ".join(bits)


def build_variants(
    current: Any,
    siblings: Iterable[Any],
) -> list[dict]:
    """Список variant-pill'ов; [] если stem вне whitelist."""
    provider = getattr(current, "provider", "eurostat")
    vg = variant_group_key(country_id=current.country_id, dataset_id=current.dataset_id)
    if vg is None:
        return []
    # siblings — primary каждой карточки той же variant-группы
    items = []
    seen: set[str] = set()
    for ind in siblings:
        if getattr(ind, "provider", "eurostat") != provider:
            continue
        if variant_group_key(country_id=ind.country_id, dataset_id=ind.dataset_id) != vg:
            continue
        if ind.code in seen:
            continue
        seen.add(ind.code)
        items.append({
            "code": ind.code,
            "label": variant_label(ind),
            "current": ind.code == current.code,
        })
    items.sort(key=lambda x: (not x["current"], x["label"]))
    return items if len(items) > 1 else []
