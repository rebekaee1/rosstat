/**
 * Переключатель ипотеки — один режим «уровень ставки».
 */

export const MORTGAGE_RATE_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Уровень ставки',
    leafMode: 'level',
  },
];

export {
  MORTGAGE_RATE_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeMortgageViewMode,
  topGroupForMode,
} from './mortgageRateViewModeResolve.js';

export function getTopGroup(id) {
  return MORTGAGE_RATE_TOP_GROUPS.find((g) => g.id === id);
}
