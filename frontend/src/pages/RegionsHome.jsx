// Лендинг регионального блока: /regions
// Мобильный сценарий: поиск сверху → чипы округов → карточки регионов.
// Режим «Карта»: choropleth по выбранному показателю (предустановки + поиск по
// всем 489), тап по региону — карточка показателя; режим «Обзор» — профиль
// региона. Зум/пан и PNG-выгрузка с watermark — созвон «На правки 13».
import { useMemo, useState, useRef, useDeferredValue, lazy, Suspense } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Search, MapPin, ChevronRight, Database, List, Map as MapIcon,
  Image as ImageIcon, X,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useRegionsLanding, useRegionsHeatmap, useRegionsHeatmapSeries,
  useRegionsCatalog, formatRegionValue,
} from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import { exportNodeToPng } from '../lib/chartImage';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';

const RegionsMap = lazy(() => import('../components/RegionsMap'));
const MapTimeline = lazy(() => import('../components/MapTimeline'));

// Спец-режим карты: клик по региону открывает его профиль, без раскраски.
const OVERVIEW = '__overview';

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

/**
 * Поиск произвольного показателя для карты («добавьте свой» — созвон
 * «На правки 13»): компактный combobox по каталогу из 489 показателей.
 *
 * Робастность (правки 2026-07-05): dropdown открывается и при вводе/клике,
 * а не только по onFocus (после «сбросить» фокус оставался в поле и печать
 * не подсвечивалась — value показывал пустую строку при open=false);
 * пустой результат рисует «Ничего не найдено», а не молча прячет список;
 * каждый набранный запрос уходит в спрос-аналитику (search_query).
 */
function MapMetricSearch({ activeCode, onPick, onClear, activeName }) {
  const catalog = useRegionsCatalog();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  const results = useMemo(() => {
    const sections = catalog.data?.sections || [];
    const all = sections.flatMap(s =>
      s.indicators.map(i => ({ code: i.code, name: i.name, section: s.name })));
    const q = normalize(query);
    if (!q) return all.slice(0, 50);
    return all.filter(i => normalize(i.name).includes(q)).slice(0, 50);
  }, [catalog.data, query]);

  useSearchTracking('map-metric', open ? query : '', results.length);

  const isCustom = !!activeCode;
  const openWith = (q) => { setOpen(true); setQuery(q); };

  return (
    <div className="relative min-w-0 flex-1 sm:max-w-xs">
      <div className={`flex items-center gap-1.5 px-3 py-2 sm:py-1.5 rounded-full text-xs border transition-colors ${
        isCustom
          ? 'bg-champagne/15 text-champagne border-transparent'
          : 'bg-surface border-border-subtle text-text-secondary focus-within:border-border-champagne'
      }`}
      >
        <Search size={13} className="shrink-0" />
        <input
          type="text"
          value={open ? query : (isCustom ? activeName : '')}
          placeholder="Свой показатель…"
          onFocus={() => openWith('')}
          onClick={() => { if (!open) openWith(''); }}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onChange={(e) => { if (!open) setOpen(true); setQuery(e.target.value); }}
          className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-text-tertiary"
          aria-label="Найти показатель для карты"
          role="combobox"
          aria-expanded={open}
        />
        {isCustom && !open && (
          <button
            type="button"
            aria-label="Сбросить показатель"
            onMouseDown={(e) => { e.preventDefault(); onClear(); }}
            className="shrink-0 text-champagne/70 hover:text-champagne"
          >
            <X size={13} />
          </button>
        )}
      </div>
      {open && (
        <div className="absolute right-0 sm:left-0 sm:right-auto z-30 mt-2 w-[min(calc(100vw-2rem),26rem)] max-h-72 overflow-auto rounded-xl border border-border-subtle bg-surface shadow-2xl">
          {catalog.isLoading ? (
            <div className="px-3.5 py-3 text-[13px] text-text-tertiary">Загрузка каталога…</div>
          ) : results.length === 0 ? (
            <div className="px-3.5 py-3 text-[13px] text-text-tertiary">
              По запросу «{query}» ничего не найдено. Попробуйте короче: «зарплата», «врач», «жильё».
            </div>
          ) : (
            results.map(i => (
              <button
                key={i.code}
                type="button"
                onMouseDown={(e) => { e.preventDefault(); onPick(i); setOpen(false); setQuery(''); }}
                className="w-full px-3.5 py-2 text-left hover:bg-surface-hover transition-colors"
              >
                <div className="text-[13px] text-text-primary leading-snug">{i.name}</div>
                <div className="text-[11px] text-text-tertiary">{i.section}</div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
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
  // Произвольный показатель из поиска: { code, name } или null (чипы-пресеты).
  const [customMetric, setCustomMetric] = useState(null);
  const isOverview = mapMetric === OVERVIEW;
  const activeMapCode = customMetric?.code || (isOverview ? null : mapMetric);
  // Серия по всем годам — для карты с ползунком времени.
  const series = useRegionsHeatmapSeries(activeMapCode, view === 'map' && !!activeMapCode);
  const mapCardRef = useRef(null);
  const [exportingMap, setExportingMap] = useState(false);

  // Год, выбранный ползунком (null → показываем последний доступный).
  // Источник года живёт внутри MapTimeline (self-driven анимация); сюда
  // прилетает через onYearChange только для раскраски карты и подписи.
  const [pickedYear, setPickedYear] = useState(null);
  const seriesYears = series.data?.years || null;
  const mapYear = useMemo(() => {
    if (!seriesYears?.length) return null;
    return pickedYear != null && seriesYears.includes(pickedYear)
      ? pickedYear
      : seriesYears[seriesYears.length - 1];
  }, [seriesYears, pickedYear]);

  // Данные для блока «Контрасты России» (list-режим).
  const wagesHeat = useRegionsHeatmap(MAP_METRICS[0].code, view === 'list');
  const unempHeat = useRegionsHeatmap('uroven-bezrabotitsy', view === 'list');

  const setView = (v) => {
    setSearchParams(v === 'map' ? { view: 'map' } : {}, { replace: true });
    track(events.REGIONS_VIEW_TOGGLE, { view: v });
  };

  const heatmapValues = useMemo(() => {
    if (!series.data || mapYear == null) return null;
    const slice = series.data.values_by_year[String(mapYear)];
    if (!slice) return null;
    return new Map(Object.entries(slice));
  }, [series.data, mapYear]);

  const namesBySlug = useMemo(() => {
    const out = {};
    (data?.districts || []).forEach(d => d.regions.forEach(r => { out[r.slug] = r.name; }));
    return out;
  }, [data]);

  useDocumentMeta({
    title: 'Регионы России — социально-экономические показатели 85 субъектов РФ',
    description:
      'Статистика по 85 регионам России: население, зарплаты, ВРП, безработица, инвестиции, цены — 489 показателей Росстата с 1990 года. Графики, рейтинги регионов, сравнение с общероссийским уровнем.',
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

  // Спрос-аналитика: что ищут в поиске регионов (в т.ч. запросы без результата).
  useSearchTracking('regions-list', deferredQuery, totalShown);

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
          Социально-экономические показатели 85 субъектов Российской Федерации:
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
            <div data-block="contrasts" className="mb-4 bg-surface border border-border-subtle rounded-xl p-4 space-y-2">
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
            <div className="mt-2 flex gap-1.5 overflow-x-auto pb-1 scrollbar-hide" role="tablist" aria-label="Федеральные округа">
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
          {/* Показатель карты: чипы-пресеты (скроллятся) + поиск любого из 489.
              Поиск ВНЕ overflow-контейнера — иначе его выпадающий список
              обрезается прокруткой чипов (баг «Свой показатель нельзя найти»). */}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center mb-3">
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-hide min-w-0" role="tablist" aria-label="Показатель карты">
              <button
                role="tab"
                aria-selected={isOverview && !customMetric}
                onClick={() => { setMapMetric(OVERVIEW); setCustomMetric(null); setPickedYear(null); track(events.REGIONS_MAP_METRIC, { metric: 'Обзор' }); }}
                title="Клик по региону открывает его карточку со всеми показателями"
                className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  isOverview && !customMetric
                    ? 'bg-champagne/15 text-champagne'
                    : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
                }`}
              >
                Обзор
              </button>
              {MAP_METRICS.map(m => (
                <button
                  key={m.code}
                  role="tab"
                  aria-selected={mapMetric === m.code && !customMetric}
                  onClick={() => { setMapMetric(m.code); setCustomMetric(null); setPickedYear(null); track(events.REGIONS_MAP_METRIC, { metric: m.label }); }}
                  className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    mapMetric === m.code && !customMetric
                      ? 'bg-champagne/15 text-champagne'
                      : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <MapMetricSearch
              activeCode={customMetric?.code}
              activeName={customMetric?.name || ''}
              onPick={(i) => {
                setCustomMetric({ code: i.code, name: i.name });
                setPickedYear(null);
                track(events.REGIONS_MAP_METRIC, { metric: `search:${i.code}` });
              }}
              onClear={() => { setCustomMetric(null); setPickedYear(null); }}
            />
          </div>

          <div data-block="regions-map" className="bg-surface border border-border-subtle rounded-xl p-3 sm:p-5 relative" ref={mapCardRef}>
            <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
              <div className="text-xs text-text-tertiary min-w-0">
                {activeMapCode && series.data ? (
                  <>
                    {series.data.indicator.name}
                    {mapYear != null ? `, ${mapYear} год` : ''}
                    {series.data.indicator.unit ? `, ${series.data.indicator.unit}` : ''}.
                    {' '}Нажмите на регион, чтобы открыть его показатель.
                  </>
                ) : (
                  'Нажмите на регион, чтобы открыть его карточку со всеми показателями.'
                )}
              </div>
              <button
                type="button"
                data-no-export="true"
                disabled={exportingMap}
                onClick={async () => {
                  if (exportingMap) return;
                  setExportingMap(true);
                  const ok = await exportNodeToPng(mapCardRef.current, {
                    filename: `regions-map_${activeMapCode || 'overview'}.png`,
                    watermark: true,
                  }).catch(() => false);
                  setExportingMap(false);
                  if (ok) track(events.CHART_IMAGE_DOWNLOAD, { indicator: `regions-map:${activeMapCode || 'overview'}` });
                }}
                title="Скачать карту картинкой"
                aria-label="Скачать карту картинкой"
                className="shrink-0 text-xs px-2 py-1 rounded-full border border-border-subtle text-text-tertiary hover:text-champagne hover:border-border-champagne transition-colors inline-flex items-center gap-1 disabled:opacity-50"
              >
                <ImageIcon size={12} /> PNG
              </button>
            </div>
            <Suspense fallback={<SkeletonBox className="h-80 rounded-xl" />}>
              <RegionsMap
                valuesBySlug={activeMapCode ? heatmapValues : null}
                transitionMs={activeMapCode ? 650 : 150}
                unit={series.data?.indicator?.unit || ''}
                nameBySlug={namesBySlug}
                onSelect={(slug) => {
                  track(events.REGIONS_MAP_SELECT, { region: slug, metric: activeMapCode || 'overview' });
                  navigate(activeMapCode ? `/region/${slug}/${activeMapCode}` : `/region/${slug}`);
                }}
              />
            </Suspense>

            {/* Ползунок времени: доступен, когда выбран показатель и есть ≥2 лет. */}
            {activeMapCode && seriesYears && seriesYears.length > 1 && mapYear != null && (
              <Suspense fallback={null}>
                <MapTimeline
                  key={activeMapCode}
                  years={seriesYears}
                  initialYear={seriesYears[seriesYears.length - 1]}
                  onYearChange={setPickedYear}
                  metric={activeMapCode}
                />
              </Suspense>
            )}
          </div>
          <p className="mt-3 text-xs text-text-tertiary leading-relaxed">
            {activeMapCode
              ? 'Интенсивность цвета — позиция региона относительно других в выбранном году (шкала пересчитывается для каждого года). Двигайте ползунок или нажмите «play», чтобы увидеть, как менялась расстановка регионов по годам. '
              : 'Режим обзора: клик по региону открывает его профиль. '}
            Москва, Санкт-Петербург и Севастополь показаны точками. Кнопки «+»/«−»
            приближают карту, в приближении её можно перетаскивать.
          </p>
        </div>
      )}
    </div>
  );
}
