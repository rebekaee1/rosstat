/**
 * URL-режимы автокредитов: один канонический режим «уровень ставки».
 */

export const AUTO_LOAN_CODES = ['auto-loan-rate'];

export const AUTO_LOAN_URL_MODES = ['level'];

export function normalizeAutoLoanViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return AUTO_LOAN_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveAutoLoanUrlMode(viewMode) {
  if (!viewMode) return false;
  return AUTO_LOAN_URL_MODES.includes(viewMode);
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

export function dataModeForAutoLoanUrlMode() {
  return 'level';
}
