"""Изолированный pipeline quality-gated прогнозов world bounded context.

Job инкрементальный: ряд с тем же отпечатком данных (history_end, points_count,
хэш дат и значений, версия методологии, готовность источника) и свежей записью
world_forecasts не переобучается.
Обход — приоритет стран, затем концепт-ряды, национальный провайдер, частота.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Sequence
from types import SimpleNamespace

from sqlalchemy import String, cast, func, literal, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.cache import bump_namespaces
from app.data.world_forecast_policy import forecast_eligibility_for
from app.database import async_session
from app.models import (
    WorldCountry,
    WorldDataPoint,
    WorldDatasetState,
    WorldForecast,
    WorldForecastValue,
    WorldIndicator,
)
from app.services.world_forecaster import (
    PUBLISHED_GATE_STATUSES,
    WORLD_FORECAST_METHOD_VERSION,
    WorldForecastGate,
    is_percentage_unit,
    train_quality_gated_world_forecast,
)

logger = logging.getLogger(__name__)

WORLD_FORECAST_CACHE_NAMESPACES = ("world", "ssr-world")
WORLD_FORECAST_JOB_LOCK_KEY = "sched:lock:world_forecast"
WORLD_FORECAST_JOB_LOCK_TTL_SECONDS = 24 * 3600
_PROGRESS_EVERY = 100
_FREQ_RANK = {"monthly": 0, "quarterly": 1, "annual": 2}
_RELEASE_LUA = (
    "if redis.call('GET', KEYS[1]) == ARGV[1] then "
    "return redis.call('DEL', KEYS[1]) else return 0 end"
)


@dataclass(frozen=True)
class WorldForecastCandidate:
    id: int
    country_slug: str
    provider: str
    dataset_id: str
    code: str
    frequency: str
    history_end: date | None = None
    points_count: int = 0
    history_digest: str | None = None
    eligible_for_training: bool = False
    source_ready: bool = True


@dataclass(frozen=True)
class WorldForecastRunSummary:
    selected: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    advisory: int = 0
    unchanged: int = 0
    to_train: int = 0
    lock_busy: bool = False


def parse_priority_countries(raw: str | None = None) -> list[str]:
    text = settings.world_forecast_priority_countries if raw is None else raw
    return [part for part in (item.strip().lower() for item in str(text).split(",")) if part]


def parse_country_slugs(raw: str | Sequence[str] | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        parts = raw.split(",")
    else:
        parts = list(raw)
    return tuple(part for part in (item.strip().lower() for item in parts) if part)


@lru_cache(maxsize=1)
def concept_priority_sets() -> tuple[frozenset[str], frozenset[str]]:
    """Дешёвый гейт концепт-ряда: dataset_id ∪ национальные коды crosswalk."""
    from app.data.world_concept_national import NATIONAL_CONCEPT_INDICATOR_CODES
    from app.data.world_concepts import WORLD_CONCEPTS

    datasets: set[str] = set()
    for concept in WORLD_CONCEPTS:
        datasets.update(str(ds).lower() for ds in concept.dataset_ids)
        for extra in (concept.provider_dataset_ids or {}).values():
            datasets.update(str(ds).lower() for ds in extra)
    codes = frozenset(
        code
        for mapping in NATIONAL_CONCEPT_INDICATOR_CODES.values()
        for code in mapping.values()
    )
    return frozenset(datasets), codes


def forecast_fingerprint(
    *, history_end: date | None, points_count: int, history_digest: str | None = None,
    source_ready: bool = True,
) -> dict:
    return {
        "history_end": history_end.isoformat() if history_end else None,
        "points_count": int(points_count or 0),
        "history_digest": history_digest,
        "source_ready": source_ready,
        "method_version": WORLD_FORECAST_METHOD_VERSION,
    }


def _stored_fingerprint(params: object) -> dict | None:
    if not isinstance(params, dict) or "method_version" not in params:
        return None
    points = params.get("points_count")
    try:
        points_count = int(points) if points is not None else 0
    except (TypeError, ValueError):
        return None
    return {
        "history_end": params.get("history_end"),
        "points_count": points_count,
        "history_digest": params.get("history_digest"),
        "source_ready": params.get("source_ready", True),
        "method_version": params.get("method_version"),
    }


def _as_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def forecast_is_unchanged(
    latest: object | None,
    *,
    history_end: date | None,
    points_count: int,
    history_digest: str | None = None,
    source_ready: bool = True,
    now: datetime,
    max_age_days: int,
    force: bool,
) -> bool:
    """Пропуск обучения: тот же отпечаток и запись не старше max_age.

    Строки без method_version требуют пересчёта: старый гейт мог проверить
    только часть публикуемого горизонта.
    """
    if force or latest is None:
        return False
    created_at = getattr(latest, "created_at", None)
    if not isinstance(created_at, datetime):
        return False
    created_at = _as_naive(created_at)
    now = _as_naive(now)
    if now - created_at > timedelta(days=int(max_age_days)):
        return False
    expected = forecast_fingerprint(
        history_end=history_end, points_count=points_count,
        history_digest=history_digest, source_ready=source_ready,
    )
    stored = _stored_fingerprint(getattr(latest, "model_params", None))
    if stored is not None:
        return stored == expected
    return False


def world_forecast_sort_key(
    row: WorldForecastCandidate,
    *,
    priority_index: dict[str, int],
    concept_dataset_ids: frozenset[str],
    national_codes: frozenset[str],
) -> tuple:
    country_rank = priority_index.get(row.country_slug, len(priority_index))
    provider = (row.provider or "").strip().lower()
    # IMF/WEO is source-owned projections, outside our forecast policy. Do not
    # spend the bounded daily training batch on those rows before live models.
    eligibility_rank = 0 if row.eligible_for_training else 1
    is_concept = (
        0
        if (row.dataset_id or "").lower() in concept_dataset_ids
        or row.code in national_codes
        else 1
    )
    # Нацпровайдер раньше Eurostat; IMF вне policy и не national — в хвосте.
    if provider and provider not in {"eurostat", "imf"}:
        provider_rank = 0
    elif provider == "eurostat":
        provider_rank = 1
    else:
        provider_rank = 2
    freq_rank = _FREQ_RANK.get((row.frequency or "").strip().lower(), 9)
    return (eligibility_rank, country_rank, is_concept, provider_rank, freq_rank, row.id)


def sort_world_forecast_candidates(
    rows: Sequence[WorldForecastCandidate],
    *,
    priority_countries: Sequence[str] | None = None,
) -> list[WorldForecastCandidate]:
    priority = list(priority_countries) if priority_countries is not None else parse_priority_countries()
    priority_index = {slug: index for index, slug in enumerate(priority)}
    datasets, codes = concept_priority_sets()
    return sorted(
        rows,
        key=lambda row: world_forecast_sort_key(
            row,
            priority_index=priority_index,
            concept_dataset_ids=datasets,
            national_codes=codes,
        ),
    )


def _format_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0 or seconds != seconds:
        return "?"
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m"


class _WorldForecastLock:
    __slots__ = ("token", "redis", "held")

    def __init__(self) -> None:
        self.token: str | None = None
        self.redis = None
        self.held = False

    async def acquire(self) -> bool:
        from app.core.cache import get_state_redis

        self.token = uuid.uuid4().hex
        try:
            self.redis = await get_state_redis()
            acquired = await self.redis.set(
                WORLD_FORECAST_JOB_LOCK_KEY,
                self.token,
                nx=True,
                ex=WORLD_FORECAST_JOB_LOCK_TTL_SECONDS,
            )
            if not acquired:
                logger.info("World forecast job: lock held by another instance, skipping")
                self.redis = None
                return False
            self.held = True
            return True
        except Exception:
            logger.warning("World forecast job: lock check failed (Redis down), running unlocked")
            self.redis = None
            self.held = False
            return True

    async def refresh(self) -> None:
        if not self.held or self.redis is None or self.token is None:
            return
        try:
            current = await self.redis.get(WORLD_FORECAST_JOB_LOCK_KEY)
            if current == self.token:
                await self.redis.expire(
                    WORLD_FORECAST_JOB_LOCK_KEY,
                    WORLD_FORECAST_JOB_LOCK_TTL_SECONDS,
                )
        except Exception:
            logger.warning("World forecast job: lock refresh failed", exc_info=True)

    async def release(self) -> None:
        if not self.held or self.redis is None or self.token is None:
            return
        try:
            await self.redis.eval(_RELEASE_LUA, 1, WORLD_FORECAST_JOB_LOCK_KEY, self.token)
        except Exception:
            pass
        self.held = False


async def _deactivate_current(
    db: AsyncSession,
    indicator_id: int,
) -> int:
    rows = (
        await db.execute(
            select(WorldForecast).where(
                WorldForecast.world_indicator_id == indicator_id,
                WorldForecast.is_current.is_(True),
            )
        )
    ).scalars().all()
    for row in rows:
        row.is_current = False
    return len(rows)


async def world_forecast_source_ready(
    db: AsyncSession,
    indicator: WorldIndicator,
    *,
    forecast: WorldForecast | None = None,
) -> bool:
    """Eurostat forecast requires a successfully applied source revision."""
    if (indicator.provider or "").lower() != "eurostat":
        return True
    state = await db.get(WorldDatasetState, ("eurostat", indicator.dataset_id))
    if state is None or state.status != "ok" or state.last_success_at is None:
        return False
    if forecast is not None and _as_naive(state.last_success_at) > _as_naive(forecast.created_at):
        return False
    return True


def _model_params_for(
    indicator: WorldIndicator,
    eligibility,
    extra: dict | None = None,
    *,
    history_digest: str | None = None,
    source_ready: bool = True,
) -> dict:
    params = {
        **forecast_fingerprint(
            history_end=indicator.history_end,
            points_count=indicator.points_count,
            history_digest=history_digest,
            source_ready=source_ready,
        ),
    }
    if eligibility is not None:
        params.update({
            "registry_key": list(eligibility.registry_key),
            "provider": eligibility.provider,
            "dataset_id": eligibility.dataset_id,
            "unit": eligibility.unit,
            "frequency": eligibility.frequency,
            "season": eligibility.season,
            "requested_strategy": eligibility.strategy,
            "methodology": "shared_multi_window",
            "gate": "rolling_origin_mase",
            "benchmark": "seasonal_naive",
        })
    if extra:
        params.update(extra)
    return params


async def retrain_world_indicator_forecast(
    db: AsyncSession,
    indicator: WorldIndicator,
    *,
    history_digest: str | None = None,
) -> str:
    source_ready = await world_forecast_source_ready(db, indicator)
    eligibility, reason = forecast_eligibility_for(indicator)
    if not source_ready:
        eligibility, reason = None, "source_dataset_pending"
    if eligibility is None:
        await _deactivate_current(db, indicator.id)
        db.add(WorldForecast(
            world_indicator_id=indicator.id,
            strategy="none",
            model_name="World-skip",
            model_params=_model_params_for(
                indicator, None, {"skip_reason": reason},
                history_digest=history_digest, source_ready=source_ready,
            ),
            gate_status="skipped",
            gate_reason=reason,
            mase=None,
            baseline_mase=None,
            origins=0,
            horizon=0,
            is_current=False,
            created_at=_naive_now(),
        ))
        return "skipped"

    points = (
        await db.execute(
            select(WorldDataPoint)
            .where(WorldDataPoint.indicator_id == indicator.id)
            .order_by(WorldDataPoint.date)
        )
    ).scalars().all()
    dates = [point.date for point in points]
    values = [float(point.value) for point in points]
    history_digest = hashlib.md5(
        "|".join(f"{point.date.isoformat()}:{point.value}" for point in points).encode(),
        usedforsecurity=False,
    ).hexdigest() if points else None
    gate = await asyncio.to_thread(
        train_quality_gated_world_forecast,
        dates,
        values,
        frequency=eligibility.frequency,
        horizon=eligibility.horizon,
        season=eligibility.season,
        strategy=eligibility.strategy,
        # Одинаковый fail-closed gate для США, Европы и остальных стран.
        strict=True,
    )
    country = await db.get(WorldCountry, indicator.country_id)
    if (
        country is not None and country.code == "US"
        and gate.result is not None and is_percentage_unit(indicator.unit)
        and values and min(values) >= 0 and max(values) <= 100
        and any(point.value < 0 or point.value > 100 for point in gate.result.points)
    ):
        gate = WorldForecastGate(
            "failed", "out_of_range", gate.strategy, gate.mase,
            gate.baseline_mase, gate.origins, None,
        )

    await _deactivate_current(db, indicator.id)
    forecast = WorldForecast(
        world_indicator_id=indicator.id,
        strategy=gate.strategy,
        model_name=(
            gate.result.model_name
            if gate.result is not None
            else f"World-{gate.strategy}-v1"
        ),
        model_params=_model_params_for(
            indicator,
            eligibility,
            {
                "resolved_strategy": gate.strategy,
            },
            history_digest=history_digest,
            source_ready=source_ready,
        ),
        gate_status=gate.status,
        gate_reason=gate.reason,
        mase=gate.mase,
        baseline_mase=gate.baseline_mase,
        origins=gate.origins,
        horizon=eligibility.horizon,
        is_current=gate.status in PUBLISHED_GATE_STATUSES,
        created_at=_naive_now(),
    )
    db.add(forecast)
    await db.flush()
    if gate.result is not None:
        for point in gate.result.points:
            db.add(WorldForecastValue(
                forecast_id=forecast.id,
                date=point.date,
                value=point.value,
                lower_bound=point.lower_bound,
                upper_bound=point.upper_bound,
            ))
    return gate.status


async def _load_candidates(
    db: AsyncSession,
    country_slugs: Sequence[str] | None = None,
) -> list[WorldForecastCandidate]:
    # Correlated index scan hashes the whole training history in SQL. This
    # detects revisions to existing observations without a new date/count.
    digest = (
        select(func.md5(func.string_agg(
            cast(WorldDataPoint.date, String) + literal(":") + cast(WorldDataPoint.value, String),
            aggregate_order_by(literal("|"), WorldDataPoint.date),
        )))
        .where(WorldDataPoint.indicator_id == WorldIndicator.id)
        .correlate(WorldIndicator)
        .scalar_subquery()
    )
    stmt = (
        select(
            WorldIndicator.id,
            WorldCountry.slug,
            WorldIndicator.provider,
            WorldIndicator.dataset_id,
            WorldIndicator.code,
            WorldIndicator.frequency,
            WorldIndicator.history_end,
            WorldIndicator.points_count,
            digest.label("history_digest"),
            WorldIndicator.name_quality,
            WorldIndicator.unit,
            WorldDatasetState.status.label("source_status"),
            WorldDatasetState.last_success_at.label("source_last_success_at"),
        )
        .join(WorldCountry, WorldIndicator.country_id == WorldCountry.id)
        .outerjoin(
            WorldDatasetState,
            (WorldDatasetState.provider == WorldIndicator.provider)
            & (WorldDatasetState.dataset_id == WorldIndicator.dataset_id),
        )
        .where(
            WorldIndicator.is_listed.is_(True),
            WorldIndicator.frequency.in_(("monthly", "quarterly", "annual")),
        )
    )
    if country_slugs:
        stmt = stmt.where(WorldCountry.slug.in_(tuple(country_slugs)))
    rows = (await db.execute(stmt)).all()
    candidates = []
    for row in rows:
        source_ready = str(row.provider or "").lower() != "eurostat" or (
            row.source_status == "ok" and row.source_last_success_at is not None
        )
        eligible, _reason = forecast_eligibility_for(SimpleNamespace(
            provider=row.provider,
            dataset_id=row.dataset_id,
            unit=row.unit,
            frequency=row.frequency,
            is_listed=True,
            name_quality=row.name_quality,
            points_count=row.points_count,
            history_end=row.history_end,
        ))
        candidates.append(WorldForecastCandidate(
            id=int(row.id),
            country_slug=str(row.slug),
            provider=str(row.provider or ""),
            dataset_id=str(row.dataset_id or ""),
            code=str(row.code or ""),
            frequency=str(row.frequency or ""),
            history_end=row.history_end,
            points_count=int(row.points_count or 0),
            history_digest=row.history_digest,
            eligible_for_training=eligible is not None and source_ready,
            source_ready=source_ready,
        ))
    return candidates


async def _latest_forecasts_map(
    db: AsyncSession,
    *,
    country_slugs: Sequence[str] | None = None,
) -> dict[int, WorldForecast]:
    """Последняя запись world_forecasts на listed M/Q/A — без IN по 35k id."""
    eligible = (
        select(WorldIndicator.id)
        .join(WorldCountry, WorldIndicator.country_id == WorldCountry.id)
        .where(
            WorldIndicator.is_listed.is_(True),
            WorldIndicator.frequency.in_(("monthly", "quarterly", "annual")),
        )
    )
    if country_slugs:
        eligible = eligible.where(WorldCountry.slug.in_(tuple(country_slugs)))
    rows = (
        await db.execute(
            select(WorldForecast)
            .where(WorldForecast.world_indicator_id.in_(eligible))
            .distinct(WorldForecast.world_indicator_id)
            .order_by(
                WorldForecast.world_indicator_id,
                WorldForecast.created_at.desc(),
                WorldForecast.id.desc(),
            )
        )
    ).scalars().all()
    return {int(row.world_indicator_id): row for row in rows}


def classify_unchanged(
    candidates: Sequence[WorldForecastCandidate],
    latest_by_id: dict[int, object],
    *,
    now: datetime,
    max_age_days: int,
    force: bool,
) -> set[int]:
    unchanged: set[int] = set()
    for row in candidates:
        if forecast_is_unchanged(
            latest_by_id.get(row.id),
            history_end=row.history_end,
            points_count=row.points_count,
            history_digest=row.history_digest,
            source_ready=row.source_ready,
            now=now,
            max_age_days=max_age_days,
            force=force,
        ):
            unchanged.add(row.id)
    return unchanged


def select_forecast_batch(
    candidates: Sequence[WorldForecastCandidate],
    unchanged_ids: set[int],
    limit: int | None,
) -> tuple[list[WorldForecastCandidate], set[int]]:
    """Лимит относится к новым обучениям, а не к первым N каталожным строкам."""
    if limit is None:
        return list(candidates), unchanged_ids
    selected = [row for row in candidates if row.id not in unchanged_ids][:max(0, int(limit))]
    return selected, set()


async def load_world_forecast_plan(
    *,
    country_slugs: Sequence[str] | str | None = None,
    limit: int | None = None,
    force: bool = False,
    eligible_only: bool = False,
) -> tuple[list[WorldForecastCandidate], set[int]]:
    """Отсортированный план обхода и id рядов, которые можно пропустить."""
    slugs = parse_country_slugs(country_slugs)
    async with async_session() as db:
        candidates = sort_world_forecast_candidates(
            await _load_candidates(db, slugs or None),
        )
        if eligible_only:
            candidates = [row for row in candidates if row.eligible_for_training]
        latest_by_id = await _latest_forecasts_map(db, country_slugs=slugs or None)
    unchanged_ids = classify_unchanged(
        candidates,
        latest_by_id,
        now=_naive_now(),
        max_age_days=int(settings.world_forecast_max_age_days),
        force=force,
    )
    return select_forecast_batch(candidates, unchanged_ids, limit)


async def _bump_world_forecast_cache() -> None:
    await bump_namespaces(*WORLD_FORECAST_CACHE_NAMESPACES)


def _empty_counts(selected: int = 0, **extra: int) -> dict[str, int]:
    counts = {
        "selected": selected,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "advisory": 0,
        "unchanged": 0,
        "to_train": 0,
    }
    counts.update(extra)
    return counts


def _summary_from_counts(counts: dict[str, int], *, lock_busy: bool = False) -> WorldForecastRunSummary:
    return WorldForecastRunSummary(
        selected=counts.get("selected", 0),
        passed=counts.get("passed", 0),
        failed=counts.get("failed", 0),
        skipped=counts.get("skipped", 0),
        errors=counts.get("errors", 0),
        advisory=counts.get("advisory", 0),
        unchanged=counts.get("unchanged", 0),
        to_train=counts.get("to_train", 0),
        lock_busy=lock_busy,
    )


async def world_forecast_job(
    *,
    country_slugs: Sequence[str] | str | None = None,
    limit: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    acquire_lock: bool = True,
    eligible_only: bool = False,
) -> WorldForecastRunSummary:
    """Пересчитать публичные M/Q/A primary-series; ошибки изолированы по ряду."""
    slugs = parse_country_slugs(country_slugs)
    lock = _WorldForecastLock()
    if acquire_lock and not dry_run:
        if not await lock.acquire():
            return _summary_from_counts(_empty_counts(), lock_busy=True)

    try:
        candidates, unchanged_ids = await load_world_forecast_plan(
            country_slugs=slugs or None,
            limit=limit,
            force=force,
            eligible_only=eligible_only,
        )
        counts = _empty_counts(
            selected=len(candidates),
            unchanged=len(unchanged_ids),
            to_train=len(candidates) - len(unchanged_ids),
        )

        if dry_run:
            logger.info(
                "World forecast dry-run: selected=%s unchanged=%s to_train=%s force=%s countries=%s",
                counts["selected"],
                counts["unchanged"],
                counts["to_train"],
                force,
                ",".join(slugs) or "*",
            )
            return _summary_from_counts(counts)

        logger.info(
            "World forecast starting selected=%s unchanged=%s to_train=%s force=%s",
            counts["selected"],
            counts["unchanged"],
            counts["to_train"],
            force,
        )
        bump_every = max(1, int(settings.world_forecast_cache_bump_every))
        writes_since_bump = 0
        changed = False
        started = time.monotonic()
        done = 0
        total = len(candidates)

        for row in candidates:
            done += 1
            if row.id not in unchanged_ids:
                try:
                    async with async_session() as db:
                        indicator = await db.get(WorldIndicator, row.id)
                        if indicator is None:
                            counts["skipped"] += 1
                        else:
                            status = await retrain_world_indicator_forecast(
                                db, indicator, history_digest=row.history_digest,
                            )
                            await db.commit()
                            counts[status] = counts.get(status, 0) + 1
                            if status in {"passed", "failed", "advisory", "skipped"}:
                                changed = True
                                writes_since_bump += 1
                                if writes_since_bump >= bump_every:
                                    await _bump_world_forecast_cache()
                                    writes_since_bump = 0
                except Exception:  # noqa: BLE001 — один ряд не отменяет весь world run
                    counts["errors"] += 1
                    logger.exception("World forecast failed for indicator_id=%s", row.id)

            if done % _PROGRESS_EVERY == 0 or done == total:
                elapsed = time.monotonic() - started
                if elapsed >= 1:
                    rate = done / (elapsed / 60.0)
                    remaining = (total - done) / rate * 60.0 if rate else None
                    rate_s = f"{rate:.1f}/min"
                    eta_s = _format_eta(remaining)
                else:
                    rate_s = "fast"
                    eta_s = "0m" if done == total else "?"
                logger.info(
                    "World forecast progress %s/%s "
                    "passed=%s advisory=%s failed=%s skipped=%s unchanged=%s errors=%s "
                    "rate=%s eta=%s",
                    done,
                    total,
                    counts["passed"],
                    counts["advisory"],
                    counts["failed"],
                    counts["skipped"],
                    counts["unchanged"],
                    counts["errors"],
                    rate_s,
                    eta_s,
                )
                await lock.refresh()

        if changed:
            await _bump_world_forecast_cache()
        summary = _summary_from_counts(counts)
        logger.info("World forecast run completed: %s", summary)
        return summary
    finally:
        await lock.release()


async def scheduled_world_forecast_job() -> WorldForecastRunSummary:
    """Cron: лок держит locked_job, внутри повторно не берём."""
    return await world_forecast_job(acquire_lock=False)
