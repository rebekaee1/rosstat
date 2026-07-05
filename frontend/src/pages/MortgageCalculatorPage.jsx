import { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import { ArrowLeft, Home, Percent, Wallet, Clock } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import useDocumentMeta from '../lib/useMeta';
import { cn, formatAxisTick } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { formatRubles, parseAmount, formatInput, fmtPct } from '../lib/calcFormat';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import FaqAccordion from '../components/FaqAccordion';

const FAQ_ITEMS = [
  {
    q: 'Как рассчитывается ежемесячный платёж?',
    a: 'Используется аннуитетная формула — самый распространённый тип платежа в российских банках: одинаковая сумма каждый месяц, внутри которой доля процентов постепенно уменьшается, а доля основного долга растёт.',
  },
  {
    q: 'Что такое переплата по ипотеке?',
    a: 'Переплата — это сумма всех процентов за весь срок кредита. При ставке 18% и сроке 30 лет переплата может превышать стоимость самой квартиры в два-три раза. Сократить её можно бóльшим первоначальным взносом, меньшим сроком или досрочными погашениями.',
  },
  {
    q: 'Какая сейчас ставка по ипотеке?',
    a: 'Рыночная ставка следует за ключевой ставкой Банка России: обычно она на 2–5 процентных пунктов выше. Льготные программы (семейная, IT-ипотека) фиксируют ставку ниже рыночной. Актуальная ключевая ставка отображается над полем ставки.',
  },
  {
    q: 'Аннуитетный или дифференцированный платёж — что выгоднее?',
    a: 'Дифференцированный платёж даёт меньшую переплату, но первые платежи заметно больше. Аннуитет удобнее для планирования бюджета и чаще одобряется банками. Этот калькулятор считает аннуитет.',
  },
  {
    q: 'Как повлияет досрочное погашение?',
    a: 'Досрочные платежи в первые годы дают максимальный эффект: они уменьшают тело долга, на которое начисляются проценты. Сокращение срока обычно выгоднее уменьшения платежа.',
  },
];

function InputCard({ label, children }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary mb-2">{label}</div>
      {children}
    </div>
  );
}

function Slider({ value, onChange, min, max, step = 1, suffix = '' }) {
  return (
    <div className="flex items-center gap-3">
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="calc-slider flex-1"
      />
      <span className="w-20 text-right text-sm font-mono font-bold text-text-primary tabular-nums shrink-0">
        {value}{suffix}
      </span>
    </div>
  );
}

function StatPill({ label, value, accent }) {
  return (
    <div className="px-4 py-2.5 rounded-xl bg-obsidian border border-border-subtle">
      <p className="text-[10px] uppercase tracking-[0.15em] text-text-tertiary font-medium mb-0.5">{label}</p>
      <p className={cn('text-base font-mono font-bold tabular-nums', accent ? 'text-champagne' : 'text-text-primary')}>{value}</p>
    </div>
  );
}

export default function MortgageCalculatorPage() {
  const containerRef = useRef(null);
  const [price, setPrice] = useState(8000000);
  const [downPct, setDownPct] = useState(20);
  const [rate, setRate] = useState(18);
  const [years, setYears] = useState(20);

  useDocumentMeta({
    title: 'Ипотечный калькулятор — рассчитать платёж по ипотеке',
    description: 'Рассчитайте ежемесячный платёж, переплату и график погашения ипотеки. Аннуитетная формула, актуальная ключевая ставка Банка России.',
    path: '/calculator/mortgage',
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

  useEffect(() => {
    if (!containerRef.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const els = containerRef.current.querySelectorAll('[data-animate]');
    if (!els.length) return;
    const tween = gsap.fromTo(els, { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.9, ease: 'power3.out', stagger: 0.08 });
    return () => tween.kill();
  }, []);

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
    const payment = r > 0 ? principal * r / (1 - Math.pow(1 + r, -n)) : principal / n;
    const total = payment * n;
    const overpay = total - principal;

    // Годовой график остатка долга и накопленных процентов.
    let balance = principal;
    let interestPaid = 0;
    const series = [{ year: 0, balance: Math.round(balance), interest: 0 }];
    for (let m = 1; m <= n; m += 1) {
      const int = balance * r;
      interestPaid += int;
      balance = Math.max(0, balance - (payment - int));
      if (m % 12 === 0 || m === n) {
        series.push({ year: Math.ceil(m / 12), balance: Math.round(balance), interest: Math.round(interestPaid) });
      }
    }
    return { principal, payment, total, overpay, series, down: price - principal };
  }, [price, downPct, rate, years]);

  return (
    <div ref={containerRef} className="max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24">
      <nav data-animate className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary mb-8">
        <Link to="/" className="hover:text-champagne transition-colors inline-flex items-center gap-1.5 group">
          <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
          Главная
        </Link>
        <span className="text-text-tertiary/40">/</span>
        <Link to="/calculator" className="hover:text-champagne transition-colors">Калькуляторы</Link>
        <span className="text-text-tertiary/40">/</span>
        <span className="text-text-secondary">Ипотека</span>
      </nav>

      <header data-animate className="mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-2xl bg-champagne/10 border border-champagne/20">
            <Home className="w-5 h-5 text-champagne" />
          </div>
          <span className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold">
            Аннуитетный платёж{keyRate != null && ` · ключевая ставка ЦБ ${keyRate}%`}
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold tracking-tight text-text-primary leading-tight mb-3">
          Ипотечный калькулятор
        </h1>
        <p className="text-base text-text-secondary leading-relaxed max-w-xl">
          Рассчитайте ежемесячный платёж, полную стоимость кредита и переплату.
          График показывает, как гасится долг и сколько процентов накапливается за срок.
        </p>
      </header>

      <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-6 md:p-8 mb-6 space-y-6">
        <InputCard label="Стоимость недвижимости">
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-xl text-text-tertiary font-display pointer-events-none" aria-hidden>₽</span>
            <input
              type="text" inputMode="numeric" value={formatInput(price)}
              onChange={(e) => setPrice(parseAmount(e.target.value))}
              placeholder="8 000 000"
              className={cn(
                FOCUS_RING_SURFACE,
                'w-full pl-10 pr-4 py-4 rounded-2xl bg-obsidian border border-border-subtle',
                'text-2xl md:text-3xl font-display font-bold text-text-primary tabular-nums',
                'placeholder:text-text-tertiary/40 placeholder:font-normal transition-colors hover:border-champagne/20',
              )}
            />
          </div>
        </InputCard>

        <div className="grid sm:grid-cols-3 gap-6">
          <InputCard label={`Первоначальный взнос — ${result ? formatRubles(result.down) : '—'}`}>
            <Slider value={downPct} onChange={setDownPct} min={0} max={90} suffix="%" />
          </InputCard>
          <InputCard label="Ставка, % годовых">
            <Slider value={rate} onChange={setRate} min={0.1} max={30} step={0.1} suffix="%" />
          </InputCard>
          <InputCard label="Срок, лет">
            <Slider value={years} onChange={setYears} min={1} max={30} />
          </InputCard>
        </div>
      </section>

      {result && (
        <>
          <section data-animate className="rounded-[2rem] bg-surface border border-border-champagne p-6 md:p-8 mb-6" aria-live="polite">
            <p className="text-sm text-text-secondary mb-2">Ежемесячный платёж</p>
            <p className="font-display font-bold tracking-tight text-text-primary text-4xl md:text-5xl lg:text-6xl mb-6">
              {formatRubles(result.payment)}
            </p>
            <div className="flex flex-wrap gap-3">
              <StatPill label="Сумма кредита" value={formatRubles(result.principal)} />
              <StatPill label="Переплата" value={formatRubles(result.overpay)} accent />
              <StatPill label="Всего выплат" value={formatRubles(result.total)} />
              <StatPill label="Переплата к кредиту" value={fmtPct(result.principal ? (result.overpay / result.principal) * 100 : 0)} />
            </div>
          </section>

          <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-5">
              Остаток долга и накопленные проценты по годам
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={result.series} margin={{ top: 5, right: 10, bottom: 5, left: -5 }}>
                <defs>
                  <linearGradient id="mortBal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#B8942F" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#B8942F" stopOpacity={0.01} />
                  </linearGradient>
                  <linearGradient id="mortInt" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#1A1A2E" stopOpacity={0.12} />
                    <stop offset="100%" stopColor="#1A1A2E" stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="year" tickFormatter={(v) => `${v} г.`} stroke="rgba(0,0,0,0.1)"
                  tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }} tickLine={false} />
                <YAxis stroke="rgba(0,0,0,0.1)" tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                  tickLine={false} axisLine={false} tickFormatter={(v) => formatAxisTick(v, 0)} width={62} />
                <Tooltip
                  formatter={(v, name) => [formatRubles(v), name === 'balance' ? 'Остаток долга' : 'Проценты накоплено']}
                  labelFormatter={(v) => `Год ${v}`}
                />
                <Area dataKey="balance" name="balance" stroke="#B8942F" strokeWidth={2} fill="url(#mortBal)" dot={false} isAnimationActive={false} />
                <Area dataKey="interest" name="interest" stroke="#1A1A2E" strokeWidth={1.4} fill="url(#mortInt)" dot={false} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </section>

          <section data-animate className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mb-6">
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-obsidian-light/70 border border-border-subtle">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Percent className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                Каждый процентный пункт ставки на этом сроке меняет переплату примерно на {formatRubles(result.principal * years / 100 * 0.55)}
              </p>
            </div>
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-obsidian-light/70 border border-border-subtle">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Clock className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                За первый год в счёт долга уйдёт лишь {formatRubles(Math.max(0, result.series[0].balance - (result.series[1]?.balance ?? 0)))} из {formatRubles(result.payment * 12)} платежей
              </p>
            </div>
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-obsidian-light/70 border border-border-subtle sm:col-span-2">
              <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-champagne/8 shrink-0 mt-0.5"><Wallet className="w-3.5 h-3.5 text-champagne" /></div>
              <p className="text-[13px] leading-relaxed text-text-secondary">
                Банки обычно требуют, чтобы платёж не превышал 40–50% дохода: для этого кредита комфортный доход — от {formatRubles(result.payment / 0.45)} в месяц
              </p>
            </div>
          </section>
        </>
      )}

      <section data-animate className="rounded-[2rem] bg-obsidian-light border border-border-subtle p-6 md:p-8 mb-8">
        <h3 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-4">Методология расчёта</h3>
        <div className="space-y-3 text-sm text-text-secondary leading-relaxed">
          <p>
            Калькулятор использует аннуитетную схему: одинаковый ежемесячный платёж на весь срок.
            Проценты начисляются на остаток долга, поэтому в начале срока их доля в платеже максимальна.
          </p>
          <p className="font-mono text-[11px] text-text-tertiary border-l-2 border-champagne/30 pl-4">
            Платёж = Кредит × r / (1 − (1 + r)⁻ⁿ), где r — месячная ставка (годовая / 12 / 100), n — число месяцев.
          </p>
          <p>
            Расчёт справочный: банк дополнительно учитывает страховку, комиссии и индивидуальные условия.
            Динамика ключевой ставки, от которой зависят ипотечные ставки, — на странице{' '}
            <Link to="/indicator/key-rate" className="text-champagne hover:underline">ключевой ставки Банка России</Link>.
          </p>
        </div>
      </section>

      <section data-animate className="mb-8">
        <h2 className="text-xs uppercase tracking-[0.2em] text-text-secondary font-semibold mb-6">Частые вопросы</h2>
        <FaqAccordion
          items={FAQ_ITEMS}
          onToggle={({ title, open }) => { if (open) track(events.FAQ_TOGGLE, { question: title }); }}
        />
      </section>
    </div>
  );
}
