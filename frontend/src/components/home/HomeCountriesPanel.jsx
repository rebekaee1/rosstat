import { lazy, Suspense, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Globe2 } from 'lucide-react';
import {
  DEFAULT_HOME_COUNTRY_CONCEPT,
  DEFAULT_HOME_COUNTRY_MACROREGION,
  HOME_COUNTRY_MACROREGIONS,
  availableCountryMacroregions,
  countryCoverageNoteKey,
  homeConceptLabel,
  resolveActiveMapYear,
  resolveCountryMacroregion,
  worldRankingFromYearItems,
  worldYearItems,
} from '../../lib/homeWorkbench';
import {
  formatWorldValue,
  ratingHref,
  useWorldCompareCatalog,
  useWorldCountries,
  useWorldMapSeries,
  useWorldRatingConcepts,
} from '../../lib/worldApi';
import { SkeletonBox } from '../Skeleton';
import ApiRetryBanner from '../ApiRetryBanner';
import { track, events } from '../../lib/track';
import {
  countryPath,
  indicatorPath,
} from '../../lib/sitePaths';
import { useT } from '../../i18n';

const WorldMap = lazy(() => import('../WorldMap'));
const MapTimeline = lazy(() => import('../MapTimeline'));

export default function HomeCountriesPanel() {
  const t = useT();
  const navigate = useNavigate();
  const [macroregion, setMacroregion] = useState(DEFAULT_HOME_COUNTRY_MACROREGION);
  const [concept, setConcept] = useState(DEFAULT_HOME_COUNTRY_CONCEPT);
  const [mapYear, setMapYear] = useState(null);

  const countries = useWorldCountries();
  const catalog = useWorldCompareCatalog();
  const mapSeries = useWorldMapSeries(concept);
  const ratingConcepts = useWorldRatingConcepts();
  const fullRatingHref = ratingHref(concept, ratingConcepts.data?.concepts);

  const activeMacro = resolveCountryMacroregion(macroregion);
  const coverage = t(countryCoverageNoteKey(activeMacro));
  const macros = availableCountryMacroregions();
  const conceptName = homeConceptLabel(
    concept,
    t,
    mapSeries.data?.concept?.name || t('home.map.metricFallback'),
  );

  const mapConcepts = useMemo(() => {
    const seen = new Map();
    for (const item of catalog.data?.items || []) {
      if (!seen.has(item.concept_slug)) {
        seen.set(item.concept_slug, {
          slug: item.concept_slug,
          name: item.concept_name,
          unit: item.unit,
        });
      }
    }
    return [...seen.values()];
  }, [catalog.data]);

  const years = mapSeries.data?.years || [];
  const activeYear = resolveActiveMapYear(years, mapYear, mapSeries.data?.values_by_year);
  const yearItems = useMemo(
    () => worldYearItems(mapSeries.data, activeYear),
    [mapSeries.data, activeYear],
  );
  const ranking = useMemo(() => worldRankingFromYearItems(yearItems, 8), [yearItems]);
  const valuesByCode = useMemo(
    () => new Map(Object.entries(yearItems).map(([code, item]) => [code, item.value])),
    [yearItems],
  );
  const detailsByCode = useMemo(() => new Map(Object.entries(yearItems)), [yearItems]);
  const benchmark = activeYear
    ? mapSeries.data?.benchmark_by_year?.[String(activeYear)]
    : null;

  return (
    <div data-block="home-workbench-countries">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-text-primary">{t('home.countries.title')}</h3>
          <p className="mt-1 max-w-xl text-xs leading-5 text-text-secondary">
            {t('home.countries.subtitle')}
          </p>
        </div>
        <Link
          to="/world"
          onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'world' })}
          className="inline-flex items-center gap-1 text-xs text-champagne hover:underline"
        >
          <Globe2 size={12} />
          {t('home.countries.catalog')}
          <ArrowRight size={12} />
        </Link>
      </div>

      <div className="mb-3 rounded-xl border border-champagne/15 bg-champagne/[0.06] px-3.5 py-2.5 text-xs leading-5 text-text-secondary">
        {coverage}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1" role="group" aria-label={t('home.countries.macroAria')}>
          {HOME_COUNTRY_MACROREGIONS.map((m) => (
            <button
              key={m.id}
              type="button"
              disabled={!m.available}
              title={m.available ? t(m.coverageNoteKey || 'home.macro.defaultCoverage') : t('home.countries.macroUnavailable')}
              onClick={() => {
                if (!m.available) return;
                setMacroregion(m.id);
                track(events.HOME_COUNTRIES_MACROREGION, { macroregion: m.id });
              }}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                m.id === activeMacro
                  ? 'bg-champagne/15 text-champagne'
                  : m.available
                    ? 'border border-border-subtle bg-surface text-text-secondary hover:text-text-primary'
                    : 'cursor-not-allowed border border-border-subtle/60 bg-surface/50 text-text-tertiary opacity-60'
              }`}
            >
              {t(m.labelKey)}
              {!m.available ? t('home.macro.soonSuffix') : ''}
            </button>
          ))}
        </div>
        <label className="min-w-[12rem] flex-1 sm:max-w-xs">
          <span className="sr-only">{t('home.countries.metricAria')}</span>
          <select
            value={concept}
            onChange={(e) => {
              setConcept(e.target.value);
              setMapYear(null);
              track(events.HOME_COUNTRIES_METRIC, { concept: e.target.value });
            }}
            className="w-full rounded-xl border border-border-subtle bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-border-champagne"
          >
            {(mapConcepts.length
              ? mapConcepts
              : [{ slug: concept, name: conceptName }]
            ).map((c) => (
              <option key={c.slug} value={c.slug}>
                {homeConceptLabel(c.slug, t, c.name)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {(countries.isError || mapSeries.isError) && (
        <ApiRetryBanner
          className="mb-4"
          onRetry={() => {
            countries.refetch();
            mapSeries.refetch();
          }}
          isFetching={countries.isFetching || mapSeries.isFetching}
        >
          {t('home.countries.loadError')}
        </ApiRetryBanner>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="order-1 rounded-2xl border border-border-subtle bg-surface p-4">
          <div className="mb-3 flex items-start justify-between gap-2">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-champagne">
                {t('home.map.rating')}
              </div>
              <div className="mt-1 text-sm font-semibold text-text-primary">
                {conceptName}
              </div>
              {activeYear != null && (
                <div className="mt-0.5 font-mono text-[10px] text-text-tertiary">
                  {t('world.yearLabel', { year: activeYear })}
                </div>
              )}
            </div>
          </div>
          {benchmark?.value != null && (
            <div className="mb-3 rounded-lg bg-champagne/[0.08] px-3 py-2">
              <div className="text-[10px] text-text-tertiary">{benchmark.label}</div>
              <div className="font-mono text-sm font-semibold text-text-primary">
                {formatWorldValue(benchmark.value)}
              </div>
            </div>
          )}
          {mapSeries.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonBox key={i} className="h-8 rounded-lg" />
              ))}
            </div>
          ) : (
            <ol className="space-y-1">
              {ranking.map((item, index) => (
                <li key={item.country_slug}>
                  <Link
                    to={item.indicator_code
                      ? indicatorPath(item.country_slug, item.indicator_code)
                      : countryPath(item.country_slug)}
                    className="group flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-surface-hover"
                  >
                    <span className="w-5 font-mono text-[10px] text-text-tertiary">{index + 1}</span>
                    <span className="min-w-0 flex-1 truncate text-sm text-text-primary group-hover:text-champagne">
                      {item.country_name}
                    </span>
                    <span className="font-mono text-xs font-semibold tabular-nums text-text-primary">
                      {formatWorldValue(item.value)}
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            {fullRatingHref && (
              <Link
                to={fullRatingHref}
                onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'rating', concept })}
                className="inline-flex items-center gap-1 text-xs text-champagne hover:underline"
              >
                {t('world.fullRating')}
                <ArrowRight size={12} />
              </Link>
            )}
            {ranking.length >= 2 && (
              <Link
                to={`/compare?codes=${encodeURIComponent(
                  ranking.slice(0, 2).map((item) => `w:${item.country_slug}:${concept}`).join(','),
                )}`}
                onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'compare', concept })}
                className="inline-flex items-center gap-1 text-xs text-champagne hover:underline"
              >
                {t('home.countries.compare')}
                <ArrowRight size={12} />
              </Link>
            )}
          </div>
        </div>

        <div className="order-2 rounded-2xl border border-border-subtle bg-surface p-3 sm:p-4">
          {mapSeries.isLoading || countries.isLoading ? (
            <SkeletonBox className="aspect-[2/1] w-full rounded-xl" />
          ) : (
            <Suspense fallback={<SkeletonBox className="aspect-[2/1] w-full rounded-xl" />}>
              <WorldMap
                countries={countries.data?.countries || []}
                valuesByCode={valuesByCode}
                detailsByCode={detailsByCode}
                unit={mapSeries.data?.concept?.unit || ''}
                metricName={conceptName}
                periodLabel={activeYear ? String(activeYear) : ''}
                colorMode={concept === 'budget-balance-gdp' ? 'diverging' : 'auto'}
                onSelect={(country, detail) => {
                  track(events.HOME_COUNTRIES_CTA, {
                    target: 'map',
                    country: country.slug,
                    concept,
                  });
                  navigate(
                    detail?.indicator_code
                      ? indicatorPath(country.slug, detail.indicator_code)
                      : countryPath(country.slug),
                  );
                }}
              />
              {years.length > 1 && activeYear != null && (
                <MapTimeline
                  years={years}
                  year={activeYear}
                  onYearChange={setMapYear}
                  metric={`home-world:${concept}`}
                />
              )}
            </Suspense>
          )}
          {macros.length === 1 && (
            <p className="mt-3 text-[11px] leading-5 text-text-tertiary">
              {t('home.countries.comingSoonNote')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
