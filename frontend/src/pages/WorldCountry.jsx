// Страница страны: /world/{slug}
// Индикаторы по категориям (аккордеон) + поиск внутри страны.
import { useEffect, useMemo, useState, useDeferredValue } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ChevronRight, Search, Globe2, BarChart3, ArrowUpRight,
  CalendarRange, TrendingUp,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useWorldCountry, formatWorldValue, pluralRu,
} from '../lib/worldApi';
import { collapseCountryIndicators, stripFrequencySuffix } from '../lib/worldViewModes';
import { formatDate } from '../lib/format';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import useSearchTracking from '../lib/useSearchTracking';
import { CountrySilhouette } from '../components/WorldMap';

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

function formatFreqList(item) {
  const freqs = Array.isArray(item.frequencies)
    ? item.frequencies.map((f) => (typeof f === 'string' ? f : f.freq)).filter(Boolean)
    : (item.frequency ? [item.frequency] : []);
  if (!freqs.length) return '';
  return freqs.map((f) => FREQ_LABEL[f] || f).join(' · ');
}

function IndicatorRow({ item, slug }) {
  const name = stripFrequencySuffix(item.name);
  const freqLine = formatFreqList(item);
  return (
    <Link
      to={`/world/${slug}/${item.code}`}
      className="group flex min-h-[92px] items-center justify-between gap-4 rounded-xl border border-border-subtle bg-white px-4 py-3.5 transition-all hover:-translate-y-0.5 hover:border-border-champagne hover:shadow-[0_12px_30px_rgba(35,30,16,0.06)]"
    >
      <div className="min-w-0 flex-1">
        <div className="text-[14px] text-text-primary leading-snug group-hover:text-champagne transition-colors">
          {name}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-text-tertiary">
          {freqLine && <span className="rounded-full bg-obsidian-light px-2 py-0.5 font-mono">{freqLine}</span>}
          {item.unit && <span className="truncate">{item.unit}</span>}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-[14px] font-medium text-text-primary">
          {formatWorldValue(item.last_value)}
        </div>
        <div className="font-mono text-[10px] text-text-tertiary">
          {item.last_date ? formatDate(item.last_date, item.frequency === 'annual' ? 'annual' : 'full') : '—'}
        </div>
      </div>
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-obsidian-light">
        <ChevronRight size={13} className="text-text-tertiary transition-colors group-hover:text-champagne" />
      </span>
    </Link>
  );
}

export default function WorldCountry() {
  const { slug } = useParams();
  const { data, isLoading, isError, refetch, isFetching, error } = useWorldCountry(slug);
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('');
  const deferredQuery = useDeferredValue(query);

  const countryName = data?.country?.name;
  const notFound = isError && error?.response?.status === 404;

  useDocumentMeta(countryName ? {
    title: `${countryName} — макроэкономические показатели`,
    description:
      `${countryName}: показатели Евростата — цены, рынок труда, национальные счета. Графики и история на Forecast Economy.`,
    path: `/world/${slug}`,
  } : {
    title: notFound ? 'Страна не найдена' : 'Мировая экономика',
    description: 'Макроэкономические показатели стран Европы.',
    path: `/world/${slug}`,
  });

  useEffect(() => {
    if (!countryName) return undefined;
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Главная', item: 'https://forecasteconomy.com/' },
        { '@type': 'ListItem', position: 2, name: 'Мировая экономика', item: 'https://forecasteconomy.com/world' },
        { '@type': 'ListItem', position: 3, name: countryName, item: `https://forecasteconomy.com/world/${slug}` },
      ],
    };
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'world-country-jsonld';
    script.textContent = JSON.stringify(jsonLd);
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
  const visibleCategories = deferredQuery
    ? filteredCategories
    : filteredCategories.filter((cat) => cat.name === resolvedActiveCategory);

  return (
    <div className="mx-auto w-full max-w-7xl px-4 pb-24 pt-24 sm:px-6">
      <nav className="flex items-center gap-1.5 text-xs text-text-tertiary mb-4 overflow-hidden" aria-label="Хлебные крошки">
        <Link to="/world" className="hover:text-champagne transition-colors shrink-0">Мировая экономика</Link>
        <ChevronRight size={12} className="shrink-0" />
        <span className="text-text-secondary truncate">{countryName || '…'}</span>
      </nav>

      {notFound && (
        <div className="rounded-2xl border border-border-subtle bg-surface p-8 text-center mt-8">
          <h1 className="font-display text-2xl font-bold text-text-primary mb-3">Страна не найдена</h1>
          <p className="text-text-secondary mb-6">
            Страницы с адресом «{slug}» в каталоге нет. Выберите страну из списка или перейдите в другой раздел.
          </p>
          <div className="flex flex-wrap justify-center gap-3 text-sm">
            <Link to="/world" className="px-4 py-2 rounded-xl bg-champagne/10 text-champagne hover:bg-champagne/20 transition-colors">
              Все страны
            </Link>
            <Link to="/regions" className="px-4 py-2 rounded-xl border border-border-subtle text-text-secondary hover:text-champagne transition-colors">
              Регионы России
            </Link>
            <Link to="/" className="px-4 py-2 rounded-xl border border-border-subtle text-text-secondary hover:text-champagne transition-colors">
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
          <section className="relative mb-8 overflow-hidden rounded-[2rem] border border-border-subtle bg-surface p-6 shadow-[0_22px_70px_rgba(35,30,16,0.06)] sm:p-8">
            <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-champagne/10 blur-3xl" />
            <div className="relative grid gap-7 lg:grid-cols-[minmax(0,1.3fr)_minmax(260px,0.7fr)] lg:items-center">
              <div>
                <div className="mb-4 flex items-center gap-3">
                  <span className="flex h-12 w-12 items-center justify-center rounded-full border border-champagne/20 bg-champagne/8 font-mono text-sm font-semibold text-champagne">
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
                <h1 className="font-display text-4xl font-bold leading-tight text-text-primary sm:text-5xl">
                  {countryName}: экономика и показатели
                </h1>
                <p className="mt-4 max-w-2xl text-sm leading-6 text-text-secondary">
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
                  to={`/world/${slug}/${item.indicator_code}`}
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
                    {formatDate(item.date, item.frequency === 'annual' ? 'annual' : 'full')}
                  </div>
                </Link>
              ))}
              {!data.overview?.length && (
                <div className="sm:col-span-3 text-xs text-text-tertiary">
                  {totalIndicators} показателей · {data.categories.length} разделов · источник — Евростат
                </div>
              )}
            </div>
            {data._fromMock && (
              <p className="mt-1 text-[12px] text-text-tertiary font-mono">
                Демо-данные (API ещё не подключён)
              </p>
            )}
          </section>

          {data.overview?.length > 0 && (
            <section className="mb-8" data-block="country-overview">
              <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
                    Экономический профиль
                  </div>
                  <h2 className="mt-1 font-display text-2xl font-bold text-text-primary">
                    Ключевые показатели
                  </h2>
                </div>
                {data.coverage?.frequencies?.length > 0 && (
                  <div className="flex items-center gap-2 text-[11px] text-text-tertiary">
                    <CalendarRange size={13} className="text-champagne" />
                    {data.coverage.frequencies.map((frequency) => FREQ_LABEL[frequency] || frequency).join(' · ')}
                  </div>
                )}
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {data.overview.slice(0, 6).map((item) => (
                  <Link
                    key={item.concept_slug}
                    to={`/world/${slug}/${item.indicator_code}`}
                    className="group rounded-2xl border border-border-subtle bg-surface p-4 shadow-[0_10px_30px_rgba(35,30,16,0.04)] transition-all hover:-translate-y-0.5 hover:border-border-champagne hover:shadow-[0_16px_35px_rgba(35,30,16,0.07)]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="text-[12px] leading-5 text-text-secondary group-hover:text-text-primary">
                        {item.name}
                      </div>
                      <TrendingUp size={14} className="mt-0.5 shrink-0 text-champagne" />
                    </div>
                    <div className="mt-4 font-mono text-2xl font-semibold tabular-nums text-text-primary">
                      {formatWorldValue(item.value)}
                    </div>
                    <div className="mt-1 line-clamp-2 text-[10px] leading-4 text-text-tertiary">
                      {item.unit}
                    </div>
                    <div className="mt-3 flex items-center justify-between border-t border-border-subtle pt-2.5 font-mono text-[10px] text-text-tertiary">
                      <span>{formatDate(item.date, item.frequency === 'annual' ? 'annual' : 'full')}</span>
                      <ChevronRight size={12} className="transition-transform group-hover:translate-x-0.5" />
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

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
              По запросу «{query}» ничего не найдено.
              {' '}
              <button type="button" onClick={() => setQuery('')} className="text-champagne hover:underline">
                Сбросить поиск
              </button>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-[250px_minmax(0,1fr)]">
            {!deferredQuery && (
              <aside className="lg:sticky lg:top-24 lg:self-start">
                <div className="mb-2 px-2 text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
                  Темы
                </div>
                <div className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible">
                  {filteredCategories.map((cat) => (
                    <button
                      key={cat.name}
                      type="button"
                      onClick={() => setActiveCategory(cat.name)}
                      className={[
                        'flex shrink-0 items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                        resolvedActiveCategory === cat.name
                          ? 'bg-champagne/12 font-medium text-champagne'
                          : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                      ].join(' ')}
                    >
                      <span>{cat.name}</span>
                      <span className="font-mono text-[10px] opacity-60">{cat.indicators.length}</span>
                    </button>
                  ))}
                </div>
              </aside>
            )}

            <div className="min-w-0 space-y-8">
              {visibleCategories.map((cat) => (
                <section key={cat.name}>
                  <div className="mb-4 flex items-end justify-between gap-4">
                    <div>
                      <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
                        {deferredQuery ? 'Результаты поиска' : 'Показатели'}
                      </div>
                      <h2 className="mt-1 font-display text-2xl font-bold text-text-primary">{cat.name}</h2>
                    </div>
                    <span className="font-mono text-xs text-text-tertiary">{cat.indicators.length}</span>
                  </div>
                  <div className="grid gap-2.5 xl:grid-cols-2">
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
