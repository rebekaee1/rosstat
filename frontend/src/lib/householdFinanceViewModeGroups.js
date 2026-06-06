/**
 * Переключатель кредитов и вкладов населения — помесячно и сглаживание по периодам.
 */

export const HOUSEHOLD_FINANCE_TOP_GROUPS = [
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
  HOUSEHOLD_FINANCE_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeHouseholdFinanceViewMode,
  topGroupForMode,
} from './householdFinanceViewModeResolve.js';

export function getTopGroup(id) {
  return HOUSEHOLD_FINANCE_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
