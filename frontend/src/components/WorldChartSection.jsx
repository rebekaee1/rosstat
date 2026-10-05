import { useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, HelpCircle } from 'lucide-react';
import { resolveDateFormat } from '../lib/format';
import '../styles/indicator-russia.css';
import '../styles/x2-indicator.css';
import '../styles/y2-indicator.css';
import '../styles/w6e-indicator.css';
import { track, events } from '../lib/track';
import { useDownloadAccess } from '../lib/useDownloadAccess';
import { exportNodeToPng } from '../lib/chartImage';
import IndicatorChart from './IndicatorChart';
import ChartSectionSkeleton from './ChartSectionSkeleton';
import ChartDownloadMenu from './ChartDownloadMenu';
import ForecastControl from './ForecastControl';
import { indicatorPublicName, worldRangePreset } from '../lib/worldViewModes';
import { unitKind } from '../lib/indicatorSummary';
import { chartCaption } from '../lib/chartCaption';
import { useLocale, useT } from '../i18n';
import { useCountryComparison } from '../lib/useCountryComparison';
import { countryPath, worldRatingPath } from '../lib/sitePaths';
import { buildChartTitle } from '../lib/z4ChartTitle';
import { localizeSource } from '../i18n/viewModeLabels';
import CountryComparePanel, { ScaleNudge } from './CountryComparePicker';
import '../styles/z4-indicator.css';

/**
 * Секция графика мировой карточки.
 * Переиспользует IndicatorChart; прогноз — только после проверки на
 * исторических данных и по явному переключателю пользователя.
 *
 * Порядок в разметке: действия (прогноз, скачать, картинка), сравнение стран, график. На компьютере секция раскладывается
 * по сетке страницы (`.z4-stage`): график слева, действия, сравнение и плитки справа; на телефоне график идёт первым.
 * Название показателя в заголовке страницы одно; над графиком только то, что именно показано: «ВВП, США: за 10 лет, млрд $».
 */

/** Самое последнее конечное значение ряда по модулю или null. */
function lastAbs(points) {
  for (let i = (points?.length || 0) - 1; i >= 0; i -= 1) {
    const v = Number(points[i]?.value);
    if (Number.isFinite(v)) return Math.abs(v);
  }
  return null;
}

// Постоянный пустой массив: новый [] на каждом рендере заставлял график перерисовываться бесконечно.
const NO_SERIES = [];

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
  const nameForAria = indicatorPublicName(indicator, locale) || (locale === 'en' ? 'Indicator' : 'Показатель');
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
    scaleMismatch,
    loadedComparisonSeries,
    displayedUnit,
    windowRebase,
    windowRebaseUnit,
  } = useCountryComparison({
    surface: 'world',
    peers: comparisonPeers,
    conceptSlug,
    countrySlug: country?.slug,
    dataPoints,
    unit,
    title: nameForAria,
    modeMeta,
  });
  const effectiveShowForecast = forecastEnabled && showForecast && !windowRebase && !rebased;
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
  const noForecastReason = highFreqNative ? t('world.chart.forecastHighFreq') : t('world.chart.forecastGate');
  const forecastNote = forecastDerivedFrom
    ? t('world.chart.forecastDerived')
    : (forecastGateStatus === 'advisory'
      ? t('world.chart.forecastAdvisory')
      : t('world.chart.forecastPassed'));

  // Страны на одной оси, но размеры отличаются вдвое и больше: линия меньшей почти плоская. Предлагаем рост в процентах.
  const suggestPercent = useMemo(() => {
    if (!loadedComparisonSeries.length) return false;
    if (unitKind(unit, modeMeta?.type) !== 'level') return false;
    const sizes = [lastAbs(dataPoints), ...loadedComparisonSeries.map((item) => lastAbs(item.data))]
      .filter((v) => v != null && v > 0);
    if (sizes.length < 2) return false;
    return Math.max(...sizes) / Math.min(...sizes) >= 2;
  }, [loadedComparisonSeries, dataPoints, unit, modeMeta?.type]);

  // Плашка «Показать в процентах» над графиком; предложение внутри панели сравнения не дублирует её.
  const showScaleNudge = scaleMismatch && comparisonScale === 'values';

  const handleDownloadImage = async () => {
    if (!downloadAuthed) {
      track(events.CHART_IMAGE_BLOCKED, { indicator: code, world: true });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    const ok = await exportNodeToPng(chartRef.current, {
      filename: `${code}_${modeMeta?.id || 'level'}.png`,
      watermark: false,
      // Фирменная рамка: знак, название, источник и адрес сайта вокруг снимка графика.
      frame: {
        title: imageTitle || caption,
        subtitle: '',
        source: indicator?.source
          ? t('z4.png.source', { source: localizeSource(indicator.source, locale) })
          : '',
      },
    }).catch(() => false);
    if (ok) {
      track(events.CHART_IMAGE_DOWNLOAD, {
        indicator: code,
        mode: modeMeta?.id,
        world: true,
      });
    }
  };

  const shownUnit = windowRebase ? windowRebaseUnit : displayedUnit;
  const caption = windowRebase
    ? t('w6e.compare.captionIndex')
    : chartCaption(modeMeta, shownUnit, t);
  // Название над графиком по-человечески; при сравнении стран остаётся прежняя подпись «что показано».
  const placeName = (locale === 'en' && country?.name_en) ? country.name_en : (country?.name || '');
  const modeWord = modeMeta?.type === 'yoy' || modeMeta?.type === 'yoyabs' ? t('w2.mode.yoy')
    : modeMeta?.type === 'step' ? t('w2.mode.step')
      : modeMeta?.type === 'index' ? t('z4.mode.index') : '';
  const humanTitle = !windowRebase && loadedComparisonSeries.length === 0;
  const titleBuilder = humanTitle
    ? (rangeText) => buildChartTitle({
      name: nameForAria, place: placeName, modeLabel: modeWord, rangeText, unit: shownUnit, locale,
    })
    : null;
  const imageTitle = humanTitle
    ? buildChartTitle({
      name: nameForAria, place: placeName, modeLabel: modeWord, unit: shownUnit, locale,
    })
    : null;

  return (
    <section
      id="chart"
      data-block="chart"
      className="fe-chart-section z4-chart-section"
      aria-busy={chartLoading ? true : undefined}
    >
      <div className="fe-chart-head z4-chart-head">
        <h2 className="fe-chart-head__title">{t('indicator.chartDynamicsLabel')}</h2>

        <div className="fe-chart-actions" data-no-export="true">
          <ForecastControl
            enabled={forecastEnabled}
            on={effectiveShowForecast}
            onToggle={onToggleForecast}
            reason={noForecastReason}
          />
          <ChartDownloadMenu
            onCsv={onDownloadCsv}
            onExcel={onDownloadExcel}
            onPng={handleDownloadImage}
            dataBlocked={downloadBlocked}
            imageBlocked={!downloadAuthed}
          />
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
        </div>
      </div>

      <div id="compare" className="z4-compare scroll-mt-24">
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
          baseLabel={country?.name || ''}
          suggestPercent={suggestPercent && !showScaleNudge}
        />
      </div>

      <div className="z4-chart-wrap">
        <ScaleNudge show={showScaleNudge} onScale={setComparisonScale} />

        {chartLoading ? (
          <ChartSectionSkeleton />
        ) : (
          <div ref={chartRef} className="relative w-full min-w-0 max-w-full overflow-hidden rounded-[1.5rem]">
            <IndicatorChart
              key={`${code}-${modeMeta?.id}-${activeFreq}`}
              mode="cpi"
              cpiData={dataPoints || []}
              forecastData={chartForecastPayload}
              showForecast={effectiveShowForecast}
              onFullData={onFullData}
              cpiChartTitle={caption}
              chartTitleBuilder={titleBuilder}
              ariaTitle={`${nameForAria}. ${caption}`}
              levelTooltipLabel={modeMeta?.label || modeMeta?.group || t('chart.tooltip.value')}
              forecastTooltipLabel={t('common.forecast')}
              emptyHint={emptyHint}
              dateFormat={resolveDateFormat({ frequency: activeFreq, chartMode: 'cpi' })}
              unit={shownUnit}
              rangePreset={worldRangePreset(activeFreq)}
              chartMode={modeMeta?.id || 'level'}
              indicatorCode={code}
              indicatorCategory={indicator?.category}
              referenceLineY={!windowRebase && (unit === '%' || unit === 'п.п.') ? 0 : null}
              numericTooltipOnly
              actualSeriesLabel={country?.name}
              comparisonSeries={windowRebase ? loadedComparisonSeries : NO_SERIES}
              rebaseVisible={windowRebase}
            />
          </div>
        )}

        <div className="fe-chart-after">

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

        {forecastEnabled && (
          <p className="mb-3 text-[13px] leading-5 text-text-secondary">
            {forecastNote}
            {' '}
            <Link to="/methodology" className="text-champagne hover:underline">
              {t('common.methodology')}
            </Link>
          </p>
        )}

        {showForecast && forecastEnabled && !chartLoading && forecastData.length === 0 && (
          <p className="mb-3 text-xs text-text-tertiary">
            {t('world.chart.forecastIncomplete')}
          </p>
        )}
        {showForecast && windowRebase && (
          <p className="mb-3 text-xs text-text-tertiary">
            {t('world.chart.forecastHiddenRebase')}
          </p>
        )}

        {/* Нет прогноза: страница не заканчивается тупиком, дальше сравнение, рейтинг и страна. */}
        {!forecastEnabled && !chartLoading && (
          <nav className="fe-next-steps" aria-label={t('w6e.next.aria')}>
            {pickerOptions.length > 0 && (
              <a href="#compare" className="fe-next-steps__link">
                {t('w6e.next.compare')}
                <ArrowUpRight size={13} aria-hidden="true" />
              </a>
            )}
            {conceptSlug && (
              <Link to={worldRatingPath(conceptSlug)} className="fe-next-steps__link">
                {t('w6e.next.rating')}
                <ArrowUpRight size={13} aria-hidden="true" />
              </Link>
            )}
            {country?.slug && (
              <Link to={countryPath(country.slug)} className="fe-next-steps__link">
                {t('w6e.next.country', { country: country?.name || '' })}
                <ArrowUpRight size={13} aria-hidden="true" />
              </Link>
            )}
          </nav>
        )}
        </div>
      </div>
    </section>
  );
}
