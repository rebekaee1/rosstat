"""Pure operations for derived indicators.

Each function here is **pure** (no I/O, no DB, no Redis): same input → same output.
The storage seam lives in `calculation_engine.py` (`DerivedSpec` + executor).
See `docs/adr/0001-derived-indicators-engine-shape.md` for why this split exists,
and `CONTEXT.md::Derived indicator` for the canonical list of ops + counts.
When adding a new op: register it in this file, then add a `DerivedSpec` row to
`calculation_engine.DERIVED_SPECS`, then update CONTEXT.md ops count + ADR-0001
"Subsequent additions" section.

Currently there are 9 pure ops behind 28 derived indicators (1 op orphaned —
`annual_inflation`, replaced by `december_to_december` and `annual_sum` in 2026-05).

- quarterly_index      — multiplicative quarterly aggregate of monthly CPI-style indices.
- annual_inflation     — rolling 12-month CPI inflation (orphaned in 2026-05, kept for reference).
- yoy                  — year-over-year growth in percent vs the same date one year prior.
- qoq                  — change vs the previous data point in the series, in percent.
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
