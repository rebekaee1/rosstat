#!/usr/bin/env python3
"""Починка витрины мирового блока без полной перезагрузки Eurostat.

1. Удаляет исключённые geo.
2. Пересобирает name_ru / unit_ru / seo_*.
3. Базовые предохранители (quality / unit / sensitive / depth).
4. Редакторские режимы датасета (full_ok / headline_ok / no).
5. Дефекты: региональный дубль, срез не в имени, мёртвые ряды, короткие annual.
6. Склейка частот по строгому card_key → is_listed только у primary.

Запуск::

    docker compose exec backend python /app/scripts/repair-world-listing.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import defaultdict

from sqlalchemy import delete, select, text

sys.path.insert(0, "/app")

from app.core.cache import bump_namespaces  # noqa: E402
from app.data.eurostat_listing import (  # noqa: E402
    card_key,
    is_headline_aggregate_slice,
    is_short_annual_singleton,
    is_stale_history,
    listing_rank_tuple,
    listing_semantic_key,
    load_listing_decisions,
    meets_listing_depth,
    national_counterpart_dataset,
    normalize_frequency,
    varying_narrowing_dims,
)
from app.data.eurostat_titles_ru import (  # noqa: E402
    build_public_name,
    country_prepositional,
    is_listed_for_quality,
    listing_substance_score,
    public_description,
    public_methodology,
    public_seo_title,
    resolve_dataset_title,
    slice_reflected_in_name,
)
from app.data.eurostat_units_ru import (  # noqa: E402
    is_sensitive_topic,
    resolve_public_unit,
    unit_is_listable,
)
from app.data.eurostat_country_visibility import (  # noqa: E402
    country_passes_vitrine,
    indicator_counts_toward_national_core,
    is_eurostat_listing_pipeline_target,
    is_eurostat_retitle_target,
)
from app.database import async_session  # noqa: E402
from app.models import WorldCountry, WorldDataPoint, WorldIndicator  # noqa: E402
from app.services.eurostat_parser import EXCLUDED_GEO_CODES  # noqa: E402
from app.services.world_cards import pick_primary  # noqa: E402
from app.services.world_plausibility import is_plausible_for_listing  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("repair-world-listing")


async def purge_excluded_geos() -> int:
    async with async_session() as db:
        rows = (
            await db.execute(
                select(WorldCountry).where(
                    WorldCountry.code.in_(sorted(EXCLUDED_GEO_CODES))
                    | WorldCountry.slug.in_(("russia",))
                )
            )
        ).scalars().all()
        n = 0
        for c in rows:
            ind_ids = (
                await db.execute(
                    select(WorldIndicator.id).where(WorldIndicator.country_id == c.id)
                )
            ).scalars().all()
            if ind_ids:
                await db.execute(
                    delete(WorldDataPoint).where(
                        WorldDataPoint.indicator_id.in_(ind_ids)
                    )
                )
                await db.execute(
                    delete(WorldIndicator).where(WorldIndicator.id.in_(ind_ids))
                )
            await db.delete(c)
            n += 1
            log.info("purged country %s (%s)", c.code, c.slug)
        await db.commit()
        return n


async def retitle_all() -> tuple[int, dict[str, int]]:
    """Пересобрать имена и единицы. Returns (updated, candidate_reasons)."""
    reasons: dict[str, int] = defaultdict(int)
    async with async_session() as db:
        inds = (await db.execute(select(WorldIndicator))).scalars().all()
        catalog = {
            r["dataset_id"]: r["title"] or ""
            for r in (
                await db.execute(
                    text(
                        """
                        SELECT dataset_id, title
                        FROM research.source_catalog
                        WHERE source = 'eurostat'
                        """
                    )
                )
            ).mappings().all()
        }
        countries = {
            c.id: c
            for c in (await db.execute(select(WorldCountry))).scalars().all()
        }

        # Частоты siblings по card_key — для честных описаний/методологии.
        by_card: dict[tuple, list[WorldIndicator]] = defaultdict(list)
        ind_card_key: dict[int, tuple] = {}
        for ind in inds:
            key = card_key(
                country_id=ind.country_id,
                dataset_id=ind.dataset_id,
                unit=ind.unit,
                unit_ru=ind.unit_ru,
                slice_json=ind.slice_json or {},
            )
            by_card[key].append(ind)
            ind_card_key[ind.id] = key

        updated = 0
        skipped = 0
        for ind in inds:
            # National passport / curated — не трогать Eurostat-композитором.
            if not is_eurostat_retitle_target(ind):
                skipped += 1
                reasons["skipped-non-eurostat-or-curated"] += 1
                continue

            en = catalog.get(ind.dataset_id) or ind.name_en or ""
            title = resolve_dataset_title(ind.dataset_id, en)
            unit = ind.unit or (ind.slice_json or {}).get("unit") or ""
            unit_ru, prov = resolve_public_unit(
                dataset_id=ind.dataset_id,
                unit_code=unit,
                slice_json=ind.slice_json or {},
            )
            unit_ru = unit_ru or ""
            name_ru = build_public_name(
                title.name_ru,
                unit=unit,
                slice_json=ind.slice_json or {},
                frequency=ind.frequency,
                dataset_id=ind.dataset_id,
            )
            quality = title.quality

            # кандидат на листинг (ещё не final is_listed)
            ok = is_listed_for_quality(quality)
            if ok and is_sensitive_topic(ind.dataset_id):
                ok = False
                reasons["sensitive-topic"] += 1
            elif ok and not unit_is_listable(unit_ru):
                ok = False
                reasons[prov or "missing-unit"] += 1

            siblings = by_card.get(ind_card_key[ind.id]) or [ind]
            avail_freqs = sorted({
                normalize_frequency(s.frequency)
                for s in siblings
                if s.frequency
            })
            # История по всей карточке (глубже любого sibling).
            hs = min(
                (s.history_start for s in siblings if s.history_start),
                default=ind.history_start,
            )
            he = max(
                (s.history_end for s in siblings if s.history_end),
                default=ind.history_end,
            )
            country = countries.get(ind.country_id)
            cname = country.name_ru if country else ""
            prep = country_prepositional(
                country.slug if country else None, cname
            )

            ind.name_ru = name_ru
            ind.name_quality = quality
            ind.unit = unit or ind.unit
            ind.unit_ru = unit_ru
            ind.description = public_description(
                name_ru,
                ind.frequency,
                unit_ru,
                country_name_ru=cname,
                country_prep=prep,
                history_start=hs,
                history_end=he,
                available_frequencies=avail_freqs,
            )
            ind.methodology = public_methodology(
                ind.frequency,
                unit_ru,
                available_frequencies=avail_freqs,
            )
            ind.seo_description = ind.description
            ind.seo_title = public_seo_title(
                name_ru, country_prep=prep, country_name_ru=cname
            )
            ind.seo_keywords = (
                f"{name_ru}, {cname}, {name_ru} в {prep}, "
                f"{cname} статистика, график"
                if cname
                else f"{name_ru}, статистика, график"
            )
            # временный флаг: прошёл базовые фильтры (без depth/card)
            ind.is_listed = ok
            updated += 1

        if skipped:
            log.info(
                "retitle skipped %d non-eurostat/curated indicator(s)",
                skipped,
            )
        await db.commit()
        return updated, dict(reasons)


def _rank(x: WorldIndicator) -> tuple:
    return listing_rank_tuple(
        points_count=x.points_count,
        unit=x.unit,
        dataset_id=x.dataset_id,
        slice_json=x.slice_json or {},
        substance_score_fn=listing_substance_score,
    )


async def apply_editorial_listing_modes() -> dict[str, int]:
    """Редакторские режимы: no → off; headline_ok → TOTAL/ключ; full_ok → без доп. фильтра.

    Решения — ``eurostat_listing_decisions.json``. Датасеты вне файла не трогаем.
    """
    decisions = load_listing_decisions()
    counts: dict[str, int] = defaultdict(int)
    if not decisions:
        log.warning("editorial decisions file empty/missing — skip")
        return dict(counts)

    async with async_session() as db:
        inds = (await db.execute(select(WorldIndicator))).scalars().all()
        by_ds: dict[str, list[WorldIndicator]] = defaultdict(list)
        for ind in inds:
            if not is_eurostat_listing_pipeline_target(ind):
                continue
            ds = (ind.dataset_id or "").strip().lower()
            if ds in decisions:
                by_ds[ds].append(ind)

        for ds, members in by_ds.items():
            mode = decisions[ds]["mode"]
            if mode == "no":
                for ind in members:
                    if ind.is_listed:
                        ind.is_listed = False
                        counts["editorial_no"] += 1
                counts["datasets_no"] += 1
                continue

            if mode == "full_ok":
                counts["datasets_full_ok"] += 1
                continue

            # headline_ok
            counts["datasets_headline_ok"] += 1
            varying = varying_narrowing_dims([m.slice_json for m in members])
            by_country: dict[int, list[WorldIndicator]] = defaultdict(list)
            for ind in members:
                if ind.is_listed:
                    by_country[ind.country_id].append(ind)

            for _country_id, cands in by_country.items():
                keep = [
                    i
                    for i in cands
                    if is_headline_aggregate_slice(
                        i.slice_json, varying_dims=varying
                    )
                ]
                if not keep:
                    keep = [max(cands, key=_rank)]
                    counts["editorial_headline_fallback"] += 1
                keep_ids = {i.id for i in keep}
                for ind in cands:
                    if ind.id in keep_ids:
                        counts["editorial_headline_keep"] += 1
                    else:
                        ind.is_listed = False
                        counts["editorial_headline_trim"] += 1

        await db.commit()
        return dict(counts)


async def apply_defect_filters() -> dict[str, int]:
    """Снять с кандидатов: срез не в имени, региональный дубль, stale, правдоподобие."""
    counts: dict[str, int] = defaultdict(int)
    async with async_session() as db:
        inds = (
            await db.execute(select(WorldIndicator).where(WorldIndicator.is_listed.is_(True)))
        ).scalars().all()

        # 1) срез не отражён в имени / противоречие понятия
        for ind in inds:
            if not is_eurostat_listing_pipeline_target(ind):
                continue
            if not slice_reflected_in_name(ind.name_ru, ind.slice_json or {}):
                ind.is_listed = False
                counts["slice_not_in_name"] += 1

        # 2) мёртвые ряды
        for ind in inds:
            if not ind.is_listed:
                continue
            if not is_eurostat_listing_pipeline_target(ind):
                continue
            if is_stale_history(ind.history_end):
                ind.is_listed = False
                counts["stale_history"] += 1

        # 3) региональный дубль национального
        by_ds: dict[tuple[int, str], list[WorldIndicator]] = defaultdict(list)
        for ind in inds:
            if ind.is_listed and is_eurostat_listing_pipeline_target(ind):
                by_ds[(ind.country_id, (ind.dataset_id or "").lower())].append(ind)

        for ind in inds:
            if not ind.is_listed:
                continue
            if not is_eurostat_listing_pipeline_target(ind):
                continue
            national = national_counterpart_dataset(ind.dataset_id)
            if not national:
                continue
            nationals = by_ds.get((ind.country_id, national), [])
            if not nationals:
                continue
            n_ok = [
                n for n in nationals
                if (n.unit or "").upper() == (ind.unit or "").upper()
                or (n.unit_ru or "") == (ind.unit_ru or "")
            ]
            if n_ok:
                ind.is_listed = False
                counts["regional_duplicate"] += 1

        # 4) правдоподобие значений (предохранитель) — батч точек
        listed_ids = [
            i.id for i in inds
            if i.is_listed and is_eurostat_listing_pipeline_target(i)
        ]
        values_by_id: dict[int, list[float]] = defaultdict(list)
        if listed_ids:
            # чанками, чтобы не раздувать память одним огромным IN
            chunk = 2000
            for offset in range(0, len(listed_ids), chunk):
                part = listed_ids[offset : offset + chunk]
                rows = (
                    await db.execute(
                        select(WorldDataPoint.indicator_id, WorldDataPoint.value).where(
                            WorldDataPoint.indicator_id.in_(part)
                        )
                    )
                ).all()
                for iid, val in rows:
                    try:
                        values_by_id[int(iid)].append(float(val))
                    except (TypeError, ValueError):
                        continue

        for ind in inds:
            if not ind.is_listed:
                continue
            if not is_eurostat_listing_pipeline_target(ind):
                continue
            vals = values_by_id.get(ind.id) or []
            if not is_plausible_for_listing(
                name_ru=ind.name_ru,
                unit=ind.unit,
                unit_ru=ind.unit_ru,
                slice_json=ind.slice_json or {},
                values=vals,
                dataset_id=ind.dataset_id,
            ):
                ind.is_listed = False
                counts["plausibility"] += 1

        await db.commit()
        return dict(counts)


async def apply_country_visibility() -> dict[str, int]:
    """Проставить ``WorldCountry.is_active`` по витрине и согласовать is_listed.

    Единая точка истины витрины стран — флаг ``is_active`` в БД (не
    пересчёт в каждом потребителе). Путь: Eurostat-порог ИЛИ national_core
    (свежий компактный паспорт / нац. провайдер / ISO-allowlist).
    Идемпотентно: повторный прогон даёт тот же набор. Индикаторы скрытой
    страны снимаются с листинга (``is_listed=false``), данные остаются;
    при возврате страны поверх порога следующий fold снова выставит
    listed у qualifying рядов.
    """
    import statistics

    stats: dict[str, int] = defaultdict(int)
    async with async_session() as db:
        countries = (await db.execute(select(WorldCountry))).scalars().all()
        inds = (await db.execute(select(WorldIndicator))).scalars().all()
        by_country: dict[int, list[WorldIndicator]] = defaultdict(list)
        for ind in inds:
            by_country[ind.country_id].append(ind)

        listed_counts: list[int] = []
        # (country, n_listed, n_cats, fresh_listed, has_non_eurostat)
        meta: list[tuple[WorldCountry, int, int, int, bool]] = []
        for c in countries:
            members = by_country.get(c.id) or []
            listed = [i for i in members if i.is_listed]
            cats = {i.category_ru for i in listed if i.category_ru}
            n_listed = len(listed)
            fresh = [i for i in listed if indicator_counts_toward_national_core(i)]
            has_non_eurostat = any(
                (getattr(i, "provider", None) or "").lower() != "eurostat"
                for i in fresh
            )
            listed_counts.append(n_listed)
            meta.append((c, n_listed, len(cats), len(fresh), has_non_eurostat))

        median_listed = float(statistics.median(listed_counts)) if listed_counts else 0.0
        stats["median_listed"] = int(round(median_listed))

        active_ids: set[int] = set()
        for c, n_listed, n_cats, n_fresh, has_non_eurostat in meta:
            ok = country_passes_vitrine(
                listed_cards=n_listed,
                category_count=n_cats,
                median_listed=median_listed,
                country_code=c.code,
                fresh_listed_count=n_fresh,
                has_non_eurostat=has_non_eurostat,
            )
            if ok:
                active_ids.add(c.id)
            if c.is_active and not ok:
                c.is_active = False
                stats["deactivated"] += 1
                log.info(
                    "hide country %s (%s): listed=%d cats=%d fresh=%d "
                    "non_eurostat=%s median=%.0f",
                    c.code, c.slug, n_listed, n_cats, n_fresh,
                    has_non_eurostat, median_listed,
                )
            elif (not c.is_active) and ok:
                c.is_active = True
                stats["reactivated"] += 1
                log.info(
                    "show country %s (%s): listed=%d cats=%d fresh=%d "
                    "non_eurostat=%s median=%.0f",
                    c.code, c.slug, n_listed, n_cats, n_fresh,
                    has_non_eurostat, median_listed,
                )
            elif ok:
                stats["kept_active"] += 1
            else:
                stats["kept_hidden"] += 1

        # Согласовать is_listed с флагом страны (sitemap/потребители по listed).
        unlisted_for_hidden = 0
        for ind in inds:
            if ind.country_id not in active_ids and ind.is_listed:
                ind.is_listed = False
                unlisted_for_hidden += 1
        stats["indicators_unlisted_inactive_country"] = unlisted_for_hidden

        await db.commit()
        return dict(stats)


# Страны с national-core YAML: eurostat не должен снова всплывать на витрину
# после fold_frequency_cards / defect filters.
_NATIONAL_PASSPORT_CODES: frozenset[str] = frozenset({
    "CA", "AU", "UK", "GB", "US", "JP", "CN", "IN", "BR", "MX", "KR",
})


async def unlist_eurostat_on_national_passports() -> dict[str, int]:
    """National-first: снять eurostat leftovers с listed у passport-стран."""
    from collections import Counter

    async with async_session() as db:
        countries = (
            await db.execute(
                select(WorldCountry).where(
                    WorldCountry.code.in_(sorted(_NATIONAL_PASSPORT_CODES))
                )
            )
        ).scalars().all()
        ids = {c.id: c.code for c in countries}
        if not ids:
            return {}
        inds = (
            await db.execute(
                select(WorldIndicator).where(
                    WorldIndicator.country_id.in_(list(ids)),
                    WorldIndicator.is_listed.is_(True),
                )
            )
        ).scalars().all()
        counts: Counter[str] = Counter()
        for ind in inds:
            if (ind.provider or "").lower() != "eurostat":
                continue
            ind.is_listed = False
            counts[ids[ind.country_id]] += 1
        await db.commit()
        return dict(counts)

    """Внутри одной частоты: смысловой ключ → самый глубокий."""
    async with async_session() as db:
        inds = (
            await db.execute(select(WorldIndicator).where(WorldIndicator.is_listed.is_(True)))
        ).scalars().all()
        # Только Eurostat non-curated — национальный паспорт не схлопываем.
        inds = [i for i in inds if is_eurostat_listing_pipeline_target(i)]

        def _collapse(groups: dict) -> int:
            n = 0
            for members in groups.values():
                if len(members) < 2:
                    continue
                ranked = sorted(members, key=_rank, reverse=True)
                for other in ranked[1:]:
                    if other.is_listed:
                        other.is_listed = False
                        n += 1
            return n

        by_sem: dict[tuple, list[WorldIndicator]] = defaultdict(list)
        for ind in inds:
            by_sem[
                listing_semantic_key(
                    country_id=ind.country_id,
                    dataset_id=ind.dataset_id,
                    name_ru=ind.name_ru,
                    frequency=ind.frequency,
                    unit=ind.unit,
                    unit_ru=ind.unit_ru,
                    slice_json=ind.slice_json or {},
                )
            ].append(ind)
        unlisted = _collapse(by_sem)

        by_name: dict[tuple, list[WorldIndicator]] = defaultdict(list)
        for ind in inds:
            if ind.is_listed:
                by_name[(ind.country_id, ind.name_ru)].append(ind)
        unlisted += _collapse(by_name)

        await db.commit()
        return unlisted


async def fold_frequency_cards() -> dict[str, int]:
    """Склеить частоты по card_key: listed только primary; shallow members ок."""
    stats: dict[str, int] = defaultdict(int)
    async with async_session() as db:
        all_inds = (await db.execute(select(WorldIndicator))).scalars().all()
        # National passport: is_listed остаётся как в БД (не eurostat fold).
        eurostat_inds = [
            i for i in all_inds if is_eurostat_listing_pipeline_target(i)
        ]
        quality_ok = [
            i for i in eurostat_inds
            if (i.name_quality or "") in ("curated", "composed")
            and not is_sensitive_topic(i.dataset_id)
            and unit_is_listable(i.unit_ru or "")
            and slice_reflected_in_name(i.name_ru, i.slice_json or {})
        ]

        # Национальные датасеты, доступные как кандидаты (для regional filter)
        national_present: set[tuple[int, str, str]] = set()
        for ind in quality_ok:
            ds = (ind.dataset_id or "").lower()
            if "_r_" in ds:
                continue
            national_present.add((
                ind.country_id,
                ds,
                (ind.unit or "").upper(),
            ))

        groups: dict[tuple, list[WorldIndicator]] = defaultdict(list)
        for ind in quality_ok:
            # региональный дубль — не кандидат в карточку/primary
            national = national_counterpart_dataset(ind.dataset_id)
            if national:
                key_u = (ind.country_id, national, (ind.unit or "").upper())
                key_empty = (ind.country_id, national, "")
                if key_u in national_present or any(
                    c == ind.country_id and d == national
                    for c, d, _u in national_present
                ):
                    stats["regional_skipped"] = stats.get("regional_skipped", 0) + 1
                    continue
            groups[
                card_key(
                    country_id=ind.country_id,
                    dataset_id=ind.dataset_id,
                    unit=ind.unit,
                    unit_ru=ind.unit_ru,
                    slice_json=ind.slice_json or {},
                )
            ].append(ind)

        # Сбрасываем только Eurostat; national passport не трогаем.
        for ind in eurostat_inds:
            ind.is_listed = False
        stats["preserved_non_eurostat"] = len(all_inds) - len(eurostat_inds)

        # Не возвращать eurostat на витрину стран с national-core YAML.
        country_by_id = {c.id: c.code for c in (
            await db.execute(select(WorldCountry))
        ).scalars().all()}

        multi_freq = 0
        members_in_multi = 0
        listed_primaries = 0
        shallow_members_kept = 0

        for _key, members in groups.items():
            sample = members[0]
            cc = country_by_id.get(sample.country_id, "")
            if cc in _NATIONAL_PASSPORT_CODES:
                stats["national_passport_eurostat_skipped"] = (
                    stats.get("national_passport_eurostat_skipped", 0) + 1
                )
                continue

            primary = pick_primary(members, listing_substance_score)
            if primary is None:
                stats["no_primary_depth"] = stats.get("no_primary_depth", 0) + 1
                continue

            freqs = {normalize_frequency(m.frequency) for m in members}
            if len(freqs) > 1:
                multi_freq += 1
                members_in_multi += len(members)

            if (
                len({normalize_frequency(m.frequency) for m in members}) == 1
                and is_short_annual_singleton(primary.frequency, primary.points_count)
            ):
                stats["short_annual_singleton"] = stats.get("short_annual_singleton", 0) + 1
                continue

            primary.is_listed = True
            listed_primaries += 1

            for m in members:
                if m.id == primary.id:
                    continue
                if not meets_listing_depth(m.frequency, m.points_count):
                    shallow_members_kept += 1

        stats["cards_listed"] = listed_primaries
        stats["multi_freq_groups"] = multi_freq
        stats["series_in_multi_freq"] = members_in_multi
        stats["shallow_members_in_cards"] = shallow_members_kept
        stats["card_groups_total"] = len(groups)
        # display_name_dedup — ПОСЛЕ plausibility (см. dedupe_display_names),
        # иначе константный IPRD «съедает» имя и после unlist карточки нет.
        stats["cards_listed"] = sum(1 for i in all_inds if i.is_listed)

        await db.commit()
        return dict(stats)


async def dedupe_same_frequency() -> int:
    """Внутри одной частоты: смысловой ключ → самый глубокий."""
    async with async_session() as db:
        inds = (
            await db.execute(select(WorldIndicator).where(WorldIndicator.is_listed.is_(True)))
        ).scalars().all()
        inds = [i for i in inds if is_eurostat_listing_pipeline_target(i)]

        def _collapse(groups: dict) -> int:
            n = 0
            for members in groups.values():
                if len(members) < 2:
                    continue
                ranked = sorted(members, key=_rank, reverse=True)
                for other in ranked[1:]:
                    if other.is_listed:
                        other.is_listed = False
                        n += 1
            return n

        by_sem: dict[tuple, list[WorldIndicator]] = defaultdict(list)
        for ind in inds:
            by_sem[
                listing_semantic_key(
                    country_id=ind.country_id,
                    dataset_id=ind.dataset_id,
                    name_ru=ind.name_ru or "",
                    frequency=ind.frequency,
                    unit=ind.unit,
                    unit_ru=ind.unit_ru,
                    slice_json=ind.slice_json or {},
                )
            ].append(ind)
        unlisted = _collapse(by_sem)

        by_name: dict[tuple, list[WorldIndicator]] = defaultdict(list)
        for ind in inds:
            if ind.is_listed:
                by_name[(ind.country_id, ind.name_ru)].append(ind)
        unlisted += _collapse(by_name)

        await db.commit()
        return unlisted


async def dedupe_display_names() -> int:
    """Схлопнуть одинаковые отображаемые имена внутри страны (после plausibility)."""
    from app.services.world_cards import display_name

    async with async_session() as db:
        inds = (
            await db.execute(select(WorldIndicator).where(WorldIndicator.is_listed.is_(True)))
        ).scalars().all()
        # Eurostat-эвристика имён: national passport не unlist'им.
        inds = [i for i in inds if is_eurostat_listing_pipeline_target(i)]
        by_disp: dict[tuple, list[WorldIndicator]] = defaultdict(list)
        for ind in inds:
            by_disp[(ind.country_id, display_name(ind.name_ru))].append(ind)
        n = 0
        for _k, members in by_disp.items():
            if len(members) < 2:
                continue
            ranked = sorted(members, key=_rank, reverse=True)
            for other in ranked[1:]:
                other.is_listed = False
                n += 1
        await db.commit()
        return n


async def main() -> int:
    before = await _stats()
    log.info("BEFORE %s", before)

    n_purge = await purge_excluded_geos()
    n_upd, base_reasons = await retitle_all()
    editorial = await apply_editorial_listing_modes()
    defect = await apply_defect_filters()
    n_dedupe = await dedupe_same_frequency()
    fold = await fold_frequency_cards()
    # правдоподобие ещё раз после fold (primary могли смениться)
    defect2 = await apply_defect_filters()
    # headline/no могли снова всплыть через fold sibling — закрепить ещё раз
    editorial2 = await apply_editorial_listing_modes()
    n_disp = await dedupe_display_names()
    country_vis = await apply_country_visibility()
    nat_eu = await unlist_eurostat_on_national_passports()

    try:
        await bump_namespaces("world")
    except Exception as exc:  # noqa: BLE001
        log.warning("cache bump skipped: %s", exc)

    after = await _stats()
    log.info("purge_countries=%d retitled=%d", n_purge, n_upd)
    log.info("base_unlist_reasons=%s", base_reasons)
    log.info("editorial=%s", editorial)
    log.info("defects=%s", defect)
    log.info("dedupe_same_freq=%d", n_dedupe)
    log.info("fold=%s", fold)
    log.info("defects_after_fold=%s", defect2)
    log.info("editorial_after_fold=%s", editorial2)
    log.info("display_name_deduped=%d", n_disp)
    log.info("country_visibility=%s", country_vis)
    log.info("national_passport_eurostat_unlisted=%s", nat_eu)
    log.info("AFTER %s", after)

    # аудит ключа: нет ли групп с разными stem (не должно быть)
    audit = await _audit_card_keys()
    log.info("card_key_audit %s", audit)

    if after.get("dup_name_groups") or after.get("listed_empty_unit"):
        return 1
    return 0


async def _stats() -> dict:
    async with async_session() as db:
        row = (
            await db.execute(
                text(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM world_countries) AS countries,
                      (SELECT COUNT(*) FROM world_indicators) AS indicators,
                      (SELECT COUNT(*) FROM world_indicators WHERE is_listed) AS listed,
                      (SELECT COUNT(*) FROM world_data_points) AS points,
                      (
                        SELECT COUNT(*) FROM (
                          SELECT country_id, name_ru
                          FROM world_indicators
                          WHERE is_listed
                          GROUP BY country_id, name_ru
                          HAVING COUNT(*) > 1
                        ) d
                      ) AS dup_name_groups,
                      (
                        SELECT COUNT(*) FROM world_indicators
                        WHERE is_listed AND (unit_ru IS NULL OR btrim(unit_ru) = '')
                      ) AS listed_empty_unit,
                      (
                        SELECT COUNT(*) FROM world_indicators
                        WHERE is_listed AND history_end < DATE '2023-01-01'
                      ) AS listed_stale,
                      (
                        SELECT COUNT(*) FROM world_indicators
                        WHERE is_listed AND frequency IN ('annual','yearly')
                          AND points_count BETWEEN 10 AND 11
                      ) AS listed_short_annual
                    """
                )
            )
        ).mappings().one()
        return dict(row)


async def _audit_card_keys() -> dict:
    """Шаг 0: проверить, что listed primary не смешивают разные stem в одной карточке."""
    async with async_session() as db:
        inds = (await db.execute(select(WorldIndicator))).scalars().all()
        quality_ok = [
            i for i in inds if (i.name_quality or "") in ("curated", "composed")
        ]
        groups: dict[tuple, list] = defaultdict(list)
        for ind in quality_ok:
            groups[
                card_key(
                    country_id=ind.country_id,
                    dataset_id=ind.dataset_id,
                    unit=ind.unit,
                    unit_ru=ind.unit_ru,
                    slice_json=ind.slice_json or {},
                )
            ].append(ind)

        multi = 0
        false_stem = 0
        examples = []
        for key, members in groups.items():
            freqs = {normalize_frequency(m.frequency) for m in members}
            if len(freqs) < 2:
                continue
            multi += 1
            stems = { (m.dataset_id or "").lower() for m in members }
            # все dataset_id должны иметь один stem (ключ[1])
            stem = key[1]
            bad = [s for s in stems if not s.startswith(stem)]
            # soft check: stem is prefix after stripping freq
            from app.data.eurostat_listing import dataset_stem
            real_stems = {dataset_stem(m.dataset_id) for m in members}
            if len(real_stems) > 1:
                false_stem += 1
                if len(examples) < 5:
                    examples.append({
                        "stem_key": stem,
                        "real_stems": sorted(real_stems),
                        "datasets": sorted(stems),
                        "name": members[0].name_ru[:60],
                    })

        return {
            "quality_ok": len(quality_ok),
            "card_groups": len(groups),
            "multi_freq_groups": multi,
            "false_stem_merges": false_stem,
            "false_examples": examples,
        }


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
