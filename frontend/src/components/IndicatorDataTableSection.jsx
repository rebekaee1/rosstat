import DataTable from './DataTable';

import { resolveDateFormat } from '../lib/format';
import { getCpiTableTitle } from '../lib/cpiViewModeContent';
import { getHousingTableTitle } from '../lib/housingViewModeContent';
import { getPpiTableTitle } from '../lib/ppiViewModeContent';
import { getCbrTermSliceTableTitle } from '../lib/cbrTermSliceRateContent';
import { getUnemploymentTableTitle } from '../lib/unemploymentViewModeContent';
import { chartSeriesForViewMode } from '../lib/chartSeriesForViewMode';

function tableTitle({
  chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
  isCbrTermSliceFamily, isUnemploymentFamily,
  indicator, safeViewMode,
}) {
  if (isUnemploymentFamily) {
    return getUnemploymentTableTitle(chartMode);
  }
  if (isPpiFamily) {
    return getPpiTableTitle(chartMode, safeViewMode);
  }
  if (isCbrTermSliceFamily) {
    return getCbrTermSliceTableTitle(chartMode, indicator?.code);
  }
  if (isHousingFamily && indicator?.code) {
    return getHousingTableTitle(chartMode, indicator.code, safeViewMode);
  }
  if (isPriceCategory && indicator?.code) {
    return getCpiTableTitle(chartMode, indicator.code, safeViewMode);
  }
  return `Исторические данные — ${indicator?.name || 'ряд'}`;
}

/**
 * Финальная секция страницы — таблица всех исторических точек выбранного
 * режима с поиском, сортировкой и пагинацией. Заголовок и формат даты
 * подбираются по chartMode.
 */
export default function IndicatorDataTableSection({
  indicator,
  chartMode,
  safeViewMode,
  isPriceCategory,
  isHousingFamily,
  isPpiFamily,
  isCbrTermSliceFamily,
  isUnemploymentFamily,
  inflationResp,
  dataPoints,
  momDataPoints,
  quarterlyDataPoints,
  annualDataPoints,
  weeklyDataPoints,
  yoyDataPoints,
  qoqDataPoints,
  periodMonthlyDataPoints,
  periodWeeklyDataPoints,
}) {
  const data = chartMode === 'inflation'
    ? (inflationResp?.actuals || [])
    : chartSeriesForViewMode({
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
    });

  return (
    <section>
      <DataTable
        key={`${indicator?.code}-${chartMode}`}
        data={data}
        title={tableTitle({
          chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
          isCbrTermSliceFamily, isUnemploymentFamily,
          indicator, safeViewMode,
        })}
        dateFormat={resolveDateFormat({ chartMode, frequency: indicator?.frequency, safeViewMode })}
        unit={chartMode === 'index' ? 'индекс' : ((isPpiFamily || isHousingFamily) && chartMode !== 'index' ? '%' : (indicator?.unit || '%'))}
      />
    </section>
  );
}
