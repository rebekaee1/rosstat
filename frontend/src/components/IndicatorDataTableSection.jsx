import DataTable from './DataTable';

function tableTitle({ chartMode, isPriceCategory, indicator }) {
  if (chartMode === 'inflation') return 'Исторические данные — Инфляция 12 мес.';
  if (chartMode === 'quarterly') return 'Исторические данные — Квартальная инфляция';
  if (chartMode === 'annual') return 'Исторические данные — Годовая инфляция';
  if (chartMode === 'weekly') return 'Исторические данные — Недельный ИПЦ';
  if (isPriceCategory) return 'Исторические данные — Прирост цен (%, м/м)';
  return `Исторические данные — ${indicator?.name || 'ряд'}`;
}

function dateFormatFor({ chartMode, indicator }) {
  if (chartMode === 'quarterly') return 'quarterly';
  if (chartMode === 'annual') return 'annual';
  if (chartMode !== 'inflation' && indicator?.frequency === 'daily') return 'day';
  if (indicator?.frequency === 'quarterly') return 'quarterly';
  if (indicator?.frequency === 'annual') return 'annual';
  return 'full';
}

/**
 * Финальная секция страницы — таблица всех исторических точек выбранного
 * режима с поиском, сортировкой и пагинацией. Заголовок и формат даты
 * подбираются по chartMode.
 */
export default function IndicatorDataTableSection({
  indicator,
  chartMode,
  isPriceCategory,
  inflationResp,
  dataPoints,
  quarterlyDataPoints,
  annualDataPoints,
  weeklyDataPoints,
}) {
  const data = chartMode === 'inflation' ? (inflationResp?.actuals || [])
    : chartMode === 'quarterly' ? quarterlyDataPoints
      : chartMode === 'annual' ? annualDataPoints
        : chartMode === 'weekly' ? weeklyDataPoints
          : dataPoints;

  return (
    <section>
      <DataTable
        key={`${indicator?.code}-${chartMode}`}
        data={data}
        title={tableTitle({ chartMode, isPriceCategory, indicator })}
        dateFormat={dateFormatFor({ chartMode, indicator })}
        unit={indicator?.unit || '%'}
      />
    </section>
  );
}
