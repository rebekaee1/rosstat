import { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, ReferenceLine,
} from 'recharts';
import { ArrowLeft, TrendingUp, Flame, PiggyBank } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { cn } from '../lib/format';
import { formatCompactTick, compactTickAxisWidth } from '../lib/regionsApi';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { formatRubles, parseAmount, formatInput, fmtPct, years as yearsPhrase } from '../lib/calcFormat';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import FaqAccordion from '../components/FaqAccordion';
import CalcSlider from '../components/CalcSlider';
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
      <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">{label}</p>
      <p className={cn('text-base font-mono font-bold tabular-nums', accent ? 'text-champagne' : 'text-text-primary')}>{value}</p>
    </div>
  );
}

export default function CompoundCalculatorPage() {
  const t = useT();
  const { locale } = useLocale();
  const faqItems = FAQ_KEYS.map((item) => ({ q: t(item.q), a: t(item.a) }));
  const containerRef = useRef(null);
  const [initial, setInitial] = useState(100000);
  const [monthly, setMonthly] = useState(10000);
  const [rate, setRate] = useState(12);
  const [years, setYears] = useState(10);
  const [inflation, setInflation] = useState(6);

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
    if (!containerRef.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const els = containerRef.current.querySelectorAll('[data-animate]');
    if (!els.length) return;
    const tween = gsap.fromTo(els, { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.9, ease: 'power3.out', stagger: 0.08 });
    return () => tween.kill();
  }, []);

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
    <div ref={containerRef} className="max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24">
      <nav data-animate className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary mb-8">
        <Link to="/" className="hover:text-champagne transition-colors inline-flex items-center gap-1.5 group">
          <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
          {t('common.home')}
        </Link>
        <span className="text-text-tertiary/40">/</span>
        <Link to="/calculator" className="hover:text-champagne transition-colors">{t('calc.breadcrumb')}</Link>
        <span className="text-text-tertiary/40">/</span>
        <span className="text-text-secondary">{t('calc.compound.title')}</span>
      </nav>

      <header data-animate className="mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-2xl bg-champagne/10 border border-champagne/20">
            <TrendingUp className="w-5 h-5 text-champagne" />
          </div>
          <span className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold">
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

      <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6 space-y-6">
        <div className="grid sm:grid-cols-2 gap-6">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary mb-2">{t('calc.compound.initial')}</div>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-lg text-text-tertiary font-display pointer-events-none" aria-hidden>₽</span>
              <input
                type="text" inputMode="numeric" value={formatInput(initial)}
                onChange={(e) => setInitial(parseAmount(e.target.value))}
                placeholder="100 000"
                className={cn(
                  FOCUS_RING_SURFACE,
                  'w-full pl-9 pr-4 py-3 rounded-2xl bg-obsidian border border-border-subtle',
                  'text-xl font-display font-bold text-text-primary tabular-nums',
                  'placeholder:text-text-tertiary/40 placeholder:font-normal transition-colors hover:border-champagne/20',
                )}
              />
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary mb-2">{t('calc.compound.monthly')}</div>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-lg text-text-tertiary font-display pointer-events-none" aria-hidden>₽</span>
              <input
                type="text" inputMode="numeric" value={formatInput(monthly)}
                onChange={(e) => setMonthly(parseAmount(e.target.value))}
                placeholder="10 000"
                className={cn(
                  FOCUS_RING_SURFACE,
                  'w-full pl-9 pr-4 py-3 rounded-2xl bg-obsidian border border-border-subtle',
                  'text-xl font-display font-bold text-text-primary tabular-nums',
                  'placeholder:text-text-tertiary/40 placeholder:font-normal transition-colors hover:border-champagne/20',
                )}
              />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-5">
          <CalcSlider label={t('calc.compound.rate')} value={rate} onChange={setRate} min={0.1} max={30} step={0.1} suffix="%" />
          <CalcSlider label={t('calc.compound.term')} value={years} onChange={setYears} min={1} max={40} />
          <CalcSlider label={t('calc.compound.inflation')} value={inflation} onChange={setInflation} min={0} max={20} step={0.5} suffix="%" />
        </div>
      </section>

      {result && (
        <>
          <section data-animate className="rounded-[2rem] bg-surface border border-border-champagne p-6 md:p-8 mb-6" aria-live="polite">
            <p className="text-sm text-text-secondary mb-2">{t('calc.compound.growsIn', {
              years: locale === 'en' ? t('calc.years', { n: years }) : yearsPhrase(years),
            })}</p>
            <p className="font-display font-bold tracking-tight text-text-primary text-4xl md:text-5xl lg:text-6xl mb-6">
              {formatRubles(result.balance)}
            </p>
            <div className="flex flex-wrap gap-3">
              <StatPill label={t('calc.compound.invested')} value={formatRubles(result.invested)} />
              <StatPill label={t('calc.compound.gain')} value={formatRubles(result.gain)} accent />
              <StatPill label={t('calc.compound.real')} value={formatRubles(result.real)} />
              {result.doubling && result.doubling < 100 && (
                <StatPill label={t('calc.compound.doubling')} value={`≈ ${result.doubling.toFixed(1).replace('.', ',')} ${t('calc.compound.yearsUnit')}`} />
              )}
            </div>
          </section>

          <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-5">
              {t('calc.compound.chartTitle')}
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={result.series} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
                <defs>
                  <linearGradient id="cmpBal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#B8942F" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#B8942F" stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="year" stroke="rgba(0,0,0,0.1)"
                  tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }} tickLine={false} />
                <YAxis stroke="rgba(0,0,0,0.1)" tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                  tickLine={false} axisLine={false} tickFormatter={formatCompactTick}
                  width={compactTickAxisWidth(result.series.map((p) => p.balance))} />
                <Tooltip
                  formatter={(v, name) => [
                    formatRubles(v),
                    name === 'balance' ? t('calc.compound.capital') : name === 'invested' ? t('calc.compound.invested') : t('calc.compound.real'),
                  ]}
                  labelFormatter={(v) => t('calc.yearN', { n: v })}
                />
                <Area dataKey="balance" name="balance" stroke="#B8942F" strokeWidth={2} fill="url(#cmpBal)" dot={false} isAnimationActive={false} />
                <Area dataKey="invested" name="invested" stroke="#1A1A2E" strokeWidth={1.4} fill="none" strokeDasharray="6 4" dot={false} isAnimationActive={false} />
                <Area dataKey="real" name="real" stroke="#2563EB" strokeWidth={1.4} fill="none" dot={false} isAnimationActive={false} />
                <ReferenceLine y={result.invested} stroke="rgba(0,0,0,0.12)" strokeDasharray="4 4" />
              </AreaChart>
            </ResponsiveContainer>
            <p className="mt-3 text-[12px] text-text-tertiary">
              {t('calc.compound.chartHint', { rate: fmtPct(inflation) })}
            </p>
          </section>

          <section data-animate className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-6">
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

      <section data-animate className="rounded-[2rem] bg-obsidian-light border border-border-subtle p-6 md:p-8 mb-8">
        <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-4">{t('calc.methodologyHeading')}</h3>
        <div className="space-y-3 text-sm text-text-secondary leading-relaxed">
          <p>
            {t('calc.compound.method.p1')}
          </p>
          <p className="font-mono text-[11px] text-text-tertiary border-l-2 border-champagne/30 pl-4">
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

      <section data-animate className="mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">{t('calc.faqHeading')}</h2>
        <FaqAccordion
          items={faqItems}
          onToggle={({ title, open }) => { if (open) track(events.FAQ_TOGGLE, { question: title }); }}
        />
      </section>
    </div>
  );
}
