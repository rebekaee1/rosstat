// Хаб субнациональных регионов: /{country}/regions
import { useMemo, lazy, Suspense, useEffect } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useWorldRegionsHub,
  useWorldRegionsMap,
  formatSubnationalValue,
} from '../lib/worldSubnationalApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { worldSubnationalHubTrail } from '../lib/breadcrumbs';
import {
  RUSSIA,
  countryRegionPath,
  countryRegionsPath,
  countryRegionMapPath,
  regionHubPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';
import usStatesMap from '../lib/usStatesMap.json';

const RegionsMap = lazy(() => import('../components/RegionsMap'));

const MAPS = {
  'us-states': usStatesMap,
};

export default function WorldRegionsHome() {
  const { countrySlug, code: mapCode } = useParams();
  const { t, locale } = useLocale();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const hub = useWorldRegionsHub(countrySlug === RUSSIA ? undefined : countrySlug);

  const defaultCode = hub.data?.default_indicator;
  const activeCode = mapCode || params.get('code') || defaultCode;
  const period = params.get('period') || undefined;
  const map = useWorldRegionsMap(
    countrySlug === RUSSIA ? undefined : countrySlug,
    activeCode,
    period,
  );

  const countryName = hub.data?.country?.name || countrySlug;
  const kindPlural = hub.data?.kind_label_plural || t('world.regions.fallbackKindPlural');
  const title = t('world.regions.hubTitle', { kind: kindPlural, country: countryName });

  useDocumentMeta({
    title: `${title} | Forecast Economy`,
    description: t('world.regions.hubDescription', { kind: kindPlural, country: countryName }),
  });

  const valuesBySlug = useMemo(() => {
    const m = new Map();
    for (const row of map.data?.values || []) {
      if (row.value != null) m.set(row.slug, row.value);
    }
    return m;
  }, [map.data]);

  const nameBySlug = useMemo(() => {
    const o = {};
    for (const r of hub.data?.regions || []) o[r.slug] = r.name;
    return o;
  }, [hub.data]);

  const geometry = MAPS[hub.data?.map_id] || usStatesMap;
  const periods = map.data?.periods || [];
  const indicators = hub.data?.indicators || [];

  const setMetric = (nextCode) => {
    navigate(`${countryRegionMapPath(countrySlug, nextCode)}${period ? `?period=${period}` : ''}`);
  };

  const setPeriod = (next) => {
    const nextParams = new URLSearchParams(params);
    if (next) nextParams.set('period', next);
    else nextParams.delete('period');
    if (activeCode) nextParams.set('code', activeCode);
    setParams(nextParams, { replace: true });
  };

  useEffect(() => {
    if (countrySlug === RUSSIA) return;
    if (mapCode || !activeCode || !countrySlug) return;
    if (params.get('code') === activeCode) return;
    const next = new URLSearchParams(params);
    next.set('code', activeCode);
    setParams(next, { replace: true });
  }, [mapCode, activeCode, countrySlug, params, setParams]);

  if (countrySlug === RUSSIA) {
    return <Navigate to={regionHubPath()} replace />;
  }

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={worldSubnationalHubTrail(countryName, countrySlug, kindPlural)} />
      {hub.isError && (
        <ApiRetryBanner onRetry={hub.refetch} isFetching={hub.isFetching} className="mb-6">
          {t('world.regions.loadError')}
        </ApiRetryBanner>
      )}
      {hub.isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-72 max-w-full" />
          <SkeletonBox className="h-80 rounded-xl" />
        </div>
      )}
      {hub.data && (
        <>
          <div className="mb-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            <MapPin size={12} />
            {kindPlural}
          </div>
          <h1 className="font-display text-[1.65rem] font-bold leading-tight text-text-primary sm:text-4xl">
            {title}
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
            {t('world.regions.hubLead', { kind: kindPlural, country: countryName })}
          </p>

          <div className="mt-6">
            <div className="mb-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
              {t('world.regions.chooseMetric')}
            </div>
            <div className="flex flex-wrap gap-2">
              {indicators.map((ind) => {
                const active = ind.code === activeCode;
                return (
                  <button
                    key={ind.code}
                    type="button"
                    onClick={() => setMetric(ind.code)}
                    className={`rounded-xl px-3 py-1.5 text-sm transition-colors ${
                      active
                        ? 'bg-champagne/15 text-champagne'
                        : 'bg-obsidian-lighter text-text-secondary hover:text-champagne'
                    }`}
                  >
                    {ind.name}
                  </button>
                );
              })}
            </div>
          </div>

          {periods.length > 0 && (
            <div className="mt-4">
              <label className="mb-2 block text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
                {t('world.regions.period')}
              </label>
              <select
                value={map.data?.period || ''}
                onChange={(e) => setPeriod(e.target.value)}
                className="rounded-xl border border-border-subtle bg-surface px-3 py-2 text-sm text-text-primary"
              >
                {periods.map((p) => (
                  <option key={p.key} value={p.key}>{p.label}</option>
                ))}
              </select>
            </div>
          )}

          <div className="mt-6 overflow-hidden rounded-2xl border border-border-subtle bg-surface">
            <Suspense fallback={<SkeletonBox className="h-80" />}>
              <RegionsMap
                mapData={geometry}
                valuesBySlug={valuesBySlug}
                unit={map.data?.indicator?.unit || ''}
                nameBySlug={nameBySlug}
                colorDirection={map.data?.indicator?.better_is_low ? 'asc' : 'desc'}
                onSelect={(slug) => navigate(countryRegionPath(countrySlug, slug))}
              />
            </Suspense>
          </div>

          <div className="mt-8 overflow-x-auto">
            <table className="w-full min-w-[32rem] text-sm">
              <thead>
                <tr className="text-left text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
                  <th className="pb-2 pr-3">{t('world.regions.rank')}</th>
                  <th className="pb-2 pr-3">{hub.data.kind_label}</th>
                  <th className="pb-2">{map.data?.indicator?.name || t('world.regions.chooseMetric')}</th>
                </tr>
              </thead>
              <tbody>
                {(map.data?.values || []).map((row) => (
                  <tr key={row.slug} className="border-t border-border-subtle">
                    <td className="py-2 pr-3 font-mono text-text-tertiary">{row.rank}</td>
                    <td className="py-2 pr-3">
                      <Link
                        to={countryRegionPath(countrySlug, row.slug)}
                        className="text-text-primary hover:text-champagne"
                      >
                        {row.name}
                      </Link>
                    </td>
                    <td className="py-2 font-mono tabular-nums">
                      {formatSubnationalValue(row.value, locale)}
                      {map.data?.indicator?.unit ? ` ${map.data.indicator.unit}` : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-xs text-text-tertiary">
            <Link to={countryRegionsPath(countrySlug)} className="hover:text-champagne">
              {kindPlural}
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
