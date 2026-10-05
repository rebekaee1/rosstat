// Профиль субнационального региона: /{country}/region/{slug}
// Эталон — RegionProfile (Россия): темы слева, HeadlineCard, IndicatorRow.
import { useMemo, useState, useDeferredValue } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ChevronRight, MapPin, SearchX } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useWorldRegionProfile } from '../lib/worldSubnationalApi';
import Button from '../components/Button';
import {
  RegionHeadlineCard, RegionIndicatorRow, RegionSectionHeading, RegionSearchField,
} from '../components/regions/RegionParts';
import { prioritizeIndicators } from '../lib/regionUi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import LoadingNote from '../components/LoadingNote';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import UsCatalogNav from '../components/UsCatalogNav';
import { groupUsSections, shortUsIndicatorName } from '../lib/usCatalogTopics';
import useSearchTracking from '../lib/useSearchTracking';
import { filterSearchOptions } from '../lib/searchSynonyms';
import { worldSubnationalRegionTrail } from '../lib/breadcrumbs';
import {
  RUSSIA,
  countryRegionIndicatorPath,
  countryRegionVsPath,
  countryRegionsPath,
  regionPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';
import '../styles/platform-pages.css';
import '../styles/regions-w4.css';
import '../styles/z5-country.css';

function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
}

export default function WorldRegionProfile() {
  const { countrySlug, slug } = useParams();
  const { t, locale } = useLocale();
  const profile = useWorldRegionProfile(countrySlug === RUSSIA ? undefined : countrySlug, slug);
  const [query, setQuery] = useState('');
  const [activeSection, setActiveSection] = useState('');
  const [searchLimit, setSearchLimit] = useState(120);
  const deferredQuery = useDeferredValue(query);
  const searching = normalize(deferredQuery).length > 0;

  const countryName = profile.data?.country?.name || countrySlug;
  const regionName = profile.data?.region?.name || slug;
  const kind = profile.data?.kind_label || t('world.regions.fallbackKind');
  const kindPlural = profile.data?.kind_label_plural || t('world.regions.fallbackKindPlural');

  useDocumentMeta({
    title: `${regionName} — ${kind} | Forecast Economy`,
    description: t('world.regions.profileDescription', { region: regionName, country: countryName }),
  });

  const isUsCatalog = countrySlug === 'united-states';
  const sections = useMemo(() => {
    const all = (profile.data?.sections || []).map((section) => ({
      ...section,
      indicators: prioritizeIndicators(section.indicators),
    }));
    if (!isUsCatalog) return all;
    // BEA publishes a few blank lines for some states. Do not show empty cards
    // or count them as available indicators on the state profile.
    return all.map((section) => ({
      ...section,
      indicators: section.indicators.filter((item) => item.value !== null),
    })).filter((section) => section.indicators.length > 0);
  }, [profile.data, isUsCatalog]);
  const usTopics = useMemo(
    () => isUsCatalog ? groupUsSections(sections, locale) : [],
    [sections, isUsCatalog, locale],
  );
  const filteredSections = useMemo(() => {
    const q = normalize(deferredQuery);
    if (!q) return sections;
    return sections
      .map((s) => ({
        ...s,
        indicators: filterSearchOptions(s.indicators, q, {
          getSearchItem: (item) => ({ ...item, section_name: s.name, country_slug: countrySlug, country_name: countryName, region_slug: slug, region_name: regionName }),
        }),
      }))
      .filter((s) => s.indicators.length > 0);
  }, [sections, deferredQuery, countrySlug, countryName, slug, regionName]);

  const foundIndicators = filteredSections.reduce((n, s) => n + s.indicators.length, 0);
  useSearchTracking('world-region-profile', deferredQuery, foundIndicators);

  const headline = useMemo(() => {
    if (!profile.data) return [];
    if (!isUsCatalog) {
      const firstOfSection = sections.map((s) => s.indicators[0]).filter(Boolean);
      const rest = (profile.data.indicators || []).filter(
        (item) => !firstOfSection.some((h) => h.code === item.code),
      );
      return [...firstOfSection, ...rest].slice(0, 8);
    }
    const byCode = new Map((profile.data.indicators || []).map((item) => [item.code, item]));
    const featured = (profile.data.featured_indicator_codes || []).map((code) => byCode.get(code)).filter(Boolean);
    const firstOfSection = sections.map((s) => s.indicators[0]).filter(Boolean);
    const seen = new Set();
    return [...featured, ...firstOfSection, ...(profile.data.indicators || [])]
      .filter((item) => {
        if (seen.has(item.code)) return false;
        seen.add(item.code);
        return item.value !== null;
      })
      .slice(0, 8);
  }, [profile.data, sections, isUsCatalog]);

  const resolvedActive = filteredSections.some((s) => String(s.num) === String(activeSection))
    ? filteredSections.find((s) => String(s.num) === String(activeSection))?.num
    : ((isUsCatalog ? usTopics[0]?.sections[0] : filteredSections[0])?.num || '');
  const activeUsTopic = usTopics.find((topic) => topic.sections.some((section) => section.num === resolvedActive));
  const selectUsTopic = (id) => {
    const first = usTopics.find((topic) => topic.id === id)?.sections[0];
    if (first) setActiveSection(first.num);
  };
  let remaining = searchLimit;
  const visibleSections = searching
    ? (isUsCatalog ? filteredSections.map((s) => {
      const indicators = s.indicators.slice(0, remaining);
      remaining -= indicators.length;
      return { ...s, indicators };
    }).filter((s) => s.indicators.length > 0) : filteredSections)
    : filteredSections.filter((s) => s.num === resolvedActive);

  if (countrySlug === RUSSIA) {
    return <Navigate to={regionPath(slug)} replace />;
  }

  return (
    <div className="fe-data-page mx-auto w-full max-w-7xl overflow-x-clip px-4 pb-12 pt-24 sm:px-6 sm:pb-16">
      <Breadcrumbs items={worldSubnationalRegionTrail(countryName, countrySlug, kindPlural, regionName, slug)} />
      {profile.isError && (
        <ApiRetryBanner onRetry={profile.refetch} isFetching={profile.isFetching} className="mb-6">
          {t('world.regions.loadError')}
        </ApiRetryBanner>
      )}
      {profile.isLoading && (
        <div role="status" aria-busy="true" aria-label={t('common.loading')}>
          <LoadingNote onRefresh={() => profile.refetch()} className="mb-4" />
          <SkeletonBox className="mb-2 mt-6 h-4 w-40" />
          <SkeletonBox className="h-[2.6rem] w-72 max-w-full sm:h-10" />
          <SkeletonBox className="mt-3 h-5 w-full max-w-2xl" />
          <div className="mb-8 mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => <SkeletonBox key={i} className="h-[92px] rounded-xl" />)}
          </div>
          <SkeletonBox className="mb-6 h-[46px] w-full rounded-xl" />
          <div className="grid grid-cols-1 gap-2 sm:gap-2.5 xl:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => <SkeletonBox key={i} className="h-[110px] rounded-xl sm:h-[84px]" />)}
          </div>
        </div>
      )}
      {profile.data && (
        <>
          <div className="fe-data-header fe-reveal">
            <div className="mb-2 flex items-center gap-1.5 text-sm font-medium text-champagne-ink">
              <MapPin size={15} aria-hidden="true" />
              {kind}
            </div>
            <h1 className="font-display text-[1.65rem] font-bold leading-tight text-text-primary sm:text-4xl">
              {regionName}
            </h1>
            <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-text-secondary">
              {t('w4.regions.profile.intro')}
            </p>
          </div>

          {headline.length > 0 && (
            <div className="mb-8 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              {headline.map((h, i) => (
                <RegionHeadlineCard
                  key={h.code}
                  item={h}
                  index={i}
                  to={countryRegionIndicatorPath(countrySlug, slug, h.code)}
                />
              ))}
            </div>
          )}

          {isUsCatalog && profile.data.comparison_regions?.length > 0 && (
            <section className="mb-6 rounded-3xl p-4 fe-glass-lite" aria-label={locale === 'en' ? 'Compare states' : 'Сравнить штаты'}>
              <h2 className="mb-2 text-sm font-semibold text-text-primary">{locale === 'en' ? 'Compare with another state' : 'Сравнить с другим штатом'}</h2>
              <div className="flex flex-wrap gap-2">
                {profile.data.comparison_regions.slice(0, 8).map((other) => (
                  <a key={other.slug} href={countryRegionVsPath(countrySlug, slug, other.slug)} className="fe-chip fe-press">{other.name}</a>
                ))}
              </div>
              {profile.data.comparison_regions.length > 8 && (
                <details className="mt-3 text-xs text-text-secondary">
                  <summary className="fe-tap-inline cursor-pointer text-champagne-ink">{locale === 'en' ? 'All states' : 'Все штаты'}</summary>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {profile.data.comparison_regions.slice(8).map((other) => (
                      <a key={other.slug} href={countryRegionVsPath(countrySlug, slug, other.slug)} className="fe-chip fe-press">{other.name}</a>
                    ))}
                  </div>
                </details>
              )}
            </section>
          )}

          <RegionSearchField
            className="mb-6"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSearchLimit(120); }}
            placeholder={t('regions.profileSearchPlaceholder')}
            ariaLabel={t('regions.profileSearchAria')}
          />

          {!searching && filteredSections.length === 0 && (
            <div className="rounded-3xl p-6 text-center text-sm text-text-secondary fe-glass-lite">
              {t('pgui.regions.profileEmpty')}
            </div>
          )}

          {searching && filteredSections.length === 0 && (
            <div className="rounded-3xl p-6 text-center text-sm text-text-secondary fe-glass-lite">
              <SearchX size={22} className="mx-auto mb-2 text-champagne-ink" aria-hidden="true" />
              {t('regions.profile.nothingFound', { query })}
              <div className="mt-3">
                <Button variant="secondary" size="sm" onClick={() => { setQuery(''); setSearchLimit(120); }}>
                  {t('regions.profile.resetSearch')}
                </Button>
              </div>
            </div>
          )}

          {!searching && !isUsCatalog && (
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
            {!searching && isUsCatalog && (
              <UsCatalogNav
                topics={usTopics}
                activeTopic={activeUsTopic?.id}
                activeSection={resolvedActive}
                onTopic={selectUsTopic}
                onSection={(num) => setActiveSection(Number(num))}
                sectionKey={(section) => section.num}
                sectionLabel={(section) => section.name}
                themesLabel={t('regions.profile.themes')}
                detailLabel={locale === 'en' ? 'Detailed topics' : 'Подробные темы'}
              />
            )}
            {!searching && !isUsCatalog && (
              <aside className="z5-topics hidden min-w-0 lg:sticky lg:top-24 lg:block lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto">
                <div className="z5-aside-title">
                  {t('regions.profile.themes')}
                </div>
                <div className="z5-topics__list">
                  {filteredSections.map((sec) => (
                    <button
                      key={sec.num}
                      type="button"
                      onClick={() => setActiveSection(sec.num)}
                      className={[
                        'fe-tap fe-press z5-topic',
                        resolvedActive === sec.num
                          ? 'is-active'
                          : '',
                      ].join(' ')}
                    >
                      <span className="min-w-0 break-words leading-snug">{sec.name}</span>
                      <span className="z5-topic__count">{sec.indicators.length}</span>
                    </button>
                  ))}
                </div>
              </aside>
            )}

            <div id="chart" className="min-w-0 space-y-8 scroll-mt-28">
              {visibleSections.map((sec) => (
                <section key={sec.num} data-block={`world-region-section-${sec.num}`}>
                  <RegionSectionHeading
                    eyebrow={searching ? t('regions.searchResults') : null}
                    title={sec.name}
                    count={sec.indicators.length}
                  />
                  <div className="grid grid-cols-1 gap-2 sm:gap-2.5 xl:grid-cols-2">
                    {sec.indicators.map((item) => (
                      <RegionIndicatorRow
                        key={item.code}
                        item={item}
                        to={countryRegionIndicatorPath(countrySlug, slug, item.code)}
                        title={shortUsIndicatorName(item.name, isUsCatalog && locale === 'ru' ? sec.name : undefined, locale)}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </div>

          {isUsCatalog && searching && foundIndicators > searchLimit && (
            <button
              type="button"
              onClick={() => setSearchLimit((current) => current + 120)}
              className="fe-tap mt-5 rounded-full px-5 py-2.5 text-sm text-text-secondary hover:text-text-primary fe-glass-2"
            >
              {locale === 'en' ? 'Show more indicators' : 'Показать ещё показатели'}
              {locale === 'en' ? ' of ' : ' из '}
              {Math.min(searchLimit, foundIndicators)} / {foundIndicators}
            </button>
          )}

          <p className="mt-8 text-sm">
            <Link to={countryRegionsPath(countrySlug)} className="fe-tap-inline gap-1 text-champagne-ink hover:underline">
              {t('world.regions.backToHub', { kind: kindPlural })}
              <ChevronRight size={14} />
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
