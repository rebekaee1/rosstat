import { useState, useEffect, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  Tooltip, CartesianGrid, PieChart, Pie, Cell,
} from 'recharts';
import { ArrowLeft, Home, Percent, Wallet, Clock, PieChart as PieIcon } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { cn } from '../lib/format';
import { formatCompactTick, compactTickAxisWidth } from '../lib/regionsApi';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { formatRubles, parseAmount, formatInput, fmtPct } from '../lib/calcFormat';
import { track, events } from '../lib/track';
import useScrollDepth from '../lib/useScrollDepth';
import FaqAccordion from '../components/FaqAccordion';
import CalcSlider from '../components/CalcSlider';
import {
  russiaIndicatorPath,
} from '../lib/sitePaths';

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

  const mortgageSeo = getPageSeo('calculator-mortgage');
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

  const yearCount = result?.yearly?.length || 1;
  const [selectedYear, setSelectedYear] = useState(1);
  // Клэмп инлайн, а не эффектом: срок могли сократить слайдером, старое
  // выбранное значение года может выйти за новый диапазон.
  const clampedYear = Math.min(Math.max(1, selectedYear), yearCount);
  const yearBreakdown = result?.yearly?.[clampedYear - 1] || null;

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
            Аннуитетный платёж{keyRate != null && ` — ключевая ставка ЦБ ${keyRate}%`}
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
        <div>
          <label htmlFor="mortgage-price" className="block text-[10px] uppercase tracking-[0.2em] font-medium text-text-tertiary mb-2">
            Стоимость недвижимости
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-xl text-text-tertiary font-display pointer-events-none" aria-hidden>₽</span>
            <input
              id="mortgage-price"
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
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-5">
          <CalcSlider
            label="Первый взнос"
            value={downPct} onChange={setDownPct} min={0} max={90}
            display={`${downPct}% — ${result ? formatCompactTick(result.down) : 0}\u00A0₽`}
          />
          <CalcSlider label="Ставка, % годовых" value={rate} onChange={setRate} min={0.1} max={30} step={0.1} suffix="%" />
          <CalcSlider label="Срок, лет" value={years} onChange={setYears} min={1} max={30} />
        </div>
      </section>

      {result && (
        <>
          <section data-animate className="rounded-[2rem] bg-surface border border-border-champagne p-6 md:p-8 mb-6" aria-live="polite">
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-6 items-center">
              <div>
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
              </div>

              <div className="flex flex-col items-center shrink-0 mx-auto lg:mx-0">
                <div className="relative w-[168px] h-[168px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={[
                          { name: 'Тело кредита', value: result.principal },
                          { name: 'Переплата', value: result.overpay },
                        ]}
                        dataKey="value" nameKey="name"
                        innerRadius={54} outerRadius={78}
                        paddingAngle={2} startAngle={90} endAngle={-270}
                        stroke="none" isAnimationActive={false}
                      >
                        <Cell fill="#B8942F" />
                        <Cell fill="#1A1A2E" fillOpacity={0.85} />
                      </Pie>
                      <Tooltip
                        formatter={(v, name) => [formatRubles(v), name]}
                        contentStyle={{ fontSize: 12 }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-[10px] uppercase tracking-wider text-text-tertiary">Переплата</span>
                    <span className="text-xl font-mono font-bold text-text-primary tabular-nums">
                      {fmtPct(result.principal ? (result.overpay / result.principal) * 100 : 0)}
                    </span>
                  </div>
                </div>
                <div className="flex gap-4 mt-3 text-[11px]">
                  <span className="flex items-center gap-1.5 text-text-secondary">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: '#B8942F' }} />Кредит
                  </span>
                  <span className="flex items-center gap-1.5 text-text-secondary">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: '#1A1A2E', opacity: 0.85 }} />Переплата
                  </span>
                </div>
              </div>
            </div>
          </section>

          <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
            <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-5">
              Остаток долга и накопленные проценты по годам
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={result.series} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
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
                <XAxis dataKey="year" stroke="rgba(0,0,0,0.1)"
                  tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }} tickLine={false} />
                <YAxis stroke="rgba(0,0,0,0.1)" tick={{ fill: 'rgba(0,0,0,0.4)', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                  tickLine={false} axisLine={false} tickFormatter={formatCompactTick}
                  width={compactTickAxisWidth(result.series.flatMap((p) => [p.balance, p.interest]))} />
                <Tooltip
                  formatter={(v, name) => [formatRubles(v), name === 'balance' ? 'Остаток долга' : 'Проценты накоплено']}
                  labelFormatter={(v) => `Год ${v}`}
                />
                <Area dataKey="balance" name="balance" stroke="#B8942F" strokeWidth={2} fill="url(#mortBal)" dot={false} isAnimationActive={false} />
                <Area dataKey="interest" name="interest" stroke="#1A1A2E" strokeWidth={1.4} fill="url(#mortInt)" dot={false} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
            <p className="mt-3 text-[12px] text-text-tertiary">
              По горизонтали — годы с начала кредита, по вертикали — рубли. Золотая линия — остаток долга, тёмная — накопленные проценты.
            </p>
          </section>

          {yearBreakdown && (
            <section data-animate className="rounded-[2rem] bg-surface border border-border-subtle shadow-sm shadow-black/[0.03] p-5 md:p-6 mb-6">
              <div className="flex items-center gap-2 mb-1">
                <PieIcon className="w-4 h-4 text-champagne" />
                <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
                  Из чего состоит платёж в конкретный год
                </h3>
              </div>
              <p className="text-[12px] text-text-tertiary mb-4">
                Сумма ежемесячного платежа не меняется, но со временем в ней падает доля процентов и растёт доля тела долга.
              </p>
              <CalcSlider
                label="Год кредита"
                value={clampedYear} onChange={setSelectedYear} min={1} max={yearCount}
                display={`${clampedYear}-й из ${yearCount}`}
              />
              <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <StatPill label="Проценты за год" value={formatRubles(yearBreakdown.interestPaid)} accent />
                <StatPill label="Тело долга за год" value={formatRubles(yearBreakdown.principalPaid)} />
                <StatPill label="Остаток долга на конец года" value={formatRubles(yearBreakdown.balance)} />
              </div>
              <div className="mt-4 h-3 rounded-full overflow-hidden bg-obsidian border border-border-subtle flex">
                <div
                  className="h-full transition-all duration-300"
                  style={{
                    width: `${(yearBreakdown.interestPaid / (yearBreakdown.interestPaid + yearBreakdown.principalPaid || 1)) * 100}%`,
                    backgroundColor: '#1A1A2E', opacity: 0.85,
                  }}
                  title="Проценты"
                />
                <div
                  className="h-full flex-1 transition-all duration-300"
                  style={{ backgroundColor: '#B8942F' }}
                  title="Тело долга"
                />
              </div>
              <div className="flex justify-between mt-1.5 text-[11px] text-text-tertiary">
                <span>Проценты — {fmtPct((yearBreakdown.interestPaid / (yearBreakdown.interestPaid + yearBreakdown.principalPaid || 1)) * 100)}</span>
                <span>Тело долга — {fmtPct((yearBreakdown.principalPaid / (yearBreakdown.interestPaid + yearBreakdown.principalPaid || 1)) * 100)}</span>
              </div>
            </section>
          )}

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
            <Link to={russiaIndicatorPath('key-rate')} className="text-champagne hover:underline">ключевой ставки Банка России</Link>.
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
