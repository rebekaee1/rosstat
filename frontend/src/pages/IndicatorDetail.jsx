import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import gsap from 'gsap';
import { ArrowLeft, ExternalLink, Activity, Info, Database, Terminal, Download } from 'lucide-react';
import {
  useIndicator, useIndicatorData, useIndicatorStats, useInflation, useForecast,
} from '../lib/hooks';
import { formatDate, unitSuffix, cn, isCpiIndex, adjustCpiForecastDisplay } from '../lib/format';
import { CATEGORIES } from '../lib/categories';
import useDocumentMeta from '../lib/useMeta';
import IndicatorChart from '../components/IndicatorChart';
import ForecastTable from '../components/ForecastTable';
import DataTable from '../components/DataTable';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { ChartSkeleton, SkeletonBox } from '../components/Skeleton';
import TelemetryCard from '../components/TelemetryCard';
import { downloadExcel, downloadCSV } from '../lib/excel';
import { track, trackOutbound, events } from '../lib/track';

const FREQ_MAP = {
  monthly: 'Помесячно',
  quarterly: 'Ежеквартально',
  annual: 'Ежегодно',
  weekly: 'Еженедельно',
  irregular: 'Нерегулярно',
  daily: 'По дням',
};

const CPI_DERIVED_CODES = {
  cpi: { quarterly: 'inflation-quarterly', annual: 'inflation-annual' },
  'cpi-food': { quarterly: 'cpi-food-quarterly', annual: 'cpi-food-annual' },
  'cpi-nonfood': { quarterly: 'cpi-nonfood-quarterly', annual: 'cpi-nonfood-annual' },
  'cpi-services': { quarterly: 'cpi-services-quarterly', annual: 'cpi-services-annual' },
};

const CPI_VIEW_MODES = [
  { mode: 'inflation', label: 'Инфляция за год', generalOnly: false },
  { mode: 'weekly', label: 'Недельная', generalOnly: true },
  { mode: 'cpi', label: 'Месячная', generalOnly: false },
  { mode: 'quarterly', label: 'Квартальная', generalOnly: false },
  { mode: 'annual', label: 'Годовая', generalOnly: false },
];

const VARIANT_GROUPS = [
  {
    label: 'Состав индекса потребительских цен',
    codes: [
      { code: 'cpi', label: 'Все товары и услуги' },
      { code: 'cpi-food', label: 'Продовольствие' },
      { code: 'cpi-nonfood', label: 'Непродовольственные' },
      { code: 'cpi-services', label: 'Услуги' },
    ],
  },
  {
    label: 'Режим ВВП',
    codes: [
      { code: 'gdp-nominal', label: 'Номинальный' },
      { code: 'gdp-real', label: 'Реальный' },
      { code: 'gdp-yoy', label: 'Год к году' },
      { code: 'gdp-qoq', label: 'Квартал к кварталу' },
    ],
  },
  {
    label: 'Режим индекса цен производителей',
    codes: [
      { code: 'ppi', label: 'Индекс' },
      { code: 'ppi-yoy', label: 'Год к году' },
    ],
  },
  {
    label: 'Первичное жильё',
    codes: [
      { code: 'housing-price-primary', label: 'Индекс' },
      { code: 'housing-yoy-primary', label: 'Год к году' },
    ],
  },
  {
    label: 'Вторичное жильё',
    codes: [
      { code: 'housing-price-secondary', label: 'Индекс' },
      { code: 'housing-yoy-secondary', label: 'Год к году' },
    ],
  },
];

const INFLATION_DESCRIPTION =
  'Накопленная инфляция за 12 месяцев показывает, на сколько процентов выросли ' +
  'потребительские цены за последний год. Рассчитывается как произведение 12 ' +
  'последовательных месячных индексов ИПЦ минус 100%.';

const INFLATION_METHODOLOGY =
  'Формула: (∏ᵢ₌₁¹² ИПЦᵢ / 100) × 100 − 100, где ИПЦᵢ — индекс потребительских ' +
  'цен за i-й месяц в % к предыдущему месяцу.';

const QUARTERLY_DESCRIPTION =
  'Квартальная инфляция показывает, на сколько процентов выросли потребительские цены за квартал (3 месяца). ' +
  'Рассчитывается как произведение 3 последовательных месячных индексов ИПЦ минус 100%.';

const QUARTERLY_METHODOLOGY =
  'Формула: (ИПЦ₁ / 100) × (ИПЦ₂ / 100) × (ИПЦ₃ / 100) × 100 − 100.';

const ANNUAL_DESCRIPTION =
  'Годовая инфляция — изменение цен за последние 12 месяцев. ' +
  'Рассчитывается как произведение 12 последовательных месячных индексов ИПЦ минус 100%.';

const ANNUAL_METHODOLOGY =
  'Формула: (∏ᵢ₌₁¹² ИПЦᵢ / 100) × 100 − 100, скользящее окно 12 месяцев.';

const WEEKLY_DESCRIPTION =
  'Недельный ИПЦ — изменение потребительских цен за неделю по данным Росстата. ' +
  'Публикуется еженедельно, является оперативным индикатором инфляционных процессов.';

const WEEKLY_METHODOLOGY =
  'Источник — еженедельные бюллетени Росстата «Об оценке индекса потребительских цен». ' +
  'Официальный агрегированный недельный ИПЦ по всей потребительской корзине. Значение 100 = без изменений.';

const CPI_MONTHLY_DESCRIPTION =
  'Месячная инфляция — процентное изменение потребительских цен к предыдущему месяцу. ' +
  'Положительное значение означает рост цен, отрицательное — снижение. ' +
  'Шкала по оси Y центрирована на нуле.';

const CPI_MONTHLY_METHODOLOGY =
  'Формула: ИПЦᵢ − 100, где ИПЦᵢ — индекс потребительских цен за i-й месяц в % к предыдущему месяцу. ' +
  'Источник — месячные индексы ИПЦ Росстата.';

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
  const CPI_CODES = ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'];
  const isPriceCategory = CPI_CODES.includes(code);
  const safeViewMode = isPriceCategory && code !== 'cpi' && viewMode === 'weekly'
    ? 'inflation'
    : viewMode;
  const shouldSubtract100 = isCpiIndex(code);
  const cpiDerivedCodes = CPI_DERIVED_CODES[code] || {};
  const variantGroup = VARIANT_GROUPS.find(group => group.codes.some(item => item.code === code));
  const {
    data: dataResp,
    isLoading: loadingData,
    isError: dataError,
    refetch: refetchData,
    isFetching: fetchingData,
  } = useIndicatorData(code);
  const { data: stats } = useIndicatorStats(code);
  const { data: inflationResp, isLoading: loadingInflation, refetch: refetchInflation } = useInflation(code, {
    enabled: isPriceCategory,
  });
  const { data: forecastResp, refetch: refetchForecast } = useForecast(code);

  const cpiViewModes = useMemo(
    () => CPI_VIEW_MODES.filter(item => !item.generalOnly || code === 'cpi'),
    [code]
  );
  const { data: quarterlyForecastResp } = useForecast(cpiDerivedCodes.quarterly, {
    enabled: !!cpiDerivedCodes.quarterly && safeViewMode === 'quarterly',
  });
  const { data: annualForecastResp } = useForecast(cpiDerivedCodes.annual, {
    enabled: !!cpiDerivedCodes.annual && safeViewMode === 'annual',
  });
  const {
    data: quarterlyResp,
    isLoading: loadingQuarterly,
  } = useIndicatorData(cpiDerivedCodes.quarterly, undefined, {
    enabled: !!cpiDerivedCodes.quarterly && safeViewMode === 'quarterly',
  });
  const {
    data: annualResp,
    isLoading: loadingAnnual,
  } = useIndicatorData(cpiDerivedCodes.annual, undefined, {
    enabled: !!cpiDerivedCodes.annual && safeViewMode === 'annual',
  });
  const {
    data: weeklyResp,
    isLoading: loadingWeekly,
  } = useIndicatorData('inflation-weekly', undefined, {
    enabled: code === 'cpi' && safeViewMode === 'weekly',
  });

  const chartMode = isPriceCategory ? safeViewMode : 'cpi';

  const inflationStats = useMemo(() => {
    if (chartMode !== 'inflation' || !inflationResp?.actuals?.length) return null;
    const a = inflationResp.actuals;
    const current = a[a.length - 1];
    const previous = a.length > 1 ? a[a.length - 2] : null;
    const highest = a.reduce((max, p) => p.value > max.value ? p : max, a[0]);
    const avg = a.reduce((s, p) => s + p.value, 0) / a.length;
    return {
      currentValue: current.value,
      currentDate: current.date,
      previousValue: previous?.value,
      previousDate: previous?.date,
      change: previous ? current.value - previous.value : null,
      highest: { value: highest.value, date: highest.date },
      average: avg,
      dataCount: a.length,
    };
  }, [chartMode, inflationResp]);

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

  const rawDataPoints = useMemo(
    () => (Array.isArray(dataResp?.data) ? dataResp.data : []),
    [dataResp],
  );

  const dataPoints = useMemo(() => {
    if (!shouldSubtract100 || !rawDataPoints.length) return rawDataPoints;
    return rawDataPoints.map(p => ({ ...p, value: Number(p.value) - 100 }));
  }, [rawDataPoints, shouldSubtract100]);

  const displayForecastData = useMemo(() => {
    if (!shouldSubtract100) return forecastResp;
    return adjustCpiForecastDisplay(forecastResp, code);
  }, [forecastResp, shouldSubtract100, code]);

  const quarterlyForecastData = useMemo(
    () => adjustCpiForecastDisplay(quarterlyForecastResp, cpiDerivedCodes.quarterly),
    [quarterlyForecastResp, cpiDerivedCodes.quarterly],
  );

  const adj = useCallback((v) => {
    if (v == null || !shouldSubtract100) return v;
    return Number(v) - 100;
  }, [shouldSubtract100]);

  const quarterlyDataPoints = useMemo(() => {
    if (!quarterlyResp?.data?.length) return [];
    return quarterlyResp.data.map(p => ({ ...p, value: Number(p.value) - 100 }));
  }, [quarterlyResp]);

  const annualDataPoints = useMemo(() => {
    if (!annualResp?.data?.length) return [];
    const byYear = new Map();
    for (const p of annualResp.data) {
      const year = String(p.date).slice(0, 4);
      const existing = byYear.get(year);
      if (!existing || String(p.date) > String(existing.date)) {
        byYear.set(year, p);
      }
    }
    return Array.from(byYear.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [annualResp]);

  const weeklyDataPoints = useMemo(() => {
    if (!weeklyResp?.data?.length) return [];
    return weeklyResp.data.map(p => ({ ...p, value: Number(p.value) - 100 }));
  }, [weeklyResp]);

  function computeDerivedStats(points) {
    if (!points.length) return null;
    const a = points;
    const current = a[a.length - 1];
    const previous = a.length > 1 ? a[a.length - 2] : null;
    const highest = a.reduce((max, p) => p.value > max.value ? p : max, a[0]);
    const avg = a.reduce((sum, p) => sum + p.value, 0) / a.length;
    return {
      currentValue: current.value,
      currentDate: current.date,
      previousValue: previous?.value,
      previousDate: previous?.date,
      change: previous ? current.value - previous.value : null,
      highest: { value: highest.value, date: highest.date },
      average: avg,
      dataCount: a.length,
    };
  }

  const quarterlyStats = useMemo(() => {
    if (safeViewMode !== 'quarterly') return null;
    return computeDerivedStats(quarterlyDataPoints);
  }, [safeViewMode, quarterlyDataPoints]);

  const annualStats = useMemo(() => {
    if (safeViewMode !== 'annual') return null;
    return computeDerivedStats(annualDataPoints);
  }, [safeViewMode, annualDataPoints]);

  const weeklyStats = useMemo(() => {
    if (safeViewMode !== 'weekly') return null;
    return computeDerivedStats(weeklyDataPoints);
  }, [safeViewMode, weeklyDataPoints]);

  const s = safeViewMode === 'quarterly' ? quarterlyStats
    : safeViewMode === 'annual' ? annualStats
    : safeViewMode === 'weekly' ? weeklyStats
    : inflationStats;
  const cpiPrevDate = dataPoints.length >= 2 ? dataPoints[dataPoints.length - 2].date : null;


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

  const chartLoading = chartMode === 'inflation' ? loadingInflation
    : chartMode === 'quarterly' ? loadingQuarterly
    : chartMode === 'annual' ? loadingAnnual
    : chartMode === 'weekly' ? loadingWeekly
    : loadingData;

  const hasForecastData = chartMode === 'quarterly'
    ? quarterlyForecastData?.forecast?.values?.length > 0
    : chartMode === 'annual'
      ? annualForecastResp?.forecast?.values?.length > 0
      : chartMode === 'weekly'
        ? false
        : chartMode === 'inflation'
          ? inflationResp?.forecast?.length > 0
          : displayForecastData?.forecast?.values?.length > 0;
  const forecastCapable = safeViewMode !== 'weekly';
  const forecastEnabled = forecastCapable && hasForecastData;

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

      <div ref={headerRef} className="mb-12 md:mb-16 max-w-4xl">
        <nav data-animate className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary mb-8">
          <Link
            to="/"
            className="hover:text-champagne transition-colors lift-hover inline-flex items-center gap-1.5 group"
          >
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
            Главная
          </Link>
          {indicator?.category && (() => {
            const cat = CATEGORIES.find(c => c.apiCategory === indicator.category);
            if (!cat) return null;
            return (
              <>
                <span className="text-text-tertiary/40">/</span>
                <Link to={`/category/${cat.slug}`} className="hover:text-champagne transition-colors">
                  {cat.name}
                </Link>
              </>
            );
          })()}
        </nav>

        {loadingInd ? (
          <div className="space-y-4">
            <SkeletonBox className="h-4 w-24" />
            <SkeletonBox className="h-14 w-3/4" />
            <SkeletonBox className="h-6 w-1/2" />
          </div>
        ) : (
          <>
            <div data-animate className="flex items-center gap-3 mb-4">
              <span className="px-3 py-1 rounded-full border border-border-subtle bg-obsidian-light text-[10px] font-mono uppercase tracking-widest text-text-secondary flex items-center gap-2">
                <Activity className="w-3 h-3 text-champagne" />
                {FREQ_MAP[indicator?.frequency] || indicator?.frequency}
              </span>
              {indicator?.category && (
                <span className="text-xs font-mono text-text-tertiary">
                  {indicator.category}
                </span>
              )}
            </div>

            <h1 data-animate className="text-4xl md:text-5xl lg:text-6xl font-display font-bold tracking-tight mb-4 leading-tight">
              {indicator?.name || code}
            </h1>
            
            {indicator?.name_en && (
              <p data-animate className="text-sm md:text-base font-mono text-text-tertiary">
                {indicator.name_en}
              </p>
            )}
          </>
        )}
      </div>

      {variantGroup && (
        <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
          <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            {variantGroup.label}
          </p>
          <div className="flex flex-wrap gap-2">
            {variantGroup.codes.map(item => (
              <Link
                key={item.code}
                to={`/indicator/${item.code}`}
                className={cn(
                  'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
                  item.code === code
                    ? 'bg-champagne/15 text-champagne'
                    : 'bg-obsidian-lighter text-text-secondary hover:text-champagne'
                )}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </section>
      )}

      {isPriceCategory && (
        <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
          <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            Режим инфляции
          </p>
          <div className="flex flex-wrap gap-2">
            {cpiViewModes.map(item => (
              <button
                key={item.mode}
                type="button"
                onClick={() => {
                  setViewMode(item.mode);
                  track(events.CHART_MODE_CHANGE, { mode: item.mode, indicator: code, indicatorCategory: indicator?.category });
                }}
                className={cn(
                  'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
                  safeViewMode === item.mode
                    ? 'bg-champagne/15 text-champagne'
                    : 'bg-obsidian-lighter text-text-secondary hover:text-champagne'
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </section>
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
              {chartMode === 'inflation' ? INFLATION_DESCRIPTION
                : safeViewMode === 'quarterly' ? QUARTERLY_DESCRIPTION
                : safeViewMode === 'annual' ? ANNUAL_DESCRIPTION
                : safeViewMode === 'weekly' ? WEEKLY_DESCRIPTION
                : safeViewMode === 'cpi' && isPriceCategory ? CPI_MONTHLY_DESCRIPTION
                : indicator?.description}
            </p>
            {(chartMode === 'inflation' ? INFLATION_METHODOLOGY
              : safeViewMode === 'quarterly' ? QUARTERLY_METHODOLOGY
              : safeViewMode === 'annual' ? ANNUAL_METHODOLOGY
              : safeViewMode === 'weekly' ? WEEKLY_METHODOLOGY
              : safeViewMode === 'cpi' && isPriceCategory ? CPI_MONTHLY_METHODOLOGY
              : indicator?.methodology) && (
              <p className="text-text-tertiary border-l-2 border-champagne/30 pl-4 my-4 font-mono text-[10px] uppercase tracking-wider">
                {chartMode === 'inflation' ? INFLATION_METHODOLOGY
                  : safeViewMode === 'quarterly' ? QUARTERLY_METHODOLOGY
                  : safeViewMode === 'annual' ? ANNUAL_METHODOLOGY
                  : safeViewMode === 'weekly' ? WEEKLY_METHODOLOGY
                  : safeViewMode === 'cpi' && isPriceCategory ? CPI_MONTHLY_METHODOLOGY
                  : indicator?.methodology}
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
