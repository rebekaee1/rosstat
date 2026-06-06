/**
 * Ставки ЦБ с разбивкой по сроку: кредиты юрлиц / физлиц / вклады.
 * На каждой карточке один режим «уровень ставки».
 */

export const CORPORATE_LOAN_CODES = [
  'credit-rate-corp-short',
  'credit-rate-corp-1to3y',
  'credit-rate-corp-over3y',
];

export const INDIVIDUAL_LOAN_CODES = [
  'credit-rate-ind-short',
  'credit-rate-ind-1to3y',
  'credit-rate-ind-over3y',
];

export const DEPOSIT_RATE_CODES = [
  'deposit-rate',
  'deposit-rate-medium',
  'deposit-rate-long',
];

export const CBR_TERM_SLICE_CODES = [
  ...CORPORATE_LOAN_CODES,
  ...INDIVIDUAL_LOAN_CODES,
  ...DEPOSIT_RATE_CODES,
];

export const CBR_TERM_SLICE_URL_MODES = ['level'];

export function normalizeCbrTermSliceViewMode(viewMode) {
  if (!viewMode || viewMode === 'level') return 'level';
  return CBR_TERM_SLICE_URL_MODES.includes(viewMode) ? viewMode : 'level';
}

export function isActiveCbrTermSliceUrlMode(viewMode) {
  if (!viewMode) return false;
  return CBR_TERM_SLICE_URL_MODES.includes(viewMode);
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

export function dataModeForCbrTermSliceUrlMode() {
  return 'level';
}

export function isCbrTermSliceFamily(code) {
  return CBR_TERM_SLICE_CODES.includes(code);
}

/** @deprecated use isCbrTermSliceFamily + CORPORATE_LOAN_CODES */
export function isCorporateLoanFamily(code) {
  return CORPORATE_LOAN_CODES.includes(code);
}
