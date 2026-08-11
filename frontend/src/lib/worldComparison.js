export function rebaseWorldComparison(basePoints, series) {
  if (!basePoints?.length || !series.length) return null;
  const seriesMaps = series.map((item) => new Map(
    item.data.map((point) => [point.date, Number(point.value)]),
  ));
  const startPoint = basePoints.find((point) => {
    const baseValue = Number(point.value);
    return Number.isFinite(baseValue)
      && baseValue > 0
      && seriesMaps.every((values) => {
        const value = values.get(point.date);
        return Number.isFinite(value) && value > 0;
      });
  });
  if (!startPoint) return null;
  const startDate = startPoint.date;
  const mapPoints = (points, baseValue) => points
    .filter((point) => point.date >= startDate && Number.isFinite(Number(point.value)))
    .map((point) => ({ ...point, value: (Number(point.value) / baseValue) * 100 }));
  return {
    base: mapPoints(basePoints, Number(startPoint.value)),
    series: series.map((item, index) => ({
      ...item,
      data: mapPoints(item.data, seriesMaps[index].get(startDate)),
    })),
    startDate,
  };
}
