/**
 * Переключатель курса юаня — ежедневный курс и сглаживание по периодам.
 */

export const CNY_RUB_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Курс (ежедневно)',
    leafMode: 'level',
  },
  {
    id: 'agg',
    label: 'Среднее за период',
    modes: [
      { mode: 'weekly', label: 'По неделям' },
      { mode: 'monthly', label: 'По месяцам' },
      { mode: 'quarterly', label: 'По кварталам' },
      { mode: 'annual', label: 'По годам' },
    ],
  },
];

export {
  CNY_RUB_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeCnyRubViewMode,
  topGroupForMode,
} from './cnyRubViewModeResolve.js';

export function getTopGroup(id) {
  return CNY_RUB_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
