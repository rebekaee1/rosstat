/**
 * URL-режимы ипотеки: один канонический режим «уровень ставки».
 */

export const MORTGAGE_RATE_CODES = ['mortgage-rate'];

export const MORTGAGE_RATE_URL_MODES = ['level'];

export function normalizeMortgageViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return MORTGAGE_RATE_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveMortgageUrlMode(viewMode) {
  if (!viewMode) return false;
  return MORTGAGE_RATE_URL_MODES.includes(viewMode);
}

export function topGroupForMode() {
  return 'level';
}

export function expandedGroupForMode() {
  return null;
}

export function highlightedTopGroup(expandedGroupId) {
  return expandedGroupId ?? 'level';
}

export function dataModeForMortgageUrlMode() {
  return 'level';
}
