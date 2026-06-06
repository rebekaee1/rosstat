/**
 * Переключатель «уровень ставки» для семейств ЦБ (срок × один режим).
 */

export const CBR_TERM_SLICE_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Уровень ставки',
    leafMode: 'level',
  },
];

export {
  CBR_TERM_SLICE_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeCbrTermSliceViewMode,
  topGroupForMode,
} from './cbrTermSliceRateResolve.js';

export function getTopGroup(id) {
  return CBR_TERM_SLICE_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup() {
  return null;
}
