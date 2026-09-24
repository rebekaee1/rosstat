/**
 * Слияние фактического ряда и прогноза для графика.
 *
 * Прогнозы содержат якорную точку на дате последнего опубликованного факта.
 * Совпадение дат само по себе не означает неполный период: замещение такого
 * факта скрывало II квартал инвестиций и других рядов за пунктиром прогноза.
 * Неполный bucket можно замещать только по явному сигналу вызывающего кода.
 */
export function mergeActualForecastChartSeries(
  points,
  forecastValues,
  { showForecast = true, bridgeLine = true, replacePartialActual = false } = {},
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
    if (replacePartialActual && fcByDate.has(p.date) && String(p.date) === lastActualDate
      && Math.abs(Number(fcByDate.get(p.date)) - Number(p.value)) > 1e-4) {
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
