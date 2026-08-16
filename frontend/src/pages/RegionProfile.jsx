// Страница региона: /russia/region/{slug}
// Как у стран: темы слева, сетка показателей справа.
import { useEffect, useMemo, useState, useDeferredValue } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ChevronRight, Search, MapPin, TrendingUp, TrendingDown, Minus,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useRegionProfile, formatRegionValue, shortUnit, yearDelta, pluralRu,
} from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import Breadcrumbs from '../components/Breadcrumbs';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import useSearchTracking from '../lib/useSearchTracking';
import { regionTrail, breadcrumbJsonLd } from '../lib/breadcrumbs';
import {
  regionHubPath,
  regionIndicatorPath,
  regionPath,
} from '../lib/sitePaths';

function normalize(s) {
  return (s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
}

function DeltaBadge({ value, prevValue }) {
  const d = yearDelta(value, prevValue);
  if (!d) return null;
  const Icon = d.up ? TrendingUp : d.down ? TrendingDown : Minus;
  const cls = d.up ? 'text-positive' : d.down ? 'text-negative' : 'text-text-tertiary';
  return (
    <span className={`inline-flex items-center gap-0.5 font-mono text-[10px] tabular-nums ${cls}`}>
      <Icon size={10} />
      {Math.abs(d.pct) >= 0.1 ? `${Math.abs(d.pct).toFixed(1).replace('.', ',')}%` : '<0,1%'}
    </span>
  );
}

function HeadlineCard({ item, slug }) {
  return (
    <Link
      to={regionIndicatorPath(slug, item.code)}
      className="group rounded-xl border border-border-subtle bg-surface p-3.5 transition-all hover:border-border-champagne hover:shadow-sm"
    >
      <div className="text-[11px] uppercase tracking-wide text-text-tertiary">{item.label}</div>
      <div className="mt-1 font-mono text-lg font-semibold leading-none text-text-primary">
        {formatRegionValue(item.value)}
        <span className="ml-1 text-[11px] font-normal text-text-secondary">{shortUnit(item.unit)}</span>
      </div>
      <div className="mt-1.5 flex items-center justify-between gap-2">
        <span className="font-mono text-[11px] text-text-tertiary">{item.year}</span>
        <DeltaBadge value={item.value} prevValue={item.prev_value} />
      </div>
    </Link>
  );
}

function IndicatorRow({ item, slug }) {
  return (
    <Link
      to={regionIndicatorPath(slug, item.code)}
      className="group flex flex-col gap-2 rounded-xl border border-border-subtle bg-white px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-[0_12px_30px_rgba(35,30,16,0.06)] sm:min-h-[84px] sm:flex-row sm:items-center sm:gap-3 sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0 flex-1">
        <div className="text-[13px] leading-snug text-text-primary transition-colors group-hover:text-champagne sm:text-[14px]">
          {item.name}
        </div>
        <div className="mt-1 text-[10px] text-text-tertiary sm:mt-1.5">
          {shortUnit(item.unit) || item.unit}
        </div>
      </div>
      <div className="flex items-baseline justify-between gap-3 border-t border-border-subtle/60 pt-2 sm:w-[7.25rem] sm:shrink-0 sm:flex-col sm:items-end sm:justify-center sm:border-0 sm:pt-0 sm:text-right">
        <div className="font-mono text-[15px] font-semibold tabular-nums text-text-primary sm:text-[14px] sm:font-medium">
          {formatRegionValue(item.value)}
        </div>
        <div className="flex items-center gap-1.5">
          <DeltaBadge value={item.value} prevValue={item.prev_value} />
          <span className="font-mono text-[10px] text-text-tertiary">{item.year}</span>
        </div>
      </div>
    </Link>
  );
}

export default function RegionProfile() {
  const { slug } = useParams();
  const { data, isLoading, isError, refetch, isFetching } = useRegionProfile(slug);
  const [query, setQuery] = useState('');
  const [activeSection, setActiveSection] = useState('');
  const deferredQuery = useDeferredValue(query);
  const searching = normalize(deferredQuery).length > 0;

  const regionName = data?.region?.name;
  useDocumentMeta(regionName ? {
    title: `${regionName} — статистика региона: население, зарплата, ВРП, цены`,
    description:
      `${regionName}: ${data.sections.reduce((n, s) => n + s.indicators.length, 0)} социально-экономических показателей Росстата с 1990 года — население, зарплаты, безработица, ВРП, инвестиции, строительство, цены. Графики и место региона в рейтингах России.`,
    path: regionPath(slug),
  } : null);

  useEffect(() => {
    if (!regionName) return undefined;
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.id = 'region-breadcrumb-jsonld';
    script.textContent = JSON.stringify(breadcrumbJsonLd(regionTrail(regionName, slug)));
    document.getElementById('region-breadcrumb-jsonld')?.remove();
    document.head.appendChild(script);
    return () => script.remove();
  }, [regionName, slug]);

  const filteredSections = useMemo(() => {
    if (!data) return [];
    const q = normalize(deferredQuery);
    if (!q) return data.sections;
    return data.sections
      .map((s) => ({ ...s, indicators: s.indicators.filter((i) => normalize(i.name).includes(q)) }))
      .filter((s) => s.indicators.length > 0);
  }, [data, deferredQuery]);

  const foundIndicators = filteredSections.reduce((n, s) => n + s.indicators.length, 0);
  useSearchTracking('region-profile', deferredQuery, foundIndicators);

  const headlineOrder = ['1.1', '3.4', '2.10.1', '8.2', '10.1', '20.1', '3.12', '8.1'];
  const headline = data
    ? headlineOrder.map((tc) => data.headline[tc]).filter(Boolean)
    : [];

  const resolvedActive = filteredSections.some((s) => String(s.num) === String(activeSection))
    ? filteredSections.find((s) => String(s.num) === String(activeSection))?.num
    : (filteredSections[0]?.num || '');
  const visibleSections = searching
    ? filteredSections
    : filteredSections.filter((s) => s.num === resolvedActive);

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-hidden px-4 pb-24 pt-24 sm:px-6">
      <Breadcrumbs items={regionTrail(regionName || '…', slug)} />

      {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}
      {isLoading && (
        <div className="space-y-4">
          <SkeletonBox className="h-10 w-72" />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => <SkeletonBox key={i} className="h-24 rounded-xl" />)}
          </div>
        </div>
      )}

      {data && (
        <>
          <div className="mb-8">
            {data.region.district_name && (
              <div className="mb-2 flex items-center gap-1.5 font-mono text-xs uppercase tracking-widest text-champagne">
                <MapPin size={13} />
                {data.region.district_name}
              </div>
            )}
            <h1 className="font-display text-[1.65rem] font-bold leading-tight text-text-primary sm:text-4xl">
              {data.region.name}
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-text-secondary">
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

          {headline.length > 0 && (
            <div className="mb-8 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {headline.map((h) => <HeadlineCard key={h.code} item={h} slug={slug} />)}
            </div>
          )}

          <div className="relative mb-6">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Найти показатель: зарплата, жильё, урожайность…"
              className="w-full rounded-xl border border-border-subtle bg-surface py-3 pl-10 pr-4 text-sm text-text-primary shadow-sm placeholder:text-text-tertiary focus:border-border-champagne focus:outline-none"
              aria-label="Поиск показателя в регионе"
            />
          </div>

          {searching && filteredSections.length === 0 && (
            <div className="rounded-2xl border border-border-subtle bg-surface p-6 text-center text-sm text-text-secondary">
              По запросу «{query}» показателей не найдено.
              {' '}
              <button type="button" onClick={() => setQuery('')} className="text-champagne hover:underline">
                Сбросить поиск
              </button>
            </div>
          )}

          {!searching && (
            <MobileNavSelect
              label="Темы"
              value={String(resolvedActive)}
              onChange={(v) => setActiveSection(Number(v))}
              options={filteredSections.map((sec) => ({
                value: String(sec.num),
                label: sec.name,
                count: sec.indicators.length,
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
                  {filteredSections.map((sec) => (
                    <button
                      key={sec.num}
                      type="button"
                      onClick={() => setActiveSection(sec.num)}
                      className={[
                        'flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                        resolvedActive === sec.num
                          ? 'bg-champagne/12 font-medium text-champagne'
                          : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                      ].join(' ')}
                    >
                      <span className="min-w-0 truncate">{sec.name}</span>
                      <span className="shrink-0 font-mono text-[10px] opacity-60">{sec.indicators.length}</span>
                    </button>
                  ))}
                </div>
              </aside>
            )}

            <div className="min-w-0 space-y-8">
              {visibleSections.map((sec) => (
                <section key={sec.num} data-block={`region-section-${sec.num}`}>
                  <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4">
                    <div className="min-w-0">
                      <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
                        {searching ? 'Результаты поиска' : 'Показатели'}
                      </div>
                      <h2 className="mt-1 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">{sec.name}</h2>
                    </div>
                    <span className="shrink-0 font-mono text-xs text-text-tertiary">{sec.indicators.length}</span>
                  </div>
                  <div className="grid gap-2 sm:gap-2.5 xl:grid-cols-2">
                    {sec.indicators.map((item) => (
                      <IndicatorRow key={item.code} item={item} slug={slug} />
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
