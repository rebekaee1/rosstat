import { formatDate, formatValueWithUnit, unitSuffix, chartValueDigits } from '../lib/format';
import { useT } from '../i18n';
import '../styles/k5-pages.css';

export default function ForecastTable({ mode = 'inflation', inflation, forecastData, actualPoints, unit = '%', dateFormat = 'full' }) {
  const t = useT();

  // Все режимы, кроме скользящей 12-месячной инфляции, получают прогноз
  // готовым рядом (forecastData); inflation — отдельный сводный endpoint.
  const usesForecastData = mode !== 'inflation';
  const forecastRows = usesForecastData
    ? (forecastData?.forecast?.values || [])
    : (inflation?.forecast || []);
  const actualRows = usesForecastData ? actualPoints : inflation?.actuals;
  const lastActualDate = Array.isArray(actualRows)
    ? actualRows.reduce((latest, row) => row?.date > latest ? row.date : latest, '')
    : '';
  const lastActual = actualRows?.find((row) => row.date === lastActualDate);
  const revisesPartialActual = usesForecastData
    && forecastData?.forecast?.replaces_partial_actual === true;
  const rows = lastActualDate
    ? forecastRows.filter((row) => row.date > lastActualDate
      || (revisesPartialActual && row.date === lastActualDate
        && Math.abs(Number(row.value) - Number(lastActual?.value)) > 1e-4))
    : forecastRows;

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
    <div
      className="fe-reveal k5-table rounded-[2rem] overflow-hidden fe-glass-lite"
      style={{ '--fe-duration': '0.28s', '--fe-rise': '8px' }}
    >
      <div className="p-5 flex items-center justify-between flex-wrap gap-3">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
          {title}
        </h3>
      </div>

      <div className="overflow-x-auto scrollbar-hide">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th scope="col" className="text-left px-5 py-3 text-xs font-medium text-text-secondary uppercase tracking-wider">
                {t('forecast.asOf')}
              </th>
              <th scope="col" className="text-right px-5 py-3 text-xs font-medium text-text-secondary uppercase tracking-wider">
                {valueLabel}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.date} className="transition-colors">
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
