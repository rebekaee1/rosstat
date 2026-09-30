"""Search destination adapters for existing family/canonical path contracts.

World resolution batches metadata reads while using the same key/rank/unit
definitions as legacy_redirects. It does not widen public eligibility.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.data.eurostat_listing import (
    card_key, catalog_merge_key, catalog_stem_alias, dataset_stem,
    measure_preference_rank, normalize_frequency,
)
from app.data.legacy_redirects import (
    _MERGE_MODE_TYPE_BY_UNIT, resolve_unlisted_indicator, world_card_primary_rank,
)
from app.models import WorldIndicator
from app.services import site_paths as paths
from app.services.search_intent import SearchIntent


@lru_cache(maxsize=1)
def _family_paths() -> dict[str, tuple[tuple[str, str, str], ...]]:
    from app.data.view_model_families import FAMILIES

    index = defaultdict(list)
    for family in FAMILIES:
        for mode in family.modes:
            index[mode.code].append((family.base, mode.group, mode.mode))
    return {code: tuple(modes) for code, modes in index.items()}


def russia_search_path(code: str, intent: SearchIntent) -> str:
    """One series may implement annual YoY and pop; retain requested group."""
    groups = {alt.removeprefix("search-mode-") for term in intent.terms for alt in term
        if alt.startswith("search-mode-")}
    for base, group, mode in _family_paths().get(code, ()):
        if group in groups:
            path = paths.russia_indicator(base)
            return path if code == base else f"{path}?mode={mode}"
    return resolve_unlisted_indicator(code) or paths.russia_indicator(code)


def russia_family_base(code: str) -> str | None:
    """Family identity for catalogue-headline ranking, never prefix guessing."""
    family = _family_paths().get(code, ())
    return family[0][0] if family else None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _card_key(row) -> tuple:
    return card_key(country_id=row.country_id, dataset_id=row.dataset_id,
        unit=row.unit, unit_ru=row.unit_ru, slice_json=row.slice_json)


def _merge_key(row) -> tuple:
    return catalog_merge_key(country_id=row.country_id, provider=row.provider,
        dataset_id=row.dataset_id, unit=row.unit, unit_ru=row.unit_ru, slice_json=row.slice_json)


async def world_search_paths(db: AsyncSession, requested: list[tuple[str, WorldIndicator]]) -> dict[tuple[str, str], str | None]:
    """Resolve a bounded ranked batch, one metadata SELECT for sibling groups.

Frequency siblings and catalogue merges follow resolve_world_frequency_sibling
exactly, including listed primary and points_count gates for merge targets.
"""
    output = {(slug, row.code): None for slug, row in requested}
    if not requested:
        return output
    groups: dict[tuple, set[str]] = defaultdict(set)
    for _slug, row in requested:
        stem = dataset_stem(row.dataset_id)
        if stem:
            groups[(row.country_id, row.provider, "frequency")].add(stem)
        if not row.is_listed:
            alias = catalog_stem_alias(row.dataset_id)
            if alias:
                groups[(row.country_id, row.provider, "merge")].update(alias.split("|"))
    clauses = []
    for (country_id, provider, kind), stems in groups.items():
        datasets = []
        for stem in stems:
            datasets.append(WorldIndicator.dataset_id == stem)
            pattern = _escape_like(stem) + ("\\_%" if kind == "frequency" else "%")
            datasets.append(WorldIndicator.dataset_id.like(pattern, escape="\\"))
        clauses.append(and_(WorldIndicator.country_id == country_id, WorldIndicator.provider == provider, or_(*datasets)))
    if not clauses:
        return output
    columns = (WorldIndicator.id, WorldIndicator.country_id, WorldIndicator.code,
        WorldIndicator.provider, WorldIndicator.dataset_id, WorldIndicator.unit,
        WorldIndicator.unit_ru, WorldIndicator.slice_json, WorldIndicator.frequency,
        WorldIndicator.points_count, WorldIndicator.history_end, WorldIndicator.is_listed)
    rows = list((await db.execute(select(WorldIndicator).options(load_only(*columns)).where(or_(*clauses)))).scalars())
    by_source = defaultdict(list)
    for row in rows:
        by_source[(row.country_id, row.provider)].append(row)
    for slug, row in requested:
        stem = dataset_stem(row.dataset_id)
        source = by_source[(row.country_id, row.provider)]
        key = _card_key(row)
        siblings = [candidate for candidate in source
            if (candidate.dataset_id == stem or candidate.dataset_id.startswith(stem + "_")) and _card_key(candidate) == key] if stem else []
        siblings = siblings or [row]
        freq = normalize_frequency(row.frequency) or "monthly"
        freq = freq if freq in ("monthly", "quarterly", "annual") else "monthly"
        if len(siblings) >= 2:
            primary = min(siblings, key=world_card_primary_rank)
            if primary.is_listed and primary.code != row.code:
                output[(slug, row.code)] = f"{paths.indicator(slug, primary.code)}?mode=level-{freq}"
            continue
        if row.is_listed:
            continue
        merge_key = _merge_key(row)
        members = [candidate for candidate in source if candidate.code != row.code
            and candidate.is_listed and (candidate.points_count or 0) > 0 and _merge_key(candidate) == merge_key]
        if members:
            primary = min(members, key=measure_preference_rank)
            unit = (row.unit or "").strip().upper().replace("-", "_")
            mode = _MERGE_MODE_TYPE_BY_UNIT.get(unit, "level")
            output[(slug, row.code)] = f"{paths.indicator(slug, primary.code)}?mode={mode}-{freq}"
    return output
