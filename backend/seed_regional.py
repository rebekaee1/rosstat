"""Идемпотентный сидер регионального bounded context.

Источник — статический артефакт app/data/regional/ (создаётся host-скриптом
scripts/regional/parse_pril_2025.py из Excel-приложения Росстата
«Регионы России. Социально-экономические показатели»; дособор из старых
Word-редакций доклеивается туда же скриптами scripts/regional/backfill_*.py).

Идемпотентность: метаданные (regions, region_indicators) — upsert по slug/code;
точки — если счётчик region_data совпадает с артефактом, шаг пропускается;
иначе полная перезаливка (TRUNCATE + COPY-стиль вставки чанками). Данные
полностью воспроизводимы из артефакта, пользовательских данных в таблицах нет.

Запуск: python seed_regional.py (вызывается из entrypoint.sh после seed_data.py).
"""

import asyncio
import csv
import gzip
import json
import sys
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.insert(0, str(Path(__file__).parent))

from app.database import async_session
from app.models import Region, RegionDataPoint, RegionIndicator

DATA_DIR = Path(__file__).parent / "app" / "data" / "regional"
CHUNK = 10_000


def load_artifact():
    regions = json.loads((DATA_DIR / "regions.json").read_text())
    indicators = json.loads((DATA_DIR / "indicators.json").read_text())
    points = []
    with gzip.open(DATA_DIR / "data.csv.gz", "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)
        for code, rslug, year, value in reader:
            points.append((code, rslug, int(year), float(value)))
    return regions, indicators, points


async def seed_regional() -> None:
    if not (DATA_DIR / "data.csv.gz").exists():
        print("regional: артефакт app/data/regional/data.csv.gz отсутствует — пропуск")
        return
    regions, indicators, points = load_artifact()

    async with async_session() as db:
        # --- регионы (upsert по slug) ---
        for i, r in enumerate(regions):
            stmt = pg_insert(Region).values(
                slug=r["slug"], name=r["name"], kind=r["kind"],
                district_slug=r["district"], sort_order=i,
            ).on_conflict_do_update(
                index_elements=["slug"],
                set_={"name": r["name"], "kind": r["kind"],
                      "district_slug": r["district"], "sort_order": i},
            )
            await db.execute(stmt)

        # --- показатели (upsert по code) ---
        for ind in indicators:
            stmt = pg_insert(RegionIndicator).values(
                code=ind["code"], table_code=ind["table_code"],
                section_num=ind["section_num"], section_name=ind["section_name"],
                name=ind["name"][:300], unit=ind["unit"][:120],
                note=ind.get("note") or None,
                source_note=ind.get("source_sheet", "")[:200] or None,
                year_min=ind.get("year_min"), year_max=ind.get("year_max"),
            ).on_conflict_do_update(
                index_elements=["code"],
                set_={"table_code": ind["table_code"],
                      "section_num": ind["section_num"],
                      "section_name": ind["section_name"],
                      "name": ind["name"][:300], "unit": ind["unit"][:120],
                      "note": ind.get("note") or None,
                      "source_note": ind.get("source_sheet", "")[:200] or None,
                      "year_min": ind.get("year_min"),
                      "year_max": ind.get("year_max")},
            )
            await db.execute(stmt)
        await db.commit()

        # --- точки: пропуск, если счётчик совпадает ---
        n_db = (await db.execute(select(func.count()).select_from(RegionDataPoint))).scalar()
        if n_db == len(points):
            print(f"regional: {n_db} точек уже загружены — пропуск")
            return

        print(f"regional: в БД {n_db}, в артефакте {len(points)} — полная перезаливка")
        rid = {s: i for s, i in (await db.execute(select(Region.slug, Region.id))).all()}
        iid = {c: i for c, i in
               (await db.execute(select(RegionIndicator.code, RegionIndicator.id))).all()}

        missing = {p[0] for p in points if p[0] not in iid} | \
                  {p[1] for p in points if p[1] not in rid}
        if missing:
            raise RuntimeError(f"regional: нет метаданных для {sorted(missing)[:10]}")

        await db.execute(text("TRUNCATE region_data RESTART IDENTITY"))
        rows = [
            {"indicator_id": iid[c], "region_id": rid[r], "year": y, "value": v}
            for c, r, y, v in points
        ]
        for i in range(0, len(rows), CHUNK):
            await db.execute(RegionDataPoint.__table__.insert(), rows[i:i + CHUNK])
        await db.commit()
        print(f"regional: загружено {len(rows)} точек, "
              f"{len(indicators)} показателей, {len(regions)} территорий")


if __name__ == "__main__":
    asyncio.run(seed_regional())
