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
