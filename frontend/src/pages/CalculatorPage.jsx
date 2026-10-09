import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';
import {
  Share2, Copy, Check, Calculator,
  TrendingDown, ShoppingCart, Package, Wrench,
  ArrowUpDown, Flame, Target, Clock, BarChart3, ChevronRight,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import useInflationCalc from '../lib/useInflationCalc';
import { formatDate, pickChartAxisTicks, cn } from '../lib/format';
import { formatInput, fmtPct, decimalText, fitAmountText, formatCompactAmount, years as yearsPhrase } from '../lib/calcFormat';
import useCalcUrlSync, { intParam } from '../lib/useCalcUrlSync';
import { getSiteOrigin } from '../lib/siteOrigin';
import { mountJsonLd } from '../lib/jsonLd';
import { CHART_THEME, GRID_PROPS, TOOLTIP_STYLES, axisTick, refLabel, axisWidthForLabels } from '../lib/chartTheme';
import { useElementWidth, useTouchTooltip } from '../lib/chartHooks';
import { revealStyle } from '../lib/calcUi';
import { SkeletonBox } from '../components/Skeleton';
import { track, events } from '../lib/track';
import { buildShareUrl } from '../lib/utm';
import useScrollDepth from '../lib/useScrollDepth';
import FaqAccordion from '../components/FaqAccordion';
import ApiRetryBanner from '../components/ApiRetryBanner';
import LoadingNote from '../components/LoadingNote';
import Breadcrumbs from '../components/Breadcrumbs';
import { toolTrail } from '../lib/breadcrumbs';
import SourceLink from '../components/SourceLink';
import CalcCountryPicker from '../components/CalcCountryPicker';
import EmptyState from '../components/brand/EmptyState';
import CalcSlider from '../components/CalcSlider';
import CalcMoneyField from '../components/CalcMoneyField';
import CalculatorSiblings from '../components/CalculatorSiblings';
import CalculatorShowcase from '../components/CalculatorShowcase';
import CalcBeforeAfter from '../components/CalcBeforeAfter';
import CalcAnimatedNumber from '../components/CalcAnimatedNumber';
import CalcStickyResult from '../components/CalcStickyResult';
import CalcSaveSlot from '../components/CalcSaveSlot';
import { CalcStatGrid, CalcStatTile } from '../components/CalcStatTile';
import CalcMethod from '../components/CalcMethod';
import ChartTouchHint, { ChartLegend } from '../components/ChartTouchHint';
import { useChartTouchHint } from '../lib/useChartTouchHint';
import '../styles/w5-tools.css';
import '../styles/z8-tools.css';
import '../styles/w6-g.css';
import '../styles/k8-tools.css';
import Chip from '../components/Chip';
import Button from '../components/Button';
import { localizeSource } from '../i18n/viewModeLabels';
import { useLocale, useT } from '../i18n';
import {
  defaultCountrySlug,
  normalizePeriod,
  RUSSIA_SLUG,
} from '../lib/inflationCalc';
import { RUB, currencyForCountry, currencyInPhrase, formatMoney } from '../lib/countryCurrency';
import { MONEY_MAX } from '../lib/calcUi';
import {
  russiaIndicatorPath,
  russiaHomePath,
  regionHubPath,
  demographicsPath,
  countryPath,
  comparePath,
  worldRatingPath,
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
  { q: 'calc.inflation.faq.world.q1', a: 'w6g.calc.faq.world.a1' },
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

/** Перелинковка «Смотреть дальше» для России. Для других стран ссылки строятся по выбранной стране. */
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

function ChartTooltip({ active, payload, label, format }) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  if (p?.value == null) return null;
  return (
    <div className="glass-surface rounded-xl px-4 py-3 shadow-2xl min-w-[160px] max-w-[calc(100vw-48px)]">
      <p className="text-xs text-text-secondary mb-1.5">{formatDate(label, 'full')}</p>
      <p className="text-sm font-semibold tabular-nums text-champagne-ink">{format(p.value)}</p>
    </div>
  );
}

function InsightCard(props) {
  const Icon = props.icon;
  return (
    <div className="flex items-start gap-3 p-3.5 rounded-xl fe-glass-2">
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
            <div className="flex items-center justify-center w-8 h-8 rounded-lg shrink-0 fe-glass-2">
              <Icon className="w-3.5 h-3.5 text-text-tertiary" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-text-secondary truncate">{c.label}</span>
                <span className={cn(
                  'text-sm font-bold tabular-nums',
                  isMax ? 'text-champagne-ink' : 'text-text-primary'
                )}>
                  {fmtPct(c.rate, true)}
                </span>
              </div>
              <div className="h-2.5 fe-k8-tube">
                <div
                  className={cn('fe-k8-liquid transition-all duration-700', !isMax && 'fe-k8-liquid--pale')}
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

function YearlyBreakdownTable({ breakdown, format, partial = null }) {
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
              <th className="text-left text-xs text-text-secondary font-medium py-2 px-1 w-16">{t('calc.inflation.table.year')}</th>
              <th className="text-left text-xs text-text-secondary font-medium py-2 px-1">{t('w5.calc.table.annual')}</th>
              <th className="text-right text-xs text-text-secondary font-medium py-2 px-1 w-20">{t('w5.calc.table.total')}</th>
              <th className="text-right text-xs text-text-secondary font-medium py-2 px-1 hidden sm:table-cell">{t('w5.calc.table.purchasing')}</th>
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
                  <td className="py-2 px-1 text-text-primary tabular-nums">
                    {row.year}
                    {row.isPeak && <Flame className="w-3 h-3 text-champagne inline ml-1 -mt-0.5" />}
                    {partial && partial.year === row.year && (
                      <span className="block text-xs leading-tight text-text-secondary">{partial.text}</span>
                    )}
                  </td>
                  <td className="py-2 px-1">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 max-w-[120px] fe-k8-tube">
                        <div
                          className={cn('fe-k8-liquid', !row.isPeak && 'fe-k8-liquid--pale')}
                          style={{ width: `${barW}%` }}
                        />
                      </div>
                      <span className={cn(
                        'tabular-nums text-xs whitespace-nowrap',
                        row.isPeak ? 'font-bold text-champagne-ink' : 'text-text-secondary'
                      )}>
                        {fmtPct(row.annualRate, true)}
                      </span>
                    </div>
                  </td>
                  <td className="py-2 px-1 text-right text-xs text-text-secondary tabular-nums">
                    {fmtPct(row.cumulativeRate, true)}
                  </td>
                  <td className="py-2 px-1 text-right text-xs text-text-secondary tabular-nums hidden sm:table-cell">
                    {format(row.purchasingPower)}
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
          className="mt-3 flex min-h-8 items-center gap-1 text-xs pointer-coarse:min-h-11 text-champagne-ink hover:text-champagne-muted transition-colors font-medium"
        >
          <ChevronRight className={cn('w-3.5 h-3.5 transition-transform', expanded && 'rotate-90')} />
          {expanded ? t('calc.inflation.collapse') : t('calc.inflation.showAllYears', { n: breakdown.length })}
        </button>
      )}
    </div>
  );
}

/* ─── Main Page ─── */

/** Последняя выбранная человеком страна хранится в браузере; без хранилища страница работает как раньше. */
const COUNTRY_MEMORY_KEY = 'fe_calc_country';
function readRememberedCountry() {
  try { return String(window.localStorage.getItem(COUNTRY_MEMORY_KEY) || '').trim().toLowerCase().slice(0, 60); } catch { return ''; }
}
function rememberCountry(slug) {
  try { window.localStorage.setItem(COUNTRY_MEMORY_KEY, slug); } catch { /* хранилище недоступно */ }
}

/** Знак своей валюты: до 6 знаков, без разметки. */
function cleanCustomCurrency(raw) {
  return String(raw || '').replace(/[<>"'&\s]/g, '').slice(0, 6);
}

/** Деноминация 1 января 1998 года: 1000 старых рублей стали 1 новым. */
const DENOMINATION_YEAR = 1998;

export default function CalculatorPage({ renderSave } = {}) {
  const t = useT();
  const { locale } = useLocale();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentYear = new Date().getFullYear();

  // Круг 11 (E): все параметры живут в адресе (?amount=&from=&to=&country=&cur=), чтобы смена языка и сохранённый расчёт открывали то же.
  const [edited, setEdited] = useState(false);
  const [amount, setAmountRaw] = useState(() => intParam(searchParams, 'amount', { min: 1, max: MONEY_MAX, fallback: 100000 }));
  const setAmount = useCallback((value) => { setEdited(true); setAmountRaw(value); }, []);
  const [customCurrency, setCustomCurrencyRaw] = useState(() => cleanCustomCurrency(searchParams.get('cur')));
  const setCustomCurrency = useCallback((value) => { setEdited(true); setCustomCurrencyRaw(cleanCustomCurrency(value)); }, []);

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
  // Нет ?country: берём страну, которую человек выбирал в прошлый раз (после монтирования, чтобы разметка совпала с серверной),
  // а если её нет, страну по языку.
  const [countrySlug, setCountrySlug] = useState(
    () => countryParam || defaultCountrySlug(locale),
  );
  useEffect(() => {
    if (countryParam) return undefined;
    // Хранилище браузера читается после монтирования; применение в следующем такте, чтобы разметка совпала с серверной.
    const timer = window.setTimeout(() => {
      const remembered = readRememberedCountry();
      if (remembered) setCountrySlug(remembered);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [countryParam]);
  const [copied, setCopied] = useState(false);
  const resultRef = useRef(null);
  const [chartMode, setChartMode] = useState('purchasing');
  const chartBoxRef = useRef(null);
  const touchTip = useTouchTooltip(chartBoxRef);
  const touchHint = useChartTouchHint();
  const [setChartWidthNode, chartWidth] = useElementWidth();
  const [reversed, setReversed] = useState(false);
  const [periodTouched, setPeriodTouched] = useState(false);

  const {
    result, isLoading, isError, isFetching, refetch, lastAvailableYear, minYear, lastAvailableDate,
    countries, countriesLoading, source, sourceUrl, resolvedCountrySlug, countryName, seriesStartYear, isRussia,
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
  // Валюта страны: «Сумма в австралийских долларах», «A$100 000» вместо «нац. валюта».
  const knownCurrency = isRussia ? RUB : currencyForCountry(resolvedCountrySlug);
  // Круг 11 (E): у страны вне таблицы валют человек может назвать свою («₸», «KZT»): знак подставляется в суммы и подписи.
  const needsCustomCurrency = !isRussia && !knownCurrency;
  const currency = useMemo(() => {
    if (knownCurrency) return knownCurrency;
    if (!needsCustomCurrency || !customCurrency) return null;
    return { code: customCurrency, symbol: customCurrency, ruIn: customCurrency, enName: customCurrency, prefix: false };
  }, [knownCurrency, needsCustomCurrency, customCurrency]);
  const money = useCallback((n) => formatMoney(n, currency, locale), [currency, locale]);
  const shortSymbolPrefix = Boolean(currency?.prefix && currency.symbol.length <= 2);
  const sourceLabel = source ? localizeSource(source, locale) : '';
  // K4b: имя источника ведёт на его сайт (source_url, новая вкладка); без URL —
  // внутренний фолбэк: страница страны или карточка ИПЦ России.
  const sourceHref = sourceUrl || null;
  const sourceFallbackTo = !isRussia && resolvedCountrySlug
    ? `/${resolvedCountrySlug}`
    : russiaIndicatorPath('cpi');

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
    return formatDate(lastAvailableDate, 'fullGen');
  }, [lastAvailableDate]);

  useCalcUrlSync({
    amount,
    from: fromYear,
    to: toYear,
    country: resolvedCountrySlug || RUSSIA_SLUG,
    cur: needsCustomCurrency ? customCurrency : '',
  }, { enabled: edited });

  const calcSeo = getPageSeo('calculator', locale);
  useDocumentMeta({
    title: calcSeo.title,
    description: calcSeo.description,
    path: calcSeo.path,
  });

  useScrollDepth({ key: 'calculator', page: 'calculator' });

  const handleFromYear = useCallback((v) => {
    setEdited(true);
    setPeriodTouched(true);
    setRawFromYear(Math.min(v, toYear - 1));
  }, [toYear]);
  const handleToYear = useCallback((v) => {
    setEdited(true);
    setPeriodTouched(true);
    setRawToYear(Math.max(v, fromYear + 1));
  }, [fromYear]);

  const handlePreset = useCallback((preset) => {
    setEdited(true);
    setPeriodTouched(true);
    if (preset.from != null) setRawFromYear(Math.max(preset.from, effectiveMin));
    else if (preset.from === null) setRawFromYear(effectiveMin);
    else setRawFromYear(Math.max(effectiveMax - preset.offset, effectiveMin));
    setRawToYear(effectiveMax);
    track(events.CALC_PRESET, { preset: preset.labelKey });
  }, [effectiveMin, effectiveMax]);

  const handleCountryChange = useCallback((slug) => {
    // Явный выбор из пикера всегда валиден: кириллица/регистр нормализуются,
    // пустой выбор означает возврат к дефолту локали (K1).
    const normalized = String(slug || '').trim().toLowerCase();
    setEdited(true);
    if (normalized) rememberCountry(normalized);
    setCountrySlug(normalized || defaultCountrySlug(locale));
  }, [locale]);

  const handleShare = useCallback(async () => {
    const params = new URLSearchParams({ amount: String(amount), from: String(fromYear), to: String(toYear) });
    if (resolvedCountrySlug && resolvedCountrySlug !== RUSSIA_SLUG) params.set('country', resolvedCountrySlug);
    if (needsCustomCurrency && customCurrency) params.set('cur', customCurrency);
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
  }, [amount, fromYear, toYear, resolvedCountrySlug, needsCustomCurrency, customCurrency, setSearchParams]);

  // В-28: hero и share-текст показывают ФАКТИЧЕСКИ посчитанный период
  // (клэмп к доступным данным), а не введённые годы — иначе «?from=1990»
  // считался бы с 1991, а пользователь видел «с 1990».
  const dispFrom = result?.effectiveFrom ?? fromYear;
  const dispTo = result?.effectiveTo ?? toYear;
  const amountText = isRussia ? formatInput(amount) : money(amount);

  const handleCopyText = useCallback(async () => {
    if (!result) return;
    track(events.CALC_COPY_RESULT);
    const fromY = result.effectiveFrom ?? fromYear;
    const toY = result.effectiveTo ?? toYear;
    const text = reversed
      ? t(withRuble ? 'calc.inflation.shareReverse' : 'calc.inflation.shareReversePlain', {
        amount: amountText,
        to: toY,
        value: money(result.purchasing),
        from: fromY,
        inflation: fmtPct(result.totalInflation),
      })
      : t(withRuble ? 'calc.inflation.shareForward' : 'calc.inflation.shareForwardPlain', {
        amount: amountText,
        from: fromY,
        value: money(result.equivalent),
        to: toY,
        inflation: fmtPct(result.totalInflation),
      });
    try { await navigator.clipboard.writeText(text); } catch { /* ok */ }
  }, [result, amountText, fromYear, toYear, reversed, t, withRuble, money]);

  // Круг 9 (K2): срок называем по месяцам («10 лет 8 мес.»), а не округляем до целых лет: чип «10 лет» и подпись «за 11 лет» расходились.
  const periodLabel = useMemo(() => {
    if (!result) return '';
    const totalMonths = Math.max(1, Math.round(result.months));
    const wholeYears = Math.floor(totalMonths / 12);
    const restMonths = totalMonths % 12;
    const yearsText = locale === 'en' ? t('calc.years', { n: wholeYears }) : yearsPhrase(wholeYears);
    if (restMonths === 0) return yearsText;
    const monthsText = t('c9d.calc.monthsShort', { n: restMonths });
    return wholeYears === 0 ? monthsText : `${yearsText} ${monthsText}`;
  }, [result, locale, t]);

  const formatHero = money;
  const heroValue = reversed ? result?.purchasing : result?.equivalent;
  // Круг 11 (E): длинная сумма (17 147 319 615 ₽ для 1991 года) не обрезается: шрифт мельчает, а рядом стоит короткая запись.
  const heroFull = heroValue != null ? formatHero(heroValue) : '';
  const compactOptions = useMemo(() => ({
    symbol: currency?.symbol || '',
    prefix: locale === 'en' && Boolean(currency?.prefix),
  }), [currency, locale]);
  const fitMoney = useCallback((n, maxChars) => fitAmountText(money(n), n, { ...compactOptions, maxChars }), [money, compactOptions]);
  const heroCompact = heroValue != null && heroFull.length > 15 ? formatCompactAmount(heroValue, compactOptions.symbol, { prefix: compactOptions.prefix }) : '';
  const heroSizeClass = heroFull.length > 18
    ? 'text-2xl sm:text-4xl lg:text-5xl'
    : heroFull.length > 14
      ? 'text-3xl sm:text-5xl lg:text-5xl'
      : 'text-4xl md:text-5xl lg:text-6xl';
  // Рубли до 1998 года были «старыми»: расчёт считает только рост цен и о замене не знает, поэтому сумму надо пояснить.
  const denomination = useMemo(() => {
    if (!isRussia || !result || dispFrom >= DENOMINATION_YEAR || dispTo < DENOMINATION_YEAR) return null;
    return reversed
      ? { key: 'c11e.denom.reverse', value: money(result.purchasing * 1000), year: dispFrom }
      : { key: 'c11e.denom.forward', value: money(result.equivalent / 1000), year: dispFrom };
  }, [isRussia, result, dispFrom, dispTo, reversed, money]);
  const saveTitle = t('c11e.save.title', { country: countryName || t('calc.country.russia'), from: dispFrom, to: dispTo });
  const savePayload = useMemo(() => ({
    page: 'inflation',
    amount,
    from: fromYear,
    to: toYear,
    country: resolvedCountrySlug || RUSSIA_SLUG,
    ...(reversed ? { reversed: true } : {}),
    ...(needsCustomCurrency && customCurrency ? { cur: customCurrency } : {}),
  }), [amount, fromYear, toYear, resolvedCountrySlug, reversed, needsCustomCurrency, customCurrency]);
  const heroPrefix = reversed
    ? t(withRuble ? 'calc.inflation.heroWas' : 'calc.inflation.heroWasPlain', { amount: amountText, year: dispTo })
    : t(withRuble ? 'calc.inflation.heroIs' : 'calc.inflation.heroIsPlain', { amount: amountText, year: dispFrom });
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
    const sampleLabel = money(niceMax);
    const w = axisWidthForLabels([sampleLabel], { min: 50, max: 110, perChar: 7.2, pad: 12 });
    return { yDomain: [niceMin, niceMax], yTicks: ticks, yWidth: w };
  }, [chartData, amount, chartMode, money]);

  // Подписи оси X — через равные годовые промежутки (а не «2016, 2019, 2026»).
  const xTicks = useMemo(
    () => pickChartAxisTicks(chartData, chartWidth > 0 && chartWidth < 560 ? 4 : 6, { cadence: 'annual' }),
    [chartData, chartWidth],
  );

  const visibleMilestones = useMemo(() => (
    isRussia
      ? MILESTONES.filter((m) => m.year > fromYear && m.year < toYear)
      : []
  ), [fromYear, toYear, isRussia]);

  // Круг 9 (K2): чип показывается, только если его начало действительно внутри данных страны (у Турции данных меньше, чем
  // у России, и «5 лет», «10 лет», «С 2000» раньше сливались в одно и то же и горели все сразу). «Всё время» остаётся всегда.
  const visiblePresets = useMemo(() => PRESETS.filter((preset) => {
    if (preset.from === null) return true;
    const start = preset.from != null ? preset.from : effectiveMax - preset.offset;
    return start >= effectiveMin;
  }), [effectiveMin, effectiveMax]);
  const activePreset = useMemo(() => visiblePresets.find((preset) => {
    const target = preset.from != null
      ? preset.from
      : preset.from === null ? effectiveMin : effectiveMax - preset.offset;
    return fromYear === target && toYear === effectiveMax;
  }) || null, [visiblePresets, fromYear, toYear, effectiveMin, effectiveMax]);
  const isActivePreset = useCallback((preset) => activePreset === preset, [activePreset]);

  const extremeInflation = result && result.totalInflation > 200;

  // Последний год периода неполный (например, январь–август): таблица честно это помечает.
  const partialYear = useMemo(() => {
    const end = result?.periodTo ? new Date(result.periodTo) : null;
    if (!end || Number.isNaN(end.getTime()) || end.getUTCMonth() === 11) return null;
    const month = formatDate(result.periodTo, 'short').split(' ')[0];
    return { year: end.getUTCFullYear(), text: t('x4.calc.partialYear', { month }) };
  }, [result, t]);

  // «Смотреть дальше» следует за выбранной страной: для России её разделы, для других стран страница страны,
  // рейтинг инфляции и сравнение.
  const watchMore = useMemo(() => {
    if (isRussia || !resolvedCountrySlug) {
      return WATCH_MORE_LINKS.map((item) => ({
        key: item.key,
        to: item.to,
        label: t(item.key, locale === 'en' ? item.fallbackEn : item.fallbackRu),
      }));
    }
    return [
      {
        key: 'country',
        to: countryPath(resolvedCountrySlug),
        label: countryName
          ? t('w6g.calc.watchMore.country', { country: countryName })
          : t('w6g.calc.watchMore.countryGeneric'),
      },
      { key: 'rating', to: worldRatingPath('hicp-index'), label: t('w6g.calc.watchMore.rating') },
      {
        key: 'compare',
        to: `${comparePath()}?codes=${encodeURIComponent(`w:${resolvedCountrySlug}:hicp-index`)}`,
        label: t('w6g.calc.watchMore.compare'),
      },
    ];
  }, [isRussia, resolvedCountrySlug, countryName, locale, t]);

  /* ── Insights ── */
  const insights = useMemo(() => {
    if (!result) return [];
    const items = [];
    const lossPercent = (1 - 1 / result.multiplier) * 100;
    const yearsLabel = periodLabel;

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
        ? t('calc.inflation.insight.peakRatio', { ratio: decimalText(ratio, 1) })
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
  }, [result, t, isRussia, periodLabel]);

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
    const removeFaq = faqItems.length >= 2 ? mountJsonLd(faqJsonLd) : () => {};
    let appScript = document.getElementById('calc-app-ld');
    if (!appScript) { appScript = document.createElement('script'); appScript.id = 'calc-app-ld'; appScript.type = 'application/ld+json'; document.head.appendChild(appScript); }
    appScript.textContent = JSON.stringify(webAppJsonLd);
    return () => { removeFaq(); document.getElementById('calc-app-ld')?.remove(); };
  }, [faqJsonLd, webAppJsonLd, faqItems.length]);

  /* ─── Render ─── */

  return (
    <div className="fe-data-page fe-gutter fe-z8-calc pt-24 md:pt-28 pb-12 sm:pb-16">

      <div style={revealStyle(0)} className="fe-reveal mb-5">
        <Breadcrumbs items={toolTrail(t('calc.inflation.title'), '/calculator')} />
      </div>

      {/* Hero: короткая шапка, чтобы форма была на первом экране */}
      <header style={revealStyle(1)} className="fe-reveal fe-z8-calc__head">
        <div className="fe-z8-calc__icon" aria-hidden="true">
          <Calculator className="w-5 h-5" />
        </div>
        <div className="fe-z8-calc__headtext">
          <span className="w5-eyebrow">
            {t(isRussia ? 'w5.calc.inflation.eyebrow' : 'w5.calc.inflation.eyebrowWorld')}
          </span>
          <h1 className="fe-z8-calc__title">{t('calc.inflation.title')}</h1>
          {!isRussia && countryName && (
            <p className="fe-z8-calc__scope" data-testid="calc-scope">
              {t('c9d.calc.scope', { country: countryName, currency: currency ? currencyInPhrase(currency, locale) : t('calc.ui.unitLocal') })}
            </p>
          )}
          <p className="fe-z8-calc__lead">
            {isRussia
              ? t('calc.inflation.subtitle')
              : countryName
                ? t('w6g.calc.subtitleWorld', { country: countryName })
                : t('w6g.calc.subtitleWorldNoName')}
          </p>
        </div>
      </header>

      <CalculatorShowcase current="inflation" />

      <div className="fe-z8-calc__grid">
      <div className="fe-z8-calc__side">
      {/* Calculator Card */}
      <section style={revealStyle(2)} data-block="calc-form" className="fe-reveal fe-panel fe-z8-card p-6 md:p-7">

        <CalcCountryPicker
          countries={countries}
          value={resolvedCountrySlug}
          onChange={handleCountryChange}
          russiaLabel={t('calc.country.russia')}
          loading={countriesLoading}
          fallbackName={countryName || ''}
        />

        {/* Направление расчёта: два понятных варианта вместо кнопки «Прямой расчёт» */}
        <div className="fe-w6g-direction" role="group" aria-label={t('w6g.calc.directionAria')}>
          <Chip
            active={!reversed}
            onClick={() => { if (reversed) { setReversed(false); track(events.CALC_DIRECTION, { reversed: false }); } }}
            className="gap-1.5 rounded-full"
          >
            <ArrowUpDown className="w-3.5 h-3.5" aria-hidden="true" />
            {t('w6g.calc.directionToday')}
          </Chip>
          <Chip
            active={reversed}
            onClick={() => { if (!reversed) { setReversed(true); track(events.CALC_DIRECTION, { reversed: true }); } }}
            className="gap-1.5 rounded-full"
          >
            <ArrowUpDown className="w-3.5 h-3.5" aria-hidden="true" />
            {t('w6g.calc.directionThen')}
          </Chip>
        </div>

        {/* Amount */}
        <div className="mb-6">
          <CalcMoneyField
            id="calc-amount"
            label={currency
              ? `${t('calc.inflation.amount')} ${currencyInPhrase(currency, locale)}`
              : t('calc.inflation.amount')}
            unitName={isRussia ? t('calc.ui.unitRubles') : (currency ? '' : t('calc.ui.unitLocal'))}
            value={amount}
            onChange={setAmount}
            prefix={isRussia ? '₽' : (shortSymbolPrefix ? currency.symbol : '')}
            suffix={isRussia || shortSymbolPrefix ? '' : (currency ? currency.symbol : t('calc.ui.suffixLocal'))}
            placeholder={locale === 'en' ? '100,000' : '100 000'}
          />
          {needsCustomCurrency && (
            <label className="fe-c11e-cur" data-testid="calc-custom-currency">
              <span className="fe-c11e-cur__label">{t('c11e.cur.label')}</span>
              <input
                type="text"
                inputMode="text"
                autoComplete="off"
                maxLength={6}
                value={customCurrency}
                onChange={(event) => setCustomCurrency(event.target.value)}
                placeholder={t('c11e.cur.placeholder')}
                className="calc-field-input fe-c11e-cur__input"
              />
              <span className="fe-c11e-cur__hint">{t('c11e.cur.hint')}</span>
            </label>
          )}
          {reversed && (
            <p className="mt-2 text-xs text-champagne-ink">
              {t('calc.inflation.reverseHint', { to: toYear, from: fromYear })}
            </p>
          )}
        </div>

        {/* Year Sliders */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          <CalcSlider
            label={t('calc.inflation.fromYear')} ariaLabel={t('calc.inflation.fromYearAria')}
            value={sliderFrom} min={effectiveMin} max={Math.max(effectiveMin, effectiveMax - 1)}
            onChange={handleFromYear} stacked
          />
          <CalcSlider
            label={t('calc.inflation.toYear')} ariaLabel={t('calc.inflation.toYearAria')}
            value={sliderTo} min={Math.min(effectiveMin + 1, effectiveMax)} max={effectiveMax}
            onChange={handleToYear} stacked
          />
        </div>

        {/* Presets */}
        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center [&>*:last-child:nth-child(odd)]:col-span-2 sm:[&>*:last-child:nth-child(odd)]:col-auto">
          {visiblePresets.map((p) => (
            <Chip
              key={t(p.labelKey)}
              active={isActivePreset(p)}
              onClick={() => handlePreset(p)}
              className="w-full justify-center rounded-full sm:w-auto"
            >
              {t(p.labelKey)}
            </Chip>
          ))}
        </div>
        {lastDateFormatted && (
          <p className="mt-3 text-xs text-text-secondary">
            {t('calc.inflation.dataUntil', { date: lastDateFormatted })}
          </p>
        )}
      </section>

      {result && !isLoading && (
        <aside style={revealStyle(3)} className="fe-reveal fe-z8-hint" data-block="calc-hint">
          <span className="fe-z8-hint__label">{t('z8.calc.hint.label')}</span>
          <p className="fe-z8-hint__big">{fmtPct(result.totalInflation)}</p>
          <p className="fe-z8-hint__line">{t('z8.calc.hint.inflation', { years: periodLabel })}</p>
          <p className="fe-z8-hint__sub">{t('z8.calc.hint.avg', { rate: fmtPct(result.avgAnnual) })}</p>
        </aside>
      )}
      </div>

      <div className="fe-z8-calc__out">
      {/* Loading: тот же размер, что у карточки результата — без прыжка высоты */}
      {isLoading && (
        <div
          style={revealStyle(3)}
          className="fe-reveal fe-panel rounded-[2rem] p-6 md:p-8 mb-6 min-h-[22rem]"
          aria-busy="true"
          role="status"
        >
          <LoadingNote onRefresh={refetch} className="mb-4" />
          <SkeletonBox className="h-4 w-48 mb-4"  />
          <SkeletonBox className="h-14 w-72 max-w-full mb-4" />
          <SkeletonBox className="h-4 w-56 max-w-full mb-8" />
          <div className="flex flex-wrap gap-3">
            <SkeletonBox className="h-14 w-32 rounded-xl" />
            <SkeletonBox className="h-14 w-32 rounded-xl" />
            <SkeletonBox className="h-14 w-32 rounded-xl" />
          </div>
        </div>
      )}

      {/* Error */}
      {isError && !isLoading && (
        <ApiRetryBanner className="mb-6" onRetry={refetch} isFetching={isFetching}>
          {t(isRussia ? 'w5.calc.inflation.loadError' : 'w6g.calc.loadError')}
        </ApiRetryBanner>
      )}

      {/* Страна без данных о ценах: короткая подсказка вместо пустой области (она занимала экран). */}
      {!isError && !isLoading && !result && amount > 0 && (
        <div
          role="status"
          data-testid="calc-no-data"
          className="mb-6 rounded-[1.5rem] p-5 text-sm text-text-secondary fe-glass-lite"
        >
          <EmptyState variant="no-data" size={80} title={t('w6a.calc.noData')} />
        </div>
      )}

      {result && !isLoading && (
        <>
          {/* ── Result Card ── */}
          <section
            ref={resultRef}
            style={revealStyle(3)}
            data-block="calc-result"
            className={cn(
              'fe-reveal fe-z8-result fe-k8-stone fe-glint rounded-[2rem] p-6 md:p-8 mb-6 min-h-[22rem] transition-colors duration-500',
              extremeInflation && 'fe-k8-stone--warn'
            )}
            aria-live="polite"
          >
            <p className="text-sm text-text-secondary mb-2">{heroPrefix}</p>
            <CalcAnimatedNumber
              value={heroValue}
              format={formatHero}
              className={cn(
                'block min-h-[1.2em] font-display font-bold tracking-tight mb-1 [overflow-wrap:anywhere]',
                extremeInflation
                  ? cn('text-negative', heroFull.length > 14 ? 'text-2xl sm:text-3xl lg:text-4xl' : 'text-3xl md:text-4xl lg:text-5xl')
                  : cn('fe-w6g-hero-num', heroSizeClass)
              )}
            />
            {heroCompact && (
              <p className="text-base font-semibold text-text-primary mb-1" data-testid="calc-hero-compact">{`≈ ${heroCompact}`}</p>
            )}
            <p className="text-sm text-text-secondary mb-2">{heroSuffix}</p>

            <CalcBeforeAfter
              ariaLabel={t('w6g.calc.baAria', {
                a: reversed ? money(result.purchasing) : amountText,
                b: reversed ? amountText : money(result.equivalent),
              })}
              before={{
                label: String(reversed ? dispFrom : dispFrom),
                value: reversed ? result.purchasing : amount,
                text: fitMoney(reversed ? result.purchasing : amount, 13),
              }}
              after={{
                label: String(dispTo),
                value: reversed ? amount : result.equivalent,
                text: fitMoney(reversed ? amount : result.equivalent, 13),
              }}
            />
            <div className="mb-6" />

            {/* В-29: границы периода проговорены явно — «из 2000 в 2026»
                означает с января 2000 по последний доступный месяц 2026. */}
            {result.periodFrom && result.periodTo && (
              <p className="text-xs text-text-tertiary mb-6 -mt-4">
                {t('calc.inflation.periodLabel', {
                  from: formatDate(result.periodFrom, 'fullGen'),
                  to: formatDate(result.periodTo, 'full'),
                })}
              </p>
            )}

            {(result.clamped || urlPeriodClamped) && (
              <p className="text-xs text-text-tertiary mb-6 -mt-4">
                {t(
                  isRussia ? 'w5.calc.inflation.clampedNote' : (countryName ? 'w6g.calc.shortData' : 'w6g.calc.shortDataNoName'),
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

            {denomination && (
              <p className="fe-c11e-note mb-6" data-testid="calc-denomination">
                {t(denomination.key, { value: denomination.value, year: denomination.year })}
              </p>
            )}

            {sourceLabel && (
              <p className="text-xs text-text-tertiary mb-6 -mt-4">
                {t('calc.inflation.source', { source: '' }).replace(/\s*$/, '')}{' '}
                <SourceLink
                  href={sourceHref}
                  fallbackTo={sourceFallbackTo}
                  className="text-champagne-ink hover:text-champagne-muted underline decoration-champagne/30 underline-offset-2 transition-colors"
                >
                  {sourceLabel}
                </SourceLink>
              </p>
            )}

            {/* Итоговые плитки */}
            <CalcStatGrid className="mb-6 w5-tiles--three">
              <CalcStatTile index={0} label={t('w5.calc.inflation.statTotal')} value={fmtPct(result.totalInflation, true)} />
              <CalcStatTile index={1} label={t('w5.calc.inflation.statAvg')} value={fmtPct(result.avgAnnual)} />
              <CalcStatTile index={2} label={t('w5.calc.inflation.statMult')} value={`×${decimalText(result.multiplier, 2)}`} accent />
            </CalcStatGrid>

            {/* Share */}
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Button variant="secondary" size="sm" onClick={handleShare} className="w-full">
                {copied ? <Check className="w-3.5 h-3.5" aria-hidden="true" /> : <Share2 className="w-3.5 h-3.5" aria-hidden="true" />}
                {copied ? t('calc.inflation.shareCopied') : t('calc.inflation.shareLink')}
              </Button>
              <Button variant="secondary" size="sm" onClick={handleCopyText} className="w-full">
                <Copy className="w-3.5 h-3.5" aria-hidden="true" />
                {t('calc.inflation.copyText')}
              </Button>
            </div>
            <CalcSaveSlot
              className="mt-2"
              renderSave={renderSave}
              itemKey={`inflation:${resolvedCountrySlug || RUSSIA_SLUG}:${fromYear}-${toYear}:${amount}${reversed ? ':r' : ''}`}
              title={saveTitle}
              payload={savePayload}
            />
          </section>

          {/* ── Insights ── */}
          {insights.length > 0 && (
            <section style={revealStyle(4)} className="fe-reveal mb-6">
              <div className="flex items-start gap-3 rounded-3xl p-5 fe-glass-lite">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-champagne/10">
                  {(() => { const LeadIcon = insights[0].icon; return <LeadIcon className="h-4 w-4 text-champagne" aria-hidden="true" />; })()}
                </div>
                <p className="text-base font-semibold leading-snug text-text-primary">{insights[0].text}</p>
              </div>
              {insights.length > 1 && (
                <details className="w5-more mt-3">
                  <summary className="w5-more__summary">
                    {t('w5.calc.inflation.moreInsights', { n: insights.length - 1 })}
                  </summary>
                  <div className="mt-2.5 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                    {insights.slice(1).map((ins, i) => (
                      <InsightCard key={i} icon={ins.icon}>{ins.text}</InsightCard>
                    ))}
                  </div>
                </details>
              )}
            </section>
          )}

          {/* ── Chart ── */}
          {chartData.length > 2 && (
            <section
              ref={setChartWidthNode}
              style={revealStyle(5)}
              className="fe-reveal fe-panel rounded-[2rem] shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6"
            >
              <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
                <h3 className="text-base font-semibold text-text-primary">
                  {chartMode === 'purchasing' ? t('calc.inflation.chartPurchasing') : t('calc.inflation.chartEquivalent')}
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { key: 'purchasing', label: t('calc.inflation.modePurchasing') },
                    { key: 'equivalent', label: t('calc.inflation.modeEquivalent') },
                  ].map(m => (
                    <Chip
                      key={m.key}
                      active={chartMode === m.key}
                      onClick={() => { setChartMode(m.key); track(events.CALC_CHART_MODE, { mode: m.key }); }}
                    >
                      {m.label}
                    </Chip>
                  ))}
                </div>
              </div>

              <div ref={chartBoxRef} onPointerDownCapture={(event) => { touchTip.onPointerDownCapture(event); touchHint.dismiss(); }}>
                <ResponsiveContainer width="100%" height={chartWidth > 0 && chartWidth < 560 ? 280 : 320}>
                  <AreaChart data={chartData} margin={{ top: 16, right: 16, bottom: 5, left: 4 }}>
                    <defs>
                      <linearGradient id="calcGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={CHART_THEME.champagne} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={CHART_THEME.champagne} stopOpacity={0.01} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid {...GRID_PROPS} />
                    <XAxis dataKey="date" tickFormatter={d => formatDate(d, 'annual')}
                      stroke={CHART_THEME.axisLine} tick={axisTick({ fontSize: 13 })}
                      tickLine={false} ticks={xTicks} interval={0}
                    />
                    <YAxis stroke={CHART_THEME.axisLine} tick={axisTick({ fontSize: 13 })}
                      tickLine={false} axisLine={false} domain={yDomain} ticks={yTicks}
                      tickFormatter={(v) => money(v)} width={yWidth}
                    />
                    <Tooltip
                      content={<ChartTooltip format={money} />}
                      cursor={TOOLTIP_STYLES.cursor}
                      {...touchTip.tooltipProps}
                    />

                    {/* Reference line: initial amount */}
                    <ReferenceLine
                      y={amount}
                      stroke={CHART_THEME.refLine}
                      strokeDasharray="6 4"
                      label={yTicks?.includes(amount) ? undefined : refLabel(
                        money(amount),
                        chartMode === 'purchasing' ? 'insideBottomRight' : 'insideTopLeft',
                      )}
                    />

                    {/* Подписи событий вынесены в легенду под графиком: на узком экране они слипались. */}
                    {visibleMilestones.map(m => (
                      <ReferenceLine key={m.year} x={`${m.year}-01-01`}
                        stroke={CHART_THEME.refLine} strokeDasharray="4 4"
                      />
                    ))}

                    <Area dataKey="value" stroke={CHART_THEME.champagne} strokeWidth={2.5}
                      fill="url(#calcGrad)" dot={false}
                      activeDot={{ r: 4, fill: CHART_THEME.champagne, stroke: CHART_THEME.surface, strokeWidth: 2 }}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              {visibleMilestones.length > 0 && (
                <ChartLegend
                  items={visibleMilestones.map((m) => ({
                    color: CHART_THEME.refLine,
                    dashed: true,
                    label: `${m.year} — ${t(m.labelKey)}`,
                  }))}
                />
              )}
              <ChartTouchHint visible={touchHint.visible} />
            </section>
          )}

          {/* ── Category Breakdown ── */}
          {isRussia && (
            <section style={revealStyle(6)} className="fe-reveal fe-panel rounded-[2rem] shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6">
              <h3 className="text-base font-semibold text-text-primary mb-5">
                {t('calc.inflation.catsTitle')}
              </h3>
              <CategoryBars result={result} />
            </section>
          )}

          {/* ── Yearly Breakdown ── */}
          {result.yearlyBreakdown?.length > 1 && (
            <section style={revealStyle(7)} className="fe-reveal fe-panel rounded-[2rem] shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6">
              <h3 className="text-base font-semibold text-text-primary mb-5">
                {t('calc.inflation.yearsTitle')}
              </h3>
              <YearlyBreakdownTable breakdown={result.yearlyBreakdown} format={money} partial={partialYear} />
            </section>
          )}
        </>
      )}

      </div>
      </div>

      <CalcStickyResult
        targetRef={resultRef}
        active={Boolean(result && !isLoading)}
        value={heroValue != null ? fitMoney(heroValue, 13) : ''}
      />

      <div className="fe-z8-calc__lower">
      {/* ── Как считаем (простыми словами; формулы на виду нет) ── */}
      <div style={revealStyle(8)} className="fe-reveal fe-z8-calc__method">
        <CalcMethod
          dataBlock="calc-methodology"
          paragraphs={[
            t(isRussia ? 'w5.calc.inflation.how.p1' : 'w5.calc.inflation.how.world.p1'),
            t(isRussia ? 'w5.calc.inflation.how.p2' : 'w5.calc.inflation.how.world.p2'),
            t(isRussia ? 'w5.calc.inflation.how.p3' : 'w6g.calc.method.p3'),
          ]}
        />
      </div>

      {/* ── FAQ ── */}
      <section style={revealStyle(9)} className="fe-reveal fe-z8-calc__faq">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">{t('calc.faqHeading')}</h2>
        <FaqAccordion
          items={faqItems}
          onToggle={({ title, open }) => {
            if (open) track(events.FAQ_TOGGLE, { question: title });
          }}
        />
      </section>

      {/* ── Другие калькуляторы ── */}
      <div style={revealStyle(10)} className="fe-reveal fe-z8-calc__siblings">
        <CalculatorSiblings current="inflation" />
      </div>
      </div>

      {/* ── K5: Смотреть дальше — третий блок перелинковки вглубь платформы ── */}
      <section style={revealStyle(10)} className="fe-reveal">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-4">
          {t('world.calc.watchMore.title', locale === 'en' ? 'Keep exploring' : 'Смотреть дальше')}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {watchMore.map((item) => (
            <Link
              key={item.key}
              to={item.to}
              className="fe-panel fe-press group block min-h-11 rounded-2xl p-4 transition-colors fe-float"
            >
              <p className="text-sm font-semibold text-text-primary group-hover:text-champagne-ink transition-colors">
                {item.label}
              </p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
