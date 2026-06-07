/**
 * Выбор ряда для графика/таблицы по chartMode.
 * Безработица кладёт свой derived-ряд прямо в dataPoints (chartMode может быть
 * 'quarterly'/'annual' для сглаживания), поэтому для неё всегда отдаём dataPoints.
 * Generic config-движок (ставки/валюты/деньги/ВВП/…) рендерится через
 * GenericIndicatorView с chartMode='cpi' — попадает в дефолтную ветку (dataPoints).
 */
export function chartSeriesForViewMode({
  chartMode,
  isUnemploymentFamily,
  dataPoints,
  momDataPoints,
  quarterlyDataPoints,
  annualDataPoints,
  weeklyDataPoints,
  yoyDataPoints,
  qoqDataPoints,
  periodWeeklyDataPoints,
  periodMonthlyDataPoints,
}) {
  if (isUnemploymentFamily) {
    return dataPoints;
  }
  if (chartMode === 'quarterly') return quarterlyDataPoints;
  if (chartMode === 'annual') return annualDataPoints;
  if (chartMode === 'weekly') return weeklyDataPoints;
  if (chartMode === 'yoy') return yoyDataPoints;
  if (chartMode === 'qoq') return qoqDataPoints;
  if (chartMode === 'period-weekly') return periodWeeklyDataPoints;
  if (chartMode === 'period-monthly') return periodMonthlyDataPoints;
  if (chartMode === 'mom') return momDataPoints;
  return dataPoints;
}
