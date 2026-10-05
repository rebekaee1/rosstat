import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { cn } from '../lib/format';
import DeltaBadge from './DeltaBadge';
import { russiaIndicatorPath } from '../lib/sitePaths';
import { tickerLaneForLocale } from '../lib/tickerLane';
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
  'usd-rub-live':  { label: 'USD/RUB', linkTo: russiaIndicatorPath('usd-rub'), decimals: 2 },
  'eur-rub-live':  { label: 'EUR/RUB', linkTo: russiaIndicatorPath('eur-rub'), decimals: 2 },
  'cny-rub-live':  { label: 'CNY/RUB', linkTo: russiaIndicatorPath('cny-rub'), decimals: 2 },
  'eur-usd':       { label: 'EUR/USD', linkTo: russiaIndicatorPath('eur-usd'), decimals: 2 },
  'gbp-usd':       { label: 'GBP/USD', linkTo: russiaIndicatorPath('gbp-usd'), decimals: 2 },
  'usd-cny':       { label: 'USD/CNY', linkTo: russiaIndicatorPath('usd-cny'), decimals: 2 },
  'btc-usd':       { label: 'BTC/USD', linkTo: russiaIndicatorPath('btc-usd'), decimals: 0 },
  'brent':         { label: 'Brent',   linkTo: russiaIndicatorPath('brent'),   decimals: 2 },
  'gold-rub-live': { labelKey: 'ticker.gold', linkTo: russiaIndicatorPath('gold-price'), decimals: 0 },
};

function formatPrice(value, decimals, locale = 'ru') {
  if (value === null || value === undefined) return '—';
  const tag = locale === 'en' ? 'en-US' : 'ru-RU';
  return value.toLocaleString(tag, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatPct(pct, locale = 'ru') {
  if (pct === null || pct === undefined) return '—';
  const sign = pct > 0 ? '+' : '';
  const tag = locale === 'en' ? 'en-US' : 'ru-RU';
  const body = Math.abs(pct).toLocaleString(tag, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  // Keep explicit sign; toLocaleString may omit '+' for positives.
  if (pct < 0) return `\u2212${body}%`;
  return `${sign}${body}%`;
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

  const body = (
    <>
      <span className="text-xs font-medium text-text-secondary">
        {meta.labelKey ? t(meta.labelKey) : meta.label}
      </span>
      <span className="text-sm font-semibold tabular-nums text-text-primary">
        {hasPrice ? formatPrice(snapshot.price, meta.decimals, locale) : '—'}
      </span>
      {sourceKind ? (
        <span className="text-xs text-text-secondary">{t(`shell.ticker.source.${sourceKind}`)}</span>
      ) : null}
      {asOfHuman ? (
        <span className="text-xs text-text-secondary">{t('shell.ticker.asOf', { date: asOfHuman })}</span>
      ) : null}
      {pct !== null && pct !== undefined && Math.abs(pct) >= 0.005 ? (
        <DeltaBadge delta={pct} className="hidden text-xs xl:inline-flex">
          {formatPct(pct, locale)}
        </DeltaBadge>
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
 * Две липкие плашки (бегущая строка и шапка) съедали ~110 px телефона. При прокрутке вниз строка уходит вверх,
 * шапка поднимается на её место; при прокрутке вверх или у начала страницы всё возвращается.
 * Состояние — атрибут на <html>, его читают стили в styles/shell.css.
 */
function useHideOnScroll() {
  useEffect(() => {
    const root = document.documentElement;
    let lastY = window.scrollY;
    let frame = 0;
    const apply = () => {
      frame = 0;
      const y = window.scrollY;
      const delta = y - lastY;
      if (y < 48 || delta < -6) root.dataset.feTicker = 'shown';
      else if (delta > 6 && y > 96) root.dataset.feTicker = 'hidden';
      if (Math.abs(delta) > 6) lastY = y;
    };
    const onScroll = () => { if (!frame) frame = window.requestAnimationFrame(apply); };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.cancelAnimationFrame(frame);
      delete root.dataset.feTicker;
    };
  }, []);
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
  useHideOnScroll();
  const t = useT();
  const { locale } = useLocale();
  const lane = tickerLaneForLocale(locale);
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
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
