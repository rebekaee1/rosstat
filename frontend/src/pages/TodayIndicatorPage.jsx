import { useMemo } from 'react';
import { Link, useParams, Navigate } from 'react-router-dom';
import { ChevronRight, ArrowRight, TrendingUp, TrendingDown } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { getTodaySpec, todaySeriesCode } from '../lib/todaySpecs';
import { formatValue, formatDate, formatChange, unitSuffix } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import IndicatorChart from '../components/IndicatorChart';
import { SkeletonBox } from '../components/Skeleton';

const MONTHS_GEN = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

function ruDate(d = new Date()) {
  return `${d.getDate()} ${MONTHS_GEN[d.getMonth()]} ${d.getFullYear()} года`;
}

function ruDateShort(iso) {
  if (!iso) return '';
  const [y, m, day] = iso.split('-');
  return `${day}.${m}.${y}`;
}

function rangePreset(frequency) {
  if (frequency === 'daily') return 'daily';
  if (frequency === 'weekly') return 'weekly';
  if (frequency === 'quarterly') return 'quarterly';
  if (frequency === 'annual') return 'annual';
  return 'default';
}

export default function TodayIndicatorPage() {
  const { code } = useParams();
  const spec = getTodaySpec(code);
  const seriesCode = todaySeriesCode(code);

  const { data: indicator, isLoading: loadingMeta, isError: metaError, refetch: refetchMeta, isFetching: fetchingMeta } = useIndicator(seriesCode);
  const { data: rowsResp, isLoading: loadingData, isError: dataError, refetch: refetchData, isFetching: fetchingData } = useIndicatorData(seriesCode, { limit: 60 });

  const points = rowsResp?.data || [];
  const last = points[points.length - 1];
  const prev = points.length > 1 ? points[points.length - 2] : null;

  const chartPoints = useMemo(
    () => points.map((p) => ({ date: p.date, value: p.value })),
    [points],
  );

  const stats = useMemo(() => {
    if (!points.length) return null;
    const values = points.map((p) => p.value);
    return {
      min: Math.min(...values),
      max: Math.max(...values),
      change: prev ? last.value - prev.value : null,
    };
  }, [points, last, prev]);

  const freq = indicator?.frequency || 'monthly';
  const dateFmt = freq === 'daily' ? 'full' : freq === 'monthly' ? 'monthly' : 'full';

  useDocumentMeta(spec && last ? {
    title: `${spec.query} сегодня, ${ruDate()} — ${formatValue(last.value)} ${indicator?.unit || ''}`.trim(),
    description:
      `${spec.query} на сегодня: ${formatValue(last.value)} ${indicator?.unit || ''} `
      + `(данные на ${formatDate(last.date, dateFmt)}). Источник — ${indicator?.source}. `
      + 'График, таблица последних значений и прогноз.',
    path: `/today/${code}`,
  } : null);

  if (!spec) return <Navigate to="/today" replace />;

  const isError = metaError || dataError;
  const isLoading = loadingMeta || loadingData;
  const refetch = () => { refetchMeta(); refetchData(); };
  const isFetching = fetchingMeta || fetchingData;

  return (
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      <nav className="flex items-center gap-1.5 text-xs text-text-tertiary mb-4 overflow-hidden" aria-label="Хлебные крошки">
        <Link to="/" className="hover:text-champagne transition-colors shrink-0">Главная</Link>
        <ChevronRight size={12} className="shrink-0" />
        <Link to="/today" className="hover:text-champagne transition-colors shrink-0">Сегодня</Link>
        <ChevronRight size={12} className="shrink-0" />
        <span className="text-text-secondary truncate">{spec.query}</span>
      </nav>

      {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}

      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-10 w-80 max-w-full" />
          <SkeletonBox className="h-72 rounded-xl" />
        </div>
      )}

      {!isLoading && last && indicator && (
        <>
          <p className="text-champagne text-xs font-mono uppercase tracking-widest mb-2">
            Показатель на сегодня
          </p>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary mb-4">
            {spec.query} сегодня
          </h1>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <div className="bg-surface border border-border-subtle rounded-xl p-3.5 col-span-2 lg:col-span-1">
              <div className="text-[11px] text-text-tertiary uppercase tracking-wide">Сейчас</div>
              <div className="mt-1 font-mono text-2xl font-bold text-text-primary">
                {formatValue(last.value)}
                <span className="ml-1 text-sm font-normal text-text-secondary">{unitSuffix(indicator.unit)}</span>
              </div>
              <div className="mt-1 text-[11px] text-text-tertiary">{formatDate(last.date, dateFmt)}</div>
            </div>
            {prev && (
              <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
                <div className="text-[11px] text-text-tertiary uppercase tracking-wide">Предыдущее</div>
                <div className="mt-1 font-mono font-semibold text-text-primary">{formatValue(prev.value)}</div>
              </div>
            )}
            {stats && (
              <>
                <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
                  <div className="text-[11px] text-text-tertiary uppercase tracking-wide">Минимум</div>
                  <div className="mt-1 font-mono font-semibold text-text-primary">{formatValue(stats.min)}</div>
                </div>
                <div className="bg-surface border border-border-subtle rounded-xl p-3.5">
                  <div className="text-[11px] text-text-tertiary uppercase tracking-wide">Максимум</div>
                  <div className="mt-1 font-mono font-semibold text-text-primary">{formatValue(stats.max)}</div>
                </div>
              </>
            )}
          </div>

          {stats?.change != null && Math.abs(stats.change) >= 1e-12 && (
            <div className={`inline-flex items-center gap-1.5 text-sm font-mono mb-4 ${stats.change > 0 ? 'text-positive' : 'text-negative'}`}>
              {stats.change > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              {formatChange(stats.change, indicator.unit)} к предыдущему значению
            </div>
          )}

          <div className="bg-surface border border-border-subtle rounded-xl p-4 mb-6">
            <IndicatorChart
              mode="cpi"
              cpiData={chartPoints}
              showForecast={false}
              unit={indicator.unit || ''}
              rangePreset={rangePreset(freq)}
              chartMode="level"
              indicatorCode={seriesCode}
              indicatorCategory={indicator.category}
              defaultChartType="area"
              cpiChartTitle={`${spec.query} — динамика`}
            />
            <p className="mt-2 text-[11px] text-text-tertiary font-mono">
              Источник: {indicator.source}
            </p>
          </div>

          <Link
            to={`/indicator/${spec.code}`}
            className="inline-flex items-center gap-2 mb-8 px-4 py-2.5 rounded-xl bg-champagne/10 text-champagne font-medium hover:bg-champagne/20 transition-colors"
          >
            Интерактивный график и прогноз
            <ArrowRight size={16} />
          </Link>

          <section className="mb-8">
            <h2 className="font-display text-lg font-semibold text-text-primary mb-3">Последние значения</h2>
            <div className="overflow-x-auto rounded-xl border border-border-subtle">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-obsidian-light/50 text-left text-[11px] uppercase tracking-wide text-text-tertiary">
                    <th className="px-4 py-2.5 font-medium">Дата</th>
                    <th className="px-4 py-2.5 font-medium">{indicator.unit || 'Значение'}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...points].reverse().slice(0, 15).map((row) => (
                    <tr key={row.date} className="border-t border-border-subtle font-mono">
                      <td className="px-4 py-2 text-text-secondary">{ruDateShort(row.date)}</td>
                      <td className="px-4 py-2 text-text-primary">{formatValue(row.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="bg-surface border border-border-subtle rounded-xl p-5">
            <h2 className="font-display text-base font-semibold text-text-primary mb-2">Полная история и прогноз</h2>
            <p className="text-sm text-text-secondary">
              Интерактивный график с историей с первого доступного года, режимы представления и прогноз — на странице{' '}
              <Link to={`/indicator/${spec.code}`} className="text-champagne hover:underline">{indicator.name}</Link>.
            </p>
          </section>
        </>
      )}
    </div>
  );
}
