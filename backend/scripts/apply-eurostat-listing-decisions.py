#!/usr/bin/env python3
"""Внедрить eurostat_listing_decisions.json без полного repair (экономия RAM).

Только датасеты из файла решений:
- no → is_listed=false
- full_ok → кандидаты через техворота, primary по card_key
- headline_ok → TOTAL по варьирующим dim (иначе 1 лучший ряд на страну)

Уже listed датасеты вне файла не трогаем. Затем лёгкий дедуп имён
внутри затронутых стран и bump world-кэша.

Запуск::

    docker compose exec backend python /app/scripts/apply-eurostat-listing-decisions.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import defaultdict

from sqlalchemy import select, text

sys.path.insert(0, "/app")

from app.core.cache import bump_namespaces  # noqa: E402
from app.data.eurostat_country_visibility import (  # noqa: E402
    is_eurostat_listing_pipeline_target,
)
from app.data.eurostat_listing import (  # noqa: E402
    card_key,
    is_headline_aggregate_slice,
    is_short_annual_singleton,
    is_stale_history,
    listing_rank_tuple,
    load_listing_decisions,
    meets_listing_depth,
    normalize_frequency,
    varying_narrowing_dims,
)
from app.data.eurostat_titles_ru import (  # noqa: E402
    listing_substance_score,
    slice_reflected_in_name,
)
from app.data.eurostat_units_ru import (  # noqa: E402
    is_sensitive_topic,
    unit_is_listable,
)
from app.database import async_session  # noqa: E402
from app.models import WorldCountry, WorldIndicator  # noqa: E402
from app.services.world_cards import pick_primary  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("apply-listing-decisions")


def _rank(ind: WorldIndicator) -> tuple:
    return listing_rank_tuple(
        points_count=ind.points_count,
        unit=ind.unit,
        dataset_id=ind.dataset_id,
        slice_json=ind.slice_json or {},
        substance_score_fn=listing_substance_score,
    )


def _passes_tech(ind: WorldIndicator, *, mode: str) -> bool:
    if not is_eurostat_listing_pipeline_target(ind):
        return False
    if (ind.name_quality or "") not in ("curated", "composed"):
        return False
    if is_sensitive_topic(ind.dataset_id):
        return False
    if not unit_is_listable(ind.unit_ru or ""):
        return False
    if is_stale_history(ind.history_end):
        return False
    # Для редакторски одобренных датасетов имя curated уже аттестовано;
    # сужающий код в slice (nace/indic) не должен прятать весь набор.
    if mode not in {"full_ok", "headline_ok"}:
        if not slice_reflected_in_name(ind.name_ru, ind.slice_json or {}):
            return False
    if not meets_listing_depth(ind.frequency, ind.points_count):
        return False
    return True


async def _stats() -> dict:
    async with async_session() as db:
        row = (
            await db.execute(
                text(
                    """
                    SELECT
                      (SELECT COUNT(DISTINCT dataset_id)
                         FROM world_indicators WHERE provider='eurostat') AS eurostat_ds,
                      (SELECT COUNT(DISTINCT dataset_id)
                         FROM world_indicators
                        WHERE provider='eurostat' AND is_listed) AS listed_ds,
                      (SELECT COUNT(*) FROM world_indicators WHERE is_listed) AS listed_series,
                      (SELECT COUNT(*) FROM (
                          SELECT dataset_id FROM world_indicators
                           WHERE provider='eurostat'
                           GROUP BY dataset_id
                          HAVING COUNT(*) FILTER (WHERE is_listed)=0
                      ) z) AS zero_listed_ds
                    """
                )
            )
        ).mappings().one()
        return dict(row)


async def apply_one_dataset(
    ds: str,
    mode: str,
    *,
    national_passport_ids: set[int],
) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    async with async_session() as db:
        members = (
            await db.execute(
                select(WorldIndicator).where(WorldIndicator.dataset_id == ds)
            )
        ).scalars().all()
        if not members:
            counts["missing_dataset"] = 1
            return dict(counts)

        # Сначала всё снять с витрины у этого dataset_id (пересоберём).
        for ind in members:
            if ind.is_listed:
                ind.is_listed = False
                counts["cleared"] += 1

        if mode == "no":
            await db.commit()
            counts["datasets_no"] = 1
            return dict(counts)

        candidates = [i for i in members if _passes_tech(i, mode=mode)]
        if national_passport_ids:
            candidates = [
                i for i in candidates if i.country_id not in national_passport_ids
            ]

        if mode == "headline_ok":
            varying = varying_narrowing_dims([m.slice_json for m in members])
            by_country: dict[int, list[WorldIndicator]] = defaultdict(list)
            for ind in candidates:
                by_country[ind.country_id].append(ind)
            narrowed: list[WorldIndicator] = []
            for _cid, cands in by_country.items():
                keep = [
                    i
                    for i in cands
                    if is_headline_aggregate_slice(i.slice_json, varying_dims=varying)
                ]
                if not keep:
                    keep = [max(cands, key=_rank)]
                    counts["headline_fallback"] += 1
                narrowed.extend(keep)
            candidates = narrowed
            counts["datasets_headline_ok"] = 1
        else:
            counts["datasets_full_ok"] = 1

        # Склейка частот / дублей по card_key внутри датасета.
        groups: dict[tuple, list[WorldIndicator]] = defaultdict(list)
        for ind in candidates:
            groups[
                card_key(
                    country_id=ind.country_id,
                    dataset_id=ind.dataset_id,
                    unit=ind.unit,
                    unit_ru=ind.unit_ru,
                    slice_json=ind.slice_json or {},
                )
            ].append(ind)

        for _key, group in groups.items():
            primary = pick_primary(group, listing_substance_score)
            if primary is None:
                counts["no_primary"] += 1
                continue
            # short-annual singleton: не режем editor-approved —
            # иначе нишевые годовые ряды 10–11 точек исчезают целиком.
            if (
                mode not in {"full_ok", "headline_ok"}
                and len({normalize_frequency(m.frequency) for m in group}) == 1
                and is_short_annual_singleton(
                    primary.frequency, primary.points_count
                )
            ):
                counts["short_annual_skip"] += 1
                continue
            primary.is_listed = True
            counts["listed"] += 1

        await db.commit()
        return dict(counts)


async def dedupe_names_for_datasets(dataset_ids: list[str]) -> int:
    """Снять дубли display-name внутри страны среди затронутых датасетов."""
    n = 0
    async with async_session() as db:
        inds = (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.dataset_id.in_(dataset_ids),
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalars().all()
        # Подтянуть всех listed с теми же именами в тех же странах.
        if not inds:
            return 0
        country_ids = {i.country_id for i in inds}
        names = {i.name_ru for i in inds if i.name_ru}
        rivals = (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.country_id.in_(country_ids),
                    WorldIndicator.name_ru.in_(names),
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalars().all()
        by_name: dict[tuple, list[WorldIndicator]] = defaultdict(list)
        for ind in rivals:
            by_name[(ind.country_id, ind.name_ru)].append(ind)
        for _key, group in by_name.items():
            if len(group) < 2:
                continue
            ranked = sorted(group, key=_rank, reverse=True)
            for other in ranked[1:]:
                # чужие датасеты вне решений не трогаем, если они выиграли rank
                other.is_listed = False
                n += 1
        await db.commit()
    return n


async def main() -> int:
    decisions = load_listing_decisions()
    log.info("decisions=%d", len(decisions))
    before = await _stats()
    log.info("BEFORE %s", before)

    async with async_session() as db:
        passport_codes = frozenset({
            "CA", "AU", "UK", "GB", "US", "JP", "CN", "IN", "BR", "MX", "KR",
        })
        rows = (
            await db.execute(
                select(WorldCountry.id).where(
                    WorldCountry.code.in_(sorted(passport_codes))
                )
            )
        ).scalars().all()
        passport_ids = set(rows)

    totals: dict[str, int] = defaultdict(int)
    items = sorted(decisions.items())
    for idx, (ds, meta) in enumerate(items, 1):
        mode = meta["mode"]
        part = await apply_one_dataset(
            ds, mode, national_passport_ids=passport_ids
        )
        for k, v in part.items():
            totals[k] += v
        if idx % 50 == 0 or idx == len(items):
            log.info("progress %d/%d totals=%s", idx, len(items), dict(totals))

    n_dedupe = await dedupe_names_for_datasets(sorted(decisions))
    log.info("name_deduped=%d", n_dedupe)

    try:
        await bump_namespaces("world")
    except Exception as exc:  # noqa: BLE001
        log.warning("cache bump skipped: %s", exc)

    after = await _stats()
    log.info("AFTER %s", after)
    log.info("DONE totals=%s", dict(totals))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
