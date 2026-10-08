import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '../lib/format';
import { russiaCategoryPath, russiaIndicatorPath } from '../lib/sitePaths';
import { tickerLaneFor } from '../lib/tickerLane';
import { tickerRefetchInterval } from '../lib/tickerPoll';
import { formatAsOfHuman, tickerSourceKind, tzFor, tickerSourceName } from '../lib/tickerFormat';
import { useScrollDirection } from '../lib/useScrollDirection';
import { useFooterTone } from '../lib/useFooterTone';
import { useLocale, useT } from '../i18n';
import '../styles/shell.css';
import '../styles/platform-pages.css';
import '../styles/z2-shell.css';
import '../styles/k3-shell.css';

/**
 * Мета ленты. linkTo — только если ведёт на ту же карточку/ряд, что и число.
 * Нет карточки → linkTo: null (не кликаем на чужой показатель).
 */
const TICKER_META = {
  // Единые знаки: курсы — два знака после запятой, биткоин и золото — целые.
  // nameKey — человеческое имя вместо кода пары («Доллар», а не USD/RUB); cur — в чём цена.
  'usd-rub-live':  { nameKey: 'w6b.ticker.usd', cur: 'rub', linkTo: russiaIndicatorPath('usd-rub'), decimals: 2 },
  'eur-rub-live':  { nameKey: 'w6b.ticker.eur', cur: 'rub', linkTo: russiaIndicatorPath('eur-rub'), decimals: 2 },
  'cny-rub-live':  { nameKey: 'w6b.ticker.cny', cur: 'rub', linkTo: russiaIndicatorPath('cny-rub'), decimals: 2 },
  'eur-usd':       { nameKey: 'w6b.ticker.eur', cur: 'usd', linkTo: russiaIndicatorPath('eur-usd'), decimals: 2 },
  'gbp-usd':       { nameKey: 'w6b.ticker.gbp', cur: 'usd', linkTo: russiaIndicatorPath('gbp-usd'), decimals: 2 },
  'usd-cny':       { nameKey: 'w7p.ticker.usdcny', cur: 'cny', pairLabel: true, linkTo: russiaIndicatorPath('usd-cny'), decimals: 2 },
  'btc-usd':       { nameKey: 'w6b.ticker.btc', cur: 'usd', linkTo: russiaIndicatorPath('btc-usd'), decimals: 0 },
  'brent':         { nameKey: 'w6b.ticker.brent', cur: 'usd', linkTo: russiaIndicatorPath('brent'), decimals: 2 },
  'gold-rub-live': { nameKey: 'w6b.ticker.gold', cur: 'rub', perGram: true, linkTo: russiaIndicatorPath('gold-price'), decimals: 0 },
};

const currenciesPath = () => russiaCategoryPath('currencies');

const CURRENCY_SIGN = { rub: '\u20BD', usd: '$', cny: '\u00A5' };

function formatPrice(value, decimals, locale = 'ru') {
  if (value === null || value === undefined) return '—';
  const tag = locale === 'en' ? 'en-US' : 'ru-RU';
  return value.toLocaleString(tag, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/**
 * Изменение за день со знаком: «+0,2 %», «−0,2 %» (круг 9, S5). Точка рядом с числом (зелёная/серо-синяя) направление лишь дублирует,
 * а «0,2 %» без знака читалось как рост или падение наугад. Минус настоящий (U+2212), не дефис.
 */
function formatPct(pct, locale = 'ru') {
  if (pct === null || pct === undefined) return '\u2014';
  const tag = locale === 'en' ? 'en-US' : 'ru-RU';
  const body = Math.abs(pct).toLocaleString(tag, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const sign = pct > 0 ? '+' : '\u2212';
  return locale === 'en' ? `${sign}${body}%` : `${sign}${body}\u00a0%`;
}

function formatAsOfTitle(isoDate, locale = 'ru') {
  if (!isoDate) return null;
  const d = isoDate.includes('T')
    ? new Date(isoDate)
    : new Date(`${isoDate}T12:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  const tag = locale === 'en' ? 'en-US' : 'ru-RU';
  return d.toLocaleDateString(tag, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: isoDate.includes('T') ? tzFor(locale) : undefined,
  });
}

/** Сколько полных календарных суток прошло с даты значения (по часовому поясу витрины); null, если даты нет. Круг 8, D5. */
function ageInDays(isoDate, locale, now = new Date()) {
  if (!isoDate) return null;
  const tz = tzFor(locale);
  let day = isoDate;
  if (isoDate.includes('T')) {
    const d = new Date(isoDate);
    if (Number.isNaN(d.getTime())) return null;
    day = d.toLocaleDateString('en-CA', { timeZone: tz });
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
  const today = now.toLocaleDateString('en-CA', { timeZone: tz });
  return Math.round((Date.parse(`${today}T12:00:00Z`) - Date.parse(`${day}T12:00:00Z`)) / 86400000);
}

/** Дневное значение старше этого числа суток подписывается «не обновлялось N дн.»: выходные и праздники метки не получают. */
const STALE_AFTER_DAYS = 3;

function resolveAsOfRaw(snapshot) {
  if (snapshot.as_of_date) return snapshot.as_of_date;
  if (snapshot.fetched_at) return snapshot.fetched_at;
  return null;
}

function TickerCell({ snapshot, nowMs }) {
  const t = useT();
  const { locale } = useLocale();
  // Хуки должны вызываться в стабильном порядке на каждом рендере (React rules-of-hooks);
  // ранний return ставим **после** объявления хуков, иначе ESLint roof-of-hooks ошибка.
  const meta = TICKER_META[snapshot.code];
  const isIntraday = Boolean(snapshot.market_open);

  // Flash только у внутридневных котировок. Дневные ряды карточек не мигают —
  // цена стабильна между ETL, иначе создаётся ложное ощущение «живой» биржи.
  const [lastSeenPrice, setLastSeenPrice] = useState(snapshot.price);
  const [flash, setFlash] = useState(null); // 'up' | 'down' | null
  if (isIntraday && lastSeenPrice !== snapshot.price) {
    setFlash(snapshot.price > lastSeenPrice ? 'up' : 'down');
    setLastSeenPrice(snapshot.price);
  } else if (!isIntraday && lastSeenPrice !== snapshot.price) {
    setLastSeenPrice(snapshot.price);
  }
  useEffect(() => {
    if (!flash) return undefined;
    const timer = setTimeout(() => setFlash(null), 600);
    return () => clearTimeout(timer);
  }, [flash]);

  if (!meta) return null;

  const pct = snapshot.change_pct;
  const hasPrice = snapshot.price > 0;

  const fetchedMs = snapshot.fetched_at ? new Date(snapshot.fetched_at).getTime() : null;
  const isStale = isIntraday && fetchedMs !== null && nowMs - fetchedMs > 15 * 60 * 1000;
  const asOfRaw = !isIntraday ? resolveAsOfRaw(snapshot) : null;
  // Выходной день не делает дневной курс «устаревшим»: дату пишем, только когда значению больше четырёх суток.
  const asOfHuman = formatAsOfHuman(asOfRaw, locale, new Date(), { minAgeDays: 4 });
  const sourceKind = tickerSourceKind(snapshot.source);
  const asOfTitle = formatAsOfTitle(asOfRaw, locale);
  const asOfClock = fetchedMs !== null
    ? new Date(fetchedMs).toLocaleTimeString(locale === 'en' ? 'en-US' : 'ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: tzFor(locale),
    })
    : null;

  const titleParts = [t('ticker.source', { source: tickerSourceName(snapshot.source, locale) })];
  // Подпись «биржа» или «ЦБ» стоит мелко под ценой (от 768 px), а полное название источника остаётся в подсказке.
  if (sourceKind) titleParts.unshift(t(`shell.ticker.source.${sourceKind}`));
  if (!isIntraday) {
    if (asOfTitle) titleParts.push(t('ticker.valueAsOf', { date: asOfTitle }));
  } else {
    if (!snapshot.market_open) titleParts.push(t('ticker.marketClosed'));
    if (asOfClock) {
      titleParts.push(
        isStale
          ? t('ticker.dataStale', { time: asOfClock })
          : t('ticker.dataAt', { time: asOfClock }),
      );
    }
  }

  // Круг 8, D5 и волна 2: значение старше трёх суток не должно выглядеть живым, но и «заброшенным» тоже.
  // Круг 9, S5: решение принимает сервер (поля `stale`, `age_days`, `as_of_day` у каждого снимка), клиентский пересчёт остаётся запасным.
  // У давнего значения нет процента изменения (красное «−0,9 %» над вчерашней ценой выглядело свежим), а серая подпись говорит
  // «данные от 29 сент.»; полная дата остаётся в подсказке.
  const ageDays = !isIntraday
    ? (Number.isFinite(snapshot.age_days) ? snapshot.age_days : ageInDays(asOfRaw, locale))
    : null;
  const longStale = !isIntraday && (typeof snapshot.stale === 'boolean'
    ? snapshot.stale
    : (ageDays !== null && ageDays > STALE_AFTER_DAYS));
  const staleDate = longStale ? formatAsOfHuman(snapshot.as_of_day || asOfRaw, locale, new Date(), { minAgeDays: 1 }) : '';

  const cellClass = cn(
    'fe-ticker__cell flex h-full min-h-7 shrink-0 items-center gap-1.5 px-2.5 rounded-md whitespace-nowrap',
    'md:gap-2 md:px-3.5',
    'transition-colors duration-200',
    meta.linkTo && 'hover:bg-champagne/10',
    // Вспышка нового тика нейтральная: рост курса не «хорошо» и не «плохо», цвет не должен оценивать.
    flash && 'bg-champagne/15 fe-shadow-2',
    isStale && 'opacity-60',
  );

  // У пары «доллар к юаню» по-английски подпись «USD/CNY» сама говорит, что это за число: знак ¥ рядом
  // читался как «доллар к иене».
  const sign = (meta.pairLabel && locale === 'en') ? '' : (CURRENCY_SIGN[meta.cur] || '');
  // По-русски знак валюты после числа («85,79 ₽»), по-английски перед («$1.12»).
  const signFirst = locale === 'en' && meta.cur !== 'rub';
  const showPct = !longStale && pct !== null && pct !== undefined && Math.abs(pct) >= 0.05;
  // Подпись под ценой: «данные от 29 сент.» у давнего значения, иначе источник — «биржа» или «ЦБ».
  const staleLabel = longStale && staleDate ? t('c9a.ticker.staleFrom', { date: staleDate }) : undefined;
  const caption = staleLabel
    ? staleLabel
    : (asOfHuman
      ? t('shell.ticker.asOf', { date: asOfHuman })
      : (sourceKind ? t(`shell.ticker.source.${sourceKind}`) : null));
  const body = (
    <>
      <span className="fe-ticker__name" data-asof={staleLabel}>{t(meta.nameKey)}</span>
      <span className="fe-ticker__quote">
        <span className="fe-ticker__price tabular-nums">
          {signFirst && hasPrice ? <span className="fe-ticker__sign">{sign}</span> : null}
          <span>{hasPrice ? formatPrice(snapshot.price, meta.decimals, locale) : '\u2014'}</span>
          {!signFirst && hasPrice && sign ? <span className="fe-ticker__sign">{`\u00a0${sign}${meta.perGram ? t('w6b.ticker.perGram') : ''}`}</span> : null}
        </span>
        {caption ? <span className="fe-ticker__caption">{caption}</span> : null}
      </span>
      {showPct ? (
        <span className="fe-ticker__delta tabular-nums" data-dir={pct > 0 ? 'up' : 'down'}>
          <span aria-hidden="true">{pct > 0 ? '\u25B2' : '\u25BC'}</span>
          <span className="sr-only">{pct > 0 ? t('w6b.ticker.up') : t('w6b.ticker.down')}</span>
          {formatPct(pct, locale)}
        </span>
      ) : null}
    </>
  );

  if (meta.linkTo) {
    return (
      <Link to={meta.linkTo} className={cellClass} title={titleParts.join(' — ')} data-stale={longStale ? 'true' : undefined}>
        {body}
      </Link>
    );
  }

  return (
    <span className={cellClass} title={titleParts.join(' — ')} data-stale={longStale ? 'true' : undefined}>
      {body}
    </span>
  );
}

async function fetchLiveTicker(lane) {
  const r = await fetch(`/api/v1/ticker/live?lane=${encodeURIComponent(lane)}`, {
    cache: 'no-store',
    credentials: 'same-origin',
  });
  if (!r.ok) {
    const err = new Error(`Live ticker: HTTP ${r.status}`);
    err.status = r.status;
    if (r.status === 429) {
      const raw = Number.parseInt(r.headers.get('retry-after') || '60', 10);
      const sec = Number.isFinite(raw) ? raw : 60;
      err.retryAfterMs = Math.min(Math.max(sec, 1), 120) * 1000;
    }
    throw err;
  }
  return r.json();
}

/**
 * Лента курсов шире экрана: у края, где есть что показать, проявляется затухание, а при первом показе лента
 * один раз чуть сдвигается и возвращается — намёк «листается». Любое касание или колесо отменяет подсказку.
 */
function useEdgeFade(dep) {
  const ref = useRef(null);
  // Телефон: правое затухание горит с первого кадра («лента листается»), до первого измерения; на компьютере сначала выключено.
  const [edges, setEdges] = useState(() => ({ start: false, end: typeof window !== 'undefined' && window.innerWidth < 768 }));
  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const overflow = el.scrollWidth - el.clientWidth;
    const next = { start: overflow > 4 && el.scrollLeft > 4, end: overflow > 4 && el.scrollLeft < overflow - 4 };
    setEdges((prev) => (prev.start === next.start && prev.end === next.end ? prev : next));
  }, []);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const frame = window.requestAnimationFrame(measure);
    window.addEventListener('resize', measure);
    // Ширина ленты меняется, когда подгружаются шрифты и курсы: измеряем края заново, иначе затухания нет.
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    observer?.observe(el);
    if (el.firstElementChild) observer?.observe(el.firstElementChild);
    document.fonts?.ready?.then(measure).catch(() => {});
    let hintTimer = 0;
    let backTimer = 0;
    let cancelled = false;
    const cancel = () => { cancelled = true; window.clearTimeout(hintTimer); window.clearTimeout(backTimer); };
    const reduce = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduce && typeof el.scrollTo === 'function') {
      hintTimer = window.setTimeout(() => {
        if (cancelled || el.scrollWidth - el.clientWidth < 24 || el.scrollLeft > 0) return;
        el.scrollTo({ left: 56, behavior: 'smooth' });
        backTimer = window.setTimeout(() => { if (!cancelled) el.scrollTo({ left: 0, behavior: 'smooth' }); }, 900);
      }, 1400);
    }
    // Наведение курсора тоже останавливает подсказку: лента не должна «убегать» из-под руки.
    el.addEventListener('pointerdown', cancel, { passive: true });
    el.addEventListener('pointerenter', cancel, { passive: true });
    el.addEventListener('wheel', cancel, { passive: true });
    return () => {
      cancel();
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', measure);
      observer?.disconnect();
      el.removeEventListener('pointerdown', cancel);
      el.removeEventListener('pointerenter', cancel);
      el.removeEventListener('wheel', cancel);
    };
  }, [measure, dep]);
  return { ref, edges, measure };
}

/** Узкий экран (телефон до 768 px): «Все валюты» там последняя ячейка ленты; шире она стоит отдельным блоком справа, вне прокрутки. */
function usePhoneWidth() {
  const [phone, setPhone] = useState(() => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 767px)').matches);
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const mql = window.matchMedia('(max-width: 767px)');
    const apply = () => setPhone(mql.matches);
    apply();
    mql.addEventListener?.('change', apply);
    return () => mql.removeEventListener?.('change', apply);
  }, []);
  return phone;
}

export default function LiveTicker() {
  const t = useT();
  const phone = usePhoneWidth();
  const { locale } = useLocale();
  const lane = tickerLaneFor(locale);
  const { data, dataUpdatedAt } = useQuery({
    queryKey: ['ticker', 'live', lane],
    queryFn: () => fetchLiveTicker(lane),
    retry: false,
    refetchInterval: tickerRefetchInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
    staleTime: 0,
  });

  // Золото в ленте — учётная цена Банка России в рублях за грамм. Англоязычному посетителю рубли ничего не говорят,
  // а золото в долларах за унцию показывать нельзя (лицензия дневного ряда), поэтому в английской ленте его нет.
  const snapshots = (data?.snapshots || []).filter((s) => !(locale === 'en' && s.code === 'gold-rub-live'));
  const { ref: scrollerRef, edges, measure } = useEdgeFade(snapshots.length);
  // Телефон: при прокрутке вниз лента уезжает вверх (CSS, только transform и opacity), при прокрутке вверх возвращается.
  const { deep, dir } = useScrollDirection();
  const hidden = deep && dir === 'down';
  const overFooter = useFooterTone().ticker;
  // --fe-ticker-h: высота ленты (36 px, на телефоне 28): вместе с --fe-header-h (Navbar) задаёт `html { scroll-padding-top }`.
  const rootRef = useRef(null);
  const hasQuotes = snapshots.length > 0;
  useEffect(() => {
    const node = rootRef.current;
    if (!node || typeof document === 'undefined') return undefined;
    const root = document.documentElement;
    const apply = () => {
      const h = Math.ceil(node.offsetHeight);
      if (h > 0) root.style.setProperty('--fe-ticker-h', `${h}px`);
    };
    apply();
    let observer = null;
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(apply);
      observer.observe(node);
    }
    return () => {
      observer?.disconnect();
      root.style.removeProperty('--fe-ticker-h');
    };
  }, [hasQuotes]);
  if (snapshots.length === 0) {
    return (
      <div ref={rootRef} className="fe-ticker fixed top-0 inset-x-0 z-[110] h-9" />
    );
  }

  const allLink = (
    <Link
      to={currenciesPath()}
      className="fe-ticker__all flex h-full min-h-7 shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-3 text-champagne-ink hover:bg-champagne/10"
    >
      {t('w6b.ticker.all')}
      <ChevronRight size={14} aria-hidden="true" />
    </Link>
  );

  return (
    <div
      ref={rootRef}
      className="fe-ticker fixed top-0 inset-x-0 z-[110] h-9 pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)]"
      data-hidden={hidden ? 'true' : 'false'}
      data-tone={overFooter ? 'dark' : undefined}
    >
      <div className="fe-ticker__inner mx-auto h-full">
        <div className={cn('fe-ticker__scroller', !phone && 'fe-ticker__scroller--aside')}>
          {/* Курсы листаются в своей полосе (.fe-ticker__lane); на планшете и компьютере «Все валюты» стоит рядом с ней плотным блоком,
              поэтому ни один курс не уходит под него (круг 8, волна 2, W-A2). */}
          <div className="fe-ticker__lane">
            <span className="fe-ticker__fade fe-ticker__fade--l" data-on={edges.start} aria-hidden="true" />
            <span className="fe-ticker__fade fe-ticker__fade--r" data-on={edges.end} aria-hidden="true" />
            <div
              ref={scrollerRef}
              onScroll={measure}
              className="fe-ticker__scroll scrollbar-hide h-full w-full overflow-x-auto overscroll-x-contain"
              role="group"
              aria-label={t('ticker.quotes')}
            >
              <div className="flex h-full w-max min-w-full">
                <div className="fe-ticker__track mx-auto flex h-full items-center">
                  {snapshots.map((s) => (
                    <TickerCell key={s.code} snapshot={s} nowMs={dataUpdatedAt} />
                  ))}
                  {phone ? allLink : null}
                </div>
              </div>
            </div>
          </div>
          {phone ? null : allLink}
        </div>
      </div>
    </div>
  );
}
