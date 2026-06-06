/**
 * Переключатель Brent — ежедневная цена и сглаживание по периодам.
 */

export const BRENT_TOP_GROUPS = [
  {
    id: 'level',
    label: 'Цена (ежедневно)',
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
  BRENT_URL_MODES,
  expandedGroupForMode,
  highlightedTopGroup,
  normalizeBrentViewMode,
  topGroupForMode,
} from './brentViewModeResolve.js';

export function getTopGroup(id) {
  return BRENT_TOP_GROUPS.find((g) => g.id === id);
}

export function defaultSubModeForGroup(groupId) {
  const group = getTopGroup(groupId);
  if (!group?.modes) return null;
  return group.modes[0]?.mode ?? null;
}
