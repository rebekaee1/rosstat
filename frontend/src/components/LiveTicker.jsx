import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { formatValue } from '../lib/format';

/**
 * Live ticker (правка D4 из звонка 2026-05-21).
 *
 * Тонкая горизонтальная лента над основным контентом главной страницы.
 * Показывает текущие значения и абсолютную дельту для:
 *   - 3 валюты (USD/EUR/CNY к рублю — daily, обновляются ЦБ ежедневно)
 *   - ключевая ставка ЦБ
 *   - RUONIA
 *   - цена золота ЦБ
 *
 * Источник — общий React-Query кэш `useIndicators()`, без отдельного
 * polling-API. Refresh происходит при обновлении кэша (по умолчанию раз
 * в 5 минут). Если индикатор временно недоступен — строка просто
 * пропускается.
 *
 * MVP: без crypto/Brent/IMOEX — это в C4/future (нужен отдельный
 * парсер MOEX ISS + CoinGecko). Лента — sticky-blok сверху, не sticky
 * через viewport, чтобы не перекрывать контент при скролле.
 */
const TICKER_CODES = [
  { code: 'usd-rub', label: 'USD/RUB' },
  { code: 'eur-rub', label: 'EUR/RUB' },
  { code: 'cny-rub', label: 'CNY/RUB' },
  { code: 'key-rate', label: 'Ключевая' },
  { code: 'ruonia', label: 'RUONIA' },
  { code: 'gold-price', label: 'Золото' },
];

function deltaIcon(change) {
  if (change == null || change === 0) return <Minus className="w-3 h-3" />;
  return change > 0
    ? <TrendingUp className="w-3 h-3 text-positive" />
    : <TrendingDown className="w-3 h-3 text-negative" />;
}

function deltaTextClass(change) {
  if (change == null || change === 0) return 'text-text-tertiary';
  return change > 0 ? 'text-positive' : 'text-negative';
}

export default function LiveTicker() {
  const { data: indicators = [], isLoading } = useIndicators();

  const items = useMemo(() => {
    const byCode = new Map(indicators.map((i) => [i.code, i]));
    return TICKER_CODES
      .map((meta) => {
        const ind = byCode.get(meta.code);
        if (!ind || ind.current_value == null) return null;
        return {
          ...meta,
          value: ind.current_value,
          change: ind.change,
          unit: ind.unit,
        };
      })
      .filter(Boolean);
  }, [indicators]);

  if (isLoading || items.length === 0) return null;

  return (
    <div className="w-full border-b border-border-subtle bg-obsidian-light/40 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-4 overflow-x-auto">
        <div className="flex items-center gap-6 py-2 text-xs whitespace-nowrap">
          <span className="text-[10px] uppercase tracking-[0.2em] font-mono text-text-tertiary shrink-0">
            Котировки
          </span>
          {items.map((it) => (
            <Link
              key={it.code}
              to={`/indicator/${it.code}`}
              className="flex items-center gap-2 shrink-0 hover:text-champagne transition-colors group"
            >
              <span className="text-text-tertiary group-hover:text-text-secondary transition-colors font-mono text-[10px] uppercase tracking-wider">
                {it.label}
              </span>
              <span className="font-mono text-text-primary tabular-nums">
                {formatValue(it.value, it.unit === 'руб./г' ? 0 : 2)}
              </span>
              <span className={`flex items-center gap-0.5 font-mono text-[10px] ${deltaTextClass(it.change)}`}>
                {deltaIcon(it.change)}
                {it.change != null && (
                  <span className="tabular-nums">
                    {it.change > 0 ? '+' : ''}{formatValue(it.change, 2)}
                  </span>
                )}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
