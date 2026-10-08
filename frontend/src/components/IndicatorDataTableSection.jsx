import { useParams } from 'react-router-dom';
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
  loading = false,
}) {
  const { locale } = useLocale();
  // Страница года (/…/indicator/{code}/2024): таблица показывает только этот год, а не всю историю.
  const { year } = useParams();
  const yearFilter = /^\d{4}$/.test(year || '') ? year : null;
  const allData = chartMode === 'inflation'
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
  const data = yearFilter
    ? (allData || []).filter((row) => String(row.date).startsWith(yearFilter))
    : allData;
  const tableTitle = resolveTableTitle(locale, {
    chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
    isCbrTermSliceFamily, isUnemploymentFamily,
    indicator, safeViewMode,
  });

  return (
    <section>
      <DataTable
        key={`${indicator?.code}-${chartMode}`}
        loading={loading}
        data={data}
        title={yearFilter ? `${tableTitle}, ${yearFilter}` : tableTitle}
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
