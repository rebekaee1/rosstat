import { useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  Terminal, Download, Lock, Image as ImageIcon, HelpCircle,
} from 'lucide-react';
import { resolveDateFormat, cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useDownloadAccess } from '../lib/useDownloadAccess';
import { exportNodeToPng } from '../lib/chartImage';
import IndicatorChart from './IndicatorChart';
import { ChartSkeleton } from './Skeleton';
import { worldChartTitle, worldRangePreset } from '../lib/worldViewModes';
import { useLocale, useT } from '../i18n';
import { useCountryComparison } from '../lib/useCountryComparison';
import CountryComparePanel from './CountryComparePicker';

/**
 * Секция графика мировой карточки.
 * Переиспользует IndicatorChart; прогноз — только после проверки на
 * исторических данных и по явному переключателю пользователя.
 */
function DownloadButton({ label, onDownload, blocked, hint }) {
  const t = useT();
  const handleClick = () => {
    // Let the export API enforce the guest limit: excel.js then retains the
    // exact payload for completion after auth, instead of losing the intent.
    onDownload?.();
  };
  const tooltip = blocked ? t('download.dataBlocked') : hint;
  return (
    <div className="relative group/dl">
      <button
        type="button"
        onClick={handleClick}
        aria-disabled={blocked}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors text-xs font-mono uppercase tracking-wider',
          blocked
            ? 'border-border-subtle/60 text-text-tertiary/50 cursor-pointer'
            : 'border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30',
        )}
        title={blocked ? t('download.dataBlocked') : t('download.downloadLabel', { label })}
      >
        {blocked ? <Lock className="w-3.5 h-3.5" /> : <Download className="w-3.5 h-3.5" />}
        {label}
      </button>
      {tooltip && (
        <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-[11px] normal-case tracking-normal text-text-secondary whitespace-nowrap opacity-0 group-hover/dl:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
          {tooltip}
        </div>
      )}
    </div>
  );
}

function ImageButton({ onDownload, authed }) {
  const t = useT();
  const tooltip = authed
    ? t('download.chartPng')
    : t('download.chartBlocked');
  return (
    <div className="relative group/img" data-no-export="true">
      <button
        type="button"
        onClick={onDownload}
        aria-disabled={!authed}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors text-xs font-mono uppercase tracking-wider',
          authed
            ? 'border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30'
            : 'border-border-subtle/60 text-text-tertiary/50 cursor-pointer',
        )}
        title={tooltip}
      >
        {authed ? <ImageIcon className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
        PNG
      </button>
      <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-[11px] normal-case tracking-normal text-text-secondary whitespace-nowrap opacity-0 group-hover/img:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
        {tooltip}
      </div>
    </div>
  );
}

export default function WorldChartSection({
  code,
  indicator,
  modeMeta,
  dataPoints,
  forecastData = [],
  forecastEnabled = false,
  forecastGateStatus = null,
  forecastDerivedFrom = null,
  showForecast = false,
  onToggleForecast,
  chartLoading,
  emptyHint,
  onFullData,
  onDownloadCsv,
  onDownloadExcel,
  frequency,
  aggregated = false,
  aggregation = null,
  unit: unitOverride,
  country,
  conceptSlug,
  comparisonPeers,
}) {
  const { blocked: downloadBlocked, isAuthed: downloadAuthed } = useDownloadAccess();
  const { locale } = useLocale();
  const t = useT();
  const chartRef = useRef(null);
  const unit = unitOverride || modeMeta?.unit || indicator?.unit || '';
  const activeFreq = frequency || modeMeta?.freq || indicator?.frequency;
  const title = worldChartTitle(indicator, modeMeta, activeFreq, locale);
  const {
    pickerOptions,
    activeComparisonIds,
    selectedComparisons,
    comparisonQueries,
    comparisonScale,
    setComparisonScale,
    toggleComparison,
    setComparisonPickerActive,
    compareCodes,
    rebased,
    loadedComparisonSeries,
    displayedDataPoints,
    displayedComparisonSeries,
    displayedUnit,
    displayedTitle,
  } = useCountryComparison({
    surface: 'world',
    peers: comparisonPeers,
    conceptSlug,
    countrySlug: country?.slug,
    dataPoints,
    unit,
    title,
    modeMeta,
  });
  const effectiveShowForecast = forecastEnabled && showForecast && !rebased;
  // IndicatorChart ждёт российскую оболочку {forecast: {values}}, а world API
  // отдаёт массив точек — без обёртки пунктир на графике не появляется.
  const chartForecastPayload = useMemo(
    () => ({
      forecast: { values: Array.isArray(forecastData) ? forecastData : [] },
    }),
    [forecastData],
  );
  const highFreqNative = activeFreq === 'weekly' || activeFreq === 'daily'
    || aggregation?.source_frequency === 'weekly'
    || aggregation?.source_frequency === 'daily';
  const forecastNote = !forecastEnabled
    ? (highFreqNative ? t('world.chart.forecastHighFreq') : t('world.chart.forecastGate'))
    : forecastDerivedFrom
      ? t('world.chart.forecastDerived')
      : (forecastGateStatus === 'advisory'
        ? t('world.chart.forecastAdvisory')
        : t('world.chart.forecastPassed'));

  const handleDownloadImage = async () => {
    if (!downloadAuthed) {
      track(events.CHART_IMAGE_BLOCKED, { indicator: code, world: true });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    const ok = await exportNodeToPng(chartRef.current, {
      filename: `${code}_${modeMeta?.id || 'level'}.png`,
      watermark: false,
    }).catch(() => false);
    if (ok) {
      track(events.CHART_IMAGE_DOWNLOAD, {
        indicator: code,
        mode: modeMeta?.id,
        world: true,
      });
    }
  };

  return (
    <section id="chart" data-block="chart" className="mb-10 sm:mb-16 scroll-mt-24">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-3 sm:mb-6 sm:pb-4">
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <Terminal className="h-4 w-4 shrink-0 text-champagne" />
          <span className="min-w-0 break-words text-xs leading-snug text-text-secondary line-clamp-3 sm:font-mono sm:text-[11px] sm:uppercase sm:tracking-widest sm:text-text-tertiary sm:line-clamp-2">
            {title}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:gap-3" data-no-export="true">
          <div className="relative group/help">
            <Link
              to="/methodology"
              aria-label={t('chart.methodologyAria')}
              onClick={() => track(events.METHODOLOGY_CLICK, {
                indicator: code,
                indicatorCategory: indicator?.category,
                world: true,
              })}
              className="text-text-tertiary transition-colors hover:text-champagne"
            >
              <HelpCircle className="h-4 w-4" />
            </Link>
            <div className="pointer-events-none absolute right-0 top-full z-50 mt-2 whitespace-nowrap rounded-xl border border-border-subtle bg-obsidian px-3 py-2 text-xs text-text-secondary opacity-0 shadow-xl transition-opacity group-hover/help:opacity-100">
              {t('chart.methodologyHint')}
            </div>
          </div>
          <div className="relative group/forecast">
            <label className={cn(
              'flex select-none items-center gap-2.5',
              forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-45',
            )}>
              <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
                {t('common.forecast')}
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={effectiveShowForecast}
                aria-label={t('chart.forecastAria')}
                disabled={!forecastEnabled}
                onClick={onToggleForecast}
                className={cn(
                  'relative h-5 w-10 rounded-full border transition-colors',
                  effectiveShowForecast
                    ? 'border-champagne/30 bg-champagne/30'
                    : 'border-border-subtle bg-obsidian-lighter',
                )}
              >
                <span className={cn(
                  'absolute left-[2px] top-[2px] h-3.5 w-3.5 rounded-full transition-transform',
                  effectiveShowForecast
                    ? 'translate-x-5 bg-champagne'
                    : 'translate-x-0 bg-text-tertiary',
                )}
                />
              </button>
            </label>
            {!forecastEnabled && (
              <div className="pointer-events-none absolute right-0 top-full z-50 mt-2 w-72 rounded-xl border border-border-subtle bg-obsidian px-3 py-2 text-[11px] leading-4 text-text-secondary opacity-0 shadow-xl transition-opacity group-hover/forecast:opacity-100">
                {forecastNote}
              </div>
            )}
          </div>
          <DownloadButton label="CSV" onDownload={onDownloadCsv} blocked={downloadBlocked} />
          <DownloadButton label="Excel" onDownload={onDownloadExcel} blocked={downloadBlocked} />
          <ImageButton onDownload={handleDownloadImage} authed={downloadAuthed} />
        </div>
      </div>

      <CountryComparePanel
        pickerOptions={pickerOptions}
        activeComparisonIds={activeComparisonIds}
        selectedComparisons={selectedComparisons}
        comparisonQueries={comparisonQueries}
        comparisonScale={comparisonScale}
        onToggle={toggleComparison}
        onOpen={() => setComparisonPickerActive(true)}
        onScale={setComparisonScale}
        conceptSlug={conceptSlug}
        countrySlug={country?.slug}
        compareCodes={compareCodes}
        rebased={rebased}
        loadedComparisonSeries={loadedComparisonSeries}
      />

      {comparisonQueries.some((query) => query.isError) && (
        <p className="mb-3 text-[12px] text-text-secondary">
          {t('world.chart.modePartial')}
        </p>
      )}

      {aggregated && (
        <p className="mb-3 text-[12px] text-text-secondary">
          {aggregation?.source_frequency === 'weekly'
            ? t('world.mode.hint.derivedWeekly')
            : aggregation?.source_frequency === 'daily'
              ? t('world.mode.hint.derivedDaily')
              : aggregation?.policy === 'sum'
                ? t('world.mode.hint.sum')
                : aggregation?.policy === 'last'
                  ? t('world.mode.hint.last')
                  : aggregation?.policy === 'mean'
                    ? t('world.mode.hint.mean')
                    : t('world.chart.aggregated', {
                      source: indicator?.source || t('world.chart.sourceFallback'),
                    })}
        </p>
      )}

      <p className="mb-3 text-[12px] leading-5 text-text-secondary">
        {forecastNote}
        {' '}
        <Link to="/methodology" className="text-champagne hover:underline">
          {t('common.methodology')}
        </Link>
      </p>

      {showForecast && forecastEnabled && !rebased && (
        <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-tertiary">
          <span>
            {t('world.chart.forecastStarts')}
          </span>
          <Link to="/methodology" className="text-champagne hover:underline">
            {t('common.methodology')}
          </Link>
        </div>
      )}
      {showForecast && forecastEnabled && !chartLoading && forecastData.length === 0 && (
        <p className="mb-3 text-[11px] text-text-tertiary">
          {t('world.chart.forecastIncomplete')}
        </p>
      )}
      {showForecast && rebased && (
        <p className="mb-3 text-[11px] text-text-tertiary">
          {t('world.chart.forecastHiddenRebase')}
        </p>
      )}

      {chartLoading ? (
        <ChartSkeleton />
      ) : (
        <div ref={chartRef} className="relative overflow-hidden rounded-[2rem]">
          <IndicatorChart
            key={`${code}-${modeMeta?.id}-${activeFreq}`}
            mode="cpi"
            cpiData={displayedDataPoints || []}
            forecastData={chartForecastPayload}
            showForecast={effectiveShowForecast}
            onFullData={onFullData}
            cpiChartTitle={displayedTitle}
            levelTooltipLabel={modeMeta?.label || modeMeta?.group || t('chart.tooltip.value')}
            forecastTooltipLabel={t('common.forecast')}
            emptyHint={emptyHint}
            dateFormat={resolveDateFormat({ frequency: activeFreq, chartMode: 'cpi' })}
            unit={displayedUnit}
            rangePreset={worldRangePreset(activeFreq)}
            chartMode={modeMeta?.id || 'level'}
            indicatorCode={code}
            indicatorCategory={indicator?.category}
            referenceLineY={unit === '%' || unit === 'п.п.' ? 0 : null}
            numericTooltipOnly
            actualSeriesLabel={country?.name}
            comparisonSeries={displayedComparisonSeries}
          />
        </div>
      )}
    </section>
  );
}
