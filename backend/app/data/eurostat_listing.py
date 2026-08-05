"""Правила листинга мирового блока: глубина истории, card_key, смысловой дедуп.

«Максимальная история» (AGENTS.md, чеклист нового индикатора): огрызок
недопустим. Источник часто отдаёт и короткую оперативную таблицу (teilm*),
и глубокий ряд (une_rt_m с 1980-х) — на витрине должен остаться глубокий.

Пороги — именованный конфиг: осмысленный график ≈ 5 лет (для дневных/недельных —
соразмерно плотнее).

Карточка (ADR-0006 для мира): частоты одного показателя склеиваются по
строгому ``card_key`` без frequency. Имя-семейный ключ запрещён (ложные склейки).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

# Минимальная длина истории для is_listed=true (primary карточки).
LISTING_MIN_POINTS_BY_FREQUENCY: dict[str, int] = {
    "monthly": 60,
    "quarterly": 20,
    "annual": 10,
    "yearly": 10,
    "weekly": 104,
    "daily": 250,
}

# Годовые одиночки с такой глубиной — огрызок после склейки частот.
SHORT_ANNUAL_SINGLETON_MAX_POINTS = 11

# Ряд оборвался до этого года → не на витрине (archived при прямом доступе).
LISTING_MIN_HISTORY_END = date(2023, 1, 1)

STORAGE_MIN_POINTS = 8

# Измерения SDMX, не входящие в identity среза карточки (служебные / частота).
_CORE_SLICE_KEYS = frozenset({
    "freq", "age", "sex", "unit", "s_adj", "geo", "time",
})

# Суффикс частоты в dataset_id Евростата: une_rt_m / sts_inpr_q / …
_DATASET_FREQ_SUFFIX = re.compile(r"_[mqawd]$", re.I)

# Variant-группы: только whitelist stem'ов (не авто на весь каталог).
VARIANT_WHITELIST_STEMS = frozenset({"une_rt"})

FREQ_ORDER = ("monthly", "quarterly", "annual", "weekly", "daily")


def min_points_for_frequency(frequency: str | None) -> int:
    freq = (frequency or "").strip().lower()
    return LISTING_MIN_POINTS_BY_FREQUENCY.get(freq, 60)


def meets_listing_depth(frequency: str | None, points_count: int | None) -> bool:
    return int(points_count or 0) >= min_points_for_frequency(frequency)


def normalize_frequency(frequency: str | None) -> str:
    f = (frequency or "").strip().lower()
    if f == "yearly":
        return "annual"
    return f


def normalize_age_code(age: str | None) -> str:
    a = (age or "").strip().upper()
    if not a or a in {"TOTAL", "T", "Y15-74"}:
        return "TOTAL"
    if a in {"Y_LT25", "Y15-24", "Y_LT25Y", "Y15_24"}:
        return "Y_LT25"
    if a in {"Y25-74", "Y25_74"}:
        return "Y25-74"
    if a in {"Y15-64", "Y15_64"}:
        return "Y15-64"
    return a


def normalize_sex_code(sex: str | None) -> str:
    s = (sex or "").strip().upper()
    if s in {"", "T", "TOTAL"}:
        return "T"
    return s


def measure_class(unit: str | None, unit_ru: str | None = None) -> str:
    """Класс меры для смыслового ключа (не путать уровень и %)."""
    u = (unit or "").strip().upper().replace("-", "_")
    ru = (unit_ru or "").lower()
    if u in {"PC_ACT", "PC", "PC_POP", "PC_GDP"} or ru.startswith("%"):
        if "активн" in ru or u == "PC_ACT":
            return "PC_ACT"
        if "населен" in ru or u == "PC_POP":
            return "PC_POP"
        if "ввп" in ru or u == "PC_GDP":
            return "PC_GDP"
        return "PC"
    if u in {"THS_PER", "THS"} or "тысяч человек" in ru:
        return "THS_PER"
    if u == "NR" or ru == "человек":
        return "NR"
    if "1000 живорожд" in ru:
        return "PER_1000_LB"
    if "1000 человек" in ru or "1000 жител" in ru:
        return "PER_1000_POP"
    if "детей на женщину" in ru:
        return "TFR"
    if u:
        return u
    return ru or "UNKNOWN"


def dataset_stem(dataset_id: str | None) -> str:
    """Строгий stem набора: une_rt_m → une_rt. Без name-fallback и без широких alias."""
    ds = (dataset_id or "").strip().lower()
    if not ds:
        return ""
    return _DATASET_FREQ_SUFFIX.sub("", ds)


def extra_dims_frozen(slice_json: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    """Все измерения среза, кроме служебных — часть identity карточки."""
    sl = slice_json or {}
    out: list[tuple[str, str]] = []
    for key, raw in sl.items():
        k = (key or "").strip()
        if not k or k.lower() in _CORE_SLICE_KEYS:
            continue
        val = str(raw).strip()
        if not val:
            continue
        # TOTAL-агрегаты измерений не различают карточку
        if val.upper() in {"TOTAL", "T", "ALL", "NSP"}:
            continue
        out.append((k.lower(), val.upper()))
    return tuple(sorted(out))


def card_key(
    *,
    country_id: int,
    dataset_id: str,
    unit: str | None,
    unit_ru: str | None,
    slice_json: dict[str, Any] | None,
) -> tuple:
    """Ключ карточки: страна × stem × мера × возраст × пол × extra. Без frequency."""
    sl = slice_json or {}
    return (
        int(country_id),
        dataset_stem(dataset_id),
        measure_class(unit or sl.get("unit"), unit_ru),
        normalize_age_code(sl.get("age")),
        normalize_sex_code(sl.get("sex")),
        extra_dims_frozen(sl),
    )


def variant_group_key(
    *,
    country_id: int,
    dataset_id: str,
) -> tuple | None:
    """Ключ variant-группы или None, если stem вне whitelist."""
    stem = dataset_stem(dataset_id)
    if stem not in VARIANT_WHITELIST_STEMS:
        return None
    return (int(country_id), stem)


def national_counterpart_dataset(dataset_id: str | None) -> str | None:
    """Региональный набор → предполагаемый национальный (demo_r_minfind → demo_minfind)."""
    ds = (dataset_id or "").strip().lower()
    if "_r_" not in ds:
        return None
    return ds.replace("_r_", "_", 1)


def is_stale_history(history_end: date | None) -> bool:
    if history_end is None:
        return True
    return history_end < LISTING_MIN_HISTORY_END


def is_short_annual_singleton(frequency: str | None, points_count: int | None) -> bool:
    freq = normalize_frequency(frequency)
    if freq != "annual":
        return False
    n = int(points_count or 0)
    return 10 <= n <= SHORT_ANNUAL_SINGLETON_MAX_POINTS


_UNEMP_DS = re.compile(
    r"^(une_rt_|teilm01|teilm02|ei_lmhu|ei_lmhr|ei_lm_m)",
    re.I,
)
_EMP_DS = re.compile(r"^(lfsi_|lfsq_er|nama_10_a10_e|namq_10_a10_e)", re.I)


def subject_family(dataset_id: str, name_ru: str | None = None) -> str:
    """Смысловой предмет ряда (для дедупа teilm* ↔ une_rt_*)."""
    ds = (dataset_id or "").lower()
    if _UNEMP_DS.search(ds):
        # teilm01* — численность, teilm02* — уровень; уточняется measure_class
        return "unemployment"
    if _EMP_DS.search(ds):
        return "employment"
    if ds.startswith("demo_minfind") or ds == "tps00027":
        return "infant_mortality_rate"
    if ds.startswith(("prc_hicp_midx", "prc_hicp_minr", "prc_hicp_ct", "ei_cphi")):
        return "hicp_index"
    if ds.startswith(("prc_hicp_manr",)):
        return "hicp_yoy"
    # fallback — нормализованное имя без частоты/единицы-хвоста
    name = (name_ru or "").lower()
    name = re.sub(
        r",\s*(помесячно|поквартально|за год|понедельно|по дням)\s*$",
        "",
        name,
    )
    name = re.sub(r"\s+", " ", name).strip()
    return name or ds


def listing_semantic_key(
    *,
    country_id: int,
    dataset_id: str,
    name_ru: str,
    frequency: str,
    unit: str | None,
    unit_ru: str | None,
    slice_json: dict[str, Any] | None,
) -> tuple:
    """Ключ «один предмет × мера × частота» внутри страны."""
    sl = slice_json or {}
    family = subject_family(dataset_id, name_ru)
    age = normalize_age_code(sl.get("age"))
    sex = normalize_sex_code(sl.get("sex"))
    measure = measure_class(unit or sl.get("unit"), unit_ru)
    # для unemployment family age TOTAL и отсутствие age — одно и то же
    return (country_id, family, measure, frequency, age, sex)


def listing_rank_tuple(
    *,
    points_count: int | None,
    unit: str | None,
    dataset_id: str,
    slice_json: dict | None,
    substance_score_fn,
) -> tuple:
    """Сортировка: сначала глубина истории, потом substance."""
    depth = int(points_count or 0)
    substance = substance_score_fn(
        unit=unit,
        points_count=depth,
        dataset_id=dataset_id,
        slice_json=slice_json or {},
    )
    # штраф коротким оперативным таблицам при равной глубине
    ds = (dataset_id or "").lower()
    prefer = 0
    if ds.startswith("une_rt_"):
        prefer += 20
    if ds.startswith("teilm"):
        prefer -= 20
    return (depth, prefer, substance)


# Дополнительные срезы глубоких наборов (headline TOTAL недостаточен).
# Без них оперативные teilm* закрывают витрину огрызками.
DEEP_DATASET_SLICES: dict[str, list[dict[str, str]]] = {
    "une_rt_m": [
        {"freq": "M", "s_adj": "SA", "age": "TOTAL", "unit": "PC_ACT", "sex": "T"},
        {"freq": "M", "s_adj": "SA", "age": "Y_LT25", "unit": "PC_ACT", "sex": "T"},
        {"freq": "M", "s_adj": "SA", "age": "Y25-74", "unit": "PC_ACT", "sex": "T"},
        {"freq": "M", "s_adj": "SA", "age": "TOTAL", "unit": "THS_PER", "sex": "T"},
        {"freq": "M", "s_adj": "SA", "age": "Y_LT25", "unit": "THS_PER", "sex": "T"},
        {"freq": "M", "s_adj": "SA", "age": "Y25-74", "unit": "THS_PER", "sex": "T"},
    ],
    "une_rt_q": [
        {"freq": "Q", "s_adj": "SA", "age": "Y15-74", "unit": "PC_ACT", "sex": "T"},
        # quarterly/annual: youth = Y15-24 (не Y_LT25 как в une_rt_m)
        {"freq": "Q", "s_adj": "SA", "age": "Y15-24", "unit": "PC_ACT", "sex": "T"},
        {"freq": "Q", "s_adj": "SA", "age": "Y25-74", "unit": "PC_ACT", "sex": "T"},
        {"freq": "Q", "s_adj": "SA", "age": "Y15-74", "unit": "THS_PER", "sex": "T"},
        {"freq": "Q", "s_adj": "SA", "age": "Y15-24", "unit": "THS_PER", "sex": "T"},
    ],
    "une_rt_a": [
        {"freq": "A", "age": "Y15-74", "unit": "PC_ACT", "sex": "T"},
        {"freq": "A", "age": "Y15-24", "unit": "PC_ACT", "sex": "T"},
        {"freq": "A", "age": "Y25-74", "unit": "PC_ACT", "sex": "T"},
        {"freq": "A", "age": "Y15-74", "unit": "THS_PER", "sex": "T"},
        {"freq": "A", "age": "Y15-24", "unit": "THS_PER", "sex": "T"},
    ],
}
