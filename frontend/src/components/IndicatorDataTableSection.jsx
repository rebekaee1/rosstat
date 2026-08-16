import DataTable from './DataTable';

import { resolveDateFormat, chartValueDigits } from '../lib/format';
import { chartSeriesForViewMode } from '../lib/chartSeriesForViewMode';
import { useLocale } from '../i18n';
import { resolveTableTitle } from '../i18n/resolveViewModeCopy';

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
  const { locale } = useLocale();
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
        title={resolveTableTitle(locale, {
          chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
          isCbrTermSliceFamily, isUnemploymentFamily,
          indicator, safeViewMode,
        })}
        dateFormat={resolveDateFormat({ chartMode, frequency: indicator?.frequency, safeViewMode })}
        unit={chartMode === 'index' ? 'индекс' : ((isPpiFamily || isHousingFamily) && chartMode !== 'index' ? '%' : (indicator?.unit || '%'))}
        valueDigits={chartValueDigits(
          chartMode === 'index' ? 'индекс' : (indicator?.unit || '%'),
          safeViewMode || chartMode,
        )}
      />
    </section>
  );
}
