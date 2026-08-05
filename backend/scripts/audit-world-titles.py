#!/usr/bin/env python3
"""Аудит русских названий и единиц мирового блока.

Падает, если:
  - у любого is_listed=true есть латиница в name_ru (порог 0);
  - у любого is_listed=true name_quality='raw';
  - у одной страны два+ листингуемых индикатора с одинаковым name_ru;
  - у листингуемого пустая unit_ru;
  - код единицы RT отображён как процент (классический misleading);
  - эвристика «коэффициент + % + малые значения» ловит младенческую
    смертность / crude rates, перепутанные с процентами;
  - листингуемый ряд короче порога глубины для своей частоты
    (см. eurostat_listing.LISTING_MIN_POINTS_BY_FREQUENCY);
  - в seo_title / name_ru листинга есть суффикс частоты
    («, помесячно» и т.п.) — частота выбирается переключателем;
  - в description / seo_description есть трафаретные обороты
    («по стране», «выбранной величины» и т.п.).
"""

from __future__ import annotations

import asyncio
import random
import re
import sys
from collections import defaultdict

sys.path.insert(0, "/app")

from sqlalchemy import select, text  # noqa: E402

from app.database import async_session  # noqa: E402
from app.data.eurostat_listing import (  # noqa: E402
    LISTING_MIN_POINTS_BY_FREQUENCY,
    meets_listing_depth,
    min_points_for_frequency,
)
from app.models import WorldCountry, WorldDataPoint, WorldIndicator  # noqa: E402
from app.data.eurostat_titles_ru import (  # noqa: E402
    collect_uncovered_from_titles,
    has_frequency_suffix,
    has_latin,
    has_template_stub,
)

_RATE_PER_THOUSAND_NAME_RE = re.compile(
    r"младенчес|"
    r"коэффициент(?:ы)?\s+(?:рождаемости|смертности|брачности|разводимости)|"
    r"общ(?:ий|ие)\s+коэффициент",
    re.I,
)


async def main() -> int:
    async with async_session() as db:
        rows = (await db.execute(select(WorldIndicator))).scalars().all()
        if not rows:
            print("NO DATA: world_indicators пуста — сначала load-world-eurostat.py")
            return 1

        countries = {
            c.id: c
            for c in (await db.execute(select(WorldCountry))).scalars().all()
        }

        catalog = (
            await db.execute(
                text(
                    """
                    SELECT DISTINCT dataset_id, COALESCE(
                        (SELECT title FROM research.source_catalog sc
                         WHERE sc.source='eurostat' AND sc.dataset_id = wi.dataset_id
                         LIMIT 1), ''
                    ) AS title
                    FROM world_indicators wi
                    """
                )
            )
        ).mappings().all()

        # последние значения для эвристики единиц
        listed_ids = [i.id for i in rows if i.is_listed]
        last_by_ind: dict[int, float] = {}
        if listed_ids:
            last_rows = (
                await db.execute(
                    text(
                        """
                        SELECT DISTINCT ON (indicator_id) indicator_id, value
                        FROM world_data_points
                        WHERE indicator_id = ANY(:ids)
                        ORDER BY indicator_id, date DESC
                        """
                    ),
                    {"ids": listed_ids},
                )
            ).all()
            last_by_ind = {int(iid): float(v) for iid, v in last_rows}

    by_q = {"curated": 0, "composed": 0, "raw": 0}
    listed = 0
    listed_latin = []
    listed_raw = []
    listed_empty_unit = []
    listed_rt_as_pct = []
    listed_rate_pct_suspect = []
    listed_shallow = []
    listed_freq_in_seo_title = []
    listed_freq_in_name = []
    listed_template_stub = []
    name_groups: dict[tuple[int, str], list[WorldIndicator]] = defaultdict(list)

    for ind in rows:
        q = ind.name_quality or "raw"
        by_q[q] = by_q.get(q, 0) + 1
        if not ind.is_listed:
            continue
        listed += 1
        name_groups[(ind.country_id, ind.name_ru)].append(ind)
        if has_latin(ind.name_ru):
            listed_latin.append((ind.code, ind.name_ru))
        if q == "raw":
            listed_raw.append((ind.code, ind.name_ru))
        unit_ru = (ind.unit_ru or "").strip()
        if not unit_ru:
            listed_empty_unit.append((ind.code, ind.name_ru))
        unit_code = (ind.unit or "").strip().upper()
        if unit_code == "RT" and "%" in unit_ru and "1000" not in unit_ru:
            listed_rt_as_pct.append((ind.code, ind.name_ru, unit_ru))
        if not meets_listing_depth(ind.frequency, ind.points_count):
            listed_shallow.append(
                (
                    ind.code,
                    ind.frequency,
                    ind.points_count,
                    min_points_for_frequency(ind.frequency),
                )
            )
        if has_frequency_suffix(ind.seo_title):
            listed_freq_in_seo_title.append((ind.code, ind.seo_title))
        if has_frequency_suffix(ind.name_ru):
            listed_freq_in_name.append((ind.code, ind.name_ru))
        for field_name, field_text in (
            ("description", ind.description),
            ("seo_description", ind.seo_description),
        ):
            if has_template_stub(field_text):
                listed_template_stub.append(
                    (ind.code, field_name, (field_text or "")[:120])
                )
        # Эвристика: «коэффициент …» + единица «%» + значение < 20 →
        # почти наверняка ставка на 1000, а не процент (младенческая 4.1).
        last = last_by_ind.get(ind.id)
        if (
            unit_ru == "%"
            and last is not None
            and abs(last) < 20
            and _RATE_PER_THOUSAND_NAME_RE.search(ind.name_ru or "")
        ):
            listed_rate_pct_suspect.append(
                (ind.code, ind.name_ru, unit_ru, last)
            )

    dup_groups = {k: v for k, v in name_groups.items() if len(v) > 1}
    dup_rows = sum(len(v) for v in dup_groups.values())

    total = len(rows)
    print("=" * 60)
    print("WORLD TITLES AUDIT")
    print("=" * 60)
    print(f"indicators total: {total}")
    print(
        f"quality: curated={by_q.get('curated', 0)} "
        f"composed={by_q.get('composed', 0)} raw={by_q.get('raw', 0)}"
    )
    print(f"listed: {listed} ({100.0 * listed / total:.1f}%)")
    print(f"datasets in DB: {len(catalog)}")
    print(f"listed name dup groups (country×name): {len(dup_groups)} rows={dup_rows}")
    print(f"listed empty unit_ru: {len(listed_empty_unit)}")
    print(f"listed RT-as-%: {len(listed_rt_as_pct)}")
    print(f"listed rate-name+%+|v|<20: {len(listed_rate_pct_suspect)}")
    print(
        f"listed below depth threshold: {len(listed_shallow)} "
        f"(thresholds={LISTING_MIN_POINTS_BY_FREQUENCY})"
    )
    print(f"listed seo_title with freq suffix: {len(listed_freq_in_seo_title)}")
    print(f"listed name_ru with freq suffix: {len(listed_freq_in_name)}")
    print(f"listed template stubs in descriptions: {len(listed_template_stub)}")

    pairs = [(r["dataset_id"], r["title"] or "") for r in catalog]
    uncovered = collect_uncovered_from_titles(pairs)
    print("\nTop-30 uncovered English tokens:")
    for tok, n in list(uncovered.items())[:30]:
        print(f"  {n:5d}  {tok}")

    if dup_groups:
        top = sorted(dup_groups.items(), key=lambda kv: -len(kv[1]))[:20]
        print("\nTop-20 listed name duplicates within country:")
        for (cid, name), members in top:
            c = countries.get(cid)
            cname = c.name_ru if c else str(cid)
            datasets = ", ".join(sorted({m.dataset_id for m in members}))
            print(f"  ×{len(members)} [{cname}] {name}")
            print(f"       datasets: {datasets}")

    sample = random.sample(rows, min(20, len(rows)))
    print("\n20 random name_ru (quality / listed):")
    for ind in sample:
        flag = "LISTED" if ind.is_listed else "hidden"
        print(f"  [{ind.name_quality:8s}|{flag:6s}] {ind.name_ru} | {ind.unit_ru or '∅'}")

    failed = False
    if listed_latin:
        failed = True
        print(f"\nFAIL: {len(listed_latin)} listed with Latin in name_ru:")
        for code, name in listed_latin[:20]:
            print(f"  {code}: {name}")
    if listed_raw:
        failed = True
        print(f"\nFAIL: {len(listed_raw)} listed with name_quality=raw:")
        for code, name in listed_raw[:20]:
            print(f"  {code}: {name}")
    if dup_groups:
        failed = True
        print(
            f"\nFAIL: {len(dup_groups)} duplicate listed name_ru groups "
            f"({dup_rows} rows) within the same country"
        )
    if listed_empty_unit:
        failed = True
        print(f"\nFAIL: {len(listed_empty_unit)} listed with empty unit_ru:")
        for code, name in listed_empty_unit[:20]:
            print(f"  {code}: {name}")
    if listed_rt_as_pct:
        failed = True
        print(f"\nFAIL: {len(listed_rt_as_pct)} listed RT rendered as bare %:")
        for code, name, u in listed_rt_as_pct[:20]:
            print(f"  {code}: {name} [{u}]")
    if listed_rate_pct_suspect:
        failed = True
        print(
            f"\nFAIL: {len(listed_rate_pct_suspect)} listed "
            f"'коэффициент/%'|value|<20 (likely per-1000 mislabeled as %):"
        )
        for code, name, u, last in listed_rate_pct_suspect[:20]:
            print(f"  {code}: {name} [{u}] last={last}")
    if listed_shallow:
        failed = True
        print(
            f"\nFAIL: {len(listed_shallow)} listed below history depth "
            f"for frequency:"
        )
        for code, freq, pts, need in listed_shallow[:20]:
            print(f"  {code}: freq={freq} points={pts} need>={need}")
    if listed_freq_in_seo_title:
        failed = True
        print(
            f"\nFAIL: {len(listed_freq_in_seo_title)} listed seo_title "
            f"with frequency suffix:"
        )
        for code, title in listed_freq_in_seo_title[:20]:
            print(f"  {code}: {title}")
    if listed_freq_in_name:
        failed = True
        print(
            f"\nFAIL: {len(listed_freq_in_name)} listed name_ru "
            f"with frequency suffix:"
        )
        for code, name in listed_freq_in_name[:20]:
            print(f"  {code}: {name}")
    if listed_template_stub:
        failed = True
        print(
            f"\nFAIL: {len(listed_template_stub)} listed descriptions "
            f"with template stubs:"
        )
        for code, field, sample in listed_template_stub[:20]:
            print(f"  {code} [{field}]: {sample}")

    if failed:
        print("\nAUDIT FAILED")
        return 1
    print(
        "\nAUDIT OK — zero listed name duplicates; units reliable; "
        "depth OK; no freq suffixes in titles; no template stubs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
