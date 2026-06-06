/**
 * Переключатель RUONIA — уровень (ежедневно) и сглаживание по периодам.
 */

export const RUONIA_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Уровень ставки',
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
  RUONIA_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeRuoniaViewMode,
  topGroupForMode,
} from './ruoniaViewModeResolve.js';

export function getTopGroup(id) {
  return RUONIA_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
