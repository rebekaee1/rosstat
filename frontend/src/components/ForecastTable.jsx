import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { formatDate } from '../lib/format';

export default function ForecastTable({ mode = 'inflation', inflation, forecastData }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(ref.current,
      { y: 20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.6, ease: 'power3.out', delay: 0.6 }
    );
  }, []);

  const isCpi = mode === 'cpi';
  const rows = isCpi
    ? (forecastData?.forecast?.values || [])
    : (inflation?.forecast || []);
  const modelName = isCpi
    ? forecastData?.forecast?.model_name
    : inflation?.model_name;

  if (!rows.length) return null;

  const title = isCpi ? 'Прогноз ИПЦ (помесячно)' : 'Прогноз инфляции (12 мес.)';
  const valueLabel = isCpi ? 'ИПЦ (%)' : 'Инфляция (12 мес.)';

  return (
    <div ref={ref} className="rounded-[2rem] bg-surface border border-border-subtle overflow-hidden">
      <div className="p-5 flex items-center justify-between flex-wrap gap-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          {title}
        </h3>
        {modelName && (
          <span className="text-xs font-mono text-text-tertiary px-2 py-1 rounded-md bg-obsidian-lighter border border-border-subtle">
            {modelName}
          </span>
        )}
      </div>

      <div className="overflow-x-auto scrollbar-hide">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-t border-border-subtle">
              <th className="text-left px-5 py-3 text-xs font-medium text-text-tertiary uppercase tracking-wider">
                На дату
              </th>
              <th className="text-right px-5 py-3 text-xs font-medium text-text-tertiary uppercase tracking-wider">
                {valueLabel}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.date} className="border-t border-border-subtle hover:bg-surface-hover transition-colors">
                <td className="px-5 py-2.5 text-text-secondary font-mono text-xs">
                  {formatDate(row.date, 'full')}
                </td>
                <td className="px-5 py-2.5 text-right font-mono font-medium text-champagne">
                  {row.value?.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
