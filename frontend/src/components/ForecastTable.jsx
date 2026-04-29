import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { formatDate, formatValueWithUnit, unitSuffix } from '../lib/format';

export default function ForecastTable({ mode = 'inflation', inflation, forecastData, unit = '%', dateFormat = 'full' }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tween = gsap.fromTo(ref.current,
      { y: 20, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.6, ease: 'power3.out', delay: 0.6 }
    );
    return () => tween.kill();
  }, []);

  const usesForecastData = mode === 'cpi' || mode === 'quarterly' || mode === 'annual';
  const rows = usesForecastData
    ? (forecastData?.forecast?.values || [])
    : (inflation?.forecast || []);

  if (!rows.length) return null;

  const period = dateFormat === 'quarterly' ? 'ежеквартально' : dateFormat === 'annual' ? 'ежегодно' : 'помесячно';
  const title = mode === 'inflation' ? 'Прогноз инфляции (12 мес.)' : `Прогноз (${period})`;
  const suffix = unitSuffix(unit);
  const valueLabel = mode === 'inflation'
    ? 'Инфляция (12 мес.)'
    : (mode === 'quarterly' ? 'Квартальная (%)' : mode === 'annual' ? 'Годовая (%)' : (suffix ? `Значение (${suffix})` : 'Значение'));

  return (
    <div ref={ref} className="rounded-[2rem] bg-surface border border-border-subtle overflow-hidden">
      <div className="p-5 flex items-center justify-between flex-wrap gap-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          {title}
        </h3>
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
                  {formatDate(row.date, dateFormat)}
                </td>
                <td className="px-5 py-2.5 text-right font-mono font-medium text-champagne">
                  {formatValueWithUnit(row.value, unit)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
