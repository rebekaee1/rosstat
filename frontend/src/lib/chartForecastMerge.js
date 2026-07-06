/**
 * Слияние фактического ряда и прогноза для графика.
 *
 * Collision-policy (В-15, CTO-аудит 2026-07-06) — явное правило вместо
 * безусловного замещения:
 *   - На ПОСЛЕДНЕЙ дате факта прогноз побеждает: для квартальных/годовых
 *     агрегатов из monthly_auto «факт» на якоре неполного bucket'а — это
 *     заниженный partial YTD, показывать его как «Факт» нельзя.
 *   - На всех БОЛЕЕ РАННИХ датах факт побеждает: история никогда не
 *     маскируется прогнозом, даже если бэкенд прислал прогнозную точку
 *     на уже закрытый период.
 */
export function mergeActualForecastChartSeries(
  points,
  forecastValues,
  { showForecast = true, bridgeLine = true } = {},
) {
  const series = Array.isArray(points) ? points : [];
  const fcValues = Array.isArray(forecastValues) ? forecastValues : [];

  if (!series.length) return [];

  if (!showForecast || !fcValues.length) {
    return series.map((p) => ({ date: p.date, actual: p.value }));
  }

  const fcByDate = new Map(fcValues.map((fv) => [fv.date, fv.value]));
  const actualDates = new Set(series.map((p) => p.date));
  const lastActualDate = series.reduce(
    (max, p) => (String(p.date) > max ? String(p.date) : max), '',
  );

  const merged = series.map((p) => {
    // Прогноз замещает факт только на последней (partial-bucket) дате.
    if (fcByDate.has(p.date) && String(p.date) === lastActualDate) {
      return { date: p.date, forecast: fcByDate.get(p.date) };
    }
    return { date: p.date, actual: p.value };
  });

  for (const fv of fcValues) {
    if (!actualDates.has(fv.date)) {
      merged.push({ date: fv.date, forecast: fv.value });
    }
  }

  merged.sort((a, b) => String(a.date).localeCompare(String(b.date)));

  if (bridgeLine) {
    const lastActualIdx = merged.findLastIndex((row) => row.actual != null);
    if (lastActualIdx >= 0) {
      const hasForecastAfter = merged
        .slice(lastActualIdx + 1)
        .some((row) => row.forecast != null);
      if (hasForecastAfter) {
        merged[lastActualIdx] = {
          ...merged[lastActualIdx],
          forecast: merged[lastActualIdx].actual,
        };
      }
    }
  }

  return merged;
}
