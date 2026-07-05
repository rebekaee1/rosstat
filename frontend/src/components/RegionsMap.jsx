// Интерактивная карта субъектов РФ (choropleth): выбор показателя → регионы
// окрашиваются по квантилям, тап/клик по региону ведёт на его профиль.
// Геометрия — regionsMap.json (SVG-пути, проекция Альберса, ~66 КБ),
// сгенерирована scripts/regional/build_map_paths.py. Города федерального
// значения (Москва, СПб, Севастополь) продублированы кликабельными маркерами —
// их полигоны на мелком масштабе не разглядеть.
// Зум (+/−/сброс) и панорамирование перетаскиванием — правка созвона
// «На правки 13» (мелкие республики Кавказа не разглядеть без приближения).
import { useMemo, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Minus, Maximize2 } from 'lucide-react';
import mapData from '../lib/regionsMap.json';
import { formatRegionValue } from '../lib/regionsApi';

// Шкала от нейтрального к champagne — 5 квантильных ступеней.
const SCALE = ['#EFEAE0', '#E3D5B3', '#D2BC7E', '#BE9F4E', '#9C7B22'];
const NO_DATA = '#F3F1EC';
const ZOOM_MAX = 8;
const ZOOM_STEP = 1.6;

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

  // Зум/пан: transform = translate(tx,ty) scale(k) в координатах viewBox.
  const [view, setView] = useState({ k: 1, tx: 0, ty: 0 });
  const panRef = useRef(null); // { startX, startY, tx, ty, moved }
  const svgRef = useRef(null);

  const [, , vbW, vbH] = useMemo(
    () => mapData.viewBox.split(' ').map(Number),
    [],
  );

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

  const clampView = useCallback((next) => {
    const k = Math.max(1, Math.min(ZOOM_MAX, next.k));
    if (k === 1) return { k: 1, tx: 0, ty: 0 };
    // Не даём карте уехать за пределы рамки.
    const tx = Math.max(vbW * (1 - k), Math.min(0, next.tx));
    const ty = Math.max(vbH * (1 - k), Math.min(0, next.ty));
    return { k, tx, ty };
  }, [vbW, vbH]);

  const zoomBy = useCallback((factor) => {
    setView(prev => {
      const k = Math.max(1, Math.min(ZOOM_MAX, prev.k * factor));
      // Держим центр рамки на месте: c = t + k*p ⇒ t' = c - k'*(c - t)/k.
      const cx = vbW / 2;
      const cy = vbH / 2;
      return clampView({
        k,
        tx: cx - (k / prev.k) * (cx - prev.tx),
        ty: cy - (k / prev.k) * (cy - prev.ty),
      });
    });
  }, [vbW, vbH, clampView]);

  const handleSelect = useCallback((slug) => {
    if (panRef.current?.moved) return; // это был drag, не клик
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

  // Панорамирование: активно только в приближении, drag ≥ 6px подавляет клик.
  const onPointerDown = useCallback((e) => {
    if (view.k === 1) return;
    panRef.current = { startX: e.clientX, startY: e.clientY, tx: view.tx, ty: view.ty, moved: false };
  }, [view]);

  const onPointerMove = useCallback((e) => {
    const p = panRef.current;
    if (!p) return;
    const dx = e.clientX - p.startX;
    const dy = e.clientY - p.startY;
    if (!p.moved && Math.hypot(dx, dy) < 6) return;
    if (!p.moved) {
      p.moved = true;
      try { svgRef.current?.setPointerCapture(e.pointerId); } catch { /* ok */ }
    }
    const box = svgRef.current.getBoundingClientRect();
    const scaleX = vbW / box.width;
    const scaleY = vbH / box.height;
    setView(prev => clampView({ k: prev.k, tx: p.tx + dx * scaleX, ty: p.ty + dy * scaleY }));
  }, [vbW, vbH, clampView]);

  const onPointerUp = useCallback(() => {
    // moved-флаг живёт до следующего pointerdown — click срабатывает после
    // pointerup, и handleSelect должен его увидеть.
    setTimeout(() => { panRef.current = null; }, 0);
  }, []);

  const hoverValue = hover && valuesBySlug ? valuesBySlug.get(hover.slug) : null;
  const { k, tx, ty } = view;

  return (
    <div className="relative select-none">
      <svg
        ref={svgRef}
        viewBox={mapData.viewBox}
        className={`w-full h-auto ${k > 1 ? 'cursor-grab active:cursor-grabbing' : ''}`}
        role="group"
        aria-label="Карта регионов России"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        style={{ touchAction: k > 1 ? 'none' : 'pan-y' }}
      >
        <g transform={`translate(${tx} ${ty}) scale(${k})`}>
          {mapData.regions.map(r => (
            <path
              key={r.slug}
              d={r.path}
              fill={colorFor(r.slug)}
              stroke={hover?.slug === r.slug ? '#B8942F' : 'rgba(26,26,46,0.18)'}
              strokeWidth={(hover?.slug === r.slug ? 1.6 : 0.5) / k}
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
              r={(hover?.slug === m.slug ? 9 : 7) / k}
              fill={colorFor(m.slug)}
              stroke={hover?.slug === m.slug ? '#B8942F' : 'rgba(26,26,46,0.45)'}
              strokeWidth={1.4 / k}
              className="cursor-pointer"
              onClick={() => handleSelect(m.slug)}
              onMouseMove={(e) => handleMove(e, m.slug)}
              onMouseLeave={() => setHover(null)}
              role="button"
              aria-label={nameBySlug[m.slug] || m.slug}
              tabIndex={-1}
            />
          ))}
        </g>
      </svg>

      {/* Кнопки масштаба */}
      <div className="absolute right-2 top-2 flex flex-col gap-1" data-no-export="true">
        <button
          type="button"
          onClick={() => zoomBy(ZOOM_STEP)}
          disabled={k >= ZOOM_MAX}
          aria-label="Приблизить карту"
          title="Приблизить"
          className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface border border-border-subtle text-text-secondary hover:text-champagne hover:border-border-champagne transition-colors shadow-sm disabled:opacity-40"
        >
          <Plus size={15} />
        </button>
        <button
          type="button"
          onClick={() => zoomBy(1 / ZOOM_STEP)}
          disabled={k <= 1}
          aria-label="Отдалить карту"
          title="Отдалить"
          className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface border border-border-subtle text-text-secondary hover:text-champagne hover:border-border-champagne transition-colors shadow-sm disabled:opacity-40"
        >
          <Minus size={15} />
        </button>
        {k > 1 && (
          <button
            type="button"
            onClick={() => setView({ k: 1, tx: 0, ty: 0 })}
            aria-label="Показать всю карту"
            title="Вся карта"
            className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface border border-border-subtle text-text-secondary hover:text-champagne hover:border-border-champagne transition-colors shadow-sm"
          >
            <Maximize2 size={14} />
          </button>
        )}
      </div>

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
