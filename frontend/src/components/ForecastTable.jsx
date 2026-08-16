import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { formatDate, formatValueWithUnit, unitSuffix, chartValueDigits } from '../lib/format';
import { useT } from '../i18n';

export default function ForecastTable({ mode = 'inflation', inflation, forecastData, unit = '%', dateFormat = 'full' }) {
  const t = useT();
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

  // Все режимы, кроме скользящей 12-месячной инфляции, получают прогноз
  // готовым рядом (forecastData); inflation — отдельный сводный endpoint.
  const usesForecastData = mode !== 'inflation';
  const rows = usesForecastData
    ? (forecastData?.forecast?.values || [])
    : (inflation?.forecast || []);

  if (!rows.length) return null;

  const periodKey = dateFormat === 'quarterly' ? 'forecast.period.quarterly'
    : dateFormat === 'annual' ? 'forecast.period.annual'
      : dateFormat === 'weekly' ? 'forecast.period.weekly'
        : 'forecast.period.monthly';
  const title = mode === 'inflation'
    ? t('forecast.title.inflation')
    : t('forecast.title.period', { period: t(periodKey) });
  const suffix = unitSuffix(unit);
  const valueDigits = chartValueDigits(unit, mode);
  const valueLabel = mode === 'inflation'
    ? t('forecast.value.inflation')
    : mode === 'quarterly' ? t('forecast.value.quarterly')
      : mode === 'annual' ? t('forecast.value.annual')
        : mode === 'weekly' ? t('forecast.value.weekly')
          : mode === 'index' ? t('forecast.value.index')
            : (suffix ? t('forecast.value.withUnit', { unit: suffix }) : t('forecast.value.generic'));

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
                {t('forecast.asOf')}
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
                  {formatValueWithUnit(row.value, unit, valueDigits)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
