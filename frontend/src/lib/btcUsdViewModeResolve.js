/**
 * Режимы карточки BTC/USD (daily + клиентские агрегаты).
 */

export const BTC_USD_CODES = ['btc-usd'];

export const BTC_USD_URL_MODES = [
  'level',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['weekly', 'monthly', 'quarterly', 'annual']);

export function normalizeBtcUsdViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return BTC_USD_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveBtcUsdUrlMode(viewMode) {
  if (!viewMode) return false;
  return BTC_USD_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeBtcUsdViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeBtcUsdViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForBtcUsdUrlMode(viewMode) {
  return normalizeBtcUsdViewMode(viewMode);
}

export function btcUsdAggGranularity(viewMode) {
  const mode = normalizeBtcUsdViewMode(viewMode);
  const mapping = {
    weekly: 'week',
    monthly: 'month',
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isBtcUsdFamily(code) {
  return BTC_USD_CODES.includes(code);
}
