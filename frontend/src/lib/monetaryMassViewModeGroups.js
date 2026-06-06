/**
 * Переключатель денежных агрегатов — помесячно и сглаживание по периодам.
 */

export const MONETARY_MASS_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Помесячно',
    leafMode: 'level',
  },
  {
    id: 'agg',
    label: 'Среднее за период',
    modes: [
      { mode: 'quarterly', label: 'По кварталам' },
      { mode: 'annual', label: 'По годам' },
    ],
  },
];

export {
  MONETARY_MASS_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeMonetaryMassViewMode,
  topGroupForMode,
} from './monetaryMassViewModeResolve.js';

export function getTopGroup(id) {
  return MONETARY_MASS_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
