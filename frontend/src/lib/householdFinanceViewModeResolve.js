/**
 * Кредиты и вклады физических лиц (помесячный ряд + клиентские агрегаты).
 */

export const HOUSEHOLD_FINANCE_CODES = [
  'consumer-credit',
  'deposits-individual',
];

export const HOUSEHOLD_FINANCE_URL_MODES = [
  'level',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['quarterly', 'annual']);

export function normalizeHouseholdFinanceViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return HOUSEHOLD_FINANCE_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveHouseholdFinanceUrlMode(viewMode) {
  if (!viewMode) return false;
  return HOUSEHOLD_FINANCE_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeHouseholdFinanceViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeHouseholdFinanceViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForHouseholdFinanceUrlMode(viewMode) {
  return normalizeHouseholdFinanceViewMode(viewMode);
}

export function householdFinanceAggGranularity(viewMode) {
  const mode = normalizeHouseholdFinanceViewMode(viewMode);
  const mapping = {
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isHouseholdFinanceFamily(code) {
  return HOUSEHOLD_FINANCE_CODES.includes(code);
}
