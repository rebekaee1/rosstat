import { useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import { HelpCircle } from 'lucide-react';
import { resolveDateFormat } from '../lib/format';
import { track, events } from '../lib/track';
import { useDownloadAccess } from '../lib/useDownloadAccess';
import { exportNodeToPng } from '../lib/chartImage';
import IndicatorChart from './IndicatorChart';
import ChartSectionSkeleton from './ChartSectionSkeleton';
import { chartSeriesForViewMode } from '../lib/chartSeriesForViewMode';
import { useLocale, useT } from '../i18n';
import { resolveChartTitle } from '../i18n/resolveViewModeCopy';
import { forecastTooltipLabel, levelTooltipLabel } from '../i18n/chartTooltipLabels';
import { useCountryComparison } from '../lib/useCountryComparison';
import CountryComparePanel, { ScaleNudge } from './CountryComparePicker';
import ChartDownloadMenu from './ChartDownloadMenu';
import ForecastControl from './ForecastControl';
import EmbedLink from './EmbedLink';
import ApiInterestLink from './ApiInterestLink';
import Button from './Button';
import '../styles/indicator-russia.css';
import '../styles/x2-indicator.css';
import '../styles/y2-indicator.css';
import '../styles/w6e-indicator.css';
import '../styles/z4-indicator.css';
import { localizeSource } from '../i18n/viewModeLabels';

/* ── Mode-зависимые подписи ──
   chartMode принимает значения: 'cpi' (default для всех некоммодити-индикаторов),
   'quarterly', 'annual', 'weekly', 'inflation' (только для CPI семьи).
   Для не-CPI индикаторов важен `indicator.frequency` — он задаёт ритм ряда
   (daily/weekly/monthly/quarterly/annual). Прогноз идёт в том же ритме —
   подписи tooltip/легенды/заголовка отражают это. */

function rangePresetFor({ chartMode, indicator }) {
  /* Mode-driven для CPI семьи (annual mode → 10y/25y/all). */
  if (chartMode === 'annual') return 'annual';
  if (chartMode === 'quarterly' || chartMode === 'qoq') return 'quarterly';
  if (chartMode === 'weekly') return 'weekly';
  if (chartMode === 'yoy' || chartMode === 'period-weekly' || chartMode === 'period-monthly') return 'default';
  // Накопленный индекс CPI — длинная история (2000+), показываем 5y/10y/25y/all.
  if (chartMode === 'index') return 'quarterly';
  /* Frequency-driven для остальных индикаторов. */
  const freq = indicator?.frequency;
  if (freq === 'quarterly') return 'quarterly';
  if (freq === 'annual') return 'annual';
  if (freq === 'weekly') return 'weekly';
  if (freq === 'daily') return 'daily';
  return 'default';
}

function ruYears(n) {
  const mod100 = Math.abs(n) % 100;
  const mod10 = n % 10;
  if (mod100 > 10 && mod100 < 20) return `${n} лет`;
  if (mod10 === 1) return `${n} год`;
  if (mod10 >= 2 && mod10 <= 4) return `${n} года`;
  return `${n} лет`;
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
  isHousingFamily,
  isPpiFamily,
  isCbrTermSliceFamily,
  isUnemploymentFamily,
  chartLoading,

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

  displayForecastData,
  quarterlyForecastData,
  annualForecastResp,
  yoyForecastData,
  qoqForecastData,
  momForecastData,
  periodMonthlyForecastData,
  periodWeeklyForecastData,

  forecastEnabled,
  showForecast,
  onToggleForecast,

  onChartData,
  onFullData,
  onRangeChange,
  emptyHint,

  onDownloadCsv,
  onDownloadExcel,
  worldCompare = null,
  onNeedCompatibleMode = null,
}) {
  const { locale } = useLocale();
  const t = useT();
  const { blocked: downloadBlocked, isAuthed: downloadAuthed, historyYears } = useDownloadAccess();
  const guestYearsLabel = locale === 'en'
    ? t('calc.years', { n: historyYears })
    : ruYears(historyYears);
  const guestHistoryHint = !downloadAuthed && !downloadBlocked && historyYears > 0
    ? t('download.guestHistory', { years: guestYearsLabel })
    : null;
  const chartRef = useRef(null);
  const cpiChartTitle = resolveChartTitle(locale, {
    chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
    isCbrTermSliceFamily, isUnemploymentFamily,
    indicator, safeViewMode,
  });
  // Скачивание графика картинкой. Единое правило по всему сайту (пересмотрено
  // 2026-07-08, созвон «На правки 13»): гость → гейт регистрации (скачать
  // нельзя вообще); зарегистрированный → чистый PNG текущего вида (режим +
  // прогноз как на экране), без водяного знака — до 2026-07-08 знак стоял и
  // у зарегистрированных тоже, решение развёрнуто владельцем.
  const handleDownloadImage = async () => {
    if (!downloadAuthed) {
      track(events.CHART_IMAGE_BLOCKED, { indicator: code, indicatorCategory: indicator?.category });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    const ok = await exportNodeToPng(chartRef.current, {
      filename: `${code}_${safeViewMode || chartMode || 'chart'}.png`,
      watermark: false,
      // Фирменная рамка: знак, название, источник и адрес сайта вокруг снимка графика.
      frame: {
        title: indicator?.name || '',
        subtitle: '',
        source: indicator?.source
          ? t('z4.png.source', { source: localizeSource(indicator.source, locale) })
          : '',
      },
    }).catch(() => false);
    if (ok) {
      track(events.CHART_IMAGE_DOWNLOAD, {
        indicator: code,
        indicatorCategory: indicator?.category,
        mode: safeViewMode || chartMode,
        forecast: forecastEnabled && showForecast,
      });
    }
  };
  const chartCpiData = chartSeriesForViewMode({
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
  const chartUnit = chartMode === 'index' ? 'индекс' : ((isPpiFamily || isHousingFamily) && chartMode !== 'index' ? '%' : (indicator?.unit || '%'));
  const compareConcept = worldCompare?.concept;
  const currentCompareMode = safeViewMode || chartMode;
  const compareCompatible = !compareConcept
    || (compareConcept.compatible_modes || []).includes(currentCompareMode);
  const compareBasePoints = (chartMode === 'inflation' && inflationResp?.actuals?.length)
    ? inflationResp.actuals
    : chartCpiData;
  const comparison = useCountryComparison({
    surface: 'russia',
    peers: worldCompare?.peers,
    conceptSlug: compareConcept?.slug,
    countrySlug: 'russia',
    dataPoints: compareBasePoints,
    unit: chartUnit,
    title: cpiChartTitle,
    peerMode: compareConcept?.peer_mode,
    peerValueScale: compareConcept?.peer_value_scale,
  });
  const handleToggleCompare = (id) => {
    if (!compareCompatible && compareConcept?.default_mode) {
      onNeedCompatibleMode?.(compareConcept.default_mode);
    }
    comparison.toggleComparison(id);
  };
  const overlayActive = compareCompatible && comparison.loadedComparisonSeries.length > 0;
  // «Динамика (=100)»: график сам ставит базу на начало выбранного периода, поэтому ему идут исходные ряды.
  const windowRebase = overlayActive && comparison.windowRebase;
  const chartDataPoints = overlayActive && !windowRebase ? comparison.displayedDataPoints : compareBasePoints;
  const chartComparisonSeries = compareCompatible
    ? (windowRebase ? comparison.loadedComparisonSeries : comparison.displayedComparisonSeries)
    : [];
  const chartDisplayUnit = windowRebase ? comparison.windowRebaseUnit : (overlayActive ? comparison.displayedUnit : chartUnit);
  const chartDisplayTitle = windowRebase
    ? t('w6e.compare.captionIndex')
    : (overlayActive ? comparison.displayedTitle : cpiChartTitle);
  const compareHint = compareConcept && !compareCompatible
    ? t('world.chart.compareNeedsMode')
    : null;

  // Недельный режим — без прогноза (созвон 2026-06-11).
  const forecastData = chartMode === 'quarterly' ? quarterlyForecastData
    : chartMode === 'annual' ? annualForecastResp
      : chartMode === 'weekly' ? null
        : chartMode === 'yoy' ? yoyForecastData
          : chartMode === 'qoq' ? qoqForecastData
            : chartMode === 'mom' ? momForecastData
              : chartMode === 'period-weekly' ? periodWeeklyForecastData
                : chartMode === 'period-monthly' ? periodMonthlyForecastData
                  : displayForecastData;
  // Overlay переводит IndicatorChart в mode=cpi (cpiData + forecast.values).
  // У инфляции г/г без overlay идёт inflation.forecast (~6–10 %), а
  // displayForecastData — индекс ИПЦ (~100). Смешивать нельзя.
  const inflationForecastValues = inflationResp?.forecast;
  const overlayForecastData = useMemo(() => {
    if (overlayActive && chartMode === 'inflation' && inflationForecastValues?.length) {
      return { forecast: { values: inflationForecastValues } };
    }
    return forecastData;
  }, [overlayActive, chartMode, inflationForecastValues, forecastData]);

  const handleForecastToggle = () => {
    if (!forecastEnabled) return;
    onToggleForecast();
    track(events.FORECAST_TOGGLE, {
      show: !showForecast,
      indicator: code,
      indicatorCategory: indicator?.category,
    });
  };

  return (
    <section id="chart" data-block="chart" className="fe-chart-section z4-chart-section" aria-busy={chartLoading ? true : undefined}>
      <div className="fe-chart-head z4-chart-head">
        <h2 className="fe-chart-head__title">{t('indicator.chartDynamicsLabel')}</h2>

        <div className="fe-chart-actions">
          <ForecastControl
            enabled={forecastEnabled}
            on={forecastEnabled && showForecast}
            onToggle={handleForecastToggle}
            reason={t('chart.forecastUnavailable')}
          />
          <ChartDownloadMenu
            dataBlocked={downloadBlocked}
            imageBlocked={!downloadAuthed}
            hint={guestHistoryHint}
            onCsv={onDownloadCsv}
            onExcel={onDownloadExcel}
            onPng={handleDownloadImage}
          />
          <EmbedLink code={code} />
          <ApiInterestLink source="indicator" code={code} />
          <Link
            to="/methodology"
            title={t('chart.methodologyHint')}
            onClick={() => track(events.METHODOLOGY_CLICK, { indicator: code, indicatorCategory: indicator?.category })}
            className="fe-help-link"
          >
            <HelpCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{t('x2.chart.methodLink')}</span>
          </Link>
        </div>
        {guestHistoryHint && !downloadBlocked && (
          <p className="fe-chart-hint">{guestHistoryHint}</p>
        )}
      </div>

      <div id="compare" className="z4-compare scroll-mt-24">
        <CountryComparePanel
          pickerOptions={comparison.pickerOptions}
          activeComparisonIds={comparison.activeComparisonIds}
          selectedComparisons={comparison.selectedComparisons}
          comparisonQueries={comparison.comparisonQueries}
          comparisonScale={comparison.comparisonScale}
          onToggle={handleToggleCompare}
          onOpen={() => comparison.setComparisonPickerActive(true)}
          onScale={comparison.setComparisonScale}
          conceptSlug={compareConcept?.slug}
          countrySlug="russia"
          compareCodes={comparison.compareCodes}
          rebased={compareCompatible ? comparison.rebased : null}
          loadedComparisonSeries={compareCompatible ? comparison.loadedComparisonSeries : []}
          hint={compareHint}
          baseLabel={t('nav.russia')}
        />
      </div>
      <div className="z4-chart-wrap">
      <ScaleNudge
        show={compareCompatible && comparison.scaleMismatch && comparison.comparisonScale === 'values'}
        onScale={comparison.setComparisonScale}
      />

      {chartLoading ? (
        <ChartSectionSkeleton />
      ) : (
        <div ref={chartRef} className="relative w-full min-w-0 max-w-full overflow-hidden rounded-[1.5rem]">
          <IndicatorChart
            key={`${indicator?.code}-${chartMode}`}
            mode={
              overlayActive
              || isUnemploymentFamily
              || ['quarterly', 'annual', 'weekly', 'index', 'yoy', 'qoq', 'mom', 'real',
                'period-weekly', 'period-monthly'].includes(chartMode)
              || (isCbrTermSliceFamily && chartMode === 'level')
                ? 'cpi'
                : chartMode
            }
            inflation={inflationResp}
            cpiData={chartDataPoints}
            forecastData={overlayForecastData}
            showForecast={forecastEnabled && showForecast && !(overlayActive && comparison.rebased)}
            onChartData={onChartData}
            onFullData={onFullData}
            onRangeChange={onRangeChange}
            referenceLineY={(isPriceCategory || isHousingFamily || isPpiFamily) && chartMode !== 'index' ? 0 : null}
            cpiChartTitle={chartDisplayTitle}
            levelTooltipLabel={levelTooltipLabel(t, {
              chartMode, isPriceCategory, isHousingFamily, isPpiFamily,
              isCbrTermSliceFamily,
              indicator,
            })}
            forecastTooltipLabel={forecastTooltipLabel(t, { chartMode, indicator })}
            emptyHint={emptyHint}
            dateFormat={resolveDateFormat({ chartMode, frequency: indicator?.frequency, safeViewMode })}
            unit={chartDisplayUnit}
            rangePreset={rangePresetFor({ chartMode, indicator })}
            chartMode={chartMode}
            indicatorCode={code}
            indicatorCategory={indicator?.category}
            numericTooltipOnly={chartComparisonSeries.length > 0}
            actualSeriesLabel={chartComparisonSeries.length ? t('nav.russia') : ''}
            comparisonSeries={chartComparisonSeries.length ? chartComparisonSeries : null}
            rebaseVisible={windowRebase}
          />
        </div>
      )}
      </div>

    </section>
  );
}
