// Страница страны: /world/{slug}
// Индикаторы по категориям (аккордеон) + поиск внутри страны.
import { useEffect, useMemo, useState, useDeferredValue } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ChevronRight, ChevronDown, Search, Globe2,
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
      className="group flex items-center justify-between gap-3 px-3.5 py-3 hover:bg-surface-hover rounded-lg transition-colors"
    >
      <div className="min-w-0 flex-1">
        <div className="text-[14px] text-text-primary leading-snug group-hover:text-champagne transition-colors">
          {name}
        </div>
        <div className="mt-0.5 text-[11px] text-text-tertiary">
          {item.unit}
          {freqLine ? ` · ${freqLine}` : ''}
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
      <ChevronRight size={14} className="shrink-0 text-text-tertiary group-hover:text-champagne transition-colors" />
    </Link>
  );
}

const OPEN_KEY = 'fe:world-open-sections';

function readOpenSections() {
  try {
    const raw = sessionStorage.getItem(OPEN_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

export default function WorldCountry() {
  const { slug } = useParams();
  const { data, isLoading, isError, refetch, isFetching, error } = useWorldCountry(slug);
  const [query, setQuery] = useState('');
  const [openSections, setOpenSections] = useState(readOpenSections);
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
    description: 'Макроэкономические показатели стран мира.',
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

  const toggleSection = (name) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      try {
        sessionStorage.setItem(OPEN_KEY, JSON.stringify([...next]));
      } catch { /* ignore */ }
      return next;
    });
  };

  // При поиске — раскрываем все совпавшие секции
  const isOpen = (name) => (deferredQuery ? true : openSections.has(name));

  return (
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
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
          <div className="mb-6">
            <div className="flex items-center gap-2 text-champagne text-xs font-mono uppercase tracking-widest mb-2">
              <Globe2 size={13} />
              {data.country.region}
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-bold text-text-primary leading-tight">
              {countryName}
            </h1>
            <p className="mt-2 text-sm text-text-secondary">
              {totalIndicators}{' '}
              {pluralRu(totalIndicators, ['показатель', 'показателя', 'показателей'])}
              {' · источник: Евростат'}
            </p>
            {data._fromMock && (
              <p className="mt-1 text-[12px] text-text-tertiary font-mono">
                Демо-данные (API ещё не подключён)
              </p>
            )}
          </div>

          <div className="mb-5 relative">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Найти показатель…"
              aria-label="Поиск по показателям страны"
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-surface border border-border-subtle text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-border-champagne"
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

          <div className="space-y-3">
            {filteredCategories.map((cat) => {
              const open = isOpen(cat.name);
              return (
                <div key={cat.name} className="bg-surface border border-border-subtle rounded-xl overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleSection(cat.name)}
                    className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-surface-hover transition-colors"
                    aria-expanded={open}
                  >
                    <span className="text-sm font-medium text-text-primary">
                      {cat.name}
                      <span className="ml-2 font-mono text-[11px] text-text-tertiary font-normal">
                        {cat.indicators.length}
                      </span>
                    </span>
                    <ChevronDown size={16} className={`text-text-tertiary transition-transform ${open ? 'rotate-180' : ''}`} />
                  </button>
                  {open && (
                    <div className="border-t border-border-subtle pb-1">
                      {cat.indicators.map((ind) => (
                        <IndicatorRow key={ind.code} item={ind} slug={slug} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
