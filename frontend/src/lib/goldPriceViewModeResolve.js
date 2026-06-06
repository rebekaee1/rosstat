/**
 * Учётная цена золота Банка России (daily + клиентские агрегаты).
 */

export const GOLD_PRICE_CODES = [
  'gold-price',
];

export const GOLD_PRICE_URL_MODES = [
  'level',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['weekly', 'monthly', 'quarterly', 'annual']);

export function normalizeGoldPriceViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return GOLD_PRICE_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveGoldPriceUrlMode(viewMode) {
  if (!viewMode) return false;
  return GOLD_PRICE_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeGoldPriceViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeGoldPriceViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForGoldPriceUrlMode(viewMode) {
  return normalizeGoldPriceViewMode(viewMode);
}

export function goldPriceAggGranularity(viewMode) {
  const mode = normalizeGoldPriceViewMode(viewMode);
  const mapping = {
    weekly: 'week',
    monthly: 'month',
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isGoldPriceFamily(code) {
  return GOLD_PRICE_CODES.includes(code);
}
