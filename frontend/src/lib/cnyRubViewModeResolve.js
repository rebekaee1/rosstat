/**
 * Режимы карточки курса юаня CNY/RUB (daily + клиентские агрегаты).
 */

export const CNY_RUB_CODES = ['cny-rub'];

export const CNY_RUB_URL_MODES = [
  'level',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['weekly', 'monthly', 'quarterly', 'annual']);

export function normalizeCnyRubViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return CNY_RUB_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveCnyRubUrlMode(viewMode) {
  if (!viewMode) return false;
  return CNY_RUB_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeCnyRubViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeCnyRubViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForCnyRubUrlMode(viewMode) {
  return normalizeCnyRubViewMode(viewMode);
}

export function cnyRubAggGranularity(viewMode) {
  const mode = normalizeCnyRubViewMode(viewMode);
  const mapping = {
    weekly: 'week',
    monthly: 'month',
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isCnyRubFamily(code) {
  return CNY_RUB_CODES.includes(code);
}
