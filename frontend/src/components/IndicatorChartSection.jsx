import { useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Lock, HelpCircle } from 'lucide-react';
import { resolveDateFormat, cn } from '../lib/format';
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
import CountryComparePanel from './CountryComparePicker';
import Button from './Button';
import '../styles/indicator-russia.css';

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
 * Скачивание данных и картинки одним блоком (ADR-0007 Phase 2).
 * Авторизованный и гость до лимита видят три обычные кнопки: клик сам решает гейт (сервер отдаёт файл либо
 * зовёт войти). Гость, исчерпавший лимит, видит один понятный элемент «Войдите, чтобы скачать» вместо трёх замков.
 */
function DownloadBar({
  blocked, authed, hint, onCsv, onExcel, onPng,
}) {
  const t = useT();
  if (blocked) {
    return (
      <Button
        variant="secondary"
        size="sm"
        onClick={onCsv}
        title={t('download.dataBlocked')}
        data-no-export="true"
      >
        <Lock className="h-3.5 w-3.5" aria-hidden="true" />
        {t('w3.chart.loginToDownload')}
      </Button>
    );
  }
  return (
    <div className="fe-dl" role="group" aria-label={t('w3.chart.download')} title={hint || undefined} data-no-export="true">
      <span className="fe-dl__label" aria-hidden="true">{t('w3.chart.download')}</span>
      <Button variant="secondary" size="sm" onClick={onCsv} aria-label={t('download.downloadLabel', { label: 'CSV' })}>CSV</Button>
      <Button variant="secondary" size="sm" onClick={onExcel} aria-label={t('download.downloadLabel', { label: 'Excel' })}>Excel</Button>
      <Button
        variant="secondary"
        size="sm"
        onClick={onPng}
        title={authed ? t('download.chartPng') : t('download.chartBlocked')}
        aria-label={authed ? t('download.chartPng') : t('download.chartBlocked')}
      >
        PNG
        {authed ? null : <Lock className="h-3 w-3" aria-hidden="true" />}
      </Button>
    </div>
  );
}

/** Переключатель прогноза: подписанная «таблетка», видна и в выключенном состоянии. */
function ForecastSwitch({ enabled, on, onToggle }) {
  const t = useT();
  const active = enabled && on;
  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      aria-disabled={!enabled}
      aria-label={t('chart.forecastAria')}
      title={enabled ? undefined : t('chart.forecastUnavailable')}
      onClick={enabled ? onToggle : undefined}
      className={cn('fe-forecast-switch fe-press', active && 'is-on', !enabled && 'is-unavailable')}
    >
      <span className="fe-forecast-switch__track" aria-hidden="true">
        <span className="fe-forecast-switch__thumb" />
      </span>
      <span>{enabled ? t('common.forecast') : t('w3.chart.forecastNone')}</span>
    </button>
  );
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
  const chartDataPoints = overlayActive ? comparison.displayedDataPoints : compareBasePoints;
  const chartComparisonSeries = compareCompatible ? comparison.displayedComparisonSeries : [];
  const chartDisplayUnit = overlayActive ? comparison.displayedUnit : chartUnit;
  const chartDisplayTitle = overlayActive ? comparison.displayedTitle : cpiChartTitle;
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
    <section id="chart" data-block="chart" className="fe-chart-section" aria-busy={chartLoading ? true : undefined}>
      <div className="fe-chart-head">
        <h2 className="fe-chart-head__title">{t('indicator.chartDynamicsLabel')}</h2>

        <div className="fe-chart-actions">
          <ForecastSwitch enabled={forecastEnabled} on={showForecast} onToggle={handleForecastToggle} />
          <DownloadBar
            blocked={downloadBlocked}
            authed={downloadAuthed}
            hint={guestHistoryHint}
            onCsv={onDownloadCsv}
            onExcel={onDownloadExcel}
            onPng={handleDownloadImage}
          />
          <Link
            to="/methodology"
            aria-label={t('chart.methodologyAria')}
            title={t('chart.methodologyHint')}
            onClick={() => track(events.METHODOLOGY_CLICK, { indicator: code, indicatorCategory: indicator?.category })}
            className="fe-help-link"
          >
            <HelpCircle className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </div>

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
          />
        </div>
      )}
    </section>
  );
}
