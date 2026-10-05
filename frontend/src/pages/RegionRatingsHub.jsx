/**
 * Хаб рейтингов регионов: /russia/region-rating
 * Поиск сверху, шесть популярных показателей карточками (с тройкой лидеров), остальное — по темам.
 */
import { useMemo, useState, useDeferredValue } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, SearchX, Trophy } from 'lucide-react';
import Breadcrumbs from '../components/Breadcrumbs';
import ApiRetryBanner from '../components/ApiRetryBanner';
import LoadingNote from '../components/LoadingNote';
import Button from '../components/Button';
import { SkeletonBox } from '../components/Skeleton';
import { RegionSearchField } from '../components/regions/RegionParts';
import useDocumentMeta from '../lib/useMeta';
import { regionRatingHubTrail } from '../lib/breadcrumbs';
import { regionRatingHubPath, regionRatingPath } from '../lib/sitePaths';
import { useRegionsCatalog, useRegionsHeatmap } from '../lib/regionsApi';
import { formatRegionCompact } from '../lib/regionUi';
import { filterSearchOptions } from '../lib/searchSynonyms';
import { useLocale } from '../i18n';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';

const POPULAR = [
  { code: 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy', labelKey: 'regions.metric.wages' },
  { code: 'uroven-bezrabotitsy', labelKey: 'regions.metric.unemployment' },
  { code: 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', labelKey: 'regions.metric.grpPerCapita' },
  { code: 'chislennost-naseleniya', labelKey: 'regions.metric.population' },
  { code: 'investitsii-v-osnovnoy-kapital', labelKey: 'regions.metric.investment' },
  { code: 'chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy', labelKey: 'regions.metric.poverty' },
];
const SEARCH_LIMIT = 40;

/** Карточка популярного показателя: название и тройка лидеров текущего года. */
function PopularCard({ metric, index }) {
  const { t, locale } = useLocale();
  const { data, isLoading } = useRegionsHeatmap(metric.code);
  const top = useMemo(() => {
    if (!data?.values?.length) return [];
    const asc = data.default_sort === 'asc';
    return [...data.values]
      .sort((a, b) => (asc ? 1 : -1) * ((a.raw ?? a.value) - (b.raw ?? b.value)))
      .slice(0, 3);
  }, [data]);
  return (
    <Link
      to={regionRatingPath(metric.code)}
      className="fe-panel fe-press fe-reveal group flex min-w-0 flex-col rounded-3xl p-4 transition-colors fe-float"
      style={{ '--fe-delay': `${Math.min(index, 5) * 0.04}s`, '--fe-rise': '8px' }}
    >
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-2 font-display text-lg font-bold text-text-primary group-hover:text-champagne-ink">
          <Trophy size={16} className="text-champagne-ink" aria-hidden="true" />
          {t(metric.labelKey)}
        </span>
      </div>
      {isLoading && (
        <div className="mt-3 space-y-2" aria-hidden="true">
          {[0, 1, 2].map((i) => <SkeletonBox key={i} className="h-5 w-full rounded-lg" />)}
        </div>
      )}
      {top.length > 0 && (
        <ol className="mt-3 space-y-1.5">
          {top.map((row, i) => (
            <li key={row.slug} className="flex items-start gap-2 text-sm leading-snug">
              <span className="fe-num w-4 shrink-0 text-text-secondary">{i + 1}</span>
              <span className="min-w-0 flex-1 break-words text-text-primary">{row.name}</span>
              <span className="fe-num shrink-0 whitespace-nowrap font-medium text-text-primary">
                {formatRegionCompact(row.raw ?? row.value, data.indicator.unit, locale)}
              </span>
            </li>
          ))}
        </ol>
      )}
      <span className="mt-3 text-sm font-medium text-champagne-ink">{t('w4.rating.open')}</span>
    </Link>
  );
}

function ThemeGroup({ name, items }) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="fe-acc rounded-2xl fe-glass-lite"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary className="fe-tap flex items-center gap-3 rounded-2xl px-4 py-3">
        <span className="min-w-0 flex-1 text-[15px] font-medium text-text-primary">{name}</span>
        <span className="fe-num shrink-0 rounded-full bg-obsidian-lighter px-2 py-0.5 text-xs font-medium text-text-secondary">{items.length}</span>
        <ChevronDown size={16} className="fe-acc__chev shrink-0 text-text-secondary" aria-hidden="true" />
      </summary>
      {open && (
        <ul className="fe-divide-y">
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
      )}
    </details>
  );
}

export default function RegionRatingsHub() {
  const { t } = useLocale();
  const crumbs = useMemo(() => regionRatingHubTrail(), []);
  const { data, isLoading, isError, refetch, isFetching } = useRegionsCatalog();
  const [query, setQuery] = useState('');
  const deferredQuery = useDeferredValue(query);
  const searching = deferredQuery.trim().length > 0;

  const sections = useMemo(() => {
    const secs = data?.sections || [];
    return secs.map((s) => ({ name: s.name || t('regions.indicators'), items: s.indicators || [] }));
  }, [data, t]);

  const found = useMemo(() => {
    if (!searching) return [];
    const all = sections.flatMap((s) => s.items.map((i) => ({ ...i, section: s.name })));
    return filterSearchOptions(all, deferredQuery);
  }, [sections, deferredQuery, searching]);

  useDocumentMeta({
    title: `${t('regions.ratingHubTitle')} — Forecast Economy`,
    description: t('regions.ratingHubDesc'),
    path: regionRatingHubPath(),
  });

  return (
    <div className="fe-data-page mx-auto max-w-5xl px-4 pb-12 pt-24 sm:px-6 sm:pb-16">
      <Breadcrumbs items={crumbs} className="mb-6" />
      <header className="mb-6 max-w-3xl">
        <h1 className="font-display text-3xl font-bold text-text-primary sm:text-4xl">
          {t('regions.ratingHubH1')}
        </h1>
        <p className="mt-3 text-[15px] leading-relaxed text-text-secondary sm:text-base">
          {t('regions.ratingHub.intro')}
        </p>
      </header>

      <RegionSearchField
        className="mb-8"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('w4.rating.searchPlaceholder')}
        ariaLabel={t('w4.rating.searchAria')}
      />

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('regions.ratingHub.loadError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <LoadingNote onRefresh={() => refetch()} className="mb-4" />
          <div className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {POPULAR.map((m) => <SkeletonBox key={m.code} className="h-[184px] rounded-3xl" />)}
          </div>
          <div className="space-y-2">
            {[0, 1, 2, 3].map((i) => <SkeletonBox key={i} className="h-[52px] rounded-2xl" />)}
          </div>
        </div>
      )}

      {!isLoading && !isError && sections.length === 0 && (
        <p className="rounded-3xl p-6 text-center text-sm text-text-secondary fe-glass-lite">
          {t('common.noData')}
        </p>
      )}

      {!isLoading && !isError && searching && (
        found.length === 0 ? (
          <div role="status" className="rounded-3xl p-6 text-center text-sm text-text-secondary fe-glass-lite">
            <SearchX size={22} className="mx-auto mb-2 text-champagne-ink" aria-hidden="true" />
            {t('regions.home.nothingFound', { query: deferredQuery })}
            <div className="mt-3">
              <Button variant="secondary" size="sm" onClick={() => setQuery('')}>{t('regions.profile.resetSearch')}</Button>
            </div>
          </div>
        ) : (
          <ul className="overflow-hidden rounded-2xl fe-glass-lite fe-divide-y">
            {found.slice(0, SEARCH_LIMIT).map((ind) => (
              <li key={ind.code}>
                <Link
                  to={regionRatingPath(ind.code)}
                  className="fe-tap block px-4 py-3 transition-colors hover:bg-champagne/[0.06]"
                >
                  <span className="block text-sm text-text-primary">{ind.name}</span>
                  <span className="block text-xs text-text-secondary">{ind.section}</span>
                </Link>
              </li>
            ))}
          </ul>
        )
      )}

      {!isLoading && !isError && !searching && sections.length > 0 && (
        <>
          <section aria-labelledby="rating-popular" className="mb-10">
            <h2 id="rating-popular" className="mb-3 font-display text-xl font-bold text-text-primary">
              {t('w4.rating.popular')}
            </h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {POPULAR.map((m, i) => <PopularCard key={m.code} metric={m} index={i} />)}
            </div>
          </section>

          <section aria-labelledby="rating-themes">
            <h2 id="rating-themes" className="mb-3 font-display text-xl font-bold text-text-primary">
              {t('w4.rating.byTheme')}
            </h2>
            <div className="space-y-2">
              {sections.map((s) => <ThemeGroup key={s.name} name={s.name} items={s.items} />)}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
