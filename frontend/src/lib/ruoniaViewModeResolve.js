/**
 * Режимы карточки RUONIA (daily + клиентские агрегаты).
 */

export const RUONIA_CODES = ['ruonia'];

export const RUONIA_URL_MODES = [
  'level',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['weekly', 'monthly', 'quarterly', 'annual']);

export function normalizeRuoniaViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return RUONIA_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveRuoniaUrlMode(viewMode) {
  if (!viewMode) return false;
  return RUONIA_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeRuoniaViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeRuoniaViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForRuoniaUrlMode(viewMode) {
  return normalizeRuoniaViewMode(viewMode);
}

export function ruoniaAggGranularity(viewMode) {
  const mode = normalizeRuoniaViewMode(viewMode);
  const mapping = {
    weekly: 'week',
    monthly: 'month',
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isRuoniaFamily(code) {
  return RUONIA_CODES.includes(code);
}
