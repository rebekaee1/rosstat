/**
 * Хаб рейтингов регионов: /russia/region-rating
 */
import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import Breadcrumbs from '../components/Breadcrumbs';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import useDocumentMeta from '../lib/useMeta';
import { regionRatingHubTrail } from '../lib/breadcrumbs';
import { regionRatingHubPath, regionRatingPath } from '../lib/sitePaths';
import { useRegionsCatalog } from '../lib/regionsApi';
import { useLocale } from '../i18n';
import '../styles/platform-pages.css';

export default function RegionRatingsHub() {
  const { t } = useLocale();
  const crumbs = useMemo(() => regionRatingHubTrail(), []);
  const { data, isLoading, isError, refetch, isFetching } = useRegionsCatalog();

  const sections = useMemo(() => {
    const secs = data?.sections || [];
    return secs.map((s) => [s.name || t('regions.indicators'), s.indicators || []]);
  }, [data, t]);

  useDocumentMeta({
    title: `${t('regions.ratingHubTitle')} — Forecast Economy`,
    description: t('regions.ratingHubDesc'),
    path: regionRatingHubPath(),
  });

  return (
    <div className="mx-auto max-w-5xl px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={crumbs} className="mb-6" />
      <header className="mb-8 max-w-3xl">
        <h1 className="font-display text-3xl font-bold text-text-primary sm:text-4xl">
          {t('regions.ratingHubH1')}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-text-secondary sm:text-base">
          {t('regions.ratingHub.intro')}
        </p>
      </header>

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('regions.ratingHub.loadError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          {[0, 1].map((i) => (
            <div key={i} className="mb-8">
              <SkeletonBox className="mb-3 h-4 w-40" />
              <div className="space-y-px overflow-hidden rounded-2xl border border-border-subtle bg-surface">
                {[0, 1, 2, 3, 4].map((j) => (
                  <SkeletonBox key={j} className="h-11 w-full rounded-none" />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {!isLoading && !isError && sections.length === 0 && (
        <p className="rounded-2xl border border-border-subtle bg-surface p-5 text-center text-sm text-text-secondary">
          {t('common.noData')}
        </p>
      )}

      {!isLoading && !isError && sections.map(([section, items]) => (
        <section key={section} className="mb-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-text-secondary">
            {section}
          </h2>
          <ul className="divide-y divide-border-subtle rounded-2xl border border-border-subtle bg-surface">
            {items.map((ind) => (
              <li key={ind.code}>
                <Link
                  to={regionRatingPath(ind.code)}
                  className="fe-tap flex items-center px-4 py-3 text-sm text-text-primary transition-colors hover:bg-champagne/[0.06] hover:text-champagne-ink"
                >
                  {ind.name}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
