import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import gsap from 'gsap';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';
import {
  ArrowLeft, Share2, Copy, Check, Calculator,
  TrendingDown, ShoppingCart, Package, Wrench,
  ArrowUpDown, Flame, Target, Clock, BarChart3, ChevronRight,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import useInflationCalc from '../lib/useInflationCalc';
import { formatDate, formatAxisTick, cn } from '../lib/format';
import { parseAmount, formatInput, fmtPct, years as yearsPhrase } from '../lib/calcFormat';
import { getSiteOrigin } from '../lib/siteOrigin';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { SkeletonBox } from '../components/Skeleton';
import { track, trackOutbound, events } from '../lib/track';
import { buildShareUrl } from '../lib/utm';
import useScrollDepth from '../lib/useScrollDepth';
import FaqAccordion from '../components/FaqAccordion';
import CalcCountryPicker from '../components/CalcCountryPicker';
import { localizeSource } from '../i18n/viewModeLabels';
import { useLocale, useT } from '../i18n';
import {
  defaultCountrySlug,
  formatCalcAmount,
  normalizePeriod,
  RUSSIA_SLUG,
} from '../lib/inflationCalc';
import {
  russiaIndicatorPath,
  russiaHomePath,
  regionHubPath,
  demographicsPath,
} from '../lib/sitePaths';

/* ─── Constants ─── */

const PRESETS = [
  { labelKey: 'calc.inflation.preset.1y', offset: 1 },
  { labelKey: 'calc.inflation.preset.5y', offset: 5 },
  { labelKey: 'calc.inflation.preset.10y', offset: 10 },
  { labelKey: 'calc.inflation.preset.from2000', from: 2000 },
  { labelKey: 'calc.inflation.preset.all', from: null },
];

const MILESTONES = [
  { year: 1998, labelKey: 'calc.inflation.milestone.default' },
  { year: 2008, labelKey: 'calc.inflation.milestone.crisis' },
  { year: 2014, labelKey: 'calc.inflation.milestone.sanctions' },
  { year: 2020, labelKey: 'calc.inflation.milestone.covid' },
  { year: 2022, labelKey: 'calc.inflation.milestone.sanctions' },
];

const WORLD_FAQ_KEYS = [
  { q: 'calc.inflation.faq.world.q1', a: 'calc.inflation.faq.world.a1' },
  { q: 'calc.inflation.faq.world.q2', a: 'calc.inflation.faq.world.a2' },
];

const FAQ_KEYS = [
  { q: 'calc.inflation.faq.q1', a: 'calc.inflation.faq.a1' },
  { q: 'calc.inflation.faq.q2', a: 'calc.inflation.faq.a2' },
  { q: 'calc.inflation.faq.q3', a: 'calc.inflation.faq.a3' },
  { q: 'calc.inflation.faq.q4', a: 'calc.inflation.faq.a4' },
  { q: 'calc.inflation.faq.q5', a: 'calc.inflation.faq.a5' },
  { q: 'calc.inflation.faq.q6', a: 'calc.inflation.faq.a6' },
];

const CATEGORY_META = [
  { key: 'food', labelKey: 'calc.inflation.cat.food', icon: ShoppingCart },
  { key: 'nonfood', labelKey: 'calc.inflation.cat.nonfood', icon: Package },
  { key: 'services', labelKey: 'calc.inflation.cat.services', icon: Wrench },
];

/** Перелинковка «Смотреть дальше»: ключи i18n + дефолты на случай гонки агентов. */
const WATCH_MORE_LINKS = [
  {
    key: 'world.calc.watchMore.regions',
    fallbackRu: 'Регионы России',
    fallbackEn: 'Regions of Russia',
    to: regionHubPath(),
  },
  {
    key: 'world.calc.watchMore.demography',
    fallbackRu: 'Демография',
    fallbackEn: 'Demographics',
    to: demographicsPath(),
  },
  {
    key: 'world.calc.watchMore.russia',
    fallbackRu: 'Экономика России',
    fallbackEn: 'Russia’s economy',
    to: russiaHomePath(),
  },
];

/* ─── Sub-components ─── */

function AnimatedNumber({ value, className, withRuble = true }) {
  const ref = useRef(null);
  const prevRef = useRef(value);

  useEffect(() => {
    if (!ref.current || value == null) return;
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      ref.current.textContent = formatCalcAmount(value, { withRuble });
      return;
    }
    const counter = { v: prevRef.current ?? 0 };
    const tween = gsap.to(counter, {
      v: value,
      duration: prevRef.current === 0 || prevRef.current == null ? 1.2 : 0.5,
      ease: 'power2.out',
      onUpdate() {
        if (ref.current) ref.current.textContent = formatCalcAmount(Math.round(counter.v), { withRuble });
      },
    });
    prevRef.current = value;
    return () => tween.kill();
  }, [value, withRuble]);

  return <span ref={ref} className={className}>{formatCalcAmount(value, { withRuble })}</span>;
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

function ChartTooltip({ active, payload, label, withRuble = true }) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  if (p?.value == null) return null;
  return (
    <div className="glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl min-w-[180px]">
      <p className="text-xs font-mono text-text-tertiary mb-1.5">{formatDate(label, 'full')}</p>
      <p className="text-sm font-mono font-semibold text-champagne">{formatCalcAmount(p.value, { withRuble })}</p>
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
  const t = useT();
  const categories = CATEGORY_META.map((c) => ({
    ...c,
    label: t(c.labelKey),
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

function YearlyBreakdownTable({ breakdown, withRuble = true }) {
  const t = useT();
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
              <th className="text-left text-[10px] uppercase tracking-wider text-text-tertiary font-medium py-2 px-1 w-16">{t('calc.inflation.table.year')}</th>
              <th className="text-left text-[10px] uppercase tracking-wider text-text-tertiary font-medium py-2 px-1">{t('calc.inflation.table.annual')}</th>
              <th className="text-right text-[10px] uppercase tracking-wider text-text-tertiary font-medium py-2 px-1 w-20">{t('calc.inflation.table.cum')}</th>
              <th className="text-right text-[10px] uppercase tracking-wider text-text-tertiary font-medium py-2 px-1 hidden sm:table-cell">{t('calc.inflation.table.purchasing')}</th>
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
                    {formatCalcAmount(row.purchasingPower, { withRuble })}
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
          onClick={() => { setExpanded(e => !e); track(events.CALC_BREAKDOWN, { expanded: !expanded }); }}
          className="mt-3 flex items-center gap-1 text-xs text-champagne hover:text-champagne-muted transition-colors font-medium"
        >
          <ChevronRight className={cn('w-3.5 h-3.5 transition-transform', expanded && 'rotate-90')} />
          {expanded ? t('calc.inflation.collapse') : t('calc.inflation.showAllYears', { n: breakdown.length })}
        </button>
      )}
    </div>
  );
}

/* ─── Main Page ─── */

export default function CalculatorPage() {
  const t = useT();
  const { locale } = useLocale();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentYear = new Date().getFullYear();
  const containerRef = useRef(null);

  const [amount, setAmount] = useState(() => {
    const p = searchParams.get('amount');
    return p ? parseInt(p, 10) || 100000 : 100000;
  });

  // K4a: URL-период снимается один раз как неизменяемый референс — нормализация
  // (перестановка from > to, клэмп к данным) выполняется в одной точке ниже.
  const [initialPeriod] = useState(() => ({
    from: parseInt(searchParams.get('from'), 10) || currentYear - 10,
    to: parseInt(searchParams.get('to'), 10) || currentYear,
  }));
  const [rawFromYear, setRawFromYear] = useState(initialPeriod.from);
  const [rawToYear, setRawToYear] = useState(initialPeriod.to);

  // K1: дефолт страны — по локали (EN-витрина → США), и только когда ?country
  // в URL нет; явный выбор пользователя всегда приоритетнее дефолта.
  const [countryParam] = useState(() => (searchParams.get('country') || '').trim().toLowerCase());
  const [countrySlug, setCountrySlug] = useState(
    () => countryParam || defaultCountrySlug(locale),
  );
  const [copied, setCopied] = useState(false);
  const [chartMode, setChartMode] = useState('purchasing');
  const [reversed, setReversed] = useState(false);
  const [periodTouched, setPeriodTouched] = useState(false);

  const {
    result, isLoading, isError, lastAvailableYear, minYear, lastAvailableDate,
    countries, source, sourceUrl, resolvedCountrySlug, countryName, seriesStartYear, isRussia,
  } = useInflationCalc(amount, rawFromYear, rawToYear, countrySlug);

  // K4a: канонизированный период — производное состояние, синхронизируемое во
  // время рендера (порядок «raw → normalized» детерминирован и не зацикливается),
  // без cascading-render эффекта. Пользовательские правки перезаписывают raw,
  // и следующая нормализация их не искажает.
  const [normalized, setNormalized] = useState(() => normalizePeriod(
    initialPeriod.from, initialPeriod.to, minYear, lastAvailableYear,
  ));
  const derived = normalizePeriod(initialPeriod.from, initialPeriod.to, minYear, lastAvailableYear);
  if (!periodTouched
    && (derived.from !== normalized.from || derived.to !== normalized.to)) {
    setNormalized(derived);
  }
  const fromYear = periodTouched ? rawFromYear : normalized.from;
  const toYear = periodTouched ? rawToYear : normalized.to;

  const withRuble = isRussia;
  const sourceLabel = source ? localizeSource(source, locale) : '';
  // K4b: у мировой ветки — прямая ссылка на источник ряда (metaQ), у России —
  // внутренняя карточка ИПЦ; без URL показывается просто подпись.
  const sourceHref = sourceUrl || null;

  // K4a: URL-период шире данных — канонизация видна пользователю оговоркой,
  // пока он сам не начал двигать слайдеры (тогда границы уже его выбор).
  const urlPeriodClamped = !periodTouched
    && (initialPeriod.from !== fromYear || initialPeriod.to !== toYear);

  const effectiveMax = lastAvailableYear || currentYear;
  const effectiveMin = minYear || 1991;
  const sliderFrom = Math.min(
    Math.max(fromYear, effectiveMin),
    Math.max(effectiveMin, effectiveMax - 1),
  );
  const sliderTo = Math.max(
    sliderFrom + 1,
    Math.min(Math.max(toYear, effectiveMin + 1), effectiveMax),
  );

  const lastDateFormatted = useMemo(() => {
    if (!lastAvailableDate) return null;
    return formatDate(lastAvailableDate, 'full');
  }, [lastAvailableDate]);

  const calcSeo = getPageSeo('calculator', locale);
  useDocumentMeta({
    title: calcSeo.title,
    description: calcSeo.description,
    path: calcSeo.path,
  });

  useScrollDepth({ key: 'calculator', page: 'calculator' });

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
    setPeriodTouched(true);
    setRawFromYear(Math.min(v, toYear - 1));
  }, [toYear]);
  const handleToYear = useCallback((v) => {
    setPeriodTouched(true);
    setRawToYear(Math.max(v, fromYear + 1));
  }, [fromYear]);

  const handlePreset = useCallback((preset) => {
    setPeriodTouched(true);
    if (preset.from != null) setRawFromYear(Math.max(preset.from, effectiveMin));
    else if (preset.from === null) setRawFromYear(effectiveMin);
    else setRawFromYear(Math.max(effectiveMax - preset.offset, effectiveMin));
    setRawToYear(effectiveMax);
    track(events.CALC_PRESET, { preset: preset.label });
  }, [effectiveMin, effectiveMax]);

  const handleCountryChange = useCallback((slug) => {
    // Явный выбор из пикера всегда валиден: кириллица/регистр нормализуются,
    // пустой выбор означает возврат к дефолту локали (K1).
    const normalized = String(slug || '').trim().toLowerCase();
    setCountrySlug(normalized || defaultCountrySlug(locale));
  }, [locale]);

  const handleShare = useCallback(async () => {
    const params = new URLSearchParams({ amount: String(amount), from: String(fromYear), to: String(toYear) });
    if (resolvedCountrySlug && resolvedCountrySlug !== RUSSIA_SLUG) params.set('country', resolvedCountrySlug);
    setSearchParams(params, { replace: true });
    // share-ссылка всегда уходит наружу с UTM, чтобы возвратный трафик
    // отделялся от Direct в Метрике (см. docs/utm_taxonomy.md::Internal share).
    const url = buildShareUrl(`${window.location.origin}/calculator?${params}`, {
      source: 'self',
      medium: 'share-link',
      campaign: 'calc-share',
      content: `${fromYear}-${toYear}`,
    });
    track(events.CALC_SHARE, { from: fromYear, to: toYear, amount, country: resolvedCountrySlug });
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard unavailable */ }
  }, [amount, fromYear, toYear, resolvedCountrySlug, setSearchParams]);

  // В-28: hero и share-текст показывают ФАКТИЧЕСКИ посчитанный период
  // (клэмп к доступным данным), а не введённые годы — иначе «?from=1990»
  // считался бы с 1991, а пользователь видел «с 1990».
  const dispFrom = result?.effectiveFrom ?? fromYear;
  const dispTo = result?.effectiveTo ?? toYear;

  const handleCopyText = useCallback(async () => {
    if (!result) return;
    track(events.CALC_COPY_RESULT);
    const fromY = result.effectiveFrom ?? fromYear;
    const toY = result.effectiveTo ?? toYear;
    const text = reversed
      ? t(withRuble ? 'calc.inflation.shareReverse' : 'calc.inflation.shareReversePlain', {
        amount: formatInput(amount),
        to: toY,
        value: formatCalcAmount(result.purchasing, { withRuble }),
        from: fromY,
        inflation: fmtPct(result.totalInflation),
      })
      : t(withRuble ? 'calc.inflation.shareForward' : 'calc.inflation.shareForwardPlain', {
        amount: formatInput(amount),
        from: fromY,
        value: formatCalcAmount(result.equivalent, { withRuble }),
        to: toY,
        inflation: fmtPct(result.totalInflation),
      });
    try { await navigator.clipboard.writeText(text); } catch { /* ok */ }
  }, [result, amount, fromYear, toYear, reversed, t, withRuble]);

  const heroValue = reversed ? result?.purchasing : result?.equivalent;
  const heroPrefix = reversed
    ? t(withRuble ? 'calc.inflation.heroWas' : 'calc.inflation.heroWasPlain', { amount: formatInput(amount), year: dispTo })
    : t(withRuble ? 'calc.inflation.heroIs' : 'calc.inflation.heroIsPlain', { amount: formatInput(amount), year: dispFrom });
  const heroSuffix = t('calc.inflation.inYear', { year: reversed ? dispFrom : dispTo });

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
    isRussia
      ? MILESTONES.filter((m) => m.year > fromYear && m.year < toYear)
      : []
  ), [fromYear, toYear, isRussia]);

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
    const yearsLabel = locale === 'en' ? t('calc.years', { n: periodYears }) : yearsPhrase(periodYears);

    items.push({
      icon: TrendingDown,
      text: t(isRussia ? 'calc.inflation.insight.loss' : 'calc.inflation.insight.lossWorld', {
        pct: lossPercent.toFixed(0),
        years: yearsLabel,
      }),
    });

    const cats = CATEGORY_META.map((c) => ({ ...c, label: t(c.labelKey), rate: result[c.key] })).sort((a, b) => b.rate - a.rate);
    if (isRussia && cats[0].rate > 0) {
      const diff = cats[0].rate - cats[cats.length - 1].rate;
      items.push({
        icon: BarChart3,
        text: t('calc.inflation.insight.topCat', {
          cat: cats[0].label.toLowerCase(),
          pct: cats[0].rate.toFixed(0),
          diff: diff.toFixed(0),
        }),
      });
    }

    if (result.peakYear && result.yearlyBreakdown.length > 2) {
      const ratio = result.peakYear.rate / result.avgAnnual;
      const peakExtra = ratio > 1.5
        ? t('calc.inflation.insight.peakRatio', { ratio: ratio.toFixed(1).replace('.', ',') })
        : '';
      items.push({
        icon: Flame,
        text: t('calc.inflation.insight.peak', {
          year: result.peakYear.year,
          rate: fmtPct(result.peakYear.rate),
        }) + peakExtra,
      });
    }

    items.push({
      icon: Target,
      text: t('calc.inflation.insight.income', { rate: fmtPct(result.avgAnnual) }),
    });

    if (result.doublingYears && result.doublingYears < 100) {
      items.push({
        icon: Clock,
        text: t('calc.inflation.insight.double', {
          rate: fmtPct(result.avgAnnual),
          years: result.doublingYears,
        }),
      });
    }

    return items;
  }, [result, t, locale, isRussia]);

  /* ── JSON-LD ── */
  const faqItems = useMemo(
    () => (isRussia ? FAQ_KEYS : WORLD_FAQ_KEYS).map((item) => ({ q: t(item.q), a: t(item.a) })),
    [t, isRussia],
  );

  const faqJsonLd = useMemo(() => ({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqItems.map((item) => ({
      '@type': 'Question', name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: item.a },
    })),
  }), [faqItems]);

  const webAppJsonLd = useMemo(() => {
    const origin = getSiteOrigin();
    return {
      '@context': 'https://schema.org',
      '@type': 'WebApplication',
      name: isRussia
        ? t('calc.inflation.jsonLdName')
        : t('calc.inflation.jsonLdNameWorld', { country: countryName || resolvedCountrySlug }),
      url: `${origin}/calculator`,
      description: isRussia
        ? t('calc.inflation.jsonLdDesc')
        : t('calc.inflation.jsonLdDescWorld', { country: countryName || resolvedCountrySlug }),
      applicationCategory: 'FinanceApplication',
      operatingSystem: 'All',
      offers: { '@type': 'Offer', price: '0', priceCurrency: 'RUB' },
      creator: { '@type': 'Organization', name: 'Forecast Economy', url: origin },
    };
  }, [t, isRussia, countryName, resolvedCountrySlug]);

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
          {t('common.home')}
        </Link>
        <span className="text-text-tertiary/40">/</span>
        <span className="text-text-secondary">{t('calc.inflation.crumb')}</span>
      </nav>

      {/* Hero */}
      <header data-animate className="mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-2xl bg-champagne/10 border border-champagne/20">
            <Calculator className="w-5 h-5 text-champagne" />
          </div>
          <span className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold">
            {isRussia
              ? t('calc.inflation.eyebrow')
              : t('calc.inflation.eyebrowWorld', { country: countryName || '', source: sourceLabel })}
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold tracking-tight text-text-primary leading-tight mb-3">
          {t('calc.inflation.title')}
        </h1>
        <p className="text-base text-text-secondary leading-relaxed max-w-xl">
          {isRussia
            ? t('calc.inflation.subtitle')
            : t('calc.inflation.subtitleWorld', { country: countryName || '' })}
        </p>
      </header>

      {/* Calculator Card */}
      <section data-animate data-block="calc-form" className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6">

        <CalcCountryPicker
          countries={countries}
          value={resolvedCountrySlug}
          onChange={handleCountryChange}
          russiaLabel={t('calc.country.russia')}
        />

        {/* Reverse mode toggle */}
        <div className="flex items-center justify-between mb-5">
          <label htmlFor="calc-amount" className="text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary">
            {t('calc.inflation.amount')}
          </label>
          <button
            type="button"
            onClick={() => { setReversed(r => !r); track(events.CALC_DIRECTION, { reversed: !reversed }); }}
            className={cn(
              FOCUS_RING_SURFACE,
              'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium transition-all duration-200',
              reversed
                ? 'bg-champagne/12 text-champagne ring-1 ring-champagne/25'
                : 'bg-obsidian border border-border-subtle text-text-tertiary hover:text-text-secondary hover:border-champagne/15'
            )}
          >
            <ArrowUpDown className="w-3 h-3" />
            {reversed ? t('calc.inflation.reverse') : t('calc.inflation.forward')}
          </button>
        </div>

        {/* Amount input */}
        <div className="mb-6">
          <div className="relative">
            {withRuble && (
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-xl text-text-tertiary font-display pointer-events-none" aria-hidden>₽</span>
            )}
            <input
              id="calc-amount"
              type="text"
              inputMode="numeric"
              value={formatInput(amount)}
              onChange={e => setAmount(parseAmount(e.target.value))}
              placeholder="100 000"
              className={cn(
                FOCUS_RING_SURFACE,
                'w-full pr-4 py-4 rounded-2xl bg-obsidian border border-border-subtle',
                withRuble ? 'pl-10' : 'pl-4',
                'text-2xl md:text-3xl font-display font-bold text-text-primary tabular-nums',
                'placeholder:text-text-tertiary/40 placeholder:font-normal',
                'transition-colors hover:border-champagne/20'
              )}
            />
          </div>
          {reversed && (
            <p className="mt-2 text-xs text-champagne/80">
              {t('calc.inflation.reverseHint', { to: toYear, from: fromYear })}
            </p>
          )}
        </div>

        {/* Year Sliders */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          <YearSlider label={t('calc.inflation.fromYear')} value={sliderFrom} min={effectiveMin} max={Math.max(effectiveMin, effectiveMax - 1)} onChange={handleFromYear} ariaLabel={t('calc.inflation.fromYearAria')} />
          <YearSlider label={t('calc.inflation.toYear')} value={sliderTo} min={Math.min(effectiveMin + 1, effectiveMax)} max={effectiveMax} onChange={handleToYear} ariaLabel={t('calc.inflation.toYearAria')} />
        </div>

        {/* Presets */}
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={t(p.labelKey)} type="button"
              onClick={() => handlePreset(p)}
              className={cn(
                FOCUS_RING_SURFACE,
                'px-3.5 py-1.5 rounded-full text-xs font-medium transition-all duration-200',
                isActivePreset(p)
                  ? 'bg-champagne/12 text-champagne ring-1 ring-champagne/25'
                  : 'bg-obsidian border border-border-subtle text-text-tertiary hover:text-text-secondary hover:border-champagne/15'
              )}
            >
              {t(p.labelKey)}
            </button>
          ))}
          {lastDateFormatted && (
            <span className="ml-auto text-[10px] text-text-tertiary self-center font-mono">
              {t('calc.inflation.dataUntil', { date: lastDateFormatted })}
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
          {t(isRussia ? 'calc.inflation.loadError' : 'calc.inflation.loadErrorWorld')}
        </div>
      )}

      {result && !isLoading && (
        <>
          {/* ── Result Card ── */}
          <section
            data-animate
            data-block="calc-result"
            className={cn(
              'rounded-[2rem] border p-6 md:p-8 mb-6 transition-colors duration-500',
              extremeInflation ? 'bg-negative/[0.03] border-negative/20' : 'bg-surface border-border-champagne'
            )}
            aria-live="polite"
          >
            <p className="text-sm text-text-secondary mb-2">{heroPrefix}</p>
            <AnimatedNumber
              value={heroValue}
              withRuble={withRuble}
              className={cn(
                'block font-display font-bold tracking-tight mb-1',
                extremeInflation
                  ? 'text-negative text-3xl md:text-4xl lg:text-5xl'
                  : 'text-text-primary text-4xl md:text-5xl lg:text-6xl'
              )}
            />
            <p className="text-sm text-text-secondary mb-6">{heroSuffix}</p>

            {/* В-29: границы периода проговорены явно — «из 2000 в 2026»
                означает с января 2000 по последний доступный месяц 2026. */}
            {result.periodFrom && result.periodTo && (
              <p className="text-xs text-text-tertiary mb-6 -mt-4">
                {t('calc.inflation.periodLabel', {
                  from: formatDate(result.periodFrom, 'full'),
                  to: formatDate(result.periodTo, 'full'),
                })}
              </p>
            )}

            {(result.clamped || urlPeriodClamped) && (
              <p className="text-xs text-text-tertiary mb-6 -mt-4">
                {t(
                  isRussia ? 'calc.inflation.clampedNote' : 'calc.inflation.shortSeries',
                  {
                    min: effectiveMin,
                    max: effectiveMax,
                    from: dispFrom,
                    to: dispTo,
                    year: seriesStartYear || effectiveMin,
                    country: countryName || '',
                  },
                )}
              </p>
            )}

            {sourceLabel && (
              <p className="text-xs text-text-tertiary mb-6 -mt-4">
                {t('calc.inflation.source', { source: '' }).replace(/\s*$/, '')}{' '}
                {sourceHref ? (
                  <a
                    href={sourceHref}
                    target="_blank"
                    rel="noopener"
                    className="text-champagne hover:text-champagne-muted underline decoration-champagne/30 underline-offset-2 transition-colors"
                    onClick={() => trackOutbound(sourceHref)}
                  >
                    {sourceLabel}
                  </a>
                ) : (
                  <Link
                    to={russiaIndicatorPath('cpi')}
                    className="text-champagne hover:text-champagne-muted underline decoration-champagne/30 underline-offset-2 transition-colors"
                  >
                    {sourceLabel}
                  </Link>
                )}
              </p>
            )}

            {/* Stat pills */}
            <div className="flex flex-wrap gap-3 mb-6">
              <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
                <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">{t('calc.inflation.statInflation')}</p>
                <p className="text-base font-mono font-bold text-text-primary tabular-nums">{fmtPct(result.totalInflation, true)}</p>
              </div>
              <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
                <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">{t('calc.inflation.statAvgAnnual')}</p>
                <p className="text-base font-mono font-bold text-text-primary tabular-nums">{fmtPct(result.avgAnnual)}</p>
              </div>
              <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
                <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">{t('calc.inflation.multiplier')}</p>
                <p className="text-base font-mono font-bold text-text-primary tabular-nums">×{result.multiplier.toFixed(2).replace('.', ',')}</p>
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
                {copied ? t('calc.inflation.shareCopied') : t('calc.inflation.shareLink')}
              </button>
              <button type="button" onClick={handleCopyText} className={cn(
                FOCUS_RING_SURFACE,
                'inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium',
                'bg-obsidian border border-border-subtle text-text-secondary hover:text-champagne hover:border-champagne/20 transition-all'
              )}>
                <Copy className="w-3.5 h-3.5" />
                {t('calc.inflation.copyText')}
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
                  {chartMode === 'purchasing' ? t('calc.inflation.chartPurchasing') : t('calc.inflation.chartEquivalent')}
                </h3>
                <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
                  {[
                    { key: 'purchasing', label: t('calc.inflation.modePurchasing') },
                    { key: 'equivalent', label: t('calc.inflation.modeEquivalent') },
                  ].map(m => (
                    <button key={m.key} type="button" onClick={() => { setChartMode(m.key); track(events.CALC_CHART_MODE, { mode: m.key }); }}
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
                  <Tooltip content={<ChartTooltip withRuble={withRuble} />} cursor={{ stroke: 'rgba(0,0,0,0.15)', strokeWidth: 1 }} />

                  {/* Reference line: initial amount */}
                  <ReferenceLine
                    y={amount}
                    stroke="rgba(0,0,0,0.15)"
                    strokeDasharray="6 4"
                    label={{
                      value: formatCalcAmount(amount, { withRuble }),
                      position: 'right',
                      fill: 'rgba(0,0,0,0.3)',
                      fontSize: 10,
                      fontFamily: 'JetBrains Mono',
                    }}
                  />

                  {visibleMilestones.map(m => (
                    <ReferenceLine key={m.year} x={`${m.year}-01-01`}
                      stroke="rgba(0,0,0,0.12)" strokeDasharray="4 4"
                      label={{ value: t(m.labelKey), position: 'insideTopRight', fill: 'rgba(0,0,0,0.3)', fontSize: 10, fontFamily: 'JetBrains Mono' }}
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
          {isRussia && (
            <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6">
              <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-5">
                {t('calc.inflation.catsTitle')}
              </h3>
              <CategoryBars result={result} />
            </section>
          )}

          {/* ── Yearly Breakdown ── */}
          {result.yearlyBreakdown?.length > 1 && (
            <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6">
              <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-5">
                {t('calc.inflation.yearsTitle')}
              </h3>
              <YearlyBreakdownTable breakdown={result.yearlyBreakdown} withRuble={withRuble} />
            </section>
          )}
        </>
      )}

      {/* ── Methodology ── */}
      <section data-animate data-block="calc-methodology" className="rounded-[2rem] bg-obsidian-light border border-border-subtle p-6 md:p-8 mb-8">
        <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-4">{t('calc.methodologyHeading')}</h3>
        <div className="space-y-3 text-sm text-text-secondary leading-relaxed">
          <p>
            {t(isRussia ? 'calc.inflation.method.p1' : 'calc.inflation.method.world.p1')}
          </p>
          <p className="font-mono text-[11px] text-text-tertiary border-l-2 border-champagne/30 pl-4">
            {t(isRussia ? 'calc.inflation.method.p2' : 'calc.inflation.method.world.p2')}
          </p>
          <p>
            {t(isRussia ? 'calc.inflation.method.p3' : 'calc.inflation.method.world.p3')}
          </p>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section data-animate className="mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">{t('calc.faqHeading')}</h2>
        <FaqAccordion
          items={faqItems}
          onToggle={({ title, open }) => {
            if (open) track(events.FAQ_TOGGLE, { question: title });
          }}
        />
      </section>

      {/* ── Другие калькуляторы ── */}
      <section data-animate className="mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-4">{t('calc.otherHeading')}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Link to="/calculator/mortgage" className="group rounded-2xl bg-surface border border-border-subtle p-4 hover:border-champagne/30 transition-colors">
            <p className="text-sm font-semibold text-text-primary group-hover:text-champagne transition-colors mb-1">{t('calc.inflation.otherMortgageTitle')}</p>
            <p className="text-[13px] text-text-secondary">{t('calc.inflation.otherMortgageDesc')}</p>
          </Link>
          <Link to="/calculator/compound" className="group rounded-2xl bg-surface border border-border-subtle p-4 hover:border-champagne/30 transition-colors">
            <p className="text-sm font-semibold text-text-primary group-hover:text-champagne transition-colors mb-1">{t('calc.inflation.otherCompoundTitle')}</p>
            <p className="text-[13px] text-text-secondary">{t('calc.inflation.otherCompoundDesc')}</p>
          </Link>
        </div>
      </section>

      {/* ── K5: Смотреть дальше — третий блок перелинковки вглубь платформы ── */}
      <section data-animate>
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-4">
          {t('world.calc.watchMore.title', locale === 'en' ? 'Keep exploring' : 'Смотреть дальше')}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {WATCH_MORE_LINKS.map((item) => (
            <Link
              key={item.key}
              to={item.to}
              className="group rounded-2xl bg-surface border border-border-subtle p-4 hover:border-champagne/30 transition-colors"
            >
              <p className="text-sm font-semibold text-text-primary group-hover:text-champagne transition-colors">
                {t(item.key, locale === 'en' ? item.fallbackEn : item.fallbackRu)}
              </p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
