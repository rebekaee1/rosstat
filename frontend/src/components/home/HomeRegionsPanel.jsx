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
import {
  regionHubPath,
  regionIndicatorPath,
  regionRatingPath,
} from '../../lib/sitePaths';
import { useT } from '../../i18n';

const RegionsMap = lazy(() => import('../RegionsMap'));

export default function HomeRegionsPanel() {
  const t = useT();
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
          <h3 className="text-base font-semibold text-text-primary">{t('home.regions.title')}</h3>
          <p className="mt-1 max-w-xl text-xs leading-5 text-text-secondary">
            {t('home.regions.subtitle')}
          </p>
        </div>
        <Link
          to={regionHubPath()}
          onClick={() => track(events.HOME_REGIONS_CTA, { target: 'regions' })}
          className="inline-flex items-center gap-1 text-xs text-champagne hover:underline"
        >
          <MapPin size={12} />
          {t('home.regions.open')}
          <ArrowRight size={12} />
        </Link>
      </div>

      <div className="mb-4 flex flex-wrap gap-1.5" role="group" aria-label={t('home.regions.metricAria')}>
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
            {t(m.labelKey)}
          </button>
        ))}
      </div>

      {heat.isError && (
        <ApiRetryBanner className="mb-4" onRetry={() => heat.refetch()} isFetching={heat.isFetching}>
          {t('home.regions.loadError')}
        </ApiRetryBanner>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div className="order-1 rounded-2xl border border-border-subtle bg-surface p-4">
          <div className="mb-3 flex items-baseline justify-between gap-2">
            <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-champagne">
              {t('home.map.rating')}
            </div>
            {year != null && (
              <div className="font-mono text-[10px] text-text-tertiary">
                {t('world.yearLabel', { year })}
              </div>
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
                    to={regionIndicatorPath(row.slug, metric.code)}
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
            to={regionRatingPath(metric.code)}
            onClick={() => track(events.HOME_REGIONS_CTA, { target: 'rating', indicator: metric.code })}
            className="mt-3 inline-flex items-center gap-1 text-xs text-champagne hover:underline"
          >
            {t('home.map.fullRating')}
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
                  navigate(regionIndicatorPath(slug, metric.code));
                }}
              />
            </Suspense>
          )}
        </div>
      </div>
    </div>
  );
}
