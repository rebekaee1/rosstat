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
import { colorsBySlug, valueExtent, MAP_SCALE, MAP_NO_DATA } from '../lib/regionsMapColors';
import {
  regionPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';

const ZOOM_MAX = 8;
const ZOOM_STEP = 1.6;

/** Тёмный режим витрины (hero /russia): шампань как у CountrySilhouette. */
const DARK_FILL = '#D8C177';
const DARK_NO_DATA = '#3A3B44';
const DARK_STROKE = 'rgba(255,243,197,0.38)';
const DARK_HOVER_STROKE = '#F3E6B0';
const LIGHT_STROKE = 'rgba(26,26,46,0.18)';
const LIGHT_HOVER_STROKE = '#B8942F';
/** Плотный кадр без полей — геометрия почти вписана в исходный viewBox. */
const COMPACT_VIEWBOX = '8 6 984 526';

export default function RegionsMap({
  valuesBySlug = null,      // Map slug -> value (для choropleth) или null
  unit = '',
  nameBySlug = {},          // slug -> имя региона (для тултипа)
  onSelect = null,          // клик по региону; по умолчанию — переход на профиль
  transitionMs = 150,       // длительность перехода цвета (плавность анимации по годам)
  brandMark = false,        // тонкий бренд в углу live-UI (в экспорт не попадает)
  variant = 'full',         // compact — витрина без зум-контролов (hero, карточки)
  theme = 'light',          // dark — тёмная territory-карточка (champagne accents)
  colorDirection = null,    // 'asc'/'desc' — привязка шкалы к порядку сортировки рейтинга
  className = '',           // доп. классы SVG-обёртки (например aspect-square)
}) {
  const compact = variant === 'compact';
  const dark = theme === 'dark';
  const { t } = useLocale();
  const navigate = useNavigate();
  const [hover, setHover] = useState(null); // { slug, x, y }

  // Зум/пан: transform = translate(tx,ty) scale(k) в координатах viewBox.
  const [view, setView] = useState({ k: 1, tx: 0, ty: 0 });
  const panRef = useRef(null); // { startX, startY, tx, ty, moved }
  const svgRef = useRef(null);

  const viewBox = compact ? COMPACT_VIEWBOX : mapData.viewBox;
  const [, , vbW, vbH] = useMemo(
    () => viewBox.split(' ').map(Number),
    [viewBox],
  );

  // Квантильная шкала по ТЕКУЩЕМУ срезу (год на ползунке): цвет отражает
  // относительную позицию региона среди других В ЭТОМ ГОДУ.
  const colorBySlug = useMemo(
    () => colorsBySlug(valuesBySlug, { direction: colorDirection }),
    [valuesBySlug, colorDirection],
  );
  const extent = useMemo(() => valueExtent(valuesBySlug), [valuesBySlug]);
  const fallbackFill = dark
    ? (valuesBySlug ? DARK_NO_DATA : DARK_FILL)
    : MAP_NO_DATA;
  const colorFor = (slug) => colorBySlug.get(slug) ?? fallbackFill;
  const regionStroke = dark ? DARK_STROKE : LIGHT_STROKE;
  const hoverStroke = dark ? DARK_HOVER_STROKE : LIGHT_HOVER_STROKE;
  const regionStrokeWidth = dark ? 0.35 : 0.5;

  // Hover-outline берёт путь из той же mapData, что и fill — без отдельного
  // кэша геометрии (баг: при зуме обводка «отставала» от актуальных полигонов,
  // когда stroke жил на fill-слое с /k и конкурировал с seal-обводкой).
  const hoverRegion = useMemo(
    () => (hover ? mapData.regions.find((r) => r.slug === hover.slug) : null),
    [hover],
  );
  const hoverMarker = useMemo(
    () => (hover ? mapData.markers.find((m) => m.slug === hover.slug) : null),
    [hover],
  );

  const clampView = useCallback((next) => {
    const k = Math.max(1, Math.min(ZOOM_MAX, next.k));
    if (k === 1) return { k: 1, tx: 0, ty: 0 };
    const tx = Math.max(vbW * (1 - k), Math.min(0, next.tx));
    const ty = Math.max(vbH * (1 - k), Math.min(0, next.ty));
    return { k, tx, ty };
  }, [vbW, vbH]);

  const zoomBy = useCallback((factor) => {
    setView((prev) => {
      const k = Math.max(1, Math.min(ZOOM_MAX, prev.k * factor));
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
    if (panRef.current?.moved) return;
    if (onSelect) onSelect(slug);
    else navigate(regionPath(slug));
  }, [onSelect, navigate]);

  const handleMove = useCallback((e, slug) => {
    const box = e.currentTarget.ownerSVGElement.getBoundingClientRect();
    setHover({
      slug,
      x: ((e.clientX - box.left) / box.width) * 100,
      y: ((e.clientY - box.top) / box.height) * 100,
    });
  }, []);

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
    setView((prev) => clampView({ k: prev.k, tx: p.tx + dx * scaleX, ty: p.ty + dy * scaleY }));
  }, [vbW, vbH, clampView]);

  const onPointerUp = useCallback(() => {
    setTimeout(() => { panRef.current = null; }, 0);
  }, []);

  const hoverValue = hover && valuesBySlug ? valuesBySlug.get(hover.slug) : null;
  const { k, tx, ty } = view;

  // Compact-тултип: одна строка «имя + значение», прижатая внутрь квадрата —
  // контейнер витрины overflow-hidden, обычный перевод на -50% резал бы края.
  const compactHover = compact && hover
    ? {
      ...hover,
      x: Math.min(Math.max(hover.x, 14), 86),
      y: Math.min(Math.max(hover.y, 16), 92),
    }
    : null;

  return (
    <div className={`select-none ${className}`.trim()}>
      {/* Обёртка только под SVG: бренд и зум привязаны к карте, не к легенде. */}
      <div className="relative">
        <svg
          ref={svgRef}
          viewBox={viewBox}
          className={`w-full h-auto ${k > 1 ? 'cursor-grab active:cursor-grabbing' : ''}`}
          role="group"
          aria-label={t('regions.mapAria')}
          onPointerDown={compact ? undefined : onPointerDown}
          onPointerMove={compact ? undefined : onPointerMove}
          onPointerUp={compact ? undefined : onPointerUp}
          onPointerCancel={compact ? undefined : onPointerUp}
          style={{ touchAction: k > 1 && !compact ? 'none' : 'pan-y' }}
        >
          <g transform={`translate(${tx} ${ty}) scale(${k})`}>
            {/* Подложка-«шов»: обводка своим цветом фиксированной (не /k) толщины —
                закрывает микрозазоры упрощённых полигонов при зуме. */}
            {mapData.regions.map((r) => (
              <path
                key={`seal-${r.slug}`}
                d={r.path}
                fill={colorFor(r.slug)}
                stroke={colorFor(r.slug)}
                strokeWidth={dark ? 0.9 : 1.4}
                style={{ transition: `fill ${transitionMs}ms ease, stroke ${transitionMs}ms ease` }}
                pointerEvents="none"
                aria-hidden="true"
              />
            ))}
            {/* Интерактивный слой: fill + тонкая постоянная обводка (screen px).
                Hover-stroke сюда НЕ кладём — отдельный overlay ниже. */}
            {mapData.regions.map((r) => (
              <path
                key={r.slug}
                d={r.path}
                fill={colorFor(r.slug)}
                stroke={regionStroke}
                strokeWidth={regionStrokeWidth}
                vectorEffect="non-scaling-stroke"
                style={{ transition: `fill ${transitionMs}ms ease` }}
                className="cursor-pointer"
                onClick={() => handleSelect(r.slug)}
                onMouseMove={(e) => handleMove(e, r.slug)}
                onMouseLeave={() => setHover(null)}
                role="button"
                aria-label={nameBySlug[r.slug] || r.slug}
                data-region-slug={r.slug}
                tabIndex={-1}
              />
            ))}
            {mapData.markers.map((m) => (
              <circle
                key={m.slug}
                cx={m.cx}
                cy={m.cy}
                r={(dark ? 5.5 : 7) / k}
                fill={colorFor(m.slug)}
                stroke={dark ? 'rgba(255,243,197,0.7)' : 'rgba(26,26,46,0.45)'}
                strokeWidth={dark ? 1 : 1.4}
                vectorEffect="non-scaling-stroke"
                style={{ transition: `fill ${transitionMs}ms ease` }}
                className="cursor-pointer"
                onClick={() => handleSelect(m.slug)}
                onMouseMove={(e) => handleMove(e, m.slug)}
                onMouseLeave={() => setHover(null)}
                role="button"
                aria-label={nameBySlug[m.slug] || m.slug}
                data-region-slug={m.slug}
                tabIndex={-1}
              />
            ))}
            {/* Hover-outline: актуальный path/marker из mapData (та же геометрия,
                что fill). vector-effect=non-scaling-stroke — толщина в px экрана
                при любом зуме, без «отстающей» /k-обводки на fill-слое. */}
            {hoverRegion && (
              <path
                d={hoverRegion.path}
                fill="none"
                stroke={hoverStroke}
                strokeWidth={dark ? 1.6 : 2}
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
                aria-hidden="true"
                data-hover-outline={hoverRegion.slug}
              />
            )}
            {hoverMarker && (
              <circle
                cx={hoverMarker.cx}
                cy={hoverMarker.cy}
                r={(dark ? 7.5 : 9) / k}
                fill="none"
                stroke={hoverStroke}
                strokeWidth={dark ? 1.6 : 2}
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
                aria-hidden="true"
                data-hover-outline={hoverMarker.slug}
              />
            )}
          </g>
        </svg>

        {!compact && (
          <div className="absolute right-2 top-2 flex flex-col gap-1" data-no-export="true">
            <button
              type="button"
              onClick={() => zoomBy(ZOOM_STEP)}
              disabled={k >= ZOOM_MAX}
              aria-label={t('regions.zoomIn')}
              title={t('regions.zoomIn')}
              className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface border border-border-subtle text-text-secondary hover:text-champagne hover:border-border-champagne transition-colors shadow-sm disabled:opacity-40"
            >
              <Plus size={15} />
            </button>
            <button
              type="button"
              onClick={() => zoomBy(1 / ZOOM_STEP)}
              disabled={k <= 1}
              aria-label={t('regions.zoomOut')}
              title={t('regions.zoomOut')}
              className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface border border-border-subtle text-text-secondary hover:text-champagne hover:border-border-champagne transition-colors shadow-sm disabled:opacity-40"
            >
              <Minus size={15} />
            </button>
            {k > 1 && (
              <button
                type="button"
                onClick={() => setView({ k: 1, tx: 0, ty: 0 })}
                aria-label={t('regions.zoomReset')}
                title={t('regions.zoomReset')}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface border border-border-subtle text-text-secondary hover:text-champagne hover:border-border-champagne transition-colors shadow-sm"
              >
                <Maximize2 size={14} />
              </button>
            )}
          </div>
        )}

        {brandMark && (
          <div
            className="absolute left-2.5 bottom-2.5 pointer-events-none select-none"
            data-no-export="true"
            aria-hidden="true"
          >
            <span className="block text-[10px] leading-none font-medium tracking-[0.04em] text-text-tertiary/55">
              Forecast Economy
            </span>
          </div>
        )}

        {compact && compactHover && nameBySlug[hover.slug] && (
          <div
            className="absolute z-10 pointer-events-none rounded-lg border border-white/25 bg-[#1E1F26]/92 px-2.5 py-1 text-[11px] text-white shadow-lg whitespace-nowrap"
            style={{ left: `${compactHover.x}%`, top: `${compactHover.y}%`, transform: 'translate(-50%, -50%)' }}
          >
            <span className="font-medium">{nameBySlug[hover.slug]}</span>
            {hoverValue != null && (
              <span className="ml-1.5 font-mono text-[#D8C177]">
                {formatRegionValue(hoverValue)}{unit ? `\u00A0${unit}` : ''}
              </span>
            )}
          </div>
        )}

        {!compact && hover && (
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
      </div>

      {valuesBySlug && (
        <div className="mt-2 flex items-center justify-center gap-2.5 text-[11px] text-text-tertiary font-mono tabular-nums">
          <span className="min-w-[3.5rem] text-right">
            {extent ? formatRegionValue(extent.min) : '—'}
          </span>
          <div className="flex h-2.5 rounded-sm overflow-hidden border border-border-subtle/60" aria-hidden="true">
            {MAP_SCALE.map((c) => (
              <span key={c} className="w-8 h-2.5" style={{ backgroundColor: c }} />
            ))}
          </div>
          <span className="min-w-[3.5rem] text-left">
            {extent ? `${formatRegionValue(extent.max)}${unit ? ` ${unit}` : ''}` : '—'}
          </span>
        </div>
      )}
    </div>
  );
}
