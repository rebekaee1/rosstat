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
from app.models import Region, RegionDataPoint, RegionIndicator, RegionMonthlyPoint

DATA_DIR = Path(__file__).parent / "app" / "data" / "regional"
CHUNK = 10_000


def load_meta():
    regions = json.loads((DATA_DIR / "regions.json").read_text())
    indicators = json.loads((DATA_DIR / "indicators.json").read_text())
    return regions, indicators


def iter_points():
    """Стрим точек из артефакта (О-10): не держим ~1M кортежей в памяти."""
    with gzip.open(DATA_DIR / "data.csv.gz", "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)
        for code, rslug, year, value in reader:
            yield code, rslug, int(year), float(value)


def iter_monthly_points():
    """Стрим помесячных точек из fuel_points.csv (период YYYYMM).

    Файл может отсутствовать — помесячный слой тогда просто пуст.
    """
    path = DATA_DIR / "fuel_points.csv"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader, None)
        for code, rslug, period, value in reader:
            if len(period) == 6 and period.isdigit():
                yield code, rslug, int(period), float(value)


def count_points() -> int:
    with gzip.open(DATA_DIR / "data.csv.gz", "rt", encoding="utf-8") as fh:
        return sum(1 for _ in fh) - 1  # минус заголовок


def count_monthly_points() -> int:
    path = DATA_DIR / "fuel_points.csv"
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader, None)
        return sum(1 for row in reader if len(row[2]) == 6 and row[2].isdigit())


async def seed_regional() -> None:
    if not (DATA_DIR / "data.csv.gz").exists():
        print("regional: артефакт app/data/regional/data.csv.gz отсутствует — пропуск")
        return
    regions, indicators = load_meta()
    n_artifact = count_points()

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
        n_db_monthly = (
            await db.execute(select(func.count()).select_from(RegionMonthlyPoint))
        ).scalar()
        n_artifact_monthly = count_monthly_points()
        if n_db == n_artifact and n_db_monthly == n_artifact_monthly:
            print(f"regional: {n_db}+{n_db_monthly} точек уже загружены — пропуск")
            return

        print(f"regional: в БД {n_db}+{n_db_monthly}, в артефакте {n_artifact}+{n_artifact_monthly}"
              " — полная перезаливка")
        rid = {s: i for s, i in (await db.execute(select(Region.slug, Region.id))).all()}
        iid = {c: i for c, i in
               (await db.execute(select(RegionIndicator.code, RegionIndicator.id))).all()}

        await db.execute(text("TRUNCATE region_data, region_monthly_data RESTART IDENTITY"))
        # О-10: COPY чанками через asyncpg вместо ~1M executemany-инсертов —
        # на порядок быстрее и без гигантского списка в памяти.
        raw = await (await db.connection()).get_raw_connection()
        driver = raw.driver_connection
        total = 0
        chunk: list[tuple[int, int, int, float]] = []
        for c, r, y, v in iter_points():
            ind_id, reg_id = iid.get(c), rid.get(r)
            if ind_id is None or reg_id is None:
                raise RuntimeError(f"regional: нет метаданных для {c!r}/{r!r}")
            chunk.append((ind_id, reg_id, y, v))
            if len(chunk) >= CHUNK:
                await driver.copy_records_to_table(
                    "region_data", records=chunk,
                    columns=("indicator_id", "region_id", "year", "value"),
                )
                total += len(chunk)
                chunk = []
        if chunk:
            await driver.copy_records_to_table(
                "region_data", records=chunk,
                columns=("indicator_id", "region_id", "year", "value"),
            )
            total += len(chunk)

        total_m = 0
        chunk = []
        for c, r, m, v in iter_monthly_points():
            ind_id, reg_id = iid.get(c), rid.get(r)
            if ind_id is None or reg_id is None:
                raise RuntimeError(f"regional-monthly: нет метаданных для {c!r}/{r!r}")
            chunk.append((ind_id, reg_id, m, v))
            if len(chunk) >= CHUNK:
                await driver.copy_records_to_table(
                    "region_monthly_data", records=chunk,
                    columns=("indicator_id", "region_id", "month", "value"),
                )
                total_m += len(chunk)
                chunk = []
        if chunk:
            await driver.copy_records_to_table(
                "region_monthly_data", records=chunk,
                columns=("indicator_id", "region_id", "month", "value"),
            )
            total_m += len(chunk)

        await db.commit()
        print(f"regional: загружено {total} годовых + {total_m} месячных точек, "
              f"{len(indicators)} показателей, {len(regions)} территорий")


if __name__ == "__main__":
    asyncio.run(seed_regional())
