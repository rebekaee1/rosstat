import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { ArrowRight, GitCompare } from 'lucide-react';
import gsap from 'gsap';
import { useIndicator, useIndicatorStats, useIndicators } from '../lib/hooks';
import useDocumentMeta from '../lib/useMeta';
import ApiRetryBanner from '../components/ApiRetryBanner';
import IndicatorDetailHeader from '../components/IndicatorDetailHeader';
import VariantGroupPicker from '../components/VariantGroupPicker';
import FrequencySwitcher from '../components/FrequencySwitcher';
import CpiViewModePicker from '../components/CpiViewModePicker';
import IndicatorTelemetryGrid from '../components/IndicatorTelemetryGrid';
import IndicatorChartSection from '../components/IndicatorChartSection';
import IndicatorMethodologyPanel from '../components/IndicatorMethodologyPanel';
import IndicatorForecastSection from '../components/IndicatorForecastSection';
import IndicatorDataTableSection from '../components/IndicatorDataTableSection';
import IndicatorSeoBlocks from '../components/IndicatorSeoBlocks';
import { findVariantGroup } from '../lib/indicatorVariants';
import { visibleCpiViewModes } from '../lib/cpiViewModes';
import useIndicatorViewModeData from '../lib/useIndicatorViewModeData';
import { getViewModeContent } from '../lib/cpiViewModeContent';
import { downloadExcel, downloadCSV } from '../lib/excel';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import { isIndicatorListed } from '../lib/categories';

export default function IndicatorDetail() {
  const { code } = useParams();
  const headerRef = useRef(null);
  const [showForecast, setShowForecast] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  // viewMode хранится в URL (?mode=monthly) — это позволяет сохранять режим
  // при переключении между «продовольственные» / «непродовольственные» / «услуги»
  // через VariantGroupPicker и при шаринге ссылок.
  const urlMode = searchParams.get('mode');
  const viewMode = urlMode || 'inflation';
  const setViewMode = useCallback((mode) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (mode && mode !== 'inflation') next.set('mode', mode);
      else next.delete('mode');
      return next;
    }, { replace: true });
  }, [setSearchParams]);
  const [chartData, setChartData] = useState([]);
  const [currentRange, setCurrentRange] = useState('5y');

  const {
    data: indicator,
    isLoading: loadingInd,
    isError: indError,
    error: indErr,
    refetch: refetchInd,
    isFetching: fetchingInd,
  } = useIndicator(code);

  // Пока данные индикатора не пришли — не трогаем <head>: SSR-renderer
  // (seo_renderer.py::render_indicator_html) уже положил правильный title из
  // БД, плюс canonical/og:*. Любая клиентская перезапись на промежуточное
  // значение (например, "Индикатор cpi") вызывала бы flap у поисковиков.
  useDocumentMeta(indicator ? {
    title: indicator.seo_title || indicator.name,
    description: indicator.seo_description,
    path: `/indicator/${code}`,
  } : null);

  const { data: stats } = useIndicatorStats(code);
  const variantGroup = findVariantGroup(code);
  const cpiViewModes = useMemo(() => visibleCpiViewModes(code), [code]);

  // Соседи по той же категории — нижний CTA-блок «Похожие индикаторы».
  // Загружается лениво (после того как мы знаем category), потому что
  // useIndicators({ category }) приходит из общего react-query-кэша и обычно
  // уже прогрет на /category/:slug страницей-родителем.
  const { data: siblings } = useIndicators({
    category: indicator?.category,
    includeInactive: false,
    enabled: Boolean(indicator?.category),
  });

  const relatedIndicators = useMemo(() => {
    if (!siblings?.length || !indicator) return [];
    return siblings
      .filter((s) => s.code !== indicator.code && isIndicatorListed(s) && s.is_active)
      .slice(0, 6);
  }, [siblings, indicator]);

  const view = useIndicatorViewModeData({ code, viewMode });
  const {
    isPriceCategory, safeViewMode, chartMode, shouldSubtract100,
    dataPoints, inflationResp,
    quarterlyDataPoints, annualDataPoints, weeklyDataPoints,
    displayForecastData, quarterlyForecastData, annualForecastResp, weeklyForecastData,
    stats: viewStats, cpiPrevDate,
    chartLoading, loadingData, loadingInflation,
    loadingAnnual, loadingWeekly, loadingQuarterly,
    dataError, fetchingData, hasForecastData, forecastEnabled,
    refetchData, refetchInflation, refetchForecast,
  } = view;

  const adj = useCallback((v) => {
    if (v == null || !shouldSubtract100) return v;
    return Number(v) - 100;
  }, [shouldSubtract100]);

  useEffect(() => {
    const els = headerRef.current?.querySelectorAll('[data-animate]');
    if (!els?.length) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(els,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 1, ease: 'power3.out', stagger: 0.1 }
    );
    return () => tween.kill();
  }, []);

  useEffect(() => {
    if (!indicator?.code) return;
    track(events.INDICATOR_VIEW, {
      indicator: indicator.code,
      indicatorCategory: indicator.category,
    });
  }, [indicator?.code, indicator?.category]);

  useScrollDepth({
    key: code,
    page: 'indicator',
    indicator: code,
    indicatorCategory: indicator?.category,
  });

  const handleChartData = useCallback((data) => {
    setChartData(data);
  }, []);

  const handleRangeChange = useCallback((range) => {
    setCurrentRange(range);
  }, []);

  const downloadMeta = useMemo(() => ({
    name: indicator?.name, unit: indicator?.unit,
  }), [indicator?.name, indicator?.unit]);

  const downloadMode = isPriceCategory ? chartMode : null;

  const handleDownloadExcel = useCallback(() => {
    downloadExcel(chartData, downloadMode, code, currentRange, downloadMeta);
    track(events.DOWNLOAD_EXCEL, { indicator: code, range: currentRange, indicatorCategory: indicator?.category });
  }, [chartData, downloadMode, code, currentRange, downloadMeta, indicator?.category]);

  const handleDownloadCSV = useCallback(() => {
    downloadCSV(chartData, downloadMode, code, currentRange, downloadMeta);
    track(events.DOWNLOAD_CSV, { indicator: code, range: currentRange, indicatorCategory: indicator?.category });
  }, [chartData, downloadMode, code, currentRange, downloadMeta, indicator?.category]);

  const chartEmptyHint = useMemo(() => {
    if (dataError) {
      return 'Не удалось получить исторический ряд. Нажмите «Повторить» выше или проверьте backend / прокси Vite.';
    }
    if (!loadingData && (dataPoints?.length ?? 0) === 0) {
      return (
        'В API пока нет точек для этого кода — например, прод ещё без backfill ключевой ставки, или локальный backend не запущен. '
        + 'После появления данных график заполнится автоматически.'
      );
    }
    return undefined;
  }, [dataError, loadingData, dataPoints]);

  const refetchIndicatorPage = useCallback(() => {
    refetchInd();
    refetchData();
    if (isPriceCategory) refetchInflation();
    refetchForecast();
  }, [refetchInd, refetchData, refetchInflation, refetchForecast, isPriceCategory]);

  const apiBannerFetching = fetchingInd || fetchingData;
  const viewModeContent = getViewModeContent({
    chartMode, safeViewMode, isPriceCategory, indicator,
  });
  const s = viewStats;

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24 md:pb-28">
      {(indError || dataError) && (
        <div className="mb-8">
          <ApiRetryBanner
            onRetry={refetchIndicatorPage}
            isFetching={apiBannerFetching}
          >
            {indError && (
              <span className="block">
                Карточка индикатора не загрузилась
                {indErr?.message ? ` (${indErr.message})` : ''}.
              </span>
            )}
            {dataError && (
              <span className="block">
                Исторические данные недоступны — график и таблица без ряда.
              </span>
            )}
          </ApiRetryBanner>
        </div>
      )}

      <IndicatorDetailHeader
        indicator={indicator}
        code={code}
        loading={loadingInd}
        headerRef={headerRef}
      />

      <IndicatorTelemetryGrid
        indicator={indicator}
        viewStats={s}
        stats={stats}
        isPriceCategory={isPriceCategory}
        safeViewMode={safeViewMode}
        cpiPrevDate={cpiPrevDate}
        adj={adj}
        loading={
          loadingInd
          || (chartMode === 'inflation' && loadingInflation)
          || (chartMode === 'annual' && loadingAnnual)
          || (chartMode === 'weekly' && loadingWeekly)
          || (chartMode === 'quarterly' && loadingQuarterly)
          || (chartMode === 'index' && loadingData)
        }
      />

      {/* Оба переключателя — НАД графиком, сверху вниз:
          1) «Состав» (категории-родственники: cpi → cpi-food / housing-primary →
             housing-secondary и т.д.) — меняет сам индикатор и весь набор данных.
          2) «Режим инфляции» (мес / кв / год / нед / индекс) — меняет представление
             того же индикатора, должен стоять сразу над графиком.
          3) График.
          Под графиком — никаких переключателей (только range-пресеты внутри самого
          IndicatorChart и форекаст-toggle в тулбаре). */}
      <VariantGroupPicker
        group={variantGroup}
        currentCode={code}
        currentMode={isPriceCategory ? safeViewMode : null}
      />

      <FrequencySwitcher
        currentCode={code}
        currentFrequency={indicator?.frequency}
        alternateFrequencies={indicator?.alternate_frequencies}
        primaryIndicatorCode={indicator?.primary_indicator_code}
        indicatorCategory={indicator?.category}
      />

      {isPriceCategory && (
        <CpiViewModePicker
          modes={cpiViewModes}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      )}

      <IndicatorChartSection
        code={code}
        indicator={indicator}
        chartMode={chartMode}
        isPriceCategory={isPriceCategory}
        chartLoading={chartLoading}
        inflationResp={inflationResp}
        dataPoints={dataPoints}
        quarterlyDataPoints={quarterlyDataPoints}
        annualDataPoints={annualDataPoints}
        weeklyDataPoints={weeklyDataPoints}
        displayForecastData={displayForecastData}
        quarterlyForecastData={quarterlyForecastData}
        annualForecastResp={annualForecastResp}
        weeklyForecastData={weeklyForecastData}
        forecastEnabled={forecastEnabled}
        showForecast={showForecast}
        onToggleForecast={() => setShowForecast((v) => !v)}
        onChartData={handleChartData}
        onRangeChange={handleRangeChange}
        emptyHint={chartEmptyHint}
        onDownloadCsv={handleDownloadCSV}
        onDownloadExcel={handleDownloadExcel}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-16">
        <IndicatorMethodologyPanel
          indicator={indicator}
          content={viewModeContent}
        />
        <IndicatorForecastSection
          indicator={indicator}
          chartMode={chartMode}
          safeViewMode={safeViewMode}
          inflationResp={inflationResp}
          displayForecastData={displayForecastData}
          quarterlyForecastData={quarterlyForecastData}
          annualForecastResp={annualForecastResp}
          weeklyForecastData={weeklyForecastData}
          forecastEnabled={forecastEnabled}
          showForecast={showForecast}
          hasForecastData={hasForecastData}
        />
      </div>

      <IndicatorDataTableSection
        indicator={indicator}
        chartMode={chartMode}
        isPriceCategory={isPriceCategory}
        inflationResp={inflationResp}
        dataPoints={dataPoints}
        quarterlyDataPoints={quarterlyDataPoints}
        annualDataPoints={annualDataPoints}
        weeklyDataPoints={weeklyDataPoints}
      />

      <IndicatorSeoBlocks blocks={indicator?.seo_blocks} />

      {relatedIndicators.length > 0 && (
        <section className="mt-16">
          <div className="flex items-center gap-4 mb-6 flex-wrap">
            <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold">
              Похожие индикаторы
            </h2>
            <div className="h-[1px] flex-1 bg-border-subtle" />
            <Link
              to={`/compare?a=${code}`}
              onClick={() => track(events.RELATED_LINK_CLICK, {
                from: code,
                to: 'compare',
                surface: 'indicator-cta',
              })}
              className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-champagne hover:text-champagne-muted transition-colors"
            >
              <GitCompare className="w-3.5 h-3.5" />
              Сравнить
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {relatedIndicators.map((rel) => (
              <Link
                key={rel.code}
                to={`/indicator/${rel.code}`}
                onClick={() => track(events.RELATED_INDICATOR_CLICK, {
                  from: code,
                  to: rel.code,
                  indicatorCategory: indicator?.category,
                  surface: 'indicator-related',
                })}
                className="group flex items-center justify-between gap-4 p-4 rounded-2xl border border-border-subtle bg-surface hover:border-champagne/30 transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-text-primary mb-1 truncate group-hover:text-champagne transition-colors">
                    {rel.name}
                  </p>
                  {rel.unit && (
                    <p className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
                      {rel.unit}
                    </p>
                  )}
                </div>
                <ArrowRight className="w-4 h-4 text-text-tertiary shrink-0 group-hover:text-champagne group-hover:translate-x-0.5 transition-all" />
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
