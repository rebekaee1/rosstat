import { geoArea } from 'd3-geo';
import { lonLatToSphere, normalizePlanetCountryCode } from './planetGeometry';

/** One geographic name per country, including countries absent from the API. */
export function buildPlanetLabels(entries = [], { locale = 'ru' } = {}) {
  const names = typeof Intl.DisplayNames === 'function'
    ? new Intl.DisplayNames([locale === 'en' ? 'en' : 'ru'], { type: 'region', fallback: 'none' })
    : null;
  const labels = new Map();
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
    labels.set(code, { id: code, code, text: name, area, position });
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

/** Shelf-pack every name or report that a smaller font is needed; never drop one. */
export function packPlanetLabelAtlas(labels, measure, {
  width = 2048, height = 1024, maxTextWidth = 220, lineHeight = 24,
} = {}) {
  const items = [];
  let x = 0;
  let y = 0;
  let rowHeight = 0;
  for (const label of labels) {
    const lines = wrapPlanetLabel(label.text, measure, maxTextWidth);
    const labelWidth = Math.ceil(Math.max(...lines.map(measure), 1)) + 12;
    const labelHeight = lines.length * lineHeight + 8;
    if (labelWidth > width) return null;
    if (x + labelWidth > width) { x = 0; y += rowHeight; rowHeight = 0; }
    if (y + labelHeight > height) return null;
    items.push({ ...label, lines, x, y, width: labelWidth, height: labelHeight });
    x += labelWidth + 2;
    rowHeight = Math.max(rowHeight, labelHeight + 2);
  }
  return items;
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
  maxVisible = 24, padding = 6, collisionGap = 5, anchorGap = 12, globe = null,
} = {}) {
  if (!(width > 0 && height > 0)) return [];
  const selected = normalizePlanetCountryCode(selectedCode);
  const hovered = normalizePlanetCountryCode(hoverCode);
  const priority = (candidate) => candidate.code === selected ? 2 : candidate.code === hovered ? 1 : 0;
  const visible = candidates.filter((candidate) => {
    if (![candidate.x, candidate.y, candidate.depth, candidate.facing, candidate.width, candidate.height].every(Number.isFinite)) return false;
    return candidate.facing > 0.2 && candidate.depth >= -1 && candidate.depth <= 1
      && candidate.width > 0 && candidate.height > 0
      && (priority(candidate) > 0 || candidate.area >= minimumArea(cameraDistance));
  }).sort((a, b) => priority(b) - priority(a) || b.area - a.area || a.code.localeCompare(b.code));
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
