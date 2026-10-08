// «Попробуйте сами»: три живых мини-инструмента прямо на главной. Человек получает ответ, не уходя со страницы,
// а «Открыть полностью» ведёт в большой калькулятор, к курсам валют и на страницу сравнения.
// Все числа берутся из ответов, которые главная и так уже загрузила (список показателей и срезы по странам):
// новых запросов нет. Это иллюстрации «на пальцах»: точные расчёты и история остаются на своих страницах.
import { useId, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeftRight, ArrowRight, Coins, GitCompare, Percent } from 'lucide-react';
import { useIndicators } from '../../lib/hooks';
import { UNITS, buildEdges, convert, convertibleUnits, formatConverted } from '../../lib/currencyRates';
import { useWorldCompareSnapshot, useWorldCountries } from '../../lib/worldApi';
import { countryPublicName } from '../../lib/homeWorkbench';
import { comparePath } from '../../lib/sitePaths';
import { formatValue } from '../../lib/format';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import '../../styles/w6-g.css';
import '../../styles/z3-home.css';

const FIAT = ['RUB', 'USD', 'EUR', 'CNY', 'GBP'];
const MAX_AMOUNT = 1_000_000_000_000;

function parseAmount(text) {
  const clean = String(text || '').replace(/\s/g, '').replace(',', '.');
  if (!/^\d*\.?\d*$/.test(clean) || clean === '' || clean === '.') return null;
  const value = Number(clean);
  return Number.isFinite(value) && value <= MAX_AMOUNT ? value : null;
}

function ToolShell({ icon: Icon, title, lead, footerTo, footerLabel, track: trackId, children }) {
  return (
    <article className="fe-tool fe-reveal">
      <header className="fe-tool__head">
        <span className="fe-tool__icon" aria-hidden="true"><Icon size={18} /></span>
        <div className="min-w-0">
          <h3 className="fe-tool__title">{title}</h3>
          <p className="fe-tool__lead">{lead}</p>
        </div>
      </header>
      <div className="fe-tool__body">{children}</div>
      <Link
        to={footerTo}
        onClick={() => track(events.HOME_CATEGORY_CLICK, { category: trackId, surface: 'home-tools' })}
        className="fe-tool__more fe-press"
      >
        {footerLabel}
        <ArrowRight size={14} aria-hidden="true" />
      </Link>
    </article>
  );
}

/** Конвертер: сумма и две валюты, ответ сразу. Курсы те же, что в разделе «Курсы валют». */
function ConverterTool() {
  const t = useT();
  const { locale } = useLocale();
  const id = useId();
  const indicators = useIndicators();
  const edges = useMemo(() => buildEdges(indicators.data || []), [indicators.data]);
  const units = useMemo(() => {
    const known = convertibleUnits(edges).filter((unit) => FIAT.includes(unit));
    return known.length >= 2 ? known : FIAT;
  }, [edges]);
  const [amountText, setAmountText] = useState('100');
  const [from, setFrom] = useState('USD');
  const [to, setTo] = useState(locale === 'en' ? 'EUR' : 'RUB');
  const amount = parseAmount(amountText);
  const result = amount != null && edges.length ? convert(amount, from, to, edges) : null;
  const asOf = result?.date
    ? new Date(`${String(result.date).slice(0, 10)}T12:00:00`).toLocaleDateString(locale === 'en' ? 'en-US' : 'ru-RU', { day: 'numeric', month: 'long' })
    : '';
  return (
    <ToolShell
      icon={Coins}
      title={t('z3.tools.cur.title')}
      lead={t('z3.tools.cur.lead')}
      footerTo="/currencies"
      footerLabel={t('z3.tools.cur.more')}
      track="currencies"
    >
      <div className="fe-tool__row">
        <label className="fe-tool__field" htmlFor={`${id}-amount`}>
          <span className="fe-tool__label">{t('z3.tools.cur.amount')}</span>
          <input
            id={`${id}-amount`}
            className="fe-tool__input"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
            aria-invalid={amount == null || undefined}
          />
        </label>
        <label className="fe-tool__field" htmlFor={`${id}-from`}>
          <span className="fe-tool__label">{t('z3.tools.cur.from')}</span>
          <select id={`${id}-from`} className="fe-tool__input" value={from} onChange={(event) => setFrom(event.target.value)}>
            {units.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
          </select>
        </label>
        <button
          type="button"
          className="fe-tool__swap fe-press"
          aria-label={t('z3.tools.cur.swap')}
          title={t('z3.tools.cur.swap')}
          onClick={() => { setFrom(to); setTo(from); }}
        >
          <ArrowLeftRight size={16} aria-hidden="true" />
        </button>
        <label className="fe-tool__field" htmlFor={`${id}-to`}>
          <span className="fe-tool__label">{t('z3.tools.cur.to')}</span>
          <select id={`${id}-to`} className="fe-tool__input" value={to} onChange={(event) => setTo(event.target.value)}>
            {units.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
          </select>
        </label>
      </div>
      <div className="fe-tool__result" role="status" aria-live="polite">
        {result ? (
          <>
            <i key={`${formatConverted(result.value, locale)}${to}`} className="fe-tool__sheen" aria-hidden="true" />
            <span className="fe-tool__big">
              <span className="fe-tool__num">{formatConverted(result.value, locale)}</span>
              <span className="fe-tool__unit">{UNITS[to].symbol}</span>
            </span>
            <span className="fe-tool__note">
              {asOf ? t('z3.tools.cur.noteDate', { date: asOf }) : t('z3.tools.cur.note')}
            </span>
          </>
        ) : (
          <span className="fe-tool__note">{amount == null ? t('z3.tools.cur.bad') : t('z3.tools.cur.wait')}</span>
        )}
      </div>
    </ToolShell>
  );
}

/** Инфляция «на пальцах»: если цены продолжат расти как сейчас, сколько сегодняшних денег останется через N лет. */
function InflationTool() {
  const t = useT();
  const { locale } = useLocale();
  const id = useId();
  const [years, setYears] = useState(10);
  const snapshot = useWorldCompareSnapshot('hicp-index');
  const homeCode = locale === 'en' ? 'US' : 'RU';
  const rate = useMemo(() => {
    const item = (snapshot.data?.items || []).find((entry) => entry?.country_code === homeCode);
    const value = Number(item?.value);
    return Number.isFinite(value) ? value : null;
  }, [snapshot.data, homeCode]);
  const amount = locale === 'en' ? 1000 : 100000;
  const symbol = locale === 'en' ? '$' : '\u20bd';
  const left = rate != null && rate > -50 ? amount / ((1 + rate / 100) ** years) : null;
  const money = (value) => (locale === 'en'
    ? `${symbol}${formatConverted(value, 'en')}`
    : `${formatConverted(value, 'ru')}\u00a0${symbol}`);
  const yearsWord = locale === 'en'
    ? t('z3.tools.inf.years_many')
    : t(years % 10 === 1 && years % 100 !== 11 ? 'z3.tools.inf.years_one'
      : (years % 10 >= 2 && years % 10 <= 4 && (years % 100 < 12 || years % 100 > 14)) ? 'z3.tools.inf.years_few' : 'z3.tools.inf.years_many');
  return (
    <ToolShell
      icon={Percent}
      title={t('z3.tools.inf.title')}
      lead={t('z3.tools.inf.lead', { amount: money(amount) })}
      footerTo="/calculator"
      footerLabel={t('z3.tools.inf.more')}
      track="calculator"
    >
      <label className="fe-tool__field fe-tool__field--wide" htmlFor={`${id}-years`}>
        <span className="fe-tool__label">
          {t('z3.tools.inf.horizon')}
          <strong className="fe-tool__label-value">{years} {yearsWord}</strong>
        </span>
        <input
          id={`${id}-years`}
          className="fe-tool__range"
          type="range"
          min="1"
          max="30"
          step="1"
          value={years}
          style={{ '--fe-range-p': `${((years - 1) / 29) * 100}%` }}
          onChange={(event) => setYears(Number(event.target.value))}
        />
      </label>
      <div className="fe-tool__result" role="status" aria-live="polite">
        {left != null ? (
          <>
            <i key={money(left)} className="fe-tool__sheen" aria-hidden="true" />
            <span className="fe-tool__big">
              <span className="fe-tool__num">{money(left)}</span>
            </span>
            <span className="fe-tool__note">
              {t('z3.tools.inf.note', { years: `${years} ${yearsWord}`, rate: formatValue(rate, 1, locale), amount: money(amount) })}
            </span>
          </>
        ) : (
          <span className="fe-tool__note">{t('z3.tools.inf.wait')}</span>
        )}
      </div>
    </ToolShell>
  );
}

const COMPARE_CONCEPTS = [
  { slug: 'gdp-usd', labelKey: 'z3.tools.cmp.gdp' },
  { slug: 'hicp-index', labelKey: 'z3.tools.cmp.inflation', rep: 'yoy' },
  { slug: 'unemployment-rate', labelKey: 'z3.tools.cmp.unemployment' },
];

/** «Сравни две страны»: два списка и показатель, кнопка ведёт на готовый график сравнения. */
function CompareTool() {
  const t = useT();
  const { locale } = useLocale();
  const id = useId();
  const countriesQ = useWorldCountries();
  const countries = useMemo(() => {
    const collator = new Intl.Collator(locale === 'en' ? 'en' : 'ru');
    return (countriesQ.data?.countries || [])
      .filter((country) => country?.slug)
      .map((country) => ({ slug: country.slug, name: countryPublicName(country, locale) }))
      .sort((a, b) => collator.compare(a.name, b.name));
  }, [countriesQ.data, locale]);
  // Круг 9 (H8): на русском сайте первой стоит Россия (ряд Росстата в мировом сравнении есть); на английском остаётся пара США и Китай.
  const [first, setFirst] = useState(locale === 'en' ? 'united-states' : 'russia');
  const [second, setSecond] = useState('china');
  const [concept, setConcept] = useState('gdp-usd');
  const has = (slug) => countries.some((country) => country.slug === slug);
  // Пока каталог не пришёл, держим стартовую пару; если пары в каталоге нет, берём первые две страны.
  const firstValue = has(first) ? first : has('united-states') ? 'united-states' : countries[0]?.slug || first;
  const secondValue = has(second) ? second : countries.find((country) => country.slug !== firstValue)?.slug || second;
  const picked = COMPARE_CONCEPTS.find((item) => item.slug === concept) || COMPARE_CONCEPTS[0];
  const codes = [firstValue, secondValue].map((slug) => `w:${slug}:${picked.slug}`);
  const params = new URLSearchParams({ codes: codes.join(',') });
  if (picked.rep) params.set('rep', codes.map((code) => `${code}:${picked.rep}`).join(','));
  const ready = countries.length > 1 && firstValue !== secondValue;
  return (
    <ToolShell
      icon={GitCompare}
      title={t('z3.tools.cmp.title')}
      lead={t('z3.tools.cmp.lead')}
      footerTo={comparePath()}
      footerLabel={t('z3.tools.cmp.more')}
      track="compare"
    >
      <div className="fe-tool__row fe-tool__row--pair">
        <label className="fe-tool__field" htmlFor={`${id}-a`}>
          <span className="fe-tool__label">{t('z3.tools.cmp.first')}</span>
          <select id={`${id}-a`} className="fe-tool__input" value={firstValue} onChange={(event) => setFirst(event.target.value)} disabled={countries.length < 2}>
            {countries.length ? countries.map((country) => <option key={country.slug} value={country.slug}>{country.name}</option>) : <option value={firstValue}>…</option>}
          </select>
        </label>
        <label className="fe-tool__field" htmlFor={`${id}-b`}>
          <span className="fe-tool__label">{t('z3.tools.cmp.second')}</span>
          <select id={`${id}-b`} className="fe-tool__input" value={secondValue} onChange={(event) => setSecond(event.target.value)} disabled={countries.length < 2}>
            {countries.length ? countries.map((country) => <option key={country.slug} value={country.slug}>{country.name}</option>) : <option value={secondValue}>…</option>}
          </select>
        </label>
      </div>
      <div className="fe-tool__seg" role="group" aria-label={t('z3.tools.cmp.what')}>
        {COMPARE_CONCEPTS.map((item) => (
          <button
            key={item.slug}
            type="button"
            className={'fe-tool__seg-btn fe-press' + (item.slug === picked.slug ? ' is-active' : '')}
            aria-pressed={item.slug === picked.slug}
            onClick={() => setConcept(item.slug)}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>
      <div className="fe-tool__result fe-tool__result--cta">
        {ready ? (
          <Link
            to={`${comparePath()}?${params.toString()}`}
            onClick={() => track(events.HOME_CATEGORY_CLICK, { category: 'compare', surface: 'home-tools-run' })}
            className="fe-tool__cta fe-press"
          >
            {t('z3.tools.cmp.go')}
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        ) : (
          <span className="fe-tool__note">{t('z3.tools.cmp.wait')}</span>
        )}
      </div>
    </ToolShell>
  );
}

export default function HomeTools() {
  const t = useT();
  return (
    <section data-block="home-tools" className="fe-w6g-home-tools fe-tools" aria-labelledby="home-tools-title">
      <div className="fe-tools__head">
        <h2 id="home-tools-title" className="fe-tools__title">{t('z3.tools.title')}</h2>
        <p className="fe-tools__sub">{t('z3.tools.sub')}</p>
      </div>
      <div className="fe-tools__grid">
        <ConverterTool />
        <InflationTool />
        <CompareTool />
      </div>
    </section>
  );
}
