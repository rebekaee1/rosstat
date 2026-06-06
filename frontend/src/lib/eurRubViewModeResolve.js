/**
 * Режимы карточки курса евро EUR/RUB (daily + клиентские агрегаты).
 */

export const EUR_RUB_CODES = ['eur-rub'];

export const EUR_RUB_URL_MODES = [
  'level',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['weekly', 'monthly', 'quarterly', 'annual']);

export function normalizeEurRubViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return EUR_RUB_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveEurRubUrlMode(viewMode) {
  if (!viewMode) return false;
  return EUR_RUB_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeEurRubViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeEurRubViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForEurRubUrlMode(viewMode) {
  return normalizeEurRubViewMode(viewMode);
}

export function eurRubAggGranularity(viewMode) {
  const mode = normalizeEurRubViewMode(viewMode);
  const mapping = {
    weekly: 'week',
    monthly: 'month',
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isEurRubFamily(code) {
  return EUR_RUB_CODES.includes(code);
}
