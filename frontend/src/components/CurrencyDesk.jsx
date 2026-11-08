// Раздел «Курсы валют и криптовалют». Слева: две плитки доллара («Курс ЦБ» и «Рынок»), конвертер, вкладки «Валюты / Крипто / Мир»
// и строки курсов. Справа: график выбранной пары за год и «Золото, нефть, биткоин». На телефоне всё идёт одной колонкой.
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Info, Search, X } from 'lucide-react';
import Button from './Button';
import DeltaBadge from './DeltaBadge';
import Sparkline from './Sparkline';
import { CoinBadge } from './CurrencySelect';
import { Converter } from './CurrencyConverter';
import CurrencyPairChart from './CurrencyPairChart';
import { useIndicatorData } from '../lib/hooks';
import { cn, formatValue } from '../lib/format';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { indicatorPolarity } from '../lib/deltaTone';
import { russiaIndicatorPath } from '../lib/sitePaths';
import EmptyState from './brand/EmptyState';
import {
  CURRENCY_TABS, buildEdges, convertibleUnits, currencySearchText, nominalFor, pairTab, pairTitle, parsePair, quoteUnitsOf, rateBasis,
  sortByPopularity, unitMeta, unitWord,
} from '../lib/currencyRates';
import { coinOf } from '../lib/currencyChart';
import { MARKET_BOARD_CODES, chartPairFor, useMarketState } from '../lib/currencyMarket';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import '../styles/y2-indicator.css';
import '../styles/w6-g.css';
import { converterCurrency, usePrefs } from '../lib/cabinetPrefs';
import '../styles/z8-tools.css';
import '../styles/k4-charts.css';
import '../styles/k8-tools.css';
import '../styles/c8-currency.css';
import '../styles/z3-cur.css';

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
  const stale = ageInDays(ind.current_date) > STALE_AFTER_DAYS;
  // «Узбекский сум» крупно, «к рублю» тише: на узком экране название идёт в одну строку.
  const baseName = pair ? (locale === 'en' ? unitMeta(pair.base).en : unitMeta(pair.base).ru) : '';
  const split = baseName && title.startsWith(baseName) && title.length > baseName.length;
  const head = split ? baseName : title;
  const tail = split ? title.slice(baseName.length) : '';
  // Ряд мелкой валюты, который пришёл «за 1» (тенге 0,18 ₽), показываем как ЦБ: «18,31 ₽ за 100 тенге».
  const apiN = quoteUnitsOf(ind.unit);
  const perN = apiN > 1 ? apiN : (pair ? nominalFor(pair.base, value) : 1);
  const shown = apiN > 1 ? value : value * perN;
  const digits = Math.abs(shown) >= 1000 ? 0 : 2;
  const showDelta = delta && !delta.flat && !stale;
  return (
    <Link
      to={russiaIndicatorPath(ind.code)}
      className="fe-trow fe-press fe-w6g-currency-row fe-z8-row"
      onClick={() => track(events.CATEGORY_TILE_CLICK, { indicator: ind.code, surface: 'currencies' })}
    >
      <CoinBadge className="fe-w6g-coin" flag={coin.flag} symbol={coin.symbol} />
      <span className="fe-trow__main">
        <h3 className="fe-trow__title">
          {head}
          {tail && <span className={cn('z3-to', pair?.quote === 'RUB' && 'z3-to--rub')}>{tail}</span>}
        </h3>
        <span className="fe-trow__meta">
          {showDelta && (
            <DeltaBadge delta={pct} polarity={indicatorPolarity(ind.name, ind.name_en, ind.code)}>{delta.text}</DeltaBadge>
          )}
          {showDelta && basis !== 'close' && <span className="z3-period">{t('z3.cur.perDay')}</span>}
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
      <span className="fe-trow__val z3-val">
        <span className="z3-val__main">
          <span className="fe-trow__num">{formatValue(shown, digits, locale)}</span>
          {quote?.symbol && <span className="fe-trow__unit z3-val__sym">{quote.symbol}</span>}
        </span>
        {perN > 1 && pair && (
          <span className="z3-val__per">
            {t('c9d.cur.perUnits', { n: `${formatValue(perN, 0, locale)}\u00a0${unitWord(perN, pair.base, locale)}` })}
          </span>
        )}
      </span>
    </Link>
  );
}

function matchesQuery(ind, needle) {
  const pair = parsePair(ind.code);
  const parts = [ind.code, ind.name, ind.name_en, pairTitle(ind.code, 'ru'), pairTitle(ind.code, 'en')];
  if (pair) {
    [pair.base, pair.quote].forEach((unit) => parts.push(currencySearchText(unit)));
  }
  const text = parts.filter(Boolean).join(' ').toLowerCase().replace(/ё/g, 'е');
  return needle.split(/\s+/).filter(Boolean).every((word) => text.includes(word));
}

export default function CurrencyDesk({ indicators }) {
  const t = useT();
  const [tab, setTab] = useState('rub');
  const [query, setQuery] = useState('');
  // Валюта конвертера по умолчанию из настроек кабинета (круг 12); пока человек не выбрал сам, входит «настройка → RUB», иначе «USD → RUB».
  const prefFrom = converterCurrency(usePrefs());
  const [pickedFrom, setFrom] = useState(null);
  const [to, setTo] = useState('RUB');
  const from = pickedFrom ?? prefFrom ?? 'USD';
  const needle = query.trim().toLowerCase().replace(/ё/g, 'е');
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
