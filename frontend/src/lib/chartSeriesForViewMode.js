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

/**
 * Ключ подписи изменения в шапке («к прошлой неделе / месяцу / …») — по частоте точек выбранного режима, а не
 * исходного ряда. Недельный ИПЦ живёт на месячном индикаторе `cpi`: без этой ветки шапка «Н/н» писала «к прошлому
 * месяцу» (находка редактора рассылки 14.11.2026). «Рост за период» по неделям сравнивается с прошлым отчётом, как в
 * плитках телеметрии.
 */
export function heroDeltaSuffixKey({ chartMode, frequency, dailyFromRawSeries = false }) {
  if (chartMode === 'weekly') return 'w3.tele.delta.prevWeek';
  if (chartMode === 'period-weekly') return 'w3.tele.delta.prevReport';
  const freq = chartMode === 'quarterly' || chartMode === 'qoq' ? 'quarterly'
    : chartMode === 'annual' ? 'annual'
      : frequency;
  if (freq === 'quarterly') return 'w3.tele.delta.prevQuarter';
  if (freq === 'daily' && dailyFromRawSeries) return 'c12u.delta.prevDay';
  if (freq === 'weekly') return 'w3.tele.delta.prevWeek';
  if (freq === 'annual') return 'w3.tele.delta.prevYear';
  if (freq === 'monthly') return 'w3.tele.delta.prevMonth';
  return 'w3.tele.delta.prevValue';
}
