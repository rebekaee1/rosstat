"""Контролируемое обновление Eurostat для world bounded context.

Это не обёртка над ежедневным российским ETL.  Eurostat публикует TOC с
версиями наборов; сначала выбираем изменившиеся dataset'ы, затем запускаем
существующий loader строго по одному набору и с обходом URL-only disk cache.
До подтверждения двух shadow-прогонов scheduler остаётся выключенным.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from sqlalchemy import func, select, text

from app.config import settings
from app.database import async_session
from app.models import (
    WorldDataPoint,
    WorldDatasetState,
    WorldIndicator,
    WorldIngestDatasetLog,
    WorldIngestRun,
)

logger = logging.getLogger(__name__)

TOC_URL = "https://ec.europa.eu/eurostat/api/dissemination/catalogue/toc/txt?lang=en"
DEFAULT_THEMES = (
    "ei_,sts_,prc_,namq_,nama_,une_,lfsi_,lfsq_,irt_,ert_,ext_,bop_,"
    "gov_,demo_,nrg_,road_,tour_,educ_,hlth_,ilc_,isoc_,sdg_,tec,tei,tin,tps"
)


@dataclass(frozen=True)
class TocEntry:
    dataset_id: str
    updated_at: date | None
    structure_changed_at: date | None
    provider: str = "eurostat"


def _parse_toc_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        return None


def parse_toc(raw: str) -> dict[str, TocEntry]:
    """Разобрать официальный tab-separated TOC, игнорируя каталожные folders."""
    result: dict[str, TocEntry] = {}
    for row in csv.reader(io.StringIO(raw), delimiter="\t", quotechar='"'):
        if len(row) < 7 or row[2].strip() not in {"dataset", "table"}:
            continue
        dataset_id = row[1].strip()
        if not dataset_id:
            continue
        result[dataset_id] = TocEntry(
            dataset_id=dataset_id,
            updated_at=_parse_toc_date(row[3]),
            structure_changed_at=_parse_toc_date(row[4]),
        )
    return result


def _fetch_toc_sync() -> dict[str, TocEntry]:
    response = requests.get(TOC_URL, timeout=120)
    response.raise_for_status()
    return parse_toc(response.content.decode("utf-8", "replace"))


async def fetch_toc() -> dict[str, TocEntry]:
    return await asyncio.to_thread(_fetch_toc_sync)


def _theme_sql(themes: list[str]) -> tuple[str, dict[str, str]]:
    clauses: list[str] = []
    params: dict[str, str] = {}
    for index, theme in enumerate(themes):
        key = f"theme_{index}"
        params[key] = f"{theme.rstrip('_').lower()}%"
        clauses.append(f"lower(dataset_id) LIKE :{key}")
    return "(" + " OR ".join(clauses) + ")", params


async def _catalog_dataset_ids() -> set[str]:
    """Тот же curated set, что ручной loader, но без повторной выгрузки TOC."""
    themes = [value.strip() for value in DEFAULT_THEMES.split(",") if value.strip()]
    theme_sql, params = _theme_sql(themes)
    sql = text(
        "SELECT dataset_id FROM research.source_catalog "
        "WHERE source = 'eurostat' AND period_end IS NOT NULL "
        "AND period_end >= '2024' "
        f"AND {theme_sql}"
    )
    async with async_session() as db:
        return set((await db.execute(sql, params)).scalars().all())


async def select_changed_datasets(toc: dict[str, TocEntry]) -> list[TocEntry]:
    """Выбрать first-seen и изменившиеся относительно последнего success набора."""
    candidates = await _catalog_dataset_ids()
    async with async_session() as db:
        states = {
            state.dataset_id: state
            for state in (
                await db.execute(
                    select(WorldDatasetState)
                    .where(WorldDatasetState.provider == "eurostat")
                )
            ).scalars().all()
        }

    selected: list[TocEntry] = []
    for dataset_id in sorted(candidates):
        entry = toc.get(dataset_id)
        if entry is None:
            continue
        state = states.get(dataset_id)
        if state is None:
            selected.append(entry)
            continue
        if state.status in {"error", "quarantine"}:
            selected.append(entry)
            continue
        if (
            state.last_update_of_data != entry.updated_at
            or state.last_structure_change != entry.structure_changed_at
        ):
            selected.append(entry)
    return selected


async def _record_dataset(
    *,
    run_id: int,
    entry: TocEntry,
    status: str,
    error: str | None = None,
    update_state: bool,
    rows_fetched: int = 0,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session() as db:
        db.add(WorldIngestDatasetLog(
            run_id=run_id,
            provider=entry.provider,
            dataset_id=entry.dataset_id,
            status=status,
            source_updated_at=entry.updated_at,
            structure_changed_at=entry.structure_changed_at,
            rows_fetched=rows_fetched,
            error_message=error[:2000] if error else None,
        ))
        if update_state:
            state = await db.get(
                WorldDatasetState,
                (entry.provider, entry.dataset_id),
            )
            if state is None:
                state = WorldDatasetState(
                    provider=entry.provider,
                    dataset_id=entry.dataset_id,
                )
                db.add(state)
            state.last_update_of_data = entry.updated_at
            state.last_structure_change = entry.structure_changed_at
            state.status = status
            state.last_success_at = now if status == "ok" else state.last_success_at
            state.last_error = error[:2000] if error else None
        await db.commit()


async def _structure_change_requires_quarantine(entry: TocEntry) -> bool:
    """Не применяем новый DSD к pinned slices без отдельной проверки."""
    async with async_session() as db:
        state = await db.get(
            WorldDatasetState,
            (entry.provider, entry.dataset_id),
        )
        return bool(
            state is not None
            and state.last_structure_change is not None
            and state.last_structure_change != entry.structure_changed_at
        )


async def _run_one_loader(entry: TocEntry) -> tuple[bool, str]:
    """Запустить проверенный manual-loader для одного dataset без stale disk cache."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "load-world-eurostat.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(script),
        "--only",
        entry.dataset_id,
        "--workers",
        "1",
        "--no-cache",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=os.environ.copy(),
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=4 * 60 * 60)
    except TimeoutError:
        process.kill()
        await process.wait()
        return False, "loader timeout after 4 hours"
    text_output = output.decode("utf-8", "replace")
    return process.returncode == 0, text_output[-2000:]


async def _persisted_rows(dataset_id: str, provider: str = "eurostat") -> int:
    """Число точек после успешного reconcile — provenance, не оценка TOC."""
    async with async_session() as db:
        return int(
            (
                await db.execute(
                    select(func.count(WorldDataPoint.id))
                    .join(WorldIndicator, WorldDataPoint.indicator_id == WorldIndicator.id)
                    .where(
                        WorldIndicator.provider == provider,
                        WorldIndicator.dataset_id == dataset_id,
                    )
                )
            ).scalar_one()
            or 0
        )


async def world_eurostat_ingest_job(*, shadow: bool | None = None) -> dict[str, int]:
    """TOC-driven sequential ingest; shadow records delta but never writes data."""
    shadow = settings.world_eurostat_ingest_shadow if shadow is None else shadow
    # Национальные ряды — быстрые (десятки HTTP-вызовов против тысяч dataset'ов
    # Eurostat): обновляем их в начале прогона, чтобы часы Eurostat-очереди
    # не отодвигали свежие точки Канады/Японии/США.
    try:
        from app.services.world_national_ingest import run_national_core_ingest

        await run_national_core_ingest()
    except Exception:  # noqa: BLE001
        logger.exception("national-core ingest before Eurostat pass failed")
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session() as db:
        run = WorldIngestRun(
            source="eurostat",
            is_shadow=shadow,
            started_at=started_at,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

    try:
        changed = await select_changed_datasets(await fetch_toc())
    except Exception as exc:  # noqa: BLE001
        async with async_session() as db:
            run = await db.get(WorldIngestRun, run_id)
            assert run is not None
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            run.error_message = str(exc)[:2000]
            await db.commit()
        raise

    async with async_session() as db:
        run = await db.get(WorldIngestRun, run_id)
        assert run is not None
        run.datasets_selected = len(changed)
        await db.commit()

    succeeded = 0
    failed = 0
    for entry in changed:
        if shadow:
            await _record_dataset(
                run_id=run_id,
                entry=entry,
                status="shadow",
                update_state=False,
            )
            continue
        if await _structure_change_requires_quarantine(entry):
            failed += 1
            await _record_dataset(
                run_id=run_id,
                entry=entry,
                status="quarantine",
                error="Eurostat TOC reports a structure change; pinned slices need review",
                update_state=True,
            )
            logger.warning(
                "World Eurostat dataset %s quarantined after TOC structure change",
                entry.dataset_id,
            )
            continue
        ok, detail = await _run_one_loader(entry)
        if ok:
            succeeded += 1
            await _record_dataset(
                run_id=run_id,
                entry=entry,
                status="ok",
                update_state=True,
                rows_fetched=await _persisted_rows(entry.dataset_id, entry.provider),
            )
        else:
            failed += 1
            logger.error("World Eurostat loader failed for %s: %s", entry.dataset_id, detail)
            await _record_dataset(
                run_id=run_id,
                entry=entry,
                status="error",
                error=detail,
                update_state=True,
            )

    async with async_session() as db:
        run = await db.get(WorldIngestRun, run_id)
        assert run is not None
        run.datasets_succeeded = succeeded
        run.datasets_failed = failed
        run.status = "shadow" if shadow else ("ok" if failed == 0 else "partial")
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

    result = {
        "run_id": run_id,
        "selected": len(changed),
        "succeeded": succeeded,
        "failed": failed,
        "shadow": int(shadow),
    }
    if not shadow:
        try:
            from app.services.world_imf_ingest import run_imf_weo_ingest

            result["imf"] = await run_imf_weo_ingest()
        except Exception:  # noqa: BLE001
            logger.exception("IMF WEO ingest after Eurostat run failed")
            result["imf_error"] = 1
    return result
