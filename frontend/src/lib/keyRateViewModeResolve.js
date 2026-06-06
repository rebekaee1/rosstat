/**
 * Режимы карточки ключевой ставки ЦБ (daily + клиентские агрегаты).
 */

export const KEY_RATE_CODES = ['key-rate'];

export const KEY_RATE_URL_MODES = [
  'level',
  'weekly',
  'monthly',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['weekly', 'monthly', 'quarterly', 'annual']);

export function normalizeKeyRateViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return KEY_RATE_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveKeyRateUrlMode(viewMode) {
  if (!viewMode) return false;
  return KEY_RATE_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeKeyRateViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeKeyRateViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForKeyRateUrlMode(viewMode) {
  return normalizeKeyRateViewMode(viewMode);
}

export function keyRateAggGranularity(viewMode) {
  const mode = normalizeKeyRateViewMode(viewMode);
  const mapping = {
    weekly: 'week',
    monthly: 'month',
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isKeyRateFamily(code) {
  return KEY_RATE_CODES.includes(code);
}
