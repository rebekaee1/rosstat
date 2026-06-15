"""Pure operations for derived indicators.

Each function here is **pure** (no I/O, no DB, no Redis): same input → same output.
The storage seam lives in `calculation_engine.py` (`DerivedSpec` + executor).
See `docs/adr/0001-derived-indicators-engine-shape.md` for why this split exists,
and `CONTEXT.md::Derived indicator` for the canonical list of ops + counts.
When adding a new op: register it in this file, then add a `DerivedSpec` row to
`calculation_engine.DERIVED_SPECS`, then update CONTEXT.md ops count + ADR-0001
"Subsequent additions" section.

Currently there are 10 pure ops behind 29 derived indicators (1 op orphaned —
`annual_inflation`, replaced by `december_to_december` and `annual_sum` in 2026-05).

- quarterly_index      — multiplicative quarterly aggregate of monthly CPI-style indices.
- annual_inflation     — rolling 12-month CPI inflation (orphaned in 2026-05, kept for reference).
- yoy                  — year-over-year growth in percent vs the same date one year prior.
- yoy_abs              — year-over-year absolute change in source units (для balances со знаком).
- qoq                  — change vs the previous data point in the series, in percent.
- qoq_abs              — change vs the previous data point in source units (ставки/сальдо со знаком).
- mom_abs              — month-over-month absolute change (п.п. для ставок/долей).
- period_over_period_abs — «к прошлому периоду» в абс. выражении на агрег. bucket'е.
- rebase_to_first      — индекс «первая точка = 100» (годовые счётные уровни).
- quarterly_avg        — average of three monthly values per quarter (e.g. unemployment).
- rolling_avg          — trailing N-window average over a monthly series (e.g. annual unemployment).
- wages_real           — real wage index (2 sources: nominal wages × cumulative CPI).
- december_to_december — Dec-to-Dec growth; replaces annual_inflation in CPI annual specs.
- annual_sum           — sum of N quarterly/monthly values per year (gdp-nominal-annual).

Each function takes lists of `(date, value)` tuples and returns a list of
`(date, value)` tuples. They contain no async, no DB access, no upserts. All
persistence and orchestration happens one layer up in `calculation_engine`.

Rounding precision matches the legacy ad-hoc functions in calculation_engine
exactly so that bit-identical values land in the database after the refactor.
"""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

DatePoint = tuple[date, float]
Series = list[DatePoint]


# --- Quarterly aggregations of monthly CPI-style indices ---------------------

_QUARTER_END_MONTHS: tuple[int, ...] = (3, 6, 9, 12)


def quarterly_index(monthly: Series) -> Series:
    """Multiplicative quarterly index from a monthly CPI-style series.

    For each calendar year, consume three monthly indices `m1, m2, m3` (the
    months within a quarter) and produce one quarterly index attached to the
    first day of the third month::

        q = (m1 / 100) * (m2 / 100) * (m3 / 100) * 100

    Result is rounded to 4 decimals. Quarters with any missing month are skipped.
    """
    by_ym = {(d.year, d.month): float(v) for d, v in monthly}
    points: Series = []
    for y in sorted({yr for yr, _ in by_ym}):
        for qe in _QUARTER_END_MONTHS:
            v1 = by_ym.get((y, qe - 2))
            v2 = by_ym.get((y, qe - 1))
            v3 = by_ym.get((y, qe))
            if v1 is None or v2 is None or v3 is None:
                continue
            q = (v1 / 100.0) * (v2 / 100.0) * (v3 / 100.0) * 100.0
            points.append((date(y, qe, 1), round(q, 4)))
    return points


def annual_inflation(monthly: Series) -> Series:
    """Trailing 12-month CPI inflation as a percent change.

    For each (year, month) in the monthly series, look back 12 consecutive
    months (current month + 11 prior). If all 12 are present, multiply them
    (each divided by 100), then convert to a percent::

        inflation = product(p / 100) * 100 - 100

    Result is rounded to 4 decimals. Months with fewer than 12 trailing values
    available are skipped.
    """
    by_ym = {(d.year, d.month): float(v) for d, v in monthly}
    sorted_keys = sorted(by_ym.keys())
    points: Series = []
    for y, m in sorted_keys:
        trailing: list[float] = []
        for offset in range(12):
            mo = m - offset
            yr = y
            if mo <= 0:
                mo += 12
                yr -= 1
            v = by_ym.get((yr, mo))
            if v is not None:
                trailing.append(v)
        if len(trailing) != 12:
            continue
        product = 1.0
        for v in trailing:
            product *= v / 100.0
        annual = product * 100.0 - 100.0
        points.append((date(y, m, 1), round(annual, 4)))
    return points


def december_to_december(monthly: Series) -> Series:
    """Calendar-year December-to-December annual inflation.

    Auto-detects two source formats and uses the right formula for each:

    - **Month-over-month index** (values cluster around 100, как у Росстат CPI):
      chained product. ``inflation_Y = (∏_{m=Jan..Dec} p_m / 100) * 100 − 100``.
      Requires all 12 months for year Y.
    - **Price level index** (values 50…500+, как у Росстат PPI 2010=100):
      December year-over-December ratio. ``inflation_Y = (p_Dec_Y / p_Dec_{Y−1}) * 100 − 100``.
      Requires Dec_Y and Dec_{Y−1} present.

    Detection: median of all input values. ``95 ≤ median ≤ 115`` → MoM% format,
    иначе — level. В обоих случаях результат анкорится на ``date(Y, 1, 1)``,
    одна точка на завершённый год, и матчит конвенцию ЦБ/Росстата по годовой
    инфляции «декабрь к декабрю».
    """
    by_ym = {(d.year, d.month): float(v) for d, v in monthly}
    if not by_ym:
        return []

    sorted_values = sorted(by_ym.values())
    median = sorted_values[len(sorted_values) // 2]
    is_mom_percent = 95.0 <= median <= 115.0

    points: Series = []
    if is_mom_percent:
        for y in sorted({yr for yr, _ in by_ym}):
            if not all((y, m) in by_ym for m in range(1, 13)):
                continue
            product = 1.0
            for m in range(1, 13):
                product *= by_ym[(y, m)] / 100.0
            annual = product * 100.0 - 100.0
            points.append((date(y, 1, 1), round(annual, 4)))
    else:
        for y in sorted({yr for yr, _ in by_ym}):
            cur = by_ym.get((y, 12))
            prev = by_ym.get((y - 1, 12))
            if cur is None or prev is None or prev == 0:
                continue
            annual = (cur / prev) * 100.0 - 100.0
            points.append((date(y, 1, 1), round(annual, 4)))
    return points


def annual_sum(series: Series) -> Series:
    """Calendar-year sum of a quarterly or monthly series.

    Group `series` by year. For each year `Y`, decide the "complete year"
    threshold from the source rhythm:

      - If any year has 12 unique months → expect 12 monthly points/year.
      - Else if any year has 4 unique months → expect 4 quarterly points/year.
      - Else expect ≥1 point (annual or sparse — emit what we have).

    Only years matching the expected count emit a point. The result is
    anchored at `date(Y, 1, 1)` — one point per complete calendar year.
    Used for ВВП-real (sum of 4 quarters in constant prices) and similar
    additive series. Rounded to 2 decimals.
    """
    by_year: dict[int, list[float]] = {}
    months_per_year: dict[int, set[int]] = {}
    for d, v in series:
        by_year.setdefault(d.year, []).append(float(v))
        months_per_year.setdefault(d.year, set()).add(d.month)

    if not by_year:
        return []

    max_unique_months = max(len(months) for months in months_per_year.values())
    if max_unique_months >= 12:
        expected = 12
    elif max_unique_months >= 4:
        expected = 4
    else:
        expected = 1

    points: Series = []
    for y in sorted(by_year):
        values = by_year[y]
        if len(values) < expected:
            continue
        points.append((date(y, 1, 1), round(sum(values), 2)))
    return points


# --- Generic delta operations -----------------------------------------------


def yoy(series: Series) -> Series:
    """Year-over-year growth: (val_t / val_{t-1y} - 1) * 100, rounded to 2 decimals.

    The match against the prior year uses `date(d.year - 1, d.month, d.day)`,
    so the input series must use stable day-of-month markers (e.g. always the
    1st of each period). Skips dates whose `t-1y` partner is missing or zero.
    """
    by_date = {d: float(v) for d, v in series}
    sorted_dates = sorted(by_date.keys())
    points: Series = []
    for d in sorted_dates:
        try:
            prev_d = date(d.year - 1, d.month, d.day)
        except ValueError:
            continue
        denom = by_date.get(prev_d)
        if denom is None or denom == 0:
            continue
        growth = (by_date[d] / denom - 1.0) * 100.0
        points.append((d, round(growth, 2)))
    return points


def qoq(series: Series) -> Series:
    """Change vs previous data point: (val_t / val_{t-1} - 1) * 100, rounded to 2 decimals.

    "Previous data point" means the one preceding `t` in date order, regardless
    of how the underlying source spaces them. Used for quarterly series where
    successive points are consecutive quarters.
    """
    sorted_pts = sorted(((d, float(v)) for d, v in series), key=lambda p: p[0])
    points: Series = []
    for i in range(1, len(sorted_pts)):
        d_cur, v_cur = sorted_pts[i]
        _, v_prev = sorted_pts[i - 1]
        if v_prev == 0:
            continue
        growth = (v_cur / v_prev - 1.0) * 100.0
        points.append((d_cur, round(growth, 2)))
    return points


def yoy_abs(series: Series) -> Series:
    """Year-over-year ABSOLUTE change: val_t − val_{t−1y}, in source units.

    Назначение — рядов, где **процент YoY бессмыслен**, потому что база может
    быть нулём или менять знак (trade-balance, current-account-balance).
    `yoy()` для таких индикаторов даёт визуально дикий ряд: деление на
    маленькое или отрицательное знаменатель плюёт в график тысячи процентов.

    Единица сохраняется (млн $, млн ₽, etc.) — это **разница** в тех же
    единицах. Округление 2 знака, как у `yoy()`.

    Алгоритм — тот же date(year-1, month, day) лукап, что и у yoy(), чтобы
    в одном году разные ряды могли матчиться.
    """
    by_date = {d: float(v) for d, v in series}
    points: Series = []
    for d in sorted(by_date.keys()):
        try:
            prev_d = date(d.year - 1, d.month, d.day)
        except ValueError:
            continue
        prev = by_date.get(prev_d)
        if prev is None:
            continue
        delta = by_date[d] - prev
        points.append((d, round(delta, 2)))
    return points


# --- Generic period bucketing (avg / last / sum) -----------------------------
#
# Эти ops — backend-эквивалент фронтового `applyAggregateTransform` (среднее)
# и `lastOfBucket` (на конец периода). Каждый разночастотный результат заводится
# отдельным sibling-индикатором с верной `frequency` (ADR-0006). Ось «гранулярность»
# (неделя/месяц/квартал/год) выражается параметром `granularity`; ось «метод»
# (last / avg / sum) — параметром `method`.
#
# Якорь даты для каждого bucket выбран так, чтобы фронтовый formatDate корректно
# вычислял подпись: month -> date(Y, M, 1); quarter -> date(Y, {3,6,9,12}, 1);
# year -> date(Y, 1, 1); week -> фактическая дата последнего наблюдения недели
# (ISO-неделя). Это совпадает с конвенцией существующих ops (quarterly_index,
# annual_sum) и с тем, как фронт читает квартал/год из даты точки.

_GRANULARITIES: tuple[str, ...] = ("week", "month", "quarter", "year")


def _bucket_anchor(d: date, granularity: str) -> tuple[tuple, date | None]:
    """Return (bucket_key, anchor_date | None). None anchor => use last obs date."""
    if granularity == "week":
        iso = d.isocalendar()
        return (iso[0], iso[1]), None
    if granularity == "month":
        return (d.year, d.month), date(d.year, d.month, 1)
    if granularity == "quarter":
        q = (d.month - 1) // 3 + 1
        return (d.year, q), date(d.year, q * 3, 1)
    if granularity == "year":
        return (d.year,), date(d.year, 1, 1)
    raise ValueError(f"unknown granularity: {granularity!r}")


def _expected_subperiods(series: Series, granularity: str) -> int | None:
    """Сколько уникальных месяцев в ПОЛНОМ bucket'е, исходя из ритма источника.

    Нужно, чтобы не показывать незавершённый текущий год/квартал: напр.
    «Инвестиции за 2026» из одного квартала рисуются обвалом, годовая сумма
    бюджета из 4 месяцев выглядит как профицит. Пока период не набрал ожидаемое
    число суб-периодов — это не точка факта, а «огрызок», и её надо отбросить
    (на её месте показывается прогнозная точка, см. derived_from_source).

    Частота источника определяется по МЕДИАННОМУ интервалу между соседними
    точками, а не по «макс. числу месяцев в каком-то году». Иначе weekly-ряд с
    короткой историей (самый полный год < 12 месяцев) ошибочно принимался за
    квартальный и пропускал неполный текущий год (баг international-reserves,
    2026-06). Медиана устойчива к длине истории и пропускам.

    Ритм → ожидаемое число уникальных месяцев:
    - суб-месячный/месячный (медиана ≤ 45 дн): year → 12, quarter → 3;
    - квартальный (≤ 100 дн): year → 4, quarter → None (квартал не дробится);
    - годовой/редкий (> 100 дн): None (полноту не проверяем).
    """
    if granularity not in ("year", "quarter"):
        return None
    dates = sorted({d for d, _ in series})
    if len(dates) < 2:
        return None
    gaps = sorted((dates[i + 1] - dates[i]).days for i in range(len(dates) - 1))
    median_gap = gaps[len(gaps) // 2]
    if median_gap <= 45:  # daily/weekly/monthly
        return 12 if granularity == "year" else 3
    if median_gap <= 100:  # quarterly
        return 4 if granularity == "year" else None
    return None  # annual/sparse — без фильтра полноты


def _aggregate(series: Series, granularity: str, method: str) -> Series:
    """Bucket `series` by `granularity` and reduce each bucket with `method`.

    method ∈ {"last", "avg", "sum"}. Buckets keep source order; the result is
    one point per bucket, rounded to 4 decimals.

    Незавершённые year/quarter bucket'ы (меньше ожидаемого числа суб-периодов,
    см. `_expected_subperiods`) отбрасываются — не показываем «огрызок» текущего
    периода как точку факта.
    """
    if granularity not in _GRANULARITIES:
        raise ValueError(f"unknown granularity: {granularity!r}")
    if method not in ("last", "avg", "sum"):
        raise ValueError(f"unknown method: {method!r}")

    expected = _expected_subperiods(series, granularity)

    buckets: dict[tuple, dict] = {}
    order: list[tuple] = []
    for d, v in sorted(series, key=lambda p: p[0]):
        key, anchor = _bucket_anchor(d, granularity)
        fv = float(v)
        if key not in buckets:
            buckets[key] = {
                "anchor": anchor, "last_date": d, "last": fv,
                "vals": [fv], "months": {d.month},
            }
            order.append(key)
        else:
            b = buckets[key]
            b["vals"].append(fv)
            b["months"].add(d.month)
            if d >= b["last_date"]:
                b["last_date"] = d
                b["last"] = fv

    out: Series = []
    last_idx = len(order) - 1
    for idx, key in enumerate(order):
        b = buckets[key]
        # Незавершённым «огрызком» может быть только ТЕКУЩИЙ (последний по времени)
        # период — он ещё наполняется. Прошлые/частичный первый bucket (начало
        # короткой истории источника, напр. international-reserves с ~март 2025)
        # сохраняем: иначе весь годовой ряд схлопывается в пустой, а движок
        # `calculation_engine._execute` не прунит до пустого (safety guard), и
        # устаревшая точка-огрызок навсегда остаётся в БД.
        # Полнота считается по числу уникальных под-периодов (месяцев), а не сырых
        # точек: у дневного источника «сырых» точек в году ~250, сравнение с 12 было
        # бы всегда истинным. См. `_expected_subperiods` — он тоже по месяцам.
        if idx == last_idx and expected is not None and len(b["months"]) < expected:
            continue
        anchor = b["anchor"] if b["anchor"] is not None else b["last_date"]
        if method == "last":
            val = b["last"]
        elif method == "avg":
            val = sum(b["vals"]) / len(b["vals"])
        else:  # sum
            val = sum(b["vals"])
        out.append((anchor, round(val, 4)))
    return out


def period_last(series: Series, granularity: str) -> Series:
    """Level on the end of each period (last observation in the bucket)."""
    return _aggregate(series, granularity, "last")


def period_avg(series: Series, granularity: str) -> Series:
    """Arithmetic mean of each period's observations (Средняя за период)."""
    return _aggregate(series, granularity, "avg")


def period_sum(series: Series, granularity: str) -> Series:
    """Sum of each period's observations (За период — для потоков, напр. бюджет)."""
    return _aggregate(series, granularity, "sum")


def mom(monthly: Series) -> Series:
    """Month-over-month change in percent vs the immediately preceding calendar
    month: (val_m / val_{m-1} - 1) * 100, rounded to 2 decimals.

    Explicit (year, month-1) lookup (not just "previous point") so a gap in the
    monthly series never silently compares across a missing month.
    """
    by_ym = {(d.year, d.month): float(v) for d, v in monthly}
    points: Series = []
    for (y, m) in sorted(by_ym):
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        prev = by_ym.get((py, pm))
        if prev is None or prev == 0:
            continue
        points.append((date(y, m, 1), round((by_ym[(y, m)] / prev - 1.0) * 100.0, 2)))
    return points


def period_over_period(series: Series, granularity: str, method: str = "last") -> Series:
    """«К прошлому периоду» on an aggregated bucket: aggregate `series` to
    `granularity` (last for stocks/levels, sum for flows), then take percent
    change vs the previous bucket. Used e.g. for quarter-over-quarter of a
    monthly stock (Кв/Кв).
    """
    return qoq(_aggregate(series, granularity, method))


def mom_abs(monthly: Series) -> Series:
    """Month-over-month ABSOLUTE change vs the preceding calendar month:
    val_m − val_{m−1}, in source units (п.п. для ставок/долей).

    Аналог `mom()`, но разница, а не процент: для ставок/долей «изменение на
    X п.п. за месяц» осмысленнее, чем «процент от процента». Тот же явный
    (year, month−1) лукап, что и `mom()`, чтобы пропуск месяца не сравнивался
    через дыру. Округление 2 знака.
    """
    by_ym = {(d.year, d.month): float(v) for d, v in monthly}
    points: Series = []
    for (y, m) in sorted(by_ym):
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        prev = by_ym.get((py, pm))
        if prev is None:
            continue
        points.append((date(y, m, 1), round(by_ym[(y, m)] - prev, 2)))
    return points


def qoq_abs(series: Series) -> Series:
    """Change vs previous data point in ABSOLUTE terms: val_t − val_{t−1},
    in source units. Версия `qoq()` для рядов со знаком (сальдо/баланс), где
    процент к предыдущему кварталу бессмыслен из-за смены знака базы.
    """
    sorted_pts = sorted(((d, float(v)) for d, v in series), key=lambda p: p[0])
    points: Series = []
    for i in range(1, len(sorted_pts)):
        d_cur, v_cur = sorted_pts[i]
        _, v_prev = sorted_pts[i - 1]
        points.append((d_cur, round(v_cur - v_prev, 2)))
    return points


def period_over_period_abs(series: Series, granularity: str, method: str = "last") -> Series:
    """«К прошлому периоду» в АБСОЛЮТНОМ выражении: агрегируем `series` к
    `granularity` (last для уровней/ставок), затем разница к предыдущему
    bucket'у. Для дневных/месячных ставок Кв/Кв в п.п. вместо процента.
    """
    return qoq_abs(_aggregate(series, granularity, method))


# --- Monthly rolling aggregates ----------------------------------------------


def quarterly_avg(monthly: Series) -> Series:
    """Quarterly average of a monthly series: simple mean of 3 months per quarter.

    Attaches the result to the first day of the third month of the quarter.
    Rounded to 1 decimal. Quarters missing any month are skipped.
    """
    by_ym = {(d.year, d.month): float(v) for d, v in monthly}
    points: Series = []
    for y in sorted({yr for yr, _ in by_ym}):
        for qe in _QUARTER_END_MONTHS:
            v1 = by_ym.get((y, qe - 2))
            v2 = by_ym.get((y, qe - 1))
            v3 = by_ym.get((y, qe))
            if v1 is None or v2 is None or v3 is None:
                continue
            avg = (v1 + v2 + v3) / 3.0
            points.append((date(y, qe, 1), round(avg, 1)))
    return points


def rolling_avg(monthly: Series, window: int = 12) -> Series:
    """Trailing-window average of a monthly series.

    For each (year, month) in the input, mean of the current month plus
    `window - 1` previous months (so window=12 ⇒ rolling annual average).
    Months without a full window of values are skipped. Rounded to 1 decimal.
    """
    by_ym = {(d.year, d.month): float(v) for d, v in monthly}
    sorted_keys = sorted(by_ym.keys())
    points: Series = []
    for y, m in sorted_keys:
        trailing: list[float] = []
        for offset in range(window):
            mo = m - offset
            yr = y
            if mo <= 0:
                mo += 12
                yr -= 1
            v = by_ym.get((yr, mo))
            if v is not None:
                trailing.append(v)
        if len(trailing) != window:
            continue
        avg = sum(trailing) / window
        points.append((date(y, m, 1), round(avg, 1)))
    return points


# --- Real wages (special: 2 sources) -----------------------------------------


def wages_real(wages_nominal: Series, cpi_monthly: Series) -> Series:
    """Real wage index from nominal wages and monthly CPI.

    Method:
      1. Build cumulative CPI index by chaining each month's `cpi/100` factor.
      2. Anchor on the first available wage month: take that wage and CPI as base.
      3. For each wage month with a matching CPI index value::

             real_t = (wage_t / wage_base) / (cpi_t / cpi_base) * 100

         (real index, base = 100). Rounded to 2 decimals.

    Returns an empty list if either base is zero or sources are too short.
    """
    if len(wages_nominal) < 2 or len(cpi_monthly) < 12:
        return []

    wages_by_ym = {(d.year, d.month): float(v) for d, v in wages_nominal}
    cpi_by_ym = {(d.year, d.month): float(v) for d, v in cpi_monthly}

    # Cumulative CPI: chain monthly indices in chronological order.
    cpi_index: dict[tuple[int, int], float] = {}
    cumulative = 1.0
    for ym, v in sorted(cpi_by_ym.items()):
        cumulative *= v / 100.0
        cpi_index[ym] = cumulative

    sorted_wages = sorted(wages_by_ym.items())
    base_ym, base_wage = sorted_wages[0]
    base_cpi = cpi_index.get(base_ym)

    if not base_wage:
        logger.warning("No base wage available for wages_real (base_wage=%s)", base_wage)
        return []
    if not base_cpi:
        logger.warning("No base CPI for wages_real anchor month %s", base_ym)
        return []

    points: Series = []
    for (y, m), wage in sorted_wages:
        ci = cpi_index.get((y, m))
        if ci is None:
            continue
        real = (wage / base_wage) / (ci / base_cpi) * 100.0
        points.append((date(y, m, 1), round(real, 2)))
    return points


# --- Rebase to index (base year average = 100) -------------------------------


def rebase_to_index(series: Series, base_year: int) -> Series:
    """Convert an absolute-level series (e.g. wages in rubles, prices in $)
    into an index where the average value of `base_year` equals 100.

    Method::

        base = mean(values in base_year)
        out[t] = value[t] / base * 100

    Used by C2: «зарплата в индексной форме (2010=100)» — превращает
    номинальные рубли в безразмерный индекс, удобный для сопоставления с
    индексом цен на жильё и расчёта доступности (C1).

    Returns empty list if base year has no data or base is zero.
    """
    if not series:
        return []
    base_values = [float(v) for d, v in series if d.year == base_year]
    if not base_values:
        return []
    base = sum(base_values) / len(base_values)
    if base == 0:
        return []
    return [(d, round(float(v) / base * 100.0, 2)) for d, v in series]


def rebase_to_index_with_base(
    series: Series, base_series: Series, base_year: int,
) -> Series:
    """Index a level series to `base_year=100`, but read the base value from a
    SECOND series.

    Нужно, когда сам ряд не содержит точек базового года (помесячная зарплата
    начинается позже базового года), а базовое среднее доступно в смежном
    годовом ряде того же показателя. Метод::

        base = mean(value in base_series where year == base_year)
        out[t] = series[t] / base * 100        для всех t в `series`

    Возвращает [] если базовый год отсутствует в `base_series` или база = 0.
    """
    if not series or not base_series:
        return []
    base_values = [float(v) for d, v in base_series if d.year == base_year]
    if not base_values:
        return []
    base = sum(base_values) / len(base_values)
    if base == 0:
        return []
    return [(d, round(float(v) / base * 100.0, 2)) for d, v in series]


def rebase_to_first(series: Series) -> Series:
    """Index where the FIRST available observation = 100: out[t] = v[t]/v0*100.

    Для годовых счётных рядов (население, число рождений/смертей, персонал
    НИР), у которых нет более мелкой гранулярности: «индекс» показывает
    относительную динамику от первой доступной точки — единственная осмысленная
    дополнительная ось для годовых уровней. Безразмерный (база = 100).
    """
    pts = sorted(((d, float(v)) for d, v in series), key=lambda p: p[0])
    if not pts or pts[0][1] == 0:
        return []
    base = pts[0][1]
    return [(d, round(v / base * 100.0, 2)) for d, v in pts]


# --- Affordability index (special: 2 sources) -------------------------------


def affordability_index(price_index: Series, wage_index: Series) -> Series:
    """Housing affordability index: how much wage growth lags or outpaces
    housing-price growth, expressed as an index with the same base as the
    inputs (typically 100 = base year average).

    Method::

        affordability[t] = wage_index[t] / price_index[t] * 100

    Interpretation: values above 100 mean wages grew faster than housing
    prices since the base year — relative affordability improved. Values
    below 100 mean housing prices outpaced wages — affordability worsened.

    Both inputs must be rebased to the same base year (use
    `rebase_to_index` first, or feed an already-rebased Rosstat index like
    `housing-price-primary` whose base = 1994).

    Returns empty list if no overlapping dates or zero-divider.
    """
    if not price_index or not wage_index:
        return []
    price_by_ym = {(d.year, d.month): float(v) for d, v in price_index}
    wage_by_ym = {(d.year, d.month): float(v) for d, v in wage_index}

    points: Series = []
    for ym, p in sorted(price_by_ym.items()):
        if p == 0:
            continue
        w = wage_by_ym.get(ym)
        if w is None:
            continue
        points.append((date(ym[0], ym[1], 1), round(w / p * 100.0, 2)))
    return points


def affordability_index_monthly(price_index: Series, wage_index: Series) -> Series:
    """Monthly housing affordability index with quarterly-price forward-fill.

    `wage_index` — помесячный индекс зарплаты; `price_index` — квартальный
    индекс цен на жильё (обе серии в одной базе, обычно базовый год = 100).
    Для каждого месяца зарплаты берём индекс цен последнего известного квартала
    (forward-fill квартального уровня на месяцы внутри квартала)::

        affordability[m] = wage_index[m] / price_index_ffill[m] * 100

    Ряд получается помесячным (по датам зарплаты), начиная с первого месяца,
    для которого уже известен хотя бы один квартал цен. Значения выше 100
    означают, что с базового года зарплаты росли быстрее цен на жильё
    (доступность улучшилась), ниже 100 — наоборот.

    Зарплата предварительно сглаживается скользящей средней за 12 месяцев:
    помесячный индекс зарплаты скачет от сезонных премий (декабрь), из-за чего
    сырой индекс доступности «дёргался» — разовая премия на один месяц делала
    жильё резко «доступнее». Содержательно квартиру покупают не на разовую
    премию, а на устойчивый годовой доход, поэтому берём среднюю зарплату за
    последние 12 месяцев. Квартальный индекс цен уже гладкий — его не сглаживаем.

    Возвращает [] при пустых входах или отсутствии перекрытия (нет квартала
    цен раньше первого месяца зарплаты).
    """
    if not price_index or not wage_index:
        return []
    wage_index = rolling_avg(wage_index, window=12)
    if not wage_index:
        return []
    prices = sorted(((d, float(v)) for d, v in price_index), key=lambda p: p[0])
    wages = sorted(((d, float(v)) for d, v in wage_index), key=lambda p: p[0])

    points: Series = []
    pi = 0
    cur_price: float | None = None
    for wd, w in wages:
        # Сдвигаем указатель цен до последнего квартала с датой <= месяца зарплаты.
        while pi < len(prices) and prices[pi][0] <= wd:
            cur_price = prices[pi][1]
            pi += 1
        if cur_price is None or cur_price == 0:
            continue
        points.append((date(wd.year, wd.month, 1), round(w / cur_price * 100.0, 2)))
    return points


# --- CPI view modes (composition × URL mode) ---------------------------------


def cumulative_level_from_mom(monthly: Series) -> Series:
    """Chain monthly MoM CPI indices (~100) to a level index (first month = 100).

    История не обрезается: ряд начинается с первой доступной месячной точки
    (для ИПЦ Росстата — 1991 год; правка созвона 2026-06-11). Выбор базы не
    влияет на производные отношения (yoy/qoq) — они инвариантны к масштабу.
    Округление здесь не применяется: уровни 90-х << 1, и round(…, 2) схлопнул
    бы их в 0.0, ломая последующие qoq/yoy. Потребители округляют сами.
    """
    pts = sorted(((d, float(v)) for d, v in monthly), key=lambda p: p[0])
    if not pts:
        return []
    points: Series = [(pts[0][0], 100.0)]
    acc = 100.0
    for i in range(1, len(pts)):
        acc *= pts[i][1] / 100.0
        points.append((pts[i][0], acc))
    return points


def cpi_mom_yoy(monthly: Series) -> Series:
    """YoY % vs the same month one year ago on chained CPI levels (full history)."""
    return yoy(cumulative_level_from_mom(monthly))


def cpi_mom_qoq(monthly: Series) -> Series:
    """QoQ %: end-of-quarter level vs previous quarter-end (chained from monthly MoM)."""
    levels = cumulative_level_from_mom(monthly)
    quarter_ends = [(d, v) for d, v in levels if d.month in _QUARTER_END_MONTHS]
    return qoq(quarter_ends)


def weekly_inflation_by_calendar_month(weekly: Series) -> Series:
    """Compound weekly CPI indices within each calendar month → one % growth point.

    Anchored to the last weekly observation in the month. Used for «Рост за период /
    Месячная» (distinct from official monthly м/м).
    """
    by_month: dict[tuple[int, int], list[tuple[date, float]]] = {}
    for d, v in weekly:
        by_month.setdefault((d.year, d.month), []).append((d, float(v)))
    points: Series = []
    for ym in sorted(by_month):
        weeks = sorted(by_month[ym], key=lambda p: p[0])
        product = 1.0
        for _, wv in weeks:
            product *= wv / 100.0
        growth = product * 100.0 - 100.0
        points.append((weeks[-1][0], round(growth, 4)))
    return points


def weekly_mtd_in_calendar_month(weekly: Series) -> Series:
    """Running MTD % within each calendar month at every weekly date.

    For week t in month M: (∏ weekly_indexᵢ/100 for all weeks in M up to t) × 100 − 100.
    Distinct from step-weekly (н/н = only vs previous week). Used for «Рост за период /
    Недельная».
    """
    by_month: dict[tuple[int, int], list[tuple[date, float]]] = {}
    for d, v in weekly:
        by_month.setdefault((d.year, d.month), []).append((d, float(v)))
    points: Series = []
    for ym in sorted(by_month):
        weeks = sorted(by_month[ym], key=lambda p: p[0])
        product = 1.0
        for d, wv in weeks:
            product *= wv / 100.0
            growth = product * 100.0 - 100.0
            points.append((d, round(growth, 4)))
    return points
