/**
 * Внешний долг РФ (квартальный ряд + годовое усреднение на клиенте).
 */

export const EXTERNAL_DEBT_CODES = [
  'external-debt',
];

export const EXTERNAL_DEBT_URL_MODES = [
  'level',
  'annual',
];

const AGG_MODES = new Set(['annual']);

export function normalizeExternalDebtViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return EXTERNAL_DEBT_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveExternalDebtUrlMode(viewMode) {
  if (!viewMode) return false;
  return EXTERNAL_DEBT_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeExternalDebtViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeExternalDebtViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForExternalDebtUrlMode(viewMode) {
  return normalizeExternalDebtViewMode(viewMode);
}

export function externalDebtAggGranularity(viewMode) {
  const mode = normalizeExternalDebtViewMode(viewMode);
  return mode === 'annual' ? 'year' : null;
}

export function isExternalDebtFamily(code) {
  return EXTERNAL_DEBT_CODES.includes(code);
}
