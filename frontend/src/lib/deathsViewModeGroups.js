/**
 * Переключатель смертемости — уровень и темп г/г.
 */

export const DEATHS_TOP_GROUPS = [
  {
    id: 'level',
    label: 'За год',
    leafMode: 'level',
  },
  {
    id: 'yoy',
    label: 'Год к году',
    leafMode: 'yoy',
  },
];

export {
  DEATHS_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeDeathsViewMode,
  topGroupForMode,
} from './deathsViewModeResolve.js';

export function getTopGroup(id) {
  return DEATHS_TOP_GROUPS.find((g) => g.id === id);
}
