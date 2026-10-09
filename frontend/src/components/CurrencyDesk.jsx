// Раздел «Курсы валют и криптовалют». Слева: две плитки доллара («Курс ЦБ» и «Рынок»), конвертер, вкладки «Валюты / Крипто / Мир»
// и строки курсов. Справа: график выбранной пары за год и «Золото, нефть, биткоин». На телефоне всё идёт одной колонкой.
import { useId, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRightLeft, Info, Search, X } from 'lucide-react';
import Button from './Button';
import DeltaBadge from './DeltaBadge';
import Sparkline from './Sparkline';
import CurrencySelect, { CoinBadge } from './CurrencySelect';
import CurrencyPairChart from './CurrencyPairChart';
import { useIndicatorData } from '../lib/hooks';
import { cn, formatDate, formatValue } from '../lib/format';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { indicatorPolarity } from '../lib/deltaTone';
import { russiaIndicatorPath } from '../lib/sitePaths';
import EmptyState from './brand/EmptyState';
import {
  CURRENCY_TABS, buildEdges, convert, convertibleUnits, formatConverted,
  formatRate, pairTab, pairTitle, parseAmountInput, parsePair, rateBasis, sortByPopularity, unitMeta,
} from '../lib/currencyRates';
import { coinOf, unitName } from '../lib/currencyChart';
import { MARKET_BOARD_CODES, chartPairFor, useMarketState } from '../lib/currencyMarket';
import { track, events } from '../lib/track';
import { useGlintOnChange } from '../lib/calcGlint';
import { useLocale, useT } from '../i18n';
import '../styles/y2-indicator.css';
import '../styles/w6-g.css';
import '../styles/z8-tools.css';
import '../styles/k4-charts.css';
import '../styles/k8-tools.css';
import '../styles/c8-currency.css';

const QUICK_AMOUNTS = ['1', '100', '1000', '10000'];
const MARKET_LABEL_KEYS = { 'gold-rub-live': 'w6b.ticker.gold', brent: 'w6b.ticker.brent', 'btc-usd': 'w6b.ticker.btc' };
const MARKET_LINKS = { 'gold-rub-live': 'gold-price', brent: 'brent', 'btc-usd': 'btc-usd' };
const MARKET_UNITS = { 'gold-rub-live': '₽/г', brent: '$', 'btc-usd': '$' };
// На английской версии «₽/г» читается как «RUB/g»: рубль и грамм без кириллицы.
const MARKET_UNITS_EN = { 'gold-rub-live': 'RUB/g' };
const MARKET_DIGITS = { 'gold-rub-live': 0, brent: 2, 'btc-usd': 0 };

function shortDate(iso, locale) {
  if (!iso) return '';
  return new Date(`${String(iso).slice(0, 10)}T12:00:00Z`).toLocaleDateString(
    locale === 'en' ? 'en-US' : 'ru-RU',
    { day: 'numeric', month: 'short', timeZone: 'UTC' },
  );
}

/** Сколько полных суток прошло с даты ряда; нет даты: 0. */
function ageInDays(iso) {
  if (!iso) return 0;
  const ms = Date.parse(`${String(iso).slice(0, 10)}T12:00:00Z`);
  return Number.isFinite(ms) ? Math.floor((Date.now() - ms) / 86_400_000) : 0;
}
/** Данные старше трёх суток считаются устаревшими (в строке вместо изменения серая пометка). */
const STALE_AFTER_DAYS = 3;

function pctOf(change, value) {
  const prev = value - change;
  return Number.isFinite(change) && Number.isFinite(prev) && prev !== 0 ? (change / prev) * 100 : null;
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

/** Доллар двумя числами: официальный курс ЦБ (для учёта) и рыночный (меняется в течение дня), с пояснением в одну строку. */
function RateTiles({ edges, market, pending = false }) {
  const t = useT();
  const { locale } = useLocale();
  const cb = edges.find((edge) => edge.code === 'usd-rub');
  const live = market['usd-rub-live'];
  if (!cb) return null;
  const livePct = Number(live?.change_pct);
  const showPct = Number.isFinite(livePct) && Math.abs(livePct) >= 0.05;
  return (
    <section className="fe-z8-rates" data-block="currency-rate-tiles" aria-label={t('z8.cur.ratesAria')}>
      <div className="fe-z8-rates__grid">
        <div className="fe-z8-rate fe-z8-rate--cb fe-reveal fe-reveal--free" style={{ '--fe-delay': '0ms' }}>
          <p className="fe-z8-rate__label">
            <span className="fe-z8-rate__mark" aria-hidden="true" />
            {t('z8.cur.tile.cb', { date: shortDate(cb.date, locale) })}
          </p>
          <p className="fe-z8-rate__value">
            <span className="fe-z8-rate__num">{formatValue(cb.rate, 2, locale)}</span>
            <span className="fe-z8-rate__unit">₽</span>
          </p>
          <p className="fe-z8-rate__note">{t('z8.cur.tile.cbNote')}</p>
        </div>
        {live ? (
          <div className="fe-z8-rate fe-reveal fe-reveal--free" style={{ '--fe-delay': '60ms' }}>
            <p className="fe-z8-rate__label">{t('z8.cur.tile.market')}</p>
            <p className="fe-z8-rate__value">
              <span className="fe-z8-rate__num">{formatValue(live.price, 2, locale)}</span>
              <span className="fe-z8-rate__unit">₽</span>
              {showPct && (
                <DeltaBadge delta={livePct} className="fe-z8-rate__delta">
                  {formatDeltaWithUnit(livePct, '%', { pct: true, locale, digits: 1 }).text}
                </DeltaBadge>
              )}
            </p>
            <p className="fe-z8-rate__note">{t('z8.cur.tile.marketNote')}</p>
          </div>
        ) : pending ? (
          // Пока рыночный курс грузится, его место занято: конвертер ниже не сдвигается, когда плитка появится.
          <div className="fe-z8-rate-ghost" aria-hidden="true" />
        ) : null}
      </div>
      {live ? (
        <p className="fe-z8-why">
          <Info size={15} aria-hidden="true" />
          <span>{t('z8.cur.why')}</span>
        </p>
      ) : pending ? <div className="fe-z8-why-ghost" aria-hidden="true" /> : null}
    </section>
  );
}

/** Результат конвертера: «камень» с золотой цифрой; блик проходит заново, когда число изменилось. */
function ConverterOut({ result, one, safeFrom, safeTo, basisKey }) {
  const t = useT();
  const { locale } = useLocale();
  const ref = useRef(null);
  useGlintOnChange(ref, result ? result.value : null);
  return (
    <div ref={ref} className="fe-z8-conv__out fe-glint" aria-live="polite" data-testid="converter-result">
      {result ? (
        <>
          <p className="fe-z8-conv__sum">
            <span className="fe-z8-conv__num">{formatConverted(result.value, locale)}</span>
            <span className="fe-z8-conv__unit">{unitName(safeTo, locale)}</span>
          </p>
          {one && (
            <p className="fe-z8-conv__rate">
              {`1 ${safeFrom} = ${formatRate(one.value, locale)} ${safeTo}`}
            </p>
          )}
          {result.date && (
            <p className="fe-z8-conv__note">
              {t(basisKey, { date: formatDate(result.date, 'day', locale) })}
            </p>
          )}
        </>
      ) : (
        <p className="fe-z8-conv__note">{t('w6g.cur.badAmount')}</p>
      )}
    </div>
  );
}

/** Сумма в поле одним видом с кнопками «1 000», «10 000»: тысячи отделены пробелом, дробь сохраняется. */
function groupedAmount(amount, locale) {
  if (!Number.isFinite(amount)) return '';
  const digits = Number.isInteger(amount) ? 0 : Math.min(8, (String(amount).split('.')[1] || '').length);
  return formatValue(amount, digits, locale);
}

function Converter({ edges, from, to, onFrom, onTo }) {
  const t = useT();
  const { locale } = useLocale();
  const id = useId();
  const units = useMemo(() => convertibleUnits(edges), [edges]);
  const [amountText, setAmountText] = useState('100');
  // Каждое нажатие на «⇄» поворачивает стрелки ещё на 180° (k8-tools: --k8-turn).
  const [turns, setTurns] = useState(0);
  if (units.length < 2) return null;

  const safeFrom = units.includes(from) ? from : units[0];
  const safeTo = units.includes(to) && to !== safeFrom ? to : units.find((u) => u !== safeFrom);
  const amount = parseAmountInput(amountText, locale);
  const result = amount != null ? convert(amount, safeFrom, safeTo, edges) : null;
  const one = convert(1, safeFrom, safeTo, edges);

  const bases = result ? new Set(result.path.map((code) => rateBasis(code)).filter(Boolean)) : new Set();
  const basisKey = bases.size === 1 ? `w6g.cur.basis.${[...bases][0]}` : 'w6g.cur.basis.mix';
  const swap = () => {
    onFrom(safeTo);
    onTo(safeFrom);
    setTurns((n) => n + 1);
    track(events.COMPARE_CHANGE, { converter: 'swap' });
  };
  const optionOf = (unit) => {
    const meta = unitMeta(unit);
    return {
      value: unit,
      name: unitName(unit, locale),
      ...coinOf(unit),
      search: [unit, meta.ru, meta.en, meta.symbol].join(' ').toLowerCase(),
    };
  };
  const fromOptions = units.map(optionOf);
  const toOptions = units.filter((unit) => unit !== safeFrom).map(optionOf);

  return (
    <section className="fe-panel fe-z8-conv" data-block="currency-converter" aria-label={t('w6g.cur.converterTitle')}>
      <h2 className="fe-z8-conv__title">{t('w6g.cur.converterTitle')}</h2>
      <div className="fe-z8-conv__row">
        <label className="fe-z8-field fe-z8-conv__amount" htmlFor={`${id}-amount`}>
          <span className="fe-z8-select__label">{t('w6g.cur.amount')}</span>
          <input
            id={`${id}-amount`}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
            onFocus={(event) => { const node = event.target; window.setTimeout(() => { if (document.activeElement === node) node.select(); }, 0); }}
            onBlur={() => { if (amount != null && amountText.trim() !== '') setAmountText(groupedAmount(amount, locale)); }}
            aria-invalid={amount == null ? 'true' : undefined}
            className="fe-z8-input"
          />
        </label>
        <CurrencySelect
          label={t('w6g.cur.from')}
          value={safeFrom}
          options={fromOptions}
          onChange={onFrom}
          searchPlaceholder={t('w6g.cur.search')}
          emptyText={t('w6g.cur.nothing')}
          className="fe-z8-conv__from"
        />
        <button
          type="button"
          className="fe-z8-swap fe-press"
          style={{ '--k8-turn': `${turns * 180}deg` }}
          onClick={swap}
          aria-label={t('w6g.cur.swap')}
          title={t('w6g.cur.swap')}
        >
          <ArrowRightLeft size={18} aria-hidden="true" />
        </button>
        <CurrencySelect
          label={t('w6g.cur.to')}
          value={safeTo}
          options={toOptions}
          onChange={onTo}
          searchPlaceholder={t('w6g.cur.search')}
          emptyText={t('w6g.cur.nothing')}
          className="fe-z8-conv__to"
        />
      </div>
      <div className="fe-z8-quick" role="group" aria-label={t('z8.cur.quickAria')}>
        {QUICK_AMOUNTS.map((value) => (
          <button
            key={value}
            type="button"
            className={cn('fe-z8-quick__btn fe-press', amount === Number(value) && 'is-active')}
            onClick={() => setAmountText(groupedAmount(Number(value), locale))}
          >
            {formatValue(Number(value), 0, locale)}
          </button>
        ))}
      </div>

      <ConverterOut
        result={result}
        one={one}
        safeFrom={safeFrom}
        safeTo={safeTo}
        basisKey={basisKey}
      />
    </section>
  );
}

/** Дата значения у цены: сервер отдаёт as_of_day (день одним форматом) для живых и дневных рядов. */
function boardDate(snap, locale = 'ru') {
  const day = snap?.as_of_day || snap?.as_of_date || '';
  return day ? shortDate(day, locale) : '';
}

/** «Золото, нефть, биткоин»: рыночные цены из той же ленты, что и строка сверху. */
function MarketBoard({ market }) {
  const t = useT();
  const { locale } = useLocale();
  const items = MARKET_BOARD_CODES.filter((code) => market[code]);
  if (!items.length) return null;
  return (
    <section className="fe-panel fe-z8-board" data-block="currency-market-board" aria-label={t('z8.cur.boardTitle')}>
      <h2 className="fe-z8-board__title">{t('z8.cur.boardTitle')}</h2>
      <ul className="fe-z8-board__list">
        {items.map((code) => {
          const snap = market[code];
          const pct = Number(snap.change_pct);
          const showPct = Number.isFinite(pct) && Math.abs(pct) >= 0.05;
          return (
            <li key={code}>
              <Link to={russiaIndicatorPath(MARKET_LINKS[code])} className="fe-z8-board__row fe-press">
                <span className="fe-z8-board__name">
                  {t(MARKET_LABEL_KEYS[code])}
                  {boardDate(snap) && (
                    <span className={cn('fe-c11e-board__date', snap.stale && 'is-stale')}>
                      {snap.stale ? t('c9d.cur.stale', { date: boardDate(snap, locale) }) : t('c11e.cur.board.asOf', { date: boardDate(snap, locale) })}
                    </span>
                  )}
                </span>
                {showPct && (
                  <DeltaBadge delta={pct} polarity="market" className="fe-z8-board__delta">
                    {formatDeltaWithUnit(pct, '%', { pct: true, locale, digits: 1 }).text}
                  </DeltaBadge>
                )}
                <span className="fe-z8-board__price">
                  <span className="fe-z8-board__num">{formatValue(snap.price, MARKET_DIGITS[code], locale)}</span>
                  <span className="fe-z8-board__unit">{locale === 'en' ? (MARKET_UNITS_EN[code] || MARKET_UNITS[code]) : MARKET_UNITS[code]}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function CurrencyRow({ ind, index }) {
  const t = useT();
  const { locale } = useLocale();
  const pair = parsePair(ind.code);
  const quote = pair ? unitMeta(pair.quote) : null;
  const coin = pair ? coinOf(pair.base) : {};
  const title = pairTitle(ind.code, locale, locale === 'en' && ind.name_en ? ind.name_en : ind.name);
  const basis = rateBasis(ind.code);
  const value = Number(ind.current_value);
  const change = Number(ind.change);
  const pct = pctOf(change, value);
  const delta = pct != null ? formatDeltaWithUnit(pct, '%', { pct: true, locale }) : null;
  const dateText = shortDate(ind.current_date, locale);
  const digits = Math.abs(value) >= 1000 ? 0 : 2;
  const stale = ageInDays(ind.current_date) > STALE_AFTER_DAYS;
  return (
    <Link
      to={russiaIndicatorPath(ind.code)}
      className="fe-trow fe-press fe-w6g-currency-row fe-z8-row"
      onClick={() => track(events.CATEGORY_TILE_CLICK, { indicator: ind.code, surface: 'currencies' })}
    >
      <CoinBadge className="fe-w6g-coin" flag={coin.flag} symbol={coin.symbol} />
      <span className="fe-trow__main">
        <h3 className="fe-trow__title">{title}</h3>
        <span className="fe-trow__meta">
          {delta && !delta.flat && !stale && (
            <DeltaBadge delta={pct} polarity={indicatorPolarity(ind.name, ind.name_en, ind.code)}>{delta.text}</DeltaBadge>
          )}
          {basis && (
            <span className={cn('fe-trow__date', stale && 'is-stale')}>
              {stale ? t('c9d.cur.stale', { date: dateText }) : t(`w6g.cur.basisShort.${basis}`, { date: dateText })}
            </span>
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
      const meta = unitMeta(unit);
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
  const [from, setFrom] = useState('USD');
  const [to, setTo] = useState('RUB');
  const needle = query.trim().toLowerCase();
  const { market, pending: marketPending } = useMarketState();

  const sorted = useMemo(() => sortByPopularity(indicators || []), [indicators]);
  const edges = useMemo(() => buildEdges(sorted), [sorted]);
  const counts = useMemo(() => {
    const map = { rub: 0, crypto: 0, world: 0 };
    sorted.forEach((ind) => { map[pairTab(ind.code)] += 1; });
    return map;
  }, [sorted]);
  const tabs = CURRENCY_TABS.filter((id) => counts[id] > 0);
  const activeTab = tabs.includes(tab) ? tab : tabs[0];

  const units = useMemo(() => convertibleUnits(edges), [edges]);
  const safeFrom = units.includes(from) ? from : units[0];
  const safeTo = units.includes(to) && to !== safeFrom ? to : units.find((u) => u !== safeFrom);
  const pair = useMemo(() => chartPairFor(edges, safeFrom, safeTo), [edges, safeFrom, safeTo]);
  const hasBoard = MARKET_BOARD_CODES.some((code) => market[code]);

  const rows = needle
    ? sorted.filter((ind) => matchesQuery(ind, needle))
    : sorted.filter((ind) => pairTab(ind.code) === activeTab);

  return (
    <div className={cn('fe-z8-cur', hasBoard && 'has-board')}>
      <div className="fe-z8-cur__rates"><RateTiles edges={edges} market={market} pending={marketPending} /></div>
      <div className="fe-z8-cur__conv"><Converter edges={edges} from={from} to={to} onFrom={setFrom} onTo={setTo} /></div>
      <div className="fe-z8-cur__chart"><CurrencyPairChart pair={pair} edges={edges} /></div>

      <section className="fe-z8-cur__list" data-block="currency-list" aria-label={t('w6g.cur.listTitle')}>
        <div className="fe-z8-toolbar">
          <div
            className={cn('fe-z8-seg', needle && 'is-idle')}
            style={{ '--k8-i': Math.max(0, tabs.indexOf(activeTab)), '--k8-n': Math.max(1, tabs.length) }}
            role="group"
            aria-label={t('w6g.cur.tabsAria')}
          >
            {tabs.map((id) => (
              <button
                key={id}
                type="button"
                aria-pressed={!needle && activeTab === id}
                className={cn('fe-z8-seg__btn fe-press', !needle && activeTab === id && 'is-active')}
                onClick={() => { setTab(id); setQuery(''); }}
              >
                {t(`w6g.cur.tab.${id}`)}
              </button>
            ))}
          </div>
          <label className="fe-z8-search">
            <Search size={16} aria-hidden="true" />
            <span className="sr-only">{t('w6g.cur.search')}</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t('w6g.cur.search')}
              autoComplete="off"
              className="fe-z8-search__input"
            />
            {query && (
              <button type="button" className="fe-z8-search__clear" aria-label={t('common.clear')} onClick={() => setQuery('')}>
                <X size={16} aria-hidden="true" />
              </button>
            )}
          </label>
        </div>

        {rows.length === 0 ? (
          <div className="fe-w6g-empty" role="status">
            <EmptyState
              variant="no-results"
              size={88}
              title={t('w6g.cur.nothing')}
              action={<Button variant="secondary" onClick={() => setQuery('')}>{t('w4.compare.clearSearch')}</Button>}
            />
          </div>
        ) : (
          <div className="fe-trow-list fe-z8-rows">
            {rows.map((ind, index) => (
              <CurrencyRow key={ind.code} ind={ind} index={index} />
            ))}
          </div>
        )}
      </section>

      <div className="fe-z8-cur__board"><MarketBoard market={market} /></div>
    </div>
  );
}
