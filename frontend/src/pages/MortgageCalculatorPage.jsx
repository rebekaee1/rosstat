import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, PieChart, Pie, Cell,
} from 'recharts';
import { Home, Percent, Wallet, Clock, PieChart as PieIcon } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { formatCompactTick } from '../lib/regionsApi';
import { CHART_THEME, COMPARE_COLORS, GRID_PROPS, TOOLTIP_STYLES, axisTick, axisWidthForLabels } from '../lib/chartTheme';
import { formatDate } from '../lib/format';
import { useElementWidth, useTouchTooltip } from '../lib/chartHooks';
import { revealStyle, formatMoneyLimit } from '../lib/calcUi';
import { formatRubles, fmtPct, loanYearOrdinal, evenYearTicks, fitAmountText, years as yearsPhrase } from '../lib/calcFormat';
import useCalcUrlSync, { intParam, floatParam } from '../lib/useCalcUrlSync';
import { buildSchedule, compareRates, earlyRepaymentGain } from '../lib/mortgageSchedule';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import FaqAccordion from '../components/FaqAccordion';
import Breadcrumbs from '../components/Breadcrumbs';
import CalculatorSiblings from '../components/CalculatorSiblings';
import CalculatorShowcase from '../components/CalculatorShowcase';
import '../styles/w6-g.css';
import { toolTrail } from '../lib/breadcrumbs';
import CalcSlider from '../components/CalcSlider';
import CalcMoneyField from '../components/CalcMoneyField';
import CalcAnimatedNumber from '../components/CalcAnimatedNumber';
import CalcStickyResult from '../components/CalcStickyResult';
import { CalcStatGrid, CalcStatTile } from '../components/CalcStatTile';
import CalcMethod from '../components/CalcMethod';
import CalcKeyRate from '../components/CalcKeyRate';
import CalcSaveSlot from '../components/CalcSaveSlot';
import CalcMortgageExtras from '../components/CalcMortgageExtras';
import CalcRateCompare from '../components/CalcRateCompare';
import CalcMortgageSchedule from '../components/CalcMortgageSchedule';
import ChartTouchHint, { ChartLegend } from '../components/ChartTouchHint';
import { useChartTouchHint } from '../lib/useChartTouchHint';
import '../styles/w5-tools.css';
import '../styles/z8-tools.css';
import '../styles/k8-tools.css';
import { useLocale, useT } from '../i18n';
import {
  russiaIndicatorPath,
} from '../lib/sitePaths';

const FAQ_KEYS = [
  { q: 'calc.mortgage.faq.q1', a: 'calc.mortgage.faq.a1' },
  { q: 'calc.mortgage.faq.q2', a: 'calc.mortgage.faq.a2' },
  { q: 'calc.mortgage.faq.q3', a: 'calc.mortgage.faq.a3' },
  { q: 'calc.mortgage.faq.q4', a: 'calc.mortgage.faq.a4' },
  { q: 'calc.mortgage.faq.q5', a: 'calc.mortgage.faq.a5' },
];

// Круг 9 (K3 цвета): тело кредита — глубокий синий бренда, переплата — бирюзовая; серо-чёрный в диаграмме не нужен.
const PRINCIPAL_COLOR = COMPARE_COLORS[0];
const OVERPAY_COLOR = COMPARE_COLORS[1];

// Круг 11 (E): предел стоимости объекта 10 млрд ₽ (выше почти наверняка опечатка), с подсказкой под полем.
const PRICE_MAX = 10_000_000_000;

// Итоги не обрезаются: длинное число (больше 14 знаков) пишется сокращённо («160 млрд ₽»).
const fitRubles = (n) => fitAmountText(formatRubles(n), n, { maxChars: 14 });
const heroSize = (text) => (text.length > 15
  ? 'text-2xl sm:text-4xl lg:text-5xl'
  : text.length > 12 ? 'text-3xl sm:text-5xl lg:text-5xl' : 'text-4xl md:text-5xl lg:text-6xl');

export default function MortgageCalculatorPage({ renderSave } = {}) {
  const t = useT();
  const { locale } = useLocale();
  const faqItems = FAQ_KEYS.map((item) => ({ q: t(item.q), a: t(item.a) }));
  const areaBoxRef = useRef(null);
  const resultRef = useRef(null);
  const pieBoxRef = useRef(null);
  const areaTouch = useTouchTooltip(areaBoxRef);
  const pieTouch = useTouchTooltip(pieBoxRef);
  const touchHint = useChartTouchHint();
  const [setChartWidthNode, chartWidth] = useElementWidth();
  const yearsLabel = (n) => (locale === 'en' ? t('calc.years', { n }) : yearsPhrase(n));
  const [searchParams] = useSearchParams();
  // Параметры расчёта живут в адресе (?price=&down=&rate=&years=): так работает «Поделиться» и сохранённый в кабинете расчёт.
  const [edited, setEdited] = useState(false);
  const [price, setPriceRaw] = useState(() => intParam(searchParams, 'price', { min: 1, max: PRICE_MAX, fallback: 8000000 }));
  const [downPct, setDownPctRaw] = useState(() => intParam(searchParams, 'down', { min: 0, max: 90, fallback: 20 }));
  // Ставка: пока человек её не менял, берётся средняя по ипотеке сейчас (ниже), а если данных нет, 18 %.
  const [userRate, setUserRate] = useState(() => floatParam(searchParams, 'rate', { min: 0.1, max: 30, fallback: null }));
  const [years, setYearsRaw] = useState(() => intParam(searchParams, 'years', { min: 1, max: 30, fallback: 20 }));
  const setPrice = useCallback((value) => { setEdited(true); setPriceRaw(value); }, []);
  const setDownPct = useCallback((value) => { setEdited(true); setDownPctRaw(value); }, []);
  const setYears = useCallback((value) => { setEdited(true); setYearsRaw(value); }, []);
  const changeRate = useCallback((value) => { setEdited(true); setUserRate(value); }, []);
  // Досрочное погашение и вторая ставка (сравнение двух ставок).
  const [extra, setExtraState] = useState({ monthly: 0, lump: 0, lumpMonth: 12, lumpMode: 'term' });
  const setExtra = useCallback((patch) => { setEdited(true); setExtraState((prev) => ({ ...prev, ...patch })); }, []);
  const [rateB, setRateB] = useState(null);

  const mortgageSeo = getPageSeo('calculator-mortgage', locale);
  useDocumentMeta({
    title: mortgageSeo.title,
    description: mortgageSeo.description,
    path: mortgageSeo.path,
  });
  useScrollDepth({ key: 'calc-mortgage', page: 'calculator-mortgage' });

  const { data: keyRate, isPending: keyRatePending } = useQuery({
    queryKey: ['key-rate-latest'],
    queryFn: () => api.get('/indicators/key-rate/data?limit=1').then((r) => {
      const p = r.data?.data?.[0];
      return p?.value != null ? Number(p.value) : null;
    }),
    staleTime: 60 * 60 * 1000,
    retry: 1,
  });

  // Круг 9 (K5): ставка по умолчанию — средняя по ипотеке сейчас, а не выдуманные 18 %. Пока человек ставку не трогал,
  // подставляем её сам; потом остаётся строка «Средняя сейчас … Подставить».
  const { data: avgMortgage } = useQuery({
    queryKey: ['mortgage-rate-latest'],
    queryFn: () => api.get('/indicators/mortgage-rate/data?limit=1').then((r) => {
      const p = r.data?.data?.[0];
      return p?.value != null ? { value: Number(p.value), date: p.date || null } : null;
    }),
    staleTime: 60 * 60 * 1000,
    retry: 1,
  });
  const avgRate = avgMortgage && Number.isFinite(avgMortgage.value) && avgMortgage.value > 0
    ? Math.round(avgMortgage.value * 10) / 10 : null;
  const rate = userRate ?? avgRate ?? 18;

  useCalcUrlSync({ price, down: downPct, rate, years }, { enabled: edited });

  // Отчёт об использовании — с паузой, чтобы не спамить слайдерами.
  useEffect(() => {
    const t = setTimeout(() => {
      track(events.CALC_MORTGAGE, { price, downPct, rate, years });
    }, 1500);
    return () => clearTimeout(t);
  }, [price, downPct, rate, years]);

  const result = useMemo(() => {
    const principal = Math.max(0, price * (1 - downPct / 100));
    const n = years * 12;
    const r = rate / 12 / 100;
    if (principal <= 0 || n <= 0) return null;
    // Платёж округляем до рубля до всех производных сумм: посетитель проверяет
    // калькулятор умножением платежа на число месяцев, и «итого» обязано
    // сойтись с этой арифметикой, иначе выглядит как ошибка расчёта.
    const exact = r > 0 ? principal * r / (1 - Math.pow(1 + r, -n)) : principal / n;
    const payment = Math.round(exact);
    const total = payment * n;
    const overpay = total - principal;

    // Годовой график остатка долга и накопленных процентов + разбивка
    // платежа на тело/проценты по годам (для интерактивного «Разбивка по
    // году» — созвон «На правки 13»: аннуитет неизменен по сумме, но доля
    // процентов внутри него падает год от года).
    let balance = principal;
    let interestPaid = 0;
    const series = [{ year: 0, balance: Math.round(balance), interest: 0 }];
    const yearly = [];
    let yearPrincipal = 0;
    let yearInterest = 0;
    for (let m = 1; m <= n; m += 1) {
      const int = balance * r;
      const princ = payment - int;
      interestPaid += int;
      yearInterest += int;
      yearPrincipal += princ;
      balance = Math.max(0, balance - princ);
      if (m % 12 === 0 || m === n) {
        const y = Math.ceil(m / 12);
        series.push({ year: y, balance: Math.round(balance), interest: Math.round(interestPaid) });
        yearly.push({
          year: y, balance: Math.round(balance),
          principalPaid: Math.round(yearPrincipal), interestPaid: Math.round(yearInterest),
        });
        yearPrincipal = 0;
        yearInterest = 0;
      }
    }
    return { principal, payment, total, overpay, series, yearly, down: price - principal };
  }, [price, downPct, rate, years]);

  const rubleTick = (v) => `${formatCompactTick(v)}\u00A0₽`;

  // График платежей, досрочное погашение и две ставки (lib/mortgageSchedule.js).
  const termMonths = years * 12;
  const principal = result?.principal ?? 0;
  const baseSchedule = useMemo(
    () => buildSchedule({ principal, ratePct: rate, months: termMonths }),
    [principal, rate, termMonths],
  );
  const hasExtra = extra.monthly > 0 || extra.lump > 0;
  const earlySchedule = useMemo(() => (hasExtra
    ? buildSchedule({
      principal, ratePct: rate, months: termMonths, monthlyExtra: extra.monthly, lumpAmount: extra.lump, lumpMonth: extra.lumpMonth, lumpMode: extra.lumpMode,
    })
    : baseSchedule), [hasExtra, principal, rate, termMonths, extra, baseSchedule]);
  const earlyGain = useMemo(() => earlyRepaymentGain(baseSchedule, earlySchedule), [baseSchedule, earlySchedule]);
  const comparison = useMemo(
    () => (rateB != null && principal > 0 ? compareRates({ principal, months: termMonths, rateA: rate, rateB }) : null),
    [rateB, principal, termMonths, rate],
  );
  const openCompare = useCallback(() => {
    // Вторая ставка по умолчанию: средняя по ипотеке сейчас, а если она совпала с первой, на пункт ниже.
    const candidate = avgRate != null && Math.abs(avgRate - rate) > 0.05 ? avgRate : Math.max(0.1, Math.round((rate - 1) * 10) / 10);
    setRateB(candidate);
  }, [avgRate, rate]);
  const comparePresets = useMemo(() => [
    ...(Number.isFinite(keyRate) && keyRate > 0 ? [{ id: 'key', label: t('c11e.cmp.presetKey'), rate: Math.round(keyRate * 10) / 10 }] : []),
    ...(avgRate != null ? [{ id: 'avg', label: t('c11e.cmp.presetAvg'), rate: avgRate }] : []),
  ], [keyRate, avgRate, t]);
  const saveTitle = t('c11e.save.titleMortgage', { price: fitRubles(price), rate: String(rate).replace('.', locale === 'en' ? '.' : ','), years: yearsLabel(years) });
  const savePayload = useMemo(() => ({ page: 'mortgage', price, down: downPct, rate, years }), [price, downPct, rate, years]);

  const yearCount = result?.yearly?.length || 1;
  const [selectedYear, setSelectedYear] = useState(1);
  // Клэмп инлайн, а не эффектом: срок могли сократить слайдером, старое
  // выбранное значение года может выйти за новый диапазон.
  const clampedYear = Math.min(Math.max(1, selectedYear), yearCount);
  const yearBreakdown = result?.yearly?.[clampedYear - 1] || null;

  return (
    <div className="fe-data-page fe-gutter fe-z8-calc pt-24 md:pt-28 pb-12 sm:pb-16">
      <div style={revealStyle(0)} className="fe-reveal mb-5">
        <Breadcrumbs items={toolTrail(t('calc.mortgage.title'), '/calculator/mortgage')} />
      </div>

      <header style={revealStyle(1)} className="fe-reveal fe-z8-calc__head">
        <div className="fe-z8-calc__icon" aria-hidden="true">
          <Home className="w-5 h-5" />
        </div>
        <div className="fe-z8-calc__headtext">
          <span className="w5-eyebrow">{t('calc.mortgage.eyebrow')}</span>
          <h1 className="fe-z8-calc__title">{t('calc.mortgage.title')}</h1>
          <p className="fe-z8-calc__lead">{t('calc.mortgage.subtitle')}</p>
          {locale === 'en' && (
            <p className="fe-z8-note" data-testid="mortgage-en-note">{t('z8.calc.mortgage.enNote')}</p>
          )}
          <CalcKeyRate rate={keyRate} pending={keyRatePending} />
        </div>
      </header>

      <CalculatorShowcase current="mortgage" />

      <div className="fe-z8-calc__grid">
      <div className="fe-z8-calc__side">
      <section style={revealStyle(2)} className="fe-reveal fe-panel fe-z8-card p-6 md:p-7 space-y-6">
        <CalcMoneyField
          id="mortgage-price"
          label={t('calc.mortgage.price')}
          unitName={t('calc.ui.unitRubles')}
          value={price}
          onChange={setPrice}
          prefix="₽"
          placeholder="8 000 000"
          max={PRICE_MAX}
          hint={t('c11e.mortgage.priceHint', { max: formatMoneyLimit(PRICE_MAX) })}
        />

        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-x-6 gap-y-5">
          <CalcSlider
            label={t('calc.mortgage.down')}
            value={downPct} onChange={setDownPct} min={0} max={90}
            display={`${downPct}% — ${result ? formatCompactTick(result.down) : 0}\u00A0₽`}
            editable suffix="%" extra={`— ${result ? formatCompactTick(result.down) : 0}\u00A0₽`}
          />
          <CalcSlider label={t('calc.mortgage.rate')} value={rate} onChange={changeRate} min={0.1} max={30} step={0.1} suffix="%" editable />
          <CalcSlider label={t('calc.mortgage.term')} value={years} onChange={setYears} min={1} max={30} display={yearsLabel(years)} editable suffix={` ${t('calc.compound.yearsUnit')}`} />
        </div>
        {avgRate != null && (
          <p className="fe-z8-note" data-testid="mortgage-avg-rate">
            {t('c9d.mortgage.avgRate', {
              rate: String(avgRate).replace('.', locale === 'en' ? '.' : ','),
              date: avgMortgage.date ? formatDate(avgMortgage.date, 'short') : '',
            })}
            {Math.abs(rate - avgRate) > 0.05 && (
              <>
                {' '}
                <button type="button" className="font-medium text-champagne-ink hover:underline" onClick={() => changeRate(avgRate)}>
                  {t('c9d.mortgage.useAvg')}
                </button>
              </>
            )}
          </p>
        )}
      </section>

      {result && (
        <aside style={revealStyle(3)} className="fe-reveal fe-z8-hint" data-block="calc-hint">
          <span className="fe-z8-hint__label">{t('z8.calc.hint.label')}</span>
          <p className="fe-z8-hint__big">{fitRubles(result.overpay)}</p>
          <p className="fe-z8-hint__line">{t('z8.calc.hint.mortgage', { years: yearsLabel(years) })}</p>
          <p className="fe-z8-hint__sub">{t('z8.calc.hint.mortgageSub', { pct: fmtPct(result.principal ? (result.overpay / result.principal) * 100 : 0) })}</p>
        </aside>
      )}
      </div>

      <div className="fe-z8-calc__out">
      {result && (
        <>
          <section ref={resultRef} style={revealStyle(3)} className="fe-reveal fe-z8-result fe-k8-stone fe-glint rounded-[2rem] p-6 md:p-8 mb-6 min-h-[19rem]" aria-live="polite">
            <div className="grid grid-cols-1 2xl:grid-cols-[1fr_auto] gap-6 items-center">
              <div>
                <p className="text-sm text-text-secondary mb-2">{t('calc.mortgage.payment')}</p>
                <CalcAnimatedNumber
                  value={result.payment}
                  format={fitRubles}
                  className={`block min-h-[1.2em] font-display font-bold tracking-tight text-text-primary ${heroSize(fitRubles(result.payment))} mb-6`}
                />
                <CalcStatGrid>
                  <CalcStatTile index={0} label={t('calc.mortgage.principal')} value={fitRubles(result.principal)} />
                  <CalcStatTile index={1} label={t('calc.mortgage.overpay')} value={fitRubles(result.overpay)} accent />
                  <CalcStatTile index={2} label={t('calc.mortgage.total')} value={fitRubles(result.total)} />
                </CalcStatGrid>
                <CalcSaveSlot
                  className="mt-4"
                  renderSave={renderSave}
                  itemKey={`mortgage:${price}:${downPct}:${rate}:${years}`}
                  title={saveTitle}
                  payload={savePayload}
                />
              </div>

              <div className="flex flex-col items-center shrink-0 mx-auto 2xl:mx-0">
                <div ref={pieBoxRef} onPointerDownCapture={pieTouch.onPointerDownCapture} className="relative w-[168px] h-[168px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={[
                          { name: t('calc.mortgage.principalShort'), value: result.principal },
                          { name: t('calc.mortgage.overpay'), value: result.overpay },
                        ]}
                        dataKey="value" nameKey="name"
                        innerRadius={54} outerRadius={78}
                        paddingAngle={2} startAngle={90} endAngle={-270}
                        stroke="none" isAnimationActive={false}
                      >
                        <Cell fill={PRINCIPAL_COLOR} />
                        <Cell fill={OVERPAY_COLOR} />
                      </Pie>
                      <Tooltip
                        {...TOOLTIP_STYLES}
                        {...pieTouch.tooltipProps}
                        formatter={(v, name) => [formatRubles(v), name]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-xs text-text-secondary">{t('calc.mortgage.overpay')}</span>
                    <span className="text-xl font-bold text-text-primary tabular-nums">
                      {fmtPct(result.principal ? (result.overpay / result.principal) * 100 : 0)}
                    </span>
                  </div>
                </div>
                <div className="flex gap-4 mt-3 text-xs">
                  <span className="flex items-center gap-1.5 text-text-secondary">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: PRINCIPAL_COLOR }} />{t('calc.mortgage.credit')}
                  </span>
                  <span className="flex items-center gap-1.5 text-text-secondary">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: OVERPAY_COLOR }} />{t('calc.mortgage.overpay')}
                  </span>
                </div>
              </div>
            </div>
          </section>

          <section ref={setChartWidthNode} style={revealStyle(4)} className="fe-reveal fe-panel rounded-[2rem] shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
            <h3 className="text-base font-semibold text-text-primary mb-5">
              {t('calc.mortgage.chartTitle')}
            </h3>
            <div ref={areaBoxRef} onPointerDownCapture={(event) => { areaTouch.onPointerDownCapture(event); touchHint.dismiss(); }}>
              <ResponsiveContainer width="100%" height={chartWidth > 0 && chartWidth < 560 ? 260 : 300}>
                <AreaChart data={result.series} margin={{ top: 8, right: 12, bottom: 5, left: 4 }}>
                  <defs>
                    <linearGradient id="mortBal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_THEME.champagne} stopOpacity={0.2} />
                      <stop offset="100%" stopColor={CHART_THEME.champagne} stopOpacity={0.01} />
                    </linearGradient>
                    <linearGradient id="mortInt" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={OVERPAY_COLOR} stopOpacity={0.14} />
                      <stop offset="100%" stopColor={OVERPAY_COLOR} stopOpacity={0.01} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis dataKey="year" stroke={CHART_THEME.axisLine} tick={axisTick({ fontSize: 13 })} tickLine={false}
                    ticks={evenYearTicks(result.series[result.series.length - 1]?.year)} interval={0}
                    tickFormatter={(y) => (y === 0 ? t('w5.calc.axisStart') : t('w5.calc.axisYear', { n: y }))} />
                  <YAxis stroke={CHART_THEME.axisLine} tick={axisTick({ fontSize: 13 })}
                    tickLine={false} axisLine={false} tickFormatter={rubleTick}
                    width={axisWidthForLabels(result.series.flatMap((p) => [rubleTick(p.balance), rubleTick(p.interest)]), { min: 56, perChar: 6.8, pad: 10 })} />
                  <Tooltip
                    {...TOOLTIP_STYLES}
                    {...areaTouch.tooltipProps}
                    formatter={(v, name) => [formatRubles(v), name === 'balance' ? t('calc.mortgage.balance') : t('calc.mortgage.interestAccum')]}
                    labelFormatter={(v) => t('calc.yearN', { n: v })}
                  />
                  <Area dataKey="balance" name="balance" stroke={CHART_THEME.champagne} strokeWidth={2} fill="url(#mortBal)" dot={false} isAnimationActive={false} />
                  <Area dataKey="interest" name="interest" stroke={OVERPAY_COLOR} strokeWidth={1.8} fill="url(#mortInt)" dot={false} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <ChartLegend
              items={[
                { color: CHART_THEME.champagne, label: t('calc.mortgage.balance') },
                { color: OVERPAY_COLOR, label: t('calc.mortgage.interestAccum') },
              ]}
            />
            <ChartTouchHint visible={touchHint.visible} />
          </section>

          {yearBreakdown && (
            <section style={revealStyle(5)} className="fe-reveal fe-panel rounded-[2rem] shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
              <div className="flex items-center gap-2 mb-1">
                <PieIcon className="w-4 h-4 text-champagne" />
                <h3 className="text-base font-semibold text-text-primary">
                  {t('calc.mortgage.yearBreakdownTitle')}
                </h3>
              </div>
              <p className="text-xs text-text-secondary mb-4">
                {t('calc.mortgage.yearBreakdownHint')}
              </p>
              <CalcSlider
                label={t('calc.mortgage.loanYear')}
                value={clampedYear} onChange={setSelectedYear} min={1} max={yearCount}
                display={t('calc.mortgage.yearOf', {
                  year: loanYearOrdinal(clampedYear, locale),
                  total: yearCount,
                })}
              />
              <CalcStatGrid className="mt-5 w5-tiles--three">
                <CalcStatTile index={0} label={t('calc.mortgage.interestYear')} value={fitRubles(yearBreakdown.interestPaid)} accent />
                <CalcStatTile index={1} label={t('calc.mortgage.principalYear')} value={fitRubles(yearBreakdown.principalPaid)} />
                <CalcStatTile index={2} label={t('calc.mortgage.balanceYearEnd')} value={fitRubles(yearBreakdown.balance)} />
              </CalcStatGrid>
              <div className="mt-4 h-3.5 flex fe-k8-tube">
                <div
                  className="h-full transition-all duration-300"
                  style={{
                    width: `${(yearBreakdown.interestPaid / (yearBreakdown.interestPaid + yearBreakdown.principalPaid || 1)) * 100}%`,
                    backgroundColor: OVERPAY_COLOR,
                  }}
                  title={t('calc.mortgage.interest')}
                />
                <div
                  className="h-full flex-1 transition-all duration-300"
                  style={{ backgroundColor: CHART_THEME.champagne }}
                  title={t('calc.mortgage.principalBody')}
                />
              </div>
              <div className="flex justify-between gap-3 mt-1.5 text-xs text-text-secondary">
                <span>{t('calc.mortgage.splitInterest', { pct: fmtPct((yearBreakdown.interestPaid / (yearBreakdown.interestPaid + yearBreakdown.principalPaid || 1)) * 100) })}</span>
                <span>{t('calc.mortgage.splitPrincipal', { pct: fmtPct((yearBreakdown.principalPaid / (yearBreakdown.interestPaid + yearBreakdown.principalPaid || 1)) * 100) })}</span>
              </div>
            </section>
          )}

          <CalcMortgageExtras
            value={extra}
            onChange={setExtra}
            termMonths={termMonths}
            base={baseSchedule}
            early={earlySchedule}
            gain={earlyGain}
            index={6}
          />

          <CalcRateCompare
            rateB={rateB}
            onRateB={setRateB}
            onOpen={openCompare}
            onClose={() => setRateB(null)}
            rateA={rate}
            comparison={comparison}
            presets={comparePresets}
            index={7}
          />

          <CalcMortgageSchedule
            schedule={earlySchedule}
            filenameBase={`mortgage-${Math.round(price)}-${String(rate).replace('.', '_')}-${years}y`}
            historyParams={{ page: 'mortgage', price, down: downPct, rate, years, extra }}
            index={8}
          />

          <section style={revealStyle(9)} className="fe-reveal grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-6">
            <div className="flex items-start gap-3 p-3.5 rounded-xl fe-glass-2">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Percent className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                {t('calc.mortgage.insight.ratePoint', { amount: formatRubles(result.principal * years / 100 * 0.55) })}
              </p>
            </div>
            <div className="flex items-start gap-3 p-3.5 rounded-xl fe-glass-2">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Clock className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                {t('calc.mortgage.insight.firstYear', {
                  toDebt: formatRubles(Math.max(0, result.series[0].balance - (result.series[1]?.balance ?? 0))),
                  paid: formatRubles(result.payment * 12),
                })}
              </p>
            </div>
            <div className="flex items-start gap-3 p-3.5 rounded-xl sm:col-span-2 fe-glass-2">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Wallet className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                {t('calc.mortgage.insight.income', { income: formatRubles(result.payment / 0.45) })}
              </p>
            </div>
          </section>
        </>
      )}
      </div>
      </div>

      <CalcStickyResult
        targetRef={resultRef}
        active={Boolean(result)}
        label={t('calc.mortgage.payment')}
        value={result ? fitRubles(result.payment) : ''}
      />

      <div className="fe-z8-calc__lower">
      <div style={revealStyle(7)} className="fe-reveal fe-z8-calc__method">
        <CalcMethod
          paragraphs={[t('w5.calc.mortgage.how.p1'), t('w5.calc.mortgage.how.p2')]}
        >
          <p>
            {t('calc.mortgage.method.p3before')}{' '}
            <Link to={russiaIndicatorPath('key-rate')}>{t('calc.mortgage.method.keyRateLink')}</Link>.
          </p>
        </CalcMethod>
      </div>

      <section style={revealStyle(8)} className="fe-reveal fe-z8-calc__faq">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">{t('calc.faqHeading')}</h2>
        <FaqAccordion
          items={faqItems}
          onToggle={({ title, open }) => { if (open) track(events.FAQ_TOGGLE, { question: title }); }}
        />
      </section>

      <div style={revealStyle(9)} className="fe-reveal fe-z8-calc__siblings">
        <CalculatorSiblings current="mortgage" />
      </div>
      </div>
    </div>
  );
}
