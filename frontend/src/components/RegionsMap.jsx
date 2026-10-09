// Интерактивная карта субъектов РФ (choropleth): выбор показателя → регионы
// окрашиваются по квантилям, тап/клик по региону ведёт на его профиль.
// Геометрия — regionsMap.json (SVG-пути, проекция Альберса, ~66 КБ),
// сгенерирована scripts/regional/build_map_paths.py. Города федерального
// значения (Москва, СПб, Севастополь) продублированы кликабельными маркерами —
// их полигоны на мелком масштабе не разглядеть.
// Зум (+/−/сброс) и панорамирование перетаскиванием — правка созвона
// «На правки 13» (мелкие республики Кавказа не разглядеть без приближения).
import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, Minus, Maximize2, X, ArrowRight, GitCompare } from 'lucide-react';
import mapData from '../lib/regionsMap.json';
import { formatRegionValue } from '../lib/regionsApi';
import { unitLabel } from '../lib/regionUi';
import { colorsBySlug, valueExtent, MAP_SCALE, MAP_NO_DATA } from '../lib/regionsMapColors';
import { bubbleLayout } from '../lib/regionsBubbles';
import {
  regionPath,
  regionVsPath,
} from '../lib/sitePaths';
import { useLocale } from '../i18n';
import RegionComparePick from './regions/RegionComparePick';
import { CHART_THEME } from '../lib/chartTheme';
import '../styles/regions-w4.css';
import '../styles/w6f-pages.css';

const ZOOM_MAX = 8;
const ZOOM_STEP = 1.6;

/** Тёмный режим витрины (hero /russia): ледяной хрусталь как у CountrySilhouette (круг 6: шампань снята). */
const DARK_FILL = '#B9CCE8';
const DARK_NO_DATA = '#3A3B44';
const DARK_STROKE = 'rgba(255,255,255,0.4)';
const DARK_HOVER_STROKE = '#FFFFFF';
const LIGHT_STROKE = 'rgba(26,26,46,0.18)';
const LIGHT_HOVER_STROKE = CHART_THEME.champagne;
/** Плотный кадр без полей — геометрия почти вписана в исходный viewBox. */
const COMPACT_VIEWBOX = '8 6 984 526';
/** Живая карта получает поля вокруг геометрии: Чукотка, Камчатка и обводка не упираются в рамку. */
const LIVE_PAD = 8;
/** Слева шире: маркер Севастополя стоит у самого края (cx≈0, радиус 10) и без запаса обрезался (круг 8, Y3). */
const LIVE_PAD_LEFT = 16;

function paddedViewBox(box) {
  const [x, y, w, h] = box.split(' ').map(Number);
  if (![x, y, w, h].every(Number.isFinite)) return box;
  return `${x - LIVE_PAD_LEFT} ${y - LIVE_PAD} ${w + LIVE_PAD + LIVE_PAD_LEFT} ${h + LIVE_PAD * 2}`;
}

export default function RegionsMap({
  valuesBySlug = null,      // Map slug -> value (для choropleth) или null
  fillValuesBySlug = null,  // Круг 10: значения только для раскраски (прошлый год, пока грузится новый); подсказки, место и шкала берут valuesBySlug
  unit = '',
  nameBySlug = {},          // slug -> имя региона (для тултипа)
  onSelect = null,          // клик по региону; по умолчанию — переход на профиль
  transitionMs = 150,       // длительность перехода цвета (плавность анимации по годам)
  brandMark = false,        // тонкий бренд в углу live-UI (в экспорт не попадает)
  variant = 'full',         // compact — витрина без зум-контролов (hero, карточки)
  theme = 'light',          // dark — тёмная territory-карточка (champagne accents)
  colorDirection = null,    // 'asc'/'desc' — привязка шкалы к порядку сортировки рейтинга
  className = '',           // доп. классы SVG-обёртки (например aspect-square)
  mapData: mapDataProp = null, // чужая геометрия; compact viewBox России — только дефолт
  ariaLabel = null,
  shape = 'regions',        // 'bubbles' — одинаковые кружки по регионам (равная площадь), без полигонов
  pickedSlug,               // регион выбран снаружи (поиск, быстрый выбор); undefined — выбор внутри карты
  onPickedChange = null,    // сообщает наружу, что выбор изменился
  compareSlugs = null,      // Круг 11: набор регионов для сравнения (массив) снаружи; null — прежнее сравнение двух внутри карты
  onCompareToggle = null,   // Круг 11: добавить или убрать регион из набора
  compareMax = 5,
  reserveCard = false,      // Круг 11: место под карточку выбранного региона занято всегда (страница не прыгает при выборе)
}) {
  const geometry = mapDataProp || mapData;
  const compact = variant === 'compact';
  const dark = theme === 'dark';
  const { t } = useLocale();
  const navigate = useNavigate();
  const [hover, setHover] = useState(null); // { slug, x, y }
  // Касание пальцем: первое нажатие выбирает регион (подсветка + карточка со ссылкой «Открыть»),
  // переход — только по кнопке или повторному касанию. Мышь и клавиатура ведут сразу, как раньше.
  const [pickedInner, setPickedInner] = useState(null); // slug
  const picked = pickedSlug !== undefined ? pickedSlug : pickedInner;
  const setPicked = useCallback((slug) => {
    setPickedInner(slug);
    if (onPickedChange) onPickedChange(slug);
  }, [onPickedChange]);
  // Второй регион для сравнения: «Сравнить с…» на карточке выбранного региона.
  const [compareSlug, setCompareSlug] = useState(null);
  const pointerTypeRef = useRef('mouse');
  const multiCompare = Array.isArray(compareSlugs) && typeof onCompareToggle === 'function';
  const bubbles = shape === 'bubbles' && !compact;
  const bubblePos = useMemo(() => (bubbles ? bubbleLayout(geometry) : null), [bubbles, geometry]);

  // Зум/пан: transform = translate(tx,ty) scale(k) в координатах viewBox.
  const [view, setView] = useState({ k: 1, tx: 0, ty: 0 });
  const panRef = useRef(null); // { startX, startY, tx, ty, moved }
  const svgRef = useRef(null);
  const pickCardRef = useRef(null);

  const viewBox = (compact && mapDataProp == null) ? COMPACT_VIEWBOX : geometry.viewBox;
  const drawBox = compact ? viewBox : paddedViewBox(viewBox);
  const [, , vbW, vbH] = useMemo(
    () => viewBox.split(' ').map(Number),
    [viewBox],
  );

  const aspect = vbH > 0 ? Number((vbW / vbH).toFixed(3)) : 1.9;

  // Квантильная шкала по ТЕКУЩЕМУ срезу (год на ползунке): цвет отражает
  // относительную позицию региона среди других В ЭТОМ ГОДУ.
  // Пока новый год грузится, страница передаёт прошлый только для цвета: карта плавно меняет оттенок, а не гаснет в «нет данных» и не
  // возвращается (раньше это был переход через белое, круг 10, К5).
  const colorSource = fillValuesBySlug && fillValuesBySlug.size ? fillValuesBySlug : valuesBySlug;
  const colorBySlug = useMemo(
    () => colorsBySlug(colorSource, { direction: colorDirection }),
    [colorSource, colorDirection],
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
  const outlineSlug = hover?.slug || picked;
  const hoverRegion = useMemo(
    () => (outlineSlug ? geometry.regions.find((r) => r.slug === outlineSlug) : null),
    [outlineSlug, geometry.regions],
  );
  const hoverMarker = useMemo(
    () => (outlineSlug ? (geometry.markers || []).find((m) => m.slug === outlineSlug) : null),
    [outlineSlug, geometry.markers],
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

  // Приближение вокруг точки экрана (щипок двумя пальцами, колесо с Ctrl или щипок на трекпаде).
  // Точка переводится из пикселей в координаты рисунка с учётом полей viewBox, чтобы карта не «уезжала» из-под пальцев.
  const zoomAround = useCallback((factor, clientX, clientY) => {
    const svg = svgRef.current;
    if (!svg) return;
    const box = svg.getBoundingClientRect();
    if (!box.width || !box.height) return;
    const [x0, y0, dw, dh] = drawBox.split(' ').map(Number);
    const fx = x0 + ((clientX - box.left) / box.width) * dw;
    const fy = y0 + ((clientY - box.top) / box.height) * dh;
    setView((prev) => {
      const k = Math.max(1, Math.min(ZOOM_MAX, prev.k * factor));
      return clampView({
        k,
        tx: fx - (k / prev.k) * (fx - prev.tx),
        ty: fy - (k / prev.k) * (fy - prev.ty),
      });
    });
  }, [drawBox, clampView]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg || compact) return undefined;
    let pinch = null; // { dist }
    const dist = (a, b) => Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
    const onTouchStart = (e) => {
      if (e.touches.length !== 2) { pinch = null; return; }
      // Два пальца: страницу не прокручиваем и не масштабируем, приближаем карту.
      e.preventDefault();
      panRef.current = null;
      pinch = { dist: dist(e.touches[0], e.touches[1]) };
    };
    const onTouchMove = (e) => {
      if (!pinch || e.touches.length !== 2) return;
      e.preventDefault();
      const d = dist(e.touches[0], e.touches[1]);
      if (!pinch.dist || !d) return;
      const factor = d / pinch.dist;
      pinch.dist = d;
      zoomAround(
        factor,
        (e.touches[0].clientX + e.touches[1].clientX) / 2,
        (e.touches[0].clientY + e.touches[1].clientY) / 2,
      );
    };
    const onTouchEnd = (e) => { if (e.touches.length < 2) pinch = null; };
    const onWheel = (e) => {
      if (!e.ctrlKey && !e.metaKey) return; // обычное колесо прокручивает страницу
      e.preventDefault();
      zoomAround(Math.exp(-e.deltaY * 0.01), e.clientX, e.clientY);
    };
    svg.addEventListener('touchstart', onTouchStart, { passive: false });
    svg.addEventListener('touchmove', onTouchMove, { passive: false });
    svg.addEventListener('touchend', onTouchEnd);
    svg.addEventListener('touchcancel', onTouchEnd);
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      svg.removeEventListener('touchstart', onTouchStart);
      svg.removeEventListener('touchmove', onTouchMove);
      svg.removeEventListener('touchend', onTouchEnd);
      svg.removeEventListener('touchcancel', onTouchEnd);
      svg.removeEventListener('wheel', onWheel);
    };
  }, [compact, zoomAround]);

  const openRegion = useCallback((slug) => {
    if (onSelect) onSelect(slug);
    else navigate(regionPath(slug));
  }, [onSelect, navigate]);

  const handleSelect = useCallback((slug) => {
    if (panRef.current?.moved) return;
    const touch = !compact && pointerTypeRef.current !== 'mouse';
    if (touch && picked !== slug) {
      setPicked(slug);
      setHover(null);
      return;
    }
    openRegion(slug);
  }, [compact, picked, openRegion, setPicked]);

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

  // Карточка выбранного региона появляется под картой и на невысоком экране оказывалась за нижней кромкой:
  // подводим её в видимую часть (минимальным сдвигом, без прыжка, если она уже видна).
  useEffect(() => {
    if (compact || !picked) return;
    const el = pickCardRef.current;
    if (!el || typeof el.scrollIntoView !== 'function') return;
    const reduce = typeof window !== 'undefined' && window.matchMedia
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
  }, [picked, compact]);

  // Место выбранного региона среди всех, у кого есть значение (1 — самое высокое значение).
  const rank = useMemo(() => {
    if (!picked || !valuesBySlug) return null;
    const mine = valuesBySlug.get(picked);
    if (mine == null) return null;
    const all = [...valuesBySlug.values()].filter((v) => v != null && Number.isFinite(Number(v)));
    return { place: all.filter((v) => Number(v) > Number(mine)).length + 1, total: all.length };
  }, [picked, valuesBySlug]);

  const hoverValue = hover && valuesBySlug ? valuesBySlug.get(hover.slug) : null;
  const { k, tx, ty } = view;
  const unitText = unitLabel(unit) || unit;

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
    <div
      className={`select-none ${className}`.trim()}
      onPointerDownCapture={(e) => { pointerTypeRef.current = e.pointerType || 'mouse'; }}
    >
      {/* Обёртка только под SVG: бренд и зум привязаны к карте, не к легенде. */}
      <div className="fe-map-frame">
        <svg
          ref={svgRef}
          viewBox={drawBox}
          className={`${compact ? '' : 'fe-map-svg '}w-full h-auto ${k > 1 ? 'cursor-grab active:cursor-grabbing' : ''}`}
          role="group"
          aria-label={ariaLabel || t('regions.mapAria')}
          onPointerDown={compact ? undefined : onPointerDown}
          onPointerMove={compact ? undefined : onPointerMove}
          onPointerUp={compact ? undefined : onPointerUp}
          onPointerCancel={compact ? undefined : onPointerUp}
          onClick={(e) => { if (e.target === e.currentTarget) setPicked(null); }}
          style={{ touchAction: k > 1 && !compact ? 'none' : 'pan-y', '--fe-map-aspect': aspect }}
        >
          <g transform={`translate(${tx} ${ty}) scale(${k})`}>
            {/* Подложка-«шов»: обводка своим цветом фиксированной (не /k) толщины —
                закрывает микрозазоры упрощённых полигонов при зуме. */}
            {!bubbles && geometry.regions.map((r) => (
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
            {bubbles && geometry.regions.map((r) => (
              <path
                key={`ghost-${r.slug}`}
                d={r.path}
                fill="none"
                stroke="rgba(26,26,46,0.12)"
                strokeWidth={0.5}
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
                aria-hidden="true"
              />
            ))}
            {bubbles && geometry.regions.map((r) => {
              const pos = bubblePos.get(r.slug);
              if (!pos) return null;
              return (
                <circle
                  key={`bubble-${r.slug}`}
                  cx={pos.x}
                  cy={pos.y}
                  r={pos.r}
                  fill={colorFor(r.slug)}
                  stroke="rgba(26,26,46,0.35)"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                  style={{ transition: `fill ${transitionMs}ms ease` }}
                  className="cursor-pointer"
                  onClick={() => handleSelect(r.slug)}
                  onMouseMove={(e) => handleMove(e, r.slug)}
                  onMouseLeave={() => setHover(null)}
                  role="button"
                  aria-label={nameBySlug[r.slug] || r.slug}
                  data-region-slug={r.slug}
                  data-bubble="true"
                  tabIndex={-1}
                />
              );
            })}
            {!bubbles && geometry.regions.map((r) => (
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
            {!bubbles && (geometry.markers || []).map((m) => (
              <g
                key={m.slug}
                className="cursor-pointer"
                onClick={() => handleSelect(m.slug)}
                onMouseMove={(e) => handleMove(e, m.slug)}
                onMouseLeave={() => setHover(null)}
                role="button"
                aria-label={nameBySlug[m.slug] || m.slug}
                data-region-slug={m.slug}
                tabIndex={-1}
              >
                {/* Невидимый широкий круг: в маркер размером с зерно пальцем не попасть. */}
                {!compact && <circle cx={m.cx} cy={m.cy} r={20 / k} fill="transparent" />}
                <circle
                  cx={m.cx}
                  cy={m.cy}
                  r={(dark ? 6.5 : 10) / k}
                  fill={colorFor(m.slug)}
                  stroke={dark ? 'rgba(255,243,197,0.7)' : 'rgba(26,26,46,0.45)'}
                  strokeWidth={dark ? 1 : 1.4}
                  vectorEffect="non-scaling-stroke"
                  style={{ transition: `fill ${transitionMs}ms ease` }}
                />
              </g>
            ))}
            {/* Hover-outline: актуальный path/marker из mapData (та же геометрия,
                что fill). vector-effect=non-scaling-stroke — толщина в px экрана
                при любом зуме, без «отстающей» /k-обводки на fill-слое. */}
            {bubbles && outlineSlug && bubblePos.get(outlineSlug) && (
              <circle
                cx={bubblePos.get(outlineSlug).x}
                cy={bubblePos.get(outlineSlug).y}
                r={bubblePos.get(outlineSlug).r + 1.6}
                fill="none"
                stroke={hoverStroke}
                strokeWidth={2}
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
                aria-hidden="true"
                data-hover-outline={outlineSlug}
              />
            )}
            {!bubbles && hoverRegion && (
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
            {!bubbles && hoverMarker && (
              <circle
                cx={hoverMarker.cx}
                cy={hoverMarker.cy}
                r={(dark ? 8.5 : 12) / k}
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

        {(!compact || brandMark) && (
          <div className="fe-map-bar">
            {brandMark && (
              <span className="fe-map-mark" data-no-export="true" aria-hidden="true">Forecast Economy</span>
            )}
            {!compact && (
              <div className="fe-map-tools" data-no-export="true">
                <button
                  type="button"
                  onClick={() => zoomBy(ZOOM_STEP)}
                  disabled={k >= ZOOM_MAX}
                  aria-label={t('regions.zoomIn')}
                  title={t('regions.zoomIn')}
                  className="fe-map-btn fe-press text-text-secondary transition-colors hover:text-champagne-ink disabled:opacity-40"
                >
                  <Plus size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => zoomBy(1 / ZOOM_STEP)}
                  disabled={k <= 1}
                  aria-label={t('regions.zoomOut')}
                  title={t('regions.zoomOut')}
                  className="fe-map-btn fe-press text-text-secondary transition-colors hover:text-champagne-ink disabled:opacity-40"
                >
                  <Minus size={16} />
                </button>
                {k > 1 && (
                  <button
                    type="button"
                    onClick={() => setView({ k: 1, tx: 0, ty: 0 })}
                    aria-label={t('regions.zoomReset')}
                    title={t('regions.zoomReset')}
                    className="fe-map-btn fe-press text-text-secondary transition-colors hover:text-champagne-ink"
                  >
                    <Maximize2 size={15} />
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {compact && compactHover && nameBySlug[hover.slug] && (
          <div
            className="absolute z-10 pointer-events-none rounded-lg bg-[#1E1F26]/92 px-2.5 py-1 text-xs text-white shadow-lg whitespace-nowrap"
            style={{ left: `${compactHover.x}%`, top: `${compactHover.y}%`, transform: 'translate(-50%, -50%)' }}
          >
            <span className="font-medium">{nameBySlug[hover.slug]}</span>
            {hoverValue != null && (
              <span className="ml-1.5 font-mono text-[#BFD2F0]">
                {formatRegionValue(hoverValue)}{unit ? `\u00A0${unit}` : ''}
              </span>
            )}
          </div>
        )}

        {!compact && hover && (
          <div
            className="absolute z-10 pointer-events-none rounded-lg px-3 py-1.5 shadow-lg text-xs whitespace-nowrap -translate-x-1/2 -translate-y-full fe-glass-pop"
            style={{ left: `${hover.x}%`, top: `${Math.max(hover.y - 2, 0)}%` }}
          >
            <div className="font-medium text-text-primary">{nameBySlug[hover.slug] || hover.slug}</div>
            {hoverValue != null && (
              <div className="font-mono text-champagne-ink mt-0.5">
                {formatRegionValue(hoverValue)}{unit ? ` ${unit}` : ''}
              </div>
            )}
          </div>
        )}
      </div>

      {!compact && !picked && reserveCard && (
        <div className="fe-map-pick fe-map-pick--empty" data-no-export="true" data-testid="map-pick-empty">
          <p className="fe-map-pick__prompt">{t('c11f.reg.pick.empty')}</p>
        </div>
      )}
      {!compact && picked && (
        <div className={`fe-map-pick${reserveCard ? ' fe-map-pick--reserve' : ''}`} role="status" data-no-export="true" ref={pickCardRef}>
          <div className="fe-map-pick__text">
            <div className="fe-map-pick__name">{nameBySlug[picked] || picked}</div>
            {valuesBySlug?.get(picked) != null && (
              <div className="fe-map-pick__value">
                {formatRegionValue(valuesBySlug.get(picked))}{unitText ? `\u00A0${unitText}` : ''}
              </div>
            )}
            {rank && (
              <div className="fe-map-pick__rank" data-testid="map-pick-rank">
                {t('w6f.map.place', { place: rank.place, total: rank.total })}
              </div>
            )}
          </div>
          <div className={`fe-map-pick__actions${multiCompare ? ' fe-map-pick__actions--grid' : ''}`}>
            {multiCompare ? (
              <button
                type="button"
                className="fe-map-pick__cmp fe-press"
                aria-pressed={compareSlugs.includes(picked)}
                disabled={!compareSlugs.includes(picked) && compareSlugs.length >= compareMax}
                onClick={() => onCompareToggle(picked)}
              >
                <GitCompare size={14} aria-hidden="true" />
                {compareSlugs.includes(picked) ? t('c11f.reg.compare.inSet') : t('c11f.reg.compare.add')}
              </button>
            ) : compareSlug && compareSlug !== picked ? (
              <Link to={regionVsPath(compareSlug, picked)} className="fe-map-pick__open fe-press">
                <GitCompare size={14} aria-hidden="true" />
                {t('w6f.map.compareWith', { name: nameBySlug[compareSlug] || compareSlug })}
              </Link>
            ) : (
              <button
                type="button"
                className="fe-map-pick__cmp fe-press"
                aria-pressed={compareSlug === picked}
                onClick={() => setCompareSlug(compareSlug === picked ? null : picked)}
              >
                <GitCompare size={14} aria-hidden="true" />
                {compareSlug === picked ? t('w6f.map.inCompare') : t('w6f.map.addCompare')}
              </button>
            )}
            <button type="button" className="fe-map-pick__open fe-press" onClick={() => openRegion(picked)}>
              {t('z2.map.open')}
              <ArrowRight size={14} aria-hidden="true" />
            </button>
            {multiCompare ? <div className="fe-map-pick__with"><RegionComparePick slug={picked} /></div> : null}
          </div>
          <button type="button" className="fe-map-pick__close fe-press" onClick={() => setPicked(null)} aria-label={t('common.close')}>
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      )}

      {valuesBySlug && (
        <div className="fe-map-legend">
          <span>
            {extent ? `${formatRegionValue(extent.min)}${unitText ? `\u00A0${unitText}` : ''}` : '—'}
          </span>
          <div className="fe-map-legend__scale" aria-hidden="true">
            {MAP_SCALE.map((c) => (
              <span key={c} style={{ backgroundColor: c }} />
            ))}
          </div>
          <span>
            {extent ? `${formatRegionValue(extent.max)}${unitText ? `\u00A0${unitText}` : ''}` : '—'}
          </span>
        </div>
      )}
    </div>
  );
}
