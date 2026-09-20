// Профиль субнационального региона: /{country}/region/{slug}
import { Link, Navigate, useParams } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useWorldRegionProfile, formatSubnationalValue } from '../lib/worldSubnationalApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import { worldSubnationalRegionTrail } from '../lib/breadcrumbs';
import {
  RUSSIA,
  countryRegionIndicatorPath,
  countryRegionsPath,
  regionPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';

export default function WorldRegionProfile() {
  const { countrySlug, slug } = useParams();
  const { t, locale } = useLocale();
  const profile = useWorldRegionProfile(countrySlug === RUSSIA ? undefined : countrySlug, slug);

  const countryName = profile.data?.country?.name || countrySlug;
  const regionName = profile.data?.region?.name || slug;
  const kind = profile.data?.kind_label || t('world.regions.fallbackKind');
  const kindPlural = profile.data?.kind_label_plural || t('world.regions.fallbackKindPlural');

  useDocumentMeta({
    title: `${regionName} — ${kind} | Forecast Economy`,
    description: t('world.regions.profileDescription', { region: regionName, country: countryName }),
  });

  if (countrySlug === RUSSIA) {
    return <Navigate to={regionPath(slug)} replace />;
  }

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={worldSubnationalRegionTrail(countryName, countrySlug, kindPlural, regionName, slug)} />
      {profile.isError && (
        <ApiRetryBanner onRetry={profile.refetch} isFetching={profile.isFetching} className="mb-6">
          {t('world.regions.loadError')}
        </ApiRetryBanner>
      )}
      {profile.isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-64" />
          <SkeletonBox className="h-40 rounded-xl" />
        </div>
      )}
      {profile.data && (
        <>
          <div className="mb-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            <MapPin size={12} />
            {kind}
          </div>
          <h1 className="font-display text-[1.65rem] font-bold leading-tight text-text-primary sm:text-4xl">
            {regionName}
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            {kind}, {countryName}
          </p>
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(profile.data.indicators || []).map((ind) => (
              <Link
                key={ind.code}
                to={countryRegionIndicatorPath(countrySlug, slug, ind.code)}
                className="rounded-xl border border-border-subtle bg-surface p-4 transition-colors hover:border-champagne/40"
              >
                <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
                  {ind.section}
                </div>
                <div className="mt-1 text-sm text-text-primary">{ind.name}</div>
                <div className="mt-2 font-mono text-lg font-semibold tabular-nums text-text-primary">
                  {formatSubnationalValue(ind.value, locale)}
                  {ind.unit ? <span className="ml-1 text-xs font-normal text-text-tertiary">{ind.unit}</span> : null}
                </div>
                <div className="mt-1 font-mono text-[11px] text-text-tertiary">
                  {ind.period_label || '—'}
                  {ind.rank != null ? ` — ${t('world.regions.rankOf', { rank: ind.rank, total: ind.of })}` : ''}
                </div>
              </Link>
            ))}
          </div>
          <p className="mt-8 text-sm">
            <Link to={countryRegionsPath(countrySlug)} className="text-champagne hover:underline">
              {t('world.regions.backToHub', { kind: kindPlural })}
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
