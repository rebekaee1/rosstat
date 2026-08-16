import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { cn } from '../lib/format';
import {
  russiaIndicatorPath,
} from '../lib/sitePaths';

/**
 * Мета ленты. linkTo — только если ведёт на ту же карточку/ряд, что и число.
 * Нет карточки → linkTo: null (не кликаем на чужой показатель).
 */
const TICKER_META = {
  'usd-rub-live':  { label: 'USD/RUB', linkTo: russiaIndicatorPath('usd-rub'), decimals: 4 },
  'eur-rub-live':  { label: 'EUR/RUB', linkTo: russiaIndicatorPath('eur-rub'), decimals: 4 },
  'cny-rub-live':  { label: 'CNY/RUB', linkTo: russiaIndicatorPath('cny-rub'), decimals: 4 },
  'btc-usd':       { label: 'BTC/USD', linkTo: russiaIndicatorPath('btc-usd'), decimals: 0 },
  'brent':         { label: 'Brent',   linkTo: russiaIndicatorPath('brent'),   decimals: 2 },
  'gold-rub-live': { label: 'Золото',  linkTo: russiaIndicatorPath('gold-price'), decimals: 1 },
};

const POLL_INTERVAL_MS = 4000;

function formatPrice(value, decimals) {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('ru-RU', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatPct(pct) {
  if (pct === null || pct === undefined) return '—';
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(2).replace('.', ',')}%`;
}

/** Компактная дата значения для не-внутридневных элементов: «15.08». */
function formatAsOfShort(isoDate) {
  if (!isoDate) return null;
  const d = isoDate.includes('T')
    ? new Date(isoDate)
    : new Date(`${isoDate}T12:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  // Для ISO-даты ряда — календарный день как есть; для timestamp — МСК.
  if (!isoDate.includes('T')) {
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    return `${dd}.${mm}`;
  }
  return d.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    timeZone: 'Europe/Moscow',
  });
}

function formatAsOfTitle(isoDate) {
  if (!isoDate) return null;
  const d = isoDate.includes('T')
    ? new Date(isoDate)
    : new Date(`${isoDate}T12:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: isoDate.includes('T') ? 'Europe/Moscow' : undefined,
  });
}

function resolveAsOfRaw(snapshot) {
  if (snapshot.as_of_date) return snapshot.as_of_date;
  if (snapshot.fetched_at) return snapshot.fetched_at;
  return null;
}

function TickerCell({ snapshot, nowMs }) {
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
    const t = setTimeout(() => setFlash(null), 600);
    return () => clearTimeout(t);
  }, [flash]);

  if (!meta) return null;

  const pct = snapshot.change_pct;
  const positive = pct !== null && pct !== undefined && pct > 0;
  const negative = pct !== null && pct !== undefined && pct < 0;
  const hasPrice = snapshot.price > 0;

  const fetchedMs = snapshot.fetched_at ? new Date(snapshot.fetched_at).getTime() : null;
  const isStale = isIntraday && fetchedMs !== null && nowMs - fetchedMs > 15 * 60 * 1000;
  const asOfRaw = !isIntraday ? resolveAsOfRaw(snapshot) : null;
  const asOfShort = formatAsOfShort(asOfRaw);
  const asOfTitle = formatAsOfTitle(asOfRaw);
  const asOfClock = fetchedMs !== null
    ? new Date(fetchedMs).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' })
    : null;

  const titleParts = [`Источник: ${snapshot.source}`];
  if (!isIntraday) {
    if (asOfTitle) titleParts.push(`значение на ${asOfTitle}`);
  } else {
    if (!snapshot.market_open) titleParts.push('торги закрыты');
    if (asOfClock) {
      titleParts.push(
        isStale
          ? `данные на ${asOfClock} МСК (обновление недоступно)`
          : `данные на ${asOfClock} МСК`,
      );
    }
  }

  const cellClass = cn(
    'flex shrink-0 items-center gap-1 px-1.5 py-1 rounded-md whitespace-nowrap',
    'sm:gap-1.5 sm:px-2.5 md:gap-2 md:px-3',
    'transition-colors duration-200',
    meta.linkTo && 'hover:bg-champagne/10',
    'border border-transparent',
    flash === 'up' && 'bg-positive/10 border-positive/30',
    flash === 'down' && 'bg-negative/10 border-negative/30',
    isStale && 'opacity-60',
  );

  const body = (
    <>
      <span className="text-[9px] uppercase tracking-wide text-text-secondary font-medium sm:text-[11px]">
        {meta.label}
      </span>
      <span className="text-xs font-semibold tabular-nums text-text-primary sm:text-sm">
        {hasPrice ? formatPrice(snapshot.price, meta.decimals) : '—'}
      </span>
      {asOfShort ? (
        <span className="text-[9px] font-mono tabular-nums text-text-tertiary sm:text-[10px]">
          {asOfShort}
        </span>
      ) : null}
      <span className={cn(
        'hidden text-[11px] font-medium tabular-nums xl:inline',
        positive && 'text-positive',
        negative && 'text-negative',
        !positive && !negative && 'text-text-secondary'
      )}>
        {formatPct(pct)}
      </span>
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

async function fetchLiveTicker() {
  const r = await fetch('/api/v1/ticker/live', { cache: 'no-store' });
  if (!r.ok) throw new Error(`Live ticker: HTTP ${r.status}`);
  return r.json();
}

export default function LiveTicker() {
  // Тикер на всех ширинах: на мобиле — компактный ряд со скроллом,
  // на широких — полная строка. justify-center на узкой ширине обрезает края.
  const { data, dataUpdatedAt } = useQuery({
    queryKey: ['ticker', 'live'],
    queryFn: fetchLiveTicker,
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
    staleTime: 0,
  });

  const snapshots = data?.snapshots || [];
  if (snapshots.length === 0) {
    return (
      <div className="fixed top-0 inset-x-0 z-[110] h-9 bg-[#faf7f0] border-b border-champagne/15" />
    );
  }

  return (
    <div className="fixed top-0 inset-x-0 z-[110] h-9 bg-[#faf7f0] border-b border-champagne/15 shadow-sm">
      <div className="mx-auto h-full max-w-7xl px-1 sm:px-3 md:px-4">
        <div
          className="scrollbar-hide flex h-full w-full items-center gap-0.5 overflow-x-auto sm:gap-1 md:gap-1.5 xl:justify-center xl:gap-3"
          aria-label="Котировки"
        >
          {snapshots.map((s) => (
            <TickerCell key={s.code} snapshot={s} nowMs={dataUpdatedAt} />
          ))}
        </div>
      </div>
    </div>
  );
}
