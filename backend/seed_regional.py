"""Regional artifact reconciliation, preserving stored history (ADR-0008).

Annual artifact keys insert/revise values; absent stored keys are retained.
Monthly artifact keys only fill missing values: existing monthly observations
belong to the live EMISS writer, whose provenance cannot be inferred from a
count or an artifact date. Metadata and both layers commit atomically.

Every startup compares content through temporary COPY staging tables. Python
holds at most CHUNK records; no TRUNCATE, table-wide replacement or count skip.
The commit owner publishes regional generations only after an actual change.
"""

import asyncio
import csv
from decimal import Decimal, InvalidOperation
import gzip
import json
import sys
from pathlib import Path

from sqlalchemy import or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.insert(0, str(Path(__file__).parent))

from app.core.cache import publish_committed_regional_changes
from app.database import async_session, set_local_statement_timeout
from app.models import Region, RegionIndicator
from app.services.regional_storage import acquire_regional_write_lock, update_regional_year_bounds

DATA_DIR = Path(__file__).parent / "app" / "data" / "regional"
CHUNK = 10_000


def load_meta():
    regions = json.loads((DATA_DIR / "regions.json").read_text())
    indicators = json.loads((DATA_DIR / "indicators.json").read_text())
    return regions, indicators


def _value(raw: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("regional: invalid artifact value") from exc
    if not value.is_finite():
        raise ValueError("regional: nonfinite artifact value")
    return value


def iter_points():
    """Stream annual numeric observations; invalid rows abort the transaction."""
    with gzip.open(DATA_DIR / "data.csv.gz", "rt", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)
        for code, rslug, raw_year, raw_value in reader:
            year = int(raw_year)
            if not 1 <= year <= 9999:
                raise ValueError("regional: invalid annual year")
            yield code, rslug, year, _value(raw_value)


def iter_monthly_points():
    """Stream YYYYMM values; legitimate four-digit annual fuel rows are skipped.

    Missing monthly artifact means no bootstrap observations, never deletion.
    """
    path = DATA_DIR / "fuel_points.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader, None)
        for code, rslug, period, raw_value in reader:
            if len(period) == 4 and period.isdigit() and 1 <= int(period) <= 9999:
                continue
            if (len(period) != 6 or not period.isdigit()
                    or not 1 <= int(period[:4]) <= 9999
                    or not 1 <= int(period[4:]) <= 12):
                raise ValueError("regional: invalid monthly period")
            yield code, rslug, int(period), _value(raw_value)


async def _upsert_metadata(db, regions, indicators) -> int:
    """Apply artifact-owned metadata only when fields actually differ."""
    changed = 0
    for order, region in enumerate(regions):
        values = dict(slug=region["slug"], name=region["name"], kind=region["kind"],
                      district_slug=region["district"], sort_order=order)
        stmt = pg_insert(Region).values(**values)
        fields = {k: getattr(stmt.excluded, k) for k in values if k != "slug"}
        result = await db.execute(stmt.on_conflict_do_update(
            index_elements=["slug"], set_=fields,
            where=or_(*(getattr(Region, k).is_distinct_from(v) for k, v in fields.items())),
        ))
        changed += result.rowcount
    for indicator in indicators:
        values = dict(
            code=indicator["code"], table_code=indicator["table_code"],
            section_num=indicator["section_num"], section_name=indicator["section_name"],
            name=indicator["name"][:300], unit=indicator["unit"][:120],
            note=indicator.get("note") or None,
            source_note=indicator.get("source_sheet", "")[:200] or None,
        )
        # Bounds come from surviving observations, not the artifact's extent.
        stmt = pg_insert(RegionIndicator).values(**values)
        fields = {k: getattr(stmt.excluded, k) for k in values if k != "code"}
        result = await db.execute(stmt.on_conflict_do_update(
            index_elements=["code"], set_=fields,
            where=or_(*(getattr(RegionIndicator, k).is_distinct_from(v) for k, v in fields.items())),
        ))
        changed += result.rowcount
    return changed


async def _stage_points(db, table, points, indicator_ids, region_ids) -> int:
    """COPY bounded chunks to a transaction-local table; reject duplicate keys."""
    # Table names are internal constants, never user/artifact input.
    if table not in {"regional_seed_annual", "regional_seed_monthly"}:
        raise ValueError("regional: invalid staging table")
    await db.execute(text(f"""CREATE TEMP TABLE {table} (
        indicator_id integer NOT NULL, region_id integer NOT NULL,
        period integer NOT NULL, value numeric(18,4) NOT NULL,
        PRIMARY KEY (indicator_id, region_id, period)
    ) ON COMMIT DROP"""))
    raw = await (await db.connection()).get_raw_connection()
    driver = raw.driver_connection
    total = 0
    chunk = []
    for code, slug, period, value in points:
        indicator_id, region_id = indicator_ids.get(code), region_ids.get(slug)
        if indicator_id is None or region_id is None:
            raise RuntimeError(f"regional: нет метаданных для {code!r}/{slug!r}")
        chunk.append((indicator_id, region_id, period, value))
        if len(chunk) >= CHUNK:
            await driver.copy_records_to_table(
                table, records=chunk, columns=("indicator_id", "region_id", "period", "value"),
            )
            total += len(chunk)
            chunk = []
    if chunk:
        await driver.copy_records_to_table(
            table, records=chunk, columns=("indicator_id", "region_id", "period", "value"),
        )
        total += len(chunk)
    await db.execute(text(f"ANALYZE {table}"))
    return total


async def seed_regional() -> None:
    if not (DATA_DIR / "data.csv.gz").exists():
        print("regional: артефакт app/data/regional/data.csv.gz отсутствует — пропуск")
        return
    regions, indicators = load_meta()
    async with async_session() as db:
        # Serialize both writers before metadata/point row locks. EMISS owns
        # monthly conflicts regardless of transaction arrival order.
        await set_local_statement_timeout(db, 120_000)
        await acquire_regional_write_lock(db)
        changed_meta = await _upsert_metadata(db, regions, indicators)
        region_ids = dict((await db.execute(select(Region.slug, Region.id))).all())
        indicator_ids = dict((await db.execute(select(RegionIndicator.code, RegionIndicator.id))).all())
        annual_count = await _stage_points(
            db, "regional_seed_annual", iter_points(), indicator_ids, region_ids,
        )
        monthly_count = await _stage_points(
            db, "regional_seed_monthly", iter_monthly_points(), indicator_ids, region_ids,
        )
        # Filter unchanged rows before INSERT to avoid consuming ~1M sequence
        # ids on every unchanged restart. ON CONFLICT also handles other writers.
        annual = await db.execute(text("""
            INSERT INTO region_data AS target (indicator_id, region_id, year, value)
            SELECT source.indicator_id, source.region_id, source.period, source.value
            FROM regional_seed_annual source
            LEFT JOIN region_data stored ON stored.indicator_id = source.indicator_id
                AND stored.region_id = source.region_id AND stored.year = source.period
            WHERE stored.value IS DISTINCT FROM source.value
            ON CONFLICT (indicator_id, region_id, year) DO UPDATE SET value = excluded.value
            WHERE target.value IS DISTINCT FROM excluded.value
        """))
        monthly = await db.execute(text("""
            INSERT INTO region_monthly_data (indicator_id, region_id, month, value)
            SELECT source.indicator_id, source.region_id, source.period, source.value
            FROM regional_seed_monthly source
            LEFT JOIN region_monthly_data stored ON stored.indicator_id = source.indicator_id
                AND stored.region_id = source.region_id AND stored.month = source.period
            WHERE stored.id IS NULL
            ON CONFLICT (indicator_id, region_id, month) DO NOTHING
        """))
        changed_bounds = await update_regional_year_bounds(db)
        changed = changed_meta + annual.rowcount + monthly.rowcount + changed_bounds
        await db.commit()
        if changed:
            await publish_committed_regional_changes()
        print(f"regional: сверено {annual_count} годовых + {monthly_count} месячных точек; "
              f"изменено {annual.rowcount} годовых + {monthly.rowcount} новых месячных, "
              f"{changed_meta} метаданных + {changed_bounds} диапазонов")


if __name__ == "__main__":
    asyncio.run(seed_regional())
