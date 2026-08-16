// Страница страны: /world/{slug}
// Темы слева + сетка показателей; поиск не ломает сетку.
import { useEffect, useMemo, useState, useDeferredValue } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ChevronRight, Search, Globe2, BarChart3, ArrowUpRight, TrendingUp,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  worldCountryDescription,
  worldCountryTitle,
} from '../lib/pageMeta';
import {
  useWorldCountry, formatWorldValue, pluralRu,
} from '../lib/worldApi';
import { collapseCountryIndicators, stripFrequencySuffix } from '../lib/worldViewModes';
import { formatChange, formatDate } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import useSearchTracking from '../lib/useSearchTracking';
import { CountrySilhouette } from '../components/WorldMap';
import {
  breadcrumbJsonLd,
  worldCountryTrail,
} from '../lib/breadcrumbs';
import {
  countryPath,
  indicatorPath,
  regionHubPath,
} from '../lib/sitePaths';

function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
}

const FREQ_LABEL = {
  daily: 'день',
  weekly: 'нед.',
  monthly: 'мес.',
  quarterly: 'кв.',
  annual: 'год',
};

function formatIndicatorDate(dateStr, frequency) {
  if (!dateStr) return '—';
  if (frequency === 'annual') return formatDate(dateStr, 'annual');
  if (frequency === 'quarterly') return formatDate(dateStr, 'quarterly');
  return formatDate(dateStr, 'full');
}

function formatFreqList(item) {
  const freqs = Array.isArray(item.frequencies)
    ? item.frequencies.map((f) => (typeof f === 'string' ? f : f.freq)).filter(Boolean)
    : (item.frequency ? [item.frequency] : []);
  if (!freqs.length) return '';
  return freqs.map((f) => FREQ_LABEL[f]).filter(Boolean).join(', ');
}

function CompactChange({ change }) {
  if (change == null || !Number.isFinite(Number(change)) || Math.abs(Number(change)) < 1e-12) {
    return null;
  }
  const n = Number(change);
  return (
    <span className={`font-mono text-[10px] tabular-nums ${n > 0 ? 'text-positive' : 'text-negative'}`}>
      {formatChange(n)}
    </span>
  );
}

function IndicatorRow({ item, slug }) {
  const name = stripFrequencySuffix(item.name);
  const freqLine = formatFreqList(item);
  return (
    <Link
      to={indicatorPath(slug, item.code)}
      className="group flex flex-col gap-2 rounded-xl border border-border-subtle bg-white px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-[0_12px_30px_rgba(35,30,16,0.06)] sm:min-h-[92px] sm:flex-row sm:items-center sm:gap-3 sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0 flex-1">
        <div className="text-[13px] leading-snug text-text-primary transition-colors group-hover:text-champagne sm:text-[14px]">
          {name}
        </div>
        <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1.5 text-[10px] text-text-tertiary sm:mt-1.5">
          {freqLine && <span className="rounded-full bg-obsidian-light px-2 py-0.5 font-mono">{freqLine}</span>}
          {item.unit && <span className="line-clamp-1 break-all">{item.unit}</span>}
        </div>
      </div>
      <div className="flex items-baseline justify-between gap-3 border-t border-border-subtle/60 pt-2 sm:w-[7.5rem] sm:shrink-0 sm:flex-col sm:items-end sm:justify-center sm:border-0 sm:pt-0 sm:text-right">
        <div className="font-mono text-[15px] font-semibold tabular-nums text-text-primary sm:text-[14px] sm:font-medium">
          {formatWorldValue(item.last_value)}
        </div>
        <div className="flex items-center gap-1.5">
          <CompactChange change={item.change} />
          <span className="font-mono text-[10px] text-text-tertiary">
            {formatIndicatorDate(item.last_date, item.frequency)}
          </span>
        </div>
      </div>
    </Link>
  );
}

export default function WorldCountry() {
  const { countrySlug, slug: slugParam } = useParams();
  const slug = countrySlug || slugParam;
  const { data, isLoading, isError, refetch, isFetching, error } = useWorldCountry(slug);
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('');
  const deferredQuery = useDeferredValue(query);
  const searching = normalize(deferredQuery).length > 0;

  const countryName = data?.country?.name;
  const notFound = isError && error?.response?.status === 404;

  const countryMeta = useMemo(() => {
    if (!countryName || !data) return null;
    const flat = (data.categories || []).flatMap((c) => c.indicators || []);
    const total = flat.length || Number(data.indicators_count) || 0;
    const hasNational = flat.some((ind) => {
      const prov = String(ind.provider || '').trim().toLowerCase();
      return prov && prov !== 'eurostat';
    });
    const sources = [...new Set(
      flat.map((ind) => ind.source).filter(Boolean),
    )];
    let sourcePhrase = 'Евростат';
    if (sources.length === 1) sourcePhrase = sources[0];
    else if (sources.length === 2) sourcePhrase = `${sources[0]} и ${sources[1]}`;
    else if (sources.length > 2) {
      sourcePhrase = `${sources.slice(0, -1).join(', ')} и ${sources[sources.length - 1]}`;
    }
    const title = worldCountryTitle(slug, countryName);
    return {
      title,
      description: worldCountryDescription(slug, countryName, total, {
        hasNational,
        sourcePhrase,
      }),
      h1: title,
    };
  }, [countryName, data, slug]);

  useDocumentMeta(countryMeta ? {
    title: countryMeta.title,
    description: countryMeta.description,
    path: countryPath(slug),
  } : (notFound ? {
    title: 'Страна не найдена',
    description: 'Запрашиваемая страница страны не найдена.',
    path: countryPath(slug),
  } : null));

  useEffect(() => {
    if (!countryName) return undefined;
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'world-country-jsonld';
    script.textContent = JSON.stringify(breadcrumbJsonLd(worldCountryTrail(countryName, slug)));
    document.getElementById('world-country-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [countryName, slug]);

  const filteredCategories = useMemo(() => {
    const cats = data?.categories || [];
    const collapsed = cats.map((cat) => ({
      ...cat,
      indicators: collapseCountryIndicators(cat.indicators || []),
      count: undefined,
    }));
    const withCounts = collapsed.map((cat) => ({
      ...cat,
      count: cat.indicators.length,
    }));
    const q = normalize(deferredQuery);
    if (!q) return withCounts;
    return withCounts
      .map((cat) => ({
        ...cat,
        indicators: cat.indicators.filter((i) =>
          normalize(i.name).includes(q) || normalize(i.code).includes(q)),
      }))
      .filter((cat) => cat.indicators.length > 0)
      .map((cat) => ({ ...cat, count: cat.indicators.length }));
  }, [data, deferredQuery]);

  const totalIndicators = useMemo(
    () => (data?.categories || []).reduce(
      (n, c) => n + collapseCountryIndicators(c.indicators || []).length,
      0,
    ),
    [data],
  );

  const matchCount = useMemo(
    () => filteredCategories.reduce((n, c) => n + c.indicators.length, 0),
    [filteredCategories],
  );

  useSearchTracking('world-country-indicators', deferredQuery, matchCount);

  const resolvedActiveCategory = filteredCategories.some((cat) => cat.name === activeCategory)
    ? activeCategory
    : (filteredCategories[0]?.name || '');
  const visibleCategories = searching
    ? filteredCategories
    : filteredCategories.filter((cat) => cat.name === resolvedActiveCategory);

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-hidden px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={worldCountryTrail(countryName || '…', slug)} />

      {notFound && (
        <div className="mt-8 rounded-2xl border border-border-subtle bg-surface p-8 text-center">
          <h1 className="mb-3 font-display text-2xl font-bold text-text-primary">Страна не найдена</h1>
          <p className="mb-6 text-text-secondary">
            Страницы с адресом «{slug}» в каталоге нет. Выберите страну из списка или перейдите в другой раздел.
          </p>
          <div className="flex flex-wrap justify-center gap-3 text-sm">
            <Link to="/world" className="rounded-xl bg-champagne/10 px-4 py-2 text-champagne transition-colors hover:bg-champagne/20">
              Все страны
            </Link>
            <Link to={regionHubPath()} className="rounded-xl border border-border-subtle px-4 py-2 text-text-secondary transition-colors hover:text-champagne">
              Регионы России
            </Link>
            <Link to="/" className="rounded-xl border border-border-subtle px-4 py-2 text-text-secondary transition-colors hover:text-champagne">
              Главная
            </Link>
          </div>
        </div>
      )}

      {isError && !notFound && (
        <ApiRetryBanner onRetry={refetch} isFetching={isFetching} className="mb-6">
          Не удалось загрузить данные страны. Попробуйте ещё раз.
        </ApiRetryBanner>
      )}

      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-9 w-64 max-w-full" />
          <SkeletonBox className="h-10 w-full rounded-xl" />
          <SkeletonBox className="h-40 rounded-xl" />
        </div>
      )}

      {data && (
        <>
          <section className="relative mb-6 overflow-hidden rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-[0_22px_70px_rgba(35,30,16,0.06)] sm:mb-8 sm:rounded-[2rem] sm:p-8">
            <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-champagne/10 blur-3xl" />
            <div className="relative grid gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)] lg:items-center lg:gap-7">
              <div>
                <div className="mb-3 flex items-center gap-3 sm:mb-4">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full border border-champagne/20 bg-champagne/8 font-mono text-sm font-semibold text-champagne sm:h-12 sm:w-12">
                    {data.country.code}
                  </span>
                  <div>
                    <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
                      <Globe2 size={12} />
                      {data.country.region}
                    </div>
                    <div className="mt-1 text-xs text-text-tertiary">{data.country.name_en}</div>
                  </div>
                </div>
                <h1 className="font-display text-[1.65rem] font-bold leading-tight text-text-primary sm:text-5xl">
                  {countryMeta?.h1 || countryName}
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-text-secondary sm:mt-4">
                  {totalIndicators} {pluralRu(totalIndicators, ['показатель', 'показателя', 'показателей'])}
                  {' '}в {data.categories.length} {pluralRu(data.categories.length, ['тематическом разделе', 'тематических разделах', 'тематических разделах'])}
                  {data.coverage?.history_start
                    ? `; доступная история начинается с ${formatDate(data.coverage.history_start, 'annual')} года.`
                    : '.'}
                </p>
              </div>
              <div>
                <CountrySilhouette
                  code={data.country.code}
                  name={countryName}
                  region={data.country.region}
                  historyStart={data.coverage?.history_start}
                  historyEnd={data.coverage?.history_end}
                  frequencies={data.coverage?.frequencies}
                  area={data.area}
                  population={data.population}
                />
                <Link
                  to={data.overview?.[0]
                    ? `/compare?codes=w:${slug}:${data.overview[0].concept_slug}`
                    : '/compare'}
                  className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-champagne px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-transform hover:-translate-y-0.5"
                >
                  <BarChart3 size={15} />
                  Сравнить показатели
                  <ArrowUpRight size={14} />
                </Link>
              </div>
            </div>

            <div className="relative mt-7 grid gap-2 border-t border-border-subtle pt-5 sm:grid-cols-3 sm:gap-4">
              {(data.overview || []).slice(0, 3).map((item) => (
                <Link
                  key={item.concept_slug}
                  to={indicatorPath(slug, item.indicator_code)}
                  className="group min-w-0 rounded-xl bg-obsidian-light/65 px-3 py-3 transition-colors hover:bg-champagne/[0.08]"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-mono text-lg font-semibold tabular-nums text-text-primary">
                      {formatWorldValue(item.value)}
                    </div>
                    <TrendingUp size={13} className="mt-1 shrink-0 text-champagne" />
                  </div>
                  <div className="mt-1 line-clamp-1 text-[10px] text-text-secondary group-hover:text-text-primary">
                    {item.name}
                  </div>
                  <div className="mt-1 truncate font-mono text-[9px] text-text-tertiary">
                    {formatIndicatorDate(item.date, item.frequency)}
                  </div>
                </Link>
              ))}
              {!data.overview?.length && (
                <div className="text-xs text-text-tertiary sm:col-span-3">
                  {totalIndicators} показателей — {data.categories.length} разделов — официальные источники
                </div>
              )}
            </div>
          </section>

          <div className="relative mb-6">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Найти показатель…"
              aria-label="Поиск по показателям страны"
              className="w-full rounded-xl border border-border-subtle bg-surface py-3 pl-10 pr-4 text-sm text-text-primary shadow-sm placeholder:text-text-tertiary focus:border-border-champagne focus:outline-none"
            />
          </div>

          {filteredCategories.length === 0 && (
            <div className="rounded-2xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
              {searching ? (
                <>
                  По запросу «{query}» ничего не найдено.
                  {' '}
                  <button type="button" onClick={() => setQuery('')} className="text-champagne hover:underline">
                    Сбросить поиск
                  </button>
                </>
              ) : (
                <>
                  Пока нет опубликованных показателей по этой стране.
                  {' '}
                  Данные появятся после проверки официальных рядов.
                  {' '}
                  <Link to="/world" className="text-champagne hover:underline">
                    К каталогу стран
                  </Link>
                </>
              )}
            </div>
          )}

          {!searching && (
            <MobileNavSelect
              label="Темы"
              value={resolvedActiveCategory}
              onChange={setActiveCategory}
              options={filteredCategories.map((cat) => ({
                value: cat.name,
                label: cat.name,
                count: cat.indicators.length,
              }))}
            />
          )}

          <div className={searching
            ? 'min-w-0 space-y-8'
            : 'grid min-w-0 gap-6 lg:grid-cols-[250px_minmax(0,1fr)]'}
          >
            {!searching && (
              <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block lg:self-start">
                <div className="mb-2 px-2 text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
                  Темы
                </div>
                <div className="flex flex-col gap-2">
                  {filteredCategories.map((cat) => (
                    <button
                      key={cat.name}
                      type="button"
                      onClick={() => setActiveCategory(cat.name)}
                      className={[
                        'flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                        resolvedActiveCategory === cat.name
                          ? 'bg-champagne/12 font-medium text-champagne'
                          : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                      ].join(' ')}
                    >
                      <span className="min-w-0 truncate">{cat.name}</span>
                      <span className="shrink-0 font-mono text-[10px] opacity-60">{cat.indicators.length}</span>
                    </button>
                  ))}
                </div>
              </aside>
            )}

            <div className="min-w-0 space-y-8">
              {visibleCategories.map((cat) => (
                <section key={cat.name}>
                  <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4">
                    <div className="min-w-0">
                      <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
                        {searching ? 'Результаты поиска' : 'Показатели'}
                      </div>
                      <h2 className="mt-1 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">{cat.name}</h2>
                    </div>
                    <span className="shrink-0 font-mono text-xs text-text-tertiary">{cat.indicators.length}</span>
                  </div>
                  <div className="grid gap-2 sm:gap-2.5 xl:grid-cols-2">
                    {cat.indicators.map((ind) => (
                      <IndicatorRow key={ind.code} item={ind} slug={slug} />
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
