/**
 * Переключатель исполнения бюджета — помесячно и сглаживание по периодам.
 */

export const BUDGET_TOP_GROUPS = [
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
  BUDGET_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeBudgetViewMode,
  topGroupForMode,
} from './budgetViewModeResolve.js';

export function getTopGroup(id) {
  return BUDGET_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
