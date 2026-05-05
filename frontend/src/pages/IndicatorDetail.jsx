import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import gsap from 'gsap';
import { ExternalLink, Activity, Info, Database, Terminal, Download } from 'lucide-react';
import { useIndicator, useIndicatorStats } from '../lib/hooks';
import { formatDate, unitSuffix, cn } from '../lib/format';
import useDocumentMeta from '../lib/useMeta';
import IndicatorChart from '../components/IndicatorChart';
import ForecastTable from '../components/ForecastTable';
import DataTable from '../components/DataTable';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { ChartSkeleton, SkeletonBox } from '../components/Skeleton';
import TelemetryCard from '../components/TelemetryCard';
import IndicatorDetailHeader from '../components/IndicatorDetailHeader';
import VariantGroupPicker from '../components/VariantGroupPicker';
import CpiViewModePicker from '../components/CpiViewModePicker';
import { findVariantGroup } from '../lib/indicatorVariants';
import { visibleCpiViewModes } from '../lib/cpiViewModes';
import useIndicatorViewModeData from '../lib/useIndicatorViewModeData';
import { getViewModeContent } from '../lib/cpiViewModeContent';
import { downloadExcel, downloadCSV } from '../lib/excel';
import { track, trackOutbound, events } from '../lib/track';

export default function IndicatorDetail() {
  const { code } = useParams();
  const headerRef = useRef(null);
  const [showForecast, setShowForecast] = useState(true);
  const [viewMode, setViewMode] = useState('inflation');
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

  useDocumentMeta({
    title: indicator?.seo_title || `Индикатор ${code}`,
    description: indicator?.seo_description,
    path: `/indicator/${code}`,
  });

  const { data: stats } = useIndicatorStats(code);
  const variantGroup = findVariantGroup(code);
  const cpiViewModes = useMemo(() => visibleCpiViewModes(code), [code]);

  const view = useIndicatorViewModeData({ code, viewMode });
  const {
    isPriceCategory, safeViewMode, chartMode, shouldSubtract100,
    dataPoints, inflationResp,
    quarterlyDataPoints, annualDataPoints, weeklyDataPoints,
    displayForecastData, quarterlyForecastData, annualForecastResp,
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

      <VariantGroupPicker group={variantGroup} currentCode={code} />

      {isPriceCategory && (
        <CpiViewModePicker
          modes={cpiViewModes}
          currentMode={safeViewMode}
          onChange={setViewMode}
          trackContext={{ code, category: indicator?.category }}
        />
      )}

      <section className="mb-12">
        {(loadingInd || (chartMode === 'inflation' && loadingInflation) || (chartMode === 'annual' && loadingAnnual) || (chartMode === 'weekly' && loadingWeekly) || (chartMode === 'quarterly' && loadingQuarterly)) ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => <SkeletonBox key={i} className="h-48 rounded-[2rem]" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <TelemetryCard
              label={
                safeViewMode === 'weekly' ? 'Инфляция за неделю'
                  : safeViewMode === 'cpi' && isPriceCategory ? 'Прирост за месяц'
                  : 'Текущее значение'
              }
              value={s?.currentValue ?? adj(indicator?.current_value)}
              unit={indicator?.unit || '%'}
              change={s?.change ?? indicator?.change}
              pctChange={
                indicator?.unit === 'индекс' && (s?.previousValue ?? indicator?.previous_value)
                  ? +(((s?.currentValue ?? indicator?.current_value) - (s?.previousValue ?? indicator?.previous_value))
                      / (s?.previousValue ?? indicator?.previous_value) * 100).toFixed(2)
                  : undefined
              }
              meta={
                safeViewMode === 'weekly' && Number(s?.currentValue) === 0
                  ? `ДАТА: ${formatDate(s?.currentDate ?? indicator?.current_date, 'full')} · ЦЕНЫ БЕЗ ИЗМЕНЕНИЙ`
                  : `ДАТА: ${formatDate(s?.currentDate ?? indicator?.current_date, 'full')}`
              }
              delay={0}
              deltaSuffix={
                safeViewMode === 'quarterly' ? 'к пред. кварталу'
                  : safeViewMode === 'annual' ? 'к пред. значению'
                  : safeViewMode === 'weekly' ? 'к пред. неделе'
                  : indicator?.frequency === 'quarterly' ? 'к пред. кварталу'
                  : isPriceCategory ? 'к пред. месяцу' : 'к пред. значению'
              }
            />
            <TelemetryCard
              label={
                safeViewMode === 'weekly' ? 'Предыдущая неделя'
                  : safeViewMode === 'quarterly' ? 'Предыдущий квартал'
                  : safeViewMode === 'annual' ? 'Год назад'
                  : isPriceCategory ? 'Предыдущий месяц' : 'Предыдущее значение'
              }
              value={s?.previousValue ?? adj(indicator?.previous_value)}
              unit={indicator?.unit || '%'}
              meta={`ДАТА: ${formatDate(s?.previousDate ?? cpiPrevDate, 'full')}`}
              delay={1}
            />
            {(s?.highest || stats?.highest) && (
              <TelemetryCard
                label="Абсолютный максимум"
                value={s?.highest?.value ?? adj(stats?.highest?.value)}
                unit={indicator?.unit || '%'}
                meta={`ПИК: ${formatDate(s?.highest?.date ?? stats?.highest?.date, 'full')}`}
                delay={2}
              />
            )}
            {(s?.average != null || stats?.average != null) && (
              <TelemetryCard
                label="Среднее значение"
                value={s?.average ?? adj(stats?.average)}
                unit={indicator?.unit || '%'}
                meta={`НАБЛ.: ${s?.dataCount ?? stats?.data_count} ПЕРИОД.`}
                delay={3}
              />
            )}
          </div>
        )}
      </section>

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
              onClick={handleDownloadCSV}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 transition-colors text-xs font-mono uppercase tracking-wider magnetic-btn"
              title="Скачать CSV"
            >
              <Download className="w-3.5 h-3.5" />
              CSV
            </button>
            <button
              onClick={handleDownloadExcel}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 transition-colors text-xs font-mono uppercase tracking-wider magnetic-btn"
              title="Скачать Excel"
            >
              <Download className="w-3.5 h-3.5" />
              Excel
            </button>

            <div className="relative group">
              <label className={cn(
                'flex items-center gap-3 select-none',
                forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'
              )}>
                <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary group-hover:text-text-secondary transition-colors">
                  Прогноз
                </span>
                <div
                  role="switch"
                  aria-checked={forecastEnabled && showForecast}
                  aria-label="Показать прогноз"
                  tabIndex={forecastEnabled ? 0 : -1}
                  onClick={() => { if (forecastEnabled) { setShowForecast(v => !v); track(events.FORECAST_TOGGLE, { show: !showForecast, indicator: code, indicatorCategory: indicator?.category }); } }}
                  onKeyDown={e => { if (forecastEnabled && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); setShowForecast(v => !v); track(events.FORECAST_TOGGLE, { show: !showForecast, indicator: code, indicatorCategory: indicator?.category }); } }}
                  className={cn(
                    'relative w-10 h-5 rounded-full transition-colors duration-300',
                    forecastEnabled ? 'cursor-pointer' : 'cursor-not-allowed',
                    forecastEnabled && showForecast ? 'bg-champagne/30' : 'bg-obsidian-lighter border border-border-subtle'
                  )}
                >
                  <div className={cn(
                    'absolute top-[2px] left-[2px] w-4 h-4 rounded-full transition-transform duration-300',
                    forecastEnabled && showForecast ? 'translate-x-5 bg-champagne' : 'translate-x-0 bg-text-tertiary'
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
              cpiData={chartMode === 'quarterly' ? quarterlyDataPoints
                : chartMode === 'annual' ? annualDataPoints
                : chartMode === 'weekly' ? weeklyDataPoints
                : dataPoints}
              forecastData={
                chartMode === 'quarterly' ? quarterlyForecastData
                  : chartMode === 'annual' ? annualForecastResp
                  : chartMode === 'weekly' ? null
                  : displayForecastData
              }
              showForecast={forecastEnabled && showForecast}
              onChartData={handleChartData}
              onRangeChange={handleRangeChange}
              referenceLineY={isPriceCategory ? 0 : null}
              cpiChartTitle={
                chartMode === 'quarterly' ? 'Квартальная инфляция (%)'
                  : chartMode === 'annual' ? 'Годовая инфляция (%)'
                  : chartMode === 'weekly' ? 'Недельная инфляция (%)'
                  : isPriceCategory
                    ? 'Прирост цен (%, к предыдущему месяцу)'
                    : `${indicator?.name || 'Показатель'}${unitSuffix(indicator?.unit) ? ` (${unitSuffix(indicator?.unit)})` : ''}`
              }
              levelTooltipLabel={
                chartMode === 'quarterly' ? 'Кв. инфляция'
                  : chartMode === 'annual' ? 'Год. инфляция'
                  : chartMode === 'weekly' ? 'Нед. ИПЦ'
                  : isPriceCategory ? 'Прирост'
                  : 'Значение'
              }
              emptyHint={chartEmptyHint}
              dateFormat={
                chartMode === 'quarterly' ? 'quarterly'
                : chartMode === 'annual' ? 'annual'
                : chartMode !== 'inflation' && indicator?.frequency === 'daily' ? 'day'
                : indicator?.frequency === 'quarterly' ? 'quarterly'
                : indicator?.frequency === 'annual' ? 'annual'
                : 'full'
              }
              unit={indicator?.unit || '%'}
              rangePreset={
                chartMode === 'annual' || indicator?.frequency === 'annual'
                  ? 'annual'
                  : 'default'
              }
              indicatorCode={code}
              indicatorCategory={indicator?.category}
            />
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-16">
        <section className="lg:col-span-1 p-8 rounded-[2rem] bg-obsidian-light border border-border-subtle flex flex-col h-full">
          <div className="flex items-center gap-3 mb-6">
            <Info className="w-4 h-4 text-champagne" />
            <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-text-secondary">
              Методология
            </h3>
          </div>
          
          <div className="prose prose-sm max-w-none">
            <p className="text-text-secondary leading-relaxed">
              {viewModeContent.description}
            </p>
            {viewModeContent.methodology && (
              <p className="text-text-tertiary border-l-2 border-champagne/30 pl-4 my-4 font-mono text-[10px] uppercase tracking-wider">
                {viewModeContent.methodology}
              </p>
            )}
          </div>
          
          {indicator?.source_url && indicator.source_url.startsWith('http') ? (
          <div className="mt-auto pt-6 border-t border-border-subtle">
            <a
              href={indicator.source_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackOutbound(indicator.source_url)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-surface border border-border-subtle text-xs font-mono uppercase tracking-widest text-champagne hover:bg-champagne/10 transition-colors lift-hover w-full justify-center"
            >
              <Database className="w-3.5 h-3.5" />
              Источник: {indicator.source}
              <ExternalLink className="w-3 h-3 ml-auto opacity-50" />
            </a>
          </div>
          ) : indicator?.source ? (
          <div className="mt-auto pt-6 border-t border-border-subtle">
            <span className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-surface border border-border-subtle text-xs font-mono uppercase tracking-widest text-text-secondary w-full justify-center">
              <Database className="w-3.5 h-3.5" />
              Источник: {indicator.source}
            </span>
          </div>
          ) : null}
        </section>

        <section className="lg:col-span-2">
          {safeViewMode === 'weekly' ? (
            <div className="h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center gap-3 text-text-tertiary p-8">
              <Activity className="w-8 h-8 mb-1 opacity-20" />
              <p className="text-sm font-medium text-text-secondary text-center max-w-md">
                Недельный ИПЦ публикуется Росстатом еженедельно
              </p>
              <p className="text-xs text-center max-w-lg leading-relaxed text-text-tertiary">
                Прогноз недоступен для недельной частоты — переключитесь на вкладку «Инфляция за год», «Месячная», «Квартальная» или «Годовая»
              </p>
            </div>
          ) : forecastEnabled && showForecast && hasForecastData ? (
            <ForecastTable
              mode={chartMode}
              inflation={inflationResp}
              forecastData={
                chartMode === 'quarterly' ? quarterlyForecastData
                  : chartMode === 'annual' ? annualForecastResp
                  : displayForecastData
              }
              unit={indicator?.unit || '%'}
              dateFormat={
                chartMode === 'quarterly' ? 'quarterly'
                : chartMode === 'annual' ? 'annual'
                : indicator?.frequency === 'quarterly' ? 'quarterly'
                : indicator?.frequency === 'annual' ? 'annual'
                : 'full'
              }
            />
          ) : forecastEnabled && !showForecast ? (
            <div className="h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center text-text-tertiary p-8">
              <Activity className="w-8 h-8 mb-4 opacity-20" />
              <p className="text-xs font-mono uppercase tracking-widest text-center">Включите переключатель «Прогноз», чтобы показать таблицу прогноза</p>
            </div>
          ) : (
            <div className="h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center gap-3 text-text-tertiary p-8">
              <Activity className="w-8 h-8 mb-1 opacity-20" />
              <p className="text-sm font-medium text-text-secondary text-center max-w-md">
                Прогноз для этого показателя не рассчитан или недоступен
              </p>
              <p className="text-xs text-center max-w-lg leading-relaxed text-text-tertiary">
                Некоторые режимы показывают только официальный исторический ряд. Если прогноз появится, переключатель станет активным автоматически.
              </p>
            </div>
          )}
        </section>
      </div>

      <section>
        <DataTable
          key={`${indicator?.code}-${chartMode}`}
          data={
            chartMode === 'inflation' ? (inflationResp?.actuals || [])
            : chartMode === 'quarterly' ? quarterlyDataPoints
            : chartMode === 'annual' ? annualDataPoints
            : chartMode === 'weekly' ? weeklyDataPoints
            : dataPoints
          }
          title={
            chartMode === 'inflation'
              ? 'Исторические данные — Инфляция 12 мес.'
              : chartMode === 'quarterly'
                ? 'Исторические данные — Квартальная инфляция'
                : chartMode === 'annual'
                  ? 'Исторические данные — Годовая инфляция'
                  : chartMode === 'weekly'
                    ? 'Исторические данные — Недельный ИПЦ'
                    : (isPriceCategory ? 'Исторические данные — Прирост цен (%, м/м)' : `Исторические данные — ${indicator?.name || 'ряд'}`)
          }
          dateFormat={
            chartMode === 'quarterly' ? 'quarterly'
            : chartMode === 'annual' ? 'annual'
            : chartMode !== 'inflation' && indicator?.frequency === 'daily' ? 'day'
            : indicator?.frequency === 'quarterly' ? 'quarterly'
            : indicator?.frequency === 'annual' ? 'annual'
            : 'full'
          }
          unit={indicator?.unit || '%'}
        />
      </section>
    </div>
  );
}
