import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import gsap from 'gsap';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';
import {
  ArrowLeft, Share2, Copy, Check, ChevronDown, Calculator,
  TrendingDown, ShoppingCart, Package, Wrench,
  ArrowUpDown, Flame, Target, Clock, BarChart3, ChevronRight,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import useInflationCalc from '../lib/useInflationCalc';
import { formatDate, formatAxisTick, cn } from '../lib/format';
import { FOCUS_RING, FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { SkeletonBox } from '../components/Skeleton';

/* ─── Constants ─── */

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

const CATEGORY_META = [
  { key: 'food', label: 'Продовольственные', icon: ShoppingCart },
  { key: 'nonfood', label: 'Непродовольственные', icon: Package },
  { key: 'services', label: 'Услуги', icon: Wrench },
];

/* ─── Helpers ─── */

function formatRubles(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  const abs = Math.abs(Math.round(n));
  const sign = n < 0 ? '-' : '';
  return sign + abs.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0') + '\u00A0₽';
}

function parseAmount(str) {
  const cleaned = str.replace(/[^\d]/g, '');
  return cleaned ? parseInt(cleaned, 10) : 0;
}

function formatInput(n) {
  if (!n || n <= 0) return '';
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

function fmtPct(v, sign = false) {
  if (v == null || !Number.isFinite(v)) return '—';
  const s = sign && v > 0 ? '+' : '';
  return `${s}${v.toFixed(1)}%`;
}

/* ─── Sub-components ─── */

function AnimatedNumber({ value, className }) {
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

  return <span ref={ref} className={className}>{formatRubles(value)}</span>;
}

function YearSlider({ value, onChange, min, max, label, ariaLabel }) {
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary">{label}</span>
        <span className="text-sm font-mono font-bold text-text-primary tabular-nums">{value}</span>
      </div>
      <input
        type="range" min={min} max={max} value={value}
        onChange={e => onChange(Number(e.target.value))}
        aria-label={ariaLabel}
        className="calc-slider w-full"
      />
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

function InsightCard(props) {
  const Icon = props.icon;
  return (
    <div className="flex items-start gap-3 p-3.5 rounded-xl bg-obsidian-light/70 border border-border-subtle">
      <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5">
        <Icon className="w-3.5 h-3.5 text-champagne" />
      </div>
      <p className="text-[13px] leading-relaxed text-text-secondary">{props.children}</p>
    </div>
  );
}

function CategoryBars({ result }) {
  const categories = CATEGORY_META.map(c => ({
    ...c,
    rate: result[c.key],
  })).sort((a, b) => b.rate - a.rate);

  const maxRate = Math.max(...categories.map(c => Math.abs(c.rate)), 1);

  return (
    <div className="space-y-3">
      {categories.map((c, i) => {
        const Icon = c.icon;
        const width = Math.max(4, (Math.abs(c.rate) / maxRate) * 100);
        const isMax = i === 0;
        return (
          <div key={c.key} className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-surface border border-border-subtle shrink-0">
              <Icon className="w-3.5 h-3.5 text-text-tertiary" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-text-secondary truncate">{c.label}</span>
                <span className={cn(
                  'text-sm font-mono font-bold tabular-nums',
                  isMax ? 'text-champagne' : 'text-text-primary'
                )}>
                  {fmtPct(c.rate, true)}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-obsidian-lighter overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-700',
                    isMax ? 'bg-champagne' : 'bg-champagne/40'
                  )}
                  style={{ width: `${width}%` }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function YearlyBreakdownTable({ breakdown }) {
  const [expanded, setExpanded] = useState(false);
  if (!breakdown?.length) return null;

  const maxRate = Math.max(...breakdown.map(r => Math.abs(r.annualRate)), 1);
  const showToggle = breakdown.length > 8;
  const visible = expanded ? breakdown : breakdown.slice(-8);

  return (
    <div>
      <div className="overflow-x-auto -mx-1">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-subtle">
              <th className="text-left text-[10px] uppercase tracking-wider text-text-tertiary font-medium py-2 px-1 w-16">Год</th>
              <th className="text-left text-[10px] uppercase tracking-wider text-text-tertiary font-medium py-2 px-1">Годовая</th>
              <th className="text-right text-[10px] uppercase tracking-wider text-text-tertiary font-medium py-2 px-1 w-20">Нак.</th>
              <th className="text-right text-[10px] uppercase tracking-wider text-text-tertiary font-medium py-2 px-1 hidden sm:table-cell">Покуп. способность</th>
            </tr>
          </thead>
          <tbody>
            {visible.map(row => {
              const barW = Math.max(3, (Math.abs(row.annualRate) / maxRate) * 100);
              return (
                <tr
                  key={row.year}
                  className={cn(
                    'border-b border-border-subtle/50 transition-colors',
                    row.isPeak && 'bg-champagne/[0.04]'
                  )}
                >
                  <td className="py-2 px-1 font-mono text-text-primary tabular-nums">
                    {row.year}
                    {row.isPeak && <Flame className="w-3 h-3 text-champagne inline ml-1 -mt-0.5" />}
                  </td>
                  <td className="py-2 px-1">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1 rounded-full bg-obsidian-lighter overflow-hidden max-w-[120px]">
                        <div
                          className={cn('h-full rounded-full', row.isPeak ? 'bg-champagne' : 'bg-champagne/50')}
                          style={{ width: `${barW}%` }}
                        />
                      </div>
                      <span className={cn(
                        'font-mono tabular-nums text-xs whitespace-nowrap',
                        row.isPeak ? 'font-bold text-champagne' : 'text-text-secondary'
                      )}>
                        {fmtPct(row.annualRate, true)}
                      </span>
                    </div>
                  </td>
                  <td className="py-2 px-1 text-right font-mono text-xs text-text-tertiary tabular-nums">
                    {fmtPct(row.cumulativeRate, true)}
                  </td>
                  <td className="py-2 px-1 text-right font-mono text-xs text-text-secondary tabular-nums hidden sm:table-cell">
                    {formatRubles(row.purchasingPower)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {showToggle && (
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          className="mt-3 flex items-center gap-1 text-xs text-champagne hover:text-champagne-muted transition-colors font-medium"
        >
          <ChevronRight className={cn('w-3.5 h-3.5 transition-transform', expanded && 'rotate-90')} />
          {expanded ? 'Свернуть' : `Показать все ${breakdown.length} лет`}
        </button>
      )}
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
            className={cn(FOCUS_RING, 'w-full flex items-center justify-between gap-4 py-5 text-left rounded-sm')}
            aria-expanded={open === i}
          >
            <span className="text-sm font-medium text-text-primary">{item.q}</span>
            <ChevronDown className={cn('w-4 h-4 text-text-tertiary shrink-0 transition-transform duration-200', open === i && 'rotate-180')} />
          </button>
          {open === i && (
            <p className="pb-5 text-sm text-text-secondary leading-relaxed -mt-1">{item.a}</p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ─── Main Page ─── */

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
  const [reversed, setReversed] = useState(false);

  const { result, isLoading, isError, lastAvailableYear, minYear, lastAvailableDate } = useInflationCalc(amount, fromYear, toYear);

  const effectiveMax = lastAvailableYear || currentYear;
  const effectiveMin = minYear || 1991;

  const lastDateFormatted = useMemo(() => {
    if (!lastAvailableDate) return null;
    return formatDate(lastAvailableDate, 'full');
  }, [lastAvailableDate]);

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

  const handleFromYear = useCallback((v) => setFromYear(Math.min(v, toYear - 1)), [toYear]);
  const handleToYear = useCallback((v) => setToYear(Math.max(v, fromYear + 1)), [fromYear]);

  const handlePreset = useCallback((preset) => {
    if (preset.from != null) setFromYear(Math.max(preset.from, effectiveMin));
    else if (preset.from === null) setFromYear(effectiveMin);
    else setFromYear(Math.max(effectiveMax - preset.offset, effectiveMin));
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
    const text = reversed
      ? `${formatInput(amount)} ₽ в ${toYear} году — это было ${formatRubles(result.purchasing)} в ${fromYear} году (инфляция ${result.totalInflation.toFixed(1)}%). Рассчитано на forecasteconomy.com/calculator`
      : `${formatInput(amount)} ₽ в ${fromYear} году эквивалентны ${formatRubles(result.equivalent)} в ${toYear} году (инфляция ${result.totalInflation.toFixed(1)}%). Рассчитано на forecasteconomy.com/calculator`;
    try { await navigator.clipboard.writeText(text); } catch { /* ok */ }
  }, [result, amount, fromYear, toYear, reversed]);

  const heroValue = reversed ? result?.purchasing : result?.equivalent;
  const heroPrefix = reversed
    ? `${formatInput(amount)} ₽ в ${toYear} году — это было`
    : `${formatInput(amount)} ₽ в ${fromYear} году — это`;
  const heroSuffix = reversed ? `в ${fromYear} году` : `в ${toYear} году`;

  const chartData = useMemo(() => {
    if (!result?.series?.length) return [];
    return result.series.map(p => ({
      date: p.date,
      value: chartMode === 'purchasing' ? p.purchasing : p.equivalent,
    }));
  }, [result, chartMode]);

  const { yDomain, yTicks, yWidth } = useMemo(() => {
    if (!chartData.length) return { yDomain: ['auto', 'auto'], yTicks: undefined, yWidth: 55 };
    let lo = Infinity, hi = -Infinity;
    for (const row of chartData) {
      if (row.value != null) { lo = Math.min(lo, row.value); hi = Math.max(hi, row.value); }
    }
    if (chartMode === 'purchasing' && amount > hi) hi = amount;
    if (chartMode === 'equivalent' && amount < lo) lo = amount;
    if (!isFinite(lo)) return { yDomain: ['auto', 'auto'], yTicks: undefined, yWidth: 55 };
    const span = hi - lo || 1;
    const rough = span / 5;
    const pow = Math.pow(10, Math.floor(Math.log10(rough)));
    const frac = rough / pow;
    const step = frac <= 1.5 ? pow : frac <= 3.5 ? 2 * pow : frac <= 7.5 ? 5 * pow : 10 * pow;
    const niceMin = Math.floor(lo / step) * step;
    const niceMax = Math.ceil(hi / step) * step;
    const ticks = [];
    for (let v = niceMin; v <= niceMax + step * 0.01; v += step) ticks.push(Math.round(v));
    const sampleLabel = formatAxisTick(niceMax, 0);
    const w = Math.max(50, Math.min(100, sampleLabel.length * 8 + 16));
    return { yDomain: [niceMin, niceMax], yTicks: ticks, yWidth: w };
  }, [chartData, amount, chartMode]);

  const visibleMilestones = useMemo(() => (
    MILESTONES.filter(m => m.year > fromYear && m.year < toYear)
  ), [fromYear, toYear]);

  const isActivePreset = useCallback((preset) => {
    const target = preset.from != null
      ? Math.max(preset.from, effectiveMin)
      : preset.from === null ? effectiveMin : Math.max(effectiveMax - preset.offset, effectiveMin);
    return fromYear === target && toYear === effectiveMax;
  }, [fromYear, toYear, effectiveMin, effectiveMax]);

  const extremeInflation = result && result.totalInflation > 200;

  /* ── Insights ── */
  const insights = useMemo(() => {
    if (!result) return [];
    const items = [];
    const periodYears = Math.round(result.months / 12);
    const lossPercent = (1 - 1 / result.multiplier) * 100;

    items.push({
      icon: TrendingDown,
      text: `Рубль потерял ${lossPercent.toFixed(0)}% покупательной способности за ${periodYears} ${periodYears === 1 ? 'год' : periodYears < 5 ? 'года' : 'лет'}`,
    });

    const cats = CATEGORY_META.map(c => ({ ...c, rate: result[c.key] })).sort((a, b) => b.rate - a.rate);
    if (cats[0].rate > 0) {
      const diff = cats[0].rate - cats[cats.length - 1].rate;
      items.push({
        icon: BarChart3,
        text: `Больше всего подорожали ${cats[0].label.toLowerCase()} (+${cats[0].rate.toFixed(0)}%), на ${diff.toFixed(0)} п.п. больше самой дешёвой категории`,
      });
    }

    if (result.peakYear && result.yearlyBreakdown.length > 2) {
      const ratio = result.peakYear.rate / result.avgAnnual;
      items.push({
        icon: Flame,
        text: `Пиковая инфляция: ${result.peakYear.year} год — ${result.peakYear.rate.toFixed(1)}%${ratio > 1.5 ? ` (в ${ratio.toFixed(1)}× больше средней)` : ''}`,
      });
    }

    items.push({
      icon: Target,
      text: `Для сохранения покупательной способности доходы должны были расти минимум на ${result.avgAnnual.toFixed(1)}% ежегодно`,
    });

    if (result.doublingYears && result.doublingYears < 100) {
      items.push({
        icon: Clock,
        text: `При средней инфляции ${result.avgAnnual.toFixed(1)}% цены удваиваются каждые ${result.doublingYears} лет`,
      });
    }

    return items;
  }, [result]);

  /* ── JSON-LD ── */
  const faqJsonLd = useMemo(() => ({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQ_ITEMS.map(item => ({
      '@type': 'Question', name: item.q,
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
    if (!faqScript) { faqScript = document.createElement('script'); faqScript.id = 'calc-faq-ld'; faqScript.type = 'application/ld+json'; document.head.appendChild(faqScript); }
    faqScript.textContent = JSON.stringify(faqJsonLd);
    let appScript = document.getElementById('calc-app-ld');
    if (!appScript) { appScript = document.createElement('script'); appScript.id = 'calc-app-ld'; appScript.type = 'application/ld+json'; document.head.appendChild(appScript); }
    appScript.textContent = JSON.stringify(webAppJsonLd);
    return () => { document.getElementById('calc-faq-ld')?.remove(); document.getElementById('calc-app-ld')?.remove(); };
  }, [faqJsonLd, webAppJsonLd]);

  /* ─── Render ─── */

  return (
    <div ref={containerRef} className="max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24">

      {/* Breadcrumb */}
      <nav data-animate className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary mb-8">
        <Link to="/" className="hover:text-champagne transition-colors lift-hover inline-flex items-center gap-1.5 group">
          <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
          Главная
        </Link>
        <span className="text-text-tertiary/40">/</span>
        <span className="text-text-secondary">Калькулятор</span>
      </nav>

      {/* Hero */}
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
          по официальным данным Росстата с годовой разбивкой и анализом по категориям.
        </p>
      </header>

      {/* Calculator Card */}
      <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6">

        {/* Reverse mode toggle */}
        <div className="flex items-center justify-between mb-5">
          <label htmlFor="calc-amount" className="text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary">
            Сумма
          </label>
          <button
            type="button"
            onClick={() => setReversed(r => !r)}
            className={cn(
              FOCUS_RING_SURFACE,
              'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium transition-all duration-200',
              reversed
                ? 'bg-champagne/12 text-champagne ring-1 ring-champagne/25'
                : 'bg-obsidian border border-border-subtle text-text-tertiary hover:text-text-secondary hover:border-champagne/15'
            )}
          >
            <ArrowUpDown className="w-3 h-3" />
            {reversed ? 'Обратный расчёт' : 'Прямой расчёт'}
          </button>
        </div>

        {/* Amount input */}
        <div className="mb-6">
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
          {reversed && (
            <p className="mt-2 text-xs text-champagne/80">
              Введите сумму в ценах {toYear} года — калькулятор покажет, сколько это было в {fromYear}
            </p>
          )}
        </div>

        {/* Year Sliders */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          <YearSlider label="Из года" value={fromYear} min={effectiveMin} max={effectiveMax - 1} onChange={handleFromYear} ariaLabel="Начальный год" />
          <YearSlider label="В год" value={toYear} min={effectiveMin + 1} max={effectiveMax} onChange={handleToYear} ariaLabel="Конечный год" />
        </div>

        {/* Presets */}
        <div className="flex flex-wrap gap-2">
          {PRESETS.map(p => (
            <button
              key={p.label} type="button"
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
          {lastDateFormatted && (
            <span className="ml-auto text-[10px] text-text-tertiary self-center font-mono">
              Данные до {lastDateFormatted}
            </span>
          )}
        </div>
      </section>

      {/* Loading */}
      {isLoading && (
        <div data-animate className="rounded-[2rem] bg-surface border border-border-subtle p-8 mb-6">
          <SkeletonBox className="h-6 w-48 mb-4" />
          <SkeletonBox className="h-14 w-72 mb-4" />
          <SkeletonBox className="h-4 w-56" />
        </div>
      )}

      {/* Error */}
      {isError && !isLoading && (
        <div className="rounded-[2rem] bg-warn-surface border border-champagne/35 p-6 mb-6 text-sm text-warn-text">
          Не удалось загрузить данные ИПЦ. Проверьте соединение и обновите страницу.
        </div>
      )}

      {result && !isLoading && (
        <>
          {/* ── Result Card ── */}
          <section
            data-animate
            className={cn(
              'rounded-[2rem] border p-6 md:p-8 mb-6 transition-colors duration-500',
              extremeInflation ? 'bg-negative/[0.03] border-negative/20' : 'bg-surface border-border-champagne'
            )}
            aria-live="polite"
          >
            <p className="text-sm text-text-secondary mb-2">{heroPrefix}</p>
            <AnimatedNumber
              value={heroValue}
              className={cn(
                'block font-display font-bold tracking-tight mb-1',
                extremeInflation
                  ? 'text-negative text-3xl md:text-4xl lg:text-5xl'
                  : 'text-text-primary text-4xl md:text-5xl lg:text-6xl'
              )}
            />
            <p className="text-sm text-text-secondary mb-6">{heroSuffix}</p>

            {/* Stat pills */}
            <div className="flex flex-wrap gap-3 mb-6">
              <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
                <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">Инфляция</p>
                <p className="text-base font-mono font-bold text-text-primary tabular-nums">+{result.totalInflation.toFixed(1)}%</p>
              </div>
              <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
                <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">Среднегодовая</p>
                <p className="text-base font-mono font-bold text-text-primary tabular-nums">{result.avgAnnual.toFixed(1)}%</p>
              </div>
              <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
                <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">Множитель</p>
                <p className="text-base font-mono font-bold text-text-primary tabular-nums">×{result.multiplier.toFixed(2)}</p>
              </div>
            </div>

            {/* Share */}
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={handleShare} className={cn(
                FOCUS_RING_SURFACE,
                'inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium transition-all',
                copied
                  ? 'bg-positive/10 text-positive border border-positive/20'
                  : 'bg-obsidian border border-border-subtle text-text-secondary hover:text-champagne hover:border-champagne/20'
              )}>
                {copied ? <Check className="w-3.5 h-3.5" /> : <Share2 className="w-3.5 h-3.5" />}
                {copied ? 'Ссылка скопирована' : 'Поделиться ссылкой'}
              </button>
              <button type="button" onClick={handleCopyText} className={cn(
                FOCUS_RING_SURFACE,
                'inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium',
                'bg-obsidian border border-border-subtle text-text-secondary hover:text-champagne hover:border-champagne/20 transition-all'
              )}>
                <Copy className="w-3.5 h-3.5" />
                Скопировать текст
              </button>
            </div>
          </section>

          {/* ── Insights ── */}
          {insights.length > 0 && (
            <section data-animate className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-6">
              {insights.map((ins, i) => (
                <InsightCard key={i} icon={ins.icon}>{ins.text}</InsightCard>
              ))}
            </section>
          )}

          {/* ── Chart ── */}
          {chartData.length > 2 && (
            <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
              <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
                  {chartMode === 'purchasing' ? 'Покупательная способность' : 'Эквивалент суммы'}
                </h3>
                <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
                  {[
                    { key: 'purchasing', label: 'Покуп. способность' },
                    { key: 'equivalent', label: 'Рост суммы' },
                  ].map(m => (
                    <button key={m.key} type="button" onClick={() => setChartMode(m.key)}
                      className={cn(
                        'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                        chartMode === m.key ? 'bg-champagne/15 text-champagne' : 'text-text-tertiary hover:text-text-secondary'
                      )}>
                      {m.label}
                    </button>
                  ))}
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
                  <XAxis dataKey="date" tickFormatter={d => formatDate(d, 'annual')}
                    stroke="rgba(0,0,0,0.1)" tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                    tickLine={false} interval="preserveStartEnd" minTickGap={50}
                  />
                  <YAxis stroke="rgba(0,0,0,0.1)" tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                    tickLine={false} axisLine={false} domain={yDomain} ticks={yTicks}
                    tickFormatter={v => formatAxisTick(v, 0)} width={yWidth}
                  />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(0,0,0,0.15)', strokeWidth: 1 }} />

                  {/* Reference line: initial amount */}
                  <ReferenceLine
                    y={amount}
                    stroke="rgba(0,0,0,0.15)"
                    strokeDasharray="6 4"
                    label={{
                      value: `${formatInput(amount)} ₽`,
                      position: 'right',
                      fill: 'rgba(0,0,0,0.3)',
                      fontSize: 10,
                      fontFamily: 'JetBrains Mono',
                    }}
                  />

                  {visibleMilestones.map(m => (
                    <ReferenceLine key={m.year} x={`${m.year}-01-01`}
                      stroke="rgba(0,0,0,0.12)" strokeDasharray="4 4"
                      label={{ value: m.label, position: 'insideTopRight', fill: 'rgba(0,0,0,0.3)', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                    />
                  ))}

                  <Area dataKey="value" stroke="#B8942F" strokeWidth={2}
                    fill="url(#calcGrad)" dot={false}
                    activeDot={{ r: 4, fill: '#B8942F', stroke: '#FFFFFF', strokeWidth: 2 }}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </section>
          )}

          {/* ── Category Breakdown ── */}
          <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6">
            <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-5">
              Инфляция по категориям за период
            </h3>
            <CategoryBars result={result} />
          </section>

          {/* ── Yearly Breakdown ── */}
          {result.yearlyBreakdown?.length > 1 && (
            <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6">
              <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-5">
                Инфляция по годам
              </h3>
              <YearlyBreakdownTable breakdown={result.yearlyBreakdown} />
            </section>
          )}
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
            Формула: amount × ∏(CPI_i / 100) для i от начального до конечного месяца,
            где CPI_i — индекс потребительских цен за i-й месяц (напр. 100.73 = рост на 0.73%).
          </p>
          <p>
            Разбивка по категориям рассчитывается аналогично с использованием отдельных индексов:
            ИПЦ на продовольственные товары, непродовольственные товары и платные услуги населению.
            Годовая разбивка показывает инфляцию за каждый календарный год в выбранном периоде.
          </p>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section data-animate className="mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">Частые вопросы</h2>
        <FAQAccordion />
      </section>
    </div>
  );
}
