/**
 * Режимы карточек федерального бюджета (помесячный ряд + клиентские агрегаты).
 */

export const BUDGET_CODES = [
  'budget-deficit',
  'budget-revenue',
  'budget-expenditure',
];

export const BUDGET_URL_MODES = [
  'level',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['quarterly', 'annual']);

export function normalizeBudgetViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return BUDGET_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveBudgetUrlMode(viewMode) {
  if (!viewMode) return false;
  return BUDGET_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeBudgetViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeBudgetViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForBudgetUrlMode(viewMode) {
  return normalizeBudgetViewMode(viewMode);
}

export function budgetAggGranularity(viewMode) {
  const mode = normalizeBudgetViewMode(viewMode);
  const mapping = {
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isBudgetFamily(code) {
  return BUDGET_CODES.includes(code);
}
