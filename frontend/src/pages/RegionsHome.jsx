// Лендинг регионального блока: /regions
// Мобильный сценарий: поиск сверху → чипы округов → карточки регионов.
// Режим «Карта»: choropleth по выбранному показателю, тап по региону —
// переход сразу на карточку этого показателя в регионе.
import { useMemo, useState, useDeferredValue, lazy, Suspense } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Search, MapPin, ChevronRight, Database, List, Map as MapIcon } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useRegionsLanding, useRegionsHeatmap, formatRegionValue } from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import { track, events } from '../lib/track';

const RegionsMap = lazy(() => import('../components/RegionsMap'));

const DISTRICT_SHORT = {
  cfo: 'Центральный',
  szfo: 'Северо-Западный',
  'ufo-south': 'Южный',
  skfo: 'Северо-Кавказский',
  pfo: 'Приволжский',
  urfo: 'Уральский',
  sfo: 'Сибирский',
  dfo: 'Дальневосточный',
};

// Показатели-переключатели карты: подпись → код регионального показателя.
const MAP_METRICS = [
  { code: 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy', label: 'Зарплата' },
  { code: 'chislennost-naseleniya', label: 'Население' },
  { code: 'uroven-bezrabotitsy', label: 'Безработица' },
  { code: 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', label: 'ВРП на душу' },
  { code: 'investitsii-v-osnovnoy-kapital', label: 'Инвестиции' },
  { code: 'chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy', label: 'Бедность' },
];

function normalize(s) {
  return s.toLowerCase().replace(/ё/g, 'е').replace(/[^а-яa-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
}

// «Контрасты России»: живой блок-приманка — крайние значения по метрике.
function ContrastRow({ heat, metricLabel, betterIsLow = false }) {
  const rows = heat?.data?.values;
  if (!rows?.length) return null;
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  const hi = sorted[0];
  const lo = sorted[sorted.length - 1];
  const first = betterIsLow ? lo : hi;
  const second = betterIsLow ? hi : lo;
  const code = heat.data.indicator.code;
  const unit = heat.data.indicator.unit;
  const short = unit === 'рублей' ? '₽' : unit === 'в процентах' ? '%' : '';
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-x-3 gap-y-0.5 text-[13px]">
      <span className="text-text-tertiary w-28 shrink-0">{metricLabel}</span>
      <span className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <Link to={`/region/${first.slug}/${code}`} className="text-text-primary hover:text-champagne transition-colors">
          {first.name} <span className="font-mono text-positive">{formatRegionValue(first.value)} {short}</span>
        </Link>
        <span className="text-text-tertiary">против</span>
        <Link to={`/region/${second.slug}/${code}`} className="text-text-primary hover:text-champagne transition-colors">
          {second.name} <span className="font-mono text-negative">{formatRegionValue(second.value)} {short}</span>
        </Link>
      </span>
    </div>
  );
}

function RegionCard({ region }) {
  const pop = region.stats['1.1'];
  const wage = region.stats['3.4'];
  const unemp = region.stats['2.10.1'];
  return (
    <Link
      to={`/region/${region.slug}`}
      className="group flex items-center justify-between gap-3 bg-surface border border-border-subtle rounded-xl px-4 py-3.5 hover:border-border-champagne hover:shadow-sm transition-all"
    >
      <div className="min-w-0">
        <div className="font-medium text-text-primary text-[15px] leading-snug truncate group-hover:text-champagne transition-colors">
          {region.name}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-text-secondary font-mono">
          {pop && <span>{formatRegionValue(pop.value)} тыс чел.</span>}
          {wage && <span>{formatRegionValue(wage.value)} ₽</span>}
          {unemp && <span>безраб. {formatRegionValue(unemp.value)}%</span>}
        </div>
      </div>
      <ChevronRight size={16} className="shrink-0 text-text-tertiary group-hover:text-champagne transition-colors" />
    </Link>
  );
}

export default function RegionsHome() {
  const { data, isLoading, isError, refetch, isFetching } = useRegionsLanding();
  const [query, setQuery] = useState('');
  const [activeDistrict, setActiveDistrict] = useState(null);
  const deferredQuery = useDeferredValue(query);
  const navigate = useNavigate();

  // Режим просмотра: список (по умолчанию) или карта — сохраняется в URL.
  const [searchParams, setSearchParams] = useSearchParams();
  const view = searchParams.get('view') === 'map' ? 'map' : 'list';
  const [mapMetric, setMapMetric] = useState(MAP_METRICS[0].code);
  const heatmap = useRegionsHeatmap(mapMetric, view === 'map');

  // Данные для блока «Контрасты России» (list-режим).
  const wagesHeat = useRegionsHeatmap(MAP_METRICS[0].code, view === 'list');
  const unempHeat = useRegionsHeatmap('uroven-bezrabotitsy', view === 'list');

  const setView = (v) => {
    setSearchParams(v === 'map' ? { view: 'map' } : {}, { replace: true });
    track(events.REGIONS_VIEW_TOGGLE, { view: v });
  };

  const heatmapValues = useMemo(() => {
    if (!heatmap.data) return null;
    return new Map(heatmap.data.values.map(v => [v.slug, v.value]));
  }, [heatmap.data]);

  const namesBySlug = useMemo(() => {
    const out = {};
    (data?.districts || []).forEach(d => d.regions.forEach(r => { out[r.slug] = r.name; }));
    return out;
  }, [data]);

  useDocumentMeta({
    title: 'Регионы России — социально-экономические показатели всех 85 субъектов РФ',
    description:
      'Статистика по всем 85 регионам России: население, зарплаты, ВРП, безработица, инвестиции, цены и ещё 450+ показателей Росстата с 1990 года. Графики, рейтинги регионов, сравнение с общероссийским уровнем.',
    path: '/regions',
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = normalize(deferredQuery);
    return data.districts
      .filter(d => !activeDistrict || d.slug === activeDistrict)
      .map(d => ({
        ...d,
        regions: q
          ? d.regions.filter(r => normalize(r.name).includes(q))
          : d.regions,
      }))
      .filter(d => d.regions.length > 0);
  }, [data, deferredQuery, activeDistrict]);

  const totalShown = filtered.reduce((n, d) => n + d.regions.length, 0);

  return (
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-20">
      {/* Hero */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-champagne text-xs font-mono uppercase tracking-widest mb-3">
          <MapPin size={14} />
          Региональная статистика
        </div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold text-text-primary leading-tight">
          Регионы России
        </h1>
        <p className="mt-3 text-text-secondary text-[15px] leading-relaxed max-w-2xl">
          Социально-экономические показатели всех 85 субъектов Российской Федерации:
          население, зарплаты, валовой региональный продукт, инвестиции, цены —
          официальные данные Росстата с 1990 года.
        </p>
        {data && (
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs font-mono text-text-tertiary">
            <span className="inline-flex items-center gap-1.5">
              <Database size={12} />
              {data.totals.points.toLocaleString('ru-RU')} значений
            </span>
            <span>{data.totals.indicators} показателей</span>
            <span>{data.totals.regions} регионов</span>
          </div>
        )}
      </div>

      {/* Переключатель Список / Карта */}
      <div className="flex items-center gap-1 mb-2 bg-surface border border-border-subtle rounded-xl p-1 w-fit" role="tablist" aria-label="Режим просмотра">
        <button
          role="tab"
          aria-selected={view === 'list'}
          onClick={() => setView('list')}
          className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            view === 'list' ? 'bg-champagne/15 text-champagne' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <List size={15} /> Список
        </button>
        <button
          role="tab"
          aria-selected={view === 'map'}
          onClick={() => setView('map')}
          className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            view === 'map' ? 'bg-champagne/15 text-champagne' : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <MapIcon size={15} /> Карта
        </button>
      </div>

      {view === 'list' && (
        <>
          {/* Контрасты России: цепляющие крайние значения */}
          {(wagesHeat.data || unempHeat.data) && (
            <div className="mb-4 bg-surface border border-border-subtle rounded-xl p-4 space-y-2">
              <div className="text-xs font-mono uppercase tracking-widest text-champagne mb-1">Контрасты России</div>
              <ContrastRow heat={wagesHeat} metricLabel="Зарплата" />
              <ContrastRow heat={unempHeat} metricLabel="Безработица" betterIsLow />
            </div>
          )}

          {/* Поиск: sticky на мобильных, всегда под рукой */}
          <div className="sticky top-14 z-10 -mx-4 px-4 py-2 bg-obsidian/95 backdrop-blur-sm">
            <div className="relative">
              <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Найти регион: Севастополь, Татарстан, Приморский…"
                className="w-full pl-10 pr-4 py-3 rounded-xl bg-surface border border-border-subtle text-[15px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-border-champagne focus:ring-2 focus:ring-champagne/10 transition-all"
                aria-label="Поиск региона"
              />
            </div>
            {/* Чипы округов — горизонтальный скролл на мобильных */}
            <div className="mt-2 flex gap-1.5 overflow-x-auto pb-1 scrollbar-none" role="tablist" aria-label="Федеральные округа">
              <button
                onClick={() => setActiveDistrict(null)}
                className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  !activeDistrict
                    ? 'bg-champagne/15 text-champagne'
                    : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
                }`}
              >
                Все округа
              </button>
              {(data?.districts || []).map(d => (
                <button
                  key={d.slug}
                  onClick={() => setActiveDistrict(activeDistrict === d.slug ? null : d.slug)}
                  className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    activeDistrict === d.slug
                      ? 'bg-champagne/15 text-champagne'
                      : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {DISTRICT_SHORT[d.slug] || d.name}
                </button>
              ))}
            </div>
          </div>

          {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}

          {isLoading && (
            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {Array.from({ length: 10 }).map((_, i) => <SkeletonBox key={i} className="h-16 rounded-xl" />)}
            </div>
          )}

          {/* Список по округам */}
          <div className="mt-6 space-y-8">
            {filtered.map(d => (
              <section key={d.slug} aria-labelledby={`district-${d.slug}`}>
                <h2 id={`district-${d.slug}`} className="text-sm font-semibold text-text-secondary uppercase tracking-wide mb-3 flex items-baseline gap-2">
                  {d.name}
                  <span className="font-mono text-xs text-text-tertiary normal-case tracking-normal">{d.regions.length}</span>
                </h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  {d.regions.map(r => <RegionCard key={r.slug} region={r} />)}
                </div>
              </section>
            ))}
            {!isLoading && totalShown === 0 && (
              <div className="text-center py-16 text-text-secondary">
                По запросу «{query}» регионов не найдено
              </div>
            )}
          </div>
        </>
      )}

      {view === 'map' && (
        <div className="mt-4">
          {/* Чипы показателей карты */}
          <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-none mb-3" role="tablist" aria-label="Показатель карты">
            {MAP_METRICS.map(m => (
              <button
                key={m.code}
                role="tab"
                aria-selected={mapMetric === m.code}
                onClick={() => { setMapMetric(m.code); track(events.REGIONS_MAP_METRIC, { metric: m.label }); }}
                className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  mapMetric === m.code
                    ? 'bg-champagne/15 text-champagne'
                    : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          <div className="bg-surface border border-border-subtle rounded-xl p-3 sm:p-5">
            {heatmap.data && (
              <div className="mb-2 text-xs text-text-tertiary">
                {heatmap.data.indicator.name}, {heatmap.data.year} год
                {heatmap.data.indicator.unit ? `, ${heatmap.data.indicator.unit}` : ''}.
                Нажмите на регион, чтобы открыть его показатель.
              </div>
            )}
            <Suspense fallback={<SkeletonBox className="h-80 rounded-xl" />}>
              <RegionsMap
                valuesBySlug={heatmapValues}
                unit={heatmap.data?.indicator?.unit || ''}
                nameBySlug={namesBySlug}
                onSelect={(slug) => {
                  track(events.REGIONS_MAP_SELECT, { region: slug, metric: mapMetric });
                  navigate(`/region/${slug}/${mapMetric}`);
                }}
              />
            </Suspense>
          </div>
          <p className="mt-3 text-xs text-text-tertiary leading-relaxed">
            Интенсивность цвета — квантильная шкала по регионам за последний доступный год.
            Москва, Санкт-Петербург и Севастополь показаны точками.
          </p>
        </div>
      )}
    </div>
  );
}
