// Раздел «Курсы валют и криптовалют». Слева: две плитки доллара («Курс ЦБ» и «Рынок»), конвертер, вкладки «Валюты / Крипто / Мир»
// и строки курсов. Справа: график выбранной пары за год и «Золото, нефть, биткоин». На телефоне всё идёт одной колонкой.
import { useId, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { ArrowRightLeft, Info, Search, X } from 'lucide-react';
import Button from './Button';
import DeltaBadge from './DeltaBadge';
import Sparkline from './Sparkline';
import CurrencySelect, { CoinBadge } from './CurrencySelect';
import { SkeletonBox } from './Skeleton';
import { useIndicatorData } from '../lib/hooks';
import { cn, formatDate, formatValue } from '../lib/format';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { russiaIndicatorPath } from '../lib/sitePaths';
import { CHART_THEME, GRID_PROPS, axisTick } from '../lib/chartTheme';
import {
  CURRENCY_TABS, UNITS, buildEdges, convert, convertibleUnits, formatConverted,
  pairTab, pairTitle, parseAmountInput, parsePair, rateBasis, sortByPopularity,
} from '../lib/currencyRates';
import { MARKET_BOARD_CODES, chartPairFor, useMarketSnapshots, yearSeries } from '../lib/currencyMarket';
import { track, events } from '../lib/track';
import { useGlintOnChange } from '../lib/calcGlint';
import { useLocale, useT } from '../i18n';
import '../styles/y2-indicator.css';
import '../styles/w6-g.css';
import '../styles/z8-tools.css';
import '../styles/k8-tools.css';

const QUICK_AMOUNTS = ['1', '100', '1000', '10000'];
const MARKET_LABEL_KEYS = { 'gold-rub-live': 'w6b.ticker.gold', brent: 'w6b.ticker.brent', 'btc-usd': 'w6b.ticker.btc' };
const MARKET_LINKS = { 'gold-rub-live': 'gold-price', brent: 'brent', 'btc-usd': 'btc-usd' };
const MARKET_UNITS = { 'gold-rub-live': '₽/г', brent: '$', 'btc-usd': '$' };
const MARKET_DIGITS = { 'gold-rub-live': 0, brent: 2, 'btc-usd': 0 };

function unitName(unit, locale) {
  const meta = UNITS[unit];
  if (!meta) return unit;
  return locale === 'en' ? meta.en : meta.ru;
}

/** Значок валюты: у доллара знак «$» (флаг США читался как «валюта страны»), у остальных флаг, у монет их знак. */
function coinOf(unit) {
  const meta = UNITS[unit];
  if (!meta) return {};
  return unit === 'USD' ? { symbol: '$' } : { flag: meta.flag, symbol: meta.symbol };
}

function shortDate(iso, locale) {
  if (!iso) return '';
  return new Date(`${String(iso).slice(0, 10)}T12:00:00Z`).toLocaleDateString(
    locale === 'en' ? 'en-US' : 'ru-RU',
    { day: 'numeric', month: 'short', timeZone: 'UTC' },
  );
}

function rateDigits(value) {
  const abs = Math.abs(value);
  if (abs >= 1000) return 0;
  if (abs >= 1) return 2;
  if (abs >= 0.01) return 4;
  return 6;
}

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
function RateTiles({ edges, market }) {
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
        ) : null}
      </div>
      {live ? (
        <p className="fe-z8-why">
          <Info size={15} aria-hidden="true" />
          <span>{t('z8.cur.why')}</span>
        </p>
      ) : null}
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
              {`1 ${safeFrom} = ${formatConverted(one.value, locale)} ${safeTo}`}
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
  const amount = parseAmountInput(amountText);
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
    const meta = UNITS[unit];
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
            className={cn('fe-z8-quick__btn fe-press', amountText.replace(/\s/g, '') === value && 'is-active')}
            onClick={() => setAmountText(value)}
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

function ChartTip({ active, payload, unit, locale }) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;
  return (
    <div className="fe-z8-tip glass-surface">
      <p className="fe-z8-tip__date">{formatDate(point.date, 'full', locale)}</p>
      <p className="fe-z8-tip__val">{formatValue(point.value, rateDigits(point.value), locale)}{unit ? `\u00A0${unit}` : ''}</p>
    </div>
  );
}

/** Крупный график выбранной пары за год: золотая линия, текущее значение и изменение за год. */
function YearChart({ pair }) {
  const t = useT();
  const { locale } = useLocale();
  const { data, isLoading } = useIndicatorData(pair?.code, { limit: 400 });
  const series = useMemo(() => yearSeries(data?.data, { invert: pair?.invert }), [data, pair?.invert]);
  if (!pair) return null;
  const quote = UNITS[pair.quote];
  const unit = quote?.symbol || '';
  const title = t('z8.cur.chartTitle', { pair: `${unitName(pair.base, locale)} → ${unitName(pair.quote, locale)}` });

  if (isLoading) {
    return (
      <section className="fe-panel fe-z8-chart" aria-busy="true" data-block="currency-year-chart">
        <SkeletonBox className="fe-z8-chart__skeleton" />
      </section>
    );
  }
  if (series.length < 2) return null;

  const first = series[0].value;
  const last = series[series.length - 1].value;
  const pct = first ? ((last - first) / first) * 100 : null;
  const delta = pct != null ? formatDeltaWithUnit(pct, '%', { pct: true, locale, digits: 1 }) : null;
  const lastIndex = series.length - 1;
  const ticks = [0, 1, 2, 3, 4].map((i) => series[Math.round((lastIndex * i) / 4)].date);
  const monthOf = (date) => new Date(`${date}T12:00:00Z`).toLocaleDateString(
    locale === 'en' ? 'en-US' : 'ru-RU', { month: 'short', timeZone: 'UTC' },
  ).replace('.', '');

  return (
    <section className="fe-panel fe-z8-chart" data-block="currency-year-chart" aria-label={title}>
      <header className="fe-z8-chart__head">
        <div>
          <h2 className="fe-z8-chart__title">{title}</h2>
          <p className="fe-z8-chart__value">
            <span className="fe-z8-chart__num">{formatValue(last, rateDigits(last), locale)}</span>
            {unit && <span className="fe-z8-chart__unit">{unit}</span>}
          </p>
        </div>
        {delta && !delta.flat && (
          <p className="fe-z8-chart__delta">
            <DeltaBadge delta={pct}>{delta.text}</DeltaBadge>
            <span>{t('z8.cur.perYear')}</span>
          </p>
        )}
      </header>
      <div className="fe-z8-chart__plot" role="img" aria-label={title}>
        <div className="fe-z8-chart__abs">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="z8CurGold" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHART_THEME.champagne} stopOpacity={0.32} />
                <stop offset="100%" stopColor={CHART_THEME.champagne} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis
              dataKey="date"
              ticks={ticks}
              interval={0}
              tickLine={false}
              axisLine={false}
              tick={axisTick({ fontSize: 12 })}
              tickFormatter={monthOf}
            />
            <YAxis
              domain={[(min) => min * 0.985, (max) => max * 1.015]}
              tickCount={4}
              tickLine={false}
              axisLine={false}
              width={52}
              tick={axisTick({ fontSize: 12 })}
              tickFormatter={(v) => formatValue(v, rateDigits(v) > 2 ? 3 : rateDigits(v), locale)}
            />
            <Tooltip content={<ChartTip unit={unit} locale={locale} />} cursor={{ stroke: CHART_THEME.champagne, strokeWidth: 1.5, strokeOpacity: 0.55 }} />
            <Area
              type="monotone"
              dataKey="value"
              stroke={CHART_THEME.champagne}
              strokeWidth={2.5}
              fill="url(#z8CurGold)"
              dot={false}
              activeDot={{ r: 5, fill: CHART_THEME.champagne, stroke: CHART_THEME.surface, strokeWidth: 2 }}
              isAnimationActive
              animationDuration={700}
            />
          </AreaChart>
        </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
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
                <span className="fe-z8-board__name">{t(MARKET_LABEL_KEYS[code])}</span>
                {showPct && (
                  <DeltaBadge delta={pct} className="fe-z8-board__delta">
                    {formatDeltaWithUnit(pct, '%', { pct: true, locale, digits: 1 }).text}
                  </DeltaBadge>
                )}
                <span className="fe-z8-board__price">
                  <span className="fe-z8-board__num">{formatValue(snap.price, MARKET_DIGITS[code], locale)}</span>
                  <span className="fe-z8-board__unit">{MARKET_UNITS[code]}</span>
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
  const quote = pair ? UNITS[pair.quote] : null;
  const coin = pair ? coinOf(pair.base) : {};
  const title = pairTitle(ind.code, locale, locale === 'en' && ind.name_en ? ind.name_en : ind.name);
  const basis = rateBasis(ind.code);
  const value = Number(ind.current_value);
  const change = Number(ind.change);
  const pct = pctOf(change, value);
  const delta = pct != null ? formatDeltaWithUnit(pct, '%', { pct: true, locale }) : null;
  const dateText = shortDate(ind.current_date, locale);
  const digits = Math.abs(value) >= 1000 ? 0 : 2;
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
  const [from, setFrom] = useState('USD');
  const [to, setTo] = useState('RUB');
  const needle = query.trim().toLowerCase();
  const market = useMarketSnapshots();

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
      <div className="fe-z8-cur__rates"><RateTiles edges={edges} market={market} /></div>
      <div className="fe-z8-cur__conv"><Converter edges={edges} from={from} to={to} onFrom={setFrom} onTo={setTo} /></div>
      <div className="fe-z8-cur__chart"><YearChart pair={pair} /></div>

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
            <span className="fe-k8-shard" aria-hidden="true" />
            <p>{t('w6g.cur.nothing')}</p>
            <Button variant="secondary" onClick={() => setQuery('')}>{t('w4.compare.clearSearch')}</Button>
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
