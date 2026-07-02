// Интерактивная карта субъектов РФ (choropleth): выбор показателя → регионы
// окрашиваются по квантилям, тап/клик по региону ведёт на его профиль.
// Геометрия — regionsMap.json (SVG-пути, проекция Альберса, ~66 КБ),
// сгенерирована scripts/regional/build_map_paths.py. Города федерального
// значения (Москва, СПб, Севастополь) продублированы кликабельными маркерами —
// их полигоны на мелком масштабе не разглядеть.
import { useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import mapData from '../lib/regionsMap.json';
import { formatRegionValue } from '../lib/regionsApi';

// Шкала от нейтрального к champagne — 5 квантильных ступеней.
const SCALE = ['#EFEAE0', '#E3D5B3', '#D2BC7E', '#BE9F4E', '#9C7B22'];
const NO_DATA = '#F3F1EC';

function buildQuantiles(values) {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return null;
  return (v) => {
    if (v == null) return NO_DATA;
    let lo = 0;
    let hi = sorted.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (sorted[mid] < v) lo = mid + 1;
      else hi = mid;
    }
    const q = lo / Math.max(sorted.length - 1, 1);
    return SCALE[Math.min(SCALE.length - 1, Math.floor(q * SCALE.length))];
  };
}

export default function RegionsMap({
  valuesBySlug = null,      // Map slug -> value (для choropleth) или null
  unit = '',
  nameBySlug = {},          // slug -> имя региона (для тултипа)
  onSelect = null,          // клик по региону; по умолчанию — переход на профиль
}) {
  const navigate = useNavigate();
  const [hover, setHover] = useState(null); // { slug, x, y }

  // Map slug → цвет (не функция-замыкание: React Compiler не может сохранить
  // memoization функций, возвращаемых из useMemo — lint preserve-manual-memoization).
  const colorBySlug = useMemo(() => {
    const out = new Map();
    if (!valuesBySlug) return out;
    const q = buildQuantiles([...valuesBySlug.values()].filter(v => v != null));
    if (!q) return out;
    for (const [slug, v] of valuesBySlug) out.set(slug, q(v));
    return out;
  }, [valuesBySlug]);
  const colorFor = (slug) => colorBySlug.get(slug) ?? NO_DATA;

  const handleSelect = useCallback((slug) => {
    if (onSelect) onSelect(slug);
    else navigate(`/region/${slug}`);
  }, [onSelect, navigate]);

  const handleMove = useCallback((e, slug) => {
    const box = e.currentTarget.ownerSVGElement.getBoundingClientRect();
    setHover({
      slug,
      x: ((e.clientX - box.left) / box.width) * 100,
      y: ((e.clientY - box.top) / box.height) * 100,
    });
  }, []);

  const hoverValue = hover && valuesBySlug ? valuesBySlug.get(hover.slug) : null;

  return (
    <div className="relative select-none">
      <svg
        viewBox={mapData.viewBox}
        className="w-full h-auto"
        role="group"
        aria-label="Карта регионов России"
      >
        {mapData.regions.map(r => (
          <path
            key={r.slug}
            d={r.path}
            fill={colorFor(r.slug)}
            stroke={hover?.slug === r.slug ? '#B8942F' : 'rgba(26,26,46,0.18)'}
            strokeWidth={hover?.slug === r.slug ? 1.6 : 0.5}
            className="cursor-pointer transition-[fill] duration-150 hover:brightness-95"
            onClick={() => handleSelect(r.slug)}
            onMouseMove={(e) => handleMove(e, r.slug)}
            onMouseLeave={() => setHover(null)}
            role="button"
            aria-label={nameBySlug[r.slug] || r.slug}
            tabIndex={-1}
          />
        ))}
        {mapData.markers.map(m => (
          <circle
            key={m.slug}
            cx={m.cx}
            cy={m.cy}
            r={hover?.slug === m.slug ? 9 : 7}
            fill={colorFor(m.slug)}
            stroke={hover?.slug === m.slug ? '#B8942F' : 'rgba(26,26,46,0.45)'}
            strokeWidth={1.4}
            className="cursor-pointer"
            onClick={() => handleSelect(m.slug)}
            onMouseMove={(e) => handleMove(e, m.slug)}
            onMouseLeave={() => setHover(null)}
            role="button"
            aria-label={nameBySlug[m.slug] || m.slug}
            tabIndex={-1}
          />
        ))}
      </svg>

      {/* Тултип */}
      {hover && (
        <div
          className="absolute z-10 pointer-events-none bg-surface border border-border-subtle rounded-lg px-3 py-1.5 shadow-lg text-xs whitespace-nowrap -translate-x-1/2 -translate-y-full"
          style={{ left: `${hover.x}%`, top: `${Math.max(hover.y - 2, 0)}%` }}
        >
          <div className="font-medium text-text-primary">{nameBySlug[hover.slug] || hover.slug}</div>
          {hoverValue != null && (
            <div className="font-mono text-champagne mt-0.5">
              {formatRegionValue(hoverValue)}{unit ? ` ${unit}` : ''}
            </div>
          )}
        </div>
      )}

      {/* Легенда шкалы */}
      {valuesBySlug && (
        <div className="mt-2 flex items-center gap-2 text-[11px] text-text-tertiary">
          <span>меньше</span>
          <div className="flex h-2 rounded overflow-hidden">
            {SCALE.map(c => (
              <span key={c} className="w-7 h-2" style={{ backgroundColor: c }} />
            ))}
          </div>
          <span>больше</span>
        </div>
      )}
    </div>
  );
}
