import { lazy, Suspense, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Globe2, MapPinned, Landmark } from 'lucide-react';
import {
  DEFAULT_HOME_COUNTRY_CONCEPT,
  HOME_MAP_SIDE_LINKS,
  homeConceptLabel,
  resolveActiveMapYear,
  withRussiaOnHomeMap,
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
import WorldConceptPicker from '../WorldConceptPicker';
import { track, events } from '../../lib/track';
import {
  countryPath,
  indicatorPath,
  russiaIndicatorPath,
  todayPath,
} from '../../lib/sitePaths';
import { useT } from '../../i18n';

const WorldMap = lazy(() => import('../WorldMap'));
const MapTimeline = lazy(() => import('../MapTimeline'));

const SIDE_ICONS = {
  'russia-macro': Landmark,
  regions: MapPinned,
  world: Globe2,
};

/**
 * Главная: одна большая карта мира + боковые переходы.
 * Россия накладывается поверх world API (её нет в Eurostat-plane).
 */
export default function HomeWorkbench({ indicators = [] }) {
  const t = useT();
  const navigate = useNavigate();
  const [concept, setConcept] = useState(DEFAULT_HOME_COUNTRY_CONCEPT);
  const [mapYear, setMapYear] = useState(null);

  const countriesQ = useWorldCountries();
  const catalog = useWorldCompareCatalog();
  const mapSeries = useWorldMapSeries(concept);
  const ratingConcepts = useWorldRatingConcepts();
  const fullRatingHref = ratingHref(concept, ratingConcepts.data?.concepts);

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
  }, [catalog.data, ratingConcepts.data]);

  const years = mapSeries.data?.years || [];
  const activeYear = resolveActiveMapYear(years, mapYear, mapSeries.data?.values_by_year);
  const baseYearItems = useMemo(
    () => worldYearItems(mapSeries.data, activeYear),
    [mapSeries.data, activeYear],
  );

  const { countries, yearItems, russiaIndicatorCode } = useMemo(
    () => withRussiaOnHomeMap({
      countries: countriesQ.data?.countries || [],
      yearItems: baseYearItems,
      mapSeries: mapSeries.data,
    }),
    [countriesQ.data, baseYearItems, mapSeries.data],
  );

  const ranking = useMemo(() => worldRankingFromYearItems(yearItems, 8), [yearItems]);
  const conceptUnit = mapSeries.data?.concept?.unit || '';
  const conceptName = homeConceptLabel(
    concept,
    t,
    mapSeries.data?.concept?.name || t('home.map.metricFallback'),
  );
  const valuesByCode = useMemo(
    () => new Map(Object.entries(yearItems).map(([code, item]) => [code, item.value])),
    [yearItems],
  );
  const detailsByCode = useMemo(() => new Map(Object.entries(yearItems)), [yearItems]);
  const benchmark = activeYear
    ? mapSeries.data?.benchmark_by_year?.[String(activeYear)]
    : null;

  const onSelectCountry = (country, detail) => {
    track(events.HOME_COUNTRIES_MAP_SELECT, {
      code: country?.code,
      concept,
      year: activeYear,
    });
    if (country?.code === 'RU') {
      const code = detail?.indicator_code || russiaIndicatorCode;
      if (code) {
        navigate(russiaIndicatorPath(code));
        return;
      }
      navigate(todayPath());
      return;
    }
    if (detail?.indicator_code && country?.slug) {
      navigate(indicatorPath(country.slug, detail.indicator_code));
      return;
    }
    if (country?.slug) {
      navigate(countryPath(country.slug));
    }
  };

  return (
    <section
      data-block="home-workbench"
      className="mb-10 md:mb-12"
      aria-labelledby="home-world-map-title"
    >
      <div className="mb-3 min-w-0">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
          {t('home.map.eyebrow')}
        </div>
        <h2 id="home-world-map-title" className="mt-1 text-base font-semibold text-text-primary sm:text-lg">
          {t('home.map.title')}
        </h2>
        <p className="mt-1 max-w-2xl text-xs leading-5 text-text-secondary">
          {t('home.map.subtitle')}
        </p>
      </div>

      <div className="mb-4 min-w-0">
        <WorldConceptPicker
          concepts={mapConcepts.length
            ? mapConcepts
            : [{ slug: concept, name: conceptName }]}
          value={concept}
          onChange={(slug) => {
            setConcept(slug);
            setMapYear(null);
            track(events.HOME_COUNTRIES_METRIC, { concept: slug });
          }}
          label={t('home.map.metricLabel')}
        />
      </div>

      {(countriesQ.isError || mapSeries.isError) && (
        <ApiRetryBanner
          className="mb-4"
          onRetry={() => {
            countriesQ.refetch();
            mapSeries.refetch();
          }}
          isFetching={countriesQ.isFetching || mapSeries.isFetching}
        >
          {t('home.map.loadError')}
        </ApiRetryBanner>
      )}

      <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)] lg:items-start lg:gap-5">
        <div className="order-1 min-w-0 overflow-hidden rounded-2xl border border-border-subtle bg-surface p-2.5 sm:p-4 lg:order-2">
          {(countriesQ.isLoading || mapSeries.isLoading) ? (
            <SkeletonBox className="h-[18rem] w-full rounded-2xl sm:h-[28rem]" />
          ) : (
            <Suspense fallback={<SkeletonBox className="h-[18rem] w-full rounded-2xl sm:h-[28rem]" />}>
              <WorldMap
                countries={countries}
                valuesByCode={valuesByCode}
                detailsByCode={detailsByCode}
                unit={conceptUnit}
                metricName={conceptName}
                periodLabel={activeYear ? String(activeYear) : ''}
                colorMode={concept === 'budget-balance-gdp' ? 'diverging' : 'auto'}
                defaultScope="world"
                onSelect={onSelectCountry}
              />
              {years.length > 1 && activeYear != null && (
                <div className="mt-3 px-0.5 sm:mt-4 sm:px-1">
                  <MapTimeline
                    years={years}
                    year={activeYear}
                    onYearChange={setMapYear}
                    metric={`home-world:${concept}`}
                  />
                </div>
              )}
            </Suspense>
          )}
        </div>

        <div className="order-2 flex min-w-0 flex-col gap-3 lg:order-1 lg:sticky lg:top-24 lg:max-h-[calc(100vh-7.5rem)] lg:gap-2 lg:overflow-y-auto lg:pr-0.5">
          <nav
            aria-label={t('home.map.navAria')}
            className="grid grid-cols-2 gap-2 lg:flex lg:flex-col"
          >
            {HOME_MAP_SIDE_LINKS.map((link) => {
              const Icon = SIDE_ICONS[link.id] || Globe2;
              return (
                <Link
                  key={link.id}
                  to={link.to}
                  onClick={(e) => {
                    track(events.HOME_COUNTRIES_CTA, { target: link.id });
                    if (link.scrollId) {
                      e.preventDefault();
                      const el = document.getElementById(link.scrollId);
                      if (el) {
                        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        try {
                          window.history.replaceState(null, '', `#${link.scrollId}`);
                        } catch { /* noop */ }
                      }
                    }
                  }}
                  className="group min-w-0 rounded-2xl border border-border-subtle bg-surface px-3 py-2.5 transition-all hover:border-border-champagne hover:shadow-sm sm:px-3.5 sm:py-3"
                >
                  <div className="flex items-start gap-2 sm:gap-2.5">
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-champagne/10 text-champagne">
                      <Icon size={15} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center justify-between gap-1 text-[13px] font-semibold leading-snug text-text-primary group-hover:text-champagne sm:text-sm">
                        <span className="min-w-0">{t(link.labelKey)}</span>
                        <ArrowRight size={13} className="hidden shrink-0 opacity-50 transition group-hover:opacity-100 sm:block" />
                      </span>
                      <span className="mt-0.5 line-clamp-2 block text-[11px] leading-snug text-text-tertiary">
                        {t(link.descriptionKey)}
                      </span>
                    </span>
                  </div>
                </Link>
              );
            })}
          </nav>

          <div className="shrink-0 rounded-2xl border border-border-subtle bg-obsidian-light/40 px-3.5 py-3">
            <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-champagne">
              {t('home.map.rating')}
            </div>
            <div className="mt-1 text-xs font-semibold text-text-primary">
              {conceptName}
            </div>
            <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 font-mono text-[10px] text-text-tertiary">
              {activeYear != null && <span>{t('world.yearLabel', { year: activeYear })}</span>}
              {conceptUnit ? <span>{conceptUnit}</span> : null}
            </div>
            {benchmark?.value != null && (
              <div className="mt-2 rounded-lg bg-champagne/[0.08] px-2.5 py-1.5">
                <div className="text-[10px] text-text-tertiary">{benchmark.label}</div>
                <div className="font-mono text-sm font-semibold text-text-primary">
                  {formatWorldValue(benchmark.value)}
                </div>
              </div>
            )}
            <ol className="mt-2 space-y-1">
              {ranking.length === 0 && (
                <li className="text-[11px] text-text-tertiary">{t('home.map.noDataYear')}</li>
              )}
              {ranking.map((item, idx) => (
                <li key={item.country_code || item.country_slug || idx}>
                  <button
                    type="button"
                    onClick={() => onSelectCountry(
                      {
                        code: item.country_code,
                        slug: item.country_slug,
                        name: item.country_name,
                      },
                      item,
                    )}
                    className="grid w-full grid-cols-[1.5rem_minmax(0,1fr)_auto] items-baseline gap-1.5 rounded-lg px-1 py-0.5 text-left hover:bg-champagne/10"
                  >
                    <span className="font-mono text-[11px] text-text-tertiary">{idx + 1}.</span>
                    <span className="min-w-0 text-[11px] leading-snug text-text-secondary">
                      {item.country_name}
                    </span>
                    <span className="font-mono text-[11px] font-semibold tabular-nums text-text-primary">
                      {formatWorldValue(item.value)}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
            {fullRatingHref && (
              <Link
                to={fullRatingHref}
                onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'rating', concept })}
                className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-champagne hover:underline"
              >
                {t('home.map.fullRating')}
                <ArrowRight size={12} />
              </Link>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
