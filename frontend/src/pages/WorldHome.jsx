// Витрина мирового блока: /world
// Сетка стран по регионам + поиск по названию страны.
import { useMemo, useState, useDeferredValue } from 'react';
import { Link } from 'react-router-dom';
import { Search, Globe2, ChevronRight } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useWorldCountries, groupCountriesByRegion, pluralRu, formatWorldValue,
} from '../lib/worldApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import useSearchTracking from '../lib/useSearchTracking';

function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/[^а-яa-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
}

function CountryCard({ country }) {
  return (
    <Link
      to={`/world/${country.slug}`}
      className="group flex items-center justify-between gap-3 bg-surface border border-border-subtle rounded-xl px-4 py-3.5 hover:border-border-champagne hover:shadow-sm transition-all"
    >
      <div className="min-w-0">
        <div className="font-medium text-text-primary text-[15px] leading-snug truncate group-hover:text-champagne transition-colors">
          {country.name}
        </div>
        <div className="mt-0.5 text-[11px] text-text-tertiary font-mono">
          {country.name_en}
        </div>
      </div>
      <div className="shrink-0 flex items-center gap-2">
        <span className="font-mono text-[12px] text-text-secondary tabular-nums">
          {formatWorldValue(country.indicators_count, 0)}
          {' '}
          {pluralRu(country.indicators_count, ['показатель', 'показателя', 'показателей'])}
        </span>
        <ChevronRight size={14} className="text-text-tertiary group-hover:text-champagne transition-colors" />
      </div>
    </Link>
  );
}

export default function WorldHome() {
  const { data, isLoading, isError, refetch, isFetching } = useWorldCountries();
  const [query, setQuery] = useState('');
  const deferredQuery = useDeferredValue(query);

  useDocumentMeta({
    title: 'Мировая экономика — показатели стран по данным Евростата',
    description:
      'Макроэкономические показатели стран Европы и мира: цены, рынок труда, национальные счета. Официальные данные Евростата, графики и история.',
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
  const fromMock = data?._fromMock;

  return (
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      <div className="mb-8">
        <div className="flex items-center gap-2 text-champagne text-xs font-mono uppercase tracking-widest mb-3">
          <Globe2 size={14} />
          Мировая экономика
        </div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-text-primary leading-tight mb-3">
          Показатели стран мира
        </h1>
        <p className="text-text-secondary text-[15px] leading-relaxed max-w-2xl">
          Официальная статистика по странам Европы и мира. Источник — Евростат.
          Графики, история и режимы отображения — как на российских карточках платформы.
        </p>
        {fromMock && (
          <p className="mt-2 text-[12px] text-text-tertiary font-mono">
            Демо-данные (API ещё не подключён)
          </p>
        )}
      </div>

      <div className="mb-6 relative">
        <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Найти страну…"
          aria-label="Поиск по странам"
          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-surface border border-border-subtle text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-border-champagne"
        />
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
          <div className="grid sm:grid-cols-2 gap-2.5">
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

      <div className="mt-10 pt-6 border-t border-border-subtle flex flex-wrap gap-x-4 gap-y-2 text-sm text-text-secondary">
        <Link to="/regions" className="hover:text-champagne transition-colors">Регионы России</Link>
        <Link to="/compare" className="hover:text-champagne transition-colors">Сравнение</Link>
        <Link to="/calendar" className="hover:text-champagne transition-colors">Календарь</Link>
        <Link to="/" className="hover:text-champagne transition-colors">Главная</Link>
      </div>
    </div>
  );
}
