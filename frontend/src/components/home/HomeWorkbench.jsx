import { lazy, Suspense, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Globe2, MapPinned, Landmark } from 'lucide-react';
import {
  DEFAULT_HOME_COUNTRY_CONCEPT,
  HOME_COUNTRY_CONCEPT_SHORT,
  HOME_MAP_SIDE_LINKS,
  resolveActiveMapYear,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
  worldYearItems,
} from '../../lib/homeWorkbench';
import {
  formatWorldValue,
  useWorldCompareCatalog,
  useWorldCountries,
  useWorldMapSeries,
} from '../../lib/worldApi';
import { SkeletonBox } from '../Skeleton';
import ApiRetryBanner from '../ApiRetryBanner';
import { track, events } from '../../lib/track';

const WorldMap = lazy(() => import('../WorldMap'));
const MapTimeline = lazy(() => import('../MapTimeline'));

const SIDE_ICONS = {
  'russia-macro': Landmark,
  regions: MapPinned,
  europe: Globe2,
  world: Globe2,
};

/**
 * Главная: одна большая карта мира + боковые переходы.
 * Россия накладывается поверх world API (её нет в Eurostat-plane).
 */
export default function HomeWorkbench({ indicators = [] }) {
  const navigate = useNavigate();
  const [concept, setConcept] = useState(DEFAULT_HOME_COUNTRY_CONCEPT);
  const [mapYear, setMapYear] = useState(null);

  const countriesQ = useWorldCountries();
  const catalog = useWorldCompareCatalog();
  const mapSeries = useWorldMapSeries(concept);

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
  const baseYearItems = useMemo(
    () => worldYearItems(mapSeries.data, activeYear),
    [mapSeries.data, activeYear],
  );

  const { countries, yearItems, russiaIndicatorCode } = useMemo(
    () => withRussiaOnHomeMap({
      countries: countriesQ.data?.countries || [],
      yearItems: baseYearItems,
      indicators,
      conceptSlug: concept,
      activeYear,
    }),
    [countriesQ.data, baseYearItems, indicators, concept, activeYear],
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

  const onSelectCountry = (country, detail) => {
    track(events.HOME_COUNTRIES_MAP_SELECT, {
      code: country?.code,
      concept,
      year: activeYear,
    });
    if (country?.code === 'RU') {
      const code = detail?.indicator_code || russiaIndicatorCode;
      if (code) {
        navigate(`/indicator/${code}`);
        return;
      }
      navigate('/today');
      return;
    }
    if (detail?.indicator_code && country?.slug) {
      navigate(`/world/${country.slug}/${detail.indicator_code}`);
      return;
    }
    if (country?.slug) {
      navigate(`/world/${country.slug}`);
    }
  };

  return (
    <section
      data-block="home-workbench"
      className="mb-10 md:mb-12"
      aria-labelledby="home-world-map-title"
    >
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
            Карта мира
          </div>
          <h2 id="home-world-map-title" className="mt-1 text-base font-semibold text-text-primary sm:text-lg">
            Страны и показатели
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-text-secondary">
            Выберите показатель и год, откройте страну на карте. Россия включена
            в срез по национальным рядам; зарубежные страны — по официальным
            источникам раздела «Мир».
          </p>
        </div>
        <label className="relative block w-full min-w-0 sm:max-w-xs sm:min-w-[12rem]">
          <span className="sr-only">Показатель карты</span>
          <select
            value={concept}
            onChange={(e) => {
              setConcept(e.target.value);
              setMapYear(null);
              track(events.HOME_COUNTRIES_METRIC, { concept: e.target.value });
            }}
            className="h-10 w-full appearance-none rounded-xl border border-border-subtle bg-surface py-0 pl-3 pr-9 text-sm leading-none text-text-primary outline-none focus:border-border-champagne"
          >
            {(mapConcepts.length
              ? mapConcepts
              : [{ slug: concept, name: HOME_COUNTRY_CONCEPT_SHORT[concept] || concept }]
            ).map((c) => (
              <option key={c.slug} value={c.slug}>
                {HOME_COUNTRY_CONCEPT_SHORT[c.slug] || c.name}
              </option>
            ))}
          </select>
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-text-tertiary"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2.5 4.5L6 8l3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </label>
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
          Не удалось загрузить карту стран.
        </ApiRetryBanner>
      )}

      <div className="grid gap-4 lg:grid-cols-[14rem_minmax(0,1fr)] lg:items-start lg:gap-5">
        <div className="order-1 min-w-0 overflow-hidden rounded-2xl border border-border-subtle bg-surface p-2.5 sm:p-4 lg:order-2">
          {(countriesQ.isLoading || mapSeries.isLoading) ? (
            <SkeletonBox className="h-[18rem] w-full rounded-2xl sm:h-[28rem]" />
          ) : (
            <Suspense fallback={<SkeletonBox className="h-[18rem] w-full rounded-2xl sm:h-[28rem]" />}>
              <WorldMap
                countries={countries}
                valuesByCode={valuesByCode}
                detailsByCode={detailsByCode}
                unit={mapSeries.data?.concept?.unit || ''}
                metricName={HOME_COUNTRY_CONCEPT_SHORT[concept] || mapSeries.data?.concept?.name || ''}
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
            aria-label="Переходы по разделам"
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
                        <span className="min-w-0">{link.label}</span>
                        <ArrowRight size={13} className="hidden shrink-0 opacity-50 transition group-hover:opacity-100 sm:block" />
                      </span>
                      <span className="mt-0.5 line-clamp-2 block text-[11px] leading-snug text-text-tertiary">
                        {link.description}
                      </span>
                    </span>
                  </div>
                </Link>
              );
            })}
          </nav>

          <div className="shrink-0 rounded-2xl border border-border-subtle bg-obsidian-light/40 px-3.5 py-3">
            <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-champagne">
              Рейтинг
            </div>
            <div className="mt-1 text-xs font-semibold text-text-primary">
              {HOME_COUNTRY_CONCEPT_SHORT[concept] || mapSeries.data?.concept?.name || 'Показатель'}
            </div>
            {activeYear != null && (
              <div className="mt-0.5 font-mono text-[10px] text-text-tertiary">
                {activeYear} год
              </div>
            )}
            {benchmark?.value != null && (
              <div className="mt-2 rounded-lg bg-champagne/[0.08] px-2.5 py-1.5">
                <div className="text-[10px] text-text-tertiary">{benchmark.label}</div>
                <div className="font-mono text-sm font-semibold text-text-primary">
                  {formatWorldValue(benchmark.value)}
                </div>
              </div>
            )}
            <ol className="mt-2 space-y-1.5">
              {ranking.length === 0 && (
                <li className="text-[11px] text-text-tertiary">Нет данных за год</li>
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
                    className="flex w-full items-baseline justify-between gap-2 rounded-lg px-1 py-0.5 text-left hover:bg-champagne/10"
                  >
                    <span className="min-w-0 truncate text-[11px] text-text-secondary">
                      <span className="font-mono text-text-tertiary">{idx + 1}.</span>{' '}
                      {item.country_name}
                    </span>
                    <span className="shrink-0 font-mono text-[11px] font-semibold tabular-nums text-text-primary">
                      {formatWorldValue(item.value)}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
