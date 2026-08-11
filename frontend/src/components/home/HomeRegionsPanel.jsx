import { lazy, Suspense, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, MapPin } from 'lucide-react';
import {
  DEFAULT_HOME_REGION_METRIC,
  HOME_REGION_METRICS,
  heatmapNameBySlug,
  heatmapValuesBySlug,
  rankHeatmapValues,
} from '../../lib/homeWorkbench';
import { formatRegionValue, useRegionsHeatmap } from '../../lib/regionsApi';
import { SkeletonBox } from '../Skeleton';
import ApiRetryBanner from '../ApiRetryBanner';
import { track, events } from '../../lib/track';

const RegionsMap = lazy(() => import('../RegionsMap'));

export default function HomeRegionsPanel() {
  const navigate = useNavigate();
  const [metricCode, setMetricCode] = useState(DEFAULT_HOME_REGION_METRIC);
  const metric = HOME_REGION_METRICS.find((m) => m.code === metricCode) || HOME_REGION_METRICS[0];
  const heat = useRegionsHeatmap(metric.code, true);

  const ranking = useMemo(
    () => rankHeatmapValues(heat.data?.values, {
      betterIsLow: !!metric.betterIsLow,
      limit: 8,
    }),
    [heat.data, metric.betterIsLow],
  );
  const valuesBySlug = useMemo(() => heatmapValuesBySlug(heat.data), [heat.data]);
  const nameBySlug = useMemo(() => heatmapNameBySlug(heat.data), [heat.data]);
  const unit = heat.data?.indicator?.unit || '';
  const year = heat.data?.year;

  const onMetricChange = (code) => {
    setMetricCode(code);
    track(events.HOME_REGIONS_METRIC, { indicator: code });
  };

  return (
    <div data-block="home-workbench-regions">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-text-primary">Регионы России</h3>
          <p className="mt-1 max-w-xl text-xs leading-5 text-text-secondary">
            Компактный рейтинг субъектов и карта выбранного показателя.
            Полный каталог — в разделе регионов.
          </p>
        </div>
        <Link
          to="/regions"
          onClick={() => track(events.HOME_REGIONS_CTA, { target: 'regions' })}
          className="inline-flex items-center gap-1 text-xs text-champagne hover:underline"
        >
          <MapPin size={12} />
          Открыть регионы
          <ArrowRight size={12} />
        </Link>
      </div>

      <div className="mb-4 flex flex-wrap gap-1.5" role="group" aria-label="Показатель рейтинга">
        {HOME_REGION_METRICS.map((m) => (
          <button
            key={m.code}
            type="button"
            onClick={() => onMetricChange(m.code)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              m.code === metric.code
                ? 'bg-champagne/15 text-champagne'
                : 'border border-border-subtle bg-surface text-text-secondary hover:text-text-primary'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {heat.isError && (
        <ApiRetryBanner className="mb-4" onRetry={() => heat.refetch()} isFetching={heat.isFetching}>
          Не удалось загрузить рейтинг регионов.
        </ApiRetryBanner>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        {/* Mobile first: таблица/карточки выше карты */}
        <div className="order-1 rounded-2xl border border-border-subtle bg-surface p-4">
          <div className="mb-3 flex items-baseline justify-between gap-2">
            <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-champagne">
              Рейтинг
            </div>
            {year != null && (
              <div className="font-mono text-[10px] text-text-tertiary">{year} год</div>
            )}
          </div>
          {heat.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonBox key={i} className="h-8 rounded-lg" />
              ))}
            </div>
          ) : (
            <ol className="space-y-1">
              {ranking.map((row, index) => (
                <li key={row.slug}>
                  <Link
                    to={`/region/${row.slug}/${metric.code}`}
                    className="group flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-surface-hover"
                  >
                    <span className="w-5 font-mono text-[10px] text-text-tertiary">{index + 1}</span>
                    <span className="min-w-0 flex-1 truncate text-sm text-text-primary group-hover:text-champagne">
                      {row.name}
                    </span>
                    <span className="font-mono text-xs font-semibold tabular-nums text-text-primary">
                      {formatRegionValue(row.value)}
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
          <Link
            to={`/region-rating/${metric.code}`}
            onClick={() => track(events.HOME_REGIONS_CTA, { target: 'rating', indicator: metric.code })}
            className="mt-3 inline-flex items-center gap-1 text-xs text-champagne hover:underline"
          >
            Полный рейтинг
            <ArrowRight size={12} />
          </Link>
        </div>

        <div className="order-2 rounded-2xl border border-border-subtle bg-surface p-3 sm:p-4">
          {heat.isLoading ? (
            <SkeletonBox className="aspect-[4/3] w-full rounded-xl" />
          ) : (
            <Suspense fallback={<SkeletonBox className="aspect-[4/3] w-full rounded-xl" />}>
              <RegionsMap
                valuesBySlug={valuesBySlug}
                unit={unit}
                nameBySlug={nameBySlug}
                onSelect={(slug) => {
                  track(events.HOME_REGIONS_CTA, { target: 'map', region: slug, indicator: metric.code });
                  navigate(`/region/${slug}/${metric.code}`);
                }}
              />
            </Suspense>
          )}
        </div>
      </div>
    </div>
  );
}
