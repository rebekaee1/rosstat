"""BEA regional ZIP archives: official US/state series with full source history.

The published catalog is pinned in ``data/world_bea_regional/us.json``.  BEA
revises observations in place, so ingestion reads whole tables on each changed
archive.  A new BEA line needs an editorial catalog rebuild before publication.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import io
import json
import logging
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import bump_namespaces
from app.data.world_indicator_titles_ru import is_public_catalog_name
from app.database import async_session
from app.models import (
    SubnationalDataPoint, SubnationalIndicator, SubnationalRegion,
    WorldCountry, WorldDatasetState, WorldIndicator,
)
from app.services.world_national_ingest import (
    NationalSeriesSpec, reconcile_points, refresh_indicator_extent,
    series_ref_from_spec, upsert_national_indicator,
)


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "world_bea_regional" / "us.json"
BEA_ZIP_ROOT = "https://apps.bea.gov/regional/zip"

# Only current BEA classifications.  Historical SIC/NAICS vintages remain in
# the source archives but must not be silently spliced into current industries.
TABLES_BY_ARCHIVE: dict[str, tuple[str, ...]] = {
    "SAGDP": ("SAGDP1", "SAGDP2", "SAGDP3", "SAGDP4", "SAGDP5", "SAGDP6", "SAGDP7", "SAGDP8", "SAGDP9", "SAGDP11"),
    "SAINC": ("SAINC1", "SAINC4", "SAINC5N", "SAINC6N", "SAINC7N", "SAINC11", "SAINC12", "SAINC30", "SAINC35", "SAINC40", "SAINC50", "SAINC51", "SAINC70"),
    "SQGDP": ("SQGDP1", "SQGDP2", "SQGDP8", "SQGDP9", "SQGDP11"),
    "SQINC": ("SQINC1", "SQINC4", "SQINC5N", "SQINC6N", "SQINC7N", "SQINC11", "SQINC12", "SQINC35"),
    "SAPCE": ("SAPCE1", "SAPCE2", "SAPCE3", "SAPCE4", "SAPCE5"),
    "SARPP": ("SAIRPD", "SARPI", "SARPP"),
    "SASUMMARY": ("SASUMMARY",),
}

_PERIOD = re.compile(r"^(\d{4})(?::Q([1-4]))?$")
_FOOTNOTE = re.compile(r"\s+\d+/\s*$")
_POINT_CHUNK = 1200
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BeaCatalogRow:
    archive: str
    table: str
    line: str
    code: str
    national_code: str
    name_en: str
    name_ru: str
    section_en: str
    section_ru: str
    unit: str
    unit_ru: str
    frequency: str
    source_url: str
    description_en: str
    description_ru: str
    methodology_en: str
    methodology_ru: str
    history_floor: str


def archive_url(archive: str) -> str:
    if archive not in TABLES_BY_ARCHIVE:
        raise ValueError(f"unapproved BEA archive: {archive}")
    return f"{BEA_ZIP_ROOT}/{archive}.zip"


def table_file_names(bundle: zipfile.ZipFile, archive: str) -> dict[str, str]:
    """Choose each aggregate file once; state-specific CSVs duplicate it."""
    allowed = set(TABLES_BY_ARCHIVE[archive])
    found: dict[str, str] = {}
    for name in bundle.namelist():
        if not name.endswith(".csv"):
            continue
        if "__ALL_AREAS_" not in name and "_STATE_" not in name:
            continue
        table = name.split("__", 1)[0].split("_STATE_", 1)[0]
        if table in allowed:
            if table in found:
                raise ValueError(f"duplicate BEA table {table} in {archive}")
            found[table] = name
    missing = allowed - found.keys()
    if missing:
        raise ValueError(f"BEA archive {archive} lacks tables {sorted(missing)}")
    return found


def clean_description(raw: str | None) -> str:
    return _FOOTNOTE.sub("", " ".join((raw or "").split())).strip()


def clean_geofips(raw: str | None) -> str:
    # BEA's CSV has a space before quoted GeoFIPS: ` "06000"`.
    return (raw or "").strip().strip('"')


def parse_period(column: str) -> date | None:
    match = _PERIOD.fullmatch(column)
    if not match:
        return None
    year, quarter = match.groups()
    return date(int(year), (int(quarter) - 1) * 3 + 1 if quarter else 1, 1)


def parse_number(raw: str | None) -> float | None:
    text = (raw or "").strip().replace(",", "")
    if not text or text.startswith("("):
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value != value or abs(value) == float("inf"):
        return None
    return value


def table_rows(bundle: zipfile.ZipFile, member: str) -> Iterator[dict[str, str]]:
    with bundle.open(member) as stream:
        reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", errors="replace"))
        for row in reader:
            if row.get("LineCode") and row.get("GeoFIPS"):
                yield row


def numeric_points(row: dict[str, str]) -> list[tuple[date, float]]:
    points: list[tuple[date, float]] = []
    for column, raw in row.items():
        period = parse_period(column)
        if period is None:
            continue
        value = parse_number(raw)
        if value is not None:
            points.append((period, value))
    return points


def catalog_code(table: str, line: str) -> str:
    if not re.fullmatch(r"[A-Z0-9]+", table) or not re.fullmatch(r"[0-9]+", line):
        raise ValueError(f"bad BEA table/line: {table}/{line}")
    return f"bea-{table.lower()}-{int(line)}"


def load_catalog(path: Path = CATALOG_PATH) -> tuple[BeaCatalogRow, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("country_code") != "US":
        raise ValueError("BEA regional catalog is not US")
    rows = tuple(BeaCatalogRow(**item) for item in raw["series"])
    if len({row.code for row in rows}) != len(rows):
        raise ValueError("duplicate BEA regional codes")
    for row in rows:
        if row.archive not in TABLES_BY_ARCHIVE or row.table not in TABLES_BY_ARCHIVE[row.archive]:
            raise ValueError(f"unapproved BEA table: {row.table}")
        if catalog_code(row.table, row.line) != row.code:
            raise ValueError(f"BEA identity mismatch: {row.code}")
        if row.national_code != f"us-{row.code}":
            raise ValueError(f"BEA national link mismatch: {row.code}")
        if row.source_url != archive_url(row.archive):
            raise ValueError(f"BEA source URL mismatch: {row.code}")
        if not is_public_catalog_name(row.name_ru):
            raise ValueError(f"BEA name is not public in Russian catalog: {row.code}")
    return rows


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fetch_archive_sync(archive: str) -> bytes:
    """Bounded official download; no third-party mirror or API key."""
    last_error: Exception | None = None
    with requests.Session() as session:
        for attempt in range(3):
            try:
                response = session.get(archive_url(archive), timeout=(10, 120))
                response.raise_for_status()
                payload = response.content
                if len(payload) > 100_000_000 or not zipfile.is_zipfile(io.BytesIO(payload)):
                    raise ValueError(f"BEA {archive} is not a bounded ZIP")
                return payload
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                logger.warning("BEA %s download attempt %s failed: %s", archive, attempt + 1, exc)
    raise RuntimeError(f"BEA {archive} download failed: {last_error}")


def extract_catalog_points(
    archive: str,
    payload: bytes,
    catalog: tuple[BeaCatalogRow, ...],
    state_fips: set[str],
) -> dict[str, dict[str, list[tuple[date, float]]]]:
    """Read only approved table/line/geography pairs from full BEA ZIP."""
    expected = {(row.table, row.line): row for row in catalog if row.archive == archive}
    if not expected:
        return {}
    results: dict[str, dict[str, list[tuple[date, float]]]] = defaultdict(dict)
    with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
        members = table_file_names(bundle, archive)
        for table, member in members.items():
            for source_row in table_rows(bundle, member):
                line = source_row["LineCode"].strip()
                spec = expected.get((table, line))
                if spec is None:
                    continue
                geo = clean_geofips(source_row["GeoFIPS"])
                if geo != "00000" and geo not in state_fips:
                    continue
                points = numeric_points(source_row)
                if points:
                    results[spec.code][geo] = points
    for spec in expected.values():
        geos = results.get(spec.code, {})
        us = geos.get("00000", [])
        if len(us) < 3 or us[0][0].year > int(spec.history_floor):
            raise ValueError(f"BEA {spec.code} lost its national historical floor")
        if sum(bool(geos.get(geo)) for geo in state_fips) < 45:
            raise ValueError(f"BEA {spec.code} now covers fewer than 45 states")
        if any(
            (spec.frequency == "annual" and any(period.month != 1 for period, _ in series))
            for series in geos.values()
        ):
            raise ValueError(f"BEA {spec.code} frequency changed")
    return dict(results)


async def _upsert_state_indicators(
    db: AsyncSession,
    specs: tuple[BeaCatalogRow, ...],
) -> dict[str, int]:
    if not specs:
        return {}
    for offset in range(0, len(specs), 100):
        chunk = specs[offset:offset + 100]
        values = [{
            "country_code": "US", "code": spec.code,
            "name_en": spec.name_en, "name_ru": spec.name_ru,
            "unit": spec.unit, "unit_en": spec.unit, "unit_ru": spec.unit_ru,
            "frequency": spec.frequency,
            "section_en": spec.section_en, "section_ru": spec.section_ru,
            "provider": "bea-regional",
            "series_template": f"BEA:{spec.table}:{spec.line}",
            "aggregation": "last",
            "description_en": spec.description_en,
            "description_ru": spec.description_ru,
            "methodology_en": spec.methodology_en,
            "methodology_ru": spec.methodology_ru,
            "source_en": "U.S. Bureau of Economic Analysis",
            "source_ru": "Бюро экономического анализа США",
            "source_url_template": spec.source_url,
            "is_listed": True,
            "national_code": spec.national_code,
            "better_is_low": False,
        } for spec in chunk]
        stmt = pg_insert(SubnationalIndicator).values(values)
        update = {key: getattr(stmt.excluded, key) for key in values[0] if key not in {"country_code", "code"}}
        await db.execute(stmt.on_conflict_do_update(
            constraint="uq_subnational_indicator_country_code", set_=update,
        ))
    rows = (
        await db.execute(select(SubnationalIndicator.code, SubnationalIndicator.id).where(
            SubnationalIndicator.country_code == "US",
            SubnationalIndicator.provider == "bea-regional",
        ))
    ).all()
    return {code: iid for code, iid in rows}


async def _retire_removed_lines(
    db: AsyncSession,
    archive: str,
    specs: tuple[BeaCatalogRow, ...],
    country_id: int,
) -> None:
    """Keep old observations but remove lines dropped by editorial catalog review."""
    current = {spec.code for spec in specs}
    tables = set(TABLES_BY_ARCHIVE[archive])
    state_rows = (
        await db.execute(select(SubnationalIndicator).where(
            SubnationalIndicator.country_code == "US",
            SubnationalIndicator.provider == "bea-regional",
        ))
    ).scalars().all()
    for indicator in state_rows:
        parts = (indicator.series_template or "").split(":")
        if len(parts) >= 3 and parts[1] in tables and indicator.code not in current:
            indicator.is_listed = False
    national_rows = (
        await db.execute(select(WorldIndicator).where(
            WorldIndicator.country_id == country_id,
            WorldIndicator.provider == "bea-regional",
        ))
    ).scalars().all()
    for indicator in national_rows:
        parts = (indicator.dataset_id or "").split(":")
        if len(parts) >= 3 and parts[1] in tables and indicator.code.removeprefix("us-") not in current:
            indicator.is_listed = False


async def ingest_bea_archive(
    archive: str,
    *,
    payload: bytes | None = None,
    force: bool = False,
) -> dict[str, int | str]:
    """Idempotent full-history refresh of one official ZIP, atomically published."""
    import asyncio

    if archive not in TABLES_BY_ARCHIVE:
        raise ValueError(f"unapproved BEA archive {archive}")
    specs = tuple(row for row in load_catalog() if row.archive == archive)
    payload = payload if payload is not None else await asyncio.to_thread(fetch_archive_sync, archive)
    catalog_bytes = json.dumps(
        [dataclasses.asdict(row) for row in specs],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    digest = sha256_bytes(payload + catalog_bytes)
    state_key = f"US:{archive}"
    async with async_session() as db:
        state = await db.get(WorldDatasetState, ("bea-regional", state_key))
        if not force and state is not None and state.status == "ok" and state.last_slice_hash == digest:
            return {"archive": archive, "status": "unchanged", "series": len(specs), "points": 0}

        region_rows = (
            await db.execute(select(SubnationalRegion.fips, SubnationalRegion.id).where(
                SubnationalRegion.country_code == "US"
            ))
        ).all()
        state_ids = {f"{fips}000": rid for fips, rid in region_rows if fips}
        if len(state_ids) != 51:
            raise RuntimeError(f"BEA state load needs 51 regions; found {len(state_ids)}")
        country = (
            await db.execute(select(WorldCountry).where(WorldCountry.code == "US"))
        ).scalar_one()
        extracted = extract_catalog_points(archive, payload, specs, set(state_ids))
        ids = await _upsert_state_indicators(db, specs)
        await _retire_removed_lines(db, archive, specs, country.id)
        touched = 0
        for index, spec in enumerate(specs, 1):
            geos = extracted[spec.code]
            national = geos["00000"]
            national_spec = NationalSeriesSpec(
                code_suffix=spec.code,
                name_ru=spec.name_ru,
                name_en=spec.name_en,
                category_ru=spec.section_ru,
                unit=spec.unit,
                unit_ru=spec.unit_ru,
                frequency=spec.frequency,
                provider="bea-regional",
                dataset_id=f"REGIONAL:{spec.table}:{spec.line}",
                series_id=f"{spec.table}:{spec.line}",
                source_url=spec.source_url,
                description=spec.description_ru,
                methodology=spec.methodology_ru,
                is_listed=True,
            )
            ref = series_ref_from_spec(national_spec, country_code="US")
            world_id, _ = await upsert_national_indicator(
                db, country=country, spec=national_spec, ref=ref,
                points=national, source_ru="Бюро экономического анализа США",
            )
            world_ind = await db.get(WorldIndicator, world_id)
            if world_ind is None:
                raise RuntimeError(f"BEA national row disappeared: {spec.national_code}")
            world_ind.name_quality = "composed"
            changed, _ = await reconcile_points(db, world_id, national)
            touched += changed
            await refresh_indicator_extent(db, world_id)

            values = [
                {"indicator_id": ids[spec.code], "region_id": state_ids[geo],
                 "period": period, "value": value}
                for geo, points in geos.items() if geo in state_ids
                for period, value in points
            ]
            for offset in range(0, len(values), _POINT_CHUNK):
                stmt = pg_insert(SubnationalDataPoint).values(values[offset:offset + _POINT_CHUNK])
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_subnational_data_point",
                    set_={"value": stmt.excluded.value},
                    where=SubnationalDataPoint.value.is_distinct_from(stmt.excluded.value),
                ).returning(SubnationalDataPoint.id)
                touched += len((await db.execute(stmt)).all())
            if index % 25 == 0 or index == len(specs):
                logger.info("BEA %s refreshed %s/%s series", archive, index, len(specs))
        if state is None:
            state = WorldDatasetState(provider="bea-regional", dataset_id=state_key)
            db.add(state)
        state.status = "ok"
        state.last_slice_hash = digest
        state.last_update_of_data = max(extracted[spec.code]["00000"][-1][0] for spec in specs)
        state.last_success_at = datetime.now(timezone.utc).replace(tzinfo=None)
        state.last_error = None
        await db.commit()
    await bump_namespaces("world", "ssr-world", "world-catalog")
    return {"archive": archive, "status": "loaded", "series": len(specs), "points": touched}


async def world_bea_regional_job() -> None:
    """Weekly full-archive revision check; raises so APScheduler alerts on error."""
    errors: list[str] = []
    loaded = unchanged = series = points = 0
    for archive in TABLES_BY_ARCHIVE:
        try:
            result = await ingest_bea_archive(archive)
            logger.info("BEA regional %s", result)
            loaded += result["status"] == "loaded"
            unchanged += result["status"] == "unchanged"
            series += int(result["series"])
            points += int(result["points"])
        except Exception:
            logger.exception("BEA regional ingest failed: %s", archive)
            errors.append(archive)
    from app.services.alerting import alert_world_ingest_summary

    await alert_world_ingest_summary(
        "США и штаты: BEA",
        status="partial" if errors else "ok",
        checked=len(TABLES_BY_ARCHIVE), changed=points, failed=len(errors),
        checked_label="Проверено архивов",
        changed_label="Изменено точек",
        details=(
            f"Архивов изменилось: {loaded}; без изменений: {unchanged}; "
            f"рядов проверено: {series}; изменённых точек: {points}. "
            + (f"Ошибки: {', '.join(errors)}" if errors else "")
        ).strip(),
    )
    if errors:
        raise RuntimeError(f"BEA regional archives failed: {', '.join(errors)}")
