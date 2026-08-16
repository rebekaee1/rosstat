import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowUpDown, BarChart3, ChevronRight, Globe2, MapPinned, SlidersHorizontal, Table2,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  formatWorldValue,
  pluralRu,
  useWorldCountries,
  useWorldMapSeries,
  useWorldRatingConcepts,
} from '../lib/worldApi';
import {
  DEFAULT_HOME_COUNTRY_CONCEPT,
  HOME_COUNTRY_CONCEPT_SHORT,
  resolveActiveMapYear,
  russiaDeepLinksForConcept,
  russiaNoteForConcept,
  withRussiaOnHomeMap,
  worldRankingFromYearItems,
  worldRatingTitle,
  worldYearItems,
} from '../lib/homeWorkbench';
import { formatDate } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import Breadcrumbs from '../components/Breadcrumbs';
import TelemetryCard from '../components/TelemetryCard';
import WorldConceptPicker from '../components/WorldConceptPicker';
import WorldMap from '../components/WorldMap';
import MapTimeline from '../components/MapTimeline';
import { worldRatingTrail } from '../lib/breadcrumbs';
import {
  countryPath,
  indicatorPath,
  worldRatingPath,
} from '../lib/sitePaths';

// Направление сортировки по умолчанию приходит с сервера вместе со списком
// показателей; локальный набор — только фолбэк на время загрузки списка.
const SORT_ASC_CONCEPTS = new Set(['unemployment-rate', 'long-term-interest-rate']);

function defaultSortForConcept(slug, concepts) {
  const known = concepts?.find((item) => item.slug === slug);
  if (known?.default_sort === 'asc' || known?.default_sort === 'desc') {
    return known.default_sort;
  }
  return SORT_ASC_CONCEPTS.has(slug) ? 'asc' : 'desc';
}

function ButtonClass(active) {
  return [
    'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
    active
      ? 'bg-champagne/15 text-champagne'
      : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
  ].join(' ');
}

function rowHref(item, russiaLinks) {
  if (item?.country_code === 'RU' || item?.country_slug === 'russia') {
    return russiaLinks.countryHref;
  }
  if (!item?.country_slug) return '/world';
  if (item.indicator_code) {
    return indicatorPath(item.country_slug, item.indicator_code);
  }
  return countryPath(item.country_slug);
}

export default function WorldRatingPage() {
  const { conceptSlug } = useParams();
  const navigate = useNavigate();
  const activeConcept = conceptSlug || DEFAULT_HOME_COUNTRY_CONCEPT;
  const [selectedYear, setSelectedYear] = useState(null);
  const [sortDirection, setSortDirection] = useState(() => defaultSortForConcept(activeConcept));

  const countriesQ = useWorldCountries();
  const catalogQ = useWorldRatingConcepts();
  const mapSeriesQ = useWorldMapSeries(activeConcept);

  useEffect(() => {
    if (!conceptSlug) {
      navigate(worldRatingPath(DEFAULT_HOME_COUNTRY_CONCEPT), { replace: true });
    }
  }, [conceptSlug, navigate]);

  const concepts = useMemo(
    () => (catalogQ.data?.concepts || []).map((item) => ({
      slug: item.slug,
      name: item.name,
      unit: item.unit,
      default_sort: item.default_sort,
    })),
    [catalogQ.data],
  );

  useEffect(() => {
    setSortDirection(defaultSortForConcept(activeConcept, concepts));
  }, [activeConcept, concepts]);

  const concept = useMemo(
    () => concepts.find((item) => item.slug === activeConcept)
      || mapSeriesQ.data?.concept
      || { slug: activeConcept, name: HOME_COUNTRY_CONCEPT_SHORT[activeConcept] || 'Рейтинг стран', unit: '' },
    [activeConcept, concepts, mapSeriesQ.data],
  );
  const knownConceptLoaded = !catalogQ.isLoading && concepts.length > 0;
  const unknownConcept = knownConceptLoaded && !concepts.some((item) => item.slug === activeConcept);
  const years = mapSeriesQ.data?.years || [];
  const activeYear = resolveActiveMapYear(years, selectedYear, mapSeriesQ.data?.values_by_year);
  const baseYearItems = useMemo(
    () => worldYearItems(mapSeriesQ.data, activeYear),
    [mapSeriesQ.data, activeYear],
  );
  const {
    countries,
    yearItems,
    russiaIndicatorCode,
  } = useMemo(
    () => withRussiaOnHomeMap({
      countries: countriesQ.data?.countries || [],
      yearItems: baseYearItems,
      mapSeries: mapSeriesQ.data,
    }),
    [countriesQ.data, baseYearItems, mapSeriesQ.data],
  );
  const russiaLinks = useMemo(
    () => russiaDeepLinksForConcept(activeConcept),
    [activeConcept],
  );
  const russiaNote = mapSeriesQ.data?.concept?.russia?.note
    || russiaNoteForConcept(activeConcept);
  const russiaInRanking = Boolean(yearItems.RU?.value != null);
  const valuesByCode = useMemo(
    () => new Map(Object.entries(yearItems).map(([countryCode, item]) => [countryCode, item.value])),
    [yearItems],
  );
  const detailsByCode = useMemo(
    () => new Map(Object.entries(yearItems)),
    [yearItems],
  );
  const ranked = useMemo(() => {
    const rows = worldRankingFromYearItems(yearItems, Number.MAX_SAFE_INTEGER);
    if (sortDirection === 'asc') rows.reverse();
    return rows.map((item, index) => ({ ...item, rank: index + 1 }));
  }, [yearItems, sortDirection]);
  const withoutData = useMemo(() => {
    const withData = new Set(Object.values(yearItems).map((item) => item.country_code));
    return countries.filter((country) => !withData.has(country.code));
  }, [countries, yearItems]);

  // Единица одна на всю таблицу — уносим её в шапку колонки: иначе строка
  // повторяет «изменение за год, %» сорок один раз подряд.
  const sharedUnit = useMemo(() => {
    const units = new Set(ranked.map((item) => (item.unit || concept.unit || '').trim()));
    return units.size === 1 ? [...units][0] : null;
  }, [ranked, concept.unit]);
  const valueHeader = useMemo(() => {
    if (!sharedUnit) return 'Значение';
    if (sharedUnit.startsWith('%')) return `Значение, ${sharedUnit}`;
    return sharedUnit[0].toUpperCase() + sharedUnit.slice(1);
  }, [sharedUnit]);
  // Месячный ряд относится к месяцу целиком: «1 декабря 2025» врёт про день замера.
  const periodGranularity = useMemo(() => {
    const dates = ranked.map((item) => item.date).filter(Boolean);
    if (!dates.length) return 'day';
    if (dates.every((d) => d.endsWith('-01-01'))) return 'annual';
    if (dates.every((d) => d.slice(8) === '01')) return 'full';
    return 'day';
  }, [ranked]);

  const loading = countriesQ.isLoading || catalogQ.isLoading || mapSeriesQ.isLoading;
  const error = countriesQ.isError || catalogQ.isError || mapSeriesQ.isError;
  const retry = () => {
    countriesQ.refetch();
    catalogQ.refetch();
    mapSeriesQ.refetch();
  };

  const shortName = HOME_COUNTRY_CONCEPT_SHORT[activeConcept] || concept.name;
  const pageTitle = worldRatingTitle(activeConcept, concept.name || shortName, activeYear);
  useDocumentMeta({
    title: pageTitle,
    description:
      `${pageTitle}: полная таблица, карта и выбор порядка сортировки. `
      + 'Официальные источники, данные в единицах публикации.',
    path: worldRatingPath(activeConcept),
  });

  const openCountry = (country, detail) => {
    if (country?.code === 'RU' || country?.slug === 'russia') {
      navigate(russiaLinks.countryHref);
      return;
    }
    if (detail?.indicator_code && country?.slug) {
      navigate(indicatorPath(country.slug, detail.indicator_code));
      return;
    }
    if (country?.slug) navigate(countryPath(country.slug));
  };

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs
        items={worldRatingTrail(shortName || concept.name || 'Рейтинг', activeConcept)}
      />

      <header className="mb-4">
        <div className="mb-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
          <Globe2 size={14} />
          Рейтинг стран
        </div>
        <h1 className="max-w-4xl font-display text-2xl font-bold leading-tight text-text-primary sm:text-3xl lg:text-4xl">
          {pageTitle}
        </h1>
        <p className="mt-2 max-w-3xl text-xs leading-5 text-text-secondary sm:text-sm sm:leading-6">
          Выберите показатель и год. Для цен на карте и в таблице — изменение за год
          в процентах, а не уровень индекса. Карта показывает пространственный срез,
          таблица ниже — все страны с опубликованным значением за выбранный год.
        </p>
      </header>

      {error && (
        <ApiRetryBanner onRetry={retry} retrying={countriesQ.isFetching || catalogQ.isFetching || mapSeriesQ.isFetching} className="mb-6">
          Не удалось загрузить рейтинг стран. Проверьте соединение и попробуйте снова.
        </ApiRetryBanner>
      )}

      {unknownConcept && (
        <div className="mb-8 rounded-2xl border border-border-subtle bg-surface p-6">
          <h2 className="font-display text-xl font-semibold text-text-primary">Показатель не найден</h2>
          <p className="mt-2 text-sm text-text-secondary">
            Для рейтингов доступны только курируемые межстрановые показатели.
          </p>
          <Link to={worldRatingPath(DEFAULT_HOME_COUNTRY_CONCEPT)} className="mt-4 inline-flex rounded-xl bg-champagne px-4 py-2.5 text-sm font-semibold text-white">
            Открыть рейтинг по безработице
          </Link>
        </div>
      )}

      {!unknownConcept && (
        <>
          <section className="mb-4 rounded-2xl border border-border-subtle bg-surface px-3.5 py-3 shadow-sm sm:px-4">
            <WorldConceptPicker
              concepts={concepts}
              value={activeConcept}
              mode="link"
              linkForSlug={(slug) => worldRatingPath(slug)}
              label="Показатель рейтинга"
            />
            {loading && concepts.length === 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {[0, 1, 2].map((i) => (
                  <SkeletonBox key={i} className="h-7 w-24 rounded-xl" />
                ))}
              </div>
            )}
            <div className="mt-2.5 flex flex-wrap items-end gap-3 border-t border-border-subtle pt-2.5">
              <label className="block min-w-[8rem] flex-1 sm:max-w-[11rem]">
                <span className="mb-1 flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.16em] text-text-tertiary">
                  <SlidersHorizontal size={11} className="text-champagne" />
                  Год
                </span>
                <select
                  value={activeYear || ''}
                  onChange={(event) => setSelectedYear(Number(event.target.value))}
                  disabled={!years.length}
                  className="h-9 w-full rounded-xl border border-border-subtle bg-obsidian-light px-2.5 text-sm font-medium text-text-primary outline-none transition-colors focus:border-border-champagne"
                >
                  {years.map((year) => (
                    <option key={year} value={year}>{year}</option>
                  ))}
                </select>
              </label>
              <div className="min-w-0">
                <p className="mb-1 text-[10px] font-mono uppercase tracking-[0.16em] text-text-tertiary">
                  Порядок
                </p>
                <div className="flex flex-wrap gap-1.5">
                  <button type="button" className={ButtonClass(sortDirection === 'desc')} onClick={() => setSortDirection('desc')}>
                    По убыванию
                  </button>
                  <button type="button" className={ButtonClass(sortDirection === 'asc')} onClick={() => setSortDirection('asc')}>
                    По возрастанию
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section className="mb-5 grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(min(100%,24rem),0.85fr)]">
            <div className="rounded-[1.5rem] border border-border-subtle bg-surface p-3 shadow-[0_16px_45px_rgba(35,30,16,0.05)] sm:p-5">
              {mapSeriesQ.isLoading ? (
                <SkeletonBox className="aspect-[2/1] w-full rounded-2xl" />
              ) : (
                <>
                  <WorldMap
                    countries={countries}
                    valuesByCode={valuesByCode}
                    detailsByCode={detailsByCode}
                    unit={concept.unit || mapSeriesQ.data?.concept?.unit || ''}
                    metricName={shortName}
                    periodLabel={activeYear ? String(activeYear) : ''}
                    colorMode={activeConcept === 'budget-balance-gdp' ? 'diverging' : 'auto'}
                    defaultScope="world"
                    onSelect={openCountry}
                  />
                  {years.length > 1 && activeYear && (
                    <MapTimeline
                      years={years}
                      year={activeYear}
                      onYearChange={setSelectedYear}
                      metric={`world-rating:${activeConcept}`}
                    />
                  )}
                </>
              )}
            </div>

            <aside className="rounded-[1.5rem] border border-border-subtle bg-surface p-5">
              <div className="mb-4 flex items-start gap-3">
                <BarChart3 size={18} className="mt-1 shrink-0 text-champagne" />
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">Сводка</p>
                  <h2 className="mt-1 font-display text-xl font-semibold text-text-primary">
                    {shortName}{activeYear ? `, ${activeYear}` : ''}
                  </h2>
                </div>
              </div>
              <p className="text-sm leading-6 text-text-secondary">
                В таблице участвуют {ranked.length} {pluralRu(ranked.length, ['страна', 'страны', 'стран'])}
                {' '}из {countries.length}. Страны без значения за выбранный год показаны отдельным списком
                ниже, чтобы охват рейтинга был виден сразу.
                {russiaInRanking
                  ? ' Россия включена по национальному ряду того же смысла.'
                  : ' России в этом рейтинге нет: сопоставимого ряда в той же единице нет.'}
              </p>
              <div className="mt-4 rounded-xl bg-obsidian-light px-3.5 py-3 text-xs leading-5 text-text-secondary">
                {activeConcept === 'hicp-index' || mapSeriesQ.data?.concept?.value_mode === 'yoy'
                  ? 'Для потребительских цен сравнивается изменение за год в процентах: базовые периоды национальных индексов при делении сокращаются, поэтому страны сопоставимы. Денежные ряды в национальных валютах в рейтинг не входят.'
                  : 'В рейтинг попадают только показатели, которые можно честно сравнить между странами в одной единице. Денежные ряды в национальных валютах сюда не входят.'}
              </div>
              {russiaNote && (
                <div className="mt-3 rounded-xl border border-border-subtle bg-white/60 px-3.5 py-3 text-xs leading-5 text-text-secondary">
                  {russiaNote}
                </div>
              )}
              <div className="mt-4 space-y-2 border-t border-border-subtle pt-4">
                <p className="text-[10px] font-mono uppercase tracking-[0.16em] text-text-tertiary">
                  Россия и регионы
                </p>
                <div className="flex flex-wrap gap-2">
                  <Link
                    to={russiaLinks.countryHref}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-champagne/15 px-3 py-2 text-xs font-medium text-champagne"
                  >
                    <Globe2 size={13} />
                    {russiaIndicatorCode ? 'Показатель России' : 'Раздел России'}
                  </Link>
                  <Link
                    to={russiaLinks.regionsHref}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-obsidian-lighter px-3 py-2 text-xs font-medium text-text-secondary hover:text-champagne"
                  >
                    <MapPinned size={13} />
                    Регионы России
                  </Link>
                  {russiaLinks.regionRatingHref && (
                    <Link
                      to={russiaLinks.regionRatingHref}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-obsidian-lighter px-3 py-2 text-xs font-medium text-text-secondary hover:text-champagne"
                    >
                      Региональный рейтинг
                    </Link>
                  )}
                </div>
              </div>
            </aside>
          </section>

          <section className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4 md:gap-4">
            <TelemetryCard label="Стран с данными" value={ranked.length} unit={pluralRu(ranked.length, ['страна', 'страны', 'стран'])} valueDigits={0} meta={activeYear ? `${activeYear} ГОД` : undefined} delay={0} />
            <TelemetryCard label="Без данных" value={withoutData.length} unit={pluralRu(withoutData.length, ['страна', 'страны', 'стран'])} valueDigits={0} meta="В ВЫБРАННОМ ГОДУ" delay={1} />
            <TelemetryCard label="Всего стран" value={countries.length} unit={pluralRu(countries.length, ['страна', 'страны', 'стран'])} valueDigits={0} meta="В МИРОВОМ КАТАЛОГЕ" delay={2} />
            <TelemetryCard label="Доступно лет" value={years.length} unit={pluralRu(years.length, ['год', 'года', 'лет'])} valueDigits={0} meta={years.length ? `${years[0]}–${years[years.length - 1]}` : undefined} delay={3} />
          </section>

          <section className="mb-8">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
                  Полная таблица
                </p>
                <h2 className="mt-1 font-display text-2xl font-bold text-text-primary">
                  Все страны с данными ({ranked.length})
                </h2>
              </div>
              <div className="inline-flex items-center gap-2 rounded-xl bg-obsidian-light px-3 py-2 text-xs text-text-secondary">
                <ArrowUpDown size={14} className="text-champagne" />
                {sortDirection === 'desc' ? 'Значение по убыванию' : 'Значение по возрастанию'}
              </div>
            </div>
            <div className="overflow-x-auto rounded-2xl border border-border-subtle bg-surface">
              <table className="w-full min-w-[52rem] text-sm">
                <thead className="sticky top-0 z-10 bg-obsidian-light/95 backdrop-blur-sm">
                  <tr className="text-left text-[11px] uppercase tracking-wide text-text-tertiary">
                    <th className="w-20 px-4 py-3 font-medium">Место</th>
                    <th className="px-4 py-3 font-medium">Страна</th>
                    <th className="px-4 py-3 text-right font-medium">{valueHeader}</th>
                    {!sharedUnit && <th className="px-4 py-3 font-medium">Единица</th>}
                    <th className="px-4 py-3 font-medium">Период</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((item) => (
                    <tr key={item.country_code} className="border-t border-border-subtle transition-colors hover:bg-surface-hover">
                      <td className="px-4 py-3 font-mono text-text-tertiary">{item.rank}</td>
                      <td className="px-4 py-3">
                        <Link to={rowHref(item, russiaLinks)} className="font-medium text-text-primary transition-colors hover:text-champagne">
                          {item.country_name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-semibold tabular-nums text-text-primary">
                        {formatWorldValue(item.value)}
                      </td>
                      {!sharedUnit && (
                        <td className="px-4 py-3 text-xs text-text-secondary">
                          {item.unit || concept.unit || 'единицы источника'}
                        </td>
                      )}
                      <td className="px-4 py-3 font-mono text-xs text-text-tertiary">
                        {item.date ? formatDate(item.date, periodGranularity) : '—'}
                      </td>
                    </tr>
                  ))}
                  {!loading && ranked.length === 0 && (
                    <tr>
                      <td colSpan={sharedUnit ? 4 : 5} className="px-4 py-8 text-center text-text-secondary">
                        За выбранный год нет данных для рейтинга.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-[1.5rem] border border-border-subtle bg-surface p-5">
            <div className="mb-3 flex items-center gap-2">
              <Table2 size={17} className="text-champagne" />
              <h2 className="font-display text-xl font-semibold text-text-primary">
                Страны без данных за {activeYear || 'выбранный год'} ({withoutData.length})
              </h2>
            </div>
            {withoutData.length > 0 ? (
              <div className="flex max-h-48 flex-wrap gap-2 overflow-y-auto pr-1">
                {withoutData.map((country) => (
                  <Link
                    key={country.slug}
                    to={country.code === 'RU' ? russiaLinks.countryHref : countryPath(country.slug)}
                    className="rounded-xl bg-obsidian-light px-3 py-2 text-xs text-text-secondary transition-colors hover:text-champagne"
                  >
                    {country.name}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-sm text-text-secondary">
                Все страны мирового каталога имеют значение за выбранный год.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
