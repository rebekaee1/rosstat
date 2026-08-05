"""Проверки правдоподобия мировых рядов (предохранитель витрины).

Ловят вырожденные случаи независимо от набора: % при десятках тысяч,
тождество ≈100, «% ВВП» у числителя-ВВП, единица из чужой предметной области.
Чистые функции — без I/O. Repair и audit вызывают одни и те же проверки.
"""

from __future__ import annotations

import statistics
from typing import Any, Sequence


def _slice(sl: dict[str, Any] | None) -> dict[str, Any]:
    return sl or {}


def _unit_code(unit: str | None, slice_json: dict[str, Any] | None) -> str:
    u = (unit or "").strip().upper()
    if u:
        return u
    return str(_slice(slice_json).get("unit") or "").strip().upper()


def _looks_percent(unit: str | None, unit_ru: str | None) -> bool:
    ru = (unit_ru or "").strip().lower()
    u = (unit or "").strip().upper()
    if ru.startswith("%") or ru in {"%", "% ввп", "% населения", "процент", "проценты"}:
        return True
    if u in {"PC", "PC_ACT", "PC_POP", "PC_GDP", "RT"}:
        return True
    return False


def check_tautological_gdp_pc_gdp(
    *,
    slice_json: dict[str, Any] | None,
    unit: str | None,
    values: Sequence[float],
) -> str | None:
    """ВВП в единице «% ВВП» — тождество ≈100."""
    if not values:
        return None
    sl = _slice(slice_json)
    na = str(sl.get("na_item") or "").upper()
    uc = _unit_code(unit, sl)
    if na != "B1GQ" or uc != "PC_GDP":
        return None
    med = float(statistics.median(values))
    if abs(med - 100.0) < 0.5:
        return "tautological_gdp_pc_gdp"
    # даже если не ровно 100 — «ВВП как % ВВП» бессмысленно
    return "gdp_as_pct_of_gdp"


def check_constant_hundred_pct(
    *,
    unit: str | None,
    unit_ru: str | None,
    values: Sequence[float],
) -> str | None:
    """Ряд тождественно ≈100 при подписи процента / % ВВП."""
    if len(values) < 4:
        return None
    if not _looks_percent(unit, unit_ru):
        return None
    if max(abs(float(v) - 100.0) for v in values) < 0.05:
        return "constant_hundred_pct"
    return None


def check_constant_series(
    *,
    values: Sequence[float],
    min_points: int = 8,
) -> str | None:
    """Ряд тождественно равен одному значению (0, 100, любое) — плоская линия."""
    if len(values) < min_points:
        return None
    first = float(values[0])
    if max(abs(float(v) - first) for v in values) < 1e-9:
        return "constant_series"
    return None


def check_mostly_zeros(
    *,
    values: Sequence[float],
    min_points: int = 20,
    zero_share: float = 0.95,
) -> str | None:
    """≥95% нулей при редких ненулевых — почти пустой ряд на витрине."""
    if len(values) < min_points:
        return None
    n_zero = sum(1 for v in values if abs(float(v)) < 1e-12)
    if n_zero / len(values) >= zero_share:
        # полностью константный ноль уже ловит constant_series
        if n_zero < len(values):
            return "mostly_zeros"
    return None


def check_pct_with_huge_levels(
    *,
    unit: str | None,
    unit_ru: str | None,
    slice_json: dict[str, Any] | None,
    values: Sequence[float],
    name_ru: str | None = None,
) -> str | None:
    """Подпись «%» при значениях в тысячах/десятках тысяч (PPS и т.п.)."""
    if not values:
        return None
    ru = (unit_ru or "").strip()
    if not (ru == "%" or ru.startswith("%")):
        return None
    hi = max(values)
    lo = min(values)
    uc = _unit_code(unit, slice_json)
    sl = _slice(slice_json)
    hay = f"{name_ru or ''} {sl}".upper()
    # PPS / per capita levels mislabeled as percent
    if hi > 500 and (
        uc in {"PC", "PC_GDP"}
        or "PPS" in hay
        or "HAB" in hay
        or "PPP" in hay
    ):
        return "unit_mislabeled_pct_but_level"
    if hi > 5000:
        return "pct_out_of_range"
    # инфляция / HICP может быть трёхзначной в экстремумах — не P0 здесь
    name_l = (name_ru or "").lower()
    if any(k in name_l for k in ("инфляц", "hicp", "ипц", "цен")):
        return None
    if hi > 500 and lo > 50:
        return "pct_out_of_range"
    return None


def check_unit_domain_mismatch(
    *,
    name_ru: str | None,
    unit_ru: str | None,
    slice_json: dict[str, Any] | None = None,
) -> str | None:
    """Единица из чужой предметной области относительно имени."""
    name = (name_ru or "").lower()
    ru = (unit_ru or "").lower()
    if not name or not ru:
        return None
    rate_name = any(
        k in name
        for k in ("процентн", "ставк", "доходност", "interest", "yield")
    )
    pop_unit = "1000 человек" in ru or "1000 жител" in ru or "на 1000" in ru
    if rate_name and pop_unit:
        return "unit_domain_mismatch_rates_as_per_1000_pop"
    # % ВВП при имени про ставки
    if rate_name and "ввп" in ru:
        return "unit_domain_mismatch_rates_as_gdp"
    # население / рождаемость подписаны процентными ставками — реже
    demo_name = any(k in name for k in ("рождаем", "смертн", "населен"))
    if demo_name and ru in {"%", "процент"} and "младен" not in name:
        indic = str((_slice(slice_json) or {}).get("indic") or "").upper()
        if indic.startswith("MF-"):
            return "unit_domain_mismatch_demo_as_rate"
    return None


def check_numerator_is_denominator_gdp(
    *,
    name_ru: str | None,
    unit_ru: str | None,
    slice_json: dict[str, Any] | None,
) -> str | None:
    """Показатель «в % ВВП», у которого числитель сам ВВП."""
    sl = _slice(slice_json)
    na = str(sl.get("na_item") or "").upper()
    ru = (unit_ru or "").lower()
    uc = _unit_code(None, sl) or _unit_code(sl.get("unit"), sl)
    if na == "B1GQ" and (uc == "PC_GDP" or "ввп" in ru):
        return "gdp_numerator_equals_gdp_denominator"
    name = (name_ru or "").lower()
    if "ввп" in name and ("ввп" in ru or uc == "PC_GDP") and na in {"", "B1GQ"}:
        # имя про ВВП + единица % ВВП при na_item пустом/ВВП
        if na == "B1GQ":
            return "gdp_numerator_equals_gdp_denominator"
    return None


def check_extreme_period_change(
    *,
    unit_ru: str | None,
    values: Sequence[float],
    hard_hi: float = 5000.0,
) -> str | None:
    """YoY/MoM «изменение…» с экстремумами (COVID и т.п.) — шок на витрине."""
    if not values:
        return None
    ru = (unit_ru or "").lower()
    if "изменен" not in ru and "темп" not in ru and "pch" not in ru:
        return None
    hi, lo = max(values), min(values)
    if hi > hard_hi or lo < -99.5:
        return "pct_out_of_range"
    return None


def plausibility_reasons(
    *,
    name_ru: str | None,
    unit: str | None,
    unit_ru: str | None,
    slice_json: dict[str, Any] | None,
    values: Sequence[float],
    dataset_id: str | None = None,
) -> list[str]:
    """Все срабатывания предохранителя для одного ряда."""
    reasons: list[str] = []
    for fn in (
        lambda: check_tautological_gdp_pc_gdp(
            slice_json=slice_json, unit=unit, values=values
        ),
        lambda: check_numerator_is_denominator_gdp(
            name_ru=name_ru, unit_ru=unit_ru, slice_json=slice_json
        ),
        lambda: check_constant_series(values=values),
        lambda: check_mostly_zeros(values=values),
        lambda: check_constant_hundred_pct(
            unit=unit, unit_ru=unit_ru, values=values
        ),
        lambda: check_pct_with_huge_levels(
            unit=unit, unit_ru=unit_ru, slice_json=slice_json,
            values=values, name_ru=name_ru,
        ),
        lambda: check_extreme_period_change(unit_ru=unit_ru, values=values),
        lambda: check_unit_domain_mismatch(
            name_ru=name_ru, unit_ru=unit_ru, slice_json=slice_json
        ),
    ):
        hit = fn()
        if hit and hit not in reasons:
            reasons.append(hit)
    return reasons


def is_plausible_for_listing(
    *,
    name_ru: str | None,
    unit: str | None,
    unit_ru: str | None,
    slice_json: dict[str, Any] | None,
    values: Sequence[float],
    dataset_id: str | None = None,
) -> bool:
    return not plausibility_reasons(
        name_ru=name_ru,
        unit=unit,
        unit_ru=unit_ru,
        slice_json=slice_json,
        values=values,
        dataset_id=dataset_id,
    )
