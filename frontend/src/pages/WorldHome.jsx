// Витрина мирового блока: /world
// Сетка стран по регионам + поиск по названию страны.
import { createElement, useMemo, useState, useDeferredValue } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Search, Globe2, ChevronRight, ArrowRight, BarChart3, Database, Layers3,
  CalendarRange,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getWorldHomeSeo } from '../lib/pageMeta';
import {
  useWorldCountries, useWorldCompareCatalog, useWorldMapSeries, useWorldRatingConcepts,
  groupCountriesByRegion, pluralRu, formatWorldValue, ratingHref,
} from '../lib/worldApi';
import {
  HOME_MAP_RUSSIA_COUNTRY,
  homeConceptLabel,
  resolveActiveMapYear,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
} from '../lib/homeWorkbench';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { useLocale, useT } from '../i18n';
import { SkeletonBox } from '../components/Skeleton';
import useSearchTracking from '../lib/useSearchTracking';
import WorldConceptPicker from '../components/WorldConceptPicker';
import WorldMap from '../components/WorldMap';
import MapTimeline from '../components/MapTimeline';
import { worldHomeTrail } from '../lib/breadcrumbs';
import {
  calendarPath,
  countryPath,
  indicatorPath,
  regionHubPath,
  russiaHomePath,
} from '../lib/sitePaths';

/** Клик по РФ на карте/в рейтинге → карточка страны /russia. */
const RUSSIA_CATEGORIES_HREF = russiaHomePath();


function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/[^а-яa-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
}

function CountryMark({ country, large = false }) {
  return (
    <span className={[
      'inline-flex shrink-0 items-center justify-center rounded-full border border-champagne/20 bg-champagne/8 font-mono font-semibold tracking-tight text-champagne',
      large ? 'h-12 w-12 text-sm' : 'h-9 w-9 text-[11px]',
    ].join(' ')}>
      {country.code}
    </span>
  );
}

function CountryCard({ country, featured = false, to = null }) {
  const t = useT();
  const { locale } = useLocale();
  const n = country.indicators_count || 0;
  const seriesLabel = locale === 'en'
    ? (n === 1 ? t('world.unit.series_one') : t('world.unit.series_many'))
    : pluralRu(n, [t('world.unit.series_one'), t('world.unit.series_few'), t('world.unit.series_many')]);

  return (
    <Link
      to={to || countryPath(country.slug)}
      className={[
        'group flex items-center gap-2.5 border border-border-subtle bg-surface transition-all hover:-translate-y-0.5 hover:border-border-champagne hover:shadow-[0_18px_45px_rgba(38,33,20,0.08)] sm:gap-3',
        featured ? 'rounded-2xl p-4 sm:p-5' : 'rounded-xl px-3.5 py-3 sm:px-4 sm:py-3.5',
      ].join(' ')}
    >
      <CountryMark country={country} large={featured} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[14px] font-medium leading-snug text-text-primary transition-colors group-hover:text-champagne sm:text-[15px]">
          {country.name}
        </div>
        <div className="mt-0.5 font-mono text-[11px] text-text-tertiary">
          {country.name_en}
        </div>
      </div>
      <div className="w-auto min-w-[3.25rem] shrink-0 text-right sm:min-w-[3.5rem]">
        {n > 0 ? (
          <>
            <div className="font-mono text-[13px] font-semibold tabular-nums text-text-primary">
              {formatWorldValue(n, 0)}
            </div>
            <div className="text-[10px] text-text-tertiary">
              {seriesLabel}
            </div>
          </>
        ) : (
          <div className="text-[11px] text-text-tertiary">
            {t('world.russiaCategories')}
          </div>
        )}
      </div>
      <div className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-full bg-obsidian-light transition-colors group-hover:bg-champagne/12 sm:flex">
        <ChevronRight size={14} className="text-text-tertiary transition-colors group-hover:text-champagne" />
      </div>
    </Link>
  );
}

export default function WorldHome() {
  const t = useT();
  const { locale } = useLocale();
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch, isFetching } = useWorldCountries();
  const compareCatalog = useWorldCompareCatalog();
  const [query, setQuery] = useState('');
  const [mapConcept, setMapConcept] = useState('unemployment-rate');
  const [mapYear, setMapYear] = useState(null);
  const deferredQuery = useDeferredValue(query);
  const mapSeries = useWorldMapSeries(mapConcept);
  const ratingConcepts = useWorldRatingConcepts();
  const fullRatingHref = ratingHref(mapConcept, ratingConcepts.data?.concepts);

  const worldSeo = getWorldHomeSeo(locale);
  useDocumentMeta({
    title: worldSeo.title,
    description: worldSeo.description,
    path: worldSeo.path,
  });

  const filtered = useMemo(() => {
    const list = data?.countries || [];
    const q = normalize(deferredQuery);
    if (!q) return list;
    return list.filter((c) =>
      normalize(c.name).includes(q)
      || normalize(c.name_en).includes(q)
      || normalize(c.code).includes(q));
  }, [data, deferredQuery]);

  const showRussiaInList = useMemo(() => {
    const q = normalize(deferredQuery);
    if (!q) return true;
    return normalize(HOME_MAP_RUSSIA_COUNTRY.name).includes(q)
      || normalize(HOME_MAP_RUSSIA_COUNTRY.name_en).includes(q)
      || normalize(HOME_MAP_RUSSIA_COUNTRY.code).includes(q);
  }, [deferredQuery]);

  useSearchTracking('world-countries', deferredQuery, filtered.length + (showRussiaInList ? 1 : 0));

  const byRegion = useMemo(() => groupCountriesByRegion(filtered), [filtered]);
  const total = (data?.total ?? filtered.length) + 1;
  const totalIndicators = useMemo(
    () => (data?.countries || []).reduce((sum, country) => sum + Number(country.indicators_count || 0), 0),
    [data],
  );
  const mapConcepts = useMemo(() => {
    const fromRating = ratingConcepts.data?.concepts || [];
    if (fromRating.length) {
      return fromRating.map((item) => ({
        slug: item.slug,
        name: item.name,
        unit: item.unit,
      }));
    }
    const seen = new Map();
    for (const item of compareCatalog.data?.items || []) {
      if (!seen.has(item.concept_slug)) {
        seen.set(item.concept_slug, {
          slug: item.concept_slug,
          name: item.concept_name,
          unit: item.unit,
        });
      }
    }
    return [...seen.values()];
  }, [compareCatalog.data, ratingConcepts.data]);
  const years = mapSeries.data?.years || [];
  const activeMapYear = resolveActiveMapYear(years, mapYear, mapSeries.data?.values_by_year);
  const baseYearItems = useMemo(
    () => (activeMapYear
      ? (mapSeries.data?.values_by_year?.[String(activeMapYear)] || {})
      : {}),
    [activeMapYear, mapSeries.data],
  );
  const { countries: mapCountries, yearItems: activeYearItems } = useMemo(
    () => withRussiaOnHomeMap({
      countries: data?.countries || [],
      yearItems: baseYearItems,
      mapSeries: mapSeries.data,
    }),
    [data?.countries, baseYearItems, mapSeries.data],
  );
  const valuesByCode = useMemo(
    () => new Map(Object.entries(activeYearItems).map(([countryCode, item]) => [countryCode, item.value])),
    [activeYearItems],
  );
  const detailsByCode = useMemo(
    () => new Map(Object.entries(activeYearItems)),
    [activeYearItems],
  );
  const ranking = useMemo(
    () => worldRankingFromYearItems(activeYearItems, 12),
    [activeYearItems],
  );
  const benchmark = activeMapYear
    ? mapSeries.data?.benchmark_by_year?.[String(activeMapYear)]
    : null;
  const fromMock = data?._fromMock;

  const openCountry = (country, detail) => {
    if (country?.code === 'RU' || country?.slug === 'russia') {
      navigate(RUSSIA_CATEGORIES_HREF);
      return;
    }
    if (detail?.indicator_code && country?.slug) {
      navigate(indicatorPath(country.slug, detail.indicator_code));
      return;
    }
    if (country?.slug) navigate(countryPath(country.slug));
  };

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-hidden px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={worldHomeTrail()} className="mb-4" />
      <section className="relative mb-5 overflow-hidden rounded-[1.5rem] border border-border-subtle bg-surface px-4 py-5 shadow-[0_24px_80px_rgba(35,30,16,0.07)] sm:mb-6 sm:rounded-[2rem] sm:px-8 sm:py-7">
        <div className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-champagne/10 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-[28%] h-32 w-32 rounded-full bg-champagne/5 blur-2xl" />
        <div className="relative grid gap-5 lg:grid-cols-[1.35fr_0.65fr] lg:items-end lg:gap-8">
          <div>
            <div className="mb-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-champagne sm:mb-3">
              <Globe2 size={14} />
              {t('world.eyebrow')}
            </div>
            <h1 className="max-w-3xl font-display text-2xl font-bold leading-tight text-text-primary sm:text-4xl lg:text-[2.75rem]">
              {worldSeo.h1}
            </h1>
            <p className="mt-3 max-w-2xl text-[13px] leading-5 text-text-secondary sm:mt-4 sm:text-sm sm:leading-6">
              {worldSeo.description}
            </p>
            <div className="mt-4 flex flex-wrap gap-2.5 sm:mt-5 sm:gap-3">
              <a href="#countries" className="magnetic-btn inline-flex items-center gap-2 rounded-xl bg-champagne px-4 py-2.5 text-sm font-semibold text-white shadow-sm">
                {t('world.selectCountry')}
                <ArrowRight size={15} />
              </a>
              <Link to="/compare" className="inline-flex items-center gap-2 rounded-xl border border-border-subtle bg-white/70 px-4 py-2.5 text-sm font-medium text-text-primary transition-colors hover:border-border-champagne hover:text-champagne">
                <BarChart3 size={15} />
                {t('world.compareCountries')}
              </Link>
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-champagne/15 bg-gradient-to-br from-champagne/[0.08] to-white/75 p-4 sm:p-5">
            <div className="mb-4 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
              <Database size={13} />
              {t('world.coverage')}
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              {[
                [Globe2, total || 39, locale === 'en' ? (total === 1 ? t('world.unit.country_one') : t('world.unit.country_many')) : pluralRu(total || 39, [t('world.unit.country_one'), t('world.unit.country_few'), t('world.unit.country_many')])],
                [Database, formatWorldValue(totalIndicators, 0), t('world.stat.series')],
                [Layers3, mapConcepts.length || 6, t('world.stat.concepts')],
                [CalendarRange, years.length ? `${years[0]}–${years[years.length - 1]}` : '—', t('world.stat.mapPeriod')],
              ].map(([Icon, value, label]) => (
                <div key={label} className="rounded-xl border border-white/80 bg-white/65 px-3 py-3 shadow-sm">
                  {createElement(Icon, { className: 'mb-2 h-3.5 w-3.5 text-champagne' })}
                  <div className="font-mono text-base font-semibold text-text-primary">{value}</div>
                  <div className="mt-0.5 text-[10px] leading-tight text-text-tertiary">{label}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 border-t border-champagne/10 pt-3 text-[11px] leading-5 text-text-secondary">
              {t('world.coverageNote')}
            </div>
          </div>
        </div>
        {fromMock && (
          <p className="mt-2 text-[12px] text-text-tertiary font-mono">
            {t('world.mockData')}
          </p>
        )}
      </section>

      {!isLoading && !isError && (
        <section className="mb-12">
          <div className="mb-4 min-w-0">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">{t('world.mapSlice')}</div>
            <h2 className="mt-1 font-display text-xl font-bold text-text-primary sm:text-2xl">{t('world.mapTitle')}</h2>
            <p className="mt-2 max-w-2xl text-xs leading-5 text-text-secondary">
              {t('world.mapHint')}
            </p>
            <div className="mt-3">
              <WorldConceptPicker
                concepts={mapConcepts}
                value={mapConcept}
                onChange={(slug) => {
                  setMapConcept(slug);
                  setMapYear(null);
                }}
                label={t('world.mapMetric')}
              />
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.65fr)_minmax(min(100%,17.5rem),0.75fr)]">
            <div className="rounded-[1.25rem] border border-border-subtle bg-surface p-3 shadow-[0_16px_45px_rgba(35,30,16,0.05)] sm:rounded-[1.5rem] sm:p-5">
              {mapSeries.isLoading ? (
                <SkeletonBox className="aspect-[2/1] w-full rounded-2xl" />
              ) : (
                <>
                  <WorldMap
                    countries={mapCountries}
                    valuesByCode={valuesByCode}
                    detailsByCode={detailsByCode}
                    unit={mapSeries.data?.concept?.unit || ''}
                    metricName={homeConceptLabel(mapConcept, t, mapSeries.data?.concept?.name || '')}
                    periodLabel={activeMapYear ? String(activeMapYear) : ''}
                    colorMode={mapConcept === 'budget-balance-gdp' ? 'diverging' : 'auto'}
                    defaultScope="world"
                    onSelect={openCountry}
                  />
                  {years.length > 1 && activeMapYear && (
                    <MapTimeline
                      years={years}
                      year={activeMapYear}
                      onYearChange={setMapYear}
                      metric={`world:${mapConcept}`}
                    />
                  )}
                </>
              )}
            </div>

            <div className="rounded-[1.25rem] border border-border-subtle bg-surface p-4 shadow-[0_16px_45px_rgba(35,30,16,0.05)] sm:rounded-[1.5rem] sm:p-5">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">{t('world.latestData')}</div>
                  <h3 className="mt-1 text-sm font-semibold leading-snug text-text-primary sm:text-base">
                    {homeConceptLabel(mapConcept, t, mapSeries.data?.concept?.name || t('world.ratingFallback'))}
                  </h3>
                  <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 font-mono text-[10px] text-text-tertiary">
                    {activeMapYear && <span>{t('world.yearLabel', { year: activeMapYear })}</span>}
                    {mapSeries.data?.concept?.unit ? <span>{mapSeries.data.concept.unit}</span> : null}
                  </div>
                </div>
                <BarChart3 size={16} className="mt-1 shrink-0 text-champagne" />
              </div>

              {benchmark?.value != null && (
                <div className="mb-4 rounded-xl bg-champagne/[0.08] px-3.5 py-3">
                  <div className="text-[10px] text-text-tertiary">{benchmark.label}</div>
                  <div className="mt-1 font-mono text-lg font-semibold text-text-primary">
                    {formatWorldValue(benchmark.value)}
                  </div>
                </div>
              )}

              <div className="space-y-1">
                {ranking.slice(0, 8).map((item, index) => {
                  const isRussia = item.country_code === 'RU' || item.country_slug === 'russia';
                  return (
                    <Link
                      key={item.country_slug || item.country_code || index}
                      to={isRussia
                        ? RUSSIA_CATEGORIES_HREF
                        : (item.indicator_code
                          ? indicatorPath(item.country_slug, item.indicator_code)
                          : countryPath(item.country_slug))}
                      className="group grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-baseline gap-2 rounded-lg px-2 py-2 transition-colors hover:bg-surface-hover"
                    >
                      <span className="font-mono text-[10px] text-text-tertiary">{index + 1}</span>
                      <span className="min-w-0 text-sm leading-snug text-text-primary group-hover:text-champagne">
                        {item.country_name}
                      </span>
                      <span className="font-mono text-xs font-semibold tabular-nums text-text-primary">
                        {formatWorldValue(item.value)}
                      </span>
                    </Link>
                  );
                })}
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
                {fullRatingHref && (
                  <Link
                    to={fullRatingHref}
                    className="inline-flex items-center gap-1 text-xs text-champagne hover:underline"
                  >
                    {t('world.fullRating')}
                    <ChevronRight size={12} />
                  </Link>
                )}
                {ranking.filter((item) => item.country_code !== 'RU').length >= 2 && (
                  <Link
                    to={`/compare?codes=${encodeURIComponent(
                      ranking
                        .filter((item) => item.country_code !== 'RU')
                        .slice(0, 2)
                        .map((item) => `w:${item.country_slug}:${mapConcept}`)
                        .join(','),
                    )}`}
                    className="inline-flex items-center gap-1 text-xs text-champagne hover:underline"
                  >
                    {t('world.compareCountries')}
                    <ChevronRight size={12} />
                  </Link>
                )}
              </div>
            </div>
          </div>
        </section>
      )}

      <section id="countries" className="scroll-mt-24">
      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">{t('world.catalog')}</div>
          <h2 className="mt-1 font-display text-2xl font-bold text-text-primary">{t('world.allCountries')}</h2>
        </div>
        <div className="relative w-full sm:max-w-md">
        <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('world.findCountry')}
          aria-label={t('world.findCountryAria')}
          className="w-full rounded-xl border border-border-subtle bg-surface py-3 pl-10 pr-4 text-sm text-text-primary shadow-sm placeholder:text-text-tertiary focus:border-border-champagne focus:outline-none"
        />
      </div>
      </div>

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          {t('world.loadError')}
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-8 w-48" />
          <div className="grid sm:grid-cols-2 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonBox key={i} className="h-16 rounded-xl" />
            ))}
          </div>
        </div>
      )}

      {!isLoading && !isError && filtered.length === 0 && !showRussiaInList && (
        <div className="rounded-2xl border border-border-subtle bg-surface p-8 text-center">
          <p className="text-text-secondary mb-4">
            {t('world.noResults', { query })}
          </p>
          <Link to="/" className="text-champagne hover:underline text-sm">
            {t('common.home')}
          </Link>
          <span className="mx-2 text-text-tertiary">—</span>
          <Link to={regionHubPath()} className="text-champagne hover:underline text-sm">
            {t('footer.regions')}
          </Link>
        </div>
      )}

      {!isLoading && showRussiaInList && (
        <section className="mb-8">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
            {t('world.russia')}
            <span className="font-mono text-[11px] font-normal text-text-tertiary">{t('world.macroTag')}</span>
          </h2>
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            <CountryCard
              country={{
                ...HOME_MAP_RUSSIA_COUNTRY,
                indicators_count: 0,
              }}
              featured
              to={RUSSIA_CATEGORIES_HREF}
            />
          </div>
        </section>
      )}

      {!isLoading && byRegion.map(({ region, countries }) => (
        <section key={region} className="mb-8">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary">
            {region}
            <span className="font-mono text-[11px] font-normal text-text-tertiary">
              {countries.length}
            </span>
          </h2>
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {countries.map((c) => (
              <CountryCard key={c.slug} country={c} />
            ))}
          </div>
        </section>
      ))}

      {!isLoading && total > 0 && (
        <p className="text-[12px] text-text-tertiary font-mono mt-4">
          {total} {locale === 'en' ? (total === 1 ? t('world.unit.country_one') : t('world.unit.country_many')) : pluralRu(total, [t('world.unit.country_one'), t('world.unit.country_few'), t('world.unit.country_many')])}
        </p>
      )}
      </section>

      <div className="mt-10 pt-6 border-t border-border-subtle flex flex-wrap gap-x-4 gap-y-2 text-sm text-text-secondary">
        <Link to={regionHubPath()} className="hover:text-champagne transition-colors">{t('footer.regions')}</Link>
        <Link to="/compare" className="hover:text-champagne transition-colors">{t('nav.compare')}</Link>
        <Link to={calendarPath()} className="hover:text-champagne transition-colors">{t('crumb.calendar')}</Link>
        <Link to="/" className="hover:text-champagne transition-colors">{t('common.home')}</Link>
      </div>
    </div>
  );
}
