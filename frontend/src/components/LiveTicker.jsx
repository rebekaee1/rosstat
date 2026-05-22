import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { cn } from '../lib/format';

const TICKER_META = {
  'usd-rub-live':  { label: 'USD/RUB', linkTo: '/indicator/usd-rub', decimals: 4 },
  'eur-rub-live':  { label: 'EUR/RUB', linkTo: '/indicator/eur-rub', decimals: 4 },
  'cny-rub-live':  { label: 'CNY/RUB', linkTo: '/indicator/cny-rub', decimals: 4 },
  'btc-usd':       { label: 'BTC/USD', linkTo: '/indicator/btc-usd', decimals: 0 },
  'brent':         { label: 'Brent',   linkTo: '/indicator/brent',   decimals: 2 },
};

const POLL_INTERVAL_MS = 4000;

function formatPrice(value, decimals) {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('ru-RU', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatPct(pct) {
  if (pct === null || pct === undefined) return '—';
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
}

function TickerCell({ snapshot }) {
  // Хуки должны вызываться в стабильном порядке на каждом рендере (React rules-of-hooks);
  // ранний return ставим **после** объявления хуков, иначе ESLint roof-of-hooks ошибка.
  const meta = TICKER_META[snapshot.code];

  // Flash-эффект на изменение цены (зелёное/красное подсвечивание на 600мс).
  // Pattern: сравниваем входящую цену с «последней увиденной» через useState,
  // чтобы соблюсти оба правила (react-hooks/refs запрещает ref-in-render;
  // react-hooks/set-state-in-effect запрещает setState в useEffect).
  // setState вызывается **во время render**, что разрешено когда новое значение
  // зависит от prop (React сам ребатчит ререндер) — это документированный
  // pattern «Adjusting state in response to a prop change», см.
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-state-when-a-prop-changes
  const [lastSeenPrice, setLastSeenPrice] = useState(snapshot.price);
  const [flash, setFlash] = useState(null); // 'up' | 'down' | null
  if (lastSeenPrice !== snapshot.price) {
    setFlash(snapshot.price > lastSeenPrice ? 'up' : 'down');
    setLastSeenPrice(snapshot.price);
  }
  useEffect(() => {
    if (!flash) return undefined;
    const t = setTimeout(() => setFlash(null), 600);
    return () => clearTimeout(t);
  }, [flash]);

  if (!meta) return null;

  // Визуально лента — единая строка котировок. Источник (MOEX live vs ЦБ daily)
  // не должен ломать типографику: цвет/жирность цены идентичны для всех
  // инструментов. Различие источника — только в title-тултипе.
  const pct = snapshot.change_pct;
  const positive = pct !== null && pct !== undefined && pct > 0;
  const negative = pct !== null && pct !== undefined && pct < 0;
  const hasPrice = snapshot.price > 0;

  return (
    <Link
      to={meta.linkTo}
      className={cn(
        'flex items-center gap-2 px-3 py-1 rounded-md shrink-0 whitespace-nowrap',
        'transition-colors duration-200 hover:bg-champagne/10',
        'border border-transparent',
        flash === 'up' && 'bg-positive/10 border-positive/30',
        flash === 'down' && 'bg-negative/10 border-negative/30',
      )}
      title={snapshot.market_open ? `Источник: ${snapshot.source}` : `Источник: ${snapshot.source} (торги закрыты)`}
    >
      <span className="text-[11px] uppercase tracking-wide text-text-secondary font-medium">
        {meta.label}
      </span>
      <span className="text-sm font-semibold tabular-nums text-text-primary">
        {hasPrice ? formatPrice(snapshot.price, meta.decimals) : '—'}
      </span>
      <span className={cn(
        'text-[11px] font-medium tabular-nums',
        positive && 'text-positive',
        negative && 'text-negative',
        !positive && !negative && 'text-text-secondary'
      )}>
        {formatPct(pct)}
      </span>
    </Link>
  );
}

async function fetchLiveTicker() {
  const r = await fetch('/api/v1/ticker/live', { cache: 'no-store' });
  if (!r.ok) throw new Error(`Live ticker: HTTP ${r.status}`);
  return r.json();
}

export default function LiveTicker() {
  const { data } = useQuery({
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
      <div className="max-w-7xl mx-auto h-full px-4 flex items-center overflow-x-auto scrollbar-hide">
        <div className="flex items-center gap-1 w-full justify-between md:justify-start md:gap-3">
          {snapshots.map((s) => (
            <TickerCell key={s.code} snapshot={s} />
          ))}
        </div>
      </div>
    </div>
  );
}
