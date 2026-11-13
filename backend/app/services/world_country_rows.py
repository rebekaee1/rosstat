"""Узкое чтение рядов страны: только те наборы данных, которые нужны карточке ряда или сравнению стран.

Замер 2026-11-13: `select(WorldIndicator).where(country_id == …)` читал все ряды страны на каждую карточку и
каждый ряд сравнения — у Испании 10 831 строка на 10 581 странице основной таблицы (83 МБ), строки страны лежат
почти по одной на страницу. База живёт под потолком памяти, и это чтение шло с диска.

Способ в два шага:

1. Справочник страны — разные пары (провайдер, набор данных). Читается только по индексу
   `ix_world_indicators_card_lookup (country_id, provider, dataset_id)`, без строк основной таблицы.
2. Из справочника теми же функциями Python, что считают ключи карточек и понятий, отбираются пары, чьи ряды
   вообще могут участвовать в расчёте; полные строки читаются только для них.

Отбор по сырым значениям из справочника, а не выражением SQL: регистр и обрезка пробелов считаются ровно тем же
кодом, что и ключи, поэтому узкая выборка — надмножество нужных рядов по построению, а не по совпадению правил
SQL и Python. Доказательство для каждого потребителя — у функций `card_dataset_pairs` и `compare_dataset_pairs`.

Порядок строк задан явно (`id`): прежний запрос шёл без `ORDER BY` и отдавал строки в порядке их расположения на
диске, который меняется при каждом обновлении ряда.

Сверка со старым расчётом на боевых данных и замер — `docs/enterprise_resilience.md#world-country-rows-2026-11-13`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.eurostat_listing import catalog_stem_alias, dataset_stem, variant_stem_alias
from app.data.world_concepts import concept_dataset_allowed
from app.models import WorldIndicator

DatasetPair = tuple[str, str]


def _merge_provider(provider: str | None) -> str:
    """Провайдер так, как его приводит `catalog_merge_key`."""
    return (provider or "eurostat").strip().lower()


def card_dataset_pairs(indicator: Any, directory: Iterable[DatasetPair]) -> list[DatasetPair]:
    """Пары справочника, чьи ряды могут войти в карточку ряда `indicator` и в его переключатель срезов.

    Расчёт карточки (`_card_context`, варианты в `indicator_meta`) обращается к рядам страны четырьмя путями:

    1. ряды с тем же ключом карточки — тот же провайдер и тот же `dataset_stem`;
    2. ряды с тем же ключом слияния каталога — тот же приведённый провайдер и тот же `catalog_stem_alias`;
    3. карточки рядов из (1) и (2) — провайдер и `dataset_stem` те же, что у ряда-источника;
    4. карточки той же группы срезов — тот же `variant_stem_alias(dataset_stem)`; ряды другого провайдера
       `build_variants` отбрасывает.

    `catalog_stem_alias` и `variant_stem_alias` зависят от набора только через `dataset_stem`, поэтому каждая
    карточка (у неё один провайдер и один `dataset_stem`) попадает в отбор целиком или не попадает вовсе:
    состав и первичный ряд любой прочитанной карточки те же, что при полном чтении страны.
    """
    provider = _merge_provider(getattr(indicator, "provider", None))
    alias = catalog_stem_alias(indicator.dataset_id)
    variant = variant_stem_alias(dataset_stem(indicator.dataset_id))
    return [
        (pair_provider, dataset_id)
        for pair_provider, dataset_id in directory
        if _merge_provider(pair_provider) == provider
        and (
            catalog_stem_alias(dataset_id) == alias
            or variant_stem_alias(dataset_stem(dataset_id)) == variant
        )
    ]


def compare_dataset_pairs(concept: Any, directory: Iterable[DatasetPair]) -> list[DatasetPair]:
    """Пары справочника, чьи ряды могут соответствовать понятию сравнения.

    `concept_for_indicator` первым шагом требует, чтобы набор ряда входил в список наборов понятия у его
    провайдера; остальные ряды понятию не соответствуют при любых единицах и срезах. Национальные ряды
    добираются отдельно по коду (`national_codes_for_concept`).
    """
    return [
        (provider, dataset_id)
        for provider, dataset_id in directory
        if concept_dataset_allowed(concept, provider, dataset_id)
    ]


async def country_dataset_directory(db: AsyncSession, country_id: int) -> list[DatasetPair]:
    """Разные пары (провайдер, набор данных) страны — чтение только по индексу."""
    rows = (
        await db.execute(
            select(WorldIndicator.provider, WorldIndicator.dataset_id)
            .where(WorldIndicator.country_id == country_id)
            .distinct()
        )
    ).all()
    return [(provider, dataset_id) for provider, dataset_id in rows]


async def country_indicators_for_datasets(
    db: AsyncSession,
    country_id: int,
    pairs: Sequence[DatasetPair],
    *,
    codes: Iterable[str] = (),
) -> list[WorldIndicator]:
    """Полные ряды страны из заданных пар (провайдер, набор) и с заданными кодами, в порядке `id`."""
    datasets_by_provider: dict[str, set[str]] = {}
    for provider, dataset_id in pairs:
        datasets_by_provider.setdefault(provider, set()).add(dataset_id)
    clauses = [
        and_(
            WorldIndicator.provider == provider,
            WorldIndicator.dataset_id.in_(sorted(datasets)),
        )
        for provider, datasets in sorted(datasets_by_provider.items())
    ]
    code_list = sorted(set(codes))
    if code_list:
        clauses.append(WorldIndicator.code.in_(code_list))
    if not clauses:
        return []
    return list(
        (
            await db.execute(
                select(WorldIndicator)
                .where(WorldIndicator.country_id == country_id, or_(*clauses))
                .order_by(WorldIndicator.id)
            )
        ).scalars().all()
    )


async def card_country_indicators(db: AsyncSession, indicator: WorldIndicator) -> list[WorldIndicator]:
    """Ряды страны, достаточные для карточки `indicator`: частоты, первичный ряд, срезы."""
    directory = await country_dataset_directory(db, indicator.country_id)
    return await country_indicators_for_datasets(
        db, indicator.country_id, card_dataset_pairs(indicator, directory),
    )


async def compare_country_indicators(
    db: AsyncSession,
    country_id: int,
    concept: Any,
    national_codes: Iterable[str],
) -> list[WorldIndicator]:
    """Ряды страны, достаточные для выбора ряда сравнения по понятию `concept`."""
    directory = await country_dataset_directory(db, country_id)
    return await country_indicators_for_datasets(
        db, country_id, compare_dataset_pairs(concept, directory), codes=national_codes,
    )
