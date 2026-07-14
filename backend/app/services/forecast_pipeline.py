"""Пересчёт прогнозов после обновления ряда.

После рефакторинга (Шаг 8): диспетчеризация стратегий вынесена в
`forecast_strategies/registry.py`. Этот модуль отвечает только за:
1. Загрузку исторических данных индикатора и approved/derived контекста.
2. Выбор стратегии (по `model_config.forecast_strategy` или legacy-fallback).
3. Сохранение всех `StrategyOutput` через `_save_forecast`.
"""

import asyncio
import logging
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Forecast, ForecastValue, Indicator, IndicatorData
from app.services.forecast_strategies import (
    STRATEGIES,
    StrategyContext,
    StrategyOutput,
    resolve,
)
from app.services.forecast_strategies.cpi_combined import (
    CPI_DERIVED_CODES,
    CPI_DERIVED_TARGETS,
)
from app.services.forecaster import CPI_INDICATOR_CODES

logger = logging.getLogger(__name__)


# Re-exported for backwards compatibility (used by tests and other modules).
CPI_DERIVED_FORECAST_CODES = CPI_DERIVED_CODES
CPI_DERIVED_FORECAST_TARGETS = CPI_DERIVED_TARGETS


# ---------------------------------------------------------------------------
#  DB helpers
# ---------------------------------------------------------------------------

async def clear_current_forecasts(db: AsyncSession, indicator: Indicator) -> int:
    old_q = await db.execute(
        select(Forecast).where(
            Forecast.indicator_id == indicator.id,
            Forecast.is_current.is_(True),
        )
    )
    old = old_q.scalars().all()
    for fc in old:
        await db.delete(fc)
    return len(old)


async def _forecast_bounds(
    db: AsyncSession, indicator: Indicator,
) -> tuple[float | None, float | None]:
    """Доменные границы прогноза (В-27).

    Явные — из `model_config_json.forecast_constraints` (`non_negative`,
    `min`, `max`). Неявный пол: если вся фактическая история ряда >= 0
    (цены, ставки, индексы, объёмы), прогноз и его CI не имеют права уходить
    ниже нуля — статистическая модель об этом не знает.
    """
    cons = (indicator.model_config_json or {}).get("forecast_constraints") or {}
    lo = cons.get("min")
    hi = cons.get("max")
    if lo is None and cons.get("non_negative"):
        lo = 0.0
    if lo is None:
        min_actual = await db.scalar(
            select(func.min(IndicatorData.value))
            .where(IndicatorData.indicator_id == indicator.id)
        )
        if min_actual is not None and float(min_actual) >= 0:
            lo = 0.0
    return (float(lo) if lo is not None else None,
            float(hi) if hi is not None else None)


def _clamp(v: float | None, lo: float | None, hi: float | None) -> float | None:
    if v is None:
        return None
    if lo is not None and v < lo:
        return lo
    if hi is not None and v > hi:
        return hi
    return v


async def _save_forecast(
    db: AsyncSession,
    indicator: Indicator,
    output: StrategyOutput,
) -> None:
    """Deactivate old forecasts with matching model prefix and save new one."""
    result = output.result
    prefix = output.model_name_prefix

    old_q = select(Forecast).where(
        Forecast.indicator_id == indicator.id,
        Forecast.is_current.is_(True),
    )
    if prefix:
        old_q = old_q.where(Forecast.model_name.like(f"{prefix}%"))
    else:
        old_q = old_q.where(~Forecast.model_name.like("Inflation-12M%"))

    old = (await db.execute(old_q)).scalars().all()
    for fc in old:
        fc.is_current = False

    new_forecast = Forecast(
        indicator_id=indicator.id,
        model_name=result.model_name,
        model_params={"cumulative_12m": result.cumulative_12m},
        aic=result.aic,
        bic=result.bic,
        is_current=True,
    )
    db.add(new_forecast)
    await db.flush()

    lo, hi = await _forecast_bounds(db, indicator)
    clamped = 0
    for fp in result.points:
        value = _clamp(fp.value, lo, hi)
        lower = _clamp(fp.lower_bound, lo, hi)
        upper = _clamp(fp.upper_bound, lo, hi)
        if (value, lower, upper) != (fp.value, fp.lower_bound, fp.upper_bound):
            clamped += 1
        db.add(ForecastValue(
            forecast_id=new_forecast.id,
            date=fp.date,
            value=value,
            lower_bound=lower,
            upper_bound=upper,
        ))
    if clamped:
        logger.warning(
            "Forecast '%s' for %s: %d/%d point(s) clamped to domain bounds [%s, %s]",
            result.model_name, indicator.code, clamped, len(result.points), lo, hi,
        )

    logger.info(
        "Saved forecast '%s' for %s (%d points)",
        result.model_name, indicator.code, len(result.points),
    )


# ---------------------------------------------------------------------------
#  Strategy selection (with legacy fallback)
# ---------------------------------------------------------------------------

def _legacy_resolve_name(indicator: Indicator, cfg: dict) -> str:
    """Старая if-цепочка из forecast_pipeline.py — используется когда у
    индикатора не задан `forecast_strategy` в model_config_json.

    Возвращает имя стратегии, под которым старая логика продолжает
    работать. После полной миграции seed_data → каждый индикатор имеет
    явное имя — этот fallback можно убрать.
    """
    if cfg.get("approved_forecast_values"):
        return "approved"
    if indicator.code in CPI_INDICATOR_CODES:
        return "cpi_combined"
    if cfg.get("forecast_model") == "housing_quarterly":
        return "housing_quarterly"
    return "generic_ols"


# ---------------------------------------------------------------------------
#  Helpers for derived strategy: load source actuals + forecast
# ---------------------------------------------------------------------------

async def _load_indicator_full_series(
    db: AsyncSession, indicator_code: str,
) -> list[tuple[date, float]]:
    """actuals + active forecast points для одного индикатора по коду.

    Когда у индикатора одновременно живут несколько активных моделей (CPI имеет
    `CPI-Monthly-MW` + `Inflation-12M-MW`, оба is_current=true), мы должны
    собрать прогноз ТОЛЬКО в той же системе единиц, что и actuals — иначе
    derived-aggregator перемешает уровни цен с %-инфляцией. Простейшая
    fix-эвристика: исключаем Inflation-12M* (та же логика, что в api/forecasts.py
    при отдаче forecast endpoint'а).
    """
    src_q = await db.execute(
        select(Indicator).where(Indicator.code == indicator_code)
    )
    src = src_q.scalar_one_or_none()
    if src is None:
        return [], set()

    actual_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == src.id)
        .order_by(IndicatorData.date)
    )
    actuals = [(d.date, float(d.value)) for d in actual_q.scalars().all()]
    actual_dates = {d for d, _ in actuals}

    fc_q = await db.execute(
        select(ForecastValue)
        .join(Forecast, Forecast.id == ForecastValue.forecast_id)
        .where(
            Forecast.indicator_id == src.id,
            Forecast.is_current.is_(True),
            ~Forecast.model_name.like("Inflation-12M%"),
        )
        .order_by(ForecastValue.date)
    )
    forecasts = [(fv.date, float(fv.value)) for fv in fc_q.scalars().all()]

    actuals_dict = dict(actuals)
    for d, v in forecasts:
        if d not in actuals_dict:
            actuals_dict[d] = v
    return sorted(actuals_dict.items()), actual_dates


async def _maybe_inject_source_for_derived(
    db: AsyncSession, ctx_cfg: dict,
) -> dict:
    """Если стратегия — derived_from_source, подгружаем ряд источника."""
    derived_cfg = ctx_cfg.get("derived_forecast") or {}
    source_code = derived_cfg.get("source_code")
    if not source_code:
        return ctx_cfg
    series, actual_dates = await _load_indicator_full_series(db, source_code)
    new_cfg = dict(ctx_cfg)
    new_cfg["_source_data"] = series
    new_cfg["_source_actual_dates"] = sorted(actual_dates)
    # Второй источник — для тождеств из двух рядов (subtract): trade-balance
    # = exports − imports. Грузим его факт+прогноз отдельным ключом.
    source_code_2 = derived_cfg.get("source_code_2")
    if source_code_2:
        series2, actual_dates2 = await _load_indicator_full_series(db, source_code_2)
        new_cfg["_source_data_2"] = series2
        new_cfg["_source_actual_dates_2"] = sorted(actual_dates2)
    return new_cfg


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

async def retrain_indicator_forecast(
    db: AsyncSession,
    indicator: Indicator,
    _retrain_chain: set[str] | None = None,
) -> None:
    """Пересчитать прогноз для одного индикатора и каскадно — для зависимых.

    `_retrain_chain` — внутренний параметр защиты от циклов в каскаде:
    содержит коды индикаторов, уже находящихся в текущей цепочке retrain.
    Внешние вызовы передают `None`.
    """
    cfg = indicator.model_config_json or {}
    forecast_steps = int(cfg.get("forecast_steps", settings.forecast_steps) or 0)

    if forecast_steps <= 0:
        if indicator.code in CPI_DERIVED_FORECAST_TARGETS:
            logger.info(
                "'%s' is populated by CPI source retrain; skipping direct retrain",
                indicator.code,
            )
            return
        removed = await clear_current_forecasts(db, indicator)
        logger.info(
            "forecast_steps<=0 for '%s', skipping retrain and removed %d stale forecast(s)",
            indicator.code, removed,
        )
        return

    strategy_name = cfg.get("forecast_strategy") or _legacy_resolve_name(indicator, cfg)
    strategy = resolve(strategy_name)
    if strategy is None:
        # Н-7: нерезолвнутая стратегия — чистим устаревший прогноз (иначе он
        # молча остаётся current и стареет) и алертим, а не только логируем.
        removed = await clear_current_forecasts(db, indicator)
        logger.error(
            "No strategy resolved for '%s' (name=%s); cleared %d stale forecast(s)",
            indicator.code, strategy_name, removed,
        )
        try:
            from app.services.alerting import alert_forecast_issue
            await alert_forecast_issue(
                indicator.code,
                f"Стратегия '{strategy_name}' не найдена в реестре; "
                f"очищено {removed} устаревших прогнозов.",
            )
        except Exception:  # pragma: no cover — алерт не роняет pipeline
            logger.warning("Forecast issue alert failed", exc_info=True)
        return

    # Derived стратегия требует данные источника — подгружаем заранее.
    enriched_cfg = await _maybe_inject_source_for_derived(db, cfg)

    data_q = await db.execute(
        select(IndicatorData)
        .where(IndicatorData.indicator_id == indicator.id)
        .order_by(IndicatorData.date)
    )
    all_data = data_q.scalars().all()

    # Approved/derived стратегии могут работать без 36 точек истории.
    requires_history = strategy_name not in ("approved", "derived_from_source")
    if requires_history and len(all_data) < 36:
        removed = await clear_current_forecasts(db, indicator)
        logger.warning(
            "Not enough data for forecast (%d points), removed %d stale forecast(s)",
            len(all_data), removed,
        )
        return

    dates = [d.date for d in all_data]
    values = [float(d.value) for d in all_data]

    ctx = StrategyContext(
        indicator_code=indicator.code,
        indicator_frequency=indicator.frequency or "monthly",
        forecast_steps=forecast_steps,
        cfg=enriched_cfg,
    )

    outputs = await asyncio.to_thread(strategy, dates, values, ctx)

    if not outputs:
        # Стратегия может явно вернуть [] (например, derived без источника):
        # в этом случае чистим существующий прогноз, чтобы не было stale.
        removed = await clear_current_forecasts(db, indicator)
        logger.warning(
            "Strategy '%s' returned 0 outputs for '%s'; cleared %d stale forecast(s)",
            strategy_name, indicator.code, removed,
        )
        return

    target_cache: dict[str, Indicator] = {indicator.code: indicator}

    for output in outputs:
        target_code = output.target_indicator_code or indicator.code
        target = target_cache.get(target_code)
        if target is None:
            target_q = await db.execute(
                select(Indicator).where(Indicator.code == target_code)
            )
            target = target_q.scalar_one_or_none()
            if target is None:
                logger.warning(
                    "Target indicator '%s' not found; skipping output for strategy '%s'",
                    target_code, strategy_name,
                )
                continue
            target_cache[target_code] = target

        await _save_forecast(db, target, output)

    logger.info(
        "Retrain complete for '%s' (strategy=%s, %d outputs)",
        indicator.code, strategy_name, len(outputs),
    )

    chain = (_retrain_chain or set()) | {indicator.code}
    await _retrain_dependents(db, indicator, chain)


async def _retrain_dependents(
    db: AsyncSession,
    source: Indicator,
    chain: set[str],
) -> None:
    """Каскадный retrain: после успешного retrain индикатора-источника
    пересчитываем все индикаторы, у которых
    `model_config.derived_forecast.source_code == source.code`.

    `chain` хранит коды индикаторов уже в текущей retrain-цепочке —
    защищает от бесконечной рекурсии при взаимных зависимостях.
    """
    candidates_q = await db.execute(select(Indicator).where(Indicator.is_active.is_(True)))
    candidates = candidates_q.scalars().all()

    for cand in candidates:
        if cand.code in chain:
            continue
        cfg = cand.model_config_json or {}
        derived_cfg = cfg.get("derived_forecast") or {}
        # Зависит ли кандидат от source: основной источник или второй
        # (для тождеств вида trade-balance = exports − imports).
        src_codes = {derived_cfg.get("source_code"), derived_cfg.get("source_code_2")}
        if source.code not in src_codes:
            continue
        logger.info("Cascading retrain: %s → %s", source.code, cand.code)
        try:
            await retrain_indicator_forecast(db, cand, _retrain_chain=chain)
        except Exception as e:  # pragma: no cover — каскад не должен ронять основной retrain
            # Н-8: зависимый прогноз молча остаётся stale — алертим.
            logger.exception("Cascading retrain failed for '%s'", cand.code)
            try:
                from app.services.alerting import alert_forecast_issue
                await alert_forecast_issue(
                    cand.code,
                    f"Каскадный retrain от '{source.code}' упал: {str(e)[:200]}",
                )
            except Exception:
                logger.warning("Forecast issue alert failed", exc_info=True)


# ---------------------------------------------------------------------------
#  Change-gate + empty-forecast gap-fill
# ---------------------------------------------------------------------------

def values_changed_for_retrain(
    records_added: int,
    records_updated: int,
    pruned: int = 0,
) -> bool:
    """True, если upsert реально изменил ряд (ADR-0002: без изменений — без retrain)."""
    return records_added > 0 or records_updated > 0 or pruned > 0


def forecast_steps_of(indicator: Indicator) -> int:
    cfg = indicator.model_config_json or {}
    return int(cfg.get("forecast_steps", 0) or 0)


def _is_derived_from_source(indicator: Indicator) -> bool:
    cfg = indicator.model_config_json or {}
    return cfg.get("forecast_strategy") == "derived_from_source"


def order_for_forecast_catch_up(indicators: list[Indicator]) -> list[Indicator]:
    """Сначала собственные модели (каскад заполнит derived_from_source), потом хвост."""
    primary = [i for i in indicators if not _is_derived_from_source(i)]
    derived = [i for i in indicators if _is_derived_from_source(i)]
    return primary + derived


async def _current_forecast_value_count(db: AsyncSession, indicator_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count(ForecastValue.id))
            .join(Forecast, Forecast.id == ForecastValue.forecast_id)
            .where(
                Forecast.indicator_id == indicator_id,
                Forecast.is_current.is_(True),
            )
        )
        or 0
    )


async def find_indicators_needing_forecast_catch_up(
    db: AsyncSession,
) -> list[Indicator]:
    """Активные ряды с forecast_steps>0 без текущего прогноза (или с 0 точек)."""
    rows = (
        await db.execute(select(Indicator).where(Indicator.is_active.is_(True)))
    ).scalars().all()
    needing: list[Indicator] = []
    for ind in rows:
        if forecast_steps_of(ind) <= 0:
            continue
        if await _current_forecast_value_count(db, ind.id) > 0:
            continue
        needing.append(ind)
    return needing


async def catch_up_empty_forecasts(db: AsyncSession) -> list[str]:
    """Одноразовый gap-fill: retrain для рядов со steps>0 без текущего прогноза.

    После seed/deploy со включённой стратегией или после сбоя retrain — без
    ручного вызова. Источники сначала: `_retrain_dependents` заполняет siblings.
    Возвращает коды, для которых вызван retrain (не гарантия непустого результата —
    мало истории / пустая стратегия остаются без точек).
    """
    needing = await find_indicators_needing_forecast_catch_up(db)
    if not needing:
        return []

    ordered = order_for_forecast_catch_up(needing)
    logger.info(
        "Forecast catch-up: %d indicator(s) missing current forecast: %s",
        len(ordered),
        ", ".join(i.code for i in ordered),
    )
    retrained: list[str] = []
    for ind in ordered:
        # Каскад от primary мог уже заполнить derived — не гоняем лишний раз.
        if await _current_forecast_value_count(db, ind.id) > 0:
            continue
        try:
            await retrain_indicator_forecast(db, ind)
            retrained.append(ind.code)
        except Exception as e:  # pragma: no cover — gap-fill не роняет startup/ETL
            logger.exception("Forecast catch-up failed for '%s'", ind.code)
            try:
                from app.services.alerting import alert_forecast_issue
                await alert_forecast_issue(
                    ind.code,
                    f"Gap-fill retrain упал: {str(e)[:200]}",
                )
            except Exception:
                logger.warning("Forecast issue alert failed", exc_info=True)
    return retrained
