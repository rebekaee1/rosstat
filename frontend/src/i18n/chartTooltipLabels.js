/**
 * Mode-dependent tooltip labels for IndicatorChart.
 * Copy lives in messages.ru/en; keep helpers pure so tests can pin EN twins.
 */

const FREQ_KEYS = {
  daily: 'chart.freq.daily',
  weekly: 'chart.freq.weekly',
  monthly: 'chart.freq.monthly',
  quarterly: 'chart.freq.quarterly',
  annual: 'chart.freq.annual',
};

export function freqShortLabel(t, frequency) {
  const key = FREQ_KEYS[frequency];
  return key ? t(key) : '';
}

export function levelTooltipLabel(t, {
  chartMode,
  isPriceCategory,
  isHousingFamily,
  isPpiFamily,
  isCbrTermSliceFamily,
  indicator,
} = {}) {
  if (isCbrTermSliceFamily && chartMode === 'level') return t('chart.tooltip.rate');
  if ((isHousingFamily || isPpiFamily) && chartMode === 'index') return t('chart.tooltip.index');
  if (isPpiFamily && chartMode === 'mom') return t('chart.tooltip.mom');
  if (isHousingFamily && chartMode === 'annual') return t('chart.tooltip.yoy');
  if (chartMode === 'quarterly') return t('chart.tooltip.quarterlyInflation');
  if (chartMode === 'annual') return t('chart.tooltip.annualInflation');
  if (chartMode === 'weekly') return t('chart.tooltip.weeklyCpi');
  if (chartMode === 'yoy') return t('chart.tooltip.yoy');
  if (chartMode === 'qoq') return t('chart.tooltip.qoq');
  if (chartMode === 'period-weekly') return t('chart.tooltip.periodWeekly');
  if (chartMode === 'period-monthly') return t('chart.tooltip.periodMonthly');
  if (chartMode === 'index') return t('chart.tooltip.cpi');
  if (isPriceCategory) return t('chart.tooltip.growth');
  const freq = freqShortLabel(t, indicator?.frequency);
  return freq ? t('chart.tooltip.actualFreq', { freq }) : t('chart.tooltip.value');
}

export function forecastTooltipLabel(t, { chartMode, indicator } = {}) {
  if (chartMode === 'quarterly') return t('chart.tooltip.forecastQuarter');
  if (chartMode === 'annual') return t('chart.tooltip.forecastYear');
  if (chartMode === 'weekly') return t('chart.tooltip.forecastWeek');
  if (chartMode === 'inflation') return t('chart.tooltip.forecast12m');
  if (chartMode === 'index') return t('chart.tooltip.forecastCpiMonth');
  const freq = freqShortLabel(t, indicator?.frequency);
  return freq ? t('chart.tooltip.forecastFreq', { freq }) : t('common.forecast');
}
