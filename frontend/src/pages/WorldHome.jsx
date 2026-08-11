// Витрина мирового блока: /world
// Сетка стран по регионам + поиск по названию страны.
import { createElement, useMemo, useState, useDeferredValue } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Search, Globe2, ChevronRight, ArrowRight, BarChart3, Database, Layers3,
  CalendarRange, SlidersHorizontal,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useWorldCountries, useWorldCompareCatalog, useWorldMapSeries,
  groupCountriesByRegion, pluralRu, formatWorldValue,
} from '../lib/worldApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import useSearchTracking from '../lib/useSearchTracking';
import WorldMap from '../components/WorldMap';
import MapTimeline from '../components/MapTimeline';

const MAP_CONCEPT_SHORT = {
  'hicp-index': 'Потребительские цены',
  'unemployment-rate': 'Безработица',
  'gdp-volume-quarterly': 'ВВП, квартал',
  'gdp-volume-annual': 'ВВП, год',
  'budget-balance-gdp': 'Баланс бюджета',
  population: 'Население',
};

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

function CountryCard({ country, featured = false }) {
  return (
    <Link
      to={`/world/${country.slug}`}
      className={[
        'group flex items-center gap-3 border border-border-subtle bg-surface transition-all hover:-translate-y-0.5 hover:border-border-champagne hover:shadow-[0_18px_45px_rgba(38,33,20,0.08)]',
        featured ? 'rounded-2xl p-5' : 'rounded-xl px-4 py-3.5',
      ].join(' ')}
    >
      <CountryMark country={country} large={featured} />
      <div className="min-w-0 flex-1">
        <div className="font-medium text-text-primary text-[15px] leading-snug truncate group-hover:text-champagne transition-colors">
          {country.name}
        </div>
        <div className="mt-0.5 text-[11px] text-text-tertiary font-mono">
          {country.name_en}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-[13px] font-semibold tabular-nums text-text-primary">
          {formatWorldValue(country.indicators_count, 0)}
        </div>
        <div className="text-[10px] text-text-tertiary">
          {pluralRu(country.indicators_count, ['ряд', 'ряда', 'рядов'])}
        </div>
      </div>
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-obsidian-light transition-colors group-hover:bg-champagne/12">
        <ChevronRight size={14} className="text-text-tertiary group-hover:text-champagne transition-colors" />
      </div>
    </Link>
  );
}

export default function WorldHome() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch, isFetching } = useWorldCountries();
  const compareCatalog = useWorldCompareCatalog();
  const [query, setQuery] = useState('');
  const [mapConcept, setMapConcept] = useState('unemployment-rate');
  const [mapYear, setMapYear] = useState(null);
  const deferredQuery = useDeferredValue(query);
  const mapSeries = useWorldMapSeries(mapConcept);

  useDocumentMeta({
    title: 'Экономика стран Европы — показатели по данным Евростата',
    description:
      'Макроэкономические показатели 39 стран Европы: цены, рынок труда, национальные счета. Официальные данные Евростата, графики и история.',
    path: '/world',
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

  useSearchTracking('world-countries', deferredQuery, filtered.length);

  const byRegion = useMemo(() => groupCountriesByRegion(filtered), [filtered]);
  const total = data?.total ?? filtered.length;
  const totalIndicators = useMemo(
    () => (data?.countries || []).reduce((sum, country) => sum + Number(country.indicators_count || 0), 0),
    [data],
  );
  const mapConcepts = useMemo(() => {
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
  }, [compareCatalog.data]);
  const years = mapSeries.data?.years || [];
  const activeMapYear = years.includes(mapYear) ? mapYear : years[years.length - 1];
  const activeYearItems = useMemo(
    () => (activeMapYear
      ? (mapSeries.data?.values_by_year?.[String(activeMapYear)] || {})
      : {}),
    [activeMapYear, mapSeries.data],
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
    () => Object.values(activeYearItems).sort((a, b) => b.value - a.value),
    [activeYearItems],
  );
  const benchmark = activeMapYear
    ? mapSeries.data?.benchmark_by_year?.[String(activeMapYear)]
    : null;
  const fromMock = data?._fromMock;

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-24 pt-24 sm:px-6">
      <section className="relative mb-10 overflow-hidden rounded-[2rem] border border-border-subtle bg-surface px-6 py-8 shadow-[0_24px_80px_rgba(35,30,16,0.07)] sm:px-10 sm:py-11">
        <div className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-champagne/10 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-[28%] h-32 w-32 rounded-full bg-champagne/5 blur-2xl" />
        <div className="relative grid gap-10 lg:grid-cols-[1.35fr_0.65fr] lg:items-end">
          <div>
            <div className="mb-4 flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.22em] text-champagne">
              <Globe2 size={15} />
              Европейская экономика
            </div>
            <h1 className="max-w-3xl font-display text-4xl font-bold leading-[1.04] text-text-primary sm:text-5xl lg:text-[3.6rem]">
              Страны в одной системе координат
            </h1>
            <p className="mt-5 max-w-2xl text-[15px] leading-7 text-text-secondary sm:text-base">
              Официальные данные Евростата: цены, рынок труда, производство,
              национальные счета и демография. Открывайте страну или сопоставляйте
              методологически одинаковые ряды на одном графике.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <a href="#countries" className="magnetic-btn inline-flex items-center gap-2 rounded-xl bg-champagne px-4 py-2.5 text-sm font-semibold text-white shadow-sm">
                Выбрать страну
                <ArrowRight size={15} />
              </a>
              <Link to="/compare" className="inline-flex items-center gap-2 rounded-xl border border-border-subtle bg-white/70 px-4 py-2.5 text-sm font-medium text-text-primary transition-colors hover:border-border-champagne hover:text-champagne">
                <BarChart3 size={15} />
                Сравнить страны
              </Link>
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-champagne/15 bg-gradient-to-br from-champagne/[0.08] to-white/75 p-4 sm:p-5">
            <div className="mb-4 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
              <Database size={13} />
              Покрытие платформы
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              {[
                [Globe2, total || 39, pluralRu(total || 39, ['страна', 'страны', 'стран'])],
                [Database, formatWorldValue(totalIndicators, 0), 'публичных рядов'],
                [Layers3, mapConcepts.length || 6, 'сопоставимых показателей'],
                [CalendarRange, years.length ? `${years[0]}–${years[years.length - 1]}` : '—', 'период карты'],
              ].map(([Icon, value, label]) => (
                <div key={label} className="rounded-xl border border-white/80 bg-white/65 px-3 py-3 shadow-sm">
                  {createElement(Icon, { className: 'mb-2 h-3.5 w-3.5 text-champagne' })}
                  <div className="font-mono text-base font-semibold text-text-primary">{value}</div>
                  <div className="mt-0.5 text-[10px] leading-tight text-text-tertiary">{label}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 border-t border-champagne/10 pt-3 text-[11px] leading-5 text-text-secondary">
              От обзора страны можно перейти к динамике, режимам показателя и
              сопоставлению на одном графике.
            </div>
          </div>
        </div>
        {fromMock && (
          <p className="mt-2 text-[12px] text-text-tertiary font-mono">
            Демо-данные (API ещё не подключён)
          </p>
        )}
      </section>

      {!isLoading && !isError && (
        <section className="mb-12">
          <div className="mb-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)] lg:items-end">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">Срез по странам</div>
              <h2 className="mt-1 font-display text-2xl font-bold text-text-primary">Карта и рейтинг</h2>
              <p className="mt-2 max-w-xl text-xs leading-5 text-text-secondary">
                Выберите показатель и год. Карта показывает последнее опубликованное
                значение внутри выбранного календарного года.
              </p>
            </div>
            <label className="rounded-2xl border border-border-subtle bg-surface p-3 shadow-sm">
              <span className="mb-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.16em] text-text-tertiary">
                <SlidersHorizontal size={12} className="text-champagne" />
                Показатель карты
              </span>
              <select
                value={mapConcept}
                onChange={(event) => {
                  setMapConcept(event.target.value);
                  setMapYear(null);
                }}
                className="w-full rounded-xl border border-border-subtle bg-obsidian-light px-3 py-2.5 text-sm font-medium text-text-primary outline-none transition-colors focus:border-border-champagne"
              >
                {mapConcepts.map((concept) => (
                  <option key={concept.slug} value={concept.slug}>
                    {MAP_CONCEPT_SHORT[concept.slug] || concept.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.65fr)_minmax(280px,0.75fr)]">
            <div className="rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-[0_16px_45px_rgba(35,30,16,0.05)] sm:p-5">
              {mapSeries.isLoading ? (
                <SkeletonBox className="aspect-[2/1] w-full rounded-2xl" />
              ) : (
                <>
                  <WorldMap
                    countries={data?.countries || []}
                    valuesByCode={valuesByCode}
                    detailsByCode={detailsByCode}
                    unit={mapSeries.data?.concept?.unit || ''}
                    metricName={MAP_CONCEPT_SHORT[mapConcept] || mapSeries.data?.concept?.name || ''}
                    periodLabel={activeMapYear ? String(activeMapYear) : ''}
                    colorMode={mapConcept === 'budget-balance-gdp' ? 'diverging' : 'auto'}
                    onSelect={(country, detail) => navigate(
                      detail?.indicator_code
                        ? `/world/${country.slug}/${detail.indicator_code}`
                        : `/world/${country.slug}`,
                    )}
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

            <div className="rounded-[1.5rem] border border-border-subtle bg-surface p-5 shadow-[0_16px_45px_rgba(35,30,16,0.05)]">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">Последние данные</div>
                  <h3 className="mt-1 text-base font-semibold leading-snug text-text-primary">
                    {MAP_CONCEPT_SHORT[mapConcept] || mapSeries.data?.concept?.name || 'Рейтинг стран'}
                  </h3>
                  {activeMapYear && (
                    <div className="mt-1 font-mono text-[10px] text-text-tertiary">
                      {activeMapYear} год
                    </div>
                  )}
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
                {ranking.slice(0, 8).map((item, index) => (
                  <Link
                    key={item.country_slug}
                    to={item.indicator_code
                      ? `/world/${item.country_slug}/${item.indicator_code}`
                      : `/world/${item.country_slug}`}
                    className="group flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-surface-hover"
                  >
                    <span className="w-5 font-mono text-[10px] text-text-tertiary">{index + 1}</span>
                    <span className="min-w-0 flex-1 truncate text-sm text-text-primary group-hover:text-champagne">
                      {item.country_name}
                    </span>
                    <span className="font-mono text-xs font-semibold text-text-primary">
                      {formatWorldValue(item.value)}
                    </span>
                  </Link>
                ))}
              </div>
              {ranking.length >= 2 && (
                <Link
                  to={`/compare?codes=${encodeURIComponent(
                    ranking.slice(0, 2).map((item) => `w:${item.country_slug}:${mapConcept}`).join(','),
                  )}`}
                  className="mt-4 inline-flex items-center gap-1 text-xs text-champagne hover:underline"
                >
                  Сравнить страны
                  <ChevronRight size={12} />
                </Link>
              )}
            </div>
          </div>
        </section>
      )}

      <section id="countries" className="scroll-mt-24">
      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">Каталог</div>
          <h2 className="mt-1 font-display text-2xl font-bold text-text-primary">Все страны</h2>
        </div>
        <div className="relative w-full sm:max-w-md">
        <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Найти страну…"
          aria-label="Поиск по странам"
          className="w-full rounded-xl border border-border-subtle bg-surface py-3 pl-10 pr-4 text-sm text-text-primary shadow-sm placeholder:text-text-tertiary focus:border-border-champagne focus:outline-none"
        />
      </div>
      </div>

      {isError && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          Не удалось загрузить список стран. Проверьте соединение и попробуйте снова.
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

      {!isLoading && !isError && filtered.length === 0 && (
        <div className="rounded-2xl border border-border-subtle bg-surface p-8 text-center">
          <p className="text-text-secondary mb-4">
            По запросу «{query}» страны не найдены.
          </p>
          <Link to="/" className="text-champagne hover:underline text-sm">
            На главную
          </Link>
          {' · '}
          <Link to="/regions" className="text-champagne hover:underline text-sm">
            Регионы России
          </Link>
        </div>
      )}

      {!isLoading && byRegion.map(({ region, countries }) => (
        <section key={region} className="mb-8">
          <h2 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
            {region}
            <span className="font-mono text-[11px] text-text-tertiary font-normal">
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
          {total} {pluralRu(total, ['страна', 'страны', 'стран'])}
        </p>
      )}
      </section>

      <div className="mt-10 pt-6 border-t border-border-subtle flex flex-wrap gap-x-4 gap-y-2 text-sm text-text-secondary">
        <Link to="/regions" className="hover:text-champagne transition-colors">Регионы России</Link>
        <Link to="/compare" className="hover:text-champagne transition-colors">Сравнение</Link>
        <Link to="/calendar" className="hover:text-champagne transition-colors">Календарь</Link>
        <Link to="/" className="hover:text-champagne transition-colors">Главная</Link>
      </div>
    </div>
  );
}
