import { Terminal, Download } from 'lucide-react';
import { unitSuffix, cn } from '../lib/format';
import { track, events } from '../lib/track';
import IndicatorChart from './IndicatorChart';
import { ChartSkeleton } from './Skeleton';

/* ── Mode-зависимые подписи ──
   chartMode принимает значения: 'cpi' (default для всех некоммодити-индикаторов),
   'quarterly', 'annual', 'weekly', 'inflation' (только для CPI семьи).
   Для не-CPI индикаторов важен `indicator.frequency` — он задаёт ритм ряда
   (daily/weekly/monthly/quarterly/annual). Прогноз идёт в том же ритме —
   подписи tooltip/легенды/заголовка отражают это. */

const FREQUENCY_LABEL = {
  daily: 'днев.',
  weekly: 'нед.',
  monthly: 'мес.',
  quarterly: 'кв.',
  annual: 'год.',
};

const FREQUENCY_LONG = {
  daily: 'днев.',
  weekly: 'недельная',
  monthly: 'помесячно',
  quarterly: 'квартально',
  annual: 'годовая',
};

function freqLabel(indicator) {
  return FREQUENCY_LABEL[indicator?.frequency] || '';
}

function freqLong(indicator) {
  return FREQUENCY_LONG[indicator?.frequency] || '';
}

function chartTitle({ chartMode, isPriceCategory, indicator }) {
  if (chartMode === 'quarterly') return 'Квартальная инфляция (%)';
  if (chartMode === 'annual') return 'Годовая инфляция (%)';
  if (chartMode === 'weekly') return 'Недельная инфляция (%)';
  if (isPriceCategory) return 'Прирост цен (%, к предыдущему месяцу)';
  const suffix = unitSuffix(indicator?.unit);
  const freq = freqLong(indicator);
  const baseTitle = `${indicator?.name || 'Показатель'}${suffix ? ` (${suffix})` : ''}`;
  return freq ? `${baseTitle} — ${freq}` : baseTitle;
}

function levelTooltipLabel({ chartMode, isPriceCategory, indicator }) {
  if (chartMode === 'quarterly') return 'Кв. инфляция';
  if (chartMode === 'annual') return 'Год. инфляция';
  if (chartMode === 'weekly') return 'Нед. ИПЦ';
  if (isPriceCategory) return 'Прирост';
  const freq = freqLabel(indicator);
  return freq ? `Факт (${freq})` : 'Значение';
}

function forecastTooltipLabel({ chartMode, indicator }) {
  if (chartMode === 'quarterly') return 'Прогноз (кв.)';
  if (chartMode === 'annual') return 'Прогноз (год.)';
  if (chartMode === 'weekly') return 'Прогноз (нед.)';
  if (chartMode === 'inflation') return 'Прогноз (12 мес.)';
  const freq = freqLabel(indicator);
  return freq ? `Прогноз (${freq})` : 'Прогноз';
}

function dateFormatFor({ chartMode, indicator }) {
  if (chartMode === 'quarterly') return 'quarterly';
  if (chartMode === 'annual') return 'annual';
  if (chartMode !== 'inflation' && indicator?.frequency === 'daily') return 'day';
  if (indicator?.frequency === 'quarterly') return 'quarterly';
  if (indicator?.frequency === 'annual') return 'annual';
  if (indicator?.frequency === 'weekly') return 'short';
  return 'full';
}

function rangePresetFor({ chartMode, indicator }) {
  /* Mode-driven для CPI семьи (annual mode → 10y/25y/all). */
  if (chartMode === 'annual') return 'annual';
  if (chartMode === 'quarterly') return 'quarterly';
  if (chartMode === 'weekly') return 'weekly';
  /* Frequency-driven для остальных индикаторов. */
  const freq = indicator?.frequency;
  if (freq === 'quarterly') return 'quarterly';
  if (freq === 'annual') return 'annual';
  if (freq === 'weekly') return 'weekly';
  if (freq === 'daily') return 'daily';
  return 'default';
}

/**
 * Секция «График» страницы индикатора:
 *   тулбар (заголовок + кнопки CSV/Excel + переключатель прогноза) +
 *   сам IndicatorChart с правильными режим-зависимыми пропсами.
 *
 * Таблица данных и таблица прогноза идут отдельными секциями ниже —
 * этот компонент отвечает только за визуализацию ряда.
 */
export default function IndicatorChartSection({
  code,
  indicator,
  chartMode,
  safeViewMode,
  isPriceCategory,
  chartLoading,

  inflationResp,
  dataPoints,
  quarterlyDataPoints,
  annualDataPoints,
  weeklyDataPoints,

  displayForecastData,
  quarterlyForecastData,
  annualForecastResp,

  forecastEnabled,
  showForecast,
  onToggleForecast,

  onChartData,
  onRangeChange,
  emptyHint,

  onDownloadCsv,
  onDownloadExcel,
}) {
  const chartCpiData = chartMode === 'quarterly' ? quarterlyDataPoints
    : chartMode === 'annual' ? annualDataPoints
      : chartMode === 'weekly' ? weeklyDataPoints
        : dataPoints;

  const forecastData = chartMode === 'quarterly' ? quarterlyForecastData
    : chartMode === 'annual' ? annualForecastResp
      : chartMode === 'weekly' ? null
        : displayForecastData;

  const handleForecastToggle = () => {
    if (!forecastEnabled) return;
    onToggleForecast();
    track(events.FORECAST_TOGGLE, {
      show: !showForecast,
      indicator: code,
      indicatorCategory: indicator?.category,
    });
  };

  const handleForecastKeyDown = (e) => {
    if (forecastEnabled && (e.key === ' ' || e.key === 'Enter')) {
      e.preventDefault();
      handleForecastToggle();
    }
  };

  return (
    <section className="mb-16">
      <div className="flex items-center justify-between mb-6 border-b border-border-subtle pb-4 flex-wrap gap-3">
        <div className="flex items-center gap-4">
          <Terminal className="w-4 h-4 text-champagne" />
          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">
            {isPriceCategory ? 'График выбранного режима' : 'Динамика показателя'}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onDownloadCsv}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 transition-colors text-xs font-mono uppercase tracking-wider magnetic-btn"
            title="Скачать CSV"
          >
            <Download className="w-3.5 h-3.5" />
            CSV
          </button>
          <button
            onClick={onDownloadExcel}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 transition-colors text-xs font-mono uppercase tracking-wider magnetic-btn"
            title="Скачать Excel"
          >
            <Download className="w-3.5 h-3.5" />
            Excel
          </button>

          <div className="relative group">
            <label className={cn(
              'flex items-center gap-3 select-none',
              forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-50',
            )}>
              <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary group-hover:text-text-secondary transition-colors">
                Прогноз
              </span>
              <div
                role="switch"
                aria-checked={forecastEnabled && showForecast}
                aria-label="Показать прогноз"
                tabIndex={forecastEnabled ? 0 : -1}
                onClick={handleForecastToggle}
                onKeyDown={handleForecastKeyDown}
                className={cn(
                  'relative w-10 h-5 rounded-full transition-colors duration-300',
                  forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed',
                  forecastEnabled && showForecast
                    ? 'bg-champagne/30'
                    : 'bg-obsidian-lighter border border-border-subtle',
                )}
              >
                <div className={cn(
                  'absolute top-[2px] left-[2px] w-4 h-4 rounded-full transition-transform duration-300',
                  forecastEnabled && showForecast ? 'translate-x-5 bg-champagne' : 'translate-x-0 bg-text-tertiary',
                )} />
              </div>
            </label>
            {!forecastEnabled && (
              <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-xs text-text-secondary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
                {safeViewMode === 'weekly' ? 'Недельный прогноз не публикуется' : 'Прогноз для этого режима недоступен'}
              </div>
            )}
          </div>
        </div>
      </div>

      {chartLoading ? (
        <ChartSkeleton />
      ) : (
        <div className="relative overflow-hidden rounded-[2rem]">
          <IndicatorChart
            key={`${indicator?.code}-${chartMode}`}
            mode={['quarterly', 'annual', 'weekly'].includes(chartMode) ? 'cpi' : chartMode}
            inflation={inflationResp}
            cpiData={chartCpiData}
            forecastData={forecastData}
            showForecast={forecastEnabled && showForecast}
            onChartData={onChartData}
            onRangeChange={onRangeChange}
            referenceLineY={isPriceCategory ? 0 : null}
            cpiChartTitle={chartTitle({ chartMode, isPriceCategory, indicator })}
            levelTooltipLabel={levelTooltipLabel({ chartMode, isPriceCategory, indicator })}
            forecastTooltipLabel={forecastTooltipLabel({ chartMode, indicator })}
            emptyHint={emptyHint}
            dateFormat={dateFormatFor({ chartMode, indicator })}
            unit={indicator?.unit || '%'}
            rangePreset={rangePresetFor({ chartMode, indicator })}
            indicatorCode={code}
            indicatorCategory={indicator?.category}
          />
        </div>
      )}
    </section>
  );
}
