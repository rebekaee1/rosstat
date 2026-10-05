// Раздел «Курсы валют и криптовалют»: сверху конвертер («100 долларов в рубли»), под ним вкладки
// «Валюты / Крипто / Мир», поле «Найти валюту» и строки по популярности: значок, мини-график, курс и изменение.
import { useId, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRightLeft, ChevronDown, Search, X } from 'lucide-react';
import Chip from './Chip';
import Button from './Button';
import DeltaBadge from './DeltaBadge';
import Sparkline from './Sparkline';
import { useIndicatorData } from '../lib/hooks';
import { formatDate, formatValue } from '../lib/format';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { russiaIndicatorPath } from '../lib/sitePaths';
import {
  CURRENCY_TABS, UNITS, buildEdges, convert, convertibleUnits, formatConverted,
  pairTab, pairTitle, parseAmountInput, parsePair, rateBasis, sortByPopularity,
} from '../lib/currencyRates';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import '../styles/y2-indicator.css';
import '../styles/w6-g.css';

function unitName(unit, locale) {
  const meta = UNITS[unit];
  if (!meta) return unit;
  return locale === 'en' ? meta.en : meta.ru;
}

/** Мини-график последних значений: у всех строк, не только у «ежедневных». */
function RowSpark({ code, index }) {
  const { data } = useIndicatorData(code, { limit: 40 });
  const values = (data?.data || []).map((row) => Number(row.value)).filter(Number.isFinite);
  if (values.length < 2) return null;
  const delta = values[values.length - 1] - values[values.length - 2];
  const trend = Math.abs(delta) < 1e-12 ? 'flat' : delta > 0 ? 'up' : 'down';
  return (
    <div className="fe-tile__spark" aria-hidden="true">
      <Sparkline points={values} trend={trend} sentiment="neutral" height={30} staggerMs={Math.min(index, 5) * 80} />
    </div>
  );
}

function Converter({ edges }) {
  const t = useT();
  const { locale } = useLocale();
  const id = useId();
  const units = useMemo(() => convertibleUnits(edges), [edges]);
  const [amountText, setAmountText] = useState('100');
  const [from, setFrom] = useState('USD');
  const [to, setTo] = useState('RUB');
  if (units.length < 2) return null;

  const safeFrom = units.includes(from) ? from : units[0];
  const safeTo = units.includes(to) && to !== safeFrom ? to : units.find((u) => u !== safeFrom);
  const amount = parseAmountInput(amountText);
  const result = amount != null ? convert(amount, safeFrom, safeTo, edges) : null;

  const bases = result ? new Set(result.path.map((code) => rateBasis(code)).filter(Boolean)) : new Set();
  const basisKey = bases.size === 1 ? `w6g.cur.basis.${[...bases][0]}` : 'w6g.cur.basis.mix';
  const swap = () => {
    setFrom(safeTo);
    setTo(safeFrom);
    track(events.COMPARE_CHANGE, { converter: 'swap' });
  };

  const selectClass = 'fe-w6g-select';
  return (
    <section className="fe-panel fe-w6g-converter" data-block="currency-converter" aria-label={t('w6g.cur.converterTitle')}>
      <h2 className="fe-w6g-converter__title">{t('w6g.cur.converterTitle')}</h2>
      <div className="fe-w6g-converter__row">
        <label className="fe-w6g-field" htmlFor={`${id}-amount`}>
          <span>{t('w6g.cur.amount')}</span>
          <input
            id={`${id}-amount`}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
            aria-invalid={amount == null ? 'true' : undefined}
            className="fe-w6g-input"
          />
        </label>
        <label className="fe-w6g-field" htmlFor={`${id}-from`}>
          <span>{t('w6g.cur.from')}</span>
          <select id={`${id}-from`} className={selectClass} value={safeFrom} onChange={(event) => setFrom(event.target.value)}>
            {units.map((unit) => (
              <option key={unit} value={unit}>{unitName(unit, locale)}</option>
            ))}
          </select>
        </label>
        <button type="button" className="fe-w6g-swap fe-press" onClick={swap} aria-label={t('w6g.cur.swap')} title={t('w6g.cur.swap')}>
          <ArrowRightLeft size={18} aria-hidden="true" />
        </button>
        <label className="fe-w6g-field" htmlFor={`${id}-to`}>
          <span>{t('w6g.cur.to')}</span>
          <select id={`${id}-to`} className={selectClass} value={safeTo} onChange={(event) => setTo(event.target.value)}>
            {units.filter((unit) => unit !== safeFrom).map((unit) => (
              <option key={unit} value={unit}>{unitName(unit, locale)}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="fe-w6g-converter__out" aria-live="polite" data-testid="converter-result">
        {result ? (
          <>
            <p className="fe-w6g-converter__sum">
              <span className="fe-w6g-converter__num">{formatConverted(result.value, locale)}</span>
              <span className="fe-w6g-converter__unit">{unitName(safeTo, locale)}</span>
            </p>
            {result.date && (
              <p className="fe-w6g-converter__note">
                {t(basisKey, { date: formatDate(result.date, 'day', locale) })}
              </p>
            )}
          </>
        ) : (
          <p className="fe-w6g-converter__note">{t('w6g.cur.badAmount')}</p>
        )}
      </div>
    </section>
  );
}

function CurrencyRow({ ind, index }) {
  const t = useT();
  const { locale } = useLocale();
  const pair = parsePair(ind.code);
  const base = pair ? UNITS[pair.base] : null;
  const quote = pair ? UNITS[pair.quote] : null;
  const title = pairTitle(ind.code, locale, locale === 'en' && ind.name_en ? ind.name_en : ind.name);
  const basis = rateBasis(ind.code);
  const value = Number(ind.current_value);
  const change = Number(ind.change);
  const prev = value - change;
  const pct = Number.isFinite(change) && Number.isFinite(prev) && prev !== 0 ? (change / prev) * 100 : null;
  const delta = pct != null ? formatDeltaWithUnit(pct, '%', { pct: true, locale }) : null;
  const dateText = ind.current_date
    ? new Date(`${String(ind.current_date).slice(0, 10)}T12:00:00Z`).toLocaleDateString(
      locale === 'en' ? 'en-US' : 'ru-RU',
      { day: 'numeric', month: 'short', timeZone: 'UTC' },
    )
    : '';
  const digits = Math.abs(value) >= 1000 ? 0 : 2;
  return (
    <Link
      to={russiaIndicatorPath(ind.code)}
      className="fe-trow fe-press fe-w6g-currency-row"
      onClick={() => track(events.CATEGORY_TILE_CLICK, { indicator: ind.code, surface: 'currencies' })}
    >
      <span className="fe-w6g-coin" aria-hidden="true">{base?.flag || base?.symbol || ''}</span>
      <span className="fe-trow__main">
        <h3 className="fe-trow__title">{title}</h3>
        <span className="fe-trow__meta">
          {delta && !delta.flat && (
            <DeltaBadge delta={pct}>{delta.text}</DeltaBadge>
          )}
          {basis && (
            <span className="fe-trow__date">{t(`w6g.cur.basisShort.${basis}`, { date: dateText })}</span>
          )}
        </span>
      </span>
      <span className="fe-trow__spark" aria-hidden="true">
        <RowSpark code={ind.code} index={index} />
      </span>
      <span className="fe-trow__val">
        <span className="fe-trow__num">{formatValue(value, digits, locale)}</span>
        {quote?.symbol && <span className="fe-trow__unit">{quote.symbol}</span>}
      </span>
    </Link>
  );
}

function matchesQuery(ind, needle) {
  const pair = parsePair(ind.code);
  const parts = [ind.code, ind.name, ind.name_en, pairTitle(ind.code, 'ru'), pairTitle(ind.code, 'en')];
  if (pair) {
    [pair.base, pair.quote].forEach((unit) => {
      const meta = UNITS[unit];
      parts.push(unit, meta.ru, meta.en, meta.symbol);
    });
  }
  const text = parts.filter(Boolean).join(' ').toLowerCase();
  return needle.split(/\s+/).filter(Boolean).every((word) => text.includes(word));
}

export default function CurrencyDesk({ indicators }) {
  const t = useT();
  const [tab, setTab] = useState('rub');
  const [query, setQuery] = useState('');
  const needle = query.trim().toLowerCase();

  const sorted = useMemo(() => sortByPopularity(indicators || []), [indicators]);
  const edges = useMemo(() => buildEdges(sorted), [sorted]);
  const counts = useMemo(() => {
    const map = { rub: 0, crypto: 0, world: 0 };
    sorted.forEach((ind) => { map[pairTab(ind.code)] += 1; });
    return map;
  }, [sorted]);
  const tabs = CURRENCY_TABS.filter((id) => counts[id] > 0);
  const activeTab = tabs.includes(tab) ? tab : tabs[0];

  const rows = needle
    ? sorted.filter((ind) => matchesQuery(ind, needle))
    : sorted.filter((ind) => pairTab(ind.code) === activeTab);

  return (
    <div className="fe-w6g-desk">
      <Converter edges={edges} />

      <section data-block="currency-list" aria-label={t('w6g.cur.listTitle')}>
        <div className="fe-w6g-toolbar">
          <div className="fe-scroll-row" role="group" aria-label={t('w6g.cur.tabsAria')}>
            {tabs.map((id) => (
              <Chip
                key={id}
                active={!needle && activeTab === id}
                onClick={() => { setTab(id); setQuery(''); }}
              >
                {t(`w6g.cur.tab.${id}`)}
              </Chip>
            ))}
          </div>
          <label className="fe-w6g-search">
            <Search size={16} aria-hidden="true" />
            <span className="sr-only">{t('w6g.cur.search')}</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('w6g.cur.search')}
              autoComplete="off"
              className="fe-w6g-search__input"
            />
            {query && (
              <button type="button" className="fe-w6g-search__clear" aria-label={t('common.clear')} onClick={() => setQuery('')}>
                <X size={16} aria-hidden="true" />
              </button>
            )}
          </label>
        </div>

        <details className="fe-w6g-why">
          <summary>
            {t('w6g.cur.whyTitle')}
            <ChevronDown size={14} aria-hidden="true" />
          </summary>
          <p>{t('w6g.cur.whyBody')}</p>
        </details>

        {rows.length === 0 ? (
          <div className="fe-w6g-empty" role="status">
            <p>{t('w6g.cur.nothing')}</p>
            <Button variant="secondary" onClick={() => setQuery('')}>{t('w4.compare.clearSearch')}</Button>
          </div>
        ) : (
          <div className="fe-trow-list">
            {rows.map((ind, index) => (
              <CurrencyRow key={ind.code} ind={ind} index={index} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
