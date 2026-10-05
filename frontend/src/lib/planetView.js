import { geoArea } from 'd3-geo';
import { lonLatToSphere } from './planetGeometry';

/** Один шаг кнопок «+» и «−»: планета увеличивается или уменьшается ровно в 1,5 раза. */
export const ZOOM_STEP = 1.5;

const RAD = Math.PI / 180;

function finiteNumber(value) {
  return (typeof value === 'number' || (typeof value === 'string' && value.trim() !== '')) && Number.isFinite(Number(value));
}

function valueOf(valuesByCode, entry) {
  if (!valuesByCode) return undefined;
  const aliases = { GB: 'UK', GR: 'EL' };
  const keys = [entry.dataCode, entry.code, aliases[entry.code]].filter(Boolean);
  for (const key of keys) {
    const value = valuesByCode instanceof Map ? valuesByCode.get(key) : valuesByCode[key];
    if (value !== undefined) return value;
  }
  return undefined;
}

/** Расстояние камеры после шага масштаба: «+» приближает в ZOOM_STEP раз, «−» отдаляет; результат зажат в границы. */
export function zoomedDistance(current, direction, { min, max }) {
  const next = direction === 'in' ? current / ZOOM_STEP : current * ZOOM_STEP;
  return Math.min(max, Math.max(min, next));
}

/**
 * Расстояние камеры при выборе страны. Уже приближенный вид не отменяется (камера лишь поворачивается);
 * с общего вида камера мягко подходит ближе тем сильнее, чем меньше страна.
 * `area` — площадь страны в стерадианах (d3.geoArea).
 */
export function focusDistance({ current, fit, min, area = 0 }) {
  if (current < fit - 0.05) return current;
  const wanted = area > 0.08 ? fit / 1.2 : area > 0.005 ? 2.4 : area > 0.0005 ? 2.0 : 1.7;
  return Math.min(current, Math.max(min, wanted));
}

/** Половина видимого участка поверхности в градусах (по широте и долготе) для рамки на мини-карте. */
export function viewHalfExtent(distance, fov = 40, aspect = 1) {
  const halfV = fov * RAD / 2;
  const halfH = Math.atan(Math.tan(halfV) * (aspect > 0 ? aspect : 1));
  const reach = (half) => {
    const s = distance * Math.sin(half);
    return s >= 1 ? Math.acos(1 / distance) : Math.asin(s) - half;
  };
  const deg = (value) => Math.min(90, Math.max(2, value / RAD));
  return { lat: deg(reach(halfV)), lon: deg(reach(halfH)) };
}

/** Единичные векторы центров стран, у которых есть значение: по ним решаем, видна ли хоть одна окрашенная страна. */
export function dataVectors(entries, valuesByCode) {
  const best = new Map();
  for (const entry of entries || []) {
    const code = entry.code || entry.dataCode;
    if (!code || !entry.focus || !finiteNumber(valueOf(valuesByCode, entry))) continue;
    const area = entry.feature ? geoArea(entry.feature) : 0;
    const known = best.get(code);
    if (!known || known.area < area) best.set(code, { area, focus: entry.focus });
  }
  return [...best.values()].map((item) => ({ area: item.area, vector: lonLatToSphere(item.focus, 1) })).filter((item) => item.vector);
}

/** Есть ли в поле зрения (в пределах `reach` градусов от центра вида) хотя бы одна страна с данными. */
export function hasVisibleData(vectors, center, reach = 62) {
  if (!vectors.length) return true;
  const limit = Math.cos(reach * RAD);
  const length = Math.hypot(center[0], center[1], center[2]) || 1;
  return vectors.some(({ vector }) => (vector[0] * center[0] + vector[1] * center[1] + vector[2] * center[2]) / length > limit);
}

/**
 * Стартовая сторона шара: долгота, при которой в поле зрения больше всего окрашенных стран
 * (крупные весят больше, поэтому выигрывает вид с Америкой и Европой, а не одной Европой).
 */
export function bestStartFocus(entries, valuesByCode, { latitude = 24, step = 5, fallback = [-25, 24] } = {}) {
  const items = dataVectors(entries, valuesByCode);
  if (items.length < 3) return fallback;
  let best = null;
  for (let lon = -180; lon < 180; lon += step) {
    const center = lonLatToSphere([lon, latitude], 1);
    let score = 0;
    for (const { vector, area } of items) {
      const dot = vector[0] * center[0] + vector[1] * center[1] + vector[2] * center[2];
      if (dot > 0.25) score += (0.35 + Math.sqrt(Math.max(area, 0))) * dot;
    }
    if (!best || score > best.score) best = { score, lon };
  }
  return best ? [best.lon, latitude] : fallback;
}

/** Точка, на которую смотрит камера, чтобы страна встала чуть выше центра: нижнюю часть шара закрывает шторка карточки. */
export function liftedFocus(focus, liftDegrees = 11) {
  if (!Array.isArray(focus)) return focus;
  return [focus[0], Math.max(-80, focus[1] - liftDegrees)];
}

/**
 * Годы впереди сегодняшнего — прогноз; текущий год годового среза — оценка (год ещё не закончился).
 * Месячные данные текущего года — уже факт, пометки нет. Возвращает 'forecast', 'estimate' или null.
 */
export function yearTag(year, { annual = true, now = new Date() } = {}) {
  const value = Number(year);
  if (!Number.isFinite(value)) return null;
  const current = now.getFullYear();
  if (value > current) return 'forecast';
  if (value === current && annual) return 'estimate';
  return null;
}

/** Годы для кнопки «Проиграть»: до последнего года, который уже наступил, не больше 16 лет. */
export function playbackYears(years, now = new Date()) {
  const sorted = [...(years || [])].map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (sorted.length < 2) return [];
  const limit = now.getFullYear() - 1;
  const past = sorted.filter((year) => year <= limit);
  const end = past.length ? past[past.length - 1] : sorted[sorted.length - 1];
  const upTo = sorted.filter((year) => year <= end);
  return upTo.slice(Math.max(0, upTo.length - 16));
}

/** Рамка видимого участка на плоской карте мира: подсказка «где я», пока шар приближен. */
export function viewRectangles(view, aspect = 1) {
  const half = viewHalfExtent(view.distance, 40, aspect);
  const lat = Math.max(-89, Math.min(89, view.lat));
  // К полюсам меридианы сходятся: тот же участок по долготе шире.
  const halfLon = Math.min(180, half.lon / Math.max(0.28, Math.cos(lat * Math.PI / 180)));
  const x = 180 + view.lon - halfLon;
  const y = 90 - Math.min(90, lat + half.lat);
  const width = Math.min(360, halfLon * 2);
  const height = Math.min(180, half.lat * 2);
  const rects = [{ x, y, width, height }];
  if (x < 0) rects.push({ x: x + 360, y, width, height });
  if (x + width > 360) rects.push({ x: x - 360, y, width, height });
  return rects;
}

