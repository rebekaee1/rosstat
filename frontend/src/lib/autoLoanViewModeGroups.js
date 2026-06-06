/**
 * Переключатель автокредитов — та же оболочка, что у ИПЦ/ИЦП,
 * одна верхняя кнопка (уровень ставки).
 */

export const AUTO_LOAN_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Уровень ставки',
    leafMode: 'level',
  },
];

export {
  AUTO_LOAN_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeAutoLoanViewMode,
  topGroupForMode,
} from './autoLoanViewModeResolve.js';

export function getTopGroup(id) {
  return AUTO_LOAN_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup() {
  return null;
}
