/**
 * Переключатель внешнего долга — поквартально и среднее по годам.
 */

export const EXTERNAL_DEBT_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Поквартально',
    leafMode: 'level',
  },
  {
    id: 'agg',
    label: 'Среднее за период',
    modes: [
      { mode: 'annual', label: 'По годам' },
    ],
  },
];

export {
  EXTERNAL_DEBT_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeExternalDebtViewMode,
  topGroupForMode,
} from './externalDebtViewModeResolve.js';

export function getTopGroup(id) {
  return EXTERNAL_DEBT_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
