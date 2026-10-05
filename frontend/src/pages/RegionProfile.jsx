// Страница региона: /russia/region/{slug}
// Как у стран: темы слева, сетка показателей справа.
import { useEffect, useMemo, useState, useDeferredValue } from 'react';
import { Link, useParams } from 'react-router-dom';
import { GitCompare, MapPin, SearchX } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useRegionProfile } from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import Button from '../components/Button';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import {
  RegionHeadlineCard, RegionIndicatorRow, RegionSectionHeading, RegionSearchField,
} from '../components/regions/RegionParts';
import { prioritizeIndicators } from '../lib/regionUi';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchOptions } from '../lib/searchSynonyms';
import { regionTrail, breadcrumbJsonLd } from '../lib/breadcrumbs';
import { mountJsonLd } from '../lib/jsonLd';
import {
  regionIndicatorPath,
  regionPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';

function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
}

export default function RegionProfile() {
  const { t } = useLocale();
  const { slug } = useParams();
  const { data, isLoading, isError, refetch, isFetching } = useRegionProfile(slug);
  const [query, setQuery] = useState('');
  const [activeSection, setActiveSection] = useState('');
  const deferredQuery = useDeferredValue(query);
  const searching = normalize(deferredQuery).length > 0;

  const regionName = data?.region?.name;
  useDocumentMeta(regionName ? {
    title: t('regions.profileTitle', { name: regionName }),
    description: t('regions.profileDesc', { name: regionName }),
    path: regionPath(slug),
  } : null);

  useEffect(() => {
    if (!regionName) return undefined;
    return mountJsonLd(breadcrumbJsonLd(regionTrail(regionName, slug)));
  }, [regionName, slug]);

  const sections = useMemo(
    () => (data?.sections || []).map((s) => ({ ...s, indicators: prioritizeIndicators(s.indicators) })),
    [data],
  );

  const filteredSections = useMemo(() => {
    if (!data) return [];
    const q = normalize(deferredQuery);
    if (!q) return sections;
    return sections
      .map((s) => ({
        ...s,
        indicators: filterSearchOptions(s.indicators, q, {
          getSearchItem: (item) => ({ ...item, section_name: s.name, country_slug: 'russia', region_slug: slug, region_name: regionName }),
        }),
      }))
      .filter((s) => s.indicators.length > 0);
  }, [data, sections, deferredQuery, slug, regionName]);

  const foundIndicators = filteredSections.reduce((n, s) => n + s.indicators.length, 0);
  useSearchTracking('region-profile', deferredQuery, foundIndicators);

  const headlineOrder = ['1.1', '3.4', '2.10.1', '8.2', '10.1', '20.1', '3.12', '8.1'];
  const headline = data
    ? headlineOrder.map((tc) => data.headline[tc]).filter(Boolean)
    : [];

  const resolvedActive = filteredSections.some((s) => String(s.num) === String(activeSection))
    ? filteredSections.find((s) => String(s.num) === String(activeSection))?.num
    : (filteredSections[0]?.num || '');
  const visibleSections = searching
    ? filteredSections
    : filteredSections.filter((s) => s.num === resolvedActive);

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-12 pt-24 sm:px-6 sm:pb-16">
      <Breadcrumbs items={regionTrail(regionName || '…', slug)} />

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('pgui.regions.profileError')}
        </ApiRetryBanner>
      )}
      {isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <SkeletonBox className="mb-6 mt-6 h-[148px] rounded-3xl" />
          <div className="mb-8 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => <SkeletonBox key={i} className="h-[112px] rounded-2xl" />)}
          </div>
          <SkeletonBox className="mb-6 h-12 w-full rounded-xl" />
          <div className="grid grid-cols-1 gap-2 sm:gap-2.5 xl:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => <SkeletonBox key={i} className="h-[110px] rounded-2xl sm:h-[84px]" />)}
          </div>
        </div>
      )}

      {data && (
        <>
          <div className="fe-data-header fe-reveal">
            {data.region.district_name && (
              <div className="mb-2 flex items-center gap-1.5 text-sm font-medium text-champagne-ink">
                <MapPin size={15} aria-hidden="true" />
                {data.region.district_name}
              </div>
            )}
            <h1 className="font-display text-[1.65rem] font-bold leading-tight text-text-primary sm:text-4xl">
              {data.region.name}
            </h1>
            <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-text-secondary">
              {t('w4.regions.profile.intro', { sections: data.sections.length })}
            </p>
            {headline.length > 0 && (
              <Link
                to={regionIndicatorPath(slug, headline.find((h) => h.code === '3.4')?.code || headline[0].code)}
                className="fe-chip fe-press mt-3 gap-1.5 text-champagne-ink"
                data-testid="region-compare-russia"
              >
                <GitCompare size={14} aria-hidden="true" />
                {t('w6f.reg.compareRussia')}
              </Link>
            )}
          </div>

          {headline.length > 0 && (
            <>
              {/* Одна общая подпись вместо года на каждой карточке: у показателей разные «последние данные». */}
              <p className="mb-2 text-sm text-text-secondary" data-testid="region-latest-note">{t('w6f.reg.latestNote')}</p>
              <div className="mb-8 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                {headline.map((h, i) => (
                  <RegionHeadlineCard key={h.code} item={h} index={i} to={regionIndicatorPath(slug, h.code)} />
                ))}
              </div>
            </>
          )}

          <RegionSearchField
            className="mb-6"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('regions.profileSearchPlaceholder')}
            ariaLabel={t('regions.profileSearchAria')}
          />

          {!searching && filteredSections.length === 0 && (
            <div className="rounded-3xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
              {t('pgui.regions.profileEmpty')}
            </div>
          )}

          {searching && filteredSections.length === 0 && (
            <div className="rounded-3xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
              <SearchX size={22} className="mx-auto mb-2 text-champagne-ink" aria-hidden="true" />
              {t('regions.profile.nothingFound', { query })}
              <div className="mt-3">
                <Button variant="secondary" size="sm" onClick={() => setQuery('')}>
                  {t('regions.profile.resetSearch')}
                </Button>
              </div>
            </div>
          )}

          {!searching && (
            <MobileNavSelect
              label={t('regions.themes')}
              value={String(resolvedActive)}
              onChange={(v) => setActiveSection(Number(v))}
              options={filteredSections.map((sec) => ({
                value: String(sec.num),
                label: sec.name,
                count: sec.indicators.length,
              }))}
            />
          )}

          <div className={searching
            ? 'min-w-0 space-y-8'
            : 'grid min-w-0 gap-6 lg:grid-cols-[250px_minmax(0,1fr)]'}
          >
            {!searching && (
              <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block lg:self-start">
                <div className="mb-2 px-2 text-sm font-medium text-text-secondary">
                  {t('regions.profile.themes')}
                </div>
                <div className="flex flex-col gap-2">
                  {filteredSections.map((sec) => (
                    <button
                      key={sec.num}
                      type="button"
                      onClick={() => setActiveSection(sec.num)}
                      className={[
                        'fe-tap fe-press flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                        resolvedActive === sec.num
                          ? 'bg-champagne/12 font-medium text-champagne-ink'
                          : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                      ].join(' ')}
                    >
                      <span className="min-w-0 break-words leading-snug">{sec.name}</span>
                      <span className="fe-num shrink-0 text-xs">{sec.indicators.length}</span>
                    </button>
                  ))}
                </div>
              </aside>
            )}

            <div id="chart" className="min-w-0 space-y-8 scroll-mt-28">
              {visibleSections.map((sec) => (
                <section key={sec.num} data-block={`region-section-${sec.num}`}>
                  <RegionSectionHeading
                    eyebrow={searching ? t('regions.searchResults') : null}
                    title={sec.name}
                    count={sec.indicators.length}
                  />
                  <div className="grid grid-cols-1 gap-2 sm:gap-2.5 xl:grid-cols-2">
                    {sec.indicators.map((item) => (
                      <RegionIndicatorRow key={item.code} item={item} to={regionIndicatorPath(slug, item.code)} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
