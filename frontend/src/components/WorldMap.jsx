import {
  createElement, startTransition, useCallback, useEffect, useId, useMemo, useRef, useState,
} from 'react';
import {
  geoGraticule10, geoMercator, geoNaturalEarth1, geoPath,
} from 'd3-geo';
import {
  Globe2, Map as MapIcon, Maximize2, Minus, Plus,
} from 'lucide-react';
import { valueExtent } from '../lib/regionsMapColors';
import { formatValue } from '../lib/format';
import { formatWorldValue } from '../lib/worldApi';
import {
  displayWorldGeometry, mainlandWorldGeometry, outlinePointCount,
} from '../lib/worldMapGeometry';
import {
  formatWorldPeriod, resolveWorldPeriodFormat, worldPeriodDates,
} from '../lib/worldMapPeriod';
import {
  loadWorldFeatures, numericId, WORLD_FEATURE_BY_ID, WORLD_FEATURES,
} from '../lib/worldTopology';
import {
  buildWorldColorModel, WORLD_NO_DATA, WORLD_OCEAN_COLOR,
} from '../lib/worldMapColors';
import { useLocale, useT } from '../i18n';
import { t as translateStandalone } from '../i18n/messages';
import { resolveBrowserLocale } from '../i18n/locale';
import { localizeSource } from '../i18n/viewModeLabels';
import { countryReference } from '../lib/countryReference';
import '../styles/world.css';
import SourceLink from './SourceLink';
import Chip from './Chip';
import '../styles/platform-pages.css';
import '../styles/k4-charts.css';

const WIDTH = 960;
const HEIGHT = 480;
const ZOOM_MAX = 7;
const ZOOM_STEP = 1.55;
const WORLD_OCEAN = WORLD_OCEAN_COLOR;
const WORLD_OUTSIDE = '#F4F5F2';
const WORLD_GRATICULE = geoGraticule10();

const ISO_NUMERIC_TO_ALPHA2 = {
  '008': 'AL', '031': 'AZ', '036': 'AU', '040': 'AT', '051': 'AM',
  '056': 'BE', '070': 'BA', '076': 'BR', '100': 'BG', '124': 'CA',
  '152': 'CL', '156': 'CN', '170': 'CO', '191': 'HR', '196': 'CY',
  '203': 'CZ', '208': 'DK', '233': 'EE', '246': 'FI', '250': 'FR',
  '268': 'GE', '276': 'DE', '300': 'EL', '348': 'HU', '352': 'IS',
  '356': 'IN', '360': 'ID', '372': 'IE', '376': 'IL', '380': 'IT',
  '383': 'XK', '392': 'JP', '410': 'KR', '428': 'LV', '440': 'LT',
  '442': 'LU', '458': 'MY', '470': 'MT', '484': 'MX', '498': 'MD',
  '499': 'ME', '528': 'NL', '554': 'NZ', '578': 'NO', '586': 'PK',
  '604': 'PE', '608': 'PH', '616': 'PL', '620': 'PT', '642': 'RO',
  '643': 'RU', '682': 'SA', '688': 'RS', '702': 'SG', '703': 'SK',
  '704': 'VN', '705': 'SI', '710': 'ZA', '724': 'ES', '752': 'SE',
  '756': 'CH', '764': 'TH', '792': 'TR', '804': 'UA', '807': 'MK',
  // world-atlas / ISO uses GB; наша БД и API — UK (как Eurostat GEO).
  '826': 'UK', '840': 'US',
};

/** Resolve API/DB country code from a map feature code (GB↔UK). */
function resolveCountry(countryByCode, code) {
  if (!code) return null;
  return countryByCode.get(code)
    || (code === 'GB' ? countryByCode.get('UK') : null)
    || (code === 'UK' ? countryByCode.get('GB') : null)
    || null;
}

const NUMERIC_ID_BY_ALPHA2 = (() => {
  const byCode = new Map();
  for (const [id, alpha2] of Object.entries(ISO_NUMERIC_TO_ALPHA2)) byCode.set(alpha2, id);
  byCode.set('GB', byCode.get('UK'));
  byCode.set('GR', byCode.get('EL'));
  return byCode;
})();

function displayFeatureFor(geometry) {
  return displayWorldGeometry(geometry, ISO_NUMERIC_TO_ALPHA2[numericId(geometry.id)]);
}

function shapeFor(geometry, index, path) {
  return {
    key: `${geometry.id ?? 'x'}-${index}`,
    code: ISO_NUMERIC_TO_ALPHA2[numericId(geometry.id)],
    d: path(geometry) || '',
  };
}

// 110m-контуры для первого кадра: считаются один раз на модуль.
let baseDisplayFeatures = null;
function getBaseDisplayFeatures() {
  if (!baseDisplayFeatures) baseDisplayFeatures = WORLD_FEATURES.map(displayFeatureFor);
  return baseDisplayFeatures;
}

/**
 * Колбэк после события load и простоя главного потока: 50m-атлас (~240 КБ
 * gzip и ~150 мс геометрии на телефоне) не должен конкурировать с первым
 * экраном. Возвращает функцию отмены.
 */
function whenIdleAfterLoad(callback) {
  if (typeof window === 'undefined') return () => {};
  let cancelled = false;
  let idleHandle = null;
  let timer = null;
  const run = () => {
    if (cancelled) return;
    if (typeof window.requestIdleCallback === 'function') {
      idleHandle = window.requestIdleCallback(() => { if (!cancelled) callback(); }, { timeout: 3000 });
    } else {
      timer = window.setTimeout(() => { if (!cancelled) callback(); }, 300);
    }
  };
  if (document.readyState === 'complete') run();
  else window.addEventListener('load', run, { once: true });
  return () => {
    cancelled = true;
    window.removeEventListener('load', run);
    if (idleHandle != null && typeof window.cancelIdleCallback === 'function') {
      window.cancelIdleCallback(idleHandle);
    }
    if (timer != null) window.clearTimeout(timer);
  };
}

const SLICE_BUDGET_MS = 8;
const yieldToMain = () => new Promise((resolve) => { setTimeout(resolve, 0); });
const nowMs = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

/**
 * map() порциями по ~8 мс с уступкой главному потоку между порциями, чтобы
 * пересчёт 50m-геометрии не давал длинных задач (TBT/INP). null — отменено.
 */
async function mapInSlices(items, fn, isActive) {
  const out = new Array(items.length);
  let sliceStart = nowMs();
  for (let index = 0; index < items.length; index += 1) {
    out[index] = fn(items[index], index);
    if (nowMs() - sliceStart > SLICE_BUDGET_MS) {
      await yieldToMain();
      if (!isActive()) return null;
      sliceStart = nowMs();
    }
  }
  return isActive() ? out : null;
}

function collectionValue(values, key) {
  if (!values) return null;
  return values instanceof Map ? values.get(key) : values[key];
}

function formatLegendValue(value) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  const locale = resolveBrowserLocale();
  const numeric = Number(value);
  const abs = Math.abs(numeric);
  const numberLocale = locale === 'en' ? 'en-US' : 'ru-RU';
  const compact = (divisor, suffix) => `${(numeric / divisor).toLocaleString(numberLocale, {
    maximumFractionDigits: 1,
  })}\u00A0${suffix}`;
  if (abs >= 1e9) return compact(1e9, translateStandalone('map.compact.billion'));
  if (abs >= 1e6) return compact(1e6, translateStandalone('map.compact.million'));
  if (abs >= 1e4) return compact(1e3, translateStandalone('map.compact.thousand'));
  return numeric.toLocaleString(numberLocale, { maximumFractionDigits: abs < 10 ? 1 : 0 });
}

/** Подпись полосы шкалы: ключ словаря плюс процентиль, если он посчитан. */
function bandText(band, t) {
  if (!band?.key) return '';
  const label = t(band.key);
  return band.rank == null
    ? label
    : t('world.map.bandRank', { band: label, rank: band.rank });
}

/** Плавный градиент трубки: цвет каждой полосы стоит в её центре, края продолжают крайние цвета. */
function tubeGradient(bins) {
  if (!bins.length) return 'none';
  const n = bins.length;
  const stops = bins.map((bin, index) => `${bin.color} ${(((index + 0.5) / n) * 100).toFixed(2)}%`);
  return `linear-gradient(90deg, ${bins[0].color} 0%, ${stops.join(', ')}, ${bins[n - 1].color} 100%)`;
}

function legendBinLabel(bin) {
  if (bin.zero) return '0';
  if (bin.min == null) return `≤ ${formatLegendValue(bin.max)}`;
  if (bin.max == null) return `≥ ${formatLegendValue(bin.min)}`;
  return `${formatLegendValue(bin.min)}–${formatLegendValue(bin.max)}`;
}

export default function WorldMap({
  countries = [],
  valuesByCode = null,
  detailsByCode = null,
  unit = '',
  metricName = '',
  periodLabel = '',
  colorMode = 'relative',
  colorDirection = null,
  defaultScope = 'world',
  onSelect,
}) {
  const t = useT();
  const [scope, setScope] = useState(defaultScope === 'europe' ? 'europe' : 'world');
  const [hover, setHover] = useState(null);
  const [view, setView] = useState({ k: 1, tx: 0, ty: 0 });
  const [detailFeatures, setDetailFeatures] = useState(null);
  const [detailShapes, setDetailShapes] = useState(null);
  const panRef = useRef(null);
  const svgRef = useRef(null);
  const noDataPatternId = `world-no-data-${useId().replaceAll(':', '')}`;
  const countryByCode = useMemo(
    () => new Map(countries.map((country) => [country.code, country])),
    [countries],
  );

  // Сразу 110m (лёгкий), затем 50m лениво — береговая линия читается достойно,
  // без утяжеления первого бандла на 740 КБ. Детальный атлас грузится только
  // после load + простоя, а его геометрия считается порциями (без длинных задач).
  useEffect(() => {
    let active = true;
    const isActive = () => active;
    const cancel = whenIdleAfterLoad(() => {
      loadWorldFeatures('detailed').then(async (byId) => {
        if (!active || !byId) return;
        const next = await mapInSlices([...byId.values()], displayFeatureFor, isActive);
        if (next) startTransition(() => setDetailFeatures(next));
      });
    });
    return () => { active = false; cancel(); };
  }, []);

  const baseFeatures = getBaseDisplayFeatures();
  const projection = useMemo(() => {
    if (scope === 'europe') {
      return geoMercator()
        .center([18, 52])
        .scale(340)
        .translate([WIDTH / 2, HEIGHT / 2]);
    }
    // Вписываем по 110m: рамка совпадает с 50m (разница масштаба ~0.02%),
    // зато проекция не пересчитывается и карта не «дёргается» при апгрейде.
    return geoNaturalEarth1().fitExtent(
      [[24, 24], [WIDTH - 24, HEIGHT - 24]],
      {
        type: 'FeatureCollection',
        features: baseFeatures,
      },
    );
  }, [baseFeatures, scope]);
  // digits(2): короче строки d (меньше DOM/парсинга), визуально без разницы
  // даже при зуме ×7.
  const path = useMemo(() => geoPath(projection).digits(2), [projection]);

  // Контуры 50m для текущей проекции — порциями, затем подмена в transition.
  useEffect(() => {
    if (!detailFeatures) return undefined;
    let active = true;
    mapInSlices(detailFeatures, (geometry, index) => shapeFor(geometry, index, path), () => active)
      .then((next) => {
        if (next) startTransition(() => setDetailShapes({ path, features: detailFeatures, shapes: next }));
      });
    return () => { active = false; };
  }, [detailFeatures, path]);

  const detailReady = Boolean(detailShapes && detailShapes.path === path);
  const features = detailReady ? detailShapes.features : baseFeatures;
  // Строки контуров не зависят от данных и ховера: без этого каждый ховер
  // пересчитывал бы path для всех стран сразу.
  const baseShapes = useMemo(
    () => (detailReady ? null : baseFeatures.map((geometry, index) => shapeFor(geometry, index, path))),
    [baseFeatures, detailReady, path],
  );
  const shapes = detailReady ? detailShapes.shapes : baseShapes;
  const colorModel = useMemo(
    () => buildWorldColorModel(valuesByCode, { mode: colorMode, direction: colorDirection }),
    [valuesByCode, colorMode, colorDirection],
  );
  const extent = useMemo(() => valueExtent(valuesByCode), [valuesByCode]);
  const periodFormat = useMemo(
    () => resolveWorldPeriodFormat(worldPeriodDates(detailsByCode)),
    [detailsByCode],
  );
  const hoverGeometry = useMemo(
    () => (hover ? features.find((geometry) => {
      const code = ISO_NUMERIC_TO_ALPHA2[numericId(geometry.id)];
      const country = resolveCountry(countryByCode, code);
      if (country?.code === hover.country.code) return true;
      if (code === hover.country.code) return true;
      if (code === 'GB' && hover.country.code === 'UK') return true;
      if (code === 'UK' && hover.country.code === 'GB') return true;
      return false;
    }) : null),
    [countryByCode, features, hover],
  );

  const clampView = useCallback((next) => {
    const k = Math.max(1, Math.min(ZOOM_MAX, next.k));
    if (k === 1) return { k: 1, tx: 0, ty: 0 };
    return {
      k,
      tx: Math.max(WIDTH * (1 - k), Math.min(0, next.tx)),
      ty: Math.max(HEIGHT * (1 - k), Math.min(0, next.ty)),
    };
  }, []);

  const zoomBy = useCallback((factor) => {
    setView((previous) => {
      const k = Math.max(1, Math.min(ZOOM_MAX, previous.k * factor));
      return clampView({
        k,
        tx: WIDTH / 2 - (k / previous.k) * (WIDTH / 2 - previous.tx),
        ty: HEIGHT / 2 - (k / previous.k) * (HEIGHT / 2 - previous.ty),
      });
    });
  }, [clampView]);

  const handlePointerDown = useCallback((event) => {
    if (view.k === 1) return;
    panRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      tx: view.tx,
      ty: view.ty,
      moved: false,
    };
  }, [view]);

  const handlePointerMove = useCallback((event) => {
    const pan = panRef.current;
    if (!pan) return;
    const dx = event.clientX - pan.startX;
    const dy = event.clientY - pan.startY;
    if (!pan.moved && Math.hypot(dx, dy) < 6) return;
    if (!pan.moved) {
      pan.moved = true;
      try { svgRef.current?.setPointerCapture(event.pointerId); } catch { /* ok */ }
    }
    const box = svgRef.current?.getBoundingClientRect();
    if (!box) return;
    setView((previous) => clampView({
      k: previous.k,
      tx: pan.tx + dx * (WIDTH / box.width),
      ty: pan.ty + dy * (HEIGHT / box.height),
    }));
  }, [clampView]);

  const handlePointerUp = useCallback(() => {
    setTimeout(() => { panRef.current = null; }, 0);
  }, []);

  const selectCountry = useCallback((country) => {
    if (panRef.current?.moved) return;
    onSelect?.(country, detailsByCode?.get(country.code) || null);
  }, [detailsByCode, onSelect]);

  const { k, tx, ty } = view;
  const hoverPeriod = formatWorldPeriod(hover?.detail?.date, periodFormat) || periodLabel;

  return (
    <div className="select-none">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-text-secondary">
          {t('world.map.pickCountry')}
        </div>
        <div className="inline-flex gap-1.5">
          {[
            ['europe', MapIcon, t('home.map.scopeEurope')],
            ['world', Globe2, t('home.map.scopeWorld')],
          ].map(([id, Icon, label]) => (
            <Chip
              key={id}
              active={scope === id}
              onClick={() => {
                setScope(id);
                setView({ k: 1, tx: 0, ty: 0 });
                setHover(null);
              }}
              className="gap-1.5"
            >
              {createElement(Icon, { size: 12 })}
              {label}
            </Chip>
          ))}
        </div>
      </div>

      <div className="k4-map-plate relative overflow-hidden rounded-2xl">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className={`block h-auto w-full ${k > 1 ? 'cursor-grab active:cursor-grabbing' : ''}`}
          role="group"
          aria-label={t('world.map.aria')}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onDoubleClick={() => zoomBy(ZOOM_STEP)}
          style={{ touchAction: k > 1 ? 'none' : 'pan-y' }}
        >
          <defs>
            {/* Страны без данных: матовое стекло (иней), а не штриховка. */}
            <linearGradient id={noDataPatternId} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#FFFFFF" stopOpacity={0.92} />
              <stop offset="100%" stopColor={WORLD_NO_DATA} stopOpacity={1} />
            </linearGradient>
          </defs>
          <rect width={WIDTH} height={HEIGHT} fill={WORLD_OCEAN} />
          <g transform={`translate(${tx} ${ty}) scale(${k})`}>
            <path
              d={path(WORLD_GRATICULE) || ''}
              fill="none"
              stroke="rgba(94,116,132,0.15)"
              strokeWidth={0.55}
              vectorEffect="non-scaling-stroke"
              pointerEvents="none"
              aria-hidden="true"
            />
            {shapes.map(({ key, code, d }) => {
              const catalogCountry = resolveCountry(countryByCode, code);
              const valueKey = catalogCountry?.code || code;
              const detail = (valueKey && detailsByCode?.get(valueKey))
                || (code && detailsByCode?.get(code))
                || null;
              const country = catalogCountry || (detail?.country_slug ? {
                code: detail.country_code || code,
                slug: detail.country_slug,
                name: detail.country_name || code,
              } : null);
              const value = valueKey ? collectionValue(valuesByCode, valueKey)
                : (code ? collectionValue(valuesByCode, code) : null);
              const active = Boolean(country);
              const hasValue = value != null && Number.isFinite(Number(value));
              const isHover = Boolean(hover && country && hover.country.code === country.code);
              return (
                <path
                  key={key}
                  d={d}
                  fill={hasValue
                    ? colorModel.colorFor(value)
                    : active ? `url(#${noDataPatternId})` : WORLD_OUTSIDE}
                  stroke={active ? 'rgba(88,74,46,0.42)' : 'rgba(88,74,46,0.14)'}
                  strokeWidth={active ? 0.9 : 0.45}
                  vectorEffect="non-scaling-stroke"
                  className={active
                    ? 'cursor-pointer outline-none focus-visible:outline-none'
                    : 'outline-none'}
                  style={isHover ? {
                    filter: 'brightness(0.92) drop-shadow(0 0 1.2px rgba(181,141,39,0.85))',
                  } : undefined}
                  onClick={() => active && selectCountry(country)}
                  onMouseEnter={() => active && setHover({
                    country,
                    value,
                    detail: detailsByCode?.get(valueKey) || detailsByCode?.get(code) || null,
                  })}
                  onMouseLeave={() => setHover(null)}
                  onFocus={() => active && setHover({
                    country,
                    value,
                    detail: detailsByCode?.get(valueKey) || detailsByCode?.get(code) || null,
                  })}
                  onBlur={() => setHover(null)}
                  role={active ? 'button' : undefined}
                  aria-label={active
                    ? (hasValue
                      ? t('world.map.countryValue', { name: country.name, value: formatWorldValue(value), unit: unit || '' })
                      : t('world.map.countryNoData', { name: country.name }))
                    : undefined}
                  tabIndex={active ? 0 : undefined}
                  onKeyDown={(event) => {
                    if (active && (event.key === 'Enter' || event.key === ' ')) {
                      event.preventDefault();
                      selectCountry(country);
                    }
                  }}
                />
              );
            })}
            {hoverGeometry && (
              <path
                d={path(hoverGeometry) || ''}
                fill="rgba(181,141,39,0.22)"
                stroke="#B58D27"
                strokeWidth={1.35}
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
                aria-hidden="true"
                style={{ filter: 'drop-shadow(0 0 2px rgba(181,141,39,0.55))' }}
              />
            )}
          </g>
        </svg>

        <div className="absolute right-3 top-3 flex flex-col gap-2" data-no-export="true">
          <button type="button" onClick={() => zoomBy(ZOOM_STEP)} disabled={k >= ZOOM_MAX} aria-label={t('map.zoomIn')} className="fe-map-btn fe-press h-11 w-11 rounded-full text-text-secondary transition-colors hover:text-champagne-ink disabled:opacity-35 fe-glass-2">
            <Plus size={16} />
          </button>
          <button type="button" onClick={() => zoomBy(1 / ZOOM_STEP)} disabled={k <= 1} aria-label={t('map.zoomOut')} className="fe-map-btn fe-press h-11 w-11 rounded-full text-text-secondary transition-colors hover:text-champagne-ink disabled:opacity-35 fe-glass-2">
            <Minus size={16} />
          </button>
          {k > 1 && (
            <button type="button" onClick={() => setView({ k: 1, tx: 0, ty: 0 })} aria-label={t('map.zoomReset')} className="fe-map-btn fe-press h-11 w-11 rounded-full text-text-secondary transition-colors hover:text-champagne-ink fe-glass-2">
              <Maximize2 size={15} />
            </button>
          )}
        </div>

        {hover && (
          <div className="pointer-events-none absolute bottom-3 left-3 z-10 max-w-[calc(100%-5rem)] rounded-xl px-3.5 py-3 text-xs fe-glass-pop">
            <div className="font-semibold text-text-primary">{hover.country.name}</div>
            <div className="mt-1 font-mono text-base font-semibold text-champagne">
              {hover.value != null ? formatWorldValue(hover.value) : t('common.noData')}
            </div>
            {hover.value != null && unit && <div className="mt-0.5 text-xs text-text-secondary">{unit}</div>}
            {hover.value != null && bandText(colorModel.describe(hover.value), t) && (
              <div
                className="mt-1 text-xs font-medium"
                style={{ color: colorModel.labelColorFor(hover.value) }}
              >
                {bandText(colorModel.describe(hover.value), t)}
              </div>
            )}
            {hoverPeriod && (
              <div className="mt-1.5 pt-1.5 font-mono text-xs text-text-secondary fe-divider">
                {hoverPeriod}
              </div>
            )}
          </div>
        )}
      </div>

      {valuesByCode && (
        <div className="mt-4 rounded-xl px-3 py-3 fe-glass-2">
          <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <div className="text-xs font-medium text-text-secondary">
              {metricName || t('world.map.distribution')}
              {periodLabel ? (
                <span className="font-mono text-text-secondary"> — {periodLabel}</span>
              ) : null}
            </div>
            <div className="text-[11px] uppercase tracking-[0.13em] text-text-secondary">
              {colorModel.kind === 'diverging' ? t('world.map.scaleZero') : t('world.map.scaleMedian')}
            </div>
          </div>
          {/* Шкала — стеклянная трубка: плавный градиент полос, блик сверху и бусины на границах; подписи полос под ней. */}
          <div className="mx-auto max-w-[46rem]">
            <div
              className="k4-tube"
              style={{ backgroundImage: tubeGradient(colorModel.bins) }}
              aria-hidden="true"
            >
              <div className="k4-tube__beads">
                {colorModel.bins.slice(1).map((bin, index) => <i key={`${bin.color}-${index}`} />)}
              </div>
            </div>
            <div className="mt-1.5 grid grid-cols-4 gap-1.5 sm:grid-cols-7">
              {colorModel.bins.map((bin, index) => (
                <div
                  key={`${bin.color}-${index}`}
                  className="min-w-0 text-center"
                  title={t(bin.labelKey)}
                >
                  <div className="k4-bin" style={{ backgroundColor: bin.color }} aria-hidden="true" />
                  <div className="mt-1 break-words font-mono text-xs leading-tight tabular-nums text-text-secondary">
                    {legendBinLabel(bin)}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-2.5 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-xs text-text-secondary">
            <span className="font-medium text-text-primary">
              {colorModel.kind === 'diverging'
                ? t('world.map.legendZero')
                : t('world.map.legendMedian')}
            </span>
            {colorModel.median != null && (
              <span>
                {t('world.map.median', { value: formatWorldValue(colorModel.median) })}
                {unit ? ` ${unit}` : ''}
              </span>
            )}
            {colorModel.sampleSize > 0 && <span>{t('world.map.withData', { n: colorModel.sampleSize })}</span>}
            {extent && (
              <span>
                {t('world.map.range', {
                  min: formatWorldValue(extent.min),
                  max: formatWorldValue(extent.max),
                })}
                {unit ? ` ${unit}` : ''}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-4 rounded-[4px] k4-nodata" aria-hidden="true" />
              {t('world.map.noDataSwatch')}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// Ниже этого числа вершин контур в кадре карточки читается как многоугольник:
// столько остаётся у Мальты, Кипра, Люксембурга и подобных. Только им догружаем
// самый тяжёлый уровень.
const FINE_OUTLINE_MIN_POINTS = 100;

/**
 * Контур страны: сразу грубый из основного бандла, затем подробный, когда
 * догрузится его чанк, и только государствам-крохам — самый подробный. Если
 * чанк не приехал или страны в нём нет, остаёмся на том, что уже есть:
 * карточка не пустеет и не прыгает.
 */
function useCountryOutline(code) {
  const [atlases, setAtlases] = useState({});
  const id = NUMERIC_ID_BY_ALPHA2.get(code) || null;

  useEffect(() => {
    let active = true;
    loadWorldFeatures('detailed').then((byId) => {
      if (active && byId) setAtlases((previous) => ({ ...previous, detailed: byId }));
    });
    return () => { active = false; };
  }, []);

  const detailed = (id && atlases.detailed?.get(id)) || null;
  const needsFine = useMemo(
    () => Boolean(detailed) && outlinePointCount(detailed) < FINE_OUTLINE_MIN_POINTS,
    [detailed],
  );

  useEffect(() => {
    if (!needsFine) return undefined;
    let active = true;
    loadWorldFeatures('fine').then((byId) => {
      if (active && byId) setAtlases((previous) => ({ ...previous, fine: byId }));
    });
    return () => { active = false; };
  }, [needsFine]);

  return useMemo(() => {
    if (!id) return null;
    const item = (needsFine ? atlases.fine?.get(id) : null)
      || detailed
      || WORLD_FEATURE_BY_ID.get(id);
    return item ? mainlandWorldGeometry(item) : null;
  }, [atlases.fine, detailed, id, needsFine]);
}

/**
 * Карточка территории на странице страны: светлая, в общем стиле сайта. Контур, площадь и население;
 * ни кодов страны, ни диапазонов лет, ни частот: это справка для эксперта, а не для человека, пришедшего за фактом.
 * `historyStart`, `historyEnd` и `frequencies` принимаются ради совместимости и не показываются.
 */
export function CountrySilhouette({
  code,
  name,
  region = '',
  area = null,
  population = null,
  slug = '',
  className = '',
  badge = null,
}) {
  const t = useT();
  const { locale } = useLocale();
  const geometry = useCountryOutline(code);
  const reference = countryReference(code, locale);
  const countryPath = useMemo(() => {
    if (!geometry) return null;
    const projection = geoMercator().fitExtent([[20, 16], [340, 184]], geometry);
    return geoPath(projection)(geometry);
  }, [geometry]);
  if (!countryPath) return null;
  const areaUnitRaw = (area?.unit || '').trim();
  // Между числом и единицей обычный пробел: длинная строка из числа с неразрывными пробелами и единицы
  // не должна рваться по буквам, перенос идёт по границе слов.
  const areaUnit = (!areaUnitRaw || areaUnitRaw === 'км²' || areaUnitRaw === 'km²' || areaUnitRaw === 'км2')
    ? t('world.unit.km2')
    : areaUnitRaw;
  const areaValue = area?.value != null
    ? `${formatValue(area.value, Number.isInteger(Number(area.value)) ? 0 : 1, locale)} ${areaUnit}`
    : '';
  const popUnitRaw = (population?.unit || '').trim();
  const popUnit = (
    !popUnitRaw
    || popUnitRaw === 'человек'
    || popUnitRaw === 'people'
    || popUnitRaw === 'persons'
  )
    ? t('world.unit.people')
    : popUnitRaw;
  // Девять-десять цифр человеку ничего не говорят: «83,4 млн человек» читается сразу.
  const populationNumber = Number(population?.value);
  const populationValue = population?.value != null
    ? (Number.isFinite(populationNumber) && populationNumber >= 1e6
      ? `${formatValue(populationNumber / 1e6, populationNumber >= 1e7 ? 0 : 1, locale)}\u00a0${t('w2.country.million')} ${popUnit}`
      : `${formatValue(population.value, 0, locale)} ${popUnit}`)
    : '';
  const populationYear = population?.year
    || (population?.date ? String(population.date).slice(0, 4) : '');
  // Реальный source_url ряда (новая вкладка); страница страны — только фолбэк.
  const fallbackHref = slug ? `/${slug}` : '/#countries';
  const sources = [];
  if (area?.source) {
    sources.push({
      label: localizeSource(area.source, locale),
      url: area.source_url || '',
      kind: 'area',
    });
  }
  if (population?.source && population.source !== area?.source) {
    sources.push({
      label: localizeSource(population.source, locale),
      url: population.source_url || '',
      kind: 'population',
    });
  } else if (!area?.source && population?.source) {
    sources.push({
      label: localizeSource(population.source, locale),
      url: population.source_url || '',
      kind: 'population',
    });
  }
  return (
    <section className={`w2-profile${className ? ` ${className}` : ''}`} aria-label={t('world.map.outlineAria', { name })}>
      <div className="w2-profile-head">
        <h2 className="w2-profile-title">{t('w6b.country.profile')}</h2>
        {badge}
        {region && <span className="w2-profile-region">{region}</span>}
      </div>
      <svg viewBox="0 0 360 200" className="w2-profile-map" role="img" aria-label={t('world.map.countryMapAria', { name })}>
        <path
          d={countryPath}
          className="w2-profile-shape"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      {(areaValue || populationValue || reference) && (
        <dl className="w2-profile-facts">
          {areaValue && (
            <div>
              <dt>{t('world.territory.area')}</dt>
              <dd>
                {/* Число с единицей не рвётся на «км» и «2». */}
                <span className="whitespace-nowrap">{areaValue}</span>
              </dd>
            </div>
          )}
          {reference?.capital && (
            <div>
              <dt>{t('w6b.country.capital')}</dt>
              <dd>{reference.capital}</dd>
            </div>
          )}
          {reference?.currency && (
            <div>
              <dt>{t('w6b.country.currency')}</dt>
              <dd>{reference.currency}</dd>
            </div>
          )}
          {populationValue && (
            <div>
              <dt>{t('world.territory.population')}</dt>
              <dd>
                {populationValue}
                {populationYear ? <small>{t('x2.country.asOfYear', { year: populationYear })}</small> : null}
              </dd>
            </div>
          )}
        </dl>
      )}
      {sources.length > 0 && (
        <p className="w2-profile-source">
          {t('common.source')}:{' '}
          {sources.map((item, index) => (
            <span key={`${item.kind}-${item.label}`}>
              {index > 0 ? ', ' : ''}
              <SourceLink href={item.url} fallbackTo={fallbackHref}>
                {item.label}
              </SourceLink>
            </span>
          ))}
        </p>
      )}
    </section>
  );
}
