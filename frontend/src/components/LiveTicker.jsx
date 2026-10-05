import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useLocation } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '../lib/format';
import { russiaCategoryPath, russiaIndicatorPath } from '../lib/sitePaths';
import { tickerLaneFor } from '../lib/tickerLane';
import { tickerRefetchInterval } from '../lib/tickerPoll';
import { formatAsOfHuman, tickerSourceKind, tzFor } from '../lib/tickerFormat';
import { useLocale, useT } from '../i18n';
import '../styles/shell.css';
import '../styles/platform-pages.css';

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

/** Изменение за день: «0,1 %» без знака (направление показывает стрелка рядом), один знак после запятой. */
function formatPct(pct, locale = 'ru') {
  if (pct === null || pct === undefined) return '\u2014';
  const tag = locale === 'en' ? 'en-US' : 'ru-RU';
  const body = Math.abs(pct).toLocaleString(tag, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return locale === 'en' ? `${body}%` : `${body}\u00a0%`;
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

  const titleParts = [t('ticker.source', { source: snapshot.source })];
  // Слова «биржа» и «ЦБ» не занимают места в строке, но остаются в подсказке.
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

  const cellClass = cn(
    'flex h-full min-h-7 shrink-0 items-center gap-1 px-1.5 rounded-md whitespace-nowrap',
    'sm:gap-1.5 sm:px-2.5 md:gap-2 md:px-3',
    'transition-colors duration-200',
    meta.linkTo && 'hover:bg-champagne/10',
    'border border-transparent',
    // Вспышка нового тика нейтральная: рост курса не «хорошо» и не «плохо», цвет не должен оценивать.
    flash && 'bg-champagne/15 border-champagne/30',
    isStale && 'opacity-60',
  );

  // У пары «доллар к юаню» по-английски подпись «USD/CNY» сама говорит, что это за число: знак ¥ рядом
  // читался как «доллар к иене».
  const sign = (meta.pairLabel && locale === 'en') ? '' : (CURRENCY_SIGN[meta.cur] || '');
  // По-русски знак валюты после числа («85,79 ₽»), по-английски перед («$1.12»).
  const signFirst = locale === 'en' && meta.cur !== 'rub';
  const showPct = pct !== null && pct !== undefined && Math.abs(pct) >= 0.05;
  const body = (
    <>
      <span className="text-xs font-medium text-text-secondary">{t(meta.nameKey)}</span>
      <span className="text-sm font-semibold tabular-nums text-text-primary">
        {signFirst && hasPrice ? <span className="fe-ticker__sign">{sign}</span> : null}
        <span>{hasPrice ? formatPrice(snapshot.price, meta.decimals, locale) : '\u2014'}</span>
        {!signFirst && hasPrice && sign ? <span className="fe-ticker__sign">{`\u00a0${sign}${meta.perGram ? t('w6b.ticker.perGram') : ''}`}</span> : null}
      </span>
      {asOfHuman ? (
        <span className="text-xs text-text-secondary">{t('shell.ticker.asOf', { date: asOfHuman })}</span>
      ) : null}
      {showPct ? (
        <span className="fe-ticker__delta tabular-nums">
          <span aria-hidden="true">{pct > 0 ? '\u25B2' : '\u25BC'}</span>
          <span className="sr-only">{pct > 0 ? t('w6b.ticker.up') : t('w6b.ticker.down')}</span>
          {formatPct(pct, locale)}
        </span>
      ) : null}
    </>
  );

  if (meta.linkTo) {
    return (
      <Link to={meta.linkTo} className={cellClass} title={titleParts.join(' — ')}>
        {body}
      </Link>
    );
  }

  return (
    <span className={cellClass} title={titleParts.join(' — ')}>
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
  const [edges, setEdges] = useState({ start: false, end: false });
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
    el.addEventListener('pointerdown', cancel, { passive: true });
    el.addEventListener('wheel', cancel, { passive: true });
    return () => {
      cancel();
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', measure);
      observer?.disconnect();
      el.removeEventListener('pointerdown', cancel);
      el.removeEventListener('wheel', cancel);
    };
  }, [measure, dep]);
  return { ref, edges, measure };
}

export default function LiveTicker() {
  const t = useT();
  const { locale } = useLocale();
  const { pathname } = useLocation();
  const lane = tickerLaneFor(locale, pathname);
  const { data, dataUpdatedAt } = useQuery({
    queryKey: ['ticker', 'live', lane],
    queryFn: () => fetchLiveTicker(lane),
    retry: false,
    refetchInterval: tickerRefetchInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: false,
    staleTime: 0,
  });

  const snapshots = data?.snapshots || [];
  const { ref: scrollerRef, edges, measure } = useEdgeFade(snapshots.length);
  if (snapshots.length === 0) {
    return (
      <div className="fe-ticker fixed top-0 inset-x-0 z-[110] h-9 bg-warn-surface border-b border-champagne/15" />
    );
  }

  return (
    <div
      className="fe-ticker fixed top-0 inset-x-0 z-[110] h-9 bg-warn-surface border-b border-champagne/15 shadow-sm pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)]"
    >
      <div className="mx-auto h-full max-w-7xl">
        <div className="fe-ticker__scroller">
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
              <div className="mx-auto flex h-full items-center gap-0.5 pl-3 pr-8 sm:gap-1 sm:px-3 md:gap-1.5 md:px-4 xl:gap-3">
                {snapshots.map((s) => (
                  <TickerCell key={s.code} snapshot={s} nowMs={dataUpdatedAt} />
                ))}
                <Link
                  to={currenciesPath()}
                  className="flex h-full min-h-7 shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-2 text-xs font-medium text-champagne-ink hover:bg-champagne/10 sm:px-3"
                >
                  {t('w6b.ticker.all')}
                  <ChevronRight size={12} aria-hidden="true" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
