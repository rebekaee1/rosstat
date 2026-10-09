import { geoArea } from 'd3-geo';
import { lonLatToSphere, normalizePlanetCountryCode } from './planetGeometry';
import { formatWorldValue, localizeWorldUnit } from './worldApi';

function metricValue(valuesByCode, entry, code) {
  if (!valuesByCode) return undefined;
  const aliases = { GB: 'UK', GR: 'EL' };
  const keys = new Set([entry.dataCode, entry.code, code, aliases[code]].filter(Boolean));
  for (const key of keys) {
    if (valuesByCode instanceof Map ? valuesByCode.has(key) : Object.prototype.hasOwnProperty.call(valuesByCode, key)) {
      return valuesByCode instanceof Map ? valuesByCode.get(key) : valuesByCode[key];
    }
  }
  return undefined;
}

function finiteMetricValue(value) {
  return (typeof value === 'number' || typeof value === 'string' && value.trim() !== '')
    && Number.isFinite(Number(value));
}

/** One geographic name per country, including countries absent from the API. */
export function buildPlanetLabels(entries = [], { locale = 'ru', valuesByCode = null, unit = '', digits } = {}) {
  const names = typeof Intl.DisplayNames === 'function'
    ? new Intl.DisplayNames([locale === 'en' ? 'en' : 'ru'], { type: 'region', fallback: 'none' })
    : null;
  const labels = new Map();
  const displayUnit = localizeWorldUnit(unit, locale);
  for (const entry of entries) {
    const code = normalizePlanetCountryCode(entry.code || entry.dataCode);
    const position = lonLatToSphere(entry.focus, 1.018);
    if (!code || !position || !/^[A-Z]{2}$/.test(code)) continue;
    const area = entry.feature ? geoArea(entry.feature) : 0;
    const country = entry.country;
    const name = (locale === 'en' ? country?.name_en : country?.name_ru || country?.name)
      || names?.of(code) || entry.name || code;
    const previous = labels.get(code);
    // Remote possessions share an ISO identity; anchor the name on the main land.
    if (previous && previous.area >= area) continue;
    const rawValue = metricValue(valuesByCode, entry, code);
    const hasValue = finiteMetricValue(rawValue);
    const value = hasValue ? rawValue : null;
    const numberText = hasValue ? formatWorldValue(value, digits, locale) : '';
    const valueText = hasValue
      ? numberText + (displayUnit ? `\u00a0${displayUnit}` : '')
      : '';
    labels.set(code, {
      id: code, code, text: name, area, position, value, hasValue,
      valueText, numberText, unitText: displayUnit,
    });
  }
  return [...labels.values()].sort((a, b) => b.area - a.area || a.code.localeCompare(b.code));
}

/** Узкая строка для названий из нескольких слов: доля от полной ширины подписи. */
const WORD_SPLIT_SHARE = 0.55;

/**
 * Break at words, then Unicode code points when a single word is too wide.
 * Круг 11 (D): `splitWords` переносит название из нескольких слов по словам уже тогда, когда оно шире `WORD_SPLIT_SHARE` подписи:
 * «United Kingdom» стоит в две строки, а не одной с «проглоченным» пробелом («UnitedKingdom»).
 */
export function wrapPlanetLabel(text, measure, maxWidth, { splitWords = false } = {}) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean);
  if (splitWords && words.length > 1 && measure(words.join(' ')) > maxWidth * WORD_SPLIT_SHARE) {
    return wrapPlanetLabel(text, measure, maxWidth * WORD_SPLIT_SHARE);
  }
  const lines = [];
  let line = '';
  for (const word of String(text || '').trim().split(/\s+/).filter(Boolean)) {
    const candidate = line ? `${line} ${word}` : word;
    if (measure(candidate) <= maxWidth) { line = candidate; continue; }
    if (line) { lines.push(line); line = ''; }
    if (measure(word) <= maxWidth) { line = word; continue; }
    for (const character of Array.from(word)) {
      if (line && measure(line + character) > maxWidth) { lines.push(line); line = ''; }
      line += character;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function splitAtlasSpace(spaces, used) {
  const next = [];
  for (const space of spaces) {
    const right = space.x + space.width;
    const bottom = space.y + space.height;
    const usedRight = used.x + used.width;
    const usedBottom = used.y + used.height;
    if (used.x >= right || usedRight <= space.x || used.y >= bottom || usedBottom <= space.y) {
      next.push(space);
      continue;
    }
    if (used.x > space.x) next.push({ ...space, width: used.x - space.x });
    if (usedRight < right) next.push({ ...space, x: usedRight, width: right - usedRight });
    if (used.y > space.y) next.push({ ...space, height: used.y - space.y });
    if (usedBottom < bottom) next.push({ ...space, y: usedBottom, height: bottom - usedBottom });
  }
  return next.filter((space, index) => !next.some((other, otherIndex) => otherIndex !== index
    && other.x <= space.x && other.y <= space.y
    && other.x + other.width >= space.x + space.width
    && other.y + other.height >= space.y + space.height
    && (other.width * other.height > space.width * space.height || otherIndex < index)));
}

/** Pack all chips into bounded free rectangles or request a smaller font. */
export function packPlanetLabelAtlas(labels, measure, {
  width = 2048, height = 1024, maxTextWidth = 220, lineHeight = 24,
  measureValue = measure, valueLineHeight = lineHeight,
  paddingX = 12, paddingY = 8, lineGap = 4, tailHeight = 0, splitWords = false,
} = {}) {
  const measured = labels.map((label, index) => {
    const nameLines = wrapPlanetLabel(label.text, measure, maxTextWidth, { splitWords });
    const valueLine = label.hasValue ? label.valueText : '';
    const valueLines = valueLine
      ? measureValue(valueLine) <= maxTextWidth || !label.numberText || !label.unitText
        ? [valueLine]
        : [label.numberText, ...wrapPlanetLabel(label.unitText, measureValue, maxTextWidth)]
      : [];
    const valueWidth = Math.max(...valueLines.map(measureValue), 0);
    const nameWidth = Math.ceil(Math.max(...nameLines.map(measure), 1)) + 2 * paddingX;
    const labelWidth = Math.ceil(Math.max(...nameLines.map(measure), valueWidth, 1)) + 2 * paddingX;
    const labelHeight = Math.ceil(nameLines.length * lineHeight
      + (valueLines.length ? lineGap + valueLines.length * valueLineHeight : 0) + 2 * paddingY + tailHeight);
    // Name-only variant (the top part of the same rectangle): every country but the selected one is shown without its value.
    const nameHeight = Math.ceil(nameLines.length * lineHeight + 2 * paddingY);
    return {
      ...label, lines: nameLines, nameLines, valueLine, valueLines,
      index, width: labelWidth, height: labelHeight, nameWidth, nameHeight,
      paddingX, paddingY, lineGap, lineHeight, valueLineHeight, tailHeight,
    };
  }).sort((a, b) => b.height - a.height || b.width - a.width || a.index - b.index);
  let spaces = [{ x: 0, y: 0, width, height }];
  const items = [];
  for (const label of measured) {
    const reservedWidth = label.width + 2;
    const reservedHeight = label.height + 2;
    let best = null;
    let bestShortSide = Infinity;
    let bestLongSide = Infinity;
    for (const space of spaces) {
      if (reservedWidth > space.width || reservedHeight > space.height) continue;
      const shortSide = Math.min(space.width - reservedWidth, space.height - reservedHeight);
      const longSide = Math.max(space.width - reservedWidth, space.height - reservedHeight);
      if (shortSide < bestShortSide || shortSide === bestShortSide && longSide < bestLongSide) {
        best = space;
        bestShortSide = shortSide;
        bestLongSide = longSide;
      }
    }
    if (!best) return null;
    const used = { x: best.x, y: best.y, width: reservedWidth, height: reservedHeight };
    items.push({ ...label, x: used.x, y: used.y });
    spaces = splitAtlasSpace(spaces, used);
  }
  return items.sort((a, b) => a.index - b.index).map(({ index: _index, ...label }) => label);
}

function minimumArea(distance) {
  if (distance <= 2) return 0;
  if (distance <= 2.5) return 0.00012;
  if (distance <= 3) return 0.0005;
  return 0.002;
}

function intersects(a, b, gap) {
  return a.left < b.right + gap && a.right + gap > b.left
    && a.top < b.bottom + gap && a.bottom + gap > b.top;
}

/**
 * Layout accepts projected CSS-pixel anchors and outward-facing dot products.
 * Selected/hovered names win collisions but never bypass hemisphere clipping.
 */
export function layoutPlanetLabels(candidates, {
  width, height, cameraDistance = 3.35, selectedCode, hoverCode,
  maxVisible = 24, padding = 6, collisionGap = 5, anchorGap = 12, globe = null, valuesOnly = false,
  // «Данные»: на шаре подписана только выбранная или наведённая страна, а не случайные крупные.
  selectionOnly = false,
  // Прямоугольники кнопок и чипов поверх шара (в тех же пикселях): подпись не заходит под них.
  keepOut = [],
  // Подписи без плашки и острия: название стоит прямо на стране, а выбранная (над маркером) поднимается на anchorGap.
  centered = false,
} = {}) {
  if (!(width > 0 && height > 0)) return [];
  const selected = normalizePlanetCountryCode(selectedCode);
  const hovered = normalizePlanetCountryCode(hoverCode);
  const priority = (candidate) => candidate.code === selected ? 2 : candidate.code === hovered ? 1 : 0;
  const visible = candidates.filter((candidate) => {
    if (![candidate.x, candidate.y, candidate.depth, candidate.facing, candidate.width, candidate.height].every(Number.isFinite)) return false;
    return candidate.facing > 0.2 && candidate.depth >= -1 && candidate.depth <= 1
      && candidate.width > 0 && candidate.height > 0
      && (!valuesOnly || candidate.hasValue || priority(candidate) > 0)
      && (!selectionOnly || priority(candidate) > 0)
      && (priority(candidate) > 0 || candidate.area >= minimumArea(cameraDistance));
  }).sort((a, b) => priority(b) - priority(a)
    || Number(Boolean(b.hasValue)) - Number(Boolean(a.hasValue))
    || b.area - a.area || a.code.localeCompare(b.code));
  const result = [];
  for (const candidate of visible) {
    const bottom = centered && priority(candidate) === 0 ? candidate.y + candidate.height / 2 : candidate.y - anchorGap;
    let box = {
      left: candidate.x - candidate.width / 2,
      right: candidate.x + candidate.width / 2,
      top: bottom - candidate.height,
      bottom,
    };
    // Подпись под чипом или кнопкой: сначала чуть сдвигаем вбок (острие остаётся над страной), иначе не рисуем.
    let shiftX = 0;
    if (keepOut.length && keepOut.some((zone) => intersects(box, zone, 2))) {
      const fits = [0.2, -0.2].find((factor) => {
        const moved = { ...box, left: box.left + factor * candidate.width, right: box.right + factor * candidate.width };
        return !keepOut.some((zone) => intersects(moved, zone, 2))
          && moved.left >= padding && moved.right <= width - padding;
      });
      if (fits === undefined) continue;
      shiftX = fits * candidate.width;
      box = { ...box, left: box.left + shiftX, right: box.right + shiftX };
    }
    if (box.left < padding || box.right > width - padding || box.top < padding || box.bottom > height - padding) continue;
    if (globe && [globe.x, globe.y, globe.radius].every(Number.isFinite)) {
      const radius = Math.max(0, globe.radius - 2);
      const corners = [[box.left, box.top], [box.right, box.top], [box.left, box.bottom], [box.right, box.bottom]];
      if (corners.some(([x, y]) => (x - globe.x) ** 2 + (y - globe.y) ** 2 > radius ** 2)) continue;
    }
    // Рядом с выбранной или наведённой страной чужие подписи не рисуются: зазор вокруг неё шире, название и число читаются без налезания.
    if (result.some((label) => intersects(box, label.box, label.active > 0 ? collisionGap * 3 : collisionGap))) continue;
    result.push({ ...candidate, box, labelX: candidate.x + shiftX, labelY: (box.top + box.bottom) / 2, active: priority(candidate) });
    if (result.length >= maxVisible) break;
  }
  return result;
}
