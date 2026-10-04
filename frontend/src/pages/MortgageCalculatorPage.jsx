import { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
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
import { CHART_THEME, GRID_PROPS, TOOLTIP_STYLES, axisTick, axisWidthForLabels } from '../lib/chartTheme';
import { useElementWidth, useTouchTooltip } from '../lib/chartHooks';
import { revealStyle } from '../lib/calcUi';
import { formatRubles, fmtPct, loanYearOrdinal, evenYearTicks, years as yearsPhrase } from '../lib/calcFormat';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import FaqAccordion from '../components/FaqAccordion';
import Breadcrumbs from '../components/Breadcrumbs';
import CalculatorSiblings from '../components/CalculatorSiblings';
import { toolTrail } from '../lib/breadcrumbs';
import CalcSlider from '../components/CalcSlider';
import CalcMoneyField from '../components/CalcMoneyField';
import CalcAnimatedNumber from '../components/CalcAnimatedNumber';
import { CalcStatGrid, CalcStatTile } from '../components/CalcStatTile';
import CalcMethod from '../components/CalcMethod';
import CalcKeyRate from '../components/CalcKeyRate';
import ChartTouchHint, { ChartLegend } from '../components/ChartTouchHint';
import { useChartTouchHint } from '../lib/useChartTouchHint';
import '../styles/w5-tools.css';
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

export default function MortgageCalculatorPage() {
  const t = useT();
  const { locale } = useLocale();
  const faqItems = FAQ_KEYS.map((item) => ({ q: t(item.q), a: t(item.a) }));
  const areaBoxRef = useRef(null);
  const pieBoxRef = useRef(null);
  const areaTouch = useTouchTooltip(areaBoxRef);
  const pieTouch = useTouchTooltip(pieBoxRef);
  const touchHint = useChartTouchHint();
  const [setChartWidthNode, chartWidth] = useElementWidth();
  const yearsLabel = (n) => (locale === 'en' ? t('calc.years', { n }) : yearsPhrase(n));
  const [price, setPrice] = useState(8000000);
  const [downPct, setDownPct] = useState(20);
  const [rate, setRate] = useState(18);
  const [years, setYears] = useState(20);

  const mortgageSeo = getPageSeo('calculator-mortgage', locale);
  useDocumentMeta({
    title: mortgageSeo.title,
    description: mortgageSeo.description,
    path: mortgageSeo.path,
  });
  useScrollDepth({ key: 'calc-mortgage', page: 'calculator-mortgage' });

  const { data: keyRate } = useQuery({
    queryKey: ['key-rate-latest'],
    queryFn: () => api.get('/indicators/key-rate/data?limit=1').then((r) => {
      const p = r.data?.data?.[0];
      return p?.value != null ? Number(p.value) : null;
    }),
    staleTime: 60 * 60 * 1000,
    retry: 1,
  });

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

  const yearCount = result?.yearly?.length || 1;
  const [selectedYear, setSelectedYear] = useState(1);
  // Клэмп инлайн, а не эффектом: срок могли сократить слайдером, старое
  // выбранное значение года может выйти за новый диапазон.
  const clampedYear = Math.min(Math.max(1, selectedYear), yearCount);
  const yearBreakdown = result?.yearly?.[clampedYear - 1] || null;

  return (
    <div className="fe-data-page max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-12 sm:pb-16">
      <div style={revealStyle(0)} className="fe-reveal mb-8">
        <Breadcrumbs items={toolTrail(t('calc.mortgage.title'), '/calculator/mortgage')} />
      </div>

      <header style={revealStyle(1)} className="fe-reveal mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-2xl bg-champagne/10 border border-champagne/20">
            <Home className="w-5 h-5 text-champagne" />
          </div>
          <span className="w5-eyebrow">{t('calc.mortgage.eyebrow')}</span>
        </div>
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold tracking-tight text-text-primary leading-tight mb-3">
          {t('calc.mortgage.title')}
        </h1>
        <p className="text-base text-text-secondary leading-relaxed max-w-xl">
          {t('calc.mortgage.subtitle')}
        </p>
        <CalcKeyRate rate={keyRate} />
      </header>

      <section style={revealStyle(2)} className="fe-reveal fe-panel rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6 space-y-6">
        <CalcMoneyField
          id="mortgage-price"
          label={t('calc.mortgage.price')}
          unitName={t('calc.ui.unitRubles')}
          value={price}
          onChange={setPrice}
          prefix="₽"
          placeholder="8 000 000"
        />

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-5">
          <CalcSlider
            label={t('calc.mortgage.down')}
            value={downPct} onChange={setDownPct} min={0} max={90}
            display={`${downPct}% — ${result ? formatCompactTick(result.down) : 0}\u00A0₽`}
          />
          <CalcSlider label={t('calc.mortgage.rate')} value={rate} onChange={setRate} min={0.1} max={30} step={0.1} suffix="%" />
          <CalcSlider label={t('calc.mortgage.term')} value={years} onChange={setYears} min={1} max={30} display={yearsLabel(years)} />
        </div>
      </section>

      {result && (
        <>
          <section style={revealStyle(3)} className="fe-reveal fe-panel rounded-[2rem] bg-surface border border-border-champagne p-6 md:p-8 mb-6 min-h-[19rem]" aria-live="polite">
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-6 items-center">
              <div>
                <p className="text-sm text-text-secondary mb-2">{t('calc.mortgage.payment')}</p>
                <CalcAnimatedNumber
                  value={result.payment}
                  format={formatRubles}
                  className="block min-h-[1.2em] font-display font-bold tracking-tight text-text-primary text-4xl md:text-5xl lg:text-6xl mb-6"
                />
                <CalcStatGrid>
                  <CalcStatTile index={0} label={t('calc.mortgage.principal')} value={formatRubles(result.principal)} />
                  <CalcStatTile index={1} label={t('calc.mortgage.overpay')} value={formatRubles(result.overpay)} accent />
                  <CalcStatTile index={2} label={t('calc.mortgage.total')} value={formatRubles(result.total)} />
                </CalcStatGrid>
              </div>

              <div className="flex flex-col items-center shrink-0 mx-auto lg:mx-0">
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
                        <Cell fill={CHART_THEME.champagne} />
                        <Cell fill={CHART_THEME.ink} fillOpacity={0.85} />
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
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: CHART_THEME.champagne }} />{t('calc.mortgage.credit')}
                  </span>
                  <span className="flex items-center gap-1.5 text-text-secondary">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: CHART_THEME.ink, opacity: 0.85 }} />{t('calc.mortgage.overpay')}
                  </span>
                </div>
              </div>
            </div>
          </section>

          <section ref={setChartWidthNode} style={revealStyle(4)} className="fe-reveal fe-panel rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
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
                      <stop offset="0%" stopColor={CHART_THEME.ink} stopOpacity={0.12} />
                      <stop offset="100%" stopColor={CHART_THEME.ink} stopOpacity={0.01} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis dataKey="year" stroke={CHART_THEME.axisLine} tick={axisTick()} tickLine={false}
                    ticks={evenYearTicks(result.series[result.series.length - 1]?.year)} interval={0}
                    tickFormatter={(y) => (y === 0 ? t('w5.calc.axisStart') : t('w5.calc.axisYear', { n: y }))} />
                  <YAxis stroke={CHART_THEME.axisLine} tick={axisTick()}
                    tickLine={false} axisLine={false} tickFormatter={rubleTick}
                    width={axisWidthForLabels(result.series.flatMap((p) => [rubleTick(p.balance), rubleTick(p.interest)]), { min: 56, perChar: 6.8, pad: 10 })} />
                  <Tooltip
                    {...TOOLTIP_STYLES}
                    {...areaTouch.tooltipProps}
                    formatter={(v, name) => [formatRubles(v), name === 'balance' ? t('calc.mortgage.balance') : t('calc.mortgage.interestAccum')]}
                    labelFormatter={(v) => t('calc.yearN', { n: v })}
                  />
                  <Area dataKey="balance" name="balance" stroke={CHART_THEME.champagne} strokeWidth={2} fill="url(#mortBal)" dot={false} isAnimationActive={false} />
                  <Area dataKey="interest" name="interest" stroke={CHART_THEME.ink} strokeWidth={1.4} fill="url(#mortInt)" dot={false} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <ChartLegend
              items={[
                { color: CHART_THEME.champagne, label: t('calc.mortgage.balance') },
                { color: CHART_THEME.ink, label: t('calc.mortgage.interestAccum') },
              ]}
            />
            <ChartTouchHint visible={touchHint.visible} />
          </section>

          {yearBreakdown && (
            <section style={revealStyle(5)} className="fe-reveal fe-panel rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
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
                <CalcStatTile index={0} label={t('calc.mortgage.interestYear')} value={formatRubles(yearBreakdown.interestPaid)} accent />
                <CalcStatTile index={1} label={t('calc.mortgage.principalYear')} value={formatRubles(yearBreakdown.principalPaid)} />
                <CalcStatTile index={2} label={t('calc.mortgage.balanceYearEnd')} value={formatRubles(yearBreakdown.balance)} />
              </CalcStatGrid>
              <div className="mt-4 h-3 rounded-full overflow-hidden bg-obsidian border border-border-subtle flex">
                <div
                  className="h-full transition-all duration-300"
                  style={{
                    width: `${(yearBreakdown.interestPaid / (yearBreakdown.interestPaid + yearBreakdown.principalPaid || 1)) * 100}%`,
                    backgroundColor: CHART_THEME.ink, opacity: 0.85,
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

          <section style={revealStyle(6)} className="fe-reveal grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-6">
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-obsidian-light/70 border border-border-subtle">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Percent className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                {t('calc.mortgage.insight.ratePoint', { amount: formatRubles(result.principal * years / 100 * 0.55) })}
              </p>
            </div>
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-obsidian-light/70 border border-border-subtle">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Clock className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                {t('calc.mortgage.insight.firstYear', {
                  toDebt: formatRubles(Math.max(0, result.series[0].balance - (result.series[1]?.balance ?? 0))),
                  paid: formatRubles(result.payment * 12),
                })}
              </p>
            </div>
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-obsidian-light/70 border border-border-subtle sm:col-span-2">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Wallet className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                {t('calc.mortgage.insight.income', { income: formatRubles(result.payment / 0.45) })}
              </p>
            </div>
          </section>
        </>
      )}

      <div style={revealStyle(7)} className="fe-reveal">
        <CalcMethod
          paragraphs={[t('w5.calc.mortgage.how.p1'), t('w5.calc.mortgage.how.p2')]}
        >
          <p>
            {t('calc.mortgage.method.p3before')}{' '}
            <Link to={russiaIndicatorPath('key-rate')}>{t('calc.mortgage.method.keyRateLink')}</Link>.
          </p>
        </CalcMethod>
      </div>

      <section style={revealStyle(8)} className="fe-reveal mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">{t('calc.faqHeading')}</h2>
        <FaqAccordion
          items={faqItems}
          onToggle={({ title, open }) => { if (open) track(events.FAQ_TOGGLE, { question: title }); }}
        />
      </section>

      <div style={revealStyle(9)} className="fe-reveal">
        <CalculatorSiblings current="mortgage" />
      </div>
    </div>
  );
}
