/**
 * Компоненты ВВП по методу использования: квартальный ряд + годовое усреднение.
 */

export const GDP_USE_CODES = [
  'gdp-consumption',
  'gdp-government',
];

export const GDP_USE_URL_MODES = [
  'level',
  'annual',
];

const AGG_MODES = new Set(['annual']);

export function normalizeGdpUseViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return GDP_USE_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveGdpUseUrlMode(viewMode) {
  if (!viewMode) return false;
  return GDP_USE_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeGdpUseViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeGdpUseViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForGdpUseUrlMode(viewMode) {
  return normalizeGdpUseViewMode(viewMode);
}

export function gdpUseAggGranularity(viewMode) {
  const mode = normalizeGdpUseViewMode(viewMode);
  return mode === 'annual' ? 'year' : null;
}

export function isGdpUseFamily(code) {
  return GDP_USE_CODES.includes(code);
}
