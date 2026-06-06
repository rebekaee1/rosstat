/**
 * Переключатель безработицы — помесячно, квартальное среднее, 12М среднее.
 */

export const UNEMPLOYMENT_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Помесячно',
    leafMode: 'level',
  },
  {
    id: 'agg',
    label: 'Сглаживание',
    modes: [
      { mode: 'quarterly', label: 'По кварталам' },
      { mode: 'annual', label: '12М среднее' },
    ],
  },
];

export {
  UNEMPLOYMENT_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeUnemploymentViewMode,
  topGroupForMode,
} from './unemploymentViewModeResolve.js';

export function getTopGroup(id) {
  return UNEMPLOYMENT_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
