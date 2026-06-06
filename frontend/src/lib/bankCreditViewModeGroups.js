/**
 * Переключатель портфеля кредитов — помесячно и сглаживание по периодам.
 */

export const BANK_CREDIT_TOP_GROUPS = [
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
  BANK_CREDIT_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeBankCreditViewMode,
  topGroupForMode,
} from './bankCreditViewModeResolve.js';

export function getTopGroup(id) {
  return BANK_CREDIT_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
