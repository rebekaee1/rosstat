import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import gsap from 'gsap';
import { ArrowLeft, ExternalLink, Activity, Info, TrendingUp, TrendingDown, Database, Terminal, Download } from 'lucide-react';
import {
  useIndicator, useIndicatorData, useIndicatorStats, useInflation, useForecast,
} from '../lib/hooks';
import { formatValue, formatDate, formatChange, unitSuffix, unitDigits, cn, isCpiIndex } from '../lib/format';
import { CATEGORIES } from '../lib/categories';
import useDocumentMeta from '../lib/useMeta';
import IndicatorChart from '../components/IndicatorChart';
import ForecastTable from '../components/ForecastTable';
import DataTable from '../components/DataTable';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { ChartSkeleton, SkeletonBox } from '../components/Skeleton';

const SEO_MAP = {
  cpi: {
    title: 'Индекс потребительских цен (ИПЦ) — прогноз и данные',
    description: 'ИПЦ России: исторические данные с 1991 года, скользящая 12-месячная инфляция, прогноз на 12 месяцев. Данные Росстата, обновление ежедневно.',
  },
  'cpi-food': {
    title: 'ИПЦ на продовольственные товары — прогноз и данные',
    description: 'Индекс потребительских цен на продовольствие: динамика, инфляция продовольственных товаров, прогноз. Данные Росстата с 1991 года.',
  },
  'cpi-nonfood': {
    title: 'ИПЦ на непродовольственные товары — прогноз и данные',
    description: 'Индекс цен на непродовольственные товары: динамика, инфляция, прогноз на 12 месяцев. Данные Росстата с 1991 года.',
  },
  'cpi-services': {
    title: 'ИПЦ на услуги — прогноз и данные',
    description: 'Индекс потребительских цен на услуги: динамика цен, инфляция в сфере услуг, прогноз. Данные Росстата с 1991 года.',
  },
  'key-rate': {
    title: 'Ключевая ставка ЦБ РФ — график и история',
    description: 'Ключевая ставка Банка России: ежедневный ряд, визуализация и справка. Источник — cbr.ru.',
  },
  'usd-rub': {
    title: 'Курс доллара к рублю (USD/RUB) — график и прогноз',
    description: 'Официальный курс доллара к рублю ЦБ РФ: ежедневные данные, история.',
  },
  'eur-rub': {
    title: 'Курс евро к рублю (EUR/RUB) — график и прогноз',
    description: 'Официальный курс евро к рублю ЦБ РФ: ежедневные данные, история.',
  },
  'cny-rub': {
    title: 'Курс юаня к рублю (CNY/RUB) — график и прогноз',
    description: 'Официальный курс юаня к рублю ЦБ РФ: ежедневные данные, история.',
  },
  ruonia: {
    title: 'Ставка RUONIA — график и динамика',
    description: 'RUONIA: индикативная ставка однодневных рублёвых межбанковских кредитов. Данные Банка России.',
  },
  m0: {
    title: 'Денежная масса М0 — график и прогноз',
    description: 'Наличные деньги в обращении (агрегат М0): данные Банка России, история.',
  },
  m2: {
    title: 'Денежная масса М2 — график и прогноз',
    description: 'Широкая денежная масса (агрегат М2): данные Банка России, история.',
  },
  'mortgage-rate': {
    title: 'Ставка по ипотеке — график и прогноз',
    description: 'Средневзвешенная ставка по ипотечным жилищным кредитам в рублях. Данные Банка России.',
  },
  'deposit-rate': {
    title: 'Ставка по вкладам — график и прогноз',
    description: 'Средневзвешенная ставка по вкладам физических лиц в рублях. Данные Банка России.',
  },
  'auto-loan-rate': {
    title: 'Ставка по автокредитам — график и прогноз',
    description: 'Средневзвешенная ставка по автокредитам физическим лицам в рублях. Данные Банка России.',
  },
  'inflation-quarterly': {
    title: 'Инфляция квартальная — график и данные',
    description: 'Квартальный индекс инфляции, рассчитанный на основе месячных ИПЦ Росстата.',
  },
  'inflation-annual': {
    title: 'Инфляция годовая — график и прогноз',
    description: 'Годовая инфляция: скользящий 12-месячный показатель роста цен. Расчёт на основе ИПЦ.',
  },
  'unemployment': {
    title: 'Уровень безработицы в России — данные и прогноз',
    description: 'Безработица по методологии МОТ: ежемесячные данные с 2015 года, динамика. Данные Росстата.',
  },
  'wages-nominal': {
    title: 'Средняя заработная плата в России — данные и прогноз',
    description: 'Среднемесячная номинальная начисленная зарплата: ежемесячные данные, динамика. Данные Росстата.',
  },
  'wages-real': {
    title: 'Реальная заработная плата — индекс и динамика',
    description: 'Индекс реальной заработной платы с учётом инфляции. Расчёт: номинальная зарплата / ИПЦ.',
  },
  'gdp-nominal': {
    title: 'ВВП России — номинальный, квартальные данные',
    description: 'Валовой внутренний продукт России в текущих ценах: квартальные данные с 2011 года, прогноз. Данные Росстата.',
  },
  'gdp-yoy': {
    title: 'Рост ВВП России (год к году) — данные',
    description: 'Темп роста номинального ВВП к аналогичному кварталу прошлого года. Расчёт на основе данных Росстата.',
  },
  'gdp-qoq': {
    title: 'Рост ВВП России (квартал к кварталу) — данные',
    description: 'Темп роста номинального ВВП к предыдущему кварталу. Расчёт на основе данных Росстата.',
  },
  m1: {
    title: 'Денежная масса М1 — график и прогноз',
    description: 'Денежный агрегат М1 (наличные + переводные депозиты): данные Банка России, история.',
  },
  'consumer-credit': {
    title: 'Кредиты физическим лицам — данные и прогноз',
    description: 'Задолженность по кредитам физлицам (портфель): данные Банка России, динамика, прогноз.',
  },
  'business-credit': {
    title: 'Кредиты бизнесу — данные и прогноз',
    description: 'Задолженность по кредитам юрлицам и ИП (портфель): данные Банка России, динамика, прогноз.',
  },
  'deposits-individual': {
    title: 'Вклады физических лиц — данные и прогноз',
    description: 'Суммарные вклады населения в банках РФ: данные Банка России, история.',
  },
  'deposits-business': {
    title: 'Депозиты организаций — данные и прогноз',
    description: 'Суммарные депозиты нефинансовых организаций: данные Банка России, история, прогноз.',
  },
  'budget-deficit': {
    title: 'Дефицит бюджета России — данные и прогноз',
    description: 'Помесячный дефицит/профицит федерального бюджета РФ: данные Минфина, история с 2011 года.',
  },
  'inflation-weekly': {
    title: 'Недельная инфляция — данные Росстата',
    description: 'ИПЦ за неделю (к предыдущей неделе): еженедельные данные Росстата по ценам.',
  },
  'unemployment-quarterly': {
    title: 'Безработица квартальная — данные',
    description: 'Средний уровень безработицы за квартал: расчёт на основе месячных данных Росстата.',
  },
  'unemployment-annual': {
    title: 'Безработица среднегодовая — данные',
    description: 'Скользящее среднее безработицы за 12 месяцев: расчёт на основе данных Росстата.',
  },
};

const FREQ_MAP = {
  monthly: 'Помесячно',
  quarterly: 'Ежеквартально',
  weekly: 'Еженедельно',
  irregular: 'Нерегулярно',
  daily: 'По дням',
};

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

function TelemetryCard({
  label, value, unit, change, meta, delay = 0,
  deltaSuffix = 'к пред. месяцу',
}) {
  const ref = useRef(null);
  const valRef = useRef(null);
  const animated = useRef(false);
  
  useEffect(() => {
    if (animated.current || !ref.current) return;
    animated.current = true;
    gsap.fromTo(ref.current,
      { y: 20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out', delay: 0.4 + delay * 0.1 }
    );
  }, [delay]);

  useEffect(() => {
    if (value == null || !valRef.current) return;
    const from = parseFloat(valRef.current.textContent) || 0;
    gsap.fromTo(valRef.current,
      { textContent: from },
      {
        textContent: Number(value),
        duration: from === 0 ? 1.5 : 0.6,
        ease: 'power2.out',
        delay: from === 0 ? 0.2 : 0,
        snap: { textContent: 0.01 },
        onUpdate() {
          if (valRef.current) {
            valRef.current.textContent = Number(valRef.current.textContent).toFixed(2);
          }
        },
      }
    );
  }, [value]);

  const changeNum = change != null ? Number(change) : null;
  const isUp = changeNum != null && changeNum > 0;
  const isDown = changeNum != null && changeNum < 0;

  return (
    <div ref={ref} className="group relative p-6 rounded-[2rem] bg-surface border border-border-subtle hover:border-champagne/30 transition-colors duration-500 overflow-hidden lift-hover">
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-champagne/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
      
      <p className="text-[10px] uppercase tracking-widest text-text-tertiary font-medium mb-4">
        {label}
      </p>

      <div className="flex items-baseline gap-2 mb-2">
        <span ref={valRef} className={cn(
          'font-mono font-bold tracking-tight text-text-primary',
          String(formatValue(value, unitDigits(unit))).length > 8 ? 'text-2xl md:text-3xl' : 'text-4xl md:text-5xl'
        )}>
          {formatValue(value, unitDigits(unit))}
        </span>
        <span className="text-sm font-medium text-text-tertiary">{unitSuffix(unit)}</span>
      </div>

      <div className="flex flex-col gap-1.5 mt-4 pt-4 border-t border-border-subtle/50">
        {changeNum != null && (
          <div className={cn(
            'flex items-center gap-1.5 text-xs font-mono font-medium',
            isUp ? 'text-positive' : '',
            isDown ? 'text-negative' : '',
            !isUp && !isDown ? 'text-text-tertiary' : ''
          )}>
            {isUp && <TrendingUp className="w-3.5 h-3.5" />}
            {isDown && <TrendingDown className="w-3.5 h-3.5" />}
            <span>Δ {formatChange(changeNum)}</span>
            <span className="text-text-tertiary text-[10px] uppercase tracking-wider ml-1">
              {deltaSuffix}
            </span>
          </div>
        )}
        {meta && (
          <div className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
            {meta}
          </div>
        )}
      </div>
    </div>
  );
}

export default function IndicatorDetail() {
  const { code } = useParams();
  const headerRef = useRef(null);
  const [showForecast, setShowForecast] = useState(true);
  const [viewMode, setViewMode] = useState('inflation');
  const [chartData, setChartData] = useState([]);
  const [currentRange, setCurrentRange] = useState('5y');

  const seo = SEO_MAP[code] || {};
  useDocumentMeta({
    title: seo.title || `Индикатор ${code}`,
    description: seo.description,
    path: `/indicator/${code}`,
  });

  const {
    data: indicator,
    isLoading: loadingInd,
    isError: indError,
    error: indErr,
    refetch: refetchInd,
    isFetching: fetchingInd,
  } = useIndicator(code);
  const CPI_CODES = ['cpi', 'cpi-food', 'cpi-nonfood', 'cpi-services'];
  const isPriceCategory = CPI_CODES.includes(code);
  const canForecast = indicator?.category === 'Цены';
  const shouldSubtract100 = isCpiIndex(code);
  const {
    data: dataResp,
    isLoading: loadingData,
    isError: dataError,
    refetch: refetchData,
    isFetching: fetchingData,
  } = useIndicatorData(code);
  const { data: stats } = useIndicatorStats(code);
  const { data: inflationResp, isLoading: loadingInflation } = useInflation(code, {
    enabled: isPriceCategory,
  });
  const { data: forecastResp } = useForecast(code);

  const hasQuarterlyTab = code === 'cpi';
  const {
    data: quarterlyResp,
    isLoading: loadingQuarterly,
  } = useIndicatorData('inflation-quarterly', undefined, {
    enabled: hasQuarterlyTab && viewMode === 'quarterly',
  });

  const chartMode = isPriceCategory ? viewMode : 'cpi';

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
    window.scrollTo(0, 0);
    const els = headerRef.current?.querySelectorAll('[data-animate]');
    if (els?.length) {
      gsap.fromTo(els,
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 1, ease: 'power3.out', stagger: 0.1 }
      );
    }
  }, []);

  const rawDataPoints = useMemo(
    () => (Array.isArray(dataResp?.data) ? dataResp.data : []),
    [dataResp?.data],
  );

  const dataPoints = useMemo(() => {
    if (!shouldSubtract100 || !rawDataPoints.length) return rawDataPoints;
    return rawDataPoints.map(p => ({ ...p, value: Number(p.value) - 100 }));
  }, [rawDataPoints, shouldSubtract100]);

  const displayForecastData = useMemo(() => {
    if (!shouldSubtract100 || !forecastResp?.forecast?.values?.length) return forecastResp;
    return {
      ...forecastResp,
      forecast: {
        ...forecastResp.forecast,
        values: forecastResp.forecast.values.map(v => ({
          ...v,
          value: Number(v.value) - 100,
        })),
      },
    };
  }, [forecastResp, shouldSubtract100]);

  const adj = useCallback((v) => {
    if (v == null || !shouldSubtract100) return v;
    return Number(v) - 100;
  }, [shouldSubtract100]);

  const quarterlyDataPoints = useMemo(() => {
    if (!quarterlyResp?.data?.length) return [];
    return quarterlyResp.data.map(p => ({ ...p, value: Number(p.value) - 100 }));
  }, [quarterlyResp]);

  const quarterlyStats = useMemo(() => {
    if (viewMode !== 'quarterly' || !quarterlyDataPoints.length) return null;
    const a = quarterlyDataPoints;
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
  }, [viewMode, quarterlyDataPoints]);

  const s = viewMode === 'quarterly' ? quarterlyStats : inflationStats;
  const cpiPrevDate = dataPoints.length >= 2 ? dataPoints[dataPoints.length - 2].date : null;

  const handleChartData = useCallback((data) => {
    setChartData(data);
  }, []);

  const handleRangeChange = useCallback((range) => {
    setCurrentRange(range);
  }, []);

  const handleDownloadExcel = useCallback(async () => {
    const { downloadExcel } = await import('../lib/excel.js');
    downloadExcel(chartData, chartMode, code, currentRange);
  }, [chartData, chartMode, code, currentRange]);

  const chartLoading = chartMode === 'inflation' ? loadingInflation
    : chartMode === 'quarterly' ? loadingQuarterly
    : loadingData;

  const hasForecastData = chartMode === 'quarterly'
    ? false
    : chartMode === 'inflation'
      ? inflationResp?.forecast?.length > 0
      : displayForecastData?.forecast?.values?.length > 0;

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
  }, [refetchInd, refetchData]);

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
              {indicator?.name}
            </h1>
            
            {indicator?.name_en && (
              <p data-animate className="text-sm md:text-base font-mono text-text-tertiary">
                {indicator.name_en}
              </p>
            )}
          </>
        )}
      </div>

      <section className="mb-12">
        {(loadingInd || (chartMode === 'inflation' && loadingInflation)) ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => <SkeletonBox key={i} className="h-48 rounded-[2rem]" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <TelemetryCard
              label="Текущее значение"
              value={s?.currentValue ?? adj(indicator?.current_value)}
              unit={indicator?.unit || '%'}
              change={s?.change ?? indicator?.change}
              meta={`ДАТА: ${formatDate(s?.currentDate ?? indicator?.current_date, 'full')}`}
              delay={0}
              deltaSuffix={isPriceCategory ? 'к пред. месяцу' : 'к пред. значению'}
            />
            <TelemetryCard
              label={isPriceCategory ? 'Предыдущий месяц' : 'Предыдущее значение'}
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
            {isPriceCategory ? (
              <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
                <button
                  type="button"
                  onClick={() => setViewMode('inflation')}
                  className={cn(
                    'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                    viewMode === 'inflation'
                      ? 'bg-champagne/15 text-champagne'
                      : 'text-text-tertiary hover:text-text-secondary'
                  )}
                >
                  Инфляция 12 мес.
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('cpi')}
                  className={cn(
                    'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                    viewMode === 'cpi'
                      ? 'bg-champagne/15 text-champagne'
                      : 'text-text-tertiary hover:text-text-secondary'
                  )}
                >
                  ИПЦ помесячно
                </button>
                {hasQuarterlyTab && (
                  <button
                    type="button"
                    onClick={() => setViewMode('quarterly')}
                    className={cn(
                      'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                      viewMode === 'quarterly'
                        ? 'bg-champagne/15 text-champagne'
                        : 'text-text-tertiary hover:text-text-secondary'
                    )}
                  >
                    Квартальная
                  </button>
                )}
              </div>
            ) : (
              <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">
                Динамика показателя
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleDownloadExcel}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30 transition-colors text-xs font-mono uppercase tracking-wider magnetic-btn"
              title="Скачать Excel"
            >
              <Download className="w-3.5 h-3.5" />
              Excel
            </button>

            {viewMode !== 'quarterly' && (
              <div className="relative group">
                <label className={cn(
                  'flex items-center gap-3 select-none',
                  canForecast ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'
                )}>
                  <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary group-hover:text-text-secondary transition-colors">
                    Прогноз
                  </span>
                  <div
                    role="switch"
                    aria-checked={canForecast && showForecast}
                    tabIndex={canForecast ? 0 : -1}
                    onClick={() => canForecast && setShowForecast(v => !v)}
                    onKeyDown={e => { if (canForecast && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); setShowForecast(v => !v); } }}
                    className={cn(
                      'relative w-10 h-5 rounded-full transition-colors duration-300',
                      canForecast ? 'cursor-pointer' : 'cursor-not-allowed',
                      canForecast && showForecast ? 'bg-champagne/30' : 'bg-obsidian-lighter border border-border-subtle'
                    )}
                  >
                    <div className={cn(
                      'absolute top-[2px] left-[2px] w-4 h-4 rounded-full transition-transform duration-300',
                      canForecast && showForecast ? 'translate-x-5 bg-champagne' : 'translate-x-0 bg-text-tertiary'
                    )} />
                  </div>
                </label>
                {!canForecast && (
                  <div className="absolute top-full right-0 mt-2 px-3 py-2 rounded-xl bg-obsidian border border-border-subtle text-xs text-text-secondary whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none shadow-xl z-50">
                    Прогноз скоро будет доступен
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {chartLoading ? (
          <ChartSkeleton />
        ) : (
          <div className="relative overflow-hidden rounded-[2rem]">
            <IndicatorChart
              key={`${indicator?.code}-${chartMode}`}
              mode={chartMode === 'quarterly' ? 'cpi' : chartMode}
              inflation={inflationResp}
              cpiData={chartMode === 'quarterly' ? quarterlyDataPoints : dataPoints}
              forecastData={chartMode === 'quarterly' ? null : displayForecastData}
              showForecast={chartMode !== 'quarterly' && canForecast && showForecast}
              onChartData={handleChartData}
              onRangeChange={handleRangeChange}
              referenceLineY={isPriceCategory ? undefined : null}
              cpiChartTitle={
                chartMode === 'quarterly'
                  ? 'Квартальная инфляция (%)'
                  : isPriceCategory
                    ? undefined
                    : `${indicator?.name || 'Показатель'} (${unitSuffix(indicator?.unit)})`
              }
              levelTooltipLabel={chartMode === 'quarterly' ? 'Кв. инфляция' : isPriceCategory ? undefined : 'Значение'}
              emptyHint={chartEmptyHint}
              dateFormat={chartMode !== 'inflation' && indicator?.frequency === 'daily' ? 'day' : 'full'}
              unit={indicator?.unit || '%'}
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
                : viewMode === 'quarterly' ? QUARTERLY_DESCRIPTION
                : indicator?.description}
            </p>
            {(chartMode === 'inflation' ? INFLATION_METHODOLOGY
              : viewMode === 'quarterly' ? QUARTERLY_METHODOLOGY
              : indicator?.methodology) && (
              <p className="text-text-tertiary border-l-2 border-champagne/30 pl-4 my-4 font-mono text-[10px] uppercase tracking-wider">
                {chartMode === 'inflation' ? INFLATION_METHODOLOGY
                  : viewMode === 'quarterly' ? QUARTERLY_METHODOLOGY
                  : indicator?.methodology}
              </p>
            )}
          </div>
          
          <div className="mt-auto pt-6 border-t border-border-subtle">
            <a
              href={indicator?.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-surface border border-border-subtle text-xs font-mono uppercase tracking-widest text-champagne hover:bg-champagne/10 transition-colors lift-hover w-full justify-center"
            >
              <Database className="w-3.5 h-3.5" />
              Источник: {indicator?.source}
              <ExternalLink className="w-3 h-3 ml-auto opacity-50" />
            </a>
          </div>
        </section>

        <section className="lg:col-span-2">
          {viewMode === 'quarterly' ? (
            <div className="h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center gap-3 text-text-tertiary p-8">
              <Activity className="w-8 h-8 mb-1 opacity-20" />
              <p className="text-sm font-medium text-text-secondary text-center max-w-md">
                Квартальные данные рассчитываются на основе месячных значений ИПЦ
              </p>
              <p className="text-xs text-center max-w-lg leading-relaxed text-text-tertiary">
                Прогнозирование квартальной инфляции не предусмотрено — для прогноза переключитесь на помесячный или годовой режим
              </p>
            </div>
          ) : canForecast && showForecast && hasForecastData ? (
            <ForecastTable
              mode={chartMode}
              inflation={inflationResp}
              forecastData={displayForecastData}
              unit={indicator?.unit || '%'}
            />
          ) : canForecast && !showForecast ? (
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
                Для ступенчатых рядов (ключевая ставка) и показателей без модели прогноз может отсутствовать — это ожидаемо.
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
            : dataPoints
          }
          title={
            chartMode === 'inflation'
              ? 'Исторические данные — Инфляция 12 мес.'
              : chartMode === 'quarterly'
                ? 'Исторические данные — Квартальная инфляция'
                : (isPriceCategory ? 'Исторические данные — ИПЦ' : `Исторические данные — ${indicator?.name || 'ряд'}`)
          }
          dateFormat={chartMode !== 'inflation' && indicator?.frequency === 'daily' ? 'day' : 'full'}
          unit={indicator?.unit || '%'}
        />
      </section>
    </div>
  );
}
