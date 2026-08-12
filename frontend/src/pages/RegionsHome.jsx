// Лендинг регионального блока: /regions
// Мобильный сценарий: поиск сверху → чипы округов → карточки регионов.
// Режим «Карта»: choropleth по выбранному показателю (предустановки + поиск по
// всем 489), тап по региону — карточка показателя; режим «Обзор» — профиль
// региона. Зум/пан — созвон «На правки 13». PNG/GIF-выгрузка карты — только для
// зарегистрированных, без watermark (правило 2026-07-08). Состояние карты в URL:
// /regions/map/{code}?year=YYYY (legacy query → 301/client replace на канон).
import { useMemo, useState, useRef, useDeferredValue, useCallback, useEffect, lazy, Suspense } from 'react';
import { Link, useNavigate, useSearchParams, useLocation, useParams } from 'react-router-dom';
import {
  Search, MapPin, ChevronRight, Database, List, Map as MapIcon,
  Image as ImageIcon, Film, X, RefreshCw,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import {
  useRegionsLanding, useRegionsHeatmap, useRegionsHeatmapSeries,
  useRegionsCatalog, formatRegionValue,
} from '../lib/regionsApi';
import ApiRetryBanner from '../components/ApiRetryBanner';
import { SkeletonBox } from '../components/Skeleton';
import MobileNavSelect from '../components/MobileNavSelect';
import { exportNodeToPng } from '../lib/chartImage';
import { buildRegionsMapGif, downloadBlob } from '../lib/regionsMapGif';
import {
  parseRegionsMapLocation, buildRegionsMapLocation, buildRegionsMapHref,
  locationsEqual, MAP_OVERVIEW, DEFAULT_MAP_CODE,
} from '../lib/regionsMapUrl';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';
import { useAuth } from '../context/authContext';

const RegionsMap = lazy(() => import('../components/RegionsMap'));
const MapTimeline = lazy(() => import('../components/MapTimeline'));

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

const MAP_METRICS = [
  { code: 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy', label: 'Зарплата' },
  { code: 'chislennost-naseleniya', label: 'Население' },
  { code: 'uroven-bezrabotitsy', label: 'Безработица' },
  { code: 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', label: 'ВРП на душу' },
  { code: 'investitsii-v-osnovnoy-kapital', label: 'Инвестиции' },
  { code: 'chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy', label: 'Бедность' },
];

const PRESET_CODES = new Set(MAP_METRICS.map((m) => m.code));

function normalize(s) {
  return s.toLowerCase().replace(/ё/g, 'е').replace(/[^а-яa-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
}

function MapMetricSearch({ activeCode, onPick, onClear, activeName }) {
  const catalog = useRegionsCatalog();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  const results = useMemo(() => {
    const sections = catalog.data?.sections || [];
    const all = sections.flatMap((s) =>
      s.indicators.map((i) => ({ code: i.code, name: i.name, section: s.name })));
    const q = normalize(query);
    if (!q) return all.slice(0, 50);
    return all.filter((i) => normalize(i.name).includes(q)).slice(0, 50);
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
            results.map((i) => (
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

const CONTRAST_METRICS = [
  { code: 'srednemesyachnaya-nominalnaya-nachislennaya-zarabotnaya-plata-rabotnikov-organizatsiy', label: 'Зарплата' },
  { code: 'uroven-bezrabotitsy', label: 'Безработица', betterIsLow: true },
  { code: 'valovoy-regionalnyy-produkt-na-dushu-naseleniya', label: 'ВРП на душу' },
  { code: 'chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy', label: 'Бедность', betterIsLow: true },
  { code: 'investitsii-v-osnovnoy-kapital', label: 'Инвестиции' },
  { code: 'chislennost-naseleniya', label: 'Население' },
];
const CONTRAST_PAGE_SIZE = 2;
const CONTRAST_PAGES = Math.ceil(CONTRAST_METRICS.length / CONTRAST_PAGE_SIZE);

function ContrastRow({ heat, metricLabel, betterIsLow = false }) {
  const rows = heat?.data?.values;
  if (!rows?.length) return null;
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  const hi = sorted[0];
  const lo = sorted[sorted.length - 1];
  const first = betterIsLow ? lo : hi;
  const second = betterIsLow ? hi : lo;
  const code = heat.data.indicator.code;
  const unit = heat.data.indicator.unit || '';
  const short = /процент/.test(unit) ? '%'
    : /миллионов рублей/.test(unit) ? 'млн ₽'
    : unit === 'рублей' ? '₽'
    : /тысяч человек/.test(unit) ? 'тыс. чел.'
    : '';
  const ratio = second.value ? Math.abs(first.value / second.value) : null;
  const ratioLabel = ratio && ratio >= 1.05
    ? `× ${ratio.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}`
    : null;
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
        {ratioLabel && (
          <span className="text-[11px] font-mono text-champagne/70" title="Во сколько раз лидер превосходит аутсайдера">
            {ratioLabel}
          </span>
        )}
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
      className="group flex items-center justify-between gap-2.5 rounded-xl border border-border-subtle bg-surface px-3.5 py-3 transition-all hover:border-border-champagne hover:shadow-sm sm:gap-3 sm:px-4 sm:py-3.5"
    >
      <div className="min-w-0">
        <div className="truncate text-[14px] font-medium leading-snug text-text-primary transition-colors group-hover:text-champagne sm:text-[15px]">
          {region.name}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 font-mono text-[11px] text-text-secondary sm:gap-x-3 sm:text-xs">
          {pop && <span>{formatRegionValue(pop.value)} тыс чел.</span>}
          {wage && <span>{formatRegionValue(wage.value)} ₽</span>}
          {unemp && <span>безраб. {formatRegionValue(unemp.value)}%</span>}
        </div>
      </div>
      <ChevronRight size={16} className="hidden shrink-0 text-text-tertiary transition-colors group-hover:text-champagne sm:block" />
    </Link>
  );
}

export default function RegionsHome() {
  const { isAuthed } = useAuth();
  const { data, isLoading, isError, refetch, isFetching } = useRegionsLanding();
  const catalog = useRegionsCatalog();
  const [query, setQuery] = useState('');
  const [activeDistrict, setActiveDistrict] = useState(null);
  const deferredQuery = useDeferredValue(query);
  const navigate = useNavigate();
  const location = useLocation();
  const { code: pathCode } = useParams();
  const [searchParams] = useSearchParams();

  const { view, indicator: urlIndicator, year: urlYear } = parseRegionsMapLocation(
    location.pathname,
    searchParams,
  );

  // Legacy query на /regions?view=map… → канон /regions/map/{code}?year=
  useEffect(() => {
    if (location.pathname !== '/regions' && location.pathname !== '/regions/') return;
    if (searchParams.get('view') !== 'map') return;
    const next = buildRegionsMapLocation({
      view: 'map',
      indicator: urlIndicator || DEFAULT_MAP_CODE,
      year: urlYear,
    });
    navigate(`${next.pathname}${next.search}`, { replace: true });
  }, [location.pathname, searchParams, urlIndicator, urlYear, navigate]);

  const isOverview = urlIndicator === MAP_OVERVIEW;
  const activeMapCode = view !== 'map' || isOverview
    ? null
    : (urlIndicator || pathCode || DEFAULT_MAP_CODE);
  const isCustomMetric = !!(activeMapCode && !PRESET_CODES.has(activeMapCode));

  const customName = useMemo(() => {
    if (!isCustomMetric || !activeMapCode) return '';
    const sections = catalog.data?.sections || [];
    for (const s of sections) {
      const hit = s.indicators.find((i) => i.code === activeMapCode);
      if (hit) return hit.name;
    }
    return activeMapCode;
  }, [isCustomMetric, activeMapCode, catalog.data]);

  const series = useRegionsHeatmapSeries(activeMapCode, view === 'map' && !!activeMapCode);
  const mapCardRef = useRef(null);
  const [exportingMap, setExportingMap] = useState(false);
  const [exportingGif, setExportingGif] = useState(false);

  const seriesYears = series.data?.years || null;

  // Год — из URL (?year=); если нет или вне ряда — последний доступный.
  const mapYear = useMemo(() => {
    if (!seriesYears?.length) return null;
    if (urlYear != null && seriesYears.includes(urlYear)) return urlYear;
    return seriesYears[seriesYears.length - 1];
  }, [seriesYears, urlYear]);

  const syncMapUrl = useCallback((next) => {
    const desired = buildRegionsMapLocation(next);
    const current = { pathname: location.pathname, search: location.search || '' };
    if (locationsEqual(desired, current)) return;
    navigate(`${desired.pathname}${desired.search}`, { replace: true });
  }, [navigate, location.pathname, location.search]);

  const mapIndicatorParam = isOverview ? MAP_OVERVIEW : activeMapCode;

  const setMapYear = useCallback((y) => {
    syncMapUrl({
      view: 'map',
      indicator: mapIndicatorParam,
      year: y,
    });
  }, [syncMapUrl, mapIndicatorParam]);

  const contrastHeat0 = useRegionsHeatmap(CONTRAST_METRICS[0].code, view === 'list');
  const contrastHeat1 = useRegionsHeatmap(CONTRAST_METRICS[1].code, view === 'list');
  const contrastHeat2 = useRegionsHeatmap(CONTRAST_METRICS[2].code, view === 'list');
  const contrastHeat3 = useRegionsHeatmap(CONTRAST_METRICS[3].code, view === 'list');
  const contrastHeat4 = useRegionsHeatmap(CONTRAST_METRICS[4].code, view === 'list');
  const contrastHeat5 = useRegionsHeatmap(CONTRAST_METRICS[5].code, view === 'list');
  const contrastHeats = [contrastHeat0, contrastHeat1, contrastHeat2, contrastHeat3, contrastHeat4, contrastHeat5];
  const [contrastPage, setContrastPage] = useState(0);
  const contrastStart = contrastPage * CONTRAST_PAGE_SIZE;
  const contrastVisible = CONTRAST_METRICS.slice(contrastStart, contrastStart + CONTRAST_PAGE_SIZE)
    .map((m, i) => ({ ...m, heat: contrastHeats[contrastStart + i] }));

  const setView = (v) => {
    if (v === 'list') {
      syncMapUrl({ view: 'list' });
    } else {
      syncMapUrl({
        view: 'map',
        indicator: mapIndicatorParam || DEFAULT_MAP_CODE,
        year: activeMapCode && mapYear != null ? mapYear : null,
      });
    }
    track(events.REGIONS_VIEW_TOGGLE, { view: v });
  };

  const selectOverview = () => {
    syncMapUrl({ view: 'map', indicator: MAP_OVERVIEW });
    track(events.REGIONS_MAP_METRIC, { metric: 'Обзор' });
  };

  const selectPreset = (m) => {
    syncMapUrl({ view: 'map', indicator: m.code });
    track(events.REGIONS_MAP_METRIC, { metric: m.label });
  };

  const selectCustom = (i) => {
    syncMapUrl({ view: 'map', indicator: i.code });
    track(events.REGIONS_MAP_METRIC, { metric: `search:${i.code}` });
  };

  const clearCustom = () => {
    syncMapUrl({ view: 'map', indicator: DEFAULT_MAP_CODE });
  };

  const heatmapValues = useMemo(() => {
    if (!series.data || mapYear == null) return null;
    const slice = series.data.values_by_year[String(mapYear)];
    if (!slice) return null;
    return new Map(Object.entries(slice));
  }, [series.data, mapYear]);

  const namesBySlug = useMemo(() => {
    const out = {};
    (data?.districts || []).forEach((d) => d.regions.forEach((r) => { out[r.slug] = r.name; }));
    return out;
  }, [data]);

  const mapMetaTitle = series.data?.indicator?.name
    ? `${series.data.indicator.name} на карте регионов России`
    : isOverview
      ? 'Карта регионов России — обзор субъектов РФ'
      : 'Регионы России — социально-экономические показатели 85 субъектов РФ';
  const mapMetaDesc = series.data?.indicator?.name
    ? `${series.data.indicator.name} по 85 субъектам РФ на карте: динамика по годам, данные Росстата. Сравните регионы и откройте карточку показателя.`
    : 'Статистика по 85 регионам России: население, зарплаты, ВРП, безработица, инвестиции, цены — 489 показателей Росстата с 1990 года. Графики, рейтинги регионов, сравнение с общероссийским уровнем.';

  useDocumentMeta({
    title: view === 'map' ? mapMetaTitle : 'Регионы России — социально-экономические показатели 85 субъектов РФ',
    description: view === 'map' ? mapMetaDesc : 'Статистика по 85 регионам России: население, зарплаты, ВРП, безработица, инвестиции, цены — 489 показателей Росстата с 1990 года. Графики, рейтинги регионов, сравнение с общероссийским уровнем.',
    path: view === 'map'
      ? buildRegionsMapHref({
        view: 'map',
        indicator: mapIndicatorParam,
        year: activeMapCode && urlYear != null ? urlYear : null,
      })
      : '/regions',
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = normalize(deferredQuery);
    const searching = q.length > 0;
    return data.districts
      .filter((d) => searching || !activeDistrict || d.slug === activeDistrict)
      .map((d) => ({
        ...d,
        regions: searching
          ? d.regions.filter((r) => normalize(r.name).includes(q))
          : d.regions,
      }))
      .filter((d) => d.regions.length > 0);
  }, [data, deferredQuery, activeDistrict]);

  const totalShown = filtered.reduce((n, d) => n + d.regions.length, 0);

  useSearchTracking('regions-list', deferredQuery, totalShown);

  const handlePng = async () => {
    if (exportingMap) return;
    if (!isAuthed) {
      track(events.CHART_IMAGE_BLOCKED, { indicator: `regions-map:${activeMapCode || 'overview'}` });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    setExportingMap(true);
    const ok = await exportNodeToPng(mapCardRef.current, {
      filename: `regions-map_${activeMapCode || 'overview'}.png`,
      watermark: false,
    }).catch(() => false);
    setExportingMap(false);
    if (ok) track(events.CHART_IMAGE_DOWNLOAD, { indicator: `regions-map:${activeMapCode || 'overview'}` });
  };

  const handleGif = async () => {
    if (exportingGif) return;
    if (!isAuthed) {
      track(events.REGIONS_MAP_GIF_BLOCKED, { indicator: activeMapCode || 'overview' });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    if (!series.data || !seriesYears || seriesYears.length < 2) return;
    setExportingGif(true);
    try {
      const blob = await buildRegionsMapGif(series.data);
      downloadBlob(blob, `regions-map_${activeMapCode}.gif`);
      track(events.REGIONS_MAP_GIF_DOWNLOAD, {
        indicator: activeMapCode,
        years: seriesYears.length,
      });
    } catch {
      /* генерация сорвалась — молча, без файла */
    }
    setExportingGif(false);
  };

  const gifAvailable = !!(activeMapCode && seriesYears && seriesYears.length > 1 && series.data);

  return (
    <div className="mx-auto w-full max-w-7xl overflow-x-hidden px-4 pb-24 pt-24 sm:px-6">
      <div className="mb-8">
        <div className="flex items-center gap-2 text-champagne text-xs font-mono uppercase tracking-widest mb-3">
          <MapPin size={14} />
          Региональная статистика
        </div>
        <h1 className="font-display text-[1.75rem] font-bold leading-tight text-text-primary sm:text-4xl">
          Регионы России
        </h1>
        <p className="mt-3 max-w-2xl text-[14px] leading-relaxed text-text-secondary sm:text-[15px]">
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
          {contrastVisible.some((m) => m.heat.data) && (
            <div data-block="contrasts" className="mb-4 bg-surface border border-border-subtle rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono uppercase tracking-widest text-champagne">Контрасты России</span>
                <button
                  type="button"
                  onClick={() => {
                    const next = (contrastPage + 1) % CONTRAST_PAGES;
                    setContrastPage(next);
                    track(events.REGIONS_CONTRASTS_SHUFFLE, { page: next });
                  }}
                  title="Показать другую пару показателей"
                  aria-label="Другая пара показателей"
                  className="p-2 -m-1 text-text-tertiary transition-colors hover:text-champagne"
                >
                  <RefreshCw size={13} />
                </button>
              </div>
              {contrastVisible.map((m) => (
                <ContrastRow key={m.code} heat={m.heat} metricLabel={m.label} betterIsLow={m.betterIsLow} />
              ))}
            </div>
          )}

          <div className="relative mb-6">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-tertiary" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Найти регион: Севастополь, Татарстан, Приморский…"
              className="w-full rounded-xl border border-border-subtle bg-surface py-3 pl-10 pr-4 text-sm text-text-primary shadow-sm placeholder:text-text-tertiary focus:border-border-champagne focus:outline-none"
              aria-label="Поиск региона"
            />
          </div>

          {isError && <ApiRetryBanner onRetry={refetch} retrying={isFetching} />}

          {isLoading && (
            <div className="grid gap-2 sm:grid-cols-2">
              {Array.from({ length: 10 }).map((_, i) => <SkeletonBox key={i} className="h-16 rounded-xl" />)}
            </div>
          )}

          {!isLoading && (() => {
            const searching = normalize(deferredQuery).length > 0;
            const districtNav = data?.districts || [];
            const resolvedDistrict = activeDistrict
              && districtNav.some((d) => d.slug === activeDistrict)
              ? activeDistrict
              : null;
            const totalRegions = districtNav.reduce((n, d) => n + d.regions.length, 0);

            return (
              <>
                {!searching && (
                  <MobileNavSelect
                    label="Округа"
                    value={resolvedDistrict || ''}
                    onChange={(v) => setActiveDistrict(v || null)}
                    options={[
                      { value: '', label: 'Все округа', count: totalRegions },
                      ...districtNav.map((d) => ({
                        value: d.slug,
                        label: DISTRICT_SHORT[d.slug] || d.name,
                        count: d.regions.length,
                      })),
                    ]}
                  />
                )}

                <div className={searching
                  ? 'min-w-0 space-y-8'
                  : 'grid min-w-0 gap-6 lg:grid-cols-[250px_minmax(0,1fr)]'}
                >
                  {!searching && (
                    <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block lg:self-start" aria-label="Федеральные округа">
                      <div className="mb-2 px-2 text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
                        Округа
                      </div>
                      <div className="flex flex-col gap-2">
                        <button
                          type="button"
                          onClick={() => setActiveDistrict(null)}
                          className={[
                            'flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                            !resolvedDistrict
                              ? 'bg-champagne/12 font-medium text-champagne'
                              : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                          ].join(' ')}
                        >
                          <span>Все округа</span>
                          <span className="font-mono text-[10px] opacity-60">{totalRegions}</span>
                        </button>
                        {districtNav.map((d) => (
                          <button
                            key={d.slug}
                            type="button"
                            onClick={() => setActiveDistrict(d.slug)}
                            className={[
                              'flex items-center justify-between gap-4 rounded-xl px-3.5 py-2.5 text-left text-sm transition-colors',
                              resolvedDistrict === d.slug
                                ? 'bg-champagne/12 font-medium text-champagne'
                                : 'bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary',
                            ].join(' ')}
                          >
                            <span className="min-w-0 truncate">{DISTRICT_SHORT[d.slug] || d.name}</span>
                            <span className="shrink-0 font-mono text-[10px] opacity-60">{d.regions.length}</span>
                          </button>
                        ))}
                      </div>
                    </aside>
                  )}

                  <div className="min-w-0 space-y-8">
                    {filtered.map((d) => (
                      <section key={d.slug} aria-labelledby={`district-${d.slug}`}>
                        <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4">
                          <div className="min-w-0">
                            <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
                              {searching ? 'Результаты поиска' : 'Регионы'}
                            </div>
                            <h2 id={`district-${d.slug}`} className="mt-1 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">
                              {d.name}
                            </h2>
                          </div>
                          <span className="shrink-0 font-mono text-xs text-text-tertiary">{d.regions.length}</span>
                        </div>
                        <div className="grid gap-2 sm:grid-cols-2 sm:gap-2.5">
                          {d.regions.map((r) => <RegionCard key={r.slug} region={r} />)}
                        </div>
                      </section>
                    ))}
                    {totalShown === 0 && searching && (
                      <div className="rounded-2xl border border-border-subtle bg-surface p-5 text-center text-sm text-text-secondary sm:p-6">
                        По запросу «{query}» регионов не найдено
                      </div>
                    )}
                  </div>
                </div>
              </>
            );
          })()}
        </>
      )}

      {view === 'map' && (
        <div className="mt-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center mb-3">
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-hide min-w-0" role="tablist" aria-label="Показатель карты">
              <button
                role="tab"
                aria-selected={isOverview}
                onClick={selectOverview}
                title="Клик по региону открывает его карточку со всеми показателями"
                className={`min-h-9 shrink-0 rounded-full px-3.5 py-2 text-xs font-medium transition-colors ${
                  isOverview
                    ? 'bg-champagne/15 text-champagne'
                    : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
                }`}
              >
                Обзор
              </button>
              {MAP_METRICS.map((m) => {
                const selected = !isOverview && !isCustomMetric && activeMapCode === m.code;
                return (
                  <button
                    key={m.code}
                    role="tab"
                    aria-selected={selected}
                    onClick={() => selectPreset(m)}
                    className={`min-h-9 shrink-0 rounded-full px-3.5 py-2 text-xs font-medium transition-colors ${
                      selected
                        ? 'bg-champagne/15 text-champagne'
                        : 'bg-surface border border-border-subtle text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    {m.label}
                  </button>
                );
              })}
            </div>
            <MapMetricSearch
              activeCode={isCustomMetric ? activeMapCode : null}
              activeName={customName}
              onPick={selectCustom}
              onClear={clearCustom}
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
              <div className="shrink-0 flex items-center gap-1.5" data-no-export="true">
                <button
                  type="button"
                  disabled={exportingMap}
                  onClick={handlePng}
                  title={isAuthed ? 'Скачать карту картинкой' : 'Скачивание доступно после регистрации'}
                  aria-label="Скачать карту картинкой"
                  className="inline-flex min-h-9 items-center gap-1 rounded-full border border-border-subtle px-3 py-2 text-xs text-text-tertiary transition-colors hover:border-border-champagne hover:text-champagne disabled:opacity-50"
                >
                  <ImageIcon size={12} /> PNG
                </button>
                <button
                  type="button"
                  disabled={exportingGif || !gifAvailable}
                  onClick={handleGif}
                  title={
                    !gifAvailable
                      ? 'GIF доступен, когда выбран показатель с историей по годам'
                      : (isAuthed ? 'Скачать GIF по годам' : 'Скачивание доступно после регистрации')
                  }
                  aria-label="Скачать GIF по годам"
                  className="inline-flex min-h-9 items-center gap-1 rounded-full border border-border-subtle px-3 py-2 text-xs text-text-tertiary transition-colors hover:border-border-champagne hover:text-champagne disabled:opacity-50"
                >
                  <Film size={12} /> {exportingGif ? 'GIF…' : 'GIF'}
                </button>
              </div>
            </div>
            <Suspense fallback={<SkeletonBox className="h-80 rounded-xl" />}>
              <RegionsMap
                valuesBySlug={activeMapCode ? heatmapValues : null}
                transitionMs={activeMapCode ? 650 : 150}
                unit={series.data?.indicator?.unit || ''}
                nameBySlug={namesBySlug}
                brandMark
                onSelect={(slug) => {
                  track(events.REGIONS_MAP_SELECT, { region: slug, metric: activeMapCode || 'overview' });
                  navigate(activeMapCode ? `/region/${slug}/${activeMapCode}` : `/region/${slug}`);
                }}
              />
            </Suspense>

            {activeMapCode && seriesYears && seriesYears.length > 1 && mapYear != null && (
              <Suspense fallback={null}>
                <MapTimeline
                  key={activeMapCode}
                  years={seriesYears}
                  year={mapYear}
                  onYearChange={setMapYear}
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
