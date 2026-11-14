#!/usr/bin/env python3
"""Замер одинаковых названий рядов стран мира внутри страны (14.11.2026).

Берёт листинговые ряды (`world_indicators.is_listed`) и строит публичное название ряда тем же кодом,
что серверная страница (`seo_world._display_name`) на русском и английском. Дубль — два и больше
разных рядов одной страны с одинаковым названием: их title и H1 различаются только числом, и для
поиска это почти копии. Выводит число групп и рядов в них, оси среза, которыми ряды различаются, и
значения срезов без подписи (по числу рядов) — очередь для словаря подписей.

Только чтение базы. Запуск: ``backend/.venv/bin/python scripts/world-title-duplicates.py
[--json путь] [--top 40]`` с ``RUSTATS_DATABASE_URL`` локальной копии; на боевом не запускать
(проход по всем листинговым рядам).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

TECHNICAL_AXES = frozenset({"freq", "unit", "s_adj", "geo", "time"})


def series_groups(rows, title_for) -> dict[tuple, list]:
    """(страна, название) → ряды; ``title_for(row)`` — публичное название ряда."""
    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        groups[(row.country_id, title_for(row))].append(row)
    return groups


def summarize(groups: dict[tuple, list], label_for, is_total=lambda axis, value: False) -> dict:
    """Сводка дублей: группы, ряды, различающие оси, значения срезов без подписи."""
    dup = [members for members in groups.values() if len(members) > 1]
    axes: Counter = Counter()
    missing: Counter = Counter()
    technical_only = 0
    for members in dup:
        keys = set().union(*(set(m.slice_json or {}) for m in members)) - TECHNICAL_AXES
        differing = [k for k in sorted(keys) if len({str((m.slice_json or {}).get(k)) for m in members}) > 1]
        if not differing:
            technical_only += 1
        for axis in differing:
            axes[axis] += 1
            for member in members:
                value = (member.slice_json or {}).get(axis)
                if value is None or is_total(axis, str(value)):
                    continue  # «итого» не подписывается: у него базовое название
                if label_for(axis, str(value)) is None:
                    missing[f"{axis}={value}"] += 1
    return {
        "groups": len(dup),
        "series_in_groups": sum(len(m) for m in dup),
        "series_total": sum(len(m) for m in groups.values()),
        "technical_only_groups": technical_only,
        "differing_axes": axes.most_common(),
        "missing_labels": missing.most_common(),
    }


async def _load(limit: int | None):
    from sqlalchemy import text

    from app.database import async_session

    sql = (
        "select id, country_id, code, name_ru, name_en, name_quality, slice_json from world_indicators "
        "where is_listed order by id" + (f" limit {int(limit)}" if limit else "")
    )
    async with async_session() as db:
        rows = (await db.execute(text(sql))).all()
    out = []
    for r in rows:
        slice_json = r.slice_json if isinstance(r.slice_json, dict) else json.loads(r.slice_json or "{}")
        out.append(SimpleNamespace(id=r.id, country_id=r.country_id, code=r.code, name_ru=r.name_ru,
                                   name_en=r.name_en, name_quality=r.name_quality, slice_json=slice_json))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="записать полную сводку в файл")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--limit", type=int, default=None, help="только первые N рядов (проверка)")
    parser.add_argument("--title-room", type=int, default=40,
                        help="место под название в <title> (70 минус хвост «in Country: value (period)»)")
    args = parser.parse_args()

    from app.data.eurostat_dim_labels_en import label_for_dim_member as label_en
    from app.data.eurostat_dim_labels_ru import is_dim_totalish
    from app.data.eurostat_dim_labels_ru import label_for_dim_member as label_ru
    from app.services.locale import _locale_var
    from app.services.seo_world import _display_name

    from app.services.world_series_title import (
        _TITLE_AXES, _TITLE_BUDGETS, differing_axes, title_budgets, world_series_title_for_tag,
    )

    rows = asyncio.run(_load(args.limit))
    # Как на странице и в API: карта различающих измерений по листинговым рядам каждой страны.
    axes = differing_axes(rows)
    axes_token = _TITLE_AXES.set(axes)
    budgets_token = _TITLE_BUDGETS.set(title_budgets(rows, axes))
    report = {}
    for locale, label in (("ru", label_ru), ("en", label_en)):
        token = _locale_var.set(locale)
        try:
            groups = series_groups(rows, _display_name)
        finally:
            _locale_var.reset(token)
        report[locale] = summarize(groups, label, is_dim_totalish)
        # <title>: уточнение укорочено под ~70 знаков (room — место под название при длинной стране).
        token = _locale_var.set(locale)
        try:
            tag_groups = series_groups(rows, lambda row: world_series_title_for_tag(row, locale, args.title_room))
        finally:
            _locale_var.reset(token)
        tag = summarize(tag_groups, label, is_dim_totalish)
        report[locale]["title_tag"] = {"groups": tag["groups"], "series_in_groups": tag["series_in_groups"],
                                       "room": args.title_room}
    _TITLE_BUDGETS.reset(budgets_token)
    _TITLE_AXES.reset(axes_token)
    for locale, data in report.items():
        print(f"[{locale}] групп с одинаковым названием: {data['groups']}, рядов в них: "
              f"{data['series_in_groups']} из {data['series_total']}; только техническое различие: "
              f"{data['technical_only_groups']}; в <title> (room {data['title_tag']['room']}): "
              f"{data['title_tag']['series_in_groups']}")
        print(f"  оси: {data['differing_axes'][:12]}")
        print(f"  без подписи (топ {args.top}): {data['missing_labels'][:args.top]}")
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
