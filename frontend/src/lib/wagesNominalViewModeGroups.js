/**
 * Переключатель средней зарплаты — уровень и динамика.
 */

export const WAGES_NOMINAL_TOP_GROUPS = [
  {
    id: 'amount',
    label: 'Уровень',
    modes: [
      { mode: 'level', label: 'Помесячно' },
      { mode: 'annual', label: 'С 1991 года' },
    ],
  },
  {
    id: 'dynamics',
    label: 'Динамика',
    modes: [
      { mode: 'real', label: 'Реальная' },
      { mode: 'yoy', label: 'Год к году' },
      { mode: 'index', label: 'Индекс 2015=100' },
    ],
  },
];

export {
  WAGES_NOMINAL_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeWagesNominalViewMode,
  topGroupForMode,
} from './wagesNominalViewModeResolve.js';

export function getTopGroup(id) {
  return WAGES_NOMINAL_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
