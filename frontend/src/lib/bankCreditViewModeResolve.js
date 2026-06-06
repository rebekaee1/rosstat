/**
 * Портфель кредитов банковского сектора (помесячный ряд + клиентские агрегаты).
 */

export const BANK_CREDIT_CODES = [
  'business-credit',
];

export const BANK_CREDIT_URL_MODES = [
  'level',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['quarterly', 'annual']);

export function normalizeBankCreditViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return BANK_CREDIT_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveBankCreditUrlMode(viewMode) {
  if (!viewMode) return false;
  return BANK_CREDIT_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeBankCreditViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeBankCreditViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForBankCreditUrlMode(viewMode) {
  return normalizeBankCreditViewMode(viewMode);
}

export function bankCreditAggGranularity(viewMode) {
  const mode = normalizeBankCreditViewMode(viewMode);
  const mapping = {
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isBankCreditFamily(code) {
  return BANK_CREDIT_CODES.includes(code);
}
