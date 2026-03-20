import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import gsap from 'gsap';
import { ArrowLeft, ExternalLink, Activity, Info, TrendingUp, TrendingDown, Database, Terminal, Download } from 'lucide-react';
import {
  useIndicator, useIndicatorData, useIndicatorStats, useInflation, useForecast,
} from '../lib/hooks';
import { formatValue, formatDate, formatChange, cn } from '../lib/format';
import useDocumentMeta from '../lib/useMeta';
import CpiChart from '../components/CpiChart';
import ForecastTable from '../components/ForecastTable';
import DataTable from '../components/DataTable';
import { ChartSkeleton, SkeletonBox } from '../components/Skeleton';

const SEO_MAP = {
  cpi: {
    title: 'Индекс потребительских цен (ИПЦ) — прогноз и данные',
    description: 'ИПЦ России: исторические данные с 1991 года, скользящая 12-месячная инфляция, OLS-прогноз на 12 месяцев. Данные Росстата, обновление ежедневно.',
  },
  'cpi-food': {
    title: 'ИПЦ на продовольственные товары — прогноз и данные',
    description: 'Индекс потребительских цен на продовольствие: динамика, инфляция продовольственных товаров, OLS-прогноз. Данные Росстата с 1991 года.',
  },
  'cpi-nonfood': {
    title: 'ИПЦ на непродовольственные товары — прогноз и данные',
    description: 'Индекс цен на непродовольственные товары: динамика, инфляция, OLS-прогноз на 12 месяцев. Данные Росстата с 1991 года.',
  },
  'cpi-services': {
    title: 'ИПЦ на услуги — прогноз и данные',
    description: 'Индекс потребительских цен на услуги: динамика цен, инфляция в сфере услуг, OLS-прогноз. Данные Росстата с 1991 года.',
  },
  unemployment: {
    title: 'Уровень безработицы в России — данные и динамика',
    description:
      'Доля безработных в экономически активном населении: официальная статистика Росстата, история ряда, контекст для макроанализа.',
  },
  'key-rate': {
    title: 'Ключевая ставка ЦБ РФ — график и история',
    description:
      'Ключевая ставка Банка России: нерегулярный ряд решений ЦБ, визуализация и справка. Официальный источник — cbr.ru.',
  },
};

const FREQ_MAP = { monthly: 'Помесячно', quarterly: 'Ежеквартально', irregular: 'Нерегулярно' };

const INFLATION_DESCRIPTION =
  'Накопленная инфляция за 12 месяцев показывает, на сколько процентов выросли ' +
  'потребительские цены за последний год. Рассчитывается как произведение 12 ' +
  'последовательных месячных индексов ИПЦ минус 100%.';

const INFLATION_METHODOLOGY =
  'Формула: (∏ᵢ₌₁¹² ИПЦᵢ / 100) × 100 − 100, где ИПЦᵢ — индекс потребительских ' +
  'цен за i-й месяц в % к предыдущему месяцу.';

function TelemetryCard({ label, value, unit, change, meta, delay = 0 }) {
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
        <span ref={valRef} className="text-4xl md:text-5xl font-mono font-bold tracking-tight text-text-primary">
          {formatValue(value)}
        </span>
        <span className="text-sm font-medium text-text-tertiary">{unit}</span>
      </div>

      <div className="flex flex-col gap-1.5 mt-4 pt-4 border-t border-border-subtle/50">
        {changeNum != null && (
          <div className={cn(
            'flex items-center gap-1.5 text-xs font-mono font-medium',
            isUp ? 'text-negative' : '',
            isDown ? 'text-positive' : '',
            !isUp && !isDown ? 'text-text-tertiary' : ''
          )}>
            {isUp && <TrendingUp className="w-3.5 h-3.5" />}
            {isDown && <TrendingDown className="w-3.5 h-3.5" />}
            <span>Δ {formatChange(changeNum)}</span>
            <span className="text-text-tertiary text-[10px] uppercase tracking-wider ml-1">к пред. месяцу</span>
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

  const { data: indicator, isLoading: loadingInd } = useIndicator(code);
  const { data: dataResp, isLoading: loadingData } = useIndicatorData(code);
  const { data: stats } = useIndicatorStats(code);
  const { data: inflationResp, isLoading: loadingInflation } = useInflation(code);
  const { data: forecastResp } = useForecast(code);

  const inflationStats = useMemo(() => {
    if (viewMode !== 'inflation' || !inflationResp?.actuals?.length) return null;
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
  }, [viewMode, inflationResp]);

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

  const dataPoints = dataResp?.data || [];
  const s = inflationStats;
  const cpiPrevDate = dataPoints.length >= 2 ? dataPoints[dataPoints.length - 2].date : null;

  const handleChartData = useCallback((data) => {
    setChartData(data);
  }, []);

  const handleRangeChange = useCallback((range) => {
    setCurrentRange(range);
  }, []);

  const handleDownloadExcel = useCallback(async () => {
    const { downloadExcel } = await import('../lib/excel.js');
    downloadExcel(chartData, viewMode, code, currentRange);
  }, [chartData, viewMode, code, currentRange]);

  const chartLoading = viewMode === 'inflation' ? loadingInflation : loadingData;

  const hasForecastData = viewMode === 'inflation'
    ? inflationResp?.forecast?.length > 0
    : forecastResp?.forecast?.values?.length > 0;

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-32 pb-24">
      <div ref={headerRef} className="mb-12 md:mb-16 max-w-4xl">
        <Link
          to="/"
          data-animate
          className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary hover:text-champagne transition-colors mb-8 lift-hover group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          Обзор
        </Link>

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
              <span className="text-xs font-mono text-text-tertiary">
                ID: {indicator?.code.toUpperCase()}
              </span>
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
        {(loadingInd || (viewMode === 'inflation' && loadingInflation)) ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => <SkeletonBox key={i} className="h-48 rounded-[2rem]" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <TelemetryCard
              label="Текущее значение"
              value={s?.currentValue ?? indicator?.current_value}
              unit="%"
              change={s?.change ?? indicator?.change}
              meta={`ДАТА: ${formatDate(s?.currentDate ?? indicator?.current_date, 'full')}`}
              delay={0}
            />
            <TelemetryCard
              label="Предыдущий месяц"
              value={s?.previousValue ?? indicator?.previous_value}
              unit="%"
              meta={`ДАТА: ${formatDate(s?.previousDate ?? cpiPrevDate, 'full')}`}
              delay={1}
            />
            {(s?.highest || stats?.highest) && (
              <TelemetryCard
                label="Абсолютный максимум"
                value={s?.highest?.value ?? stats?.highest?.value}
                unit="%"
                meta={`ПИК: ${formatDate(s?.highest?.date ?? stats?.highest?.date, 'full')}`}
                delay={2}
              />
            )}
            {(s?.average != null || stats?.average != null) && (
              <TelemetryCard
                label="Среднее значение"
                value={s?.average ?? stats?.average}
                unit="%"
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
            <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
              <button
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
            </div>
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

            <label className="flex items-center gap-3 cursor-pointer group select-none">
              <span className="text-[10px] font-mono uppercase tracking-widest text-text-tertiary group-hover:text-text-secondary transition-colors">
                Прогноз
              </span>
              <div
                role="switch"
                aria-checked={showForecast}
                tabIndex={0}
                onClick={() => setShowForecast(v => !v)}
                onKeyDown={e => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); setShowForecast(v => !v); } }}
                className={cn(
                  'relative w-10 h-5 rounded-full transition-colors duration-300 cursor-pointer',
                  showForecast ? 'bg-champagne/30' : 'bg-obsidian-lighter border border-border-subtle'
                )}
              >
                <div className={cn(
                  'absolute top-[2px] left-[2px] w-4 h-4 rounded-full transition-transform duration-300',
                  showForecast ? 'translate-x-5 bg-champagne' : 'translate-x-0 bg-text-tertiary'
                )} />
              </div>
            </label>
          </div>
        </div>

        {chartLoading ? (
          <ChartSkeleton />
        ) : (
          <div className="relative overflow-hidden rounded-[2rem]">
            <CpiChart
              mode={viewMode}
              inflation={inflationResp}
              cpiData={dataPoints}
              forecastData={forecastResp}
              showForecast={showForecast}
              onChartData={handleChartData}
              onRangeChange={handleRangeChange}
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
              {viewMode === 'inflation' ? INFLATION_DESCRIPTION : indicator?.description}
            </p>
            {(viewMode === 'inflation' ? INFLATION_METHODOLOGY : indicator?.methodology) && (
              <p className="text-text-tertiary border-l-2 border-champagne/30 pl-4 my-4 font-mono text-[10px] uppercase tracking-wider">
                {viewMode === 'inflation' ? INFLATION_METHODOLOGY : indicator?.methodology}
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
          {showForecast && hasForecastData ? (
            <ForecastTable
              mode={viewMode}
              inflation={inflationResp}
              forecastData={forecastResp}
            />
          ) : (
            <div className="h-full min-h-[300px] rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center text-text-tertiary p-8">
              <Activity className="w-8 h-8 mb-4 opacity-20" />
              <p className="text-xs font-mono uppercase tracking-widest text-center">Прогноз отключён</p>
            </div>
          )}
        </section>
      </div>

      <section>
        <DataTable
          data={viewMode === 'inflation' ? (inflationResp?.actuals || []) : dataPoints}
          title={viewMode === 'inflation' ? 'Исторические данные — Инфляция 12 мес.' : 'Исторические данные — ИПЦ'}
        />
      </section>
    </div>
  );
}
