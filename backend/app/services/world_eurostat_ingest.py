"""Контролируемое обновление Eurostat для world bounded context.

Это не обёртка над ежедневным российским ETL.  Eurostat публикует TOC с
версиями наборов; сначала выбираем изменившиеся dataset'ы, затем запускаем
существующий loader строго по одному набору и с обходом URL-only disk cache.
Первые два scheduler-прогона каждой БД — shadow; далее применяется bounded
live batch с версионным курсором по последнему успешному TOC.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import sys
import time
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
MAX_DATASETS_PER_RUN = 200
MAX_RUN_SECONDS = 3 * 3600


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


async def _listed_dataset_ids() -> set[str]:
    """Prioritize public Eurostat cards when a refresh backlog exists."""
    async with async_session() as db:
        return set((await db.execute(
            select(WorldIndicator.dataset_id).where(
                WorldIndicator.provider == "eurostat",
                WorldIndicator.is_listed.is_(True),
            ).distinct()
        )).scalars().all())


async def _failed_dataset_ids() -> set[str]:
    """Put retries behind never-attempted changes so failures cannot starve the queue."""
    async with async_session() as db:
        return set((await db.execute(
            select(WorldDatasetState.dataset_id).where(
                WorldDatasetState.provider == "eurostat",
                WorldDatasetState.status.in_(("error", "quarantine")),
            )
        )).scalars().all())


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
            # A failed/quarantined attempt must not advance the applied TOC
            # version: a later retry must still see the unreviewed DSD change.
            if status == "ok":
                state.last_update_of_data = entry.updated_at
                state.last_structure_change = entry.structure_changed_at
            state.status = status
            state.last_success_at = now if status == "ok" else state.last_success_at
            state.last_error = error[:2000] if error else None
        await db.commit()


async def _mark_changed_states_pending(entries: list[TocEntry]) -> None:
    """Hide forecasts for changed datasets before the bounded loader starts."""
    async with async_session() as db:
        states = (
            await db.execute(
                select(WorldDatasetState).where(
                    WorldDatasetState.provider == "eurostat",
                    WorldDatasetState.dataset_id.in_([entry.dataset_id for entry in entries]),
                    WorldDatasetState.status == "ok",
                )
            )
        ).scalars().all()
        for state in states:
            state.status = "pending"
        if states:
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
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
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


async def world_eurostat_ingest_job(
    *, shadow: bool | None = None, include_imf: bool = True,
    only_dataset_ids: tuple[str, ...] | None = None,
) -> dict[str, int]:
    """TOC-driven sequential ingest; shadow records delta but never writes data."""
    if shadow is None:
        async with async_session() as db:
            shadow_runs = (await db.execute(
                select(func.count()).select_from(WorldIngestRun).where(
                    WorldIngestRun.source == "eurostat",
                    WorldIngestRun.status == "shadow",
                    WorldIngestRun.completed_at.is_not(None),
                )
            )).scalar_one()
        shadow = settings.world_eurostat_ingest_shadow or shadow_runs < 2
    # National-core has its own preceding scheduled job. Running it here
    # doubles provider traffic and duplicates Telegram reports.
    run_clock = time.monotonic()
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
        from app.services.alerting import alert_world_ingest_summary

        await alert_world_ingest_summary(
            "Европа: Eurostat", status="failed", checked=0,
            changed=0, failed=1, details=f"Каталог не получен: {exc}",
            checked_label="Проверено наборов",
            changed_label="Успешно обновлено наборов",
        )
        raise

    total_changed = len(changed)
    if not shadow and changed:
        await _mark_changed_states_pending(changed)
    if only_dataset_ids:
        wanted = set(only_dataset_ids)
        changed = [entry for entry in changed if entry.dataset_id in wanted]
    pending = total_changed - len(changed)
    if not shadow:
        listed = await _listed_dataset_ids()
        retries = await _failed_dataset_ids()
        changed.sort(key=lambda item: (
            item.dataset_id in retries,
            item.dataset_id not in listed,
            -(item.updated_at.toordinal() if item.updated_at else 0),
            item.dataset_id,
        ))
        pending += max(0, len(changed) - MAX_DATASETS_PER_RUN)
        changed = changed[:MAX_DATASETS_PER_RUN]

    async with async_session() as db:
        run = await db.get(WorldIngestRun, run_id)
        assert run is not None
        run.datasets_selected = len(changed)
        await db.commit()

    succeeded = 0
    failed = 0
    processed = 0
    for entry in changed:
        if not shadow and processed and time.monotonic() - run_clock >= MAX_RUN_SECONDS:
            pending += len(changed) - processed
            break
        processed += 1
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
        run.datasets_selected = processed
        run.datasets_succeeded = succeeded
        run.datasets_failed = failed
        run.status = "shadow" if shadow else ("ok" if failed == 0 and pending == 0 else "partial")
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()

    result = {
        "run_id": run_id,
        "selected": processed,
        "succeeded": succeeded,
        "failed": failed,
        "shadow": int(shadow),
        "pending": pending,
    }
    if not shadow and include_imf:
        try:
            from app.services.world_imf_ingest import run_imf_weo_ingest

            result["imf"] = await run_imf_weo_ingest()
        except Exception:  # noqa: BLE001
            logger.exception("IMF WEO ingest after Eurostat run failed")
            result["imf_error"] = 1
    from app.services.alerting import alert_world_ingest_summary

    await alert_world_ingest_summary(
        "Европа: Eurostat",
        status="shadow" if shadow else ("partial" if failed or pending or result.get("imf_error") else "ok"),
        checked=processed, changed=succeeded, failed=failed,
        checked_label="Проверено наборов",
        changed_label="Успешно обновлено наборов",
        details=(
            f"Наборов обновлено: {succeeded}; очередь: {pending}. "
            + ("Данные не записаны (shadow). " if shadow else "")
            + ("Отдельный источник IMF WEO: ошибка обновления. " if result.get("imf_error") else "")
        ).strip(),
    )
    return result
