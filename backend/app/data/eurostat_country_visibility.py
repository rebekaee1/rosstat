"""Правило витрины стран мирового блока.

Страна попадает на главную /world и в список стран, только если Евростат
по ней — реальный наблюдатель (десятки показателей, несколько тем), а не
случайный партнёр сравнения в 1–3 таблицах.

Данные в БД не удаляем: ``is_active=false`` скрывает страну с витрины;
ряды остаются для будущего национального источника.
"""

from __future__ import annotations

# Абсолютный пол: меньше — заведомо «огрызок» рядом с медианой EU ~200+.
COUNTRY_VITRINE_MIN_LISTED = 30

# Минимум разных category_ru у листингуемых рядов (темы, не дубли одного блока).
COUNTRY_VITRINE_MIN_CATEGORIES = 3

# Относительный пол к медиане listed по активным странам.
# 0.15 × медиана ≈ 30–35 при медиане 200–230: совпадает с абсолютным полом
# и отсекает партнёров (CN/US/JP/…) без ручного geo-списка.
COUNTRY_VITRINE_MEDIAN_FRACTION = 0.15

# Страны с national-core YAML: eurostat ingest/deep-expand не ставит is_listed.
EUROSTAT_SUPPRESS_LISTED_CODES: frozenset[str] = frozenset({
    "CA", "AU", "UK", "GB", "US", "JP", "CN", "IN", "BR", "MX", "KR",
})


def country_passes_vitrine_threshold(
    *,
    listed_cards: int,
    category_count: int,
    median_listed: float,
) -> bool:
    """True → страна видима на витрине (is_active=True).

    Обоснование порога
    ------------------
    - Партнёры сравнения (ZA/IN/CN/…): 1–11 карточек, 1–4 темы — ниже обоих
      абсолютных порогов.
    - Страны расширения с узким набором (AM ~17 / 1 тема): не проходят
      ``MIN_CATEGORIES`` — Eurostat отдаёт почти только демографию.
    - Медианная доля ловит «серую зону» (15–29 карточек), если медиана EU
      растёт: пол поднимается вместе с витриной, без ручного списка ISO.
    - Великобритания после Brexit: в БД сотни рядов, но свежих листингуемых
      ~15 (хвост оборвался ~2020) — порог честно скрывает полую полку;
      данные остаются для нац. источника (ONS).
    """
    listed = int(listed_cards or 0)
    cats = int(category_count or 0)
    if listed < COUNTRY_VITRINE_MIN_LISTED:
        return False
    if cats < COUNTRY_VITRINE_MIN_CATEGORIES:
        return False
    med = float(median_listed or 0.0)
    if med > 0 and listed < med * COUNTRY_VITRINE_MEDIAN_FRACTION:
        return False
    return True


def is_eurostat_listing_pipeline_target(ind: object) -> bool:
    """Ряд участвует в Eurostat fold/defect/listing (не national passport)."""
    return (getattr(ind, "provider", None) or "").lower() == "eurostat"


def is_eurostat_retitle_target(ind: object) -> bool:
    """Eurostat-композитор может пересобрать name/unit/seo.

    National-provider ряды не трогаем. Ручной curated passport на Eurostat
    тоже не переписываем (quality=curated + suppress-country).
    """
    if not is_eurostat_listing_pipeline_target(ind):
        return False
    quality = (getattr(ind, "name_quality", None) or "").lower()
    # Обычный eurostat curated/composed — пересобираем (словари обновились).
    # Явный national overlay помечается отдельно, если появится; пока все eurostat.
    _ = quality
    return True


def indicator_counts_toward_national_core(ind: object) -> bool:
    """Свежий listed-ряд учитывается в national-core / витрине страны."""
    from datetime import date, datetime

    if not getattr(ind, "is_listed", False):
        return False
    he = getattr(ind, "history_end", None)
    if he is None:
        return False
    if isinstance(he, datetime):
        he = he.date()
    if not isinstance(he, date):
        return False
    # Brexit/партнёры с хвостом ≤2019 не считаем «живым» ядром витрины.
    return he.year >= 2020


def country_passes_vitrine(
    *,
    listed_cards: int,
    category_count: int,
    median_listed: float,
    country_code: str | None = None,
    fresh_listed_count: int = 0,
    has_non_eurostat: bool = False,
) -> bool:
    """Витрина: Eurostat-порог ИЛИ national-core (нац. провайдер / свежий паспорт)."""
    code = (country_code or "").strip().upper()
    # Есть живые non-eurostat ряды — страна на витрине даже при узком Eurostat.
    if has_non_eurostat and int(fresh_listed_count or 0) >= 1:
        return True
    # Suppress-list без национального источника — только через общий порог
    # (обычно не проходит: мало свежих listed).
    return country_passes_vitrine_threshold(
        listed_cards=listed_cards,
        category_count=category_count,
        median_listed=median_listed,
    )
