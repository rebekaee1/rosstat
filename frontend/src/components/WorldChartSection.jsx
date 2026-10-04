import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ChevronDown, Download, FileSpreadsheet, FileText, HelpCircle, Image as ImageIcon, LineChart, Lock,
} from 'lucide-react';
import { resolveDateFormat, cn } from '../lib/format';
import '../styles/indicator-russia.css';
import '../styles/x2-indicator.css';
import { track, events } from '../lib/track';
import { useDownloadAccess } from '../lib/useDownloadAccess';
import { exportNodeToPng } from '../lib/chartImage';
import IndicatorChart from './IndicatorChart';
import ChartSectionSkeleton from './ChartSectionSkeleton';
import Button from './Button';
import { indicatorPublicName, worldRangePreset } from '../lib/worldViewModes';
import { useLocale, useT } from '../i18n';
import { useCountryComparison } from '../lib/useCountryComparison';
import CountryComparePanel from './CountryComparePicker';

/**
 * Секция графика мировой карточки.
 * Переиспользует IndicatorChart; прогноз — только после проверки на
 * исторических данных и по явному переключателю пользователя.
 */

const MODE_TITLE_KEY = {
  step: 'w2.mode.step', yoy: 'w2.mode.yoy', yoyabs: 'w2.mode.yoy', index: 'w2.mode.index',
};

/** Заголовок графика для человека: имя показателя и, если это не просто значения, что именно показано. Без «(по годам)» и «Уровень». */
function humanChartTitle(indicator, modeMeta, locale, t) {
  const name = indicatorPublicName(indicator, locale) || (locale === 'en' ? 'Indicator' : 'Показатель');
  const key = MODE_TITLE_KEY[modeMeta?.type];
  return key ? `${name}, ${t(key).toLowerCase()}` : name;
}

/** Одна кнопка «Скачать» вместо трёх слипшихся кнопок с замками. Гостю вход предлагает сам экспорт. */
function DownloadMenu({ onCsv, onExcel, onPng, dataBlocked, imageBlocked }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => { if (!rootRef.current?.contains(event.target)) setOpen(false); };
    const onKey = (event) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);
  const items = [
    { id: 'csv', label: t('w2.dl.csv'), Icon: FileText, run: onCsv, blocked: dataBlocked, hint: dataBlocked ? t('download.dataBlocked') : undefined },
    { id: 'excel', label: t('w2.dl.excel'), Icon: FileSpreadsheet, run: onExcel, blocked: dataBlocked, hint: dataBlocked ? t('download.dataBlocked') : undefined },
    { id: 'png', label: t('w2.dl.png'), Icon: ImageIcon, run: onPng, blocked: imageBlocked, hint: imageBlocked ? t('download.chartBlocked') : t('download.chartPng') },
  ];
  return (
    <div ref={rootRef} className="relative" data-no-export="true">
      <Button
        variant="secondary"
        size="sm"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((value) => !value)}
        className="gap-1.5"
      >
        <Download size={14} aria-hidden="true" />
        {t('w2.dl.title')}
        <ChevronDown size={13} aria-hidden="true" className={cn('transition-transform', open && 'rotate-180')} />
      </Button>
      {open && (
        <div role="menu" className="fe-dialog-panel absolute right-0 top-full z-50 mt-2 min-w-[15rem] rounded-2xl border border-border-subtle bg-surface p-1.5 shadow-2xl">
          {items.map(({ id, label, Icon, run, blocked, hint }) => (
            <button
              key={id}
              type="button"
              role="menuitem"
              title={hint}
              onClick={() => { setOpen(false); run?.(); }}
              className="flex min-h-11 w-full items-center gap-2.5 rounded-xl px-3 text-left text-sm text-text-primary transition-colors hover:bg-obsidian-light"
            >
              <Icon size={16} className="shrink-0 text-text-secondary" aria-hidden="true" />
              <span className="min-w-0 flex-1">{label}</span>
              {blocked && <Lock size={14} className="shrink-0 text-text-tertiary" aria-label={hint} />}
            </button>
          ))}
        </div>
      )}
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
  const title = humanChartTitle(indicator, modeMeta, locale, t);
  const priceIndexLevel = conceptSlug === 'hicp-index'
    && modeMeta?.type === 'level'
    && /индекс|index/i.test(indicator?.unit || '');
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
    <section id="chart" data-block="chart" className="mb-10 sm:mb-16 scroll-mt-24" aria-busy={chartLoading ? true : undefined}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-3 sm:mb-6 sm:pb-4">
        <div className="flex min-w-0 items-center gap-3">
          <LineChart className="h-4 w-4 shrink-0 text-champagne" aria-hidden="true" />
          <h2 className="min-w-0 break-words text-sm font-semibold leading-snug text-text-primary line-clamp-3 sm:text-base">
            {title}
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-3" data-no-export="true">
          <div className="relative group/forecast">
            <label className={cn(
              'flex select-none items-center gap-2.5 text-sm text-text-secondary',
              forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-60',
            )}>
              <span>{t('common.forecast')}</span>
              <button
                type="button"
                role="switch"
                aria-checked={effectiveShowForecast}
                aria-label={t('chart.forecastAria')}
                disabled={!forecastEnabled}
                onClick={onToggleForecast}
                className={cn(
                  'relative h-6 w-11 rounded-full border transition-colors',
                  effectiveShowForecast
                    ? 'border-champagne/30 bg-champagne/30'
                    : 'border-border-subtle bg-obsidian-lighter',
                )}
              >
                <span className={cn(
                  'absolute left-[2px] top-[2px] h-4 w-4 rounded-full transition-transform',
                  effectiveShowForecast
                    ? 'translate-x-5 bg-champagne'
                    : 'translate-x-0 bg-text-tertiary',
                )}
                />
              </button>
            </label>
          </div>
          <Link
            to="/methodology"
            title={t('chart.methodologyHint')}
            onClick={() => track(events.METHODOLOGY_CLICK, {
              indicator: code,
              indicatorCategory: indicator?.category,
              world: true,
            })}
            className="fe-help-link"
          >
            <HelpCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{t('x2.chart.methodLink')}</span>
          </Link>
          <DownloadMenu
            onCsv={onDownloadCsv}
            onExcel={onDownloadExcel}
            onPng={handleDownloadImage}
            dataBlocked={downloadBlocked}
            imageBlocked={!downloadAuthed}
          />
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

      {priceIndexLevel && activeComparisonIds.length === 0 && (
        <p className="mb-4 text-xs text-text-tertiary">
          {t('world.chart.priceIndexBaseHint')}{' '}
          <Link to="/world/rating/hicp-index" className="text-champagne hover:underline">
            {t('world.chart.compareInflationRates')}
          </Link>
        </p>
      )}

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
        <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-tertiary">
          <span>
            {t('world.chart.forecastStarts')}
          </span>
          <Link to="/methodology" className="text-champagne hover:underline">
            {t('common.methodology')}
          </Link>
        </div>
      )}
      {showForecast && forecastEnabled && !chartLoading && forecastData.length === 0 && (
        <p className="mb-3 text-xs text-text-tertiary">
          {t('world.chart.forecastIncomplete')}
        </p>
      )}
      {showForecast && rebased && (
        <p className="mb-3 text-xs text-text-tertiary">
          {t('world.chart.forecastHiddenRebase')}
        </p>
      )}

      {chartLoading ? (
        <ChartSectionSkeleton />
      ) : (
        <div ref={chartRef} className="relative w-full min-w-0 max-w-full overflow-hidden rounded-3xl">
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
