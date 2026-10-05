import { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import { TrendingUp, Flame, PiggyBank } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { formatCompactTick } from '../lib/regionsApi';
import { CHART_THEME, GRID_PROPS, TOOLTIP_STYLES, axisTick, axisWidthForLabels } from '../lib/chartTheme';
import { useElementWidth, useTouchTooltip } from '../lib/chartHooks';
import { revealStyle } from '../lib/calcUi';
import { formatRubles, fmtPct, decimalText, evenYearTicks, years as yearsPhrase } from '../lib/calcFormat';
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
import { CalcStatGrid, CalcStatTile } from '../components/CalcStatTile';
import CalcMethod from '../components/CalcMethod';
import CalcKeyRate from '../components/CalcKeyRate';
import ChartTouchHint, { ChartLegend } from '../components/ChartTouchHint';
import { useChartTouchHint } from '../lib/useChartTouchHint';
import '../styles/w5-tools.css';
import '../styles/z8-tools.css';
import { useT, useLocale } from '../i18n';
import {
  russiaIndicatorPath,
} from '../lib/sitePaths';

const FAQ_KEYS = [
  { q: 'calc.compound.faq.q1', a: 'calc.compound.faq.a1' },
  { q: 'calc.compound.faq.q2', a: 'calc.compound.faq.a2' },
  { q: 'calc.compound.faq.q3', a: 'calc.compound.faq.a3' },
  { q: 'calc.compound.faq.q4', a: 'calc.compound.faq.a4' },
  { q: 'calc.compound.faq.q5', a: 'calc.compound.faq.a5' },
];

export default function CompoundCalculatorPage() {
  const t = useT();
  const { locale } = useLocale();
  const faqItems = FAQ_KEYS.map((item) => ({ q: t(item.q), a: t(item.a) }));
  const chartBoxRef = useRef(null);
  const touchTip = useTouchTooltip(chartBoxRef);
  const touchHint = useChartTouchHint();
  const [setChartWidthNode, chartWidth] = useElementWidth();
  const [initial, setInitial] = useState(100000);
  const [monthly, setMonthly] = useState(10000);
  const [rate, setRate] = useState(12);
  const [years, setYears] = useState(10);
  const [inflation, setInflation] = useState(6);

  const yearsLabel = (n) => (locale === 'en' ? t('calc.years', { n }) : yearsPhrase(n));

  const compoundSeo = getPageSeo('calculator-compound', locale);
  useDocumentMeta({
    title: compoundSeo.title,
    description: compoundSeo.description,
    path: compoundSeo.path,
  });
  useScrollDepth({ key: 'calc-compound', page: 'calculator-compound' });

  const { data: keyRate } = useQuery({
    queryKey: ['key-rate-latest'],
    queryFn: () => api.get('/indicators/key-rate/data?limit=1').then((r) => {
      const p = r.data?.data?.[0];
      return p?.value != null ? Number(p.value) : null;
    }),
    staleTime: 60 * 60 * 1000,
    retry: 1,
  });

  useEffect(() => {
    const t = setTimeout(() => {
      track(events.CALC_COMPOUND, { initial, monthly, rate, years, inflation });
    }, 1500);
    return () => clearTimeout(t);
  }, [initial, monthly, rate, years, inflation]);

  const rubleTick = (v) => `${formatCompactTick(v)}\u00A0₽`;

  const result = useMemo(() => {
    const n = years * 12;
    const r = rate / 12 / 100;
    const infMonthly = Math.pow(1 + inflation / 100, 1 / 12) - 1;
    let balance = initial;
    let invested = initial;
    let deflator = 1;
    const series = [{ year: 0, balance: Math.round(balance), invested: Math.round(invested), real: Math.round(balance) }];
    for (let m = 1; m <= n; m += 1) {
      balance = balance * (1 + r) + monthly;
      invested += monthly;
      deflator *= 1 + infMonthly;
      if (m % 12 === 0) {
        series.push({
          year: m / 12,
          balance: Math.round(balance),
          invested: Math.round(invested),
          real: Math.round(balance / deflator),
        });
      }
    }
    const gain = balance - invested;
    const real = balance / deflator;
    const doubling = rate > 0 ? 72 / rate : null;
    return { balance, invested, gain, real, series, doubling };
  }, [initial, monthly, rate, years, inflation]);

  return (
    <div className="fe-data-page fe-gutter fe-z8-calc pt-24 md:pt-28 pb-12 sm:pb-16">
      <div style={revealStyle(0)} className="fe-reveal mb-5">
        <Breadcrumbs items={toolTrail(t('calc.compound.title'), '/calculator/compound')} />
      </div>

      <header style={revealStyle(1)} className="fe-reveal fe-z8-calc__head">
        <div className="fe-z8-calc__icon" aria-hidden="true">
          <TrendingUp className="w-5 h-5" />
        </div>
        <div className="fe-z8-calc__headtext">
          <span className="w5-eyebrow">{t('calc.compound.eyebrow')}</span>
          <h1 className="fe-z8-calc__title">{t('calc.compound.title')}</h1>
          <p className="fe-z8-calc__lead">{t('calc.compound.subtitle')}</p>
          <CalcKeyRate rate={keyRate} />
        </div>
      </header>

      <CalculatorShowcase current="compound" />

      <div className="fe-z8-calc__grid">
      <div className="fe-z8-calc__side">
      <section style={revealStyle(2)} className="fe-reveal fe-panel fe-z8-card p-6 md:p-7 space-y-6">
        <div className="grid sm:grid-cols-2 lg:grid-cols-1 gap-6">
          <CalcMoneyField
            label={t('calc.compound.initial')} unitName={t('calc.ui.unitRubles')}
            value={initial} onChange={setInitial} prefix="₽" placeholder="100 000" size="md" allowZero
          />
          <CalcMoneyField
            label={t('calc.compound.monthly')} unitName={t('calc.ui.unitRubles')}
            value={monthly} onChange={setMonthly} prefix="₽" placeholder="10 000" size="md" allowZero
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-x-6 gap-y-5">
          <CalcSlider label={t('calc.compound.rate')} value={rate} onChange={setRate} min={0.1} max={30} step={0.1} suffix="%" />
          <CalcSlider label={t('calc.compound.term')} value={years} onChange={setYears} min={1} max={40} display={yearsLabel(years)} />
          <CalcSlider label={t('calc.compound.inflation')} value={inflation} onChange={setInflation} min={0} max={20} step={0.5} suffix="%" />
        </div>
      </section>

      {result && (
        <aside style={revealStyle(3)} className="fe-reveal fe-z8-hint" data-block="calc-hint">
          <span className="fe-z8-hint__label">{t('z8.calc.hint.label')}</span>
          <p className="fe-z8-hint__big">{`×${decimalText(result.invested ? result.balance / result.invested : 1, 1)}`}</p>
          <p className="fe-z8-hint__line">{t('z8.calc.hint.compound', { years: yearsLabel(years) })}</p>
          <p className="fe-z8-hint__sub">{t('z8.calc.hint.compoundSub', { amount: formatRubles(result.gain) })}</p>
        </aside>
      )}
      </div>

      <div className="fe-z8-calc__out">
      {result && (
        <>
          <section style={revealStyle(3)} className="fe-reveal fe-panel fe-z8-result rounded-[2rem] p-6 md:p-8 mb-6 min-h-[17rem]" aria-live="polite">
            <p className="text-sm text-text-secondary mb-2">{t('calc.compound.growsIn', {
              years: yearsLabel(years),
            })}</p>
            <CalcAnimatedNumber
              value={Math.round(result.balance)}
              format={formatRubles}
              className="block min-h-[1.2em] font-display font-bold tracking-tight text-text-primary text-4xl md:text-5xl lg:text-6xl mb-6"
            />
            <CalcStatGrid>
              <CalcStatTile index={0} label={t('calc.compound.invested')} value={formatRubles(result.invested)} />
              <CalcStatTile index={1} label={t('calc.compound.gain')} value={formatRubles(result.gain)} accent />
              <CalcStatTile index={2} label={t('calc.compound.real')} value={formatRubles(result.real)} />
              {result.doubling && result.doubling < 100 && (
                <CalcStatTile index={3} label={t('calc.compound.doubling')} value={`≈ ${decimalText(result.doubling, 1)} ${t('calc.compound.yearsUnit')}`} />
              )}
            </CalcStatGrid>
          </section>

          <section ref={setChartWidthNode} style={revealStyle(4)} className="fe-reveal fe-panel rounded-[2rem] shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
            <h3 className="text-base font-semibold text-text-primary mb-5">
              {t('calc.compound.chartTitle')}
            </h3>
            <div ref={chartBoxRef} onPointerDownCapture={(event) => { touchTip.onPointerDownCapture(event); touchHint.dismiss(); }}>
              <ResponsiveContainer width="100%" height={chartWidth > 0 && chartWidth < 560 ? 260 : 300}>
                <AreaChart data={result.series} margin={{ top: 8, right: 12, bottom: 5, left: 4 }}>
                  <defs>
                    <linearGradient id="cmpBal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_THEME.champagne} stopOpacity={0.2} />
                      <stop offset="100%" stopColor={CHART_THEME.champagne} stopOpacity={0.01} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis dataKey="year" stroke={CHART_THEME.axisLine} tick={axisTick({ fontSize: 13 })} tickLine={false}
                    ticks={evenYearTicks(result.series[result.series.length - 1]?.year)} interval={0}
                    tickFormatter={(y) => (y === 0 ? t('w5.calc.axisStart') : t('w5.calc.axisYear', { n: y }))} />
                  <YAxis stroke={CHART_THEME.axisLine} tick={axisTick({ fontSize: 13 })}
                    tickLine={false} axisLine={false} tickFormatter={rubleTick}
                    width={axisWidthForLabels(result.series.flatMap((p) => [rubleTick(p.balance), rubleTick(0)]), { min: 56, perChar: 6.8, pad: 10 })} />
                  <Tooltip
                    {...TOOLTIP_STYLES}
                    {...touchTip.tooltipProps}
                    formatter={(v, name) => [
                      formatRubles(v),
                      name === 'balance' ? t('calc.compound.capital') : name === 'invested' ? t('calc.compound.invested') : t('calc.compound.real'),
                    ]}
                    labelFormatter={(v) => t('calc.yearN', { n: v })}
                  />
                  <Area dataKey="balance" name="balance" stroke={CHART_THEME.champagne} strokeWidth={2} fill="url(#cmpBal)" dot={false} isAnimationActive={false} />
                  <Area dataKey="invested" name="invested" stroke={CHART_THEME.ink} strokeWidth={1.4} fill="none" strokeDasharray="6 4" dot={false} isAnimationActive={false} />
                  <Area dataKey="real" name="real" stroke={CHART_THEME.blue} strokeWidth={1.4} fill="none" dot={false} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <ChartLegend
              items={[
                { color: CHART_THEME.champagne, label: t('calc.compound.capital') },
                { color: CHART_THEME.ink, label: t('calc.compound.invested'), dashed: true },
                { color: CHART_THEME.blue, label: t('w5.calc.compound.legendReal', { rate: fmtPct(inflation) }) },
              ]}
            />
            <ChartTouchHint visible={touchHint.visible} />
          </section>

          <section style={revealStyle(5)} className="fe-reveal grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-6">
            <div className="flex items-start gap-3 p-3.5 rounded-xl fe-glass-2">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Flame className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                {t('calc.compound.insight.gain', {
                  pct: fmtPct(result.balance ? (result.gain / result.balance) * 100 : 0),
                  tail: result.gain > result.invested ? t('calc.compound.insight.gainMore') : t('calc.compound.insight.gainLess'),
                })}
              </p>
            </div>
            <div className="flex items-start gap-3 p-3.5 rounded-xl fe-glass-2">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><PiggyBank className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                {t('calc.compound.insight.inflation', {
                  rate: fmtPct(inflation),
                  amount: formatRubles(result.balance - result.real),
                })}
              </p>
            </div>
          </section>
        </>
      )}
      </div>
      </div>

      <div className="fe-z8-calc__lower">
      <div style={revealStyle(6)} className="fe-reveal fe-z8-calc__method">
        <CalcMethod
          paragraphs={[t('w5.calc.compound.how.p1'), t('w5.calc.compound.how.p2')]}
        >
          <p>
            {t('calc.compound.method.refsBefore')}{' '}
            <Link to={russiaIndicatorPath('key-rate')}>{t('calc.compound.method.keyRate')}</Link>,{' '}
            <Link to={russiaIndicatorPath('ruonia')}>{t('calc.compound.method.ruonia')}</Link>
            ; {t('calc.compound.method.inflationBefore')}{' '}
            <Link to="/calculator">{t('calc.compound.method.inflationLink')}</Link>.
          </p>
        </CalcMethod>
      </div>

      <section style={revealStyle(7)} className="fe-reveal fe-z8-calc__faq">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">{t('calc.faqHeading')}</h2>
        <FaqAccordion
          items={faqItems}
          onToggle={({ title, open }) => { if (open) track(events.FAQ_TOGGLE, { question: title }); }}
        />
      </section>

      <div style={revealStyle(8)} className="fe-reveal fe-z8-calc__siblings">
        <CalculatorSiblings current="compound" />
      </div>
      </div>
    </div>
  );
}
