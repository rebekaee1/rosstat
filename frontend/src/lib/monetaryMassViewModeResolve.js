/**
 * Денежные агрегаты М0, М1, М2 (помесячный ряд + клиентские агрегаты).
 */

export const MONETARY_MASS_CODES = [
  'm0',
  'm1',
  'm2',
];

export const MONETARY_MASS_URL_MODES = [
  'level',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['quarterly', 'annual']);

export function normalizeMonetaryMassViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return MONETARY_MASS_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveMonetaryMassUrlMode(viewMode) {
  if (!viewMode) return false;
  return MONETARY_MASS_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeMonetaryMassViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeMonetaryMassViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForMonetaryMassUrlMode(viewMode) {
  return normalizeMonetaryMassViewMode(viewMode);
}

export function monetaryMassAggGranularity(viewMode) {
  const mode = normalizeMonetaryMassViewMode(viewMode);
  const mapping = {
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isMonetaryMassFamily(code) {
  return MONETARY_MASS_CODES.includes(code);
}
