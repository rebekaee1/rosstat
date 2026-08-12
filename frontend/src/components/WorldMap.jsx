import {
  createElement, useCallback, useId, useMemo, useRef, useState,
} from 'react';
import {
  geoGraticule10, geoMercator, geoNaturalEarth1, geoPath,
} from 'd3-geo';
import { feature } from 'topojson-client';
import worldTopology from 'world-atlas/countries-110m.json';
import {
  Globe2, Map as MapIcon, Maximize2, Minus, Plus,
} from 'lucide-react';
import { valueExtent } from '../lib/regionsMapColors';
import { formatWorldValue } from '../lib/worldApi';
import { displayWorldGeometry } from '../lib/worldMapGeometry';
import {
  buildWorldColorModel, WORLD_NO_DATA,
} from '../lib/worldMapColors';

const WIDTH = 960;
const HEIGHT = 480;
const ZOOM_MAX = 7;
const ZOOM_STEP = 1.55;
const WORLD_OCEAN = '#E8EEF3';
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
const WORLD_FEATURES = feature(worldTopology, worldTopology.objects.countries).features;

function numericId(raw) {
  return String(raw).padStart(3, '0');
}

function collectionValue(values, key) {
  if (!values) return null;
  return values instanceof Map ? values.get(key) : values[key];
}

function formatLegendValue(value) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  const numeric = Number(value);
  const abs = Math.abs(numeric);
  const compact = (divisor, suffix) => `${(numeric / divisor).toLocaleString('ru-RU', {
    maximumFractionDigits: 1,
  })}\u00A0${suffix}`;
  if (abs >= 1e9) return compact(1e9, 'млрд');
  if (abs >= 1e6) return compact(1e6, 'млн');
  if (abs >= 1e4) return compact(1e3, 'тыс');
  return numeric.toLocaleString('ru-RU', { maximumFractionDigits: abs < 10 ? 1 : 0 });
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
  colorMode = 'auto',
  defaultScope = 'world',
  onSelect,
}) {
  const [scope, setScope] = useState(defaultScope === 'europe' ? 'europe' : 'world');
  const [hover, setHover] = useState(null);
  const [view, setView] = useState({ k: 1, tx: 0, ty: 0 });
  const panRef = useRef(null);
  const svgRef = useRef(null);
  const noDataPatternId = `world-no-data-${useId().replaceAll(':', '')}`;
  const countryByCode = useMemo(
    () => new Map(countries.map((country) => [country.code, country])),
    [countries],
  );
  const features = useMemo(
    () => WORLD_FEATURES.map((geometry) => {
      const code = ISO_NUMERIC_TO_ALPHA2[numericId(geometry.id)];
      return displayWorldGeometry(geometry, code);
    }),
    [],
  );
  const projection = useMemo(() => {
    if (scope === 'europe') {
      return geoMercator()
        .center([18, 52])
        .scale(340)
        .translate([WIDTH / 2, HEIGHT / 2]);
    }
    return geoNaturalEarth1().fitExtent(
      [[24, 24], [WIDTH - 24, HEIGHT - 24]],
      {
        type: 'FeatureCollection',
        features,
      },
    );
  }, [features, scope]);
  const path = useMemo(() => geoPath(projection), [projection]);
  const colorModel = useMemo(
    () => buildWorldColorModel(valuesByCode, { mode: colorMode }),
    [valuesByCode, colorMode],
  );
  const extent = useMemo(() => valueExtent(valuesByCode), [valuesByCode]);
  const hoverGeometry = useMemo(
    () => (hover ? features.find((geometry) => {
      const code = ISO_NUMERIC_TO_ALPHA2[numericId(geometry.id)];
      const country = resolveCountry(countryByCode, code);
      return country?.code === hover.country.code;
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

  return (
    <div className="select-none">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-tertiary">
          Выберите страну на карте
        </div>
        <div className="inline-flex rounded-lg bg-obsidian-light p-0.5">
          {[
            ['europe', MapIcon, 'Европа'],
            ['world', Globe2, 'Мир'],
          ].map(([id, Icon, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                setScope(id);
                setView({ k: 1, tx: 0, ty: 0 });
                setHover(null);
              }}
              className={[
                'inline-flex min-h-9 items-center gap-1 rounded-md px-3 py-2 text-[11px] transition-colors',
                scope === id ? 'bg-white text-text-primary shadow-sm' : 'text-text-tertiary hover:text-text-primary',
              ].join(' ')}
            >
              {createElement(Icon, { size: 12 })}
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="relative overflow-hidden rounded-2xl border border-[#d7dfe5] bg-[#E8EEF3] shadow-[inset_0_1px_0_rgba(255,255,255,0.72),0_16px_40px_rgba(38,54,67,0.05)]">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className={`block h-auto w-full ${k > 1 ? 'cursor-grab active:cursor-grabbing' : ''}`}
          role="group"
          aria-label="Интерактивная карта стран"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          onDoubleClick={() => zoomBy(ZOOM_STEP)}
          style={{ touchAction: k > 1 ? 'none' : 'pan-y' }}
        >
          <defs>
            <pattern
              id={noDataPatternId}
              width="8"
              height="8"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(35)"
            >
              <rect width="8" height="8" fill={WORLD_NO_DATA} />
              <rect width="2" height="8" fill="rgba(122,132,130,0.16)" />
            </pattern>
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
            {features.map((geometry) => {
              const code = ISO_NUMERIC_TO_ALPHA2[numericId(geometry.id)];
              const country = resolveCountry(countryByCode, code);
              const valueKey = country?.code || code;
              const value = valueKey ? collectionValue(valuesByCode, valueKey) : null;
              const active = Boolean(country);
              const hasValue = value != null && Number.isFinite(Number(value));
              return (
                <path
                  key={geometry.id}
                  d={path(geometry) || ''}
                  fill={hasValue
                    ? colorModel.colorFor(value)
                    : active ? `url(#${noDataPatternId})` : WORLD_OUTSIDE}
                  stroke={active ? 'rgba(24,70,67,0.52)' : 'rgba(62,74,82,0.16)'}
                  strokeWidth={active ? 0.9 : 0.45}
                  vectorEffect="non-scaling-stroke"
                  className={active ? 'cursor-pointer transition-[filter,opacity] hover:brightness-[0.96]' : ''}
                  onClick={() => active && selectCountry(country)}
                  onMouseEnter={() => active && setHover({
                    country,
                    value,
                    detail: detailsByCode?.get(valueKey) || detailsByCode?.get(code) || null,
                  })}
                  onMouseLeave={() => setHover(null)}
                  role={active ? 'button' : undefined}
                  aria-label={active ? `${country.name}${hasValue ? `: ${formatWorldValue(value)} ${unit}` : ': нет данных'}` : undefined}
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
                fill="none"
                stroke="#B58D27"
                strokeWidth={2.2}
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
                aria-hidden="true"
              />
            )}
          </g>
        </svg>

        <div className="absolute right-3 top-3 flex flex-col gap-1" data-no-export="true">
          <button type="button" onClick={() => zoomBy(ZOOM_STEP)} disabled={k >= ZOOM_MAX} aria-label="Приблизить карту" className="flex h-9 w-9 items-center justify-center rounded-lg border border-border-subtle bg-white/95 text-text-secondary shadow-sm transition-colors hover:border-border-champagne hover:text-champagne disabled:opacity-35">
            <Plus size={15} />
          </button>
          <button type="button" onClick={() => zoomBy(1 / ZOOM_STEP)} disabled={k <= 1} aria-label="Отдалить карту" className="flex h-9 w-9 items-center justify-center rounded-lg border border-border-subtle bg-white/95 text-text-secondary shadow-sm transition-colors hover:border-border-champagne hover:text-champagne disabled:opacity-35">
            <Minus size={15} />
          </button>
          {k > 1 && (
            <button type="button" onClick={() => setView({ k: 1, tx: 0, ty: 0 })} aria-label="Показать всю карту" className="flex h-9 w-9 items-center justify-center rounded-lg border border-border-subtle bg-white/95 text-text-secondary shadow-sm transition-colors hover:border-border-champagne hover:text-champagne">
              <Maximize2 size={14} />
            </button>
          )}
        </div>

        {hover && (
          <div className="pointer-events-none absolute bottom-3 left-3 z-10 max-w-[calc(100%-5rem)] rounded-xl border border-border-subtle bg-white/95 px-3.5 py-3 text-xs shadow-xl backdrop-blur-sm">
            <div className="font-semibold text-text-primary">{hover.country.name}</div>
            <div className="mt-1 font-mono text-base font-semibold text-champagne">
              {hover.value != null ? formatWorldValue(hover.value) : 'Нет данных'}
            </div>
            {hover.value != null && unit && <div className="mt-0.5 text-[10px] text-text-tertiary">{unit}</div>}
            {hover.value != null && colorModel.describe(hover.value) && (
              <div
                className="mt-1 text-[10px] font-medium"
                style={{ color: colorModel.labelColorFor(hover.value) }}
              >
                {colorModel.describe(hover.value)}
              </div>
            )}
            {(hover.detail?.date || periodLabel) && (
              <div className="mt-1.5 border-t border-border-subtle pt-1.5 font-mono text-[10px] text-text-tertiary">
                {hover.detail?.date || periodLabel}
              </div>
            )}
          </div>
        )}
      </div>

      {valuesByCode && (
        <div className="mt-4 rounded-xl border border-border-subtle bg-obsidian-light/45 px-3 py-3">
          <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <div className="text-[10px] font-medium text-text-secondary">
              {metricName || 'Распределение показателя'}
              {periodLabel ? (
                <span className="font-mono text-text-tertiary"> — {periodLabel}</span>
              ) : null}
            </div>
            <div className="text-[9px] uppercase tracking-[0.13em] text-text-tertiary">
              {colorModel.kind === 'diverging' ? 'Отклонение от нуля' : 'Положение относительно медианы'}
            </div>
          </div>
          <div className="mx-auto grid max-w-[46rem] grid-cols-4 gap-1.5 sm:grid-cols-7">
            {colorModel.bins.map((bin, index) => (
              <div
                key={`${bin.color}-${index}`}
                className="min-w-0 text-center"
                title={bin.label}
              >
                <div
                  className="h-3.5 rounded-[4px] border border-black/[0.08] shadow-[inset_0_1px_0_rgba(255,255,255,0.32)]"
                  style={{ backgroundColor: bin.color }}
                />
                <div className="mt-1 truncate font-mono text-[8px] tabular-nums text-text-tertiary sm:text-[9px]">
                  {legendBinLabel(bin)}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-2.5 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-[10px] text-text-tertiary">
            <span className="font-medium text-text-secondary">
              {colorModel.kind === 'diverging'
                ? 'Бордовый — ниже нуля; светлый — около нуля; зелёный — выше нуля'
                : 'Синий — ниже медианы; светлый — около медианы; золотой — выше медианы'}
            </span>
            {colorModel.median != null && (
              <span>
                Медиана: {formatWorldValue(colorModel.median)}
                {unit ? ` ${unit}` : ''}
              </span>
            )}
            {colorModel.sampleSize > 0 && <span>Стран с данными: {colorModel.sampleSize}</span>}
            {extent && (
              <span>
                Диапазон: {formatWorldValue(extent.min)}–{formatWorldValue(extent.max)}
                {unit ? ` ${unit}` : ''}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5">
              <span
                className="h-2.5 w-4 rounded-[3px] border border-black/[0.08]"
                style={{
                  backgroundColor: WORLD_NO_DATA,
                  backgroundImage: 'repeating-linear-gradient(35deg, transparent 0, transparent 3px, rgba(122,132,130,0.2) 3px, rgba(122,132,130,0.2) 5px)',
                }}
              />
              Нет данных
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

const SILHOUETTE_FREQ = {
  daily: 'D',
  weekly: 'W',
  monthly: 'M',
  quarterly: 'Q',
  annual: 'A',
};

export function CountrySilhouette({
  code,
  name,
  region = '',
  historyStart = '',
  historyEnd = '',
  frequencies = [],
}) {
  const geometry = useMemo(
    () => {
      const item = WORLD_FEATURES.find(
        (featureItem) => ISO_NUMERIC_TO_ALPHA2[numericId(featureItem.id)] === code,
      );
      return item ? displayWorldGeometry(item, code) : null;
    },
    [code],
  );
  const countryPath = useMemo(() => {
    if (!geometry) return null;
    const projection = geoMercator().fitExtent([[24, 24], [336, 216]], geometry);
    return geoPath(projection)(geometry);
  }, [geometry]);
  if (!countryPath) return null;
  const history = historyStart
    ? `${String(historyStart).slice(0, 4)}–${String(historyEnd || historyStart).slice(0, 4)}`
    : '';
  const frequencyLabel = frequencies
    .map((frequency) => SILHOUETTE_FREQ[frequency] || frequency)
    .filter(Boolean)
    .join(', ');
  return (
    <div
      className="relative min-h-[250px] overflow-hidden rounded-2xl border border-white/10 bg-[#191A20] shadow-[0_20px_45px_rgba(24,24,31,0.18)]"
      aria-label={`Контур территории: ${name}`}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_72%_28%,rgba(207,180,95,0.2),transparent_47%)]" />
      <div
        className="pointer-events-none absolute inset-0 opacity-20"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />
      <div className="absolute left-4 top-3 z-10">
        <div className="text-[9px] font-mono uppercase tracking-[0.2em] text-white/45">
          Профиль территории
        </div>
        {region && <div className="mt-1 text-[10px] text-[#d8c58b]">{region}</div>}
      </div>
      <svg viewBox="0 0 360 240" className="relative block h-auto w-full" role="img" aria-label={`Карта страны: ${name}`}>
        <path
          d={countryPath}
          fill="#D8C177"
          stroke="rgba(255,243,197,0.78)"
          strokeWidth="1.2"
          vectorEffect="non-scaling-stroke"
          style={{ filter: 'drop-shadow(0 12px 18px rgba(0,0,0,0.28))' }}
        />
      </svg>
      <div className="absolute bottom-3 left-4 right-4 flex items-end justify-between gap-3 border-t border-white/10 pt-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-white/50">{code}</div>
          <div className="mt-0.5 max-w-[11rem] truncate text-xs font-medium text-white/90">{name}</div>
        </div>
        <div className="flex flex-wrap justify-end gap-1.5 text-[9px] font-mono text-white/60">
          {history && <span className="rounded-md border border-white/10 bg-white/5 px-2 py-1">{history}</span>}
          {frequencyLabel && <span className="rounded-md border border-white/10 bg-white/5 px-2 py-1">{frequencyLabel}</span>}
        </div>
      </div>
    </div>
  );
}
