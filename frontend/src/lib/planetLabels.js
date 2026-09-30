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
export function buildPlanetLabels(entries = [], { locale = 'ru', valuesByCode = null, unit = '' } = {}) {
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
    const numberText = hasValue ? formatWorldValue(value, undefined, locale) : '';
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

/** Break at words, then Unicode code points when a single word is too wide. */
export function wrapPlanetLabel(text, measure, maxWidth) {
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
  paddingX = 12, paddingY = 8, lineGap = 4,
} = {}) {
  const measured = labels.map((label, index) => {
    const nameLines = wrapPlanetLabel(label.text, measure, maxTextWidth);
    const valueLine = label.hasValue ? label.valueText : '';
    const valueLines = valueLine
      ? measureValue(valueLine) <= maxTextWidth || !label.numberText || !label.unitText
        ? [valueLine]
        : [label.numberText, ...wrapPlanetLabel(label.unitText, measureValue, maxTextWidth)]
      : [];
    const valueWidth = Math.max(...valueLines.map(measureValue), 0);
    const labelWidth = Math.ceil(Math.max(...nameLines.map(measure), valueWidth, 1)) + 2 * paddingX;
    const labelHeight = Math.ceil(nameLines.length * lineHeight
      + (valueLines.length ? lineGap + valueLines.length * valueLineHeight : 0) + 2 * paddingY);
    return {
      ...label, lines: nameLines, nameLines, valueLine, valueLines,
      index, width: labelWidth, height: labelHeight,
      paddingX, paddingY, lineGap, lineHeight, valueLineHeight,
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
      && (priority(candidate) > 0 || candidate.area >= minimumArea(cameraDistance));
  }).sort((a, b) => priority(b) - priority(a)
    || Number(Boolean(b.hasValue)) - Number(Boolean(a.hasValue))
    || b.area - a.area || a.code.localeCompare(b.code));
  const result = [];
  for (const candidate of visible) {
    const bottom = candidate.y - anchorGap;
    const box = {
      left: candidate.x - candidate.width / 2,
      right: candidate.x + candidate.width / 2,
      top: bottom - candidate.height,
      bottom,
    };
    if (box.left < padding || box.right > width - padding || box.top < padding || box.bottom > height - padding) continue;
    if (globe && [globe.x, globe.y, globe.radius].every(Number.isFinite)) {
      const radius = Math.max(0, globe.radius - 2);
      const corners = [[box.left, box.top], [box.right, box.top], [box.left, box.bottom], [box.right, box.bottom]];
      if (corners.some(([x, y]) => (x - globe.x) ** 2 + (y - globe.y) ** 2 > radius ** 2)) continue;
    }
    if (result.some((label) => intersects(box, label.box, collisionGap))) continue;
    result.push({ ...candidate, box, labelX: candidate.x, labelY: (box.top + box.bottom) / 2, active: priority(candidate) });
    if (result.length >= maxVisible) break;
  }
  return result;
}
