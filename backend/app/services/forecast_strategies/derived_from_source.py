"""Derived forecast: производный прогноз от прогноза другого индикатора.

Когда у индикатора X есть свой прогноз (например, gdp-nominal), а
индикатор Y — это его математическая производная (например, gdp-yoy =
yoy от gdp-nominal), нет смысла отдельно обучать модель Y.

Эта стратегия читает прогноз индикатора-источника из БД, применяет
формулу `op` к (история X + прогноз X) и выдаёт прогноз для Y.

Конфигурация в `model_config_json.derived_forecast`:
    {
        "source_code": "gdp-nominal",
        "operation": "yoy",      // см. список ниже
        "model_name": "GDP-YoY-Derived",
        "extra": {...}           // op-специфические аргументы
    }

Поддерживаемые operation (соответствуют DerivedSpec ops в БД):
    - yoy_quarterly       : Y[t] = (X[t] / X[t-4]) * 100 - 100   (квартальный yoy)
    - yoy_monthly         : Y[t] = (X[t] / X[t-12]) * 100 - 100  (месячный yoy)
    - qoq                 : Y[t] = (X[t] / X[t-1]) * 100 - 100
    - real_from_yoy       : Y[t] = Y[t-1y] * (1 + yoy_source[t]/100)
    - december_to_december: Y[year] = (∏ X[m]/100 за m=Jan..Dec) * 100 - 100
                            (1 точка/год, точка анкорится на date(year, 1, 1);
                            годы с неполными 12 мес. пропускаются)
    - annual_sum          : Y[year] = Σ X[q] за q ∈ year
                            (1 точка/год, для квартальных рядов нужны 4 кв.;
                            годы с неполным числом точек пропускаются)
    - cpi_mom_yoy           : YoY % на накопленном уровне из месячных ИПЦ (~100)
    - cpi_mom_qoq           : QoQ % на концах кварталов из месячных ИПЦ
    - weekly_inflation_by_calendar_month : ∏ недель в календарном месяце − 100
    - weekly_mtd_in_calendar_month      : накопление с 1-й недели месяца по каждую неделю
    - pipeline            : generic-цепочка ops из `derived_ops` (для унифи-
                            цированных view-mode siblings: period_sum/avg/last,
                            period_over_period[_abs], mom[_abs], yoy[_abs],
                            rebase_to_first). Конфиг: `pipeline` = список
                            [op_name, kwargs]; опц. `complete_bucket`+`min_periods`
                            отбрасывают неполные будущие кварталы/годы.

ВАЖНО: эта стратегия — RUNTIME-only. Она не пишет в БД, она лишь
готовит точки прогноза, которые pipeline сохранит обычным образом.
БД-доступ принципиально нужен (читаем прогноз источника), поэтому
сигнатура стратегии расширена опциональным `db_session` через ctx.cfg.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Sequence

from app.services.forecast_strategies.base import StrategyContext, StrategyOutput
from app.services.forecaster import ForecastPoint, ForecastResult
from app.services import derived_ops as ops_module
from app.services.derived_ops import (
    annual_sum as ops_annual_sum,
    cpi_mom_qoq as ops_cpi_mom_qoq,
    cpi_mom_yoy as ops_cpi_mom_yoy,
    december_to_december as ops_december_to_december,
    weekly_inflation_by_calendar_month as ops_weekly_inflation_by_calendar_month,
    weekly_mtd_in_calendar_month as ops_weekly_mtd_in_calendar_month,
)

logger = logging.getLogger(__name__)


def _yoy(values_with_dates: list[tuple[date, float]], step: int) -> list[tuple[date, float]]:
    """Y[t] = (X[t] / X[t-step]) * 100 - 100. step=12 для месячного yoy, 4 для квартального."""
    by_date = {d: v for d, v in values_with_dates}
    out: list[tuple[date, float]] = []
    sorted_pairs = sorted(values_with_dates)
    for i, (d, v) in enumerate(sorted_pairs):
        if i < step or v is None:
            continue
        prev_d, prev_v = sorted_pairs[i - step]
        if prev_v in (None, 0):
            continue
        out.append((d, v / prev_v * 100.0 - 100.0))
    return out


def _qoq(values_with_dates: list[tuple[date, float]]) -> list[tuple[date, float]]:
    out: list[tuple[date, float]] = []
    sorted_pairs = sorted(values_with_dates)
    for i in range(1, len(sorted_pairs)):
        d, v = sorted_pairs[i]
        prev_d, prev_v = sorted_pairs[i - 1]
        if prev_v in (None, 0) or v is None:
            continue
        out.append((d, v / prev_v * 100.0 - 100.0))
    return out


def _run_pipeline(
    source_data: list[tuple[date, float]],
    derived_cfg: dict,
) -> list[tuple[date, float]]:
    """Прогон generic-pipeline (op_name, kwargs) на (история+прогноз) источника.

    Те же чистые ops из `derived_ops`, что считают actuals в CalculationEngine,
    применяются к объединённому ряду источника — прогноз derived-режима
    считается ровно так же, как его факт.

    Guard полноты: для агрегаций крупнее нативной (квартал/год из месяцев)
    `_aggregate` выдаёт точку даже по неполному bucket'у → в будущем это даёт
    «частичный» квартал/год (напр. сумма 1 месяца как годовая). Поэтому при
    заданных `complete_bucket` + `min_periods` оставляем только те bucket'ы,
    где в объединённом источнике набралось ≥ `min_periods` суб-периодов.
    """
    steps = derived_cfg.get("pipeline") or []
    series: list[tuple[date, float]] = list(source_data)
    for name, kwargs in steps:
        fn = getattr(ops_module, name, None)
        if fn is None:
            logger.error("derived_from_source pipeline: unknown op '%s'", name)
            return []
        series = fn(series, **dict(kwargs))

    complete_bucket = derived_cfg.get("complete_bucket")
    min_periods = int(derived_cfg.get("min_periods", 0) or 0)
    if complete_bucket and min_periods > 1:
        counts: dict[date, int] = {}
        for d, _v in source_data:
            _key, anchor = ops_module._bucket_anchor(d, complete_bucket)
            if anchor is None:
                continue
            counts[anchor] = counts.get(anchor, 0) + 1
        series = [(d, v) for d, v in series if counts.get(d, 0) >= min_periods]
    return series


def _pipeline_bucket_spec(pipeline: list) -> tuple[str, str] | None:
    """Метод агрегации и гранулярность для квартала/года в pipeline-режиме."""
    for op, kwargs in pipeline:
        gran = kwargs.get("granularity")
        if gran not in ("quarter", "year"):
            continue
        if op == "period_sum":
            return "sum", gran
        if op == "period_last":
            return "last", gran
        if op == "period_avg":
            return "avg", gran
    return None


def _forecast_from_monthly_tail(
    source_data: list[tuple[date, float]],
    source_actual_dates: set[date],
    granularity: str,
    method: str,
) -> list[tuple[date, float]]:
    """Прогноз квартала/года из месячного ряда источника (факт + прогноз).

    Для каждого bucket'а, в котором есть хотя бы один прогнозный месяц, значение
    считается по ВСЕМ месяцам bucket'а — факт за прошедшие месяцы плюс прогноз
    на оставшиеся:
    - поток (sum): сумма всех месяцев периода (YTD факт + прогноз остатка);
    - уровень/ставка (last): последний месяц периода;
    - среднее (avg): среднее по месяцам периода.

    Так текущий незавершённый год = факт с начала года + прогноз до декабря,
    а не «последний месяц × 12» (что давало нереалистичные −18 трлн на бюджете).

    Для гранулярности `year` отдаётся РОВНО ОДНА точка — первый незавершённый
    год (тот, по которому ещё нет полных данных). Никаких +1 года вперёд (2027).
    """
    expected = ops_module._expected_subperiods(source_data, granularity)

    buckets: dict[date, list[tuple[date, float]]] = {}
    has_forecast: dict[date, bool] = {}
    for d, v in source_data:
        _key, anchor = ops_module._bucket_anchor(d, granularity)
        if anchor is None:
            continue
        buckets.setdefault(anchor, []).append((d, float(v)))
        if d not in source_actual_dates:
            has_forecast[anchor] = True

    # Прогнозируем только bucket'ы с прогнозными месяцами и полным составом
    # суб-периодов (текущий год добирается фактом+прогнозом до 12 мес.). Так не
    # отдаём «частичный» будущий квартал/год на конце горизонта (визуальный обвал).
    fc_anchors = sorted(
        a for a in buckets
        if has_forecast.get(a) and (expected is None or len(buckets[a]) >= expected)
    )
    if not fc_anchors:
        return []
    if granularity == "year":
        # Одна годовая точка: только первый незавершённый год.
        fc_anchors = fc_anchors[:1]

    out: list[tuple[date, float]] = []
    for anchor in fc_anchors:
        pairs = buckets[anchor]
        vals = [v for _, v in pairs]
        if method == "sum":
            val = round(sum(vals), 4)
        elif method == "avg":
            val = round(sum(vals) / len(vals), 4)
        else:
            _last_d, last_v = max(pairs, key=lambda p: p[0])
            val = round(last_v, 4)
        out.append((anchor, val))
    return out


def _allows_period_sum_anchor_revision(derived_cfg: dict, operation: str | None) -> bool:
    """period_sum на квартал/год якорится на конец bucket'а.

    Для текущего незавершённого квартала/года факт уже лежит на том же якоре
    (partial YTD). Прогноз источника пересчитывает полный bucket — точку нужно
    обновить, иначе `d > last_actual` отфильтрует единственный годовой прогноз.
    """
    if derived_cfg.get("monthly_tail_extrapolate"):
        return True
    if operation != "pipeline":
        return False
    return any(op == "period_sum" for op, _ in (derived_cfg.get("pipeline") or []))


def _select_forecast_points(
    derived_full: list[tuple[date, float]],
    dates: Sequence[date],
    values: Sequence[float],
    *,
    operation: str | None,
    derived_cfg: dict,
) -> list[tuple[date, float]]:
    if not dates:
        return derived_full

    last_actual_date = max(dates)
    actual_by_date = {
        d: float(v) for d, v in zip(dates, values) if v is not None
    }
    revise_anchors = _allows_period_sum_anchor_revision(derived_cfg, operation)

    selected: list[tuple[date, float]] = []
    for d, v in derived_full:
        if d > last_actual_date:
            selected.append((d, v))
        elif revise_anchors and d in actual_by_date:
            if abs(float(v) - actual_by_date[d]) > 1e-4:
                selected.append((d, v))
    return selected


def derived_from_source_strategy(
    dates: Sequence[date],
    values: Sequence[float],
    ctx: StrategyContext,
) -> Sequence[StrategyOutput]:
    """Derived forecast — нужен `_runtime_helpers.source_actuals_and_forecast` в ctx.cfg.

    Pipeline собирает источник перед вызовом этой стратегии и кладёт его в:
        ctx.cfg["_source_data"] = list[(date, float)]   # actuals + forecast вместе
    Если данных нет — возвращаем пустой результат (pipeline почистит старый прогноз).
    """
    derived_cfg = ctx.cfg.get("derived_forecast") or {}
    operation = derived_cfg.get("operation")
    model_name = str(derived_cfg.get("model_name", f"{ctx.indicator_code}-Derived"))

    source_data = ctx.cfg.get("_source_data") or []
    if not source_data:
        logger.warning(
            "derived_from_source: %s — no _source_data in ctx; pipeline must inject it",
            ctx.indicator_code,
        )
        return []

    last_actual_date = max(dates) if len(dates) else None

    if operation == "yoy_quarterly":
        derived_full = _yoy(source_data, step=4)
    elif operation == "yoy_monthly":
        derived_full = _yoy(source_data, step=12)
    elif operation == "qoq":
        derived_full = _qoq(source_data)
    elif operation == "real_from_yoy":
        # gdp-real[t] = gdp-real[t-1year] * (1 + gdp-yoy[t] / 100), при условии что
        # source_data == список (date, yoy_value).
        # ВАЖНО: исторические real-точки не перезаписываем (они factual),
        # только заполняем будущие даты, используя факт за tn-1y как базу.
        derived_full = []
        sorted_pairs = sorted(source_data)
        actual_real: dict[date, float] = {d: v for d, v in zip(dates, values)}
        running: dict[date, float] = dict(actual_real)
        for d, yoy_v in sorted_pairs:
            if d in actual_real or yoy_v is None:
                continue
            year_ago = date(d.year - 1, d.month, 1)
            base = running.get(year_ago)
            if base is None:
                continue
            new_val = base * (1.0 + yoy_v / 100.0)
            running[d] = new_val
            derived_full.append((d, new_val))
    elif operation == "december_to_december":
        # 1 точка на год: годовая инфляция = ∏ месячных индексов / 100 - 1.
        # Используем ту же чистую функцию, что и CalculationEngine для actuals,
        # — гарантирует, что forecast и historic считаются одинаково.
        derived_full = ops_december_to_december(list(source_data))
    elif operation == "annual_sum":
        # 1 точка на год: годовая сумма по календарному году. Для квартального
        # источника нужны 4 кв., для месячного — 12 мес. Год с неполным числом
        # точек игнорируется.
        derived_full = ops_annual_sum(list(source_data))
    elif operation == "cpi_mom_yoy":
        derived_full = ops_cpi_mom_yoy(list(source_data))
    elif operation == "cpi_mom_qoq":
        derived_full = ops_cpi_mom_qoq(list(source_data))
    elif operation == "weekly_inflation_by_calendar_month":
        derived_full = ops_weekly_inflation_by_calendar_month(list(source_data))
    elif operation == "weekly_mtd_in_calendar_month":
        derived_full = ops_weekly_mtd_in_calendar_month(list(source_data))
    elif operation == "subtract":
        # Тождество из двух источников: Y[t] = source1[t] − source2[t].
        # Для trade-balance = exports − imports. Источники переданы как
        # (факт+прогноз) обоих рядов; считаем по пересечению дат.
        source_data_2 = ctx.cfg.get("_source_data_2") or []
        s2 = {d: v for d, v in source_data_2}
        derived_full = [
            (d, v - s2[d]) for d, v in sorted(source_data) if d in s2
        ]
    elif operation == "pipeline":
        pipeline_steps = derived_cfg.get("pipeline") or []
        bucket_spec = _pipeline_bucket_spec(pipeline_steps)
        if derived_cfg.get("monthly_tail_extrapolate") and bucket_spec:
            method, gran = bucket_spec
            actual_src = set(ctx.cfg.get("_source_actual_dates") or ())
            derived_full = _forecast_from_monthly_tail(
                list(source_data), actual_src, gran, method,
            )
        else:
            derived_full = _run_pipeline(list(source_data), derived_cfg)
    else:
        logger.error("derived_from_source: unknown operation '%s'", operation)
        return []

    future_only = _select_forecast_points(
        derived_full,
        dates,
        values,
        operation=operation,
        derived_cfg=derived_cfg,
    )

    if not future_only:
        logger.info(
            "derived_from_source: %s → 0 future points (op=%s)",
            ctx.indicator_code, operation,
        )
        return []

    points = [
        ForecastPoint(date=d, value=round(float(v), 4), lower_bound=None, upper_bound=None)
        for d, v in future_only
    ]
    result = ForecastResult(model_name=model_name, aic=None, bic=None, points=points)
    logger.info(
        "derived_from_source: %s → %d points (op=%s, model=%s)",
        ctx.indicator_code, len(points), operation, model_name,
    )
    return [StrategyOutput(result=result)]
