/**
 * Слияние фактического ряда и прогноза для графика.
 *
 * Для квартальных/годовых агрегатов из monthly_auto последний «факт» на якоре
 * неполного bucket'а (partial YTD) совпадает по дате с anchor-revision прогнозом.
 * Если оставить оба — tooltip и линия показывают заниженный partial как «Факт».
 * Прогноз на ту же дату заменяет partial actual.
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

  const merged = series.map((p) => {
    if (fcByDate.has(p.date)) {
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
