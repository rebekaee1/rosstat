/**
 * Режимы карточки нефти Brent (daily + клиентские агрегаты).
 */

export const BRENT_CODES = ['brent'];

export const BRENT_URL_MODES = [
  'level',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['weekly', 'monthly', 'quarterly', 'annual']);

export function normalizeBrentViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return BRENT_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveBrentUrlMode(viewMode) {
  if (!viewMode) return false;
  return BRENT_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeBrentViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeBrentViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForBrentUrlMode(viewMode) {
  return normalizeBrentViewMode(viewMode);
}

export function brentAggGranularity(viewMode) {
  const mode = normalizeBrentViewMode(viewMode);
  const mapping = {
    weekly: 'week',
    monthly: 'month',
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isBrentFamily(code) {
  return BRENT_CODES.includes(code);
}
