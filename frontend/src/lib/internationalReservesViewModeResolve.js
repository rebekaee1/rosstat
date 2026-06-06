/**
 * Международные резервы РФ (еженедельный ряд + клиентские агрегаты).
 */

export const INTERNATIONAL_RESERVES_CODES = [
  'international-reserves',
];

export const INTERNATIONAL_RESERVES_URL_MODES = [
  'level',
  'monthly',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['monthly', 'quarterly', 'annual']);

export function normalizeInternationalReservesViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return INTERNATIONAL_RESERVES_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveInternationalReservesUrlMode(viewMode) {
  if (!viewMode) return false;
  return INTERNATIONAL_RESERVES_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeInternationalReservesViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeInternationalReservesViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForInternationalReservesUrlMode(viewMode) {
  return normalizeInternationalReservesViewMode(viewMode);
}

export function internationalReservesAggGranularity(viewMode) {
  const mode = normalizeInternationalReservesViewMode(viewMode);
  const mapping = {
    monthly: 'month',
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isInternationalReservesFamily(code) {
  return INTERNATIONAL_RESERVES_CODES.includes(code);
}
