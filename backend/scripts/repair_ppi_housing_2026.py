#!/usr/bin/env python3
"""Разовый ремонт данных после багов парсеров (диагностика 2026-09-26).

1. PPI (`ppi`): точки 2026-02..2026-07 вписаны YoY-коэффициентами и со сдвигом
   месяца. Пересобираем цепочку от 2026-01 (SDDS-seed, не затронут) по MoM из
   официальных докладов osn-02..osn-07-2026.pdf новым парсером.
2. Жильё (`housing-price-primary/secondary`): добавляем пропущенный Q2 2026
   (2026-06-01) из osn-06-2026.pdf новым парсером.
3. Пересчёт derived-замыкания (ppi-mom/-yoy/-qoq/-annual, housing-*), retrain
   прогнозов source + derived, инвалидация кэша (namespace кода — там же SSR,
   плюс `indicators`, `dashboard`).

Режимы (по умолчанию DRY-RUN, всё в транзакции + ROLLBACK, Redis не трогается):

    # dry-run: before/after source и derived
    python scripts/repair_ppi_housing_2026.py [--pdf-dir DIR]

    # применить (сначала бэкап: см. --backup-json и pg_dump в runbook ниже)
    python scripts/repair_ppi_housing_2026.py --apply --backup-json /backups/ppi-repair.json

    # откат строк indicator_data затронутых рядов из JSON-снимка
    python scripts/repair_ppi_housing_2026.py --rollback-from /backups/ppi-repair.json

Runbook на проде (ПОСЛЕ деплоя etl-fixes; лучше до ближайшего ETL 06:00/20:00 —
иначе ETL успеет дописать 2026-07 от битой базы, скрипт это всё равно перепишет):

    cd /opt/rosstat
    docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -Fc \
        -t indicator_data -t forecasts -t forecast_values "$POSTGRES_DB"' \
        > /root/backups/pre-ppi-repair-$(date -u +%Y%m%dT%H%M).dump
    docker compose exec backend python /app/scripts/repair_ppi_housing_2026.py
    docker compose exec backend python /app/scripts/repair_ppi_housing_2026.py \
        --apply --backup-json /tmp/ppi-repair-backup.json
    docker compose cp backend:/tmp/ppi-repair-backup.json /root/backups/

Полный откат: `--rollback-from` (данные) + retrain/инвалидация делаются им же;
крайний случай — pg_restore таблиц из дампа (`pg_restore --clean -t …`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent, Path("/app")):
    if (_candidate / "app" / "database.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from sqlalchemy import delete, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models import Indicator, IndicatorData  # noqa: E402
from app.services import calculation_engine as ce_module  # noqa: E402
from app.services.calculation_engine import calculation_engine  # noqa: E402
from app.services.rosstat_housing_parser import (  # noqa: E402
    extract_pdf_text as housing_pdf_text,
)
from app.services.rosstat_housing_parser import parse_housing_report_text  # noqa: E402
from app.services.rosstat_ppi_parser import (  # noqa: E402
    chain_ppi_point,
    parse_ppi_reading_from_report,
    previous_month,
)
from app.services.rosstat_ppi_parser import extract_pdf_text as ppi_pdf_text  # noqa: E402
from app.services.rosstat_sdds_fetcher import PDF_MAGIC, _get_session, mediabank_url  # noqa: E402
from app.services.upsert import bulk_upsert  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("repair_ppi_housing_2026")

PPI_CODE = "ppi"
PPI_BASE_MONTH = date(2026, 1, 1)
PPI_REPORTS = [f"osn-{m:02d}-2026.pdf" for m in range(2, 8)]  # Feb..Jul
PPI_EXPECTED_MONTHS = [date(2026, m, 1) for m in range(2, 8)]
HOUSING_REPORT = "osn-06-2026.pdf"
HOUSING_QUARTER = date(2026, 6, 1)
HOUSING_BASE = date(2026, 3, 1)
HOUSING_CODES = ("housing-price-primary", "housing-price-secondary")
SOURCE_CODES = [PPI_CODE, *HOUSING_CODES]
SHOW_FROM = date(2025, 11, 1)


# ---------------------------------------------------------------- fetching ---

def load_pdf(name: str, pdf_dir: Path | None) -> bytes:
    if pdf_dir is not None:
        path = pdf_dir / name
        if path.is_file():
            return path.read_bytes()
    resp = _get_session().get(mediabank_url(name), timeout=settings.rosstat_request_timeout)
    resp.raise_for_status()
    if resp.content[:4] != PDF_MAGIC:
        raise RuntimeError(f"{name}: response is not a PDF")
    return resp.content


# ------------------------------------------------------------------ helpers ---

async def _indicator(db, code: str) -> Indicator:
    ind = (await db.execute(select(Indicator).where(Indicator.code == code))).scalar_one_or_none()
    if ind is None:
        raise SystemExit(f"indicator {code!r} not found")
    return ind


async def _series(db, code: str, since: date = SHOW_FROM) -> dict[date, float]:
    ind = await _indicator(db, code)
    rows = (await db.execute(
        select(IndicatorData.date, IndicatorData.value)
        .where(IndicatorData.indicator_id == ind.id, IndicatorData.date >= since)
        .order_by(IndicatorData.date)
    )).all()
    return {d: float(v) for d, v in rows}


def _print_diff(code: str, before: dict[date, float], after: dict[date, float]) -> None:
    dates = sorted(set(before) | set(after))
    changed = [d for d in dates if before.get(d) != after.get(d)]
    print(f"\n  {code}: {len(changed)} changed point(s)")
    for d in dates:
        b, a = before.get(d), after.get(d)
        mark = "  <-" if b != a else ""
        fb = "—" if b is None else f"{b:.4f}"
        fa = "—" if a is None else f"{a:.4f}"
        print(f"    {d}  {fb:>12} -> {fa:>12}{mark}")


# ------------------------------------------------------------------- plan ---

async def build_plan(db, pdf_dir: Path | None) -> dict[str, list[tuple[date, float]]]:
    """Новые значения source-рядов из официальных PDF (новыми парсерами)."""
    plan: dict[str, list[tuple[date, float]]] = {}

    ppi = await _series(db, PPI_CODE, since=date(2025, 1, 1))
    if PPI_BASE_MONTH not in ppi:
        raise SystemExit(f"ppi base point {PPI_BASE_MONTH} missing — abort")
    value = ppi[PPI_BASE_MONTH]
    points: list[tuple[date, float]] = []
    print("PPI MoM from official reports (section 'Индексы и уровни цен производителей'):")
    for name, expected in zip(PPI_REPORTS, PPI_EXPECTED_MONTHS):
        reading = parse_ppi_reading_from_report(ppi_pdf_text(load_pdf(name, pdf_dir)))
        if reading is None or reading.reference_month != expected:
            raise SystemExit(f"{name}: unexpected PPI reading {reading} (want {expected})")
        assert previous_month(reading.reference_month) == (points[-1][0] if points else PPI_BASE_MONTH)
        pt = chain_ppi_point(value, reading)
        value = pt.value
        points.append((pt.date, pt.value))
        yoy_base = ppi.get(date(expected.year - 1, expected.month, 1))
        yoy = f"  implied YoY {pt.value / yoy_base * 100:.1f}%" if yoy_base else ""
        print(f"  {name}: {expected:%Y-%m} MoM {reading.mom_pct:.1f}% -> {pt.value:.2f}{yoy}")
    plan[PPI_CODE] = points

    report = parse_housing_report_text(housing_pdf_text(load_pdf(HOUSING_REPORT, pdf_dir)))
    if report.reference_quarter != HOUSING_QUARTER or report.qoq_pair is None:
        raise SystemExit(f"{HOUSING_REPORT}: unexpected housing parse {report}")
    print(f"Housing QoQ from {HOUSING_REPORT}: {report.reference_quarter} -> {report.qoq_pair}")
    for idx, code in enumerate(HOUSING_CODES):
        series = await _series(db, code, since=date(2025, 1, 1))
        if HOUSING_BASE not in series:
            raise SystemExit(f"{code}: base point {HOUSING_BASE} missing — abort")
        new_value = round(series[HOUSING_BASE] * report.qoq_pair[idx] / 100.0, 2)
        plan[code] = [(HOUSING_QUARTER, new_value)]
    return plan


# ---------------------------------------------------------------- execution ---

async def _noop_invalidate(code: str) -> None:
    return None


async def apply_plan(db, plan) -> list[str]:
    for code, points in plan.items():
        ind = await _indicator(db, code)
        await bulk_upsert(db, ind.id, points)
    derived = calculation_engine.dependents_closure_topo(list(plan))
    await calculation_engine.run_for_updated_sources(db, list(plan))
    return derived


async def snapshot(db, codes: list[str]) -> dict[str, dict[date, float]]:
    return {c: await _series(db, c, since=date(1900, 1, 1)) for c in codes}


async def retrain_and_invalidate(db, codes_source: list[str], codes_derived: list[str]) -> None:
    from app.core.cache import bump_namespaces, cache_invalidate_indicator
    from app.services.forecast_pipeline import retrain_indicator_forecast
    from app.tasks.scheduler import _retrain_recalculated_derived

    for code in codes_source:
        ind = await _indicator(db, code)
        await retrain_indicator_forecast(db, ind)
        await db.commit()
    await _retrain_recalculated_derived(db, codes_derived)
    for code in [*codes_source, *codes_derived]:
        await cache_invalidate_indicator(code)
    await bump_namespaces("indicators", "dashboard")


async def run(args) -> int:
    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else None
    async with async_session() as db:
        if args.rollback_from:
            return await rollback(db, Path(args.rollback_from))

        plan = await build_plan(db, pdf_dir)
        derived = calculation_engine.dependents_closure_topo(list(plan))
        codes = [*SOURCE_CODES, *derived]
        print(f"\nDerived closure ({len(derived)}): {', '.join(derived)}")

        before_full = await snapshot(db, codes)
        before = {c: {d: v for d, v in s.items() if d >= SHOW_FROM} for c, s in before_full.items()}

        if not args.apply:
            # DRY-RUN: движок пишет в текущую транзакцию, кэш не трогаем, ROLLBACK.
            ce_module.cache_invalidate_indicator = _noop_invalidate
            await apply_plan(db, plan)
            after = await snapshot(db, codes)
            await db.rollback()
            print("\n=== DRY-RUN (rolled back; no cache/forecast changes) ===")
            for c in codes:
                _print_diff(c, before[c], {d: v for d, v in after[c].items() if d >= SHOW_FROM})
            print("\nWould then: retrain forecasts for", ", ".join(SOURCE_CODES),
                  "+ derived with active strategy; invalidate cache namespaces of",
                  len(codes), "codes + indicators, dashboard.")
            return 0

        if not args.backup_json:
            raise SystemExit("--apply requires --backup-json PATH (row snapshot for rollback)")
        backup = {c: {d.isoformat(): v for d, v in s.items()} for c, s in before_full.items()}
        Path(args.backup_json).write_text(json.dumps(backup, ensure_ascii=False, indent=1))
        print(f"Row snapshot of {len(codes)} indicator(s) written to {args.backup_json}")

        await apply_plan(db, plan)
        await db.commit()
        after = await snapshot(db, codes)
        for c in codes:
            _print_diff(c, before[c], {d: v for d, v in after[c].items() if d >= SHOW_FROM})
        await retrain_and_invalidate(db, SOURCE_CODES, derived)
        print("\nAPPLIED: data committed, forecasts retrained, cache invalidated.")
        return 0


async def rollback(db, path: Path) -> int:
    backup = json.loads(path.read_text())
    for code, rows in backup.items():
        ind = await _indicator(db, code)
        points = [(date.fromisoformat(d), v) for d, v in rows.items()]
        keep = {d for d, _ in points}
        await db.execute(delete(IndicatorData).where(
            IndicatorData.indicator_id == ind.id, IndicatorData.date.not_in(keep),
        ))
        if points:
            await bulk_upsert(db, ind.id, points)
    await db.commit()
    sources = [c for c in backup if c in SOURCE_CODES]
    derived = [c for c in backup if c not in SOURCE_CODES]
    await retrain_and_invalidate(db, sources, derived)
    print(f"ROLLED BACK {len(backup)} indicator(s) from {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--backup-json", help="row snapshot of affected indicators (required with --apply)")
    ap.add_argument("--rollback-from", help="restore affected indicators from a --backup-json file")
    ap.add_argument("--pdf-dir", help="dir with osn-MM-2026.pdf copies (else download from rosstat.gov.ru)")
    return asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
