/**
 * Режимы карточки курса доллара USD/RUB (daily + клиентские агрегаты).
 */

export const USD_RUB_CODES = ['usd-rub'];

export const USD_RUB_URL_MODES = [
  'level',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['weekly', 'monthly', 'quarterly', 'annual']);

export function normalizeUsdRubViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return USD_RUB_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveUsdRubUrlMode(viewMode) {
  if (!viewMode) return false;
  return USD_RUB_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeUsdRubViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeUsdRubViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForUsdRubUrlMode(viewMode) {
  return normalizeUsdRubViewMode(viewMode);
}

export function usdRubAggGranularity(viewMode) {
  const mode = normalizeUsdRubViewMode(viewMode);
  const mapping = {
    weekly: 'week',
    monthly: 'month',
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isUsdRubFamily(code) {
  return USD_RUB_CODES.includes(code);
}
