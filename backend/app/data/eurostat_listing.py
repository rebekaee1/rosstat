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

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

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

# Измерения публикации (flash-оценки prc_hicp_fp: release=FIN/EST) — служебные:
# различают волну выпуска, а не смысл ряда. В identity карточки не входят.
_RELEASE_SLICE_KEYS = frozenset({"release"})

# Суффикс частоты в dataset_id Евростата: une_rt_m / sts_inpr_q / …
_DATASET_FREQ_SUFFIX = re.compile(r"_[mqawd]$", re.I)

# Variant-группы: любой stem с >1 карточкой (build_variants сам вернёт [] при одном).
VARIANT_WHITELIST_STEMS = frozenset()  # deprecated; variant_group_key больше не фильтрует

# Кросс-стемовые variant-алиасы (M3, 2026-08-27): разные наборы Евростата
# об одном показателе. Штатный ключ «страна × stem» разводит их в разные
# карточки без переключателя; алиас склеивает в одну variant-группу.
# Каждый член — frozenset стемов; ключ группировки = alias-группа или stem.
VARIANT_STEM_ALIASES: tuple[frozenset[str], ...] = (
    frozenset({"prc_hpi", "ei_hppi"}),  # индекс цен на жильё: основной ↔ быстрая оценка
    # ГИПЦ, один смысл: месячный индекс / среднегодовой / быстрая оценка flash
    # (release=FIN — измерение публикации, не смысла) / темп к предыдущему
    # периоду (ei_cphi, RT1). prc_hicp_cind (постоянные налоги) — другой
    # показатель, сознательно вне группы.
    frozenset({
        "prc_hicp_midx", "prc_hicp_aind", "prc_hicp_fp", "ei_cphi",
    }),
)


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


# COICOP-код «все товары и услуги»: агрегат не сужает смысл карточки,
# поэтому prc_hicp_* (coicop=CP00) и ei_cphi (без coicop) — один предмет.
_ALL_ITEMS_COICOP = frozenset({"CP00", "TOT", "TOTAL", "T"})

# Класс слияния «индекс/уровень-индекс»: только индексные I/INX-единицы.
# ВАЖНО: THS_PER/EUR/NR/PC сюда НЕ входят — численность и уровень в % —
# разные показатели, их слияние запрещено (une_rt: уровень vs численность).
_INDEX_UNITS = frozenset({
    "I15", "I15_Q", "I15_A_AVG", "I10", "I10_Q", "I10_A_AVG", "I05", "I96",
    "I2015", "I2021", "I21", "I21_SCA", "I25", "I25_NSA", "INX", "INX_A_AVG",
    "INDEX", "I20", "I2010", "I2015_SCA", "I16", "I16_Q", "I16_A_AVG",
})

# Производные меры одного предмета: темп/изменение — то же измерение,
# другое представление. Сливаются с индексом (владелец, 2026-08-28:
# «ИПЦ индекс» + «ИПЦ темп к предыдущему периоду» = одна карточка).
_CHANGE_UNITS = frozenset({
    "RCH_A", "RCH_M", "RCH_MV12MAVR", "RT1", "RT1-SCA", "RT_M_DIF",
    "PCH_SM", "PCH_PRE", "PCH_SAME",
})


def catalog_measure_class(
    unit: str | None,
    unit_ru: str | None = None,
) -> str:
    """Класс единицы для слияния мер: IDX | сущностный measure_class.

    Индекс и производные от него темпы → «IDX» (одно измерение, разные
    представления). Остальные единицы — как есть (measure_class): человек,
    евро, % ЭАН и т.п. сущностно различны и не сливаются.
    """
    u = (unit or "").strip().upper().replace("-", "_")
    ru = (unit_ru or "").strip().lower()
    if u in _INDEX_UNITS or u in _CHANGE_UNITS:
        return "IDX"
    if ru.startswith("индекс") or ru.startswith("темп изменения") or ru.startswith("изменение"):
        return "IDX"
    return measure_class(unit, unit_ru)


def _catalog_extra_dims(slice_json: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    """Extra-измерения для каталога: coicop-итог «CP00» = отсутствие среза."""
    out = []
    for dim, code in extra_dims_frozen(slice_json):
        if dim in _RELEASE_SLICE_KEYS:
            continue
        if dim in ("coicop", "coicop18") and code in _ALL_ITEMS_COICOP:
            continue
        out.append((dim, code))
    return tuple(sorted(out))


def catalog_merge_key(
    *,
    country_id: int,
    provider: str | None,
    dataset_id: str,
    unit: str | None = None,
    unit_ru: str | None = None,
    slice_json: dict[str, Any] | None,
) -> tuple:
    """Ключ слияния каталога: меры/базы одного смысла схлопываются.

    Отличие от ``card_key``: measure_class проходит через
    catalog_measure_class (индекс и его темп — одна карточка), стемы —
    по alias-группе (prc_hpi ↔ ei_hppi). Разные сущностные единицы
    (уровень % vs численность), срезы (coicop FOOD vs CP00) и возрасты/полы
    НЕ схлопываются.
    """
    sl = slice_json or {}
    return (
        int(country_id),
        (provider or "eurostat").strip().lower(),
        variant_stem_alias(dataset_stem(dataset_id)),
        catalog_measure_class(unit or sl.get("unit"), unit_ru),
        normalize_age_code(sl.get("age")),
        normalize_sex_code(sl.get("sex")),
        _catalog_extra_dims(sl),
    )


def _measure_preference_rank(
    unit: str | None,
    unit_ru: str | None = None,
) -> int:
    """Порядок меры для primary слитой карточки: уровень-индекс > % > прочее."""
    from app.data.eurostat_titles_ru import _DERIVED_UNITS, _LEVEL_UNITS

    u = (unit or "").strip().upper().replace("-", "_")
    if u in _LEVEL_UNITS:
        return 0
    if u in _DERIVED_UNITS:
        return 1
    return 2


def measure_preference_rank(ind: Any) -> tuple:
    """Сортировочный ключ выбора главной меры: rank меры → глубина → код.

    Меньше = лучше. При равном ранге меры берём самый глубокий ряд
    (точки листинга — это качество), затем код для детерминизма.
    """
    return (
        _measure_preference_rank(ind.unit, ind.unit_ru),
        -int(ind.points_count or 0),
        getattr(ind, "code", "") or "",
    )


def variant_stem_alias(stem: str) -> str:
    """Alias-ключ stem'а для variant-группы (кросс-стемовые семьи, M3).

    Стемы одной alias-группы (VARIANT_STEM_ALIASES) получают общий ключ;
    остальные возвращаются как есть. Отдельные dataset_id внутри стема
    (prc_hpi_q / prc_hpi_a / prc_hpi_ooq) остаются разными карточками.
    """
    s = (stem or "").strip().lower()
    if not s:
        return s
    for group in VARIANT_STEM_ALIASES:
        if s in group:
            return "|".join(sorted(group))
    return s


def variant_group_key(
    *,
    country_id: int,
    dataset_id: str,
) -> tuple | None:
    """Ключ variant-группы: страна × stem (с кросс-стемовыми алиасами).

    Один срез → UI сам скроет picker.
    """
    stem = dataset_stem(dataset_id)
    if not stem:
        return None
    return (int(country_id), variant_stem_alias(stem))


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


ListingMode = Literal["full_ok", "headline_ok", "no"]

_LISTING_DECISIONS_PATH = Path(__file__).with_name("eurostat_listing_decisions.json")

# Измерения, которые не считаем «микросрезом» при headline_ok.
_HEADLINE_IDENTITY_DIMS = frozenset({
    "freq", "geo", "time", "unit", "s_adj",
})


@lru_cache(maxsize=1)
def load_listing_decisions() -> dict[str, dict[str, Any]]:
    """Редакторские решения listable/mode по dataset_id (SEO-merged канон)."""
    if not _LISTING_DECISIONS_PATH.is_file():
        return {}
    raw = json.loads(_LISTING_DECISIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, val in raw.items():
        ds = str(key).strip().lower()
        if not ds or not isinstance(val, dict):
            continue
        mode = str(val.get("mode") or "").strip().lower()
        if mode not in {"full_ok", "headline_ok", "no"}:
            continue
        out[ds] = {
            "listable": bool(val.get("listable")) and mode != "no",
            "mode": mode,
            "reason": str(val.get("reason") or ""),
        }
    return out


def listing_mode_for_dataset(dataset_id: str | None) -> ListingMode | None:
    """Режим витрины для датасета или None, если решения нет."""
    ds = (dataset_id or "").strip().lower()
    if not ds:
        return None
    hit = load_listing_decisions().get(ds)
    if not hit:
        return None
    return hit["mode"]  # type: ignore[return-value]


def narrowing_dim_is_aggregate(dim: str, code: str | None) -> bool:
    """True, если код измерения — итоговый / не сужает headline."""
    from app.data.eurostat_dim_labels_ru import is_dim_totalish

    d = (dim or "").strip().lower()
    c = (code or "").strip().upper()
    if not c or is_dim_totalish(d, c):
        return True
    # Возрастной «рабочий возраст» уже totalish в dim_labels; дубль на всякий.
    if d == "age" and c in {"Y15-74", "TOTAL", "T"}:
        return True
    if d == "sex" and c in {"T", "TOTAL"}:
        return True
    return False


def varying_narrowing_dims(
    slices: list[dict[str, Any] | None],
) -> frozenset[str]:
    """Измерения, которые реально варьируют между срезами датасета."""
    from app.data.eurostat_titles_ru import _NARROWING_NAME_DIMS

    values: dict[str, set[str]] = {}
    for sl in slices:
        if not sl:
            continue
        for dim in _NARROWING_NAME_DIMS:
            if dim in _HEADLINE_IDENTITY_DIMS:
                continue
            raw = sl.get(dim)
            if raw is None:
                continue
            val = str(raw).strip().upper()
            if not val:
                continue
            values.setdefault(dim, set()).add(val)
    return frozenset(d for d, vals in values.items() if len(vals) > 1)


def is_headline_aggregate_slice(
    slice_json: dict[str, Any] | None,
    *,
    varying_dims: frozenset[str] | None = None,
) -> bool:
    """Срез годится для headline_ok: все варьирующие narrowing-dim — TOTAL.

    Константные по датасету измерения (часть identity набора) не требуют TOTAL.
    """
    sl = slice_json or {}
    dims = varying_dims
    if dims is None:
        from app.data.eurostat_titles_ru import _NARROWING_NAME_DIMS

        dims = frozenset(
            d for d in _NARROWING_NAME_DIMS if d not in _HEADLINE_IDENTITY_DIMS
        )
    for dim in dims:
        if not narrowing_dim_is_aggregate(dim, sl.get(dim)):
            return False
    return True


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
    # Средний эквивалентный доход по составу домохозяйства (EU-SILC).
    # TOTAL + основные разрезы; пустые члены кодлистa отсеются MIN_POINTS.
    "ilc_di04": [
        {"freq": "A", "hhcomp": hh, "statinfo": "MEAN_EI", "unit": "EUR"}
        for hh in (
            "TOTAL",
            "A1",
            "A1_DCH",
            "A2",
            "A2_DCH1",
            "A2_DCH2",
            "A2_DCH_GE3",
            "A_GE2_DCH",
            "A_GE2_NDCH",
            "A_GE3",
            "A_GE3_DCH",
            "DCH",
            "NDCH",
            "A2_2LT65",
            "A2_GE1_GE65",
        )
    ],
}
