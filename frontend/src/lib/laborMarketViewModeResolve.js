/**
 * Рабочая сила и занятое население (помесячный ряд + клиентские агрегаты).
 */

export const LABOR_MARKET_CODES = [
  'labor-force',
  'employment',
];

export const LABOR_MARKET_URL_MODES = [
  'level',
  'quarterly',
  'annual',
];

const AGG_MODES = new Set(['quarterly', 'annual']);

export function normalizeLaborMarketViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return LABOR_MARKET_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveLaborMarketUrlMode(viewMode) {
  if (!viewMode) return false;
  return LABOR_MARKET_URL_MODES.includes(viewMode);
}

export function topGroupForMode(viewMode) {
  const mode = normalizeLaborMarketViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : 'level';
}

export function expandedGroupForMode(viewMode) {
  const mode = normalizeLaborMarketViewMode(viewMode);
  return AGG_MODES.has(mode) ? 'agg' : null;
}

export function highlightedTopGroup(expandedGroupId, currentMode) {
  return expandedGroupId ?? topGroupForMode(currentMode);
}

export function dataModeForLaborMarketUrlMode(viewMode) {
  return normalizeLaborMarketViewMode(viewMode);
}

export function laborMarketAggGranularity(viewMode) {
  const mode = normalizeLaborMarketViewMode(viewMode);
  const mapping = {
    quarterly: 'quarter',
    annual: 'year',
  };
  return mapping[mode] ?? null;
}

export function isLaborMarketFamily(code) {
  return LABOR_MARKET_CODES.includes(code);
}
