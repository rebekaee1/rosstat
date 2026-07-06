// Страница региона: /region/{slug}
// Мобильный сценарий: ключевые цифры → поиск по показателям → разделы-аккордеоны.
import { useEffect, useMemo, useState, useDeferredValue } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ChevronRight, ChevronDown, Search, MapPin, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useRegionProfile, formatRegionValue, shortUnit, yearDelta, pluralRu,
} from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import useSearchTracking from '../lib/useSearchTracking';

function normalize(s) {
  return s.toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
}

function DeltaBadge({ value, prevValue }) {
  const d = yearDelta(value, prevValue);
  if (!d) return null;
  const Icon = d.up ? TrendingUp : d.down ? TrendingDown : Minus;
  const cls = d.up ? 'text-positive' : d.down ? 'text-negative' : 'text-text-tertiary';
  return (
    <span className={`inline-flex items-center gap-0.5 font-mono text-[11px] ${cls}`}>
      <Icon size={11} />
      {Math.abs(d.pct) >= 0.1 ? `${Math.abs(d.pct).toFixed(1).replace('.', ',')}%` : '<0,1%'}
    </span>
  );
}

function HeadlineCard({ item, slug }) {
  return (
    <Link
      to={`/region/${slug}/${item.code}`}
      className="group bg-surface border border-border-subtle rounded-xl p-3.5 hover:border-border-champagne hover:shadow-sm transition-all"
    >
      <div className="text-[11px] text-text-tertiary uppercase tracking-wide">{item.label}</div>
      <div className="mt-1 font-mono font-semibold text-text-primary text-lg leading-none">
        {formatRegionValue(item.value)}
        <span className="ml-1 text-[11px] font-normal text-text-secondary">{shortUnit(item.unit)}</span>
      </div>
      <div className="mt-1.5 flex items-center justify-between">
        <span className="font-mono text-[11px] text-text-tertiary">{item.year}</span>
        <DeltaBadge value={item.value} prevValue={item.prev_value} />
      </div>
    </Link>
  );
}

function IndicatorRow({ item, slug }) {
  return (
    <Link
      to={`/region/${slug}/${item.code}`}
      className="group flex items-center justify-between gap-3 px-3.5 py-3 hover:bg-surface-hover rounded-lg transition-colors"
    >
      <div className="min-w-0 flex-1">
        <div className="text-[14px] text-text-primary leading-snug group-hover:text-champagne transition-colors">
          {item.name}
        </div>
        <div className="mt-0.5 text-[11px] text-text-tertiary">
          {shortUnit(item.unit) || item.unit}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-[14px] font-medium text-text-primary">
          {formatRegionValue(item.value)}
        </div>
        <div className="flex items-center justify-end gap-1.5">
          <span className="font-mono text-[10px] text-text-tertiary">{item.year}</span>
          <DeltaBadge value={item.value} prevValue={item.prev_value} />
        </div>
      </div>
      <ChevronRight size={14} className="shrink-0 text-text-tertiary group-hover:text-champagne transition-colors" />
    </Link>
  );
}

// Открытые разделы живут в sessionStorage: по умолчанию всё свёрнуто (правка
// руководителя 2026-07-05), а выбор пользователя переживает уход на показатель
// и возврат назад (жалоба из созвона: «открываются обратно»).
const OPEN_SECTIONS_KEY = 'fe:region-open-sections';

function readOpenSections() {
  try {
    const raw = sessionStorage.getItem(OPEN_SECTIONS_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

export default function RegionProfile() {
  const { slug } = useParams();
  const { data, isLoading, isError, refetch, isFetching } = useRegionProfile(slug);
  const [query, setQuery] = useState('');
  const [openSections, setOpenSections] = useState(readOpenSections);
  const deferredQuery = useDeferredValue(query);

  const regionName = data?.region?.name;
  useDocumentMeta(regionName ? {
    title: `${regionName} — статистика региона: население, зарплата, ВРП, цены`,
    description:
      `${regionName}: ${data.sections.reduce((n, s) => n + s.indicators.length, 0)} социально-экономических показателей Росстата с 1990 года — население, зарплаты, безработица, ВРП, инвестиции, строительство, цены. Графики и место региона в рейтингах России.`,
    path: `/region/${slug}`,
  } : null);

  // Breadcrumb JSON-LD
  useEffect(() => {
    if (!regionName) return;
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Главная', item: 'https://forecasteconomy.com/' },
        { '@type': 'ListItem', position: 2, name: 'Регионы', item: 'https://forecasteconomy.com/regions' },
        { '@type': 'ListItem', position: 3, name: regionName, item: `https://forecasteconomy.com/region/${slug}` },
      ],
    };
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'region-breadcrumb-jsonld';
    script.textContent = JSON.stringify(jsonLd);
    document.getElementById('region-breadcrumb-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [regionName, slug]);

  const filteredSections = useMemo(() => {
    if (!data) return [];
    const q = normalize(deferredQuery);
    if (!q) return data.sections;
    return data.sections
      .map(s => ({ ...s, indicators: s.indicators.filter(i => normalize(i.name).includes(q)) }))
      .filter(s => s.indicators.length > 0);
  }, [data, deferredQuery]);

  const searching = normalize(deferredQuery).length > 0;

  // Спрос-аналитика поиска показателей внутри карточки региона.
  const foundIndicators = filteredSections.reduce((n, s) => n + s.indicators.length, 0);
  useSearchTracking('region-profile', deferredQuery, foundIndicators);
  const headlineOrder = ['1.1', '3.4', '2.10.1', '8.2', '10.1', '20.1', '3.12', '8.1'];
  const headline = data
    ? headlineOrder.map(tc => data.headline[tc]).filter(Boolean)
    : [];

  const toggleSection = (num) => {
    setOpenSections(prev => {
      const next = new Set(prev);
      if (next.has(num)) next.delete(num);
      else next.add(num);
      try {
        sessionStorage.setItem(OPEN_SECTIONS_KEY, JSON.stringify([...next]));
      } catch { /* приватный режим — не критично */ }
      return next;
    });
  };

  return (
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      {/* Хлебные крошки */}
      <nav className="flex items-center gap-1.5 text-xs text-text-tertiary mb-4" aria-label="Хлебные крошки">
        <Link to="/" className="hover:text-champagne transition-colors">Главная</Link>
        <ChevronRight size={12} />
        <Link to="/regions" className="hover:text-champagne transition-colors">Регионы</Link>
        {regionName && (<><ChevronRight size={12} /><span className="text-text-secondary truncate">{regionName}</span></>)}
      </nav>

      {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}
      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-10 w-72" />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {Array.from({ length: 8 }).map((_, i) => <SkeletonBox key={i} className="h-24 rounded-xl" />)}
          </div>
        </div>
      )}

      {data && (
        <>
          {/* Шапка региона */}
          <div className="mb-6">
            {data.region.district_name && (
              <div className="flex items-center gap-1.5 text-champagne text-xs font-mono uppercase tracking-widest mb-2">
                <MapPin size={13} />
                {data.region.district_name}
              </div>
            )}
            <h1 className="font-display text-3xl sm:text-4xl font-bold text-text-primary leading-tight">
              {data.region.name}
            </h1>
            <p className="mt-2 text-sm text-text-secondary max-w-2xl">
              {(() => {
                const catalog = data.catalog_total ?? data.sections.reduce((acc, s) => acc + s.indicators.length, 0);
                const available = data.available_total ?? catalog;
                const catalogWord = pluralRu(catalog, ['показатель', 'показателя', 'показателей']);
                const availableWord = pluralRu(available, ['показатель', 'показателя', 'показателей']);
                if (available < catalog) {
                  return `Официальная статистика Росстата: ${catalog} ${catalogWord} в каталоге; по региону — данные по ${available} ${availableWord} в ${data.sections.length} разделах, с 1990 года.`;
                }
                return `Официальная статистика Росстата по региону: ${catalog} ${catalogWord} в ${data.sections.length} разделах, данные с 1990 года.`;
              })()}
            </p>
          </div>

          {/* Ключевые цифры */}
          {headline.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-8">
              {headline.map(h => <HeadlineCard key={h.code} item={h} slug={slug} />)}
            </div>
          )}

          {/* Поиск по показателям */}
          <div className="sticky top-14 z-10 -mx-4 px-4 py-2 bg-obsidian/95 backdrop-blur-sm mb-4">
            <div className="relative">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Найти показатель: зарплата, жильё, урожайность…"
                className="w-full pl-10 pr-4 py-3 rounded-xl bg-surface border border-border-subtle text-[15px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-border-champagne focus:ring-2 focus:ring-champagne/10 transition-all"
                aria-label="Поиск показателя в регионе"
              />
            </div>
          </div>

          {/* Разделы */}
          <div className="space-y-3">
            {filteredSections.map(sec => {
              const isOpen = searching || openSections.has(sec.num);
              return (
                <section key={sec.num} data-block={`region-section-${sec.num}`} className="bg-surface border border-border-subtle rounded-xl overflow-hidden">
                  <button
                    onClick={() => toggleSection(sec.num)}
                    className="w-full flex items-center justify-between gap-3 px-4 py-3.5 text-left hover:bg-surface-hover transition-colors"
                    aria-expanded={isOpen}
                  >
                    <span className="font-medium text-[15px] text-text-primary">
                      {sec.name}
                    </span>
                    <span className="flex items-center gap-2 shrink-0">
                      <span className="font-mono text-xs text-text-tertiary">{sec.indicators.length}</span>
                      <ChevronDown size={16} className={`text-text-tertiary transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                    </span>
                  </button>
                  {isOpen && (
                    <div className="border-t border-border-subtle py-1">
                      {sec.indicators.map(item => (
                        <IndicatorRow key={item.code} item={item} slug={slug} />
                      ))}
                    </div>
                  )}
                </section>
              );
            })}
            {searching && filteredSections.length === 0 && (
              <div className="text-center py-12 text-text-secondary">
                По запросу «{query}» показателей не найдено
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
