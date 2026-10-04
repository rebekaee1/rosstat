import { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';
import { TrendingUp, Flame, PiggyBank } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { cn } from '../lib/format';
import { formatCompactTick, compactTickAxisWidth } from '../lib/regionsApi';
import { CHART_THEME, GRID_PROPS, TOOLTIP_STYLES, axisTick } from '../lib/chartTheme';
import { useElementWidth, useTouchTooltip } from '../lib/chartHooks';
import { revealStyle } from '../lib/calcUi';
import { formatRubles, fmtPct, years as yearsPhrase } from '../lib/calcFormat';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import FaqAccordion from '../components/FaqAccordion';
import Breadcrumbs from '../components/Breadcrumbs';
import CalculatorSiblings from '../components/CalculatorSiblings';
import { toolTrail } from '../lib/breadcrumbs';
import CalcSlider from '../components/CalcSlider';
import CalcMoneyField from '../components/CalcMoneyField';
import CalcAnimatedNumber from '../components/CalcAnimatedNumber';
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

function StatPill({ label, value, accent }) {
  return (
    <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
      <p className="text-[11px] uppercase tracking-[0.15em] text-text-secondary font-medium mb-0.5">{label}</p>
      <p className={cn('text-base font-mono font-bold tabular-nums', accent ? 'text-champagne-ink' : 'text-text-primary')}>{value}</p>
    </div>
  );
}

export default function CompoundCalculatorPage() {
  const t = useT();
  const { locale } = useLocale();
  const faqItems = FAQ_KEYS.map((item) => ({ q: t(item.q), a: t(item.a) }));
  const chartBoxRef = useRef(null);
  const touchTip = useTouchTooltip(chartBoxRef);
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
    <div className="fe-data-page max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24">
      <div style={revealStyle(0)} className="fe-reveal mb-8">
        <Breadcrumbs items={toolTrail(t('calc.compound.title'), '/calculator/compound')} />
      </div>

      <header style={revealStyle(1)} className="fe-reveal mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-2xl bg-champagne/10 border border-champagne/20">
            <TrendingUp className="w-5 h-5 text-champagne" />
          </div>
          <span className="text-[11px] uppercase tracking-[0.3em] text-champagne-ink font-semibold">
            {t('calc.compound.eyebrow')}{keyRate != null && ` — ${t('calc.mortgage.keyRate', { rate: keyRate })}`}
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold tracking-tight text-text-primary leading-tight mb-3">
          {t('calc.compound.title')}
        </h1>
        <p className="text-base text-text-secondary leading-relaxed max-w-xl">
          {t('calc.compound.subtitle')}
        </p>
      </header>

      <section style={revealStyle(2)} className="fe-reveal fe-panel rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6 space-y-6">
        <div className="grid sm:grid-cols-2 gap-6">
          <CalcMoneyField
            label={t('calc.compound.initial')} unitName={t('calc.ui.unitRubles')}
            value={initial} onChange={setInitial} prefix="₽" placeholder="100 000" size="md" allowZero
          />
          <CalcMoneyField
            label={t('calc.compound.monthly')} unitName={t('calc.ui.unitRubles')}
            value={monthly} onChange={setMonthly} prefix="₽" placeholder="10 000" size="md" allowZero
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-5">
          <CalcSlider label={t('calc.compound.rate')} value={rate} onChange={setRate} min={0.1} max={30} step={0.1} suffix="%" />
          <CalcSlider label={t('calc.compound.term')} value={years} onChange={setYears} min={1} max={40} display={yearsLabel(years)} />
          <CalcSlider label={t('calc.compound.inflation')} value={inflation} onChange={setInflation} min={0} max={20} step={0.5} suffix="%" />
        </div>
      </section>

      {result && (
        <>
          <section style={revealStyle(3)} className="fe-reveal fe-panel rounded-[2rem] bg-surface border border-border-champagne p-6 md:p-8 mb-6 min-h-[17rem]" aria-live="polite">
            <p className="text-sm text-text-secondary mb-2">{t('calc.compound.growsIn', {
              years: yearsLabel(years),
            })}</p>
            <CalcAnimatedNumber
              value={Math.round(result.balance)}
              format={formatRubles}
              className="block min-h-[1.2em] font-display font-bold tracking-tight text-text-primary text-4xl md:text-5xl lg:text-6xl mb-6"
            />
            <div className="flex flex-wrap gap-3">
              <StatPill label={t('calc.compound.invested')} value={formatRubles(result.invested)} />
              <StatPill label={t('calc.compound.gain')} value={formatRubles(result.gain)} accent />
              <StatPill label={t('calc.compound.real')} value={formatRubles(result.real)} />
              {result.doubling && result.doubling < 100 && (
                <StatPill label={t('calc.compound.doubling')} value={`≈ ${result.doubling.toFixed(1).replace('.', ',')} ${t('calc.compound.yearsUnit')}`} />
              )}
            </div>
          </section>

          <section ref={setChartWidthNode} style={revealStyle(4)} className="fe-reveal fe-panel rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-5">
              {t('calc.compound.chartTitle')}
            </h3>
            <div ref={chartBoxRef} onPointerDownCapture={touchTip.onPointerDownCapture}>
              <ResponsiveContainer width="100%" height={chartWidth > 0 && chartWidth < 560 ? 260 : 300}>
                <AreaChart data={result.series} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
                  <defs>
                    <linearGradient id="cmpBal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_THEME.champagne} stopOpacity={0.2} />
                      <stop offset="100%" stopColor={CHART_THEME.champagne} stopOpacity={0.01} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis dataKey="year" stroke={CHART_THEME.axisLine} tick={axisTick()} tickLine={false} />
                  <YAxis stroke={CHART_THEME.axisLine} tick={axisTick()}
                    tickLine={false} axisLine={false} tickFormatter={formatCompactTick}
                    width={compactTickAxisWidth(result.series.map((p) => p.balance), { narrow: chartWidth > 0 && chartWidth < 420 })} />
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
                  <ReferenceLine y={result.invested} stroke={CHART_THEME.refLine} strokeDasharray="4 4" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-3 text-xs text-text-secondary">
              {t('calc.compound.chartHint', { rate: fmtPct(inflation) })}
            </p>
          </section>

          <section style={revealStyle(5)} className="fe-reveal grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-6">
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-obsidian-light/70 border border-border-subtle">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Flame className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                {t('calc.compound.insight.gain', {
                  pct: fmtPct(result.balance ? (result.gain / result.balance) * 100 : 0),
                  tail: result.gain > result.invested ? t('calc.compound.insight.gainMore') : t('calc.compound.insight.gainLess'),
                })}
              </p>
            </div>
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-obsidian-light/70 border border-border-subtle">
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

      <section style={revealStyle(6)} className="fe-reveal rounded-[2rem] bg-obsidian-light border border-border-subtle p-6 md:p-8 mb-8">
        <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-4">{t('calc.methodologyHeading')}</h3>
        <div className="space-y-3 text-sm text-text-secondary leading-relaxed">
          <p>
            {t('calc.compound.method.p1')}
          </p>
          <p className="font-mono text-xs text-text-secondary border-l-2 border-champagne/30 pl-4">
            {t('calc.compound.method.p2')}
          </p>
          <p>
            {t('calc.compound.method.refsBefore')}{' '}
            <Link to={russiaIndicatorPath('key-rate')} className="text-champagne hover:underline">{t('calc.compound.method.keyRate')}</Link>,{' '}
            <Link to={russiaIndicatorPath('ruonia')} className="text-champagne hover:underline">{t('calc.compound.method.ruonia')}</Link>
            ; {t('calc.compound.method.inflationBefore')}{' '}
            <Link to="/calculator" className="text-champagne hover:underline">{t('calc.compound.method.inflationLink')}</Link>.
          </p>
        </div>
      </section>

      <section style={revealStyle(7)} className="fe-reveal mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">{t('calc.faqHeading')}</h2>
        <FaqAccordion
          items={faqItems}
          onToggle={({ title, open }) => { if (open) track(events.FAQ_TOGGLE, { question: title }); }}
        />
      </section>

      <div style={revealStyle(8)} className="fe-reveal">
        <CalculatorSiblings current="compound" />
      </div>
    </div>
  );
}
