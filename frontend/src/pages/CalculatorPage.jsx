import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import gsap from 'gsap';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';
import { ArrowLeft, Share2, Copy, Check, ChevronDown, Calculator, TrendingDown, ShoppingCart, Package, Wrench } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import useInflationCalc from '../lib/useInflationCalc';
import { formatDate, formatAxisTick, cn } from '../lib/format';
import { FOCUS_RING, FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { SkeletonBox } from '../components/Skeleton';

const PRESETS = [
  { label: '1 год', offset: 1 },
  { label: '5 лет', offset: 5 },
  { label: '10 лет', offset: 10 },
  { label: 'С 2000', from: 2000 },
  { label: 'Всё время', from: null },
];

const MILESTONES = [
  { year: 1998, label: 'Дефолт' },
  { year: 2008, label: 'Кризис' },
  { year: 2014, label: 'Санкции' },
  { year: 2020, label: 'COVID' },
  { year: 2022, label: 'Санкции' },
];

const FAQ_ITEMS = [
  {
    q: 'Как рассчитывается инфляция?',
    a: 'Инфляция рассчитывается на основе индекса потребительских цен (ИПЦ), который ежемесячно публикует Росстат. ИПЦ показывает, на сколько процентов изменилась стоимость фиксированной потребительской корзины из ~500 товаров и услуг.',
  },
  {
    q: 'Что такое ИПЦ?',
    a: 'ИПЦ (индекс потребительских цен) — основной показатель инфляции. Значение 100.73 означает рост цен на 0.73% за месяц. Росстат публикует ИПЦ отдельно для продуктов, непродовольственных товаров и услуг.',
  },
  {
    q: 'Почему моя личная инфляция отличается от официальной?',
    a: 'Официальный ИПЦ рассчитывается по усреднённой корзине. Ваша структура расходов может отличаться: если тратите больше на еду — ваша инфляция будет ближе к продовольственному ИПЦ, который обычно выше общего.',
  },
  {
    q: 'Как защитить сбережения от инфляции?',
    a: 'Основные инструменты: банковские вклады (ставки обычно близки к инфляции), ОФЗ-ИН (индексируются на инфляцию), недвижимость, акции. Хранение наличных — гарантированная потеря покупательной способности.',
  },
  {
    q: 'Какой была максимальная инфляция в России?',
    a: '2 508% в 1992 году (переход к рыночной экономике). В более позднее время: 131% в 1995, 84% в 1998 (дефолт), 12% в 2022. Цель ЦБ РФ — 4% в год.',
  },
  {
    q: 'Откуда берутся данные?',
    a: 'Все данные — официальные значения ИПЦ Росстата (Федеральной службы государственной статистики) с января 1991 года по текущий месяц. Обновляются ежедневно.',
  },
];

function formatRubles(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  const abs = Math.abs(Math.round(n));
  const sign = n < 0 ? '-' : '';
  return sign + abs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0') + ' ₽';
}

function parseAmount(str) {
  const cleaned = str.replace(/[^\d]/g, '');
  return cleaned ? parseInt(cleaned, 10) : 0;
}

function formatInput(n) {
  if (!n || n <= 0) return '';
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

function AnimatedNumber({ value, prefix = '', suffix = '', className }) {
  const ref = useRef(null);
  const prevRef = useRef(value);

  useEffect(() => {
    if (!ref.current || value == null) return;
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      ref.current.textContent = formatRubles(value);
      return;
    }
    const counter = { v: prevRef.current ?? 0 };
    const tween = gsap.to(counter, {
      v: value,
      duration: prevRef.current === 0 || prevRef.current == null ? 1.2 : 0.5,
      ease: 'power2.out',
      onUpdate() {
        if (ref.current) ref.current.textContent = formatRubles(Math.round(counter.v));
      },
    });
    prevRef.current = value;
    return () => tween.kill();
  }, [value]);

  return (
    <span className={className}>
      {prefix}<span ref={ref}>{formatRubles(value)}</span>{suffix}
    </span>
  );
}

function YearSlider({ value, onChange, min, max, label, ariaLabel }) {
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary">{label}</span>
        <span className="text-sm font-mono font-bold text-text-primary tabular-nums">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        aria-label={ariaLabel}
        className="calc-slider w-full"
      />
    </div>
  );
}

function CategoryCard({ icon: Icon, label, rate, color }) {
  const formatted = rate != null && Number.isFinite(rate)
    ? `${rate >= 0 ? '+' : ''}${rate.toFixed(1)}%`
    : '—';

  return (
    <div className="flex items-center gap-3 p-4 rounded-2xl bg-obsidian-light border border-border-subtle">
      <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-surface border border-border-subtle shrink-0">
        <Icon className="w-4 h-4 text-text-tertiary" />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium truncate">{label}</p>
        <p className={cn('text-lg font-mono font-bold tabular-nums', color)}>{formatted}</p>
      </div>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  if (p?.value == null) return null;

  return (
    <div className="glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl min-w-[180px]">
      <p className="text-xs font-mono text-text-tertiary mb-1.5">{formatDate(label, 'full')}</p>
      <p className="text-sm font-mono font-semibold text-champagne">{formatRubles(p.value)}</p>
    </div>
  );
}

function FAQAccordion() {
  const [open, setOpen] = useState(null);

  return (
    <div className="divide-y divide-border-subtle border-t border-b border-border-subtle">
      {FAQ_ITEMS.map((item, i) => (
        <div key={i}>
          <button
            type="button"
            onClick={() => setOpen(open === i ? null : i)}
            className={cn(
              FOCUS_RING,
              'w-full flex items-center justify-between gap-4 py-5 text-left rounded-sm'
            )}
            aria-expanded={open === i}
          >
            <span className="text-sm font-medium text-text-primary">{item.q}</span>
            <ChevronDown className={cn(
              'w-4 h-4 text-text-tertiary shrink-0 transition-transform duration-200',
              open === i && 'rotate-180'
            )} />
          </button>
          {open === i && (
            <p className="pb-5 text-sm text-text-secondary leading-relaxed -mt-1">{item.a}</p>
          )}
        </div>
      ))}
    </div>
  );
}

export default function CalculatorPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentYear = new Date().getFullYear();
  const containerRef = useRef(null);

  const [amount, setAmount] = useState(() => {
    const p = searchParams.get('amount');
    return p ? parseInt(p, 10) || 100000 : 100000;
  });
  const [fromYear, setFromYear] = useState(() => {
    const p = searchParams.get('from');
    return p ? parseInt(p, 10) || currentYear - 10 : currentYear - 10;
  });
  const [toYear, setToYear] = useState(() => {
    const p = searchParams.get('to');
    return p ? parseInt(p, 10) || currentYear : currentYear;
  });
  const [copied, setCopied] = useState(false);
  const [chartMode, setChartMode] = useState('purchasing');

  const { result, isLoading, isError, lastAvailableYear, minYear } = useInflationCalc(amount, fromYear, toYear);

  const effectiveMax = lastAvailableYear || currentYear;
  const effectiveMin = minYear || 1991;

  useDocumentMeta({
    title: 'Калькулятор инфляции в России — покупательная способность рубля с 1991 года',
    description: `Рассчитайте инфляцию в России за любой период с ${effectiveMin} по ${effectiveMax} год. Официальные данные ИПЦ Росстата, мгновенный расчёт, разбивка по категориям.`,
    path: '/calculator',
  });

  useEffect(() => {
    if (!containerRef.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const els = containerRef.current.querySelectorAll('[data-animate]');
    if (!els.length) return;
    const tween = gsap.fromTo(els,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.9, ease: 'power3.out', stagger: 0.08 }
    );
    return () => tween.kill();
  }, []);

  const handleFromYear = useCallback((v) => {
    setFromYear(Math.min(v, toYear - 1));
  }, [toYear]);

  const handleToYear = useCallback((v) => {
    setToYear(Math.max(v, fromYear + 1));
  }, [fromYear]);

  const handlePreset = useCallback((preset) => {
    if (preset.from != null) {
      setFromYear(Math.max(preset.from, effectiveMin));
    } else if (preset.from === null) {
      setFromYear(effectiveMin);
    } else {
      setFromYear(Math.max(effectiveMax - preset.offset, effectiveMin));
    }
    setToYear(effectiveMax);
  }, [effectiveMin, effectiveMax]);

  const handleShare = useCallback(async () => {
    const params = new URLSearchParams({ amount: String(amount), from: String(fromYear), to: String(toYear) });
    setSearchParams(params, { replace: true });
    const url = `${window.location.origin}/calculator?${params}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard unavailable */ }
  }, [amount, fromYear, toYear, setSearchParams]);

  const handleCopyText = useCallback(async () => {
    if (!result) return;
    const text = `${formatInput(amount)} ₽ в ${fromYear} году эквивалентны ${formatRubles(result.equivalent)} в ${toYear} году (инфляция ${result.totalInflation.toFixed(1)}%). Рассчитано на forecasteconomy.com/calculator`;
    try { await navigator.clipboard.writeText(text); } catch { /* ok */ }
  }, [result, amount, fromYear, toYear]);

  const chartData = useMemo(() => {
    if (!result?.series?.length) return [];
    return result.series.map(p => ({
      date: p.date,
      value: chartMode === 'purchasing' ? p.purchasing : p.equivalent,
    }));
  }, [result, chartMode]);

  const { yDomain, yTicks, yWidth } = useMemo(() => {
    if (!chartData.length) return { yDomain: ['auto', 'auto'], yTicks: undefined, yWidth: 55 };
    let min = Infinity, max = -Infinity;
    for (const row of chartData) {
      if (row.value != null) { min = Math.min(min, row.value); max = Math.max(max, row.value); }
    }
    if (!isFinite(min)) return { yDomain: ['auto', 'auto'], yTicks: undefined, yWidth: 55 };
    const span = max - min || 1;
    const rough = span / 5;
    const pow = Math.pow(10, Math.floor(Math.log10(rough)));
    const frac = rough / pow;
    const step = frac <= 1.5 ? pow : frac <= 3.5 ? 2 * pow : frac <= 7.5 ? 5 * pow : 10 * pow;
    const niceMin = Math.floor(min / step) * step;
    const niceMax = Math.ceil(max / step) * step;
    const ticks = [];
    for (let v = niceMin; v <= niceMax + step * 0.01; v += step) ticks.push(Math.round(v));
    const sampleLabel = formatAxisTick(niceMax, 0);
    const w = Math.max(50, Math.min(100, sampleLabel.length * 8 + 16));
    return { yDomain: [niceMin, niceMax], yTicks: ticks, yWidth: w };
  }, [chartData]);

  const visibleMilestones = useMemo(() => {
    return MILESTONES.filter(m => m.year > fromYear && m.year < toYear);
  }, [fromYear, toYear]);

  const isActivePreset = useCallback((preset) => {
    const target = preset.from != null
      ? Math.max(preset.from, effectiveMin)
      : preset.from === null
        ? effectiveMin
        : Math.max(effectiveMax - preset.offset, effectiveMin);
    return fromYear === target && toYear === effectiveMax;
  }, [fromYear, toYear, effectiveMin, effectiveMax]);

  const extremeInflation = result && result.totalInflation > 200;

  const faqJsonLd = useMemo(() => ({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQ_ITEMS.map(item => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: item.a },
    })),
  }), []);

  const webAppJsonLd = useMemo(() => ({
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: 'Калькулятор инфляции в России',
    url: 'https://forecasteconomy.com/calculator',
    description: 'Рассчитайте кумулятивную инфляцию и покупательную способность рубля с 1991 года по данным ИПЦ Росстата.',
    applicationCategory: 'FinanceApplication',
    operatingSystem: 'All',
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'RUB' },
    creator: { '@type': 'Organization', name: 'Forecast Economy', url: 'https://forecasteconomy.com' },
  }), []);

  useEffect(() => {
    let faqScript = document.getElementById('calc-faq-ld');
    if (!faqScript) {
      faqScript = document.createElement('script');
      faqScript.id = 'calc-faq-ld';
      faqScript.type = 'application/ld+json';
      document.head.appendChild(faqScript);
    }
    faqScript.textContent = JSON.stringify(faqJsonLd);

    let appScript = document.getElementById('calc-app-ld');
    if (!appScript) {
      appScript = document.createElement('script');
      appScript.id = 'calc-app-ld';
      appScript.type = 'application/ld+json';
      document.head.appendChild(appScript);
    }
    appScript.textContent = JSON.stringify(webAppJsonLd);

    return () => {
      document.getElementById('calc-faq-ld')?.remove();
      document.getElementById('calc-app-ld')?.remove();
    };
  }, [faqJsonLd, webAppJsonLd]);

  return (
    <div ref={containerRef} className="max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24">

      {/* ── Breadcrumb ── */}
      <nav data-animate className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary mb-8">
        <Link to="/" className="hover:text-champagne transition-colors lift-hover inline-flex items-center gap-1.5 group">
          <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
          Главная
        </Link>
        <span className="text-text-tertiary/40">/</span>
        <span className="text-text-secondary">Калькулятор</span>
      </nav>

      {/* ── Hero ── */}
      <header data-animate className="mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-2xl bg-champagne/10 border border-champagne/20">
            <Calculator className="w-5 h-5 text-champagne" />
          </div>
          <span className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold">
            Данные ИПЦ Росстата с 1991 года
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold tracking-tight text-text-primary leading-tight mb-3">
          Калькулятор инфляции
        </h1>
        <p className="text-base text-text-secondary leading-relaxed max-w-xl">
          Узнайте, как изменилась покупательная способность рубля. Мгновенный расчёт
          по официальным данным Росстата с разбивкой по категориям товаров и услуг.
        </p>
      </header>

      {/* ── Calculator Card ── */}
      <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6">

        {/* Amount */}
        <div className="mb-6">
          <label htmlFor="calc-amount" className="block text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary mb-2">
            Сумма
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-xl text-text-tertiary font-display pointer-events-none" aria-hidden>₽</span>
            <input
              id="calc-amount"
              type="text"
              inputMode="numeric"
              value={formatInput(amount)}
              onChange={e => setAmount(parseAmount(e.target.value))}
              placeholder="100 000"
              className={cn(
                FOCUS_RING_SURFACE,
                'w-full pl-10 pr-4 py-4 rounded-2xl bg-obsidian border border-border-subtle',
                'text-2xl md:text-3xl font-display font-bold text-text-primary tabular-nums',
                'placeholder:text-text-tertiary/40 placeholder:font-normal',
                'transition-colors hover:border-champagne/20'
              )}
            />
          </div>
        </div>

        {/* Year Sliders */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          <YearSlider
            label="Из года"
            value={fromYear}
            min={effectiveMin}
            max={effectiveMax - 1}
            onChange={handleFromYear}
            ariaLabel="Начальный год"
          />
          <YearSlider
            label="В год"
            value={toYear}
            min={effectiveMin + 1}
            max={effectiveMax}
            onChange={handleToYear}
            ariaLabel="Конечный год"
          />
        </div>

        {/* Presets */}
        <div className="flex flex-wrap gap-2">
          {PRESETS.map(p => (
            <button
              key={p.label}
              type="button"
              onClick={() => handlePreset(p)}
              className={cn(
                FOCUS_RING_SURFACE,
                'px-3.5 py-1.5 rounded-full text-xs font-medium transition-all duration-200',
                isActivePreset(p)
                  ? 'bg-champagne/12 text-champagne ring-1 ring-champagne/25'
                  : 'bg-obsidian border border-border-subtle text-text-tertiary hover:text-text-secondary hover:border-champagne/15'
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </section>

      {/* ── Result ── */}
      {isLoading && (
        <div data-animate className="rounded-[2rem] bg-surface border border-border-subtle p-8 mb-6">
          <SkeletonBox className="h-6 w-48 mb-4" />
          <SkeletonBox className="h-14 w-72 mb-4" />
          <SkeletonBox className="h-4 w-56" />
        </div>
      )}

      {isError && !isLoading && (
        <div className="rounded-[2rem] bg-warn-surface border border-champagne/35 p-6 mb-6 text-sm text-warn-text">
          Не удалось загрузить данные ИПЦ. Проверьте соединение и обновите страницу.
        </div>
      )}

      {result && !isLoading && (
        <>
          <section
            data-animate
            className={cn(
              'rounded-[2rem] border p-6 md:p-8 mb-6 transition-colors duration-500',
              extremeInflation
                ? 'bg-negative/[0.03] border-negative/20'
                : 'bg-surface border-border-champagne'
            )}
            aria-live="polite"
          >
            <p className="text-sm text-text-secondary mb-2">
              {formatInput(amount)} ₽ в {fromYear} году — это
            </p>

            <AnimatedNumber
              value={result.equivalent}
              className={cn(
                'block font-display font-bold tracking-tight mb-1',
                extremeInflation
                  ? 'text-negative text-3xl md:text-4xl lg:text-5xl'
                  : 'text-text-primary text-4xl md:text-5xl lg:text-6xl'
              )}
            />

            <p className="text-sm text-text-secondary mb-6">
              в {toYear} году
            </p>

            {/* Stat pills */}
            <div className="flex flex-wrap gap-3 mb-6">
              <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
                <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">Инфляция</p>
                <p className="text-base font-mono font-bold text-text-primary tabular-nums">
                  +{result.totalInflation.toFixed(1)}%
                </p>
              </div>
              <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
                <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">Среднегодовая</p>
                <p className="text-base font-mono font-bold text-text-primary tabular-nums">
                  {result.avgAnnual.toFixed(1)}%
                </p>
              </div>
              <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
                <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">Покупательная сила</p>
                <p className="text-base font-mono font-bold text-negative tabular-nums">
                  <TrendingDown className="w-3.5 h-3.5 inline mr-1 -mt-0.5" />
                  {formatRubles(result.purchasing)}
                </p>
              </div>
            </div>

            {/* Share */}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleShare}
                className={cn(
                  FOCUS_RING_SURFACE,
                  'inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium transition-all',
                  copied
                    ? 'bg-positive/10 text-positive border border-positive/20'
                    : 'bg-obsidian border border-border-subtle text-text-secondary hover:text-champagne hover:border-champagne/20'
                )}
              >
                {copied ? <Check className="w-3.5 h-3.5" /> : <Share2 className="w-3.5 h-3.5" />}
                {copied ? 'Ссылка скопирована' : 'Поделиться ссылкой'}
              </button>
              <button
                type="button"
                onClick={handleCopyText}
                className={cn(
                  FOCUS_RING_SURFACE,
                  'inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium',
                  'bg-obsidian border border-border-subtle text-text-secondary hover:text-champagne hover:border-champagne/20 transition-all'
                )}
              >
                <Copy className="w-3.5 h-3.5" />
                Скопировать текст
              </button>
            </div>
          </section>

          {/* ── Chart ── */}
          {chartData.length > 2 && (
            <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
              <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
                  {chartMode === 'purchasing' ? 'Покупательная способность' : 'Эквивалент суммы'}
                </h3>
                <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
                  <button
                    type="button"
                    onClick={() => setChartMode('purchasing')}
                    className={cn(
                      'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                      chartMode === 'purchasing'
                        ? 'bg-champagne/15 text-champagne'
                        : 'text-text-tertiary hover:text-text-secondary'
                    )}
                  >
                    Покуп. способность
                  </button>
                  <button
                    type="button"
                    onClick={() => setChartMode('equivalent')}
                    className={cn(
                      'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                      chartMode === 'equivalent'
                        ? 'bg-champagne/15 text-champagne'
                        : 'text-text-tertiary hover:text-text-secondary'
                    )}
                  >
                    Рост суммы
                  </button>
                </div>
              </div>

              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: -5 }}>
                  <defs>
                    <linearGradient id="calcGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#B8942F" stopOpacity={0.18} />
                      <stop offset="100%" stopColor="#B8942F" stopOpacity={0.01} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={d => formatDate(d, 'annual')}
                    stroke="rgba(0,0,0,0.1)"
                    tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                    tickLine={false}
                    interval="preserveStartEnd"
                    minTickGap={50}
                  />
                  <YAxis
                    stroke="rgba(0,0,0,0.1)"
                    tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                    tickLine={false}
                    axisLine={false}
                    domain={yDomain}
                    ticks={yTicks}
                    tickFormatter={v => formatAxisTick(v, 0)}
                    width={yWidth}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(0,0,0,0.15)', strokeWidth: 1 }} />

                  {visibleMilestones.map(m => (
                    <ReferenceLine
                      key={m.year}
                      x={`${m.year}-01-01`}
                      stroke="rgba(0,0,0,0.12)"
                      strokeDasharray="4 4"
                      label={{
                        value: m.label,
                        position: 'insideTopRight',
                        fill: 'rgba(0,0,0,0.3)',
                        fontSize: 10,
                        fontFamily: 'JetBrains Mono',
                      }}
                    />
                  ))}

                  <Area
                    dataKey="value"
                    stroke="#B8942F"
                    strokeWidth={2}
                    fill="url(#calcGrad)"
                    dot={false}
                    activeDot={{ r: 4, fill: '#B8942F', stroke: '#FFFFFF', strokeWidth: 2 }}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </section>
          )}

          {/* ── Category Breakdown ── */}
          <section data-animate className="mb-8">
            <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-4">
              Инфляция по категориям за период
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <CategoryCard icon={ShoppingCart} label="Продовольственные" rate={result.food} color="text-text-primary" />
              <CategoryCard icon={Package} label="Непродовольственные" rate={result.nonfood} color="text-text-primary" />
              <CategoryCard icon={Wrench} label="Услуги" rate={result.services} color="text-text-primary" />
            </div>
          </section>
        </>
      )}

      {/* ── Methodology ── */}
      <section data-animate className="rounded-[2rem] bg-obsidian-light border border-border-subtle p-6 md:p-8 mb-8">
        <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-4">Методология расчёта</h3>
        <div className="space-y-3 text-sm text-text-secondary leading-relaxed">
          <p>
            Калькулятор использует официальные ежемесячные значения ИПЦ (индекса потребительских цен) Росстата с января 1991 года.
            ИПЦ отражает изменение стоимости фиксированной корзины из ~500 товаров и услуг.
          </p>
          <p className="font-mono text-[11px] text-text-tertiary border-l-2 border-champagne/30 pl-4">
            Формула: Σ(amount) × ∏(CPI_i / 100) для i от начального до конечного месяца,
            где CPI_i — индекс потребительских цен за i-й месяц (напр. 100.73 = рост на 0.73%).
          </p>
          <p>
            Разбивка по категориям рассчитывается аналогично с использованием отдельных индексов:
            ИПЦ на продовольственные товары, непродовольственные товары и платные услуги населению.
          </p>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section data-animate className="mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">
          Частые вопросы
        </h2>
        <FAQAccordion />
      </section>
    </div>
  );
}
